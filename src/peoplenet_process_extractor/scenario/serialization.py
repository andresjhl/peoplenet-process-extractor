import json
from typing import Any

from .enums import Source, Status
from .migration import MigrationReport
from .models import (
    AnalysisScope,
    EntryPoint,
    Process,
    PropertyBinding,
    RuntimeValue,
    Scenario,
    ScopeMethod,
    SourceRef,
    TypedValue,
)


def scenario_to_dict(scenario: Scenario) -> dict[str, Any]:
    return {
        "schema_version": scenario.schema_version,
        "scenario_id": scenario.scenario_id,
        "process": {
            "id": scenario.process.id,
            "source": scenario.process.source.value,
            "status": scenario.process.status.value,
        },
        "entry_point": {
            "meta4object": scenario.entry_point.meta4object,
            "node": scenario.entry_point.node,
            "method": scenario.entry_point.method,
            "arguments": scenario.entry_point.arguments,
        },
        "entry_inputs": [_typed_value_to_dict(v) for v in scenario.entry_inputs],
        "property_bindings": [
            {"property": b.property, "input": b.input}
            for b in scenario.property_bindings
        ],
        "runtime_values": [_runtime_value_to_dict(v) for v in scenario.runtime_values],
        "flags": [_typed_value_to_dict(f) for f in scenario.flags],
        "configuration": [_typed_value_to_dict(c) for c in scenario.configuration],
        "analysis_scope": {
            "methods": [
                {
                    "name": m.name,
                    "source": m.source.value,
                    "status": m.status.value,
                    "reason": m.reason,
                }
                for m in scenario.analysis_scope.methods
            ]
        },
        "notes": scenario.notes,
        "source_files": {
            "legacy_file": scenario.source_files.legacy_file,
            "original_call": scenario.source_files.original_call,
            "hash": scenario.source_files.hash,
            "source_type": scenario.source_files.source_type,
        },
    }


def _typed_value_to_dict(v: TypedValue) -> dict[str, Any]:
    return {
        "name": v.name,
        "value": v.value,
        "type": v.type,
        "source": v.source.value,
        "status": v.status.value,
    }


def _runtime_value_to_dict(v: RuntimeValue) -> dict[str, Any]:
    # All schema fields are always serialized; optional absent values become null.
    return {
        "name": v.name,
        "value": v.value,
        "type": v.type,
        "source": v.source.value,
        "status": v.status.value,
        "evidence": v.evidence,
        "expression": v.expression,
    }


def scenario_from_dict(data: dict[str, Any]) -> Scenario:
    proc = data["process"]
    ep = data["entry_point"]
    scope = data.get("analysis_scope", {})
    sf = data.get("source_files", {})

    return Scenario(
        schema_version=data["schema_version"],
        scenario_id=data["scenario_id"],
        process=Process(
            id=proc["id"],
            source=Source(proc["source"]),
            status=Status(proc["status"]),
        ),
        entry_point=EntryPoint(
            meta4object=ep["meta4object"],
            node=ep["node"],
            method=ep["method"],
            arguments=ep.get("arguments", []),
        ),
        entry_inputs=[_typed_value_from_dict(v) for v in data.get("entry_inputs", [])],
        property_bindings=[
            PropertyBinding(property=b["property"], input=b["input"])
            for b in data.get("property_bindings", [])
        ],
        runtime_values=[_runtime_value_from_dict(v) for v in data.get("runtime_values", [])],
        flags=[_typed_value_from_dict(f) for f in data.get("flags", [])],
        configuration=[_typed_value_from_dict(c) for c in data.get("configuration", [])],
        analysis_scope=AnalysisScope(
            methods=[
                ScopeMethod(
                    name=m["name"],
                    source=Source(m["source"]),
                    status=Status(m["status"]),
                    reason=m.get("reason"),
                )
                for m in scope.get("methods", [])
            ]
        ),
        notes=data.get("notes", []),
        source_files=SourceRef(
            legacy_file=sf.get("legacy_file"),
            original_call=sf.get("original_call"),
            hash=sf.get("hash"),
            source_type=sf.get("source_type"),
        ),
    )


def _typed_value_from_dict(d: dict[str, Any]) -> TypedValue:
    return TypedValue(
        name=d["name"],
        value=d["value"],
        type=d["type"],
        source=Source(d["source"]),
        status=Status(d["status"]),
    )


def _runtime_value_from_dict(d: dict[str, Any]) -> RuntimeValue:
    return RuntimeValue(
        name=d["name"],
        value=d["value"],
        type=d["type"],
        source=Source(d["source"]),
        status=Status(d["status"]),
        evidence=d.get("evidence"),
        expression=d.get("expression"),
    )


def serialize_scenario(scenario: Scenario) -> str:
    return json.dumps(scenario_to_dict(scenario), indent=2, ensure_ascii=False) + "\n"


def deserialize_scenario(text: str) -> Scenario:
    return scenario_from_dict(json.loads(text))


def report_to_dict(report: MigrationReport) -> dict[str, Any]:
    return {
        "migrated_fields": report.migrated_fields,
        "defaults_applied": [
            {"field": d.field, "value": d.value} for d in report.defaults_applied
        ],
        "warnings": [{"code": w.code, "message": w.message} for w in report.warnings],
        "unknown_legacy_fields": report.unknown_legacy_fields,
        "errors": [{"code": e.code, "message": e.message} for e in report.errors],
        "contradictions": report.contradictions,
        "decisions": report.decisions,
    }


def serialize_report(report: MigrationReport) -> str:
    return json.dumps(report_to_dict(report), indent=2, ensure_ascii=False) + "\n"
