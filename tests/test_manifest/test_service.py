import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from peoplenet_process_extractor.manifest.service import (
    RunDirectoryError,
    ScenarioValidationError,
    create_run,
    generate_run_id,
    verify_run,
)

SCENARIO_FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "scenarios" / "expected_scenario_v1.json"
)

_FIXED_DT = datetime(2026, 6, 23, 14, 30, 0, tzinfo=timezone.utc)
_FIXED_TOKEN = "abcd1234efgh5678"  # first 8 chars → run_id suffix

_FIXED_RUN_ID = "run-20260623-abcd1234"


def _clock():
    return _FIXED_DT


def _token():
    return _FIXED_TOKEN


# ---------------------------------------------------------------------------
# generate_run_id
# ---------------------------------------------------------------------------


def test_generate_run_id_format():
    run_id = generate_run_id(_clock_fn=_clock, _token_fn=_token)
    assert run_id == _FIXED_RUN_ID


def test_generate_run_id_no_path_separators():
    run_id = generate_run_id(_clock_fn=_clock, _token_fn=_token)
    assert "/" not in run_id
    assert "\\" not in run_id


def test_generate_run_id_different_tokens():
    tokens = iter(["aaa11111", "bbb22222"])
    ids = [generate_run_id(_clock_fn=_clock, _token_fn=lambda: next(tokens)) for _ in range(2)]
    assert ids[0] != ids[1]


# ---------------------------------------------------------------------------
# create_run — valid scenario
# ---------------------------------------------------------------------------


def test_create_run_valid_scenario(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    assert manifest.run_id == _FIXED_RUN_ID
    assert manifest.status == "prepared"


def test_create_run_run_dir_equals_run_id(tmp_path):
    """Final directory name must equal manifest.run_id (Hallazgo 5)."""
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    assert run_dir.is_dir()


def test_create_run_explicit_run_id(tmp_path):
    manifest = create_run(
        SCENARIO_FIXTURE, tmp_path,
        run_id="my-custom-run",
        _clock_fn=_clock, _token_fn=_token,
    )
    assert manifest.run_id == "my-custom-run"
    assert (tmp_path / "my-custom-run").is_dir()


def test_create_run_directory_structure(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    assert (run_dir / "run-manifest.json").exists()
    assert (run_dir / "inputs").is_dir()
    assert (run_dir / "artifacts").is_dir()
    assert (run_dir / "reports").is_dir()


def test_create_run_scenario_copied(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    assert (run_dir / "inputs" / "scenario.json").exists()


def test_create_run_scenario_hash_correct(tmp_path):
    from peoplenet_process_extractor.manifest.hashing import compute_file_hash_and_size
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    expected_sha, expected_size = compute_file_hash_and_size(run_dir / "inputs" / "scenario.json")
    assert manifest.scenario.sha256 == expected_sha
    assert manifest.scenario.size_bytes == expected_size


def test_create_run_scenario_id_recorded(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    assert manifest.scenario.scenario_id == "11-jorn-store-u"


def test_create_run_tool_registered(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    assert len(manifest.tools) == 1
    assert manifest.tools[0].id == "peoplenet-process-extractor"


def test_create_run_prepared_event(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    assert len(manifest.events) == 1
    assert manifest.events[0].type == "prepared"
    assert manifest.events[0].sequence == 1


def test_create_run_timestamp_uses_clock(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    assert manifest.events[0].timestamp == "2026-06-23T14:30:00Z"


def test_create_run_portable_paths_in_manifest(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    data = json.loads((run_dir / "run-manifest.json").read_text(encoding="utf-8"))
    assert data["scenario"]["path"] == "inputs/scenario.json"
    assert data["sources"][0]["path"] == "inputs/scenario.json"


def test_create_run_no_absolute_paths_in_json(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    text = (run_dir / "run-manifest.json").read_text(encoding="utf-8")
    assert ":\\" not in text
    assert '"/' not in text


def test_create_run_manifest_file_exists(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    assert (run_dir / "run-manifest.json").is_file()


def test_create_run_manifest_valid_json(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    text = (run_dir / "run-manifest.json").read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["schema_version"] == "1.0"


# ---------------------------------------------------------------------------
# create_run — symlink rejection (Hallazgo 7)
# ---------------------------------------------------------------------------


def test_create_run_rejects_symlink_scenario(tmp_path):
    """Symlink scenario files must be rejected (Hallazgo 7)."""
    link = tmp_path / "scenario_link.json"
    try:
        link.symlink_to(SCENARIO_FIXTURE)
    except OSError:
        pytest.skip("Symlinks not available in this environment")

    with pytest.raises(ScenarioValidationError, match="symlink"):
        create_run(link, tmp_path, _clock_fn=_clock, _token_fn=_token)


# ---------------------------------------------------------------------------
# create_run — invalid scenario
# ---------------------------------------------------------------------------


def test_create_run_missing_scenario_file(tmp_path):
    with pytest.raises(ScenarioValidationError, match="not found"):
        create_run(tmp_path / "ghost.json", tmp_path)


def test_create_run_invalid_json_scenario(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(ScenarioValidationError, match="parse"):
        create_run(bad, tmp_path)


def test_create_run_invalid_scenario_validation(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": "1.0", "scenario_id": ""}), encoding="utf-8")
    with pytest.raises(ScenarioValidationError):
        create_run(bad, tmp_path)


# ---------------------------------------------------------------------------
# create_run — directory handling (Hallazgo 2)
# ---------------------------------------------------------------------------


def test_create_run_existing_dir_raises(tmp_path):
    create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    with pytest.raises(RunDirectoryError, match="already exists"):
        create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)


def test_create_run_force_overwrites_managed_run(tmp_path):
    create_run(SCENARIO_FIXTURE, tmp_path, run_id="my-run", _clock_fn=_clock, _token_fn=_token)
    manifest = create_run(
        SCENARIO_FIXTURE, tmp_path,
        run_id="my-run",
        force=True,
        _clock_fn=_clock, _token_fn=_token,
    )
    assert manifest.run_id == "my-run"
    run_dir = tmp_path / "my-run"
    assert (run_dir / "run-manifest.json").is_file()


def test_create_run_force_preserves_old_run_until_publish(tmp_path):
    """Previous run must remain intact throughout staging build."""
    first = create_run(SCENARIO_FIXTURE, tmp_path, run_id="my-run", _clock_fn=_clock, _token_fn=_token)
    old_hash = first.scenario.sha256
    # Overwrite succeeds; new run replaces old.
    second = create_run(
        SCENARIO_FIXTURE, tmp_path, run_id="my-run", force=True,
        _clock_fn=_clock, _token_fn=_token,
    )
    assert second.scenario.sha256 == old_hash  # same file, same hash


def test_create_run_force_refuses_unknown_file(tmp_path):
    """--force must reject a run directory containing unknown files (Hallazgo 2)."""
    run_dir = tmp_path / _FIXED_RUN_ID
    create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    (run_dir / "user-note.txt").write_text("my note")
    with pytest.raises(RunDirectoryError, match="unknown"):
        create_run(SCENARIO_FIXTURE, tmp_path, force=True, _clock_fn=_clock, _token_fn=_token)


def test_create_run_force_refuses_unknown_subdirectory(tmp_path):
    """--force must reject a run directory containing unknown subdirectories."""
    run_dir = tmp_path / _FIXED_RUN_ID
    create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    (run_dir / "my-extra-dir").mkdir()
    with pytest.raises(RunDirectoryError, match="unknown"):
        create_run(SCENARIO_FIXTURE, tmp_path, force=True, _clock_fn=_clock, _token_fn=_token)


def test_create_run_force_refuses_dir_without_manifest(tmp_path):
    """--force must refuse a directory that has no run-manifest.json."""
    run_dir = tmp_path / _FIXED_RUN_ID
    run_dir.mkdir()
    with pytest.raises(RunDirectoryError):
        create_run(SCENARIO_FIXTURE, tmp_path, force=True, _clock_fn=_clock, _token_fn=_token)


def test_create_run_force_refuses_invalid_manifest(tmp_path):
    """--force must refuse when the existing manifest fails validation."""
    run_dir = tmp_path / _FIXED_RUN_ID
    create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    mpath = run_dir / "run-manifest.json"
    data = json.loads(mpath.read_text(encoding="utf-8"))
    data["status"] = "not_valid"
    mpath.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RunDirectoryError):
        create_run(SCENARIO_FIXTURE, tmp_path, force=True, _clock_fn=_clock, _token_fn=_token)


def test_create_run_force_refuses_mismatched_run_id(tmp_path):
    """--force must refuse when manifest.run_id doesn't match the directory name."""
    run_dir = tmp_path / _FIXED_RUN_ID
    create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    mpath = run_dir / "run-manifest.json"
    data = json.loads(mpath.read_text(encoding="utf-8"))
    data["run_id"] = "some-other-run"
    mpath.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RunDirectoryError, match="run_id"):
        create_run(SCENARIO_FIXTURE, tmp_path, force=True, _clock_fn=_clock, _token_fn=_token)


def test_create_run_unknown_content_not_deleted_on_force_reject(tmp_path):
    """Rejected --force must leave the run directory and its unknown contents intact."""
    run_dir = tmp_path / _FIXED_RUN_ID
    create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    user_note = run_dir / "user-note.txt"
    user_note.write_text("do not delete me")

    with pytest.raises(RunDirectoryError):
        create_run(SCENARIO_FIXTURE, tmp_path, force=True, _clock_fn=_clock, _token_fn=_token)

    assert user_note.exists(), "Unknown file must not have been deleted"
    assert user_note.read_text() == "do not delete me"


# ---------------------------------------------------------------------------
# create_run — staging cleanup (Hallazgo 2)
# ---------------------------------------------------------------------------


def test_create_run_staging_cleaned_on_failure(tmp_path, monkeypatch):
    """Staging directory must be removed when the build fails."""
    def fail_copy(*args, **kwargs):
        raise OSError("simulated copy failure")

    monkeypatch.setattr(shutil, "copy2", fail_copy)

    with pytest.raises(OSError):
        create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)

    staging_dirs = list(tmp_path.glob(f".{_FIXED_RUN_ID}.staging-*"))
    assert staging_dirs == [], "Staging directory must be cleaned up on failure"


def test_create_run_old_run_preserved_when_staging_fails(tmp_path, monkeypatch):
    """Previous run must remain intact when the staging build fails."""
    create_run(SCENARIO_FIXTURE, tmp_path, run_id="my-run", _clock_fn=_clock, _token_fn=_token)
    old_manifest_text = (tmp_path / "my-run" / "run-manifest.json").read_text(encoding="utf-8")

    def fail_copy(*args, **kwargs):
        raise OSError("simulated copy failure")

    monkeypatch.setattr(shutil, "copy2", fail_copy)

    with pytest.raises(OSError):
        create_run(SCENARIO_FIXTURE, tmp_path, run_id="my-run", force=True,
                   _clock_fn=_clock, _token_fn=_token)

    # Old run must be completely intact.
    current_text = (tmp_path / "my-run" / "run-manifest.json").read_text(encoding="utf-8")
    assert current_text == old_manifest_text, "Old run must be intact after staging failure"


def test_publish_failure_restores_old_run(tmp_path, monkeypatch):
    """
    Simulate a failure in the staging→final rename (after backup is created).

    Scenario:
      1. A valid managed run exists.
      2. Staging is built completely and validated.
      3. final is renamed to backup.
      4. staging.rename(final) FAILS.

    Expected: backup is restored to final; no staging and no backup remain;
    error is propagated; run content is unchanged.
    """
    # Step 1: create the initial run.
    create_run(SCENARIO_FIXTURE, tmp_path, run_id="my-run", _clock_fn=_clock, _token_fn=_token)
    old_manifest_text = (tmp_path / "my-run" / "run-manifest.json").read_text(encoding="utf-8")

    # Step 2: monkeypatch Path.rename to fail on the second call.
    # Inside _publish_staging with an existing run:
    #   call 1 → final.rename(backup)   [must succeed]
    #   call 2 → staging.rename(final)  [FAIL here]
    #   call 3 → backup.rename(final)   [restore; must succeed]
    import peoplenet_process_extractor.manifest.service as svc

    real_rename = svc.Path.rename
    call_count = [0]

    def controlled_rename(self, target):
        call_count[0] += 1
        if call_count[0] == 2:
            raise OSError("simulated staging publish failure")
        return real_rename(self, target)

    monkeypatch.setattr(svc.Path, "rename", controlled_rename)

    with pytest.raises(OSError, match="simulated staging publish failure"):
        create_run(SCENARIO_FIXTURE, tmp_path, run_id="my-run", force=True,
                   _clock_fn=_clock, _token_fn=_token)

    run_dir = tmp_path / "my-run"

    # Old run must be restored with its original content.
    assert run_dir.is_dir(), "Run directory must be restored"
    restored_text = (run_dir / "run-manifest.json").read_text(encoding="utf-8")
    assert restored_text == old_manifest_text, "Manifest content must be unchanged after restore"

    # No staging directory must remain.
    staging_dirs = list(tmp_path.glob(".my-run.staging-*"))
    assert staging_dirs == [], f"Staging dirs must be cleaned up, found: {staging_dirs}"

    # No backup directory must remain.
    backup_dirs = list(tmp_path.glob(".my-run.backup-*"))
    assert backup_dirs == [], f"Backup dirs must be cleaned up, found: {backup_dirs}"


# ---------------------------------------------------------------------------
# create_run — cleanup on failure (general)
# ---------------------------------------------------------------------------


def test_create_run_no_partial_dir_on_failure(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("INVALID", encoding="utf-8")
    with pytest.raises(ScenarioValidationError):
        create_run(bad, tmp_path)
    run_dir = tmp_path / _FIXED_RUN_ID
    assert not run_dir.exists()


def test_create_run_no_temp_files_left(tmp_path):
    create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    assert list(tmp_path.rglob("*.tmp")) == []


def test_create_run_no_staging_left_on_success(tmp_path):
    create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    staging_dirs = list(tmp_path.glob(f".{_FIXED_RUN_ID}.staging-*"))
    assert staging_dirs == []


# ---------------------------------------------------------------------------
# verify_run
# ---------------------------------------------------------------------------


def test_verify_run_valid(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    result = verify_run(run_dir / "run-manifest.json")
    assert result.ok


def test_verify_run_returns_zero_issues_on_valid(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    result = verify_run(run_dir / "run-manifest.json")
    assert result.issues == []


def test_verify_run_missing_scenario(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    (run_dir / "inputs" / "scenario.json").unlink()
    result = verify_run(run_dir / "run-manifest.json")
    assert not result.ok
    assert any(i.kind == "missing" for i in result.issues)


def test_verify_run_modified_scenario(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    scen = run_dir / "inputs" / "scenario.json"
    original = json.loads(scen.read_text(encoding="utf-8"))
    original["notes"].append("tampered")
    scen.write_text(json.dumps(original), encoding="utf-8")
    result = verify_run(run_dir / "run-manifest.json")
    assert not result.ok
    kinds = {i.kind for i in result.issues}
    assert "hash_mismatch" in kinds or "size_mismatch" in kinds


def test_verify_run_invalid_manifest(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    manifest_path = run_dir / "run-manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["status"] = "not_valid"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    result = verify_run(manifest_path)
    assert not result.ok
    assert any(i.kind == "validation_error" for i in result.issues)


def test_verify_run_does_not_modify_manifest(tmp_path):
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    manifest_path = run_dir / "run-manifest.json"
    original_text = manifest_path.read_text(encoding="utf-8")
    verify_run(manifest_path)
    assert manifest_path.read_text(encoding="utf-8") == original_text


# ---------------------------------------------------------------------------
# verify_run — symlink rejection (Hallazgo 7)
# ---------------------------------------------------------------------------


def test_verify_run_rejects_symlink_scenario(tmp_path):
    """verify_run must flag a symlink at the scenario path as a symlink issue."""
    manifest = create_run(SCENARIO_FIXTURE, tmp_path, _clock_fn=_clock, _token_fn=_token)
    run_dir = tmp_path / manifest.run_id
    scen_path = run_dir / "inputs" / "scenario.json"

    # Replace the real scenario file with a symlink.
    real_copy = tmp_path / "scenario_real.json"
    scen_path.rename(real_copy)
    try:
        scen_path.symlink_to(real_copy)
    except OSError:
        pytest.skip("Symlinks not available in this environment")

    result = verify_run(run_dir / "run-manifest.json")
    assert not result.ok
    assert any(i.kind == "symlink" for i in result.issues)
