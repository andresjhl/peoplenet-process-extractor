import argparse
import sys
from pathlib import Path

from .service import (
    ManifestParseError,
    RunDirectoryError,
    RunError,
    ScenarioValidationError,
    create_run,
    verify_run,
)


def register_manifest_subparser(sub: argparse._SubParsersAction) -> None:
    manifest = sub.add_parser("manifest", help="Run manifest commands")
    manifest_sub = manifest.add_subparsers(dest="manifest_command", required=True)

    # manifest create
    create = manifest_sub.add_parser("create", help="Create a new run from a scenario")
    create.add_argument("--scenario", required=True, help="Path to scenario.json (scenario-v1)")
    create.add_argument(
        "--runs-root",
        dest="runs_root",
        required=True,
        help=(
            "Parent directory under which the run directory is created. "
            "The final directory is <runs-root>/<run-id>."
        ),
    )
    create.add_argument(
        "--run-id",
        dest="run_id",
        help="Explicit run ID (auto-generated if omitted)",
    )
    create.add_argument(
        "--force",
        action="store_true",
        help=(
            "Overwrite an existing managed run (must contain run-manifest.json "
            "with a valid manifest, matching run_id, and no unknown entries). "
            "Unmanaged directories and directories with unknown files are always rejected."
        ),
    )

    # manifest verify
    verify = manifest_sub.add_parser("verify", help="Verify file integrity of a run manifest")
    verify.add_argument("manifest", help="Path to run-manifest.json")


def cmd_manifest_create(args: argparse.Namespace) -> int:
    scenario_path = Path(args.scenario)
    runs_root = Path(args.runs_root)
    run_id: str | None = args.run_id

    try:
        manifest = create_run(
            scenario_path=scenario_path,
            runs_root=runs_root,
            run_id=run_id,
            force=args.force,
        )
    except ScenarioValidationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except RunDirectoryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except RunError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    run_dir = runs_root / manifest.run_id
    print(f"Run created: {run_dir / 'run-manifest.json'}")
    print(f"  run_id   : {manifest.run_id}")
    print(f"  status   : {manifest.status}")
    print(f"  scenario : {manifest.scenario.scenario_id} ({manifest.scenario.schema_version})")
    return 0


def cmd_manifest_verify(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)

    try:
        result = verify_run(manifest_path)
    except ManifestParseError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if result.ok:
        print(f"OK  {manifest_path}")
        print(f"    run_id: {result.manifest.run_id}  status: {result.manifest.status}")
        return 0

    print(f"FAIL  {manifest_path}")
    for issue in result.issues:
        path_info = f" [{issue.path}]" if issue.path else ""
        print(f"  {issue.kind}{path_info}: {issue.message}")
    return 2
