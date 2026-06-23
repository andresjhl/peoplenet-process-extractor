import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .migration import MigrationError, migrate_from_legacy
from .serialization import serialize_report, serialize_scenario
from .validation import validate


def register_migrate_subparser(sub: argparse._SubParsersAction) -> None:
    mig = sub.add_parser("migrate", help="Migrate a legacy peoplenet_call.json to scenario-v1")
    mig.add_argument("input", help="Path to legacy JSON file")
    mig.add_argument("--output", "-o", required=True, help="Output scenario.json path")
    mig.add_argument("--report", "-r", help="Output migration-report.json path")
    mig.add_argument("--scenario-id", dest="scenario_id", help="Override derived scenario ID")
    mig.add_argument("--force", action="store_true", help="Overwrite existing output files")


def register_scenario_subparser(sub: argparse._SubParsersAction) -> None:
    """Register the 'scenario' subcommand group in the top-level CLI."""
    scenario_parser = sub.add_parser("scenario", help="Scenario tools")
    scenario_sub = scenario_parser.add_subparsers(dest="scenario_command", required=True)
    register_migrate_subparser(scenario_sub)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="peoplenet-process-extractor",
        description="PeopleNet Process Extractor — Scenario tools",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    register_migrate_subparser(sub)
    return parser


def _write_atomic(text: str, dest: Path) -> None:
    """Write text to dest via a temp file in the same directory, then rename atomically."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp: str | None = None
    try:
        fd, tmp = tempfile.mkstemp(dir=dest.parent, suffix=".tmp")
        os.close(fd)
        Path(tmp).write_text(text, encoding="utf-8")
        Path(tmp).replace(dest)
        tmp = None
    finally:
        if tmp is not None:
            try:
                Path(tmp).unlink(missing_ok=True)
            except OSError:
                pass


def cmd_migrate(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)
    report_path = Path(args.report) if args.report else None

    # Read and parse input.
    # Failures here happen before a MigrationReport exists — no error report can be written.
    try:
        raw = input_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error reading {input_path}: {exc}", file=sys.stderr)
        return 1

    try:
        legacy = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {input_path}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(legacy, dict):
        print(
            f"Error: legacy file must be a JSON object, got {type(legacy).__name__}",
            file=sys.stderr,
        )
        return 1

    # Validate destinations before any work
    if output_path.exists() and not args.force:
        print(
            f"Error: output file already exists: {output_path}. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1
    if report_path and report_path.exists() and not args.force:
        print(
            f"Error: report file already exists: {report_path}. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    # Migrate and validate
    scenario, report = migrate_from_legacy(
        legacy,
        scenario_id=args.scenario_id,
        legacy_file=str(input_path),
    )
    for verr in validate(scenario):
        report.errors.append(MigrationError(code=verr.code, message=verr.message))

    for w in report.warnings:
        print(f"Warning [{w.code}]: {w.message}", file=sys.stderr)

    if report.has_errors:
        for err in report.errors:
            print(f"Error [{err.code}]: {err.message}", file=sys.stderr)
        # Write the error report if requested — scenario is never written on error.
        if report_path:
            try:
                _write_atomic(serialize_report(report), report_path)
                print(f"Migration report written to {report_path}")
            except OSError as exc:
                print(f"Error writing report: {exc}", file=sys.stderr)
        return 1

    # Serialize before touching the filesystem
    scenario_text = serialize_scenario(scenario)
    report_text = serialize_report(report) if report_path else None

    # Write via temp files then rename (atomic per-file).
    # NOTE: the two replace() calls are not jointly atomic — if the process is
    # interrupted between them, scenario.json will exist but report.json will not.
    # This is an inherent limit of two-file output without filesystem transactions.
    tmp_out: str | None = None
    tmp_rep: str | None = None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_out = tempfile.mkstemp(dir=output_path.parent, suffix=".tmp")
        os.close(fd)
        Path(tmp_out).write_text(scenario_text, encoding="utf-8")

        if report_path and report_text is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_rep = tempfile.mkstemp(dir=report_path.parent, suffix=".tmp")
            os.close(fd)
            Path(tmp_rep).write_text(report_text, encoding="utf-8")

        # Both temps written; publish via rename
        Path(tmp_out).replace(output_path)
        tmp_out = None
        if report_path and tmp_rep is not None:
            Path(tmp_rep).replace(report_path)
            tmp_rep = None

    except OSError as exc:
        print(f"Error writing output: {exc}", file=sys.stderr)
        return 1
    finally:
        for tmp in [tmp_out, tmp_rep]:
            if tmp is not None:
                try:
                    Path(tmp).unlink(missing_ok=True)
                except OSError:
                    pass

    print(f"Scenario written to {output_path}")
    if report_path:
        print(f"Migration report written to {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "migrate":
        return cmd_migrate(args)
    print(f"Unknown command: {args.command}", file=sys.stderr)
    return 1
