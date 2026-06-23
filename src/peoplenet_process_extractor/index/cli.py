"""
CLI for structural-index-v1 commands:
  index build   -- build a structural index from a corpus manifest
  index verify  -- verify an existing index
  index query   -- query the index (subcommands: files, elements, stats)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .queries import query_elements, query_files, query_stats
from .service import build_index_service, verify_index_service


def register_index_subparser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    index = sub.add_parser("index", help="Structural index commands")
    index_sub = index.add_subparsers(dest="index_command", required=True)

    _register_build(index_sub)
    _register_verify(index_sub)
    _register_query(index_sub)


def _register_build(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = sub.add_parser("build", help="Build a structural index from a corpus manifest")
    p.add_argument(
        "--corpus-root",
        dest="corpus_root",
        required=True,
        help="Path to the corpus directory.",
    )
    p.add_argument(
        "--corpus-manifest",
        dest="corpus_manifest",
        required=True,
        help="Path to the corpus-manifest.json.",
    )
    p.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output path for the structural-index.sqlite.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing output file.",
    )


def _register_verify(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = sub.add_parser("verify", help="Verify a structural index against a corpus and manifest")
    p.add_argument(
        "--corpus-root",
        dest="corpus_root",
        required=True,
        help="Path to the corpus directory.",
    )
    p.add_argument(
        "--corpus-manifest",
        dest="corpus_manifest",
        required=True,
        help="Path to the corpus-manifest.json.",
    )
    p.add_argument(
        "--database",
        "-d",
        dest="database",
        required=True,
        help="Path to the structural-index.sqlite.",
    )


def _register_query(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    query = sub.add_parser("query", help="Query a structural index")
    query_sub = query.add_subparsers(dest="query_command", required=True)

    # index query files
    files_p = query_sub.add_parser("files", help="Query source files")
    files_p.add_argument("--database", "-d", dest="database", required=True)
    files_p.add_argument("--path", default=None, help="Filter by exact path.")
    files_p.add_argument("--classification", default=None, help="Filter by classification.")
    files_p.add_argument("--source-root", dest="source_root", default=None)
    files_p.add_argument("--extension", default=None)
    files_p.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON.")

    # index query elements
    elem_p = query_sub.add_parser("elements", help="Query structural elements")
    elem_p.add_argument("--database", "-d", dest="database", required=True)
    elem_p.add_argument("--meta4object", default=None)
    elem_p.add_argument("--item-type", dest="item_type", default=None)
    elem_p.add_argument("--item-name", dest="item_name", default=None)
    elem_p.add_argument("--rule-id", dest="rule_id", default=None)
    elem_p.add_argument("--source-root", dest="source_root", default=None)
    elem_p.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON.")

    # index query stats
    stats_p = query_sub.add_parser("stats", help="Show index statistics")
    stats_p.add_argument("--database", "-d", dest="database", required=True)
    stats_p.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON.")


def cmd_index_build(args: argparse.Namespace) -> int:
    corpus_root = Path(args.corpus_root)
    manifest_path = Path(args.corpus_manifest)
    output_path = Path(args.output)

    exit_code, messages = build_index_service(
        corpus_root=corpus_root,
        manifest_path=manifest_path,
        output_path=output_path,
        force=args.force,
    )

    _print_messages(messages, exit_code)
    return exit_code


def cmd_index_verify(args: argparse.Namespace) -> int:
    corpus_root = Path(args.corpus_root)
    manifest_path = Path(args.corpus_manifest)
    db_path = Path(args.database)

    exit_code, messages = verify_index_service(
        corpus_root=corpus_root,
        manifest_path=manifest_path,
        db_path=db_path,
    )

    _print_messages(messages, exit_code)
    return exit_code


def cmd_index_query_files(args: argparse.Namespace) -> int:
    db_path = Path(args.database)
    try:
        rows = query_files(
            db_path,
            path=args.path,
            classification=args.classification,
            source_root=args.source_root,
            extension=args.extension,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        data = [
            {
                "path": r.path,
                "sha256": r.sha256,
                "size_bytes": r.size_bytes,
                "extension": r.extension,
                "source_root": r.source_root,
                "classification": r.classification,
                "warning_count": r.warning_count,
            }
            for r in rows
        ]
        print(json.dumps(data, indent=2))
        return 0

    if not rows:
        print("No files found.")
        return 0

    print(f"{'path':<60} {'classification':<20} {'source_root':<15} {'ext':<8}")
    print("-" * 103)
    for r in rows:
        print(
            f"{r.path:<60} {r.classification:<20} {(r.source_root or ''):<15} {r.extension:<8}"
        )
    return 0


def cmd_index_query_elements(args: argparse.Namespace) -> int:
    db_path = Path(args.database)
    try:
        rows = query_elements(
            db_path,
            meta4object=args.meta4object,
            item_type=args.item_type,
            item_name=args.item_name,
            rule_id=args.rule_id,
            source_root=args.source_root,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        data = [
            {
                "path": r.path,
                "source_root": r.source_root,
                "meta4object": r.meta4object,
                "item_type": r.item_type,
                "item_name": r.item_name,
                "rule_id": r.rule_id,
                "rule_date": r.rule_date,
            }
            for r in rows
        ]
        print(json.dumps(data, indent=2))
        return 0

    if not rows:
        print("No elements found.")
        return 0

    print(f"{'meta4object':<20} {'item_type':<15} {'item_name':<25} {'rule_id':<10} {'rule_date':<12}")
    print("-" * 82)
    for r in rows:
        print(
            f"{r.meta4object:<20} {r.item_type:<15} {r.item_name:<25} "
            f"{(r.rule_id or ''):<10} {(r.rule_date or ''):<12}"
        )
    return 0


def cmd_index_query_stats(args: argparse.Namespace) -> int:
    db_path = Path(args.database)
    try:
        stats = query_stats(db_path)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        data = {
            "total_files": stats.total_files,
            "structured_files": stats.structured_files,
            "unstructured_files": stats.unstructured_files,
            "by_classification": stats.by_classification,
            "by_source_root": stats.by_source_root,
            "by_item_type": stats.by_item_type,
        }
        print(json.dumps(data, indent=2))
        return 0

    print(f"Total files    : {stats.total_files}")
    print(f"Structured     : {stats.structured_files}")
    print(f"Unstructured   : {stats.unstructured_files}")

    if stats.by_classification:
        print("\nBy classification:")
        for cls, count in sorted(stats.by_classification.items()):
            print(f"  {cls:<25} {count}")

    if stats.by_source_root:
        print("\nBy source root:")
        for root, count in sorted(stats.by_source_root.items()):
            label = root or "(corpus root)"
            print(f"  {label:<25} {count}")

    if stats.by_item_type:
        print("\nBy item type:")
        for itype, count in sorted(stats.by_item_type.items()):
            print(f"  {itype:<25} {count}")

    return 0


def _print_messages(messages: list[str], exit_code: int) -> None:
    for msg in messages:
        if msg.startswith("Error:") or msg.startswith("Validation error"):
            print(msg, file=sys.stderr)
        elif msg.startswith("  Warning:") or msg.startswith("Warning:"):
            print(msg, file=sys.stderr)
        else:
            stream = sys.stdout if exit_code == 0 else sys.stderr
            print(msg, file=stream)
