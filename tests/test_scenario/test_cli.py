import json
from pathlib import Path


from peoplenet_process_extractor.scenario.cli import main

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "scenarios"


def _legacy_path(name: str = "legacy_peoplenet_call.json") -> str:
    return str(FIXTURE_DIR / name)


# ---------------------------------------------------------------------------
# valid migration
# ---------------------------------------------------------------------------


def test_migrate_valid_exit_zero(tmp_path):
    out = tmp_path / "scenario.json"
    result = main(["migrate", _legacy_path(), "--output", str(out)])
    assert result == 0


def test_migrate_valid_creates_output(tmp_path):
    out = tmp_path / "scenario.json"
    main(["migrate", _legacy_path(), "--output", str(out)])
    assert out.exists()


def test_migrate_valid_output_is_json(tmp_path):
    out = tmp_path / "scenario.json"
    main(["migrate", _legacy_path(), "--output", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"


def test_migrate_generates_report(tmp_path):
    out = tmp_path / "scenario.json"
    rep = tmp_path / "report.json"
    main(["migrate", _legacy_path(), "--output", str(out), "--report", str(rep)])
    assert rep.exists()
    data = json.loads(rep.read_text(encoding="utf-8"))
    assert "migrated_fields" in data
    assert "warnings" in data


def test_migrate_report_has_defaults(tmp_path):
    out = tmp_path / "scenario.json"
    rep = tmp_path / "report.json"
    main(["migrate", _legacy_path(), "--output", str(out), "--report", str(rep)])
    data = json.loads(rep.read_text(encoding="utf-8"))
    assert data["defaults_applied"]


# ---------------------------------------------------------------------------
# invalid JSON
# ---------------------------------------------------------------------------


def test_invalid_json_exit_nonzero(tmp_path):
    out = tmp_path / "scenario.json"
    result = main(["migrate", _legacy_path("invalid_json.json"), "--output", str(out)])
    assert result != 0


def test_invalid_json_no_output_file(tmp_path):
    out = tmp_path / "scenario.json"
    main(["migrate", _legacy_path("invalid_json.json"), "--output", str(out)])
    assert not out.exists()


# ---------------------------------------------------------------------------
# process mismatch
# ---------------------------------------------------------------------------


def test_process_mismatch_exit_nonzero(tmp_path):
    out = tmp_path / "scenario.json"
    result = main(["migrate", _legacy_path("invalid_process_mismatch.json"), "--output", str(out)])
    assert result != 0


def test_process_mismatch_no_scenario_file(tmp_path):
    out = tmp_path / "scenario.json"
    main(["migrate", _legacy_path("invalid_process_mismatch.json"), "--output", str(out)])
    assert not out.exists()


def test_process_mismatch_report_written(tmp_path):
    # Error report IS written even when migration has errors.
    # The scenario file is never created on error.
    out = tmp_path / "scenario.json"
    rep = tmp_path / "report.json"
    main([
        "migrate", _legacy_path("invalid_process_mismatch.json"),
        "--output", str(out),
        "--report", str(rep),
    ])
    assert not out.exists()
    assert rep.exists()


def test_process_mismatch_report_exactly_one_error(tmp_path):
    # validate() is the sole authority: the report must contain exactly one
    # process_id_mismatch — not zero, not two.
    out = tmp_path / "scenario.json"
    rep = tmp_path / "report.json"
    main([
        "migrate", _legacy_path("invalid_process_mismatch.json"),
        "--output", str(out),
        "--report", str(rep),
    ])
    data = json.loads(rep.read_text(encoding="utf-8"))
    mismatch_count = sum(1 for e in data["errors"] if e["code"] == "process_id_mismatch")
    assert mismatch_count == 1


# ---------------------------------------------------------------------------
# missing entry point — validation errors
# ---------------------------------------------------------------------------


def test_missing_entry_point_exit_nonzero(tmp_path):
    out = tmp_path / "scenario.json"
    result = main(["migrate", _legacy_path("invalid_missing_entry_point.json"), "--output", str(out)])
    assert result != 0


# ---------------------------------------------------------------------------
# --scenario-id
# ---------------------------------------------------------------------------


def test_custom_scenario_id(tmp_path):
    out = tmp_path / "scenario.json"
    main(["migrate", _legacy_path(), "--output", str(out), "--scenario-id", "my-custom-id"])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["scenario_id"] == "my-custom-id"


# ---------------------------------------------------------------------------
# output already exists
# ---------------------------------------------------------------------------


def test_no_overwrite_existing_output(tmp_path):
    out = tmp_path / "scenario.json"
    out.write_text("existing", encoding="utf-8")
    result = main(["migrate", _legacy_path(), "--output", str(out)])
    assert result != 0
    assert out.read_text(encoding="utf-8") == "existing"


def test_force_overwrites_existing(tmp_path):
    out = tmp_path / "scenario.json"
    out.write_text("existing", encoding="utf-8")
    result = main(["migrate", _legacy_path(), "--output", str(out), "--force"])
    assert result == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"


def test_no_overwrite_existing_report(tmp_path):
    out = tmp_path / "scenario.json"
    rep = tmp_path / "report.json"
    rep.write_text("existing", encoding="utf-8")
    result = main(["migrate", _legacy_path(), "--output", str(out), "--report", str(rep)])
    assert result != 0
    assert rep.read_text(encoding="utf-8") == "existing"


# ---------------------------------------------------------------------------
# exit codes
# ---------------------------------------------------------------------------


def test_exit_code_zero_on_success(tmp_path):
    out = tmp_path / "s.json"
    assert main(["migrate", _legacy_path(), "--output", str(out)]) == 0


def test_exit_code_one_on_missing_file(tmp_path):
    out = tmp_path / "s.json"
    assert main(["migrate", str(tmp_path / "nonexistent.json"), "--output", str(out)]) == 1


# ---------------------------------------------------------------------------
# runtime binding: warning but still succeeds
# ---------------------------------------------------------------------------


def test_runtime_binding_exits_zero(tmp_path):
    out = tmp_path / "scenario.json"
    result = main(["migrate", _legacy_path("runtime_input_binding.json"), "--output", str(out)])
    assert result == 0


def test_runtime_binding_binding_preserved(tmp_path):
    out = tmp_path / "scenario.json"
    main(["migrate", _legacy_path("runtime_input_binding.json"), "--output", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    props = [b["property"] for b in data["property_bindings"]]
    assert "GLB_COND_HOR_SRZ" in props


def test_runtime_binding_no_null_input(tmp_path):
    out = tmp_path / "scenario.json"
    main(["migrate", _legacy_path("runtime_input_binding.json"), "--output", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    input_names = [i["name"] for i in data["entry_inputs"]]
    assert "P_14" not in input_names


# ---------------------------------------------------------------------------
# atomic write guarantees
# ---------------------------------------------------------------------------


def test_no_partial_scenario_on_report_failure(tmp_path):
    # Block report directory by placing a file where the directory would be.
    # The scenario temp is written first; if the report temp then fails, the
    # scenario temp must be cleaned up — scenario.json must NOT appear.
    blocker = tmp_path / "reports"
    blocker.write_text("i am a file", encoding="utf-8")

    out = tmp_path / "scenario.json"
    rep = blocker / "report.json"  # parent is a file → mkdir will raise OSError

    result = main(["migrate", _legacy_path(), "--output", str(out), "--report", str(rep)])
    assert result == 1
    assert not out.exists()


def test_no_residual_temp_files_on_success(tmp_path):
    out = tmp_path / "scenario.json"
    main(["migrate", _legacy_path(), "--output", str(out)])
    assert list(tmp_path.rglob("*.tmp")) == []


def test_no_residual_temp_files_on_failure(tmp_path):
    # Use the report-dir-blocked scenario so the scenario temp IS created before
    # the OSError, then must be cleaned up by the finally block.
    blocker = tmp_path / "reports"
    blocker.write_text("i am a file", encoding="utf-8")
    out = tmp_path / "scenario.json"
    rep = blocker / "report.json"
    main(["migrate", _legacy_path(), "--output", str(out), "--report", str(rep)])
    assert list(tmp_path.rglob("*.tmp")) == []


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def test_migrate_subcommand_exists():
    from peoplenet_process_extractor.scenario.cli import build_parser

    parser = build_parser()
    assert parser.prog == "peoplenet-process-extractor"
    args = parser.parse_args(["migrate", "input.json", "--output", "out.json"])
    assert args.command == "migrate"


# ---------------------------------------------------------------------------
# error-path report: pre-existing report file
# ---------------------------------------------------------------------------


def test_error_report_not_overwritten_without_force(tmp_path):
    # Pre-check fires before migration: existing report + no --force → return 1, no overwrite.
    out = tmp_path / "scenario.json"
    rep = tmp_path / "error_report.json"
    rep.write_text("existing", encoding="utf-8")
    result = main([
        "migrate", _legacy_path("invalid_process_mismatch.json"),
        "--output", str(out), "--report", str(rep),
    ])
    assert result != 0
    assert rep.read_text(encoding="utf-8") == "existing"


def test_error_report_overwritten_with_force(tmp_path):
    # --force: existing report is replaced by the structured error report.
    out = tmp_path / "scenario.json"
    rep = tmp_path / "error_report.json"
    rep.write_text("existing", encoding="utf-8")
    result = main([
        "migrate", _legacy_path("invalid_process_mismatch.json"),
        "--output", str(out), "--report", str(rep), "--force",
    ])
    assert result != 0
    data = json.loads(rep.read_text(encoding="utf-8"))
    codes = [e["code"] for e in data["errors"]]
    assert "process_id_mismatch" in codes


# ---------------------------------------------------------------------------
# error-path report: when no MigrationReport exists (parse failure)
# ---------------------------------------------------------------------------


def test_invalid_json_no_report_generated(tmp_path):
    # JSON parse failure occurs before MigrationReport exists.
    # The spec says: do not invent a report if none is available.
    out = tmp_path / "scenario.json"
    rep = tmp_path / "report.json"
    result = main([
        "migrate", _legacy_path("invalid_json.json"),
        "--output", str(out), "--report", str(rep),
    ])
    assert result != 0
    assert not rep.exists()


# ---------------------------------------------------------------------------
# error-path report: validation errors (MigrationReport IS available)
# ---------------------------------------------------------------------------


def test_validation_errors_report_generated(tmp_path):
    # Missing entry-point fields → validation errors → report IS written even on error.
    out = tmp_path / "scenario.json"
    rep = tmp_path / "report.json"
    result = main([
        "migrate", _legacy_path("invalid_missing_entry_point.json"),
        "--output", str(out), "--report", str(rep),
    ])
    assert result != 0
    assert not out.exists()
    assert rep.exists()
    data = json.loads(rep.read_text(encoding="utf-8"))
    assert data["errors"]


# ---------------------------------------------------------------------------
# error-path report: no residual temps when report write fails
# ---------------------------------------------------------------------------


def test_no_residual_temp_files_on_error_report_failure(tmp_path):
    # Mismatch → error path → blocked report dir → OSError in _write_atomic →
    # no temps left (mkdir fails before mkstemp, so nothing to clean up).
    blocker = tmp_path / "reports"
    blocker.write_text("i am a file", encoding="utf-8")
    out = tmp_path / "scenario.json"
    rep = blocker / "report.json"
    main([
        "migrate", _legacy_path("invalid_process_mismatch.json"),
        "--output", str(out), "--report", str(rep),
    ])
    assert list(tmp_path.rglob("*.tmp")) == []
