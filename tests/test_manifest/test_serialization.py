import json
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
from peoplenet_process_extractor.manifest.serialization import (
    deserialize_manifest,
    manifest_to_dict,
    serialize_manifest,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "manifests"

_SHA = "a3f8c1b2d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1"


def _minimal() -> RunManifest:
    return RunManifest(
        schema_version="1.0",
        run_id="run-20260623-abc12345",
        status="prepared",
        scenario=ScenarioRef(
            path="inputs/scenario.json",
            sha256=_SHA,
            size_bytes=1234,
            scenario_id="test-scenario-001",
            schema_version="1.0",
        ),
    )


def test_round_trip_no_loss():
    m = _minimal()
    text = serialize_manifest(m)
    restored = deserialize_manifest(text)
    assert serialize_manifest(restored) == text


def test_output_ends_with_newline():
    assert serialize_manifest(_minimal()).endswith("\n")


def test_output_is_valid_json():
    text = serialize_manifest(_minimal())
    data = json.loads(text)
    assert data["schema_version"] == "1.0"


def test_all_top_level_keys_present():
    data = manifest_to_dict(_minimal())
    required = {
        "schema_version", "run_id", "status", "scenario",
        "sources", "tools", "artifacts", "events",
        "warnings", "errors", "started_at", "finished_at",
    }
    assert required <= set(data.keys())


def test_optional_null_fields_serialized():
    data = manifest_to_dict(_minimal())
    assert data["started_at"] is None
    assert data["finished_at"] is None


def test_round_trip_with_all_collections():
    m = RunManifest(
        schema_version="1.0",
        run_id="run-20260623-full",
        status="prepared",
        scenario=ScenarioRef(
            path="inputs/scenario.json",
            sha256=_SHA,
            size_bytes=42,
            scenario_id="full-test",
            schema_version="1.0",
        ),
        sources=[
            SourceFile(
                id="src-1",
                kind="frontend_call",
                path="inputs/call.json",
                sha256=_SHA,
                size_bytes=100,
                exists=True,
                required=True,
                description="A call trace",
            )
        ],
        tools=[
            Tool(
                id="tool-1",
                name="extractor",
                version="0.1.0",
                command="extractor run",
                git_commit="abc1234",
                schema_info="scenario-v1",
            )
        ],
        artifacts=[
            Artifact(
                id="art-1",
                kind="migration_report",
                path="reports/migration.json",
                sha256=_SHA,
                size_bytes=200,
                producer="tool-1",
                derived_from=["src-1"],
                status="generated",
            )
        ],
        events=[
            Event(
                sequence=1,
                type="prepared",
                timestamp="2026-06-23T14:30:00Z",
                message="Run prepared",
                reference_id=None,
            )
        ],
        warnings=[ManifestEntry(code="W001", message="A warning")],
        errors=[],
        started_at="2026-06-23T14:30:01Z",
        finished_at="2026-06-23T14:45:00Z",
    )
    text = serialize_manifest(m)
    restored = deserialize_manifest(text)
    assert serialize_manifest(restored) == text


def test_load_valid_fixture():
    text = (FIXTURE_DIR / "valid_run_manifest.json").read_text(encoding="utf-8")
    m = deserialize_manifest(text)
    assert m.run_id == "run-20260623-abc12345"
    assert m.status == "prepared"
    assert m.schema_version == "1.0"
    assert len(m.sources) == 1
    assert len(m.tools) == 1
    assert len(m.events) == 1


def test_optional_tool_fields_round_trip():
    m = _minimal()
    m.tools = [Tool(id="t1", name="tool", version="1.0")]
    data = manifest_to_dict(m)
    assert data["tools"][0]["command"] is None
    assert data["tools"][0]["git_commit"] is None
    assert data["tools"][0]["schema_info"] is None


def test_deterministic_output():
    m = _minimal()
    assert serialize_manifest(m) == serialize_manifest(m)
