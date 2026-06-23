import json
from typing import Any

from .models import (
    Artifact,
    Event,
    ManifestEntry,
    RunManifest,
    ScenarioRef,
    SourceFile,
    Tool,
)


def manifest_to_dict(m: RunManifest) -> dict[str, Any]:
    return {
        "schema_version": m.schema_version,
        "run_id": m.run_id,
        "status": m.status,
        "scenario": {
            "path": m.scenario.path,
            "sha256": m.scenario.sha256,
            "size_bytes": m.scenario.size_bytes,
            "scenario_id": m.scenario.scenario_id,
            "schema_version": m.scenario.schema_version,
        },
        "sources": [_source_to_dict(s) for s in m.sources],
        "tools": [_tool_to_dict(t) for t in m.tools],
        "artifacts": [_artifact_to_dict(a) for a in m.artifacts],
        "events": [_event_to_dict(e) for e in m.events],
        "warnings": [_entry_to_dict(w) for w in m.warnings],
        "errors": [_entry_to_dict(e) for e in m.errors],
        "started_at": m.started_at,
        "finished_at": m.finished_at,
    }


def _source_to_dict(s: SourceFile) -> dict[str, Any]:
    return {
        "id": s.id,
        "kind": s.kind,
        "path": s.path,
        "sha256": s.sha256,
        "size_bytes": s.size_bytes,
        "exists": s.exists,
        "required": s.required,
        "description": s.description,
    }


def _tool_to_dict(t: Tool) -> dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "version": t.version,
        "command": t.command,
        "git_commit": t.git_commit,
        "schema_info": t.schema_info,
    }


def _artifact_to_dict(a: Artifact) -> dict[str, Any]:
    return {
        "id": a.id,
        "kind": a.kind,
        "path": a.path,
        "sha256": a.sha256,
        "size_bytes": a.size_bytes,
        "producer": a.producer,
        "derived_from": a.derived_from,
        "status": a.status,
    }


def _event_to_dict(e: Event) -> dict[str, Any]:
    return {
        "sequence": e.sequence,
        "type": e.type,
        "timestamp": e.timestamp,
        "message": e.message,
        "reference_id": e.reference_id,
    }


def _entry_to_dict(e: ManifestEntry) -> dict[str, Any]:
    return {
        "code": e.code,
        "message": e.message,
        "reference_id": e.reference_id,
    }


def manifest_from_dict(data: dict[str, Any]) -> RunManifest:
    scen = data["scenario"]
    return RunManifest(
        schema_version=data["schema_version"],
        run_id=data["run_id"],
        status=data["status"],
        scenario=ScenarioRef(
            path=scen["path"],
            sha256=scen["sha256"],
            size_bytes=scen["size_bytes"],
            scenario_id=scen["scenario_id"],
            schema_version=scen["schema_version"],
        ),
        sources=[_source_from_dict(s) for s in data.get("sources", [])],
        tools=[_tool_from_dict(t) for t in data.get("tools", [])],
        artifacts=[_artifact_from_dict(a) for a in data.get("artifacts", [])],
        events=[_event_from_dict(e) for e in data.get("events", [])],
        warnings=[_entry_from_dict(w) for w in data.get("warnings", [])],
        errors=[_entry_from_dict(e) for e in data.get("errors", [])],
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
    )


def _source_from_dict(d: dict[str, Any]) -> SourceFile:
    return SourceFile(
        id=d["id"],
        kind=d["kind"],
        path=d["path"],
        sha256=d.get("sha256"),
        size_bytes=d.get("size_bytes"),
        exists=d["exists"],
        required=d["required"],
        description=d.get("description"),
    )


def _tool_from_dict(d: dict[str, Any]) -> Tool:
    return Tool(
        id=d["id"],
        name=d["name"],
        version=d["version"],
        command=d.get("command"),
        git_commit=d.get("git_commit"),
        schema_info=d.get("schema_info"),
    )


def _artifact_from_dict(d: dict[str, Any]) -> Artifact:
    return Artifact(
        id=d["id"],
        kind=d["kind"],
        path=d["path"],
        sha256=d.get("sha256"),
        size_bytes=d.get("size_bytes"),
        producer=d.get("producer"),
        derived_from=d.get("derived_from", []),
        status=d["status"],
    )


def _event_from_dict(d: dict[str, Any]) -> Event:
    return Event(
        sequence=d["sequence"],
        type=d["type"],
        timestamp=d["timestamp"],
        message=d["message"],
        reference_id=d.get("reference_id"),
    )


def _entry_from_dict(d: dict[str, Any]) -> ManifestEntry:
    return ManifestEntry(
        code=d["code"],
        message=d["message"],
        reference_id=d.get("reference_id"),
    )


def serialize_manifest(manifest: RunManifest) -> str:
    return json.dumps(manifest_to_dict(manifest), indent=2, ensure_ascii=False) + "\n"


def deserialize_manifest(text: str) -> RunManifest:
    return manifest_from_dict(json.loads(text))
