"""
Serialization and deserialization for corpus-manifest-v1.

Round-trip policy:
- All null fields are serialized as JSON null (never omitted).
- Empty lists serialize as [].
- Dicts serialize with stable sorted key order.
- Output is UTF-8, indented 2 spaces, terminated with a newline.
"""
from __future__ import annotations

import json
from typing import Any

from .models import (
    CorpusManifest,
    CorpusSummary,
    FileEntry,
    GitInfo,
    Ln4Structure,
    M4oStructure,
    RootInfo,
)
from .validation import ValidationError, validate_manifest


class DeserializationError(Exception):
    """Raised when JSON cannot be parsed into a valid CorpusManifest."""


def serialize_manifest(manifest: CorpusManifest) -> str:
    """Return a deterministic JSON string (UTF-8, 2-space indent, trailing newline)."""
    return json.dumps(_manifest_to_dict(manifest), indent=2, ensure_ascii=False) + "\n"


def deserialize_manifest(text: str) -> tuple[CorpusManifest, list[ValidationError]]:
    """
    Parse JSON text and return (CorpusManifest, validation_errors).

    Raises DeserializationError on JSON parse failures or structural type errors.
    Validation errors (business-rule violations) are returned in the second element.
    """
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DeserializationError(f"Invalid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise DeserializationError(
            f"Expected a JSON object at the top level, got {type(raw).__name__}."
        )

    manifest = _dict_to_manifest(raw)
    errors = validate_manifest(manifest)
    return manifest, errors


# ── to-dict helpers ───────────────────────────────────────────────────────


def _manifest_to_dict(m: CorpusManifest) -> dict[str, Any]:
    return {
        "schema_version": m.schema_version,
        "corpus_id": m.corpus_id,
        "created_at": m.created_at,
        "root": _root_to_dict(m.root),
        "git": _git_to_dict(m.git),
        "included_source_roots": list(m.included_source_roots),
        "files": [_file_to_dict(f) for f in m.files],
        "summary": _summary_to_dict(m.summary),
        "warnings": list(m.warnings),
        "errors": list(m.errors),
    }


def _root_to_dict(r: RootInfo) -> dict[str, Any]:
    return {"label": r.label, "path_policy": r.path_policy}


def _git_to_dict(g: GitInfo) -> dict[str, Any]:
    return {"commit": g.commit, "dirty": g.dirty}


def _file_to_dict(f: FileEntry) -> dict[str, Any]:
    return {
        "path": f.path,
        "sha256": f.sha256,
        "size_bytes": f.size_bytes,
        "extension": f.extension,
        "source_root": f.source_root,
        "classification": f.classification,
        "structure": _structure_to_dict(f.structure),
        "m4o_structure": _m4o_structure_to_dict(f.m4o_structure),
        "warnings": list(f.warnings),
    }


def _structure_to_dict(s: Ln4Structure | None) -> dict[str, Any] | None:
    if s is None:
        return None
    return {
        "meta4object": s.meta4object,
        "item_type": s.item_type,
        "item_name": s.item_name,
        "rule_id": s.rule_id,
        "rule_date": s.rule_date,
    }


def _m4o_structure_to_dict(s: M4oStructure | None) -> dict[str, Any] | None:
    if s is None:
        return None
    return {
        "id_t3": s.id_t3,
        "id_node": s.id_node,
    }


def _summary_to_dict(s: CorpusSummary) -> dict[str, Any]:
    return {
        "total_files": s.total_files,
        "total_bytes": s.total_bytes,
        "structured_files": s.structured_files,
        "unstructured_files": s.unstructured_files,
        "by_source_root": dict(sorted(s.by_source_root.items())),
        "by_extension": dict(sorted(s.by_extension.items())),
        "by_classification": dict(sorted(s.by_classification.items())),
    }


# ── from-dict helpers ─────────────────────────────────────────────────────


def _manifest_from_dict(d: dict[str, Any]) -> CorpusManifest:
    return _dict_to_manifest(d)


def _dict_to_manifest(d: dict[str, Any]) -> CorpusManifest:
    try:
        root_raw = _require_dict(d, "root")
        git_raw = _require_dict(d, "git")

        return CorpusManifest(
            schema_version=_require_str(d, "schema_version"),
            corpus_id=_require_str(d, "corpus_id"),
            created_at=_require_str(d, "created_at"),
            root=_dict_to_root(root_raw),
            git=_dict_to_git(git_raw),
            included_source_roots=_require_list_of_str(d, "included_source_roots"),
            files=[_dict_to_file(f) for f in _require_list(d, "files")],
            summary=_dict_to_summary(_require_dict(d, "summary")),
            warnings=_require_list_of_str(d, "warnings"),
            errors=_require_list_of_str(d, "errors"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DeserializationError(str(exc)) from exc


def _dict_to_root(d: dict[str, Any]) -> RootInfo:
    return RootInfo(
        label=_require_str(d, "label"),
        path_policy=_require_str(d, "path_policy"),
    )


def _dict_to_git(d: dict[str, Any]) -> GitInfo:
    commit = d.get("commit")
    dirty = d.get("dirty")
    if commit is not None and not isinstance(commit, str):
        raise DeserializationError(f"git.commit must be a string or null, got {type(commit).__name__}.")
    if dirty is not None and not isinstance(dirty, bool):
        raise DeserializationError(f"git.dirty must be a boolean or null, got {type(dirty).__name__}.")
    return GitInfo(commit=commit, dirty=dirty)


def _dict_to_file(d: Any) -> FileEntry:
    if not isinstance(d, dict):
        raise DeserializationError(f"Each file entry must be a JSON object, got {type(d).__name__}.")
    structure_raw = d.get("structure")
    structure = _dict_to_structure(structure_raw) if structure_raw is not None else None
    # m4o_structure is absent in 1.0 manifests — treat missing as null.
    m4o_structure_raw = d.get("m4o_structure")
    m4o_structure = _dict_to_m4o_structure(m4o_structure_raw) if m4o_structure_raw is not None else None
    source_root = d.get("source_root")
    if source_root is not None and not isinstance(source_root, str):
        raise DeserializationError(
            f"source_root must be a string or null, got {type(source_root).__name__}."
        )
    return FileEntry(
        path=_require_str(d, "path"),
        sha256=_require_str(d, "sha256"),
        size_bytes=_require_int(d, "size_bytes"),
        extension=_require_str(d, "extension"),
        source_root=source_root,
        classification=_require_str(d, "classification"),
        structure=structure,
        m4o_structure=m4o_structure,
        warnings=_require_list_of_str(d, "warnings"),
    )


def _dict_to_structure(d: Any) -> Ln4Structure:
    if not isinstance(d, dict):
        raise DeserializationError(
            f"structure must be a JSON object or null, got {type(d).__name__}."
        )
    rule_id = d.get("rule_id")
    rule_date = d.get("rule_date")
    if rule_id is not None and not isinstance(rule_id, str):
        raise DeserializationError("structure.rule_id must be string or null.")
    if rule_date is not None and not isinstance(rule_date, str):
        raise DeserializationError("structure.rule_date must be string or null.")
    return Ln4Structure(
        meta4object=_require_str(d, "meta4object"),
        item_type=_require_str(d, "item_type"),
        item_name=_require_str(d, "item_name"),
        rule_id=rule_id,
        rule_date=rule_date,
    )


def _dict_to_m4o_structure(d: Any) -> M4oStructure:
    if not isinstance(d, dict):
        raise DeserializationError(
            f"m4o_structure must be a JSON object or null, got {type(d).__name__}."
        )
    id_t3 = _require_str(d, "id_t3")
    id_node = d.get("id_node")
    if id_node is not None and not isinstance(id_node, str):
        raise DeserializationError("m4o_structure.id_node must be a string or null.")
    return M4oStructure(id_t3=id_t3, id_node=id_node)


def _dict_to_summary(d: dict[str, Any]) -> CorpusSummary:
    return CorpusSummary(
        total_files=_require_int(d, "total_files"),
        total_bytes=_require_int(d, "total_bytes"),
        structured_files=_require_int(d, "structured_files"),
        unstructured_files=_require_int(d, "unstructured_files"),
        by_source_root=_require_str_int_dict(d, "by_source_root"),
        by_extension=_require_str_int_dict(d, "by_extension"),
        by_classification=_require_str_int_dict(d, "by_classification"),
    )


# ── type-safe field accessors ─────────────────────────────────────────────


def _require_str(d: dict, key: str) -> str:
    v = d.get(key)
    if v is None:
        raise DeserializationError(f"Missing required field '{key}'.")
    if not isinstance(v, str):
        raise DeserializationError(f"Field '{key}' must be a string, got {type(v).__name__}.")
    return v


def _require_int(d: dict, key: str) -> int:
    v = d.get(key)
    if v is None:
        raise DeserializationError(f"Missing required field '{key}'.")
    if isinstance(v, bool) or not isinstance(v, int):
        raise DeserializationError(f"Field '{key}' must be an integer, got {type(v).__name__}.")
    return v


def _require_dict(d: dict, key: str) -> dict:
    v = d.get(key)
    if v is None:
        raise DeserializationError(f"Missing required field '{key}'.")
    if not isinstance(v, dict):
        raise DeserializationError(f"Field '{key}' must be a JSON object, got {type(v).__name__}.")
    return v


def _require_list(d: dict, key: str) -> list:
    v = d.get(key)
    if v is None:
        raise DeserializationError(f"Missing required field '{key}'.")
    if not isinstance(v, list):
        raise DeserializationError(f"Field '{key}' must be a JSON array, got {type(v).__name__}.")
    return v


def _require_list_of_str(d: dict, key: str) -> list[str]:
    items = _require_list(d, key)
    for i, item in enumerate(items):
        if not isinstance(item, str):
            raise DeserializationError(
                f"Field '{key}[{i}]' must be a string, got {type(item).__name__}."
            )
    return items


def _require_str_int_dict(d: dict, key: str) -> dict[str, int]:
    v = _require_dict(d, key)
    result = {}
    for k, val in v.items():
        if not isinstance(k, str):
            raise DeserializationError(f"Keys in '{key}' must be strings.")
        if isinstance(val, bool) or not isinstance(val, int):
            raise DeserializationError(
                f"Values in '{key}' must be integers, got {type(val).__name__} for key '{k}'."
            )
        result[k] = val
    return result
