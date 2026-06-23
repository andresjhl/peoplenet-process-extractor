from pathlib import Path

from peoplenet_process_extractor.manifest.models import (
    Artifact,
    Event,
    ManifestEntry,
    RunManifest,
    ScenarioRef,
    SourceFile,
    Tool,
)
from peoplenet_process_extractor.manifest.validation import validate

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "manifests"

_SHA = "a3f8c1b2d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1"
_SHA2 = "b4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5"


def _scen_src(**overrides) -> SourceFile:
    """Build a scenario source that matches the default scenario ref in _minimal()."""
    base = dict(
        id="scenario",
        kind="scenario",
        path="inputs/scenario.json",
        sha256=_SHA,
        size_bytes=100,
        exists=True,
        required=True,
    )
    base.update(overrides)
    return SourceFile(**base)


def _minimal(**overrides) -> RunManifest:
    """
    Minimal valid RunManifest. Includes one scenario source matching the scenario ref
    so that _check_scenario_source_consistency() passes by default.
    """
    base = dict(
        schema_version="1.0",
        run_id="run-20260623-abc12345",
        status="prepared",
        scenario=ScenarioRef(
            path="inputs/scenario.json",
            sha256=_SHA,
            size_bytes=100,
            scenario_id="test-scenario",
            schema_version="1.0",
        ),
        sources=[_scen_src()],
    )
    base.update(overrides)
    return RunManifest(**base)


def _codes(m: RunManifest) -> list[str]:
    return [e.code for e in validate(m)]


def test_valid_manifest_no_errors():
    assert _codes(_minimal()) == []


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------


def test_unsupported_schema_version():
    m = _minimal(schema_version="2.0")
    assert "unsupported_schema_version" in _codes(m)


# ---------------------------------------------------------------------------
# run_id
# ---------------------------------------------------------------------------


def test_empty_run_id():
    m = _minimal(run_id="")
    assert "empty_run_id" in _codes(m)


def test_run_id_with_path_separator():
    m = _minimal(run_id="run/2026")
    assert "invalid_run_id" in _codes(m)


def test_run_id_with_backslash():
    m = _minimal(run_id="run\\2026")
    assert "invalid_run_id" in _codes(m)


def test_run_id_starting_with_dot():
    m = _minimal(run_id=".hidden")
    assert "invalid_run_id" in _codes(m)


def test_valid_run_id_with_hyphens():
    m = _minimal(run_id="run-20260623-abc12345")
    assert "invalid_run_id" not in _codes(m)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def test_invalid_status():
    m = _minimal(status="invalid_state")
    assert "invalid_run_status" in _codes(m)


def test_valid_statuses():
    for s in ("prepared", "running", "succeeded", "failed", "cancelled"):
        m = _minimal(status=s)
        if s == "failed":
            m.errors = [ManifestEntry(code="E1", message="err")]
        assert "invalid_run_status" not in _codes(m)


# ---------------------------------------------------------------------------
# Scenario ref
# ---------------------------------------------------------------------------


def test_invalid_scenario_sha256():
    m = _minimal()
    m.scenario.sha256 = "NOTVALID"
    assert "invalid_sha256" in _codes(m)


def test_negative_scenario_size():
    m = _minimal()
    m.scenario.size_bytes = -1
    assert "negative_size" in _codes(m)


def test_absolute_path_in_scenario():
    m = _minimal()
    m.scenario.path = "/etc/passwd"
    assert "absolute_path" in _codes(m)


def test_traversal_in_scenario_path():
    m = _minimal()
    m.scenario.path = "inputs/../etc/passwd"
    assert "path_traversal" in _codes(m)


# ---------------------------------------------------------------------------
# Scenario-source consistency (Hallazgo 1)
# ---------------------------------------------------------------------------


def test_no_scenario_source():
    """Manifests without a scenario-kind source must fail validation."""
    m = _minimal(sources=[])
    assert "no_scenario_source" in _codes(m)


def test_no_scenario_source_only_frontend():
    front = SourceFile(
        id="s1", kind="frontend_call", path="inputs/a.json",
        sha256=_SHA, size_bytes=10, exists=True, required=False,
    )
    m = _minimal(sources=[front])
    assert "no_scenario_source" in _codes(m)


def test_multiple_scenario_sources():
    src1 = _scen_src(id="scenario")
    src2 = _scen_src(id="scenario2")
    m = _minimal(sources=[src1, src2])
    assert "multiple_scenario_sources" in _codes(m)


def test_scenario_source_path_mismatch():
    src = _scen_src(path="inputs/other.json")
    m = _minimal(sources=[src])
    assert "scenario_source_path_mismatch" in _codes(m)


def test_scenario_source_sha256_mismatch():
    src = _scen_src(sha256=_SHA2, size_bytes=100)
    m = _minimal(sources=[src])
    assert "scenario_source_sha256_mismatch" in _codes(m)


def test_scenario_source_size_mismatch():
    src = _scen_src(size_bytes=9999)
    m = _minimal(sources=[src])
    assert "scenario_source_size_mismatch" in _codes(m)


def test_scenario_source_all_match_no_errors():
    m = _minimal()
    codes = _codes(m)
    assert "no_scenario_source" not in codes
    assert "scenario_source_path_mismatch" not in codes
    assert "scenario_source_sha256_mismatch" not in codes
    assert "scenario_source_size_mismatch" not in codes


# ---------------------------------------------------------------------------
# Global ID uniqueness (Hallazgo 3)
# ---------------------------------------------------------------------------


def test_source_and_artifact_share_id():
    """An ID used by both a source and an artifact must fail with duplicate_global_id."""
    art = Artifact(
        id="scenario",  # same as the scenario source ID
        kind="migration_report", path="reports/r.json",
        sha256=None, size_bytes=None, producer=None, status="planned",
    )
    m = _minimal(artifacts=[art])
    assert "duplicate_global_id" in _codes(m)


def test_unique_source_and_artifact_ids_ok():
    art = Artifact(
        id="art-001",
        kind="migration_report", path="reports/r.json",
        sha256=None, size_bytes=None, producer=None, status="planned",
    )
    m = _minimal(artifacts=[art])
    assert "duplicate_global_id" not in _codes(m)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


def test_duplicate_source_ids():
    src = SourceFile(
        id="dup", kind="scenario", path="inputs/a.json",
        sha256=_SHA, size_bytes=10, exists=True, required=True,
    )
    m = _minimal(sources=[src, SourceFile(
        id="dup", kind="frontend_call", path="inputs/b.json",
        sha256=None, size_bytes=None, exists=False, required=False,
    )])
    assert "duplicate_source_id" in _codes(m)


def test_invalid_source_kind():
    src = SourceFile(
        id="s1", kind="not_a_kind", path="inputs/a.json",
        sha256=None, size_bytes=None, exists=False, required=False,
    )
    m = _minimal(sources=[src])
    assert "invalid_source_kind" in _codes(m)


def test_source_exists_requires_hash():
    src = SourceFile(
        id="s1", kind="frontend_call", path="inputs/a.json",
        sha256=None, size_bytes=100, exists=True, required=True,
    )
    m = _minimal(sources=[src])
    assert "missing_hash" in _codes(m)


def test_source_exists_requires_size():
    src = SourceFile(
        id="s1", kind="frontend_call", path="inputs/a.json",
        sha256=_SHA, size_bytes=None, exists=True, required=True,
    )
    m = _minimal(sources=[src])
    assert "missing_size" in _codes(m)


def test_source_invalid_sha256():
    src = SourceFile(
        id="s1", kind="frontend_call", path="inputs/a.json",
        sha256="badbadbad", size_bytes=10, exists=True, required=True,
    )
    m = _minimal(sources=[src])
    assert "invalid_sha256" in _codes(m)


def test_source_negative_size():
    src = SourceFile(
        id="s1", kind="frontend_call", path="inputs/a.json",
        sha256=_SHA, size_bytes=-5, exists=True, required=True,
    )
    m = _minimal(sources=[src])
    assert "negative_size" in _codes(m)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def test_duplicate_tool_ids():
    t = Tool(id="dup", name="tool", version="1.0")
    m = _minimal(tools=[t, Tool(id="dup", name="other", version="1.0")])
    assert "duplicate_tool_id" in _codes(m)


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def test_duplicate_artifact_ids():
    tool = Tool(id="t1", name="tool", version="1.0")
    art = Artifact(
        id="dup", kind="migration_report", path="reports/r.json",
        sha256=None, size_bytes=None, producer=None, status="planned",
    )
    art2 = Artifact(
        id="dup", kind="other", path="reports/r2.json",
        sha256=None, size_bytes=None, producer=None, status="planned",
    )
    m = _minimal(tools=[tool], artifacts=[art, art2])
    assert "duplicate_artifact_id" in _codes(m)


def test_artifact_generated_requires_hash():
    tool = Tool(id="t1", name="tool", version="1.0")
    art = Artifact(
        id="a1", kind="migration_report", path="reports/r.json",
        sha256=None, size_bytes=100, producer="t1",
        derived_from=["scenario"], status="generated",
    )
    m = _minimal(tools=[tool], artifacts=[art])
    assert "missing_hash" in _codes(m)


def test_artifact_generated_requires_size():
    tool = Tool(id="t1", name="tool", version="1.0")
    art = Artifact(
        id="a1", kind="migration_report", path="reports/r.json",
        sha256=_SHA, size_bytes=None, producer="t1",
        derived_from=["scenario"], status="generated",
    )
    m = _minimal(tools=[tool], artifacts=[art])
    assert "missing_size" in _codes(m)


def test_artifact_unknown_producer():
    art = Artifact(
        id="a1", kind="migration_report", path="reports/r.json",
        sha256=None, size_bytes=None, producer="ghost-tool", status="planned",
    )
    m = _minimal(artifacts=[art])
    assert "unknown_producer" in _codes(m)


# ---------------------------------------------------------------------------
# derived_from (including self-reference, Hallazgo 3)
# ---------------------------------------------------------------------------


def test_unknown_derived_from():
    tool = Tool(id="t1", name="tool", version="1.0")
    art = Artifact(
        id="a1", kind="migration_report", path="reports/r.json",
        sha256=None, size_bytes=None, producer="t1",
        derived_from=["nonexistent-id"], status="planned",
    )
    m = _minimal(tools=[tool], artifacts=[art])
    assert "unknown_derived_from" in _codes(m)


def test_self_reference_in_derived_from():
    """An artifact must not list its own ID in derived_from."""
    art = Artifact(
        id="a1", kind="migration_report", path="reports/r.json",
        sha256=None, size_bytes=None, producer=None,
        derived_from=["a1"], status="planned",
    )
    m = _minimal(artifacts=[art])
    assert "self_reference_in_derived_from" in _codes(m)


def test_artifact_can_derive_from_other_artifact():
    tool = Tool(id="t1", name="tool", version="1.0")
    art1 = Artifact(
        id="a1", kind="clean_trace", path="reports/r1.json",
        sha256=_SHA, size_bytes=10, producer="t1",
        derived_from=["scenario"], status="generated",
    )
    art2 = Artifact(
        id="a2", kind="writes_trace", path="reports/r2.json",
        sha256=_SHA, size_bytes=10, producer="t1",
        derived_from=["a1"], status="generated",
    )
    m = _minimal(tools=[tool], artifacts=[art1, art2])
    assert "unknown_derived_from" not in _codes(m)


def test_duplicate_derived_from_entry():
    art = Artifact(
        id="a1", kind="migration_report", path="reports/r.json",
        sha256=None, size_bytes=None, producer=None,
        derived_from=["scenario", "scenario"], status="planned",
    )
    m = _minimal(artifacts=[art])
    assert "duplicate_derived_from" in _codes(m)


# ---------------------------------------------------------------------------
# Events — sequence (Hallazgo 4)
# ---------------------------------------------------------------------------


def test_duplicate_event_sequence():
    e1 = Event(sequence=1, type="prepared", timestamp="2026-06-23T14:00:00Z", message="a")
    e2 = Event(sequence=1, type="started", timestamp="2026-06-23T14:01:00Z", message="b")
    m = _minimal(events=[e1, e2])
    assert "duplicate_event_sequence" in _codes(m)


def test_event_sequence_zero():
    e = Event(sequence=0, type="prepared", timestamp="2026-06-23T14:00:00Z", message="a")
    m = _minimal(events=[e])
    assert "invalid_event_sequence" in _codes(m)


def test_event_sequence_negative():
    e = Event(sequence=-5, type="prepared", timestamp="2026-06-23T14:00:00Z", message="a")
    m = _minimal(events=[e])
    assert "invalid_event_sequence" in _codes(m)


def test_event_sequence_non_increasing():
    """Events must be strictly increasing in list order."""
    e1 = Event(sequence=1, type="prepared", timestamp="2026-06-23T14:00:00Z", message="a")
    e2 = Event(sequence=3, type="started", timestamp="2026-06-23T14:01:00Z", message="b")
    e3 = Event(sequence=2, type="finished", timestamp="2026-06-23T14:02:00Z", message="c")
    m = _minimal(events=[e1, e2, e3])
    assert "non_increasing_sequence" in _codes(m)


def test_event_sequence_strictly_increasing_ok():
    e1 = Event(sequence=1, type="prepared", timestamp="2026-06-23T14:00:00Z", message="a")
    e2 = Event(sequence=5, type="started", timestamp="2026-06-23T14:01:00Z", message="b")
    e3 = Event(sequence=10, type="finished", timestamp="2026-06-23T14:02:00Z", message="c")
    m = _minimal(events=[e1, e2, e3])
    codes = _codes(m)
    assert "invalid_event_sequence" not in codes
    assert "duplicate_event_sequence" not in codes
    assert "non_increasing_sequence" not in codes


# ---------------------------------------------------------------------------
# Events — sequence type robustness (must not crash with non-int values)
# ---------------------------------------------------------------------------


def test_event_sequence_string_no_traceback():
    """sequence='1' (string) must produce invalid_event_sequence, not TypeError."""
    e = Event(sequence="1", type="prepared", timestamp="2026-06-23T14:00:00Z", message="a")  # type: ignore[arg-type]
    m = _minimal(events=[e])
    codes = _codes(m)
    assert "invalid_event_sequence" in codes


def test_event_sequence_float_rejected():
    e = Event(sequence=1.0, type="prepared", timestamp="2026-06-23T14:00:00Z", message="a")  # type: ignore[arg-type]
    m = _minimal(events=[e])
    assert "invalid_event_sequence" in _codes(m)


def test_event_sequence_bool_true_rejected():
    """True is a bool (subclass of int) and must be rejected."""
    e = Event(sequence=True, type="prepared", timestamp="2026-06-23T14:00:00Z", message="a")  # type: ignore[arg-type]
    m = _minimal(events=[e])
    assert "invalid_event_sequence" in _codes(m)


def test_event_sequence_none_rejected():
    e = Event(sequence=None, type="prepared", timestamp="2026-06-23T14:00:00Z", message="a")  # type: ignore[arg-type]
    m = _minimal(events=[e])
    assert "invalid_event_sequence" in _codes(m)


def test_event_sequence_invalid_type_no_errors_in_other_events():
    """An invalid-type sequence in one event must not prevent other events from being checked."""
    e_bad = Event(sequence="bad", type="prepared", timestamp="2026-06-23T14:00:00Z", message="a")  # type: ignore[arg-type]
    e_good = Event(sequence=1, type="started", timestamp="2026-06-23T14:01:00Z", message="b")
    m = _minimal(events=[e_bad, e_good])
    codes = _codes(m)
    # The bad event fires invalid_event_sequence; the good one must not be flagged as non-increasing.
    assert "invalid_event_sequence" in codes
    assert "non_increasing_sequence" not in codes


def test_invalid_sequence_fixture_no_traceback():
    """Fixture with sequence='1' (string) must not raise — must return structured error."""
    from peoplenet_process_extractor.manifest.serialization import deserialize_manifest
    text = (FIXTURE_DIR / "invalid_sequence.json").read_text(encoding="utf-8")
    m = deserialize_manifest(text)
    codes = _codes(m)
    assert "invalid_event_sequence" in codes


# ---------------------------------------------------------------------------
# Events — timestamp format (Hallazgo 4)
# ---------------------------------------------------------------------------


def test_event_timestamp_naive_rejected():
    """Timestamps without timezone must be rejected."""
    e = Event(sequence=1, type="prepared", timestamp="2026-06-23T14:00:00", message="a")
    m = _minimal(events=[e])
    assert "invalid_event_timestamp" in _codes(m)


def test_event_timestamp_invalid_string():
    e = Event(sequence=1, type="prepared", timestamp="not-a-date", message="a")
    m = _minimal(events=[e])
    assert "invalid_event_timestamp" in _codes(m)


def test_event_timestamp_z_suffix_ok():
    e = Event(sequence=1, type="prepared", timestamp="2026-06-23T14:00:00Z", message="a")
    m = _minimal(events=[e])
    assert "invalid_event_timestamp" not in _codes(m)


def test_event_timestamp_offset_ok():
    e = Event(sequence=1, type="prepared", timestamp="2026-06-23T14:00:00+05:30", message="a")
    m = _minimal(events=[e])
    assert "invalid_event_timestamp" not in _codes(m)


# ---------------------------------------------------------------------------
# Timestamps — started_at / finished_at (Hallazgo 4)
# ---------------------------------------------------------------------------


def test_started_at_naive_rejected():
    m = _minimal(started_at="2026-06-23T14:00:00")  # no timezone
    assert "invalid_timestamp" in _codes(m)


def test_finished_at_naive_rejected():
    m = _minimal(
        started_at="2026-06-23T14:00:00Z",
        finished_at="2026-06-23T15:00:00",  # no timezone
    )
    assert "invalid_timestamp" in _codes(m)


def test_finished_before_started():
    m = _minimal(
        started_at="2026-06-23T15:00:00Z",
        finished_at="2026-06-23T14:00:00Z",
    )
    assert "incoherent_timestamps" in _codes(m)


def test_finished_after_started_ok():
    m = _minimal(
        started_at="2026-06-23T14:00:00Z",
        finished_at="2026-06-23T15:00:00Z",
    )
    assert "incoherent_timestamps" not in _codes(m)


def test_finished_equals_started_ok():
    """finished_at == started_at is valid (instantaneous run)."""
    m = _minimal(
        started_at="2026-06-23T14:00:00Z",
        finished_at="2026-06-23T14:00:00Z",
    )
    assert "incoherent_timestamps" not in _codes(m)


def test_timestamps_with_offsets_compared_correctly():
    """Comparison must use parsed datetimes, not string order."""
    m = _minimal(
        started_at="2026-06-23T10:00:00+05:30",   # = 04:30 UTC
        finished_at="2026-06-23T05:00:00Z",         # = 05:00 UTC → after started_at
    )
    assert "incoherent_timestamps" not in _codes(m)


def test_only_started_at_ok():
    m = _minimal(started_at="2026-06-23T14:00:00Z")
    assert "incoherent_timestamps" not in _codes(m)


# ---------------------------------------------------------------------------
# Status constraints
# ---------------------------------------------------------------------------


def test_succeeded_with_errors():
    m = _minimal(
        status="succeeded",
        errors=[ManifestEntry(code="E1", message="an error")],
    )
    assert "succeeded_with_errors" in _codes(m)


def test_succeeded_with_error_event():
    e = Event(sequence=1, type="error", timestamp="2026-06-23T14:00:00Z", message="err")
    m = _minimal(status="succeeded", events=[e])
    assert "succeeded_with_errors" in _codes(m)


def test_failed_without_errors():
    m = _minimal(status="failed")
    assert "failed_without_errors" in _codes(m)


def test_failed_with_error_is_ok():
    m = _minimal(
        status="failed",
        errors=[ManifestEntry(code="E1", message="an error")],
    )
    assert "failed_without_errors" not in _codes(m)


def test_failed_with_error_event_is_ok():
    e = Event(sequence=1, type="error", timestamp="2026-06-23T14:00:00Z", message="err")
    m = _minimal(status="failed", events=[e])
    assert "failed_without_errors" not in _codes(m)


# ---------------------------------------------------------------------------
# Events — reference_id
# ---------------------------------------------------------------------------


def test_invalid_event_type():
    e = Event(sequence=1, type="not_a_type", timestamp="2026-06-23T14:00:00Z", message="a")
    m = _minimal(events=[e])
    assert "invalid_event_type" in _codes(m)


def test_event_unknown_reference_id():
    e = Event(
        sequence=1, type="prepared",
        timestamp="2026-06-23T14:00:00Z",
        message="a",
        reference_id="ghost-id",
    )
    m = _minimal(events=[e])
    assert "unknown_event_reference" in _codes(m)


def test_event_known_reference_id_ok():
    e = Event(
        sequence=1, type="prepared",
        timestamp="2026-06-23T14:00:00Z",
        message="a",
        reference_id="scenario",  # the scenario source ID in _minimal()
    )
    m = _minimal(events=[e])
    assert "unknown_event_reference" not in _codes(m)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def test_valid_fixture_passes():
    from peoplenet_process_extractor.manifest.serialization import deserialize_manifest
    text = (FIXTURE_DIR / "valid_run_manifest.json").read_text(encoding="utf-8")
    m = deserialize_manifest(text)
    assert _codes(m) == []


def test_invalid_duplicate_ids_fixture():
    from peoplenet_process_extractor.manifest.serialization import deserialize_manifest
    text = (FIXTURE_DIR / "invalid_duplicate_ids.json").read_text(encoding="utf-8")
    m = deserialize_manifest(text)
    assert "duplicate_source_id" in _codes(m)


def test_invalid_broken_reference_fixture():
    from peoplenet_process_extractor.manifest.serialization import deserialize_manifest
    text = (FIXTURE_DIR / "invalid_broken_reference.json").read_text(encoding="utf-8")
    m = deserialize_manifest(text)
    assert "unknown_derived_from" in _codes(m)


def test_invalid_status_fixture():
    from peoplenet_process_extractor.manifest.serialization import deserialize_manifest
    text = (FIXTURE_DIR / "invalid_status.json").read_text(encoding="utf-8")
    m = deserialize_manifest(text)
    assert "invalid_run_status" in _codes(m)


def test_invalid_hash_fixture():
    from peoplenet_process_extractor.manifest.serialization import deserialize_manifest
    text = (FIXTURE_DIR / "invalid_hash.json").read_text(encoding="utf-8")
    m = deserialize_manifest(text)
    assert "invalid_sha256" in _codes(m)
