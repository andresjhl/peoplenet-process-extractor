"""
Query interface for reference-extraction-v1 artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReferenceRow:
    path: str
    reference_id: str
    kind: str
    function_name: str
    status: str
    line_start: int
    column_start: int
    raw_expression: str


def query_references(
    extraction_path: Path,
    path: str | None = None,
    status: str | None = None,
    function_name: str | None = None,
    kind: str | None = None,
) -> list[ReferenceRow]:
    """
    Load extraction and return filtered references in deterministic order (path, start_offset).

    All filters are optional and combined with AND.
    """
    try:
        text = extraction_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Cannot read extraction file: {exc}") from exc

    from .serialization import deserialize_extraction
    extraction = deserialize_extraction(text)

    rows: list[ReferenceRow] = []
    for file_result in extraction.files:
        for ref in file_result.references:
            # Apply filters
            if path is not None and file_result.path != path:
                continue
            if status is not None and ref.status != status:
                continue
            if function_name is not None and ref.function_name != function_name:
                continue
            if kind is not None and ref.kind != kind:
                continue

            rows.append(ReferenceRow(
                path=file_result.path,
                reference_id=ref.id,
                kind=ref.kind,
                function_name=ref.function_name,
                status=ref.status,
                line_start=ref.line_start,
                column_start=ref.column_start,
                raw_expression=ref.raw_expression,
            ))

    # Results are already in (path, start_offset) order because:
    # - files are sorted by path
    # - references within each file are sorted by start_offset
    return rows
