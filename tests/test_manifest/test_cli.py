import json
from pathlib import Path

import pytest

from peoplenet_process_extractor.cli import main

SCENARIO_FIXTURE = str(
    Path(__file__).parent.parent / "fixtures" / "scenarios" / "expected_scenario_v1.json"
)
LEGACY_FIXTURE = str(
    Path(__file__).parent.parent / "fixtures" / "scenarios" / "legacy_peoplenet_call.json"
)


# ---------------------------------------------------------------------------
# Top-level help
# ---------------------------------------------------------------------------


def test_help_does_not_crash():
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_manifest_subcommand_in_help(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert "manifest" in out


def test_scenario_subcommand_in_help(capsys):
    """'scenario' group must appear in the top-level help (Hallazgo 6)."""
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert "scenario" in out


# ---------------------------------------------------------------------------
# Scenario CLI hierarchy (Hallazgo 6)
# ---------------------------------------------------------------------------


def test_scenario_help_does_not_crash():
    with pytest.raises(SystemExit) as exc:
        main(["scenario", "--help"])
    assert exc.value.code == 0


def test_scenario_migrate_help_does_not_crash():
    with pytest.raises(SystemExit) as exc:
        main(["scenario", "migrate", "--help"])
    assert exc.value.code == 0


def test_scenario_migrate_canonical(tmp_path):
    """Canonical 'scenario migrate' path must work (Hallazgo 6)."""
    out = tmp_path / "scenario.json"
    result = main(["scenario", "migrate", LEGACY_FIXTURE, "--output", str(out)])
    assert result == 0
    assert out.exists()


def test_migrate_alias_still_works(tmp_path):
    """Deprecated 'migrate' alias at top level must keep working (Hallazgo 6)."""
    out = tmp_path / "scenario.json"
    result = main(["migrate", LEGACY_FIXTURE, "--output", str(out)])
    assert result == 0
    assert out.exists()


# ---------------------------------------------------------------------------
# Manifest help
# ---------------------------------------------------------------------------


def test_manifest_help_does_not_crash():
    with pytest.raises(SystemExit) as exc:
        main(["manifest", "--help"])
    assert exc.value.code == 0


def test_manifest_create_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["manifest", "create", "--help"])
    assert exc.value.code == 0


def test_manifest_verify_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["manifest", "verify", "--help"])
    assert exc.value.code == 0


# ---------------------------------------------------------------------------
# manifest create — success (uses --runs-root, Hallazgo 5)
# ---------------------------------------------------------------------------


def test_create_exit_zero(tmp_path):
    result = main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    assert result == 0


def test_create_run_dir_equals_run_id(tmp_path):
    """Final directory name must equal the run_id (Hallazgo 5)."""
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    assert (tmp_path / "run-test-001").is_dir()
    assert (tmp_path / "run-test-001" / "run-manifest.json").is_file()


def test_create_makes_manifest_file(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    assert (tmp_path / "run-test-001" / "run-manifest.json").exists()


def test_create_manifest_is_valid_json(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    data = json.loads((tmp_path / "run-test-001" / "run-manifest.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert data["run_id"] == "run-test-001"


def test_create_creates_directory_structure(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    run_dir = tmp_path / "run-test-001"
    assert (run_dir / "inputs").is_dir()
    assert (run_dir / "artifacts").is_dir()
    assert (run_dir / "reports").is_dir()


def test_create_scenario_copied(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    assert (tmp_path / "run-test-001" / "inputs" / "scenario.json").exists()


def test_create_no_absolute_paths_in_json(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    text = (tmp_path / "run-test-001" / "run-manifest.json").read_text(encoding="utf-8")
    assert ":\\" not in text
    assert '"/' not in text


# ---------------------------------------------------------------------------
# manifest create — auto run_id
# ---------------------------------------------------------------------------


def test_create_auto_run_id(tmp_path):
    result = main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
    ])
    assert result == 0
    # Some run-* directory must have been created inside tmp_path.
    run_dirs = [d for d in tmp_path.iterdir() if d.is_dir() and d.name.startswith("run-")]
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "run-manifest.json").is_file()
    data = json.loads((run_dirs[0] / "run-manifest.json").read_text(encoding="utf-8"))
    assert data["run_id"].startswith("run-")


# ---------------------------------------------------------------------------
# manifest create — errors
# ---------------------------------------------------------------------------


def test_create_missing_scenario_exit_nonzero(tmp_path):
    result = main([
        "manifest", "create",
        "--scenario", str(tmp_path / "ghost.json"),
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    assert result != 0


def test_create_missing_scenario_no_partial_dir(tmp_path):
    main([
        "manifest", "create",
        "--scenario", str(tmp_path / "ghost.json"),
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    assert not (tmp_path / "run-test-001").exists()


def test_create_existing_dir_exit_nonzero(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    result = main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",  # same run_id → conflict
    ])
    assert result != 0


def test_create_force_overwrites_managed(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    result = main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
        "--force",
    ])
    assert result == 0
    data = json.loads((tmp_path / "run-test-001" / "run-manifest.json").read_text(encoding="utf-8"))
    assert data["run_id"] == "run-test-001"


def test_create_force_refuses_unknown_file(tmp_path):
    """--force must refuse when the run directory contains unknown files (Hallazgo 2)."""
    run_dir = tmp_path / "run-test-001"
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    (run_dir / "user_data.txt").write_text("important", encoding="utf-8")
    result = main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
        "--force",
    ])
    assert result != 0
    # Original file untouched.
    assert (run_dir / "user_data.txt").read_text(encoding="utf-8") == "important"


def test_create_force_refuses_no_manifest(tmp_path):
    """--force must refuse a directory that has no run-manifest.json."""
    run_dir = tmp_path / "run-test-001"
    run_dir.mkdir()
    result = main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
        "--force",
    ])
    assert result != 0


# ---------------------------------------------------------------------------
# manifest verify — success
# ---------------------------------------------------------------------------


def test_verify_exit_zero_on_valid(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    result = main(["manifest", "verify", str(tmp_path / "run-test-001" / "run-manifest.json")])
    assert result == 0


# ---------------------------------------------------------------------------
# manifest verify — failures
# ---------------------------------------------------------------------------


def test_verify_nonzero_on_missing_scenario(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    (tmp_path / "run-test-001" / "inputs" / "scenario.json").unlink()
    result = main(["manifest", "verify", str(tmp_path / "run-test-001" / "run-manifest.json")])
    assert result != 0


def test_verify_nonzero_on_modified_scenario(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    scen = tmp_path / "run-test-001" / "inputs" / "scenario.json"
    data = json.loads(scen.read_text(encoding="utf-8"))
    data["notes"].append("tampered line")
    scen.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result = main(["manifest", "verify", str(tmp_path / "run-test-001" / "run-manifest.json")])
    assert result != 0


def test_verify_nonzero_on_invalid_manifest(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    manifest_path = tmp_path / "run-test-001" / "run-manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["status"] = "not_valid"
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result = main(["manifest", "verify", str(manifest_path)])
    assert result != 0


def test_verify_nonzero_on_missing_manifest_file(tmp_path):
    result = main(["manifest", "verify", str(tmp_path / "ghost.json")])
    assert result != 0


def test_verify_does_not_modify_manifest(tmp_path):
    main([
        "manifest", "create",
        "--scenario", SCENARIO_FIXTURE,
        "--runs-root", str(tmp_path),
        "--run-id", "run-test-001",
    ])
    manifest_path = tmp_path / "run-test-001" / "run-manifest.json"
    original = manifest_path.read_text(encoding="utf-8")
    main(["manifest", "verify", str(manifest_path)])
    assert manifest_path.read_text(encoding="utf-8") == original
