"""
Serialization and deserialization for m4object-node-index-v1.

Round-trip policy:
- All null fields serialized as JSON null (never omitted).
- Empty lists serialize as [].
- Key order follows dataclass field order (deterministic).
- Output is JSON UTF-8, 2-space indent, trailing newline.
- bool values for is_root serialize as JSON true/false.
"""
from __future__ import annotations

import json
from typing import Any

from .models import (
    AliasBinding,
    CorpusManifestRef,
    Diagnostic,
    Generator,
    InheritanceEdge,
    M4oEvidence,
    M4oNodeIndex,
    NodeBinding,
    NodeIndexSummary,
)


class DeserializationError(Exception):
    """Raised when JSON cannot be parsed into a valid M4oNodeIndex."""


def serialize_index(index: M4oNodeIndex) -> str:
    """Return canonical JSON: UTF-8, 2-space indent, trailing newline."""
    return json.dumps(_index_to_dict(index), indent=2, ensure_ascii=False) + "\n"


def deserialize_index(text: str) -> M4oNodeIndex:
    """
    Parse JSON text and return M4oNodeIndex.

    Raises DeserializationError on JSON or structural failures.
    """
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DeserializationError(f"Invalid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise DeserializationError(
            f"Expected a JSON object at the top level, got {type(raw).__name__}."
        )

    try:
        return _dict_to_index(raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise DeserializationError(str(exc)) from exc


# ── to-dict ────────────────────────────────────────────────────────────────


def _index_to_dict(idx: M4oNodeIndex) -> dict[str, Any]:
    return {
        "format": idx.format,
        "schema_version": idx.schema_version,
        "generator": _generator_to_dict(idx.generator),
        "created_at": idx.created_at,
        "source_manifest": _manifest_ref_to_dict(idx.source_manifest),
        "node_bindings": [_node_binding_to_dict(b) for b in idx.node_bindings],
        "alias_bindings": [_alias_binding_to_dict(b) for b in idx.alias_bindings],
        "inheritance_edges": [_edge_to_dict(e) for e in idx.inheritance_edges],
        "diagnostics": [_diagnostic_to_dict(d) for d in idx.diagnostics],
        "summary": _summary_to_dict(idx.summary),
    }


def _generator_to_dict(g: Generator) -> dict[str, Any]:
    return {"name": g.name, "version": g.version}


def _manifest_ref_to_dict(r: CorpusManifestRef) -> dict[str, Any]:
    return {
        "corpus_id": r.corpus_id,
        "corpus_schema_version": r.corpus_schema_version,
        "sha256": r.sha256,
        "size_bytes": r.size_bytes,
    }


def _evidence_to_dict(e: M4oEvidence) -> dict[str, Any]:
    return {
        "path": e.path,
        "sha256": e.sha256,
        "classification": e.classification,
        "table": e.table,
        "row_index": e.row_index,
    }


def _node_binding_to_dict(b: NodeBinding) -> dict[str, Any]:
    return {
        "owner_id_t3": b.owner_id_t3,
        "path_id_node": b.path_id_node,
        "content_id_t3": b.content_id_t3,
        "content_id_node": b.content_id_node,
        "id_ti": b.id_ti,
        "is_root": b.is_root,
        "evidence": _evidence_to_dict(b.evidence),
    }


def _alias_binding_to_dict(b: AliasBinding) -> dict[str, Any]:
    return {
        "owner_id_t3": b.owner_id_t3,
        "path_node_reference": b.path_node_reference,
        "alias": b.alias,
        "id_node": b.id_node,
        "id_ti": b.id_ti,
        "id_alias_t3": b.id_alias_t3,
        "evidence": _evidence_to_dict(b.evidence),
    }


def _edge_to_dict(e: InheritanceEdge) -> dict[str, Any]:
    return {
        "owner_id_t3": e.owner_id_t3,
        "base_id_t3": e.base_id_t3,
        "derived_id_t3": e.derived_id_t3,
        "evidence": _evidence_to_dict(e.evidence),
    }


def _diagnostic_to_dict(d: Diagnostic) -> dict[str, Any]:
    return {
        "code": d.code,
        "severity": d.severity,
        "path": d.path,
        "table": d.table,
        "row_index": d.row_index,
        "message": d.message,
    }


def _summary_to_dict(s: NodeIndexSummary) -> dict[str, Any]:
    return {
        "selected_file_count": s.selected_file_count,
        "successfully_parsed_file_count": s.successfully_parsed_file_count,
        "failed_file_count": s.failed_file_count,
        "node_binding_count": s.node_binding_count,
        "alias_binding_count": s.alias_binding_count,
        "inheritance_edge_count": s.inheritance_edge_count,
        "diagnostic_count": s.diagnostic_count,
    }


# ── from-dict ──────────────────────────────────────────────────────────────


_SUPPORTED_FORMAT = "m4object-node-index-v1"
_SUPPORTED_SCHEMA_VERSION = 1


def _dict_to_index(d: dict[str, Any]) -> M4oNodeIndex:
    fmt = _req_str(d, "format")
    if fmt != _SUPPORTED_FORMAT:
        raise DeserializationError(
            f"Unsupported format: {fmt!r}. Expected {_SUPPORTED_FORMAT!r}."
        )
    sv = _req_int(d, "schema_version")
    if sv != _SUPPORTED_SCHEMA_VERSION:
        raise DeserializationError(
            f"Unsupported schema_version: {sv}. Expected {_SUPPORTED_SCHEMA_VERSION}."
        )
    return M4oNodeIndex(
        format=fmt,
        schema_version=sv,
        generator=_dict_to_generator(_req_dict(d, "generator")),
        created_at=_req_str(d, "created_at"),
        source_manifest=_dict_to_manifest_ref(_req_dict(d, "source_manifest")),
        node_bindings=[_dict_to_node_binding(b) for b in _req_list(d, "node_bindings")],
        alias_bindings=[_dict_to_alias_binding(b) for b in _req_list(d, "alias_bindings")],
        inheritance_edges=[_dict_to_edge(e) for e in _req_list(d, "inheritance_edges")],
        diagnostics=[_dict_to_diagnostic(x) for x in _req_list(d, "diagnostics")],
        summary=_dict_to_summary(_req_dict(d, "summary")),
    )


def _dict_to_generator(d: dict[str, Any]) -> Generator:
    return Generator(name=_req_str(d, "name"), version=_req_str(d, "version"))


def _dict_to_manifest_ref(d: dict[str, Any]) -> CorpusManifestRef:
    return CorpusManifestRef(
        corpus_id=_req_str(d, "corpus_id"),
        corpus_schema_version=_req_str(d, "corpus_schema_version"),
        sha256=_req_str(d, "sha256"),
        size_bytes=_req_int(d, "size_bytes"),
    )


def _dict_to_evidence(d: Any) -> M4oEvidence:
    if not isinstance(d, dict):
        raise DeserializationError(f"evidence must be a JSON object, got {type(d).__name__}.")
    return M4oEvidence(
        path=_req_str(d, "path"),
        sha256=_req_str(d, "sha256"),
        classification=_req_str(d, "classification"),
        table=_req_str(d, "table"),
        row_index=_req_int(d, "row_index"),
    )


def _dict_to_node_binding(d: Any) -> NodeBinding:
    if not isinstance(d, dict):
        raise DeserializationError(
            f"node_binding must be a JSON object, got {type(d).__name__}."
        )
    is_root_raw = d.get("is_root")
    if is_root_raw is not None and not isinstance(is_root_raw, bool):
        raise DeserializationError(
            f"node_binding.is_root must be boolean or null, got {type(is_root_raw).__name__}."
        )
    return NodeBinding(
        owner_id_t3=_req_str(d, "owner_id_t3"),
        path_id_node=_req_str(d, "path_id_node"),
        content_id_t3=_req_str(d, "content_id_t3"),
        content_id_node=_req_str(d, "content_id_node"),
        id_ti=_req_str(d, "id_ti"),
        is_root=is_root_raw,
        evidence=_dict_to_evidence(_req_dict(d, "evidence")),
    )


def _dict_to_alias_binding(d: Any) -> AliasBinding:
    if not isinstance(d, dict):
        raise DeserializationError(
            f"alias_binding must be a JSON object, got {type(d).__name__}."
        )
    return AliasBinding(
        owner_id_t3=_req_str(d, "owner_id_t3"),
        path_node_reference=_req_str(d, "path_node_reference"),
        alias=_req_str(d, "alias"),
        id_node=_req_str(d, "id_node"),
        id_ti=_req_str(d, "id_ti"),
        id_alias_t3=_req_str(d, "id_alias_t3"),
        evidence=_dict_to_evidence(_req_dict(d, "evidence")),
    )


def _dict_to_edge(d: Any) -> InheritanceEdge:
    if not isinstance(d, dict):
        raise DeserializationError(
            f"inheritance_edge must be a JSON object, got {type(d).__name__}."
        )
    return InheritanceEdge(
        owner_id_t3=_req_str(d, "owner_id_t3"),
        base_id_t3=_req_str(d, "base_id_t3"),
        derived_id_t3=_req_str(d, "derived_id_t3"),
        evidence=_dict_to_evidence(_req_dict(d, "evidence")),
    )


def _dict_to_diagnostic(d: Any) -> Diagnostic:
    if not isinstance(d, dict):
        raise DeserializationError(
            f"diagnostic must be a JSON object, got {type(d).__name__}."
        )
    table_v = d.get("table")
    ri_v = d.get("row_index")
    if table_v is not None and not isinstance(table_v, str):
        raise DeserializationError(
            f"diagnostic.table must be string or null, got {type(table_v).__name__}."
        )
    if ri_v is not None:
        if isinstance(ri_v, bool) or not isinstance(ri_v, int):
            raise DeserializationError(
                f"diagnostic.row_index must be integer or null, got {type(ri_v).__name__}."
            )
    return Diagnostic(
        code=_req_str(d, "code"),
        severity=_req_str(d, "severity"),
        path=_req_str(d, "path"),
        table=table_v,
        row_index=ri_v,
        message=_req_str(d, "message"),
    )


def _dict_to_summary(d: dict[str, Any]) -> NodeIndexSummary:
    return NodeIndexSummary(
        selected_file_count=_req_int(d, "selected_file_count"),
        successfully_parsed_file_count=_req_int(d, "successfully_parsed_file_count"),
        failed_file_count=_req_int(d, "failed_file_count"),
        node_binding_count=_req_int(d, "node_binding_count"),
        alias_binding_count=_req_int(d, "alias_binding_count"),
        inheritance_edge_count=_req_int(d, "inheritance_edge_count"),
        diagnostic_count=_req_int(d, "diagnostic_count"),
    )


# ── type-safe accessors ────────────────────────────────────────────────────


def _req_str(d: dict, key: str) -> str:
    v = d.get(key)
    if v is None:
        raise DeserializationError(f"Missing required field '{key}'.")
    if not isinstance(v, str):
        raise DeserializationError(f"Field '{key}' must be a string, got {type(v).__name__}.")
    return v


def _req_int(d: dict, key: str) -> int:
    v = d.get(key)
    if v is None:
        raise DeserializationError(f"Missing required field '{key}'.")
    if isinstance(v, bool) or not isinstance(v, int):
        raise DeserializationError(f"Field '{key}' must be an integer, got {type(v).__name__}.")
    return v


def _req_dict(d: dict, key: str) -> dict:
    v = d.get(key)
    if v is None:
        raise DeserializationError(f"Missing required field '{key}'.")
    if not isinstance(v, dict):
        raise DeserializationError(
            f"Field '{key}' must be a JSON object, got {type(v).__name__}."
        )
    return v


def _req_list(d: dict, key: str) -> list:
    v = d.get(key)
    if v is None:
        raise DeserializationError(f"Missing required field '{key}'.")
    if not isinstance(v, list):
        raise DeserializationError(
            f"Field '{key}' must be a JSON array, got {type(v).__name__}."
        )
    return v
