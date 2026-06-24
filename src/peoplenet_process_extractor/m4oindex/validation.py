"""
Model validation for m4object-node-index-v1.

validate_index_model performs all in-memory consistency checks:
- Artifact-level fields (format, schema_version, generator, created_at, manifest_ref).
- Evidence (classification, table, row_index bounds, binding/classification coherence).
- Bindings (required strings non-empty, is_root constraints, is_root=None ↔ diagnostic).
- Diagnostics (allowed codes, severities, levels, table/row_index consistency, path non-empty).
- Canonical order (nodes, aliases, edges, diagnostics).
- Summary counters match actual lengths and satisfy the parsed + failed == selected invariant.
"""
from __future__ import annotations

import re
from datetime import datetime

from .models import (
    ALLOWED_CLASSIFICATIONS,
    ALLOWED_DIAGNOSTIC_CODES,
    ALLOWED_DIAGNOSTIC_LEVELS,
    ALLOWED_DIAGNOSTIC_SEVERITIES,
    CLASSIFICATION_TABLE,
    DIAGNOSTIC_LEVELS,
    DIAGNOSTIC_SEVERITIES,
    FORMAT,
    SCHEMA_VERSION,
    M4oEvidence,
    M4oNodeIndex,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_index_model(index: M4oNodeIndex) -> list[str]:
    """
    Validate the in-memory model.

    Returns a list of error strings. Empty list means valid.
    """
    errors: list[str] = []

    # ── Artifact-level ───────────────────────────────────────────────────
    if index.format != FORMAT:
        errors.append(f"Invalid format: expected '{FORMAT}', got '{index.format}'.")
    if index.schema_version != SCHEMA_VERSION:
        errors.append(
            f"Invalid schema_version: expected {SCHEMA_VERSION}, "
            f"got {index.schema_version}."
        )
    if not index.generator.name:
        errors.append("generator.name must not be empty.")
    if not index.generator.version:
        errors.append("generator.version must not be empty.")

    _validate_utc_timestamp(index.created_at, "created_at", errors)

    # Manifest ref
    mr = index.source_manifest
    if not mr.corpus_id:
        errors.append("source_manifest.corpus_id must not be empty.")
    if not mr.corpus_schema_version:
        errors.append("source_manifest.corpus_schema_version must not be empty.")
    if not _SHA256_RE.match(mr.sha256 or ""):
        errors.append(
            f"source_manifest.sha256 is not a valid 64-char hex string: '{mr.sha256}'."
        )
    if mr.size_bytes < 0:
        errors.append(f"source_manifest.size_bytes is negative: {mr.size_bytes}.")

    # ── Diagnostic codes completeness (all codes have a level) ──────────
    # This is a structural invariant of the models module.
    for code in ALLOWED_DIAGNOSTIC_CODES:
        if code not in DIAGNOSTIC_LEVELS:
            errors.append(f"Diagnostic code '{code}' has no entry in DIAGNOSTIC_LEVELS.")
        if code not in DIAGNOSTIC_SEVERITIES:
            errors.append(f"Diagnostic code '{code}' has no entry in DIAGNOSTIC_SEVERITIES.")

    # ── Node bindings ────────────────────────────────────────────────────
    # Collect (path, row_index) pairs for is_root=None check
    invalid_is_root_keys: set[tuple[str, str, int]] = set()
    for i, b in enumerate(index.node_bindings):
        ctx = f"node_bindings[{i}]"
        _validate_evidence(b.evidence, "m4o_node_json", ctx, errors)
        _require_nonempty(b.owner_id_t3, f"{ctx}.owner_id_t3", errors)
        _require_nonempty(b.content_id_t3, f"{ctx}.content_id_t3", errors)
        _require_nonempty(b.content_id_node, f"{ctx}.content_id_node", errors)
        _require_nonempty(b.id_ti, f"{ctx}.id_ti", errors)
        if b.is_root not in (True, False, None):
            errors.append(f"{ctx}.is_root must be True, False, or None.")
        if b.is_root is None:
            invalid_is_root_keys.add((b.evidence.path, b.evidence.table, b.evidence.row_index))

    # Verify every is_root=None binding has an associated invalid_is_root diagnostic
    for path, table, row_index in invalid_is_root_keys:
        found = any(
            d.code == "invalid_is_root"
            and d.path == path
            and d.table == table
            and d.row_index == row_index
            for d in index.diagnostics
        )
        if not found:
            errors.append(
                f"NodeBinding with is_root=None at {path}:{row_index} "
                f"has no associated 'invalid_is_root' diagnostic."
            )

    # ── Alias bindings ───────────────────────────────────────────────────
    for i, b in enumerate(index.alias_bindings):
        ctx = f"alias_bindings[{i}]"
        _validate_evidence(b.evidence, "m4o_alias_json", ctx, errors)
        _require_nonempty(b.owner_id_t3, f"{ctx}.owner_id_t3", errors)
        _require_nonempty(b.alias, f"{ctx}.alias", errors)
        _require_nonempty(b.id_node, f"{ctx}.id_node", errors)
        _require_nonempty(b.id_ti, f"{ctx}.id_ti", errors)
        _require_nonempty(b.id_alias_t3, f"{ctx}.id_alias_t3", errors)

    # ── Inheritance edges ────────────────────────────────────────────────
    for i, e in enumerate(index.inheritance_edges):
        ctx = f"inheritance_edges[{i}]"
        _validate_evidence(e.evidence, "m4o_mapping_json", ctx, errors)
        _require_nonempty(e.owner_id_t3, f"{ctx}.owner_id_t3", errors)
        _require_nonempty(e.base_id_t3, f"{ctx}.base_id_t3", errors)
        _require_nonempty(e.derived_id_t3, f"{ctx}.derived_id_t3", errors)

    # ── Diagnostics ──────────────────────────────────────────────────────
    for i, d in enumerate(index.diagnostics):
        ctx = f"diagnostics[{i}]"
        if d.code not in ALLOWED_DIAGNOSTIC_CODES:
            errors.append(f"{ctx}.code unknown: '{d.code}'.")
        if d.severity not in ALLOWED_DIAGNOSTIC_SEVERITIES:
            errors.append(f"{ctx}.severity unknown: '{d.severity}'.")
        else:
            # Severity must match the canonical table
            expected_sev = DIAGNOSTIC_SEVERITIES.get(d.code)
            if expected_sev is not None and d.severity != expected_sev:
                errors.append(
                    f"{ctx}: severity for '{d.code}' must be '{expected_sev}', "
                    f"got '{d.severity}'."
                )
        # Level derivable
        if d.code in DIAGNOSTIC_LEVELS:
            level = DIAGNOSTIC_LEVELS[d.code]
            if level not in ALLOWED_DIAGNOSTIC_LEVELS:
                errors.append(f"{ctx}: level '{level}' for code '{d.code}' is not allowed.")
        if not d.path:
            errors.append(f"{ctx}.path must not be empty.")
        if d.table is None and d.row_index is not None:
            errors.append(
                f"{ctx}: row_index must be None when table is None "
                f"(got row_index={d.row_index})."
            )
        if d.row_index is not None and d.row_index < 0:
            errors.append(f"{ctx}.row_index is negative: {d.row_index}.")

    # ── Canonical order ──────────────────────────────────────────────────
    _check_order(
        index.node_bindings,
        lambda b: (b.owner_id_t3, b.content_id_node, b.evidence.path, b.evidence.row_index),
        "node_bindings",
        errors,
    )
    _check_order(
        index.alias_bindings,
        lambda b: (b.owner_id_t3, b.alias, b.evidence.path, b.evidence.row_index),
        "alias_bindings",
        errors,
    )
    _check_order(
        index.inheritance_edges,
        lambda e: (e.base_id_t3, e.derived_id_t3, e.evidence.path, e.evidence.row_index),
        "inheritance_edges",
        errors,
    )
    _check_order(
        index.diagnostics,
        lambda d: (
            d.path,
            d.table or "",
            d.row_index if d.row_index is not None else -1,
            d.code,
        ),
        "diagnostics",
        errors,
    )

    # ── Summary ──────────────────────────────────────────────────────────
    s = index.summary
    for field, val in [
        ("selected_file_count", s.selected_file_count),
        ("successfully_parsed_file_count", s.successfully_parsed_file_count),
        ("failed_file_count", s.failed_file_count),
        ("node_binding_count", s.node_binding_count),
        ("alias_binding_count", s.alias_binding_count),
        ("inheritance_edge_count", s.inheritance_edge_count),
        ("diagnostic_count", s.diagnostic_count),
    ]:
        if val < 0:
            errors.append(f"summary.{field} is negative: {val}.")

    if s.node_binding_count != len(index.node_bindings):
        errors.append(
            f"summary.node_binding_count={s.node_binding_count} "
            f"but len(node_bindings)={len(index.node_bindings)}."
        )
    if s.alias_binding_count != len(index.alias_bindings):
        errors.append(
            f"summary.alias_binding_count={s.alias_binding_count} "
            f"but len(alias_bindings)={len(index.alias_bindings)}."
        )
    if s.inheritance_edge_count != len(index.inheritance_edges):
        errors.append(
            f"summary.inheritance_edge_count={s.inheritance_edge_count} "
            f"but len(inheritance_edges)={len(index.inheritance_edges)}."
        )
    if s.diagnostic_count != len(index.diagnostics):
        errors.append(
            f"summary.diagnostic_count={s.diagnostic_count} "
            f"but len(diagnostics)={len(index.diagnostics)}."
        )
    if s.successfully_parsed_file_count + s.failed_file_count != s.selected_file_count:
        errors.append(
            f"summary invariant violated: "
            f"successfully_parsed_file_count ({s.successfully_parsed_file_count}) + "
            f"failed_file_count ({s.failed_file_count}) != "
            f"selected_file_count ({s.selected_file_count})."
        )

    return errors


# ── helpers ────────────────────────────────────────────────────────────────


def _validate_utc_timestamp(value: str, field: str, errors: list[str]) -> None:
    if not value:
        errors.append(f"{field} must not be empty.")
        return
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        errors.append(f"{field} is not a valid ISO-8601 timestamp: '{value}'.")
        return
    if dt.tzinfo is None or dt.utcoffset().total_seconds() != 0:
        errors.append(f"{field} must be a UTC timestamp (got '{value}').")


def _validate_evidence(
    ev: M4oEvidence,
    expected_classification: str,
    ctx: str,
    errors: list[str],
) -> None:
    if ev.classification not in ALLOWED_CLASSIFICATIONS:
        errors.append(
            f"{ctx}.evidence.classification unknown: '{ev.classification}'."
        )
    elif ev.classification != expected_classification:
        errors.append(
            f"{ctx}.evidence.classification must be '{expected_classification}', "
            f"got '{ev.classification}'."
        )
    expected_table = CLASSIFICATION_TABLE.get(ev.classification, "")
    if ev.table != expected_table:
        errors.append(
            f"{ctx}.evidence.table must be '{expected_table}' "
            f"for classification '{ev.classification}', got '{ev.table}'."
        )
    if not _SHA256_RE.match(ev.sha256 or ""):
        errors.append(
            f"{ctx}.evidence.sha256 is not a valid 64-char hex string: '{ev.sha256}'."
        )
    if ev.row_index < 0:
        errors.append(f"{ctx}.evidence.row_index is negative: {ev.row_index}.")
    if not ev.path:
        errors.append(f"{ctx}.evidence.path must not be empty.")


def _require_nonempty(value: str, field: str, errors: list[str]) -> None:
    if not value or not value.strip():
        errors.append(f"{field} must not be empty or whitespace.")


def _check_order(items: list, key_fn, name: str, errors: list[str]) -> None:
    keys = [key_fn(x) for x in items]
    if keys != sorted(keys):
        errors.append(f"{name} is not in canonical order.")
