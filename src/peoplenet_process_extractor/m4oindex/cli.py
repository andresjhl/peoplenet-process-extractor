"""
CLI for m4object-node-index-v1 commands:
  m4object-node-index build   -- build the index from a corpus manifest
  m4object-node-index verify  -- verify an existing index artifact
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .service import build_node_index, verify_node_index


def register_m4oindex_subparser(
    sub: argparse._SubParsersAction,  # type: ignore[type-arg]
) -> None:
    m4o = sub.add_parser(
        "m4object-node-index",
        help="Meta4Object node index commands",
    )
    m4o_sub = m4o.add_subparsers(dest="m4oindex_command", required=True)
    _register_build(m4o_sub)
    _register_verify(m4o_sub)


def _register_build(
    sub: argparse._SubParsersAction,  # type: ignore[type-arg]
) -> None:
    p = sub.add_parser("build", help="Build m4object-node-index-v1 from a corpus manifest")
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
        help="Output path for the m4object-node-index.json.",
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
            "Fix the created_at timestamp (ISO-8601 UTC, e.g. 2026-06-24T12:00:00+00:00). "
            "Two runs with the same inputs and timestamp produce byte-identical output."
        ),
    )


def _register_verify(
    sub: argparse._SubParsersAction,  # type: ignore[type-arg]
) -> None:
    p = sub.add_parser("verify", help="Verify an m4object-node-index-v1 artifact")
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
        help="Path to the m4object-node-index.json.",
    )


def cmd_m4oindex_build(args: argparse.Namespace) -> int:
    corpus_root = Path(args.corpus_root)
    manifest_path = Path(args.corpus_manifest)
    output_path = Path(args.output)

    now: datetime | None = None
    if args.created_at is not None:
        try:
            now = datetime.fromisoformat(args.created_at)
        except ValueError as exc:
            print(
                f"Error: --created-at is not a valid ISO-8601 timestamp: {exc}",
                file=sys.stderr,
            )
            return 1
        if now.tzinfo is None or now.utcoffset().total_seconds() != 0:
            print(
                f"Error: --created-at must be UTC (e.g. +00:00 or Z), "
                f"got: {args.created_at!r}.",
                file=sys.stderr,
            )
            return 1
        now = now.astimezone(timezone.utc)

    exit_code, messages = build_node_index(
        corpus_root=corpus_root,
        manifest_path=manifest_path,
        output_path=output_path,
        force=args.force,
        now=now,
    )
    _print_messages(messages, exit_code)
    return exit_code


def cmd_m4oindex_verify(args: argparse.Namespace) -> int:
    corpus_root = Path(args.corpus_root)
    manifest_path = Path(args.corpus_manifest)
    index_path = Path(args.index)

    exit_code, messages = verify_node_index(
        corpus_root=corpus_root,
        manifest_path=manifest_path,
        index_path=index_path,
    )
    _print_messages(messages, exit_code)
    return exit_code


def _print_messages(messages: list[str], exit_code: int) -> None:
    for msg in messages:
        if msg.startswith("Error:") or msg.startswith("Manifest validation error"):
            print(msg, file=sys.stderr)
        elif msg.startswith("  Warning:") or msg.startswith("Warning:"):
            print(msg, file=sys.stderr)
        else:
            stream = sys.stdout if exit_code == 0 else sys.stderr
            print(msg, file=stream)
