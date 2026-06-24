import argparse
import sys

from .corpus.cli import cmd_corpus_inventory, cmd_corpus_verify, register_corpus_subparser
from .index.cli import (
    cmd_index_build,
    cmd_index_query_elements,
    cmd_index_query_files,
    cmd_index_query_stats,
    cmd_index_verify,
    register_index_subparser,
)
from .manifest.cli import cmd_manifest_create, cmd_manifest_verify, register_manifest_subparser
from .references.cli import (
    cmd_references_extract,
    cmd_references_query,
    cmd_references_verify,
    register_references_subparser,
)
from .scenario.cli import cmd_migrate, register_migrate_subparser, register_scenario_subparser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="peoplenet-process-extractor",
        description="PeopleNet Process Extractor",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Canonical: scenario migrate
    register_scenario_subparser(sub)

    # Deprecated alias: migrate (kept for backward compatibility)
    register_migrate_subparser(sub)

    register_manifest_subparser(sub)
    register_corpus_subparser(sub)
    register_index_subparser(sub)
    register_references_subparser(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scenario":
        if args.scenario_command == "migrate":
            return cmd_migrate(args)

    if args.command == "migrate":
        return cmd_migrate(args)

    if args.command == "manifest":
        if args.manifest_command == "create":
            return cmd_manifest_create(args)
        if args.manifest_command == "verify":
            return cmd_manifest_verify(args)

    if args.command == "corpus":
        if args.corpus_command == "inventory":
            return cmd_corpus_inventory(args)
        if args.corpus_command == "verify":
            return cmd_corpus_verify(args)

    if args.command == "index":
        if args.index_command == "build":
            return cmd_index_build(args)
        if args.index_command == "verify":
            return cmd_index_verify(args)
        if args.index_command == "query":
            if args.query_command == "files":
                return cmd_index_query_files(args)
            if args.query_command == "elements":
                return cmd_index_query_elements(args)
            if args.query_command == "stats":
                return cmd_index_query_stats(args)

    if args.command == "references":
        if args.references_command == "extract":
            return cmd_references_extract(args)
        if args.references_command == "verify":
            return cmd_references_verify(args)
        if args.references_command == "query":
            return cmd_references_query(args)

    print(f"Unknown command: {args.command}", file=sys.stderr)
    return 1
