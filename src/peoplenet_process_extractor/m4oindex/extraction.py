"""
Extraction logic for m4object-node-index-v1.

Pipeline per resource:
1. Resolve path; check it stays inside corpus_root (path-escape guard).
2. Read raw bytes (OSError → resource_read_error).
3. Compute SHA-256 and compare with FileEntry.sha256 (drift → resource_hash_mismatch).
4. Decode UTF-8 with optional BOM (invalid_encoding).
5. Parse JSON (invalid_json).
6. Require dict root (invalid_document_type).
7. Extract rows from the expected table (_extract_table_rows).
8. For each row extract typed fields → emit NodeBinding / AliasBinding / InheritanceEdge.
9. Detect and annotate duplicates / conflicts with a deterministic algorithm.
10. Sort all output lists into canonical order.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from importlib.metadata import version as _pkg_version
    _GENERATOR_VERSION = _pkg_version("peoplenet-process-extractor")
except Exception:
    _GENERATOR_VERSION = "unknown"

from ..corpus.models import CorpusManifest, FileEntry
from .models import (
    ALLOWED_CLASSIFICATIONS,
    CLASSIFICATION_TABLE,
    DIAGNOSTIC_SEVERITIES,
    FORMAT,
    GENERATOR_NAME,
    SCHEMA_VERSION,
    AliasBinding,
    CorpusManifestRef,
    Diagnostic,
    Generator,
    InheritanceEdge,
    M4oEvidence,
    M4oNodeIndex,
    NodeBinding,
    NodeIndexSummary,
    _normalize_is_root,
)


# ── helpers ────────────────────────────────────────────────────────────────


def _diag(
    code: str,
    path: str,
    message: str,
    table: str | None = None,
    row_index: int | None = None,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=DIAGNOSTIC_SEVERITIES[code],
        path=path,
        table=table,
        row_index=row_index,
        message=message,
    )


def _is_nonempty_str(v: Any) -> bool:
    return isinstance(v, bool) is False and isinstance(v, str) and bool(v.strip())


def _check_required_field(
    row: dict[str, Any],
    field: str,
    path: str,
    table: str,
    row_index: int,
    diagnostics: list[Diagnostic],
) -> str | None:
    """
    Validate a required string field.

    Returns the raw (untrimmed) value on success, None on failure (diagnostic already added).
    """
    if field not in row:
        diagnostics.append(_diag(
            "missing_required_field",
            path,
            f"Row {row_index}: field '{field}' is missing.",
            table,
            row_index,
        ))
        return None
    v = row[field]
    if not isinstance(v, str) or isinstance(v, bool):
        diagnostics.append(_diag(
            "invalid_field_type",
            path,
            f"Row {row_index}: field '{field}' must be a string, got {type(v).__name__}.",
            table,
            row_index,
        ))
        return None
    if not v.strip():
        diagnostics.append(_diag(
            "empty_required_field",
            path,
            f"Row {row_index}: field '{field}' is empty or whitespace.",
            table,
            row_index,
        ))
        return None
    return v


def _extract_table_rows(
    doc: dict[str, Any],
    table: str,
    path: str,
    diagnostics: list[Diagnostic],
) -> list[dict[str, Any]] | None:
    """
    Extract a list of row dicts from doc[table].

    Returns None when the table produces a blocking error (invalid_table_type).
    Returns [] for missing/null tables (missing_table warning) or empty lists.
    """
    if table not in doc or doc[table] is None:
        diagnostics.append(_diag(
            "missing_table",
            path,
            f"Table '{table}' is absent or null.",
            table,
        ))
        return []
    raw = doc[table]
    if not isinstance(raw, list):
        diagnostics.append(_diag(
            "invalid_table_type",
            path,
            f"Table '{table}' must be a JSON array, got {type(raw).__name__}.",
            table,
        ))
        return None
    return raw


# ── per-classification extractors ─────────────────────────────────────────


def _extract_nodes(
    rows: list[Any],
    entry: FileEntry,
    sha256: str,
    diagnostics: list[Diagnostic],
) -> list[NodeBinding]:
    table = CLASSIFICATION_TABLE["m4o_node_json"]
    owner_id_t3 = entry.m4o_structure.id_t3  # type: ignore[union-attr]
    path_id_node = entry.m4o_structure.id_node or ""  # type: ignore[union-attr]
    bindings: list[NodeBinding] = []

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            diagnostics.append(_diag(
                "invalid_row_type",
                entry.path,
                f"Row {i}: expected JSON object, got {type(row).__name__}.",
                table,
                i,
            ))
            continue

        id_t3 = _check_required_field(row, "ID_T3", entry.path, table, i, diagnostics)
        id_node = _check_required_field(row, "ID_NODE", entry.path, table, i, diagnostics)
        id_ti = _check_required_field(row, "ID_TI", entry.path, table, i, diagnostics)
        if id_t3 is None or id_node is None or id_ti is None:
            continue

        # IS_ROOT normalization
        raw_is_root = row.get("IS_ROOT") if "IS_ROOT" in row else None
        is_root = _normalize_is_root(raw_is_root)
        evidence = M4oEvidence(
            path=entry.path,
            sha256=sha256,
            classification=entry.classification,
            table=table,
            row_index=i,
        )
        if is_root is None:
            diagnostics.append(_diag(
                "invalid_is_root",
                entry.path,
                f"Row {i}: IS_ROOT value {raw_is_root!r} cannot be normalized to bool.",
                table,
                i,
            ))

        # Path/content consistency
        if owner_id_t3 != id_t3:
            diagnostics.append(_diag(
                "id_t3_mismatch",
                entry.path,
                (
                    f"Row {i}: path owner_id_t3={owner_id_t3!r} "
                    f"differs from content ID_T3={id_t3!r}."
                ),
                table,
                i,
            ))
        if path_id_node and path_id_node != id_node:
            diagnostics.append(_diag(
                "id_node_mismatch",
                entry.path,
                (
                    f"Row {i}: path path_id_node={path_id_node!r} "
                    f"differs from content ID_NODE={id_node!r}."
                ),
                table,
                i,
            ))

        bindings.append(NodeBinding(
            owner_id_t3=owner_id_t3,
            path_id_node=path_id_node,
            content_id_t3=id_t3,
            content_id_node=id_node,
            id_ti=id_ti,
            is_root=is_root,
            evidence=evidence,
        ))

    return bindings


def _extract_aliases(
    rows: list[Any],
    entry: FileEntry,
    sha256: str,
    diagnostics: list[Diagnostic],
) -> list[AliasBinding]:
    table = CLASSIFICATION_TABLE["m4o_alias_json"]
    owner_id_t3 = entry.m4o_structure.id_t3  # type: ignore[union-attr]
    path_node_reference = entry.m4o_structure.id_node or ""  # type: ignore[union-attr]
    bindings: list[AliasBinding] = []

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            diagnostics.append(_diag(
                "invalid_row_type",
                entry.path,
                f"Row {i}: expected JSON object, got {type(row).__name__}.",
                table,
                i,
            ))
            continue

        alias = _check_required_field(row, "ALIAS", entry.path, table, i, diagnostics)
        id_node = _check_required_field(row, "ID_NODE", entry.path, table, i, diagnostics)
        id_ti = _check_required_field(row, "ID_TI", entry.path, table, i, diagnostics)
        id_alias_t3 = _check_required_field(row, "ID_ALIAS_T3", entry.path, table, i, diagnostics)
        if alias is None or id_node is None or id_ti is None or id_alias_t3 is None:
            continue

        evidence = M4oEvidence(
            path=entry.path,
            sha256=sha256,
            classification=entry.classification,
            table=table,
            row_index=i,
        )

        if path_node_reference and path_node_reference != id_node:
            diagnostics.append(_diag(
                "path_node_reference_mismatch",
                entry.path,
                (
                    f"Row {i}: path_node_reference={path_node_reference!r} "
                    f"differs from content ID_NODE={id_node!r}."
                ),
                table,
                i,
            ))

        bindings.append(AliasBinding(
            owner_id_t3=owner_id_t3,
            path_node_reference=path_node_reference,
            alias=alias,
            id_node=id_node,
            id_ti=id_ti,
            id_alias_t3=id_alias_t3,
            evidence=evidence,
        ))

    return bindings


def _extract_mappings(
    rows: list[Any],
    entry: FileEntry,
    sha256: str,
    diagnostics: list[Diagnostic],
) -> list[InheritanceEdge]:
    table = CLASSIFICATION_TABLE["m4o_mapping_json"]
    owner_id_t3 = entry.m4o_structure.id_t3  # type: ignore[union-attr]
    edges: list[InheritanceEdge] = []

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            diagnostics.append(_diag(
                "invalid_row_type",
                entry.path,
                f"Row {i}: expected JSON object, got {type(row).__name__}.",
                table,
                i,
            ))
            continue

        base_id_t3 = _check_required_field(row, "ID_T3", entry.path, table, i, diagnostics)
        derived_id_t3 = _check_required_field(row, "ID_T3_I", entry.path, table, i, diagnostics)
        if base_id_t3 is None or derived_id_t3 is None:
            continue

        evidence = M4oEvidence(
            path=entry.path,
            sha256=sha256,
            classification=entry.classification,
            table=table,
            row_index=i,
        )

        if owner_id_t3 != derived_id_t3:
            diagnostics.append(_diag(
                "owner_derived_mismatch",
                entry.path,
                (
                    f"Row {i}: path owner_id_t3={owner_id_t3!r} "
                    f"differs from content ID_T3_I (derived)={derived_id_t3!r}."
                ),
                table,
                i,
            ))

        edges.append(InheritanceEdge(
            owner_id_t3=owner_id_t3,
            base_id_t3=base_id_t3,
            derived_id_t3=derived_id_t3,
            evidence=evidence,
        ))

    return edges


# ── duplicate / conflict detection ────────────────────────────────────────


def _node_binding_content(b: NodeBinding) -> tuple:
    return (b.content_id_t3, b.id_ti, b.is_root)


def _alias_binding_content(b: AliasBinding) -> tuple:
    return (b.id_node, b.id_ti, b.id_alias_t3)


def _annotate_duplicates(
    node_bindings: list[NodeBinding],
    alias_bindings: list[AliasBinding],
    inheritance_edges: list[InheritanceEdge],
    diagnostics: list[Diagnostic],
) -> None:
    """
    Detect duplicates and conflicts.

    Algorithm (deterministic):
    1. Sort each list by (evidence.path, evidence.row_index).
    2. Group by logical key.
    3. Within each group use first binding as reference.
    4. Each additional binding: duplicate if content matches, conflict if it differs.
    5. Emit exactly one diagnostic per additional binding.
    """
    # Node bindings key: (owner_id_t3, content_id_node)
    node_groups: dict[tuple, list[NodeBinding]] = {}
    for b in sorted(node_bindings, key=lambda x: (x.evidence.path, x.evidence.row_index)):
        key = (b.owner_id_t3, b.content_id_node)
        node_groups.setdefault(key, []).append(b)

    for (owner, node), group in node_groups.items():
        ref = group[0]
        for extra in group[1:]:
            if _node_binding_content(extra) == _node_binding_content(ref):
                code = "duplicate_node_binding"
            else:
                code = "conflicting_node_binding"
            diagnostics.append(_diag(
                code,
                extra.evidence.path,
                (
                    f"NodeBinding ({owner!r}, {node!r}): "
                    f"{'duplicate' if code.startswith('duplicate') else 'conflict'} "
                    f"at row {extra.evidence.row_index} "
                    f"(reference at {ref.evidence.path}:{ref.evidence.row_index})."
                ),
                extra.evidence.table,
                extra.evidence.row_index,
            ))

    # Alias bindings key: (owner_id_t3, alias)
    alias_groups: dict[tuple, list[AliasBinding]] = {}
    for b in sorted(alias_bindings, key=lambda x: (x.evidence.path, x.evidence.row_index)):
        key = (b.owner_id_t3, b.alias)
        alias_groups.setdefault(key, []).append(b)

    for (owner, alias), group in alias_groups.items():
        ref = group[0]
        for extra in group[1:]:
            if _alias_binding_content(extra) == _alias_binding_content(ref):
                code = "duplicate_alias_binding"
            else:
                code = "conflicting_alias_binding"
            diagnostics.append(_diag(
                code,
                extra.evidence.path,
                (
                    f"AliasBinding ({owner!r}, {alias!r}): "
                    f"{'duplicate' if code.startswith('duplicate') else 'conflict'} "
                    f"at row {extra.evidence.row_index} "
                    f"(reference at {ref.evidence.path}:{ref.evidence.row_index})."
                ),
                extra.evidence.table,
                extra.evidence.row_index,
            ))

    # Inheritance edges key: (base_id_t3, derived_id_t3) — only exact duplicate
    edge_groups: dict[tuple, list[InheritanceEdge]] = {}
    for e in sorted(inheritance_edges, key=lambda x: (x.evidence.path, x.evidence.row_index)):
        key = (e.base_id_t3, e.derived_id_t3)
        edge_groups.setdefault(key, []).append(e)

    for (base, derived), group in edge_groups.items():
        ref = group[0]
        for extra in group[1:]:
            diagnostics.append(_diag(
                "duplicate_inheritance_edge",
                extra.evidence.path,
                (
                    f"InheritanceEdge ({base!r} → {derived!r}): "
                    f"duplicate at row {extra.evidence.row_index} "
                    f"(reference at {ref.evidence.path}:{ref.evidence.row_index})."
                ),
                extra.evidence.table,
                extra.evidence.row_index,
            ))


# ── canonical sort ─────────────────────────────────────────────────────────


def _sort_node_bindings(bindings: list[NodeBinding]) -> list[NodeBinding]:
    return sorted(
        bindings,
        key=lambda b: (
            b.owner_id_t3,
            b.content_id_node,
            b.evidence.path,
            b.evidence.row_index,
        ),
    )


def _sort_alias_bindings(bindings: list[AliasBinding]) -> list[AliasBinding]:
    return sorted(
        bindings,
        key=lambda b: (b.owner_id_t3, b.alias, b.evidence.path, b.evidence.row_index),
    )


def _sort_inheritance_edges(edges: list[InheritanceEdge]) -> list[InheritanceEdge]:
    return sorted(
        edges,
        key=lambda e: (
            e.base_id_t3,
            e.derived_id_t3,
            e.evidence.path,
            e.evidence.row_index,
        ),
    )


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    return sorted(
        diagnostics,
        key=lambda d: (
            d.path,
            d.table or "",
            d.row_index if d.row_index is not None else -1,
            d.code,
        ),
    )


# ── resource reading ───────────────────────────────────────────────────────


def _read_resource(
    corpus_root: Path,
    entry: FileEntry,
    diagnostics: list[Diagnostic],
) -> tuple[bool, dict[str, Any] | None, str | None]:
    """
    Read and validate a resource file.

    Returns (success, doc_or_None, actual_sha256_or_None).
    On failure, appends the appropriate diagnostic and returns (False, None, None).
    """
    # Path escape guard
    try:
        full = (corpus_root / entry.path).resolve()
        corpus_resolved = corpus_root.resolve()
        full.relative_to(corpus_resolved)
    except ValueError:
        diagnostics.append(_diag(
            "resource_path_escape",
            entry.path,
            f"Resolved path escapes corpus root: {full}.",
        ))
        return False, None, None

    # Read
    try:
        raw = full.read_bytes()
    except OSError as exc:
        diagnostics.append(_diag(
            "resource_read_error",
            entry.path,
            f"Cannot read resource: {exc}.",
        ))
        return False, None, None

    # Hash
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != entry.sha256:
        diagnostics.append(_diag(
            "resource_hash_mismatch",
            entry.path,
            f"SHA-256 mismatch: expected {entry.sha256}, got {actual_sha256}.",
        ))
        return False, None, None

    # Decode (UTF-8, BOM optional)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        diagnostics.append(_diag(
            "invalid_encoding",
            entry.path,
            f"Cannot decode as UTF-8: {exc}.",
        ))
        return False, None, None

    # JSON
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        diagnostics.append(_diag(
            "invalid_json",
            entry.path,
            f"Invalid JSON: {exc}.",
        ))
        return False, None, None

    # Root type
    if not isinstance(doc, dict):
        diagnostics.append(_diag(
            "invalid_document_type",
            entry.path,
            f"JSON root must be an object, got {type(doc).__name__}.",
        ))
        return False, None, None

    return True, doc, actual_sha256


# ── main build function ────────────────────────────────────────────────────


def build_m4o_node_index(
    *,
    corpus_root: Path,
    manifest: CorpusManifest,
    manifest_ref: CorpusManifestRef,
    now: datetime | None = None,
    generator_version: str | None = None,
) -> M4oNodeIndex:
    """
    Build an M4oNodeIndex from a validated CorpusManifest.

    manifest_ref must be pre-computed by the caller from the physical manifest file.
    now controls the created_at timestamp (defaults to current UTC time).
    generator_version overrides the installed package version (useful for reproducibility).
    """
    ts = now or datetime.now(timezone.utc)
    created_at = ts.isoformat()
    version = generator_version or _GENERATOR_VERSION

    # Filter to M4O entries
    selected = [
        e for e in manifest.files
        if e.classification in ALLOWED_CLASSIFICATIONS
    ]

    node_bindings: list[NodeBinding] = []
    alias_bindings: list[AliasBinding] = []
    inheritance_edges: list[InheritanceEdge] = []
    diagnostics: list[Diagnostic] = []

    selected_count = len(selected)
    failed_count = 0
    parsed_count = 0

    for entry in selected:
        ok, doc, actual_sha256 = _read_resource(corpus_root, entry, diagnostics)
        if not ok:
            failed_count += 1
            continue

        parsed_count += 1
        table = CLASSIFICATION_TABLE[entry.classification]
        rows = _extract_table_rows(doc, table, entry.path, diagnostics)  # type: ignore[arg-type]
        if rows is None:
            # invalid_table_type: blocking at table level but file counts as parsed
            continue

        sha256 = actual_sha256 or entry.sha256

        if entry.classification == "m4o_node_json":
            node_bindings.extend(_extract_nodes(rows, entry, sha256, diagnostics))
        elif entry.classification == "m4o_alias_json":
            alias_bindings.extend(_extract_aliases(rows, entry, sha256, diagnostics))
        elif entry.classification == "m4o_mapping_json":
            inheritance_edges.extend(_extract_mappings(rows, entry, sha256, diagnostics))

    # Detect duplicates / conflicts (adds diagnostics in-place)
    _annotate_duplicates(node_bindings, alias_bindings, inheritance_edges, diagnostics)

    # Canonical sort
    node_bindings = _sort_node_bindings(node_bindings)
    alias_bindings = _sort_alias_bindings(alias_bindings)
    inheritance_edges = _sort_inheritance_edges(inheritance_edges)
    diagnostics = _sort_diagnostics(diagnostics)

    summary = NodeIndexSummary(
        selected_file_count=selected_count,
        successfully_parsed_file_count=parsed_count,
        failed_file_count=failed_count,
        node_binding_count=len(node_bindings),
        alias_binding_count=len(alias_bindings),
        inheritance_edge_count=len(inheritance_edges),
        diagnostic_count=len(diagnostics),
    )

    return M4oNodeIndex(
        format=FORMAT,
        schema_version=SCHEMA_VERSION,
        generator=Generator(name=GENERATOR_NAME, version=version),
        created_at=created_at,
        source_manifest=manifest_ref,
        node_bindings=node_bindings,
        alias_bindings=alias_bindings,
        inheritance_edges=inheritance_edges,
        diagnostics=diagnostics,
        summary=summary,
    )
