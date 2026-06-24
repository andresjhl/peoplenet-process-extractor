"""
Serialization and deserialization for reference-extraction-v1.

Round-trip policy:
- All null fields are serialized as JSON null (never omitted).
- Empty lists serialize as [].
- Key order is deterministic (follows dataclass field order).
- Output is UTF-8, indented 2 spaces, LF line endings, trailing newline, no BOM.
"""
from __future__ import annotations

import json
from typing import Any

from .models import (
    Argument,
    ExtractionSummary,
    FileError,
    FileResult,
    Generator,
    Reference,
    ReferenceExtraction,
    SourceRef,
)


class DeserializationError(Exception):
    """Raised when JSON cannot be parsed into a valid ReferenceExtraction."""


def serialize_extraction(extraction: ReferenceExtraction) -> str:
    """Return canonical JSON string: UTF-8, 2-space indent, LF endings, trailing newline."""
    return json.dumps(_extraction_to_dict(extraction), indent=2, ensure_ascii=False) + "\n"


def deserialize_extraction(text: str) -> ReferenceExtraction:
    """
    Parse JSON text and return ReferenceExtraction.

    Raises ValueError or DeserializationError on structural problems.
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
        return _dict_to_extraction(raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise DeserializationError(str(exc)) from exc


# ── to-dict helpers ────────────────────────────────────────────────────────


def _extraction_to_dict(e: ReferenceExtraction) -> dict[str, Any]:
    return {
        "format": e.format,
        "schema_version": e.schema_version,
        "generator": _generator_to_dict(e.generator),
        "created_at": e.created_at,
        "source_manifest": _source_ref_to_dict(e.source_manifest),
        "source_index": _source_ref_to_dict(e.source_index),
        "summary": _summary_to_dict(e.summary),
        "files": [_file_result_to_dict(f) for f in e.files],
    }


def _generator_to_dict(g: Generator) -> dict[str, Any]:
    return {"name": g.name, "version": g.version}


def _source_ref_to_dict(s: SourceRef) -> dict[str, Any]:
    return {"sha256": s.sha256, "size_bytes": s.size_bytes}


def _summary_to_dict(s: ExtractionSummary) -> dict[str, Any]:
    return {
        "files_total": s.files_total,
        "files_processed": s.files_processed,
        "files_with_calls": s.files_with_calls,
        "calls_total": s.calls_total,
        "observed": s.observed,
        "partially_parsed": s.partially_parsed,
        "ambiguous": s.ambiguous,
        "malformed": s.malformed,
        "unsupported": s.unsupported,
        "file_errors": s.file_errors,
    }


def _file_result_to_dict(f: FileResult) -> dict[str, Any]:
    return {
        "path": f.path,
        "source_file_id": f.source_file_id,
        "source_file_sha256": f.source_file_sha256,
        "encoding": f.encoding,
        "line_ending": f.line_ending,
        "status": f.status,
        "errors": [_file_error_to_dict(e) for e in f.errors],
        "references": [_reference_to_dict(r) for r in f.references],
    }


def _file_error_to_dict(e: FileError) -> dict[str, Any]:
    return {
        "code": e.code,
        "message": e.message,
        "evidence": e.evidence,
    }


def _reference_to_dict(r: Reference) -> dict[str, Any]:
    return {
        "id": r.id,
        "kind": r.kind,
        "function_name": r.function_name,
        "status": r.status,
        "source_file_id": r.source_file_id,
        "path": r.path,
        "source_file_sha256": r.source_file_sha256,
        "start_offset": r.start_offset,
        "end_offset": r.end_offset,
        "line_start": r.line_start,
        "column_start": r.column_start,
        "line_end": r.line_end,
        "column_end": r.column_end,
        "raw_expression": r.raw_expression,
        "raw_arguments": r.raw_arguments,
        "arguments": [_argument_to_dict(a) for a in r.arguments],
        "parser_rule": r.parser_rule,
        "diagnostics": list(r.diagnostics),
    }


def _argument_to_dict(a: Argument) -> dict[str, Any]:
    return {
        "position": a.position,
        "raw": a.raw,
        "kind": a.kind,
        "literal_value": a.literal_value,
        "status": a.status,
    }


# ── from-dict helpers ──────────────────────────────────────────────────────


def _dict_to_extraction(d: dict[str, Any]) -> ReferenceExtraction:
    return ReferenceExtraction(
        format=_require_str(d, "format"),
        schema_version=_require_int(d, "schema_version"),
        generator=_dict_to_generator(_require_dict(d, "generator")),
        created_at=_require_str(d, "created_at"),
        source_manifest=_dict_to_source_ref(_require_dict(d, "source_manifest")),
        source_index=_dict_to_source_ref(_require_dict(d, "source_index")),
        summary=_dict_to_summary(_require_dict(d, "summary")),
        files=[_dict_to_file_result(f) for f in _require_list(d, "files")],
    )


def _dict_to_generator(d: dict[str, Any]) -> Generator:
    return Generator(
        name=_require_str(d, "name"),
        version=_require_str(d, "version"),
    )


def _dict_to_source_ref(d: dict[str, Any]) -> SourceRef:
    return SourceRef(
        sha256=_require_str(d, "sha256"),
        size_bytes=_require_int(d, "size_bytes"),
    )


def _dict_to_summary(d: dict[str, Any]) -> ExtractionSummary:
    return ExtractionSummary(
        files_total=_require_int(d, "files_total"),
        files_processed=_require_int(d, "files_processed"),
        files_with_calls=_require_int(d, "files_with_calls"),
        calls_total=_require_int(d, "calls_total"),
        observed=_require_int(d, "observed"),
        partially_parsed=_require_int(d, "partially_parsed"),
        ambiguous=_require_int(d, "ambiguous"),
        malformed=_require_int(d, "malformed"),
        unsupported=_require_int(d, "unsupported"),
        file_errors=_require_int(d, "file_errors"),
    )


def _dict_to_file_result(d: Any) -> FileResult:
    if not isinstance(d, dict):
        raise DeserializationError(f"File entry must be a JSON object, got {type(d).__name__}.")
    sha256_val = d.get("source_file_sha256")
    encoding_val = d.get("encoding")
    line_ending_val = d.get("line_ending")
    return FileResult(
        path=_require_str(d, "path"),
        source_file_id=_require_int(d, "source_file_id"),
        source_file_sha256=sha256_val if isinstance(sha256_val, str) else None,
        encoding=encoding_val if isinstance(encoding_val, str) else None,
        line_ending=line_ending_val if isinstance(line_ending_val, str) else None,
        status=_require_str(d, "status"),
        errors=[_dict_to_file_error(e) for e in _require_list(d, "errors")],
        references=[_dict_to_reference(r) for r in _require_list(d, "references")],
    )


def _dict_to_file_error(d: Any) -> FileError:
    if not isinstance(d, dict):
        raise DeserializationError(f"FileError must be a JSON object, got {type(d).__name__}.")
    evidence_val = d.get("evidence")
    return FileError(
        code=_require_str(d, "code"),
        message=_require_str(d, "message"),
        evidence=evidence_val if isinstance(evidence_val, str) else None,
    )


def _dict_to_reference(d: Any) -> Reference:
    if not isinstance(d, dict):
        raise DeserializationError(f"Reference must be a JSON object, got {type(d).__name__}.")
    return Reference(
        id=_require_str(d, "id"),
        kind=_require_str(d, "kind"),
        function_name=_require_str(d, "function_name"),
        status=_require_str(d, "status"),
        source_file_id=_require_int(d, "source_file_id"),
        path=_require_str(d, "path"),
        source_file_sha256=_require_str(d, "source_file_sha256"),
        start_offset=_require_int(d, "start_offset"),
        end_offset=_require_int(d, "end_offset"),
        line_start=_require_int(d, "line_start"),
        column_start=_require_int(d, "column_start"),
        line_end=_require_int(d, "line_end"),
        column_end=_require_int(d, "column_end"),
        raw_expression=_require_str(d, "raw_expression"),
        raw_arguments=_require_str(d, "raw_arguments"),
        arguments=[_dict_to_argument(a) for a in _require_list(d, "arguments")],
        parser_rule=_require_str(d, "parser_rule"),
        diagnostics=_require_list_of_str(d, "diagnostics"),
    )


def _dict_to_argument(d: Any) -> Argument:
    if not isinstance(d, dict):
        raise DeserializationError(f"Argument must be a JSON object, got {type(d).__name__}.")
    lit_val = d.get("literal_value")
    return Argument(
        position=_require_int(d, "position"),
        raw=_require_str(d, "raw"),
        kind=_require_str(d, "kind"),
        literal_value=lit_val if isinstance(lit_val, str) else None,
        status=_require_str(d, "status"),
    )


# ── type-safe field accessors ──────────────────────────────────────────────


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
