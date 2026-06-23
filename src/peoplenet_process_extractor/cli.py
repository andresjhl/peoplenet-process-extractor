import argparse
import sys

from .manifest.cli import cmd_manifest_create, cmd_manifest_verify, register_manifest_subparser
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

    print(f"Unknown command: {args.command}", file=sys.stderr)
    return 1
