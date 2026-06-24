"""
CLI for reference-extraction-v1 commands:
  references extract  -- extract Call() references from a corpus
  references verify   -- verify an existing extraction artifact
  references query    -- query an extraction artifact
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .extraction import extract_references
from .queries import query_references
from .validation import verify_extraction


def register_references_subparser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    refs = sub.add_parser("references", help="Reference extraction commands")
    refs_sub = refs.add_subparsers(dest="references_command", required=True)

    _register_extract(refs_sub)
    _register_verify(refs_sub)
    _register_query(refs_sub)


def _register_extract(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = sub.add_parser("extract", help="Extract Call() references from a corpus")
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
        "--index",
        required=True,
        help="Path to the structural-index.sqlite.",
    )
    p.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output path for the reference-extraction.json.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing output file.",
    )
    p.add_argument(
        "--created-at",
        dest="created_at",
        default=None,
        metavar="ISO8601_UTC",
        help=(
            "Fix the created_at timestamp (ISO-8601 UTC, e.g. 2026-06-24T12:00:00+00:00 or "
            "2026-06-24T12:00:00Z). "
            "Two runs with the same value and identical inputs produce byte-identical output."
        ),
    )


def _register_verify(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = sub.add_parser("verify", help="Verify a reference extraction artifact")
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
        "--index",
        required=True,
        help="Path to the structural-index.sqlite.",
    )
    p.add_argument(
        "--references",
        required=True,
        help="Path to the reference-extraction.json.",
    )


def _register_query(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = sub.add_parser("query", help="Query a reference extraction artifact")
    p.add_argument(
        "--references",
        required=True,
        help="Path to the reference-extraction.json.",
    )
    p.add_argument("--path", default=None, help="Filter by file path.")
    p.add_argument("--status", default=None, help="Filter by reference status.")
    p.add_argument("--function-name", dest="function_name", default=None, help="Filter by function name.")
    p.add_argument("--kind", default=None, help="Filter by reference kind.")
    p.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON.")


def cmd_references_extract(args: argparse.Namespace) -> int:
    corpus_root = Path(args.corpus_root)
    manifest_path = Path(args.corpus_manifest)
    index_path = Path(args.index)
    output_path = Path(args.output)

    now: datetime | None = None
    if args.created_at is not None:
        try:
            now = datetime.fromisoformat(args.created_at)
        except ValueError as exc:
            print(f"Error: --created-at is not a valid ISO-8601 timestamp: {exc}", file=sys.stderr)
            return 1
        if now.tzinfo is None or now.utcoffset().total_seconds() != 0:
            print(
                f"Error: --created-at must be a UTC timestamp (e.g. +00:00 or Z), "
                f"got: {args.created_at!r}.",
                file=sys.stderr,
            )
            return 1
        now = now.astimezone(timezone.utc)

    exit_code, messages = extract_references(
        corpus_root=corpus_root,
        manifest_path=manifest_path,
        index_path=index_path,
        output_path=output_path,
        force=args.force,
        now=now,
    )

    _print_messages(messages, exit_code)
    return exit_code


def cmd_references_verify(args: argparse.Namespace) -> int:
    corpus_root = Path(args.corpus_root)
    manifest_path = Path(args.corpus_manifest)
    index_path = Path(args.index)
    extraction_path = Path(args.references)

    exit_code, messages = verify_extraction(
        corpus_root=corpus_root,
        manifest_path=manifest_path,
        index_path=index_path,
        extraction_path=extraction_path,
    )

    _print_messages(messages, exit_code)
    return exit_code


def cmd_references_query(args: argparse.Namespace) -> int:
    extraction_path = Path(args.references)

    try:
        rows = query_references(
            extraction_path,
            path=args.path,
            status=args.status,
            function_name=args.function_name,
            kind=args.kind,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        data = [
            {
                "path": r.path,
                "reference_id": r.reference_id,
                "kind": r.kind,
                "function_name": r.function_name,
                "status": r.status,
                "line_start": r.line_start,
                "column_start": r.column_start,
                "raw_expression": r.raw_expression,
            }
            for r in rows
        ]
        print(json.dumps(data, indent=2))
        return 0

    if not rows:
        print("No references found.")
        return 0

    print(f"{'path':<50} {'line':<6} {'col':<6} {'status':<18} {'expression'}")
    print("-" * 110)
    for r in rows:
        expr_short = r.raw_expression[:40].replace("\n", "\\n").replace("\r", "\\r")
        print(
            f"{r.path:<50} {r.line_start:<6} {r.column_start:<6} {r.status:<18} {expr_short}"
        )
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
