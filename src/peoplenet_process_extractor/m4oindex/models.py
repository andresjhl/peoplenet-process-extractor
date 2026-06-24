"""
Models for m4object-node-index-v1.

Key distinctions preserved throughout:
- owner_id_t3 / path_id_node: identifiers extracted from the filesystem path
- content_id_t3 / content_id_node: identifiers extracted from the JSON content
- DIAGNOSTIC_LEVELS is a derived property; it is never serialized.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FORMAT = "m4object-node-index-v1"
SCHEMA_VERSION = 1
GENERATOR_NAME = "peoplenet-process-extractor"

ALLOWED_CLASSIFICATIONS: frozenset[str] = frozenset({
    "m4o_node_json",
    "m4o_alias_json",
    "m4o_mapping_json",
})

# Expected table per classification
CLASSIFICATION_TABLE: dict[str, str] = {
    "m4o_node_json": "M4RCH_NODES",
    "m4o_alias_json": "M4RCH_T3_ALIAS_RES",
    "m4o_mapping_json": "SPR_DIN_OBJECTS",
}

# Severities for each diagnostic code.
DIAGNOSTIC_SEVERITIES: dict[str, str] = {
    "resource_read_error": "error",
    "resource_hash_mismatch": "error",
    "resource_path_escape": "error",
    "invalid_encoding": "error",
    "invalid_json": "error",
    "invalid_document_type": "error",
    "missing_table": "warning",
    "invalid_table_type": "error",
    "invalid_row_type": "error",
    "missing_required_field": "error",
    "empty_required_field": "error",
    "invalid_field_type": "error",
    "invalid_is_root": "warning",
    "id_t3_mismatch": "warning",
    "id_node_mismatch": "warning",
    "path_node_reference_mismatch": "warning",
    "owner_derived_mismatch": "warning",
    "duplicate_node_binding": "warning",
    "duplicate_alias_binding": "warning",
    "duplicate_inheritance_edge": "warning",
    "conflicting_node_binding": "error",
    "conflicting_alias_binding": "error",
}

# Structural levels for each diagnostic code. Not serialized.
DIAGNOSTIC_LEVELS: dict[str, str] = {
    "resource_read_error": "resource",
    "resource_hash_mismatch": "resource",
    "resource_path_escape": "resource",
    "invalid_encoding": "resource",
    "invalid_json": "document",
    "invalid_document_type": "document",
    "missing_table": "table",
    "invalid_table_type": "table",
    "invalid_row_type": "row",
    "missing_required_field": "row",
    "empty_required_field": "row",
    "invalid_field_type": "row",
    "invalid_is_root": "row",
    "id_t3_mismatch": "consistency",
    "id_node_mismatch": "consistency",
    "path_node_reference_mismatch": "consistency",
    "owner_derived_mismatch": "consistency",
    "duplicate_node_binding": "duplicate",
    "duplicate_alias_binding": "duplicate",
    "duplicate_inheritance_edge": "duplicate",
    "conflicting_node_binding": "consistency",
    "conflicting_alias_binding": "consistency",
}

ALLOWED_DIAGNOSTIC_CODES: frozenset[str] = frozenset(DIAGNOSTIC_LEVELS)
ALLOWED_DIAGNOSTIC_SEVERITIES: frozenset[str] = frozenset({"error", "warning"})
ALLOWED_DIAGNOSTIC_LEVELS: frozenset[str] = frozenset(DIAGNOSTIC_LEVELS.values())


@dataclass(frozen=True)
class M4oEvidence:
    path: str
    sha256: str
    classification: str
    table: str
    row_index: int


@dataclass(frozen=True)
class NodeBinding:
    owner_id_t3: str
    path_id_node: str
    content_id_t3: str
    content_id_node: str
    id_ti: str
    is_root: bool | None
    evidence: M4oEvidence


@dataclass(frozen=True)
class AliasBinding:
    owner_id_t3: str
    path_node_reference: str
    alias: str
    id_node: str
    id_ti: str
    id_alias_t3: str
    evidence: M4oEvidence


@dataclass(frozen=True)
class InheritanceEdge:
    owner_id_t3: str
    base_id_t3: str
    derived_id_t3: str
    evidence: M4oEvidence


@dataclass
class Diagnostic:
    code: str
    severity: str
    path: str
    table: str | None
    row_index: int | None
    message: str


@dataclass
class NodeIndexSummary:
    selected_file_count: int
    successfully_parsed_file_count: int
    failed_file_count: int
    node_binding_count: int
    alias_binding_count: int
    inheritance_edge_count: int
    diagnostic_count: int


@dataclass(frozen=True)
class CorpusManifestRef:
    corpus_id: str
    corpus_schema_version: str
    sha256: str
    size_bytes: int


@dataclass
class Generator:
    name: str
    version: str


@dataclass
class M4oNodeIndex:
    format: str
    schema_version: int
    generator: Generator
    created_at: str
    source_manifest: CorpusManifestRef
    node_bindings: list[NodeBinding]
    alias_bindings: list[AliasBinding]
    inheritance_edges: list[InheritanceEdge]
    diagnostics: list[Diagnostic]
    summary: NodeIndexSummary


def _normalize_is_root(value: Any) -> bool | None:
    """
    Normalize IS_ROOT to bool or None.

    Order matters: bool must be checked before int because bool is a subclass of int.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return value == 1
    if isinstance(value, str) and value in ("0", "1"):
        return value == "1"
    return None
