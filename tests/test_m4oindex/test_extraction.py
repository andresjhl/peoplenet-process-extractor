"""
Unit tests for extraction.py.

Covers: resource access pipeline, IS_ROOT normalization, field validation,
table handling, node/alias/mapping extractors, duplicate/conflict detection,
canonical sort, summary invariants.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from peoplenet_process_extractor.corpus.models import (
    CorpusManifest,
    CorpusSummary,
    FileEntry,
    GitInfo,
    M4oStructure,
    RootInfo,
)
from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
from peoplenet_process_extractor.m4oindex.extraction import _read_resource, build_m4o_node_index
from peoplenet_process_extractor.m4oindex.models import CorpusManifestRef, Diagnostic

from .conftest import FIXTURE_CORPUS, FIXED_NOW, FIXED_GENERATOR_VERSION, load_manifest_ref


# ── helpers ────────────────────────────────────────────────────────────────

def _build_index_from_fixture(tmp_path: Path):
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURE_CORPUS, corpus)
    manifest_path = tmp_path / "manifest.json"
    code, msgs = create_inventory(
        corpus_root=corpus,
        output_path=manifest_path,
        corpus_id="node-index-corpus",
        now=FIXED_NOW,
    )
    assert code == 0, msgs
    ref = load_manifest_ref(manifest_path)
    manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
    return build_m4o_node_index(
        corpus_root=corpus,
        manifest=manifest,
        manifest_ref=ref,
        now=FIXED_NOW,
        generator_version=FIXED_GENERATOR_VERSION,
    ), corpus, manifest_path


def _make_json_file(path: Path, content: dict) -> str:
    raw = json.dumps(content).encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _make_corpus_with_single_entry(
    tmp_path: Path,
    *,
    classification: str,
    id_t3: str,
    id_node: str | None,
    content: dict,
    source_root: str = "CP",
) -> tuple[Path, Path]:
    """Build a minimal corpus + manifest with a single M4O entry."""
    corpus = tmp_path / "corpus"
    if classification == "m4o_node_json":
        dir_ = corpus / source_root / "META4OBJECT" / id_t3 / "NODE" / (id_node or "NODE_X")
    elif classification == "m4o_alias_json":
        dir_ = corpus / source_root / "META4OBJECT" / id_t3 / "M4O ALIAS RESOLUTION" / (id_node or "NODE_X")
    else:
        dir_ = corpus / source_root / "META4OBJECT" / id_t3 / "MAPPING META4OBJECT" / id_t3
    dir_.mkdir(parents=True)
    fname = "data.json"
    raw = json.dumps(content).encode("utf-8")
    (dir_ / fname).write_bytes(raw)
    manifest_path = tmp_path / "manifest.json"
    code, msgs = create_inventory(
        corpus_root=corpus,
        output_path=manifest_path,
        corpus_id="test-corpus",
        now=FIXED_NOW,
    )
    assert code == 0, msgs
    return corpus, manifest_path


# ── integration: fixture corpus ───────────────────────────────────────────

class TestFixtureCorpus:
    def test_builds_successfully(self, tmp_path):
        idx, _, _ = _build_index_from_fixture(tmp_path)
        assert idx.format == "m4object-node-index-v1"
        assert idx.schema_version == 1

    def test_summary_invariant(self, tmp_path):
        idx, _, _ = _build_index_from_fixture(tmp_path)
        s = idx.summary
        assert s.successfully_parsed_file_count + s.failed_file_count == s.selected_file_count

    def test_counts_match_lists(self, tmp_path):
        idx, _, _ = _build_index_from_fixture(tmp_path)
        assert idx.summary.node_binding_count == len(idx.node_bindings)
        assert idx.summary.alias_binding_count == len(idx.alias_bindings)
        assert idx.summary.inheritance_edge_count == len(idx.inheritance_edges)
        assert idx.summary.diagnostic_count == len(idx.diagnostics)

    def test_has_node_bindings(self, tmp_path):
        idx, _, _ = _build_index_from_fixture(tmp_path)
        assert idx.summary.node_binding_count > 0

    def test_has_alias_bindings(self, tmp_path):
        idx, _, _ = _build_index_from_fixture(tmp_path)
        assert idx.summary.alias_binding_count > 0

    def test_has_inheritance_edges(self, tmp_path):
        idx, _, _ = _build_index_from_fixture(tmp_path)
        assert idx.summary.inheritance_edge_count > 0

    def test_node_sec_id_node_equals_id_ti(self, tmp_path):
        idx, _, _ = _build_index_from_fixture(tmp_path)
        sec = [b for b in idx.node_bindings if b.content_id_node == "NODE_SEC"]
        assert sec, "NODE_SEC binding not found"
        assert sec[0].content_id_node == sec[0].id_ti

    def test_node_root_id_node_differs_from_id_ti(self, tmp_path):
        idx, _, _ = _build_index_from_fixture(tmp_path)
        root = [b for b in idx.node_bindings if b.content_id_node == "NODE_ROOT" and b.content_id_t3 == "OBJ_ALPHA"]
        assert root, "NODE_ROOT binding not found"
        assert root[0].content_id_node != root[0].id_ti

    def test_canonical_order_node_bindings(self, tmp_path):
        idx, _, _ = _build_index_from_fixture(tmp_path)
        keys = [(b.owner_id_t3, b.content_id_node, b.evidence.path, b.evidence.row_index)
                for b in idx.node_bindings]
        assert keys == sorted(keys)

    def test_canonical_order_diagnostics(self, tmp_path):
        idx, _, _ = _build_index_from_fixture(tmp_path)
        keys = [(d.path, d.table or "", d.row_index if d.row_index is not None else -1, d.code)
                for d in idx.diagnostics]
        assert keys == sorted(keys)

    def test_evidence_sha256_matches_file(self, tmp_path):
        idx, corpus, _ = _build_index_from_fixture(tmp_path)
        for b in idx.node_bindings:
            actual = hashlib.sha256((corpus / b.evidence.path).read_bytes()).hexdigest()
            assert b.evidence.sha256 == actual

    def test_path_and_content_preserved_separately(self, tmp_path):
        """owner_id_t3/path_id_node and content_id_t3/content_id_node are separate fields."""
        idx, _, _ = _build_index_from_fixture(tmp_path)
        for b in idx.node_bindings:
            assert hasattr(b, "owner_id_t3")
            assert hasattr(b, "path_id_node")
            assert hasattr(b, "content_id_t3")
            assert hasattr(b, "content_id_node")


# ── resource access ───────────────────────────────────────────────────────

class TestResourceAccess:
    def test_missing_file(self, tmp_path):
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path, classification="m4o_node_json", id_t3="T3A", id_node="N1",
            content={"M4RCH_NODES": [{"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "N1", "IS_ROOT": 0}]},
        )
        # Delete the physical file to trigger resource_read_error
        for f in corpus.rglob("*.json"):
            f.unlink()
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(
            corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW,
        )
        codes = {d.code for d in idx.diagnostics}
        assert "resource_read_error" in codes
        assert idx.summary.failed_file_count == 1
        assert idx.summary.successfully_parsed_file_count == 0

    def test_hash_mismatch(self, tmp_path):
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path, classification="m4o_node_json", id_t3="T3A", id_node="N1",
            content={"M4RCH_NODES": [{"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "N1", "IS_ROOT": 0}]},
        )
        # Modify the file after manifest was built → hash mismatch
        for f in corpus.rglob("*.json"):
            f.write_bytes(b'{"M4RCH_NODES": []}')
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(
            corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW,
        )
        codes = {d.code for d in idx.diagnostics}
        assert "resource_hash_mismatch" in codes
        assert idx.summary.failed_file_count == 1

    def test_invalid_encoding(self, tmp_path):
        corpus = tmp_path / "corpus"
        dir_ = corpus / "CP" / "META4OBJECT" / "T3A" / "NODE" / "N1"
        dir_.mkdir(parents=True)
        # Write latin-1 bytes that are invalid UTF-8
        raw = b"\xff\xfe" + "data".encode("utf-16-le")
        (dir_ / "data.json").write_bytes(raw)
        manifest_path = tmp_path / "manifest.json"
        code, msgs = create_inventory(corpus_root=corpus, output_path=manifest_path,
                                      corpus_id="tc", now=FIXED_NOW)
        assert code == 0
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(
            corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW,
        )
        codes = {d.code for d in idx.diagnostics}
        assert "invalid_encoding" in codes
        assert idx.summary.failed_file_count == 1

    def test_invalid_json(self, tmp_path):
        corpus = tmp_path / "corpus"
        dir_ = corpus / "CP" / "META4OBJECT" / "T3A" / "NODE" / "N1"
        dir_.mkdir(parents=True)
        raw = b"not json {"
        (dir_ / "data.json").write_bytes(raw)
        manifest_path = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus, output_path=manifest_path, corpus_id="tc", now=FIXED_NOW)
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(
            corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW,
        )
        codes = {d.code for d in idx.diagnostics}
        assert "invalid_json" in codes
        assert idx.summary.failed_file_count == 1

    def test_root_is_list(self, tmp_path):
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path, classification="m4o_node_json", id_t3="T3A", id_node="N1",
            content={"M4RCH_NODES": []},  # first build to get correct hash
        )
        # Overwrite with list root AFTER manifest build (hash mismatch test would catch it)
        # Instead: build corpus where the file already has a list root
        corpus2, manifest_path2 = _make_corpus_with_single_entry(
            tmp_path / "c2", classification="m4o_node_json", id_t3="T3A", id_node="N1",
            content=[],  # list root
        )
        ref = load_manifest_ref(manifest_path2)
        manifest, _ = deserialize_manifest(manifest_path2.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(
            corpus_root=corpus2, manifest=manifest, manifest_ref=ref, now=FIXED_NOW,
        )
        codes = {d.code for d in idx.diagnostics}
        assert "invalid_document_type" in codes

    def test_root_is_string(self, tmp_path):
        corpus2, manifest_path2 = _make_corpus_with_single_entry(
            tmp_path / "c2", classification="m4o_node_json", id_t3="T3A", id_node="N1",
            content="string root",
        )
        ref = load_manifest_ref(manifest_path2)
        manifest, _ = deserialize_manifest(manifest_path2.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(
            corpus_root=corpus2, manifest=manifest, manifest_ref=ref, now=FIXED_NOW,
        )
        codes = {d.code for d in idx.diagnostics}
        assert "invalid_document_type" in codes


# ── table extraction ──────────────────────────────────────────────────────

class TestTableExtraction:
    def _idx_for(self, tmp_path, content, classification="m4o_node_json",
                 id_t3="T3A", id_node="N1"):
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path, classification=classification, id_t3=id_t3, id_node=id_node,
            content=content,
        )
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        return build_m4o_node_index(
            corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW,
        )

    def test_missing_table_is_warning(self, tmp_path):
        idx = self._idx_for(tmp_path, {})
        codes = {d.code for d in idx.diagnostics}
        assert "missing_table" in codes
        severities = {d.code: d.severity for d in idx.diagnostics}
        assert severities["missing_table"] == "warning"

    def test_null_table_is_missing_warning(self, tmp_path):
        idx = self._idx_for(tmp_path, {"M4RCH_NODES": None})
        codes = {d.code for d in idx.diagnostics}
        assert "missing_table" in codes

    def test_invalid_table_type_is_error(self, tmp_path):
        idx = self._idx_for(tmp_path, {"M4RCH_NODES": "not a list"})
        codes = {d.code for d in idx.diagnostics}
        assert "invalid_table_type" in codes
        severities = {d.code: d.severity for d in idx.diagnostics}
        assert severities["invalid_table_type"] == "error"

    def test_empty_table_produces_no_bindings_no_diags(self, tmp_path):
        idx = self._idx_for(tmp_path, {"M4RCH_NODES": []})
        assert len(idx.node_bindings) == 0
        assert len(idx.diagnostics) == 0

    def test_invalid_row_type_skipped(self, tmp_path):
        content = {"M4RCH_NODES": ["not a dict", {"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "N1", "IS_ROOT": 0}]}
        idx = self._idx_for(tmp_path, content)
        codes = {d.code for d in idx.diagnostics}
        assert "invalid_row_type" in codes
        # Second row is valid
        assert len(idx.node_bindings) == 1

    def test_file_parsed_even_with_row_errors(self, tmp_path):
        content = {"M4RCH_NODES": [{"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "N1", "IS_ROOT": 0}, "bad"]}
        idx = self._idx_for(tmp_path, content)
        assert idx.summary.successfully_parsed_file_count == 1
        assert idx.summary.failed_file_count == 0


# ── field validation ──────────────────────────────────────────────────────

class TestFieldValidation:
    def _make_node(self, tmp_path, row: dict, subdir="sub"):
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path / subdir, classification="m4o_node_json", id_t3="T3A", id_node="N1",
            content={"M4RCH_NODES": [row]},
        )
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        return build_m4o_node_index(
            corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW,
        )

    def test_missing_required_field(self, tmp_path):
        idx = self._make_node(tmp_path, {"ID_T3": "T3A", "ID_NODE": "N1"})  # missing ID_TI
        codes = {d.code for d in idx.diagnostics}
        assert "missing_required_field" in codes

    def test_empty_field(self, tmp_path):
        idx = self._make_node(tmp_path, {"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "", "IS_ROOT": 0})
        codes = {d.code for d in idx.diagnostics}
        assert "empty_required_field" in codes

    def test_whitespace_field(self, tmp_path):
        idx = self._make_node(tmp_path, {"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "  \t  ", "IS_ROOT": 0})
        codes = {d.code for d in idx.diagnostics}
        assert "empty_required_field" in codes

    def test_invalid_field_type_int(self, tmp_path):
        idx = self._make_node(tmp_path, {"ID_T3": "T3A", "ID_NODE": 123, "ID_TI": "N1", "IS_ROOT": 0})
        codes = {d.code for d in idx.diagnostics}
        assert "invalid_field_type" in codes

    def test_value_not_trimmed(self, tmp_path):
        # Values with leading/trailing spaces are stored as-is (no trimming)
        idx = self._make_node(tmp_path, {"ID_T3": " T3A", "ID_NODE": "N1", "ID_TI": "N1", "IS_ROOT": 0})
        # " T3A" is non-empty after strip... but wait: "  T3A" → strip = "T3A" which is truthy
        # So it should pass (stored as-is)
        # But the field starts with a space → strip is " T3A".strip() = "T3A" → truthy
        # This should produce an id_t3_mismatch (path is "T3A", content is " T3A")
        codes = {d.code for d in idx.diagnostics}
        assert "id_t3_mismatch" in codes
        # The raw value must be stored as-is
        b = idx.node_bindings[0]
        assert b.content_id_t3 == " T3A"  # not trimmed


# ── IS_ROOT tests ─────────────────────────────────────────────────────────

class TestIsRoot:
    def _make(self, tmp_path, is_root_val, subdir="sub"):
        row = {"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "N1", "IS_ROOT": is_root_val}
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path / subdir, classification="m4o_node_json", id_t3="T3A", id_node="N1",
            content={"M4RCH_NODES": [row]},
        )
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        return build_m4o_node_index(
            corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW,
        )

    @pytest.mark.parametrize("val,expected", [
        (True, True), (False, False), (1, True), (0, False), ("1", True), ("0", False),
    ])
    def test_valid_is_root(self, tmp_path, val, expected):
        idx = self._make(tmp_path, val, subdir=str(val))
        assert len(idx.node_bindings) == 1
        assert idx.node_bindings[0].is_root == expected
        # No invalid_is_root diagnostic
        codes = {d.code for d in idx.diagnostics}
        assert "invalid_is_root" not in codes

    @pytest.mark.parametrize("val", [None, "true", "false", 2, -1])
    def test_invalid_is_root_produces_diagnostic(self, tmp_path, val):
        idx = self._make(tmp_path, val, subdir=str(val))
        assert len(idx.node_bindings) == 1
        assert idx.node_bindings[0].is_root is None
        codes = {d.code for d in idx.diagnostics}
        assert "invalid_is_root" in codes
        d = next(d for d in idx.diagnostics if d.code == "invalid_is_root")
        assert d.severity == "warning"


# ── consistency checks ────────────────────────────────────────────────────

class TestConsistency:
    def test_id_t3_mismatch(self, tmp_path):
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path, classification="m4o_node_json", id_t3="T3A", id_node="N1",
            content={"M4RCH_NODES": [
                {"ID_T3": "DIFFERENT_T3", "ID_NODE": "N1", "ID_TI": "N1", "IS_ROOT": 0}
            ]},
        )
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW)
        codes = {d.code for d in idx.diagnostics}
        assert "id_t3_mismatch" in codes
        # Binding is still present
        assert len(idx.node_bindings) == 1
        b = idx.node_bindings[0]
        assert b.owner_id_t3 == "T3A"
        assert b.content_id_t3 == "DIFFERENT_T3"

    def test_id_node_mismatch(self, tmp_path):
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path, classification="m4o_node_json", id_t3="T3A", id_node="N1",
            content={"M4RCH_NODES": [
                {"ID_T3": "T3A", "ID_NODE": "N_OTHER", "ID_TI": "N1", "IS_ROOT": 0}
            ]},
        )
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW)
        codes = {d.code for d in idx.diagnostics}
        assert "id_node_mismatch" in codes

    def test_owner_derived_mismatch(self, tmp_path):
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path, classification="m4o_mapping_json", id_t3="T3A", id_node=None,
            content={"SPR_DIN_OBJECTS": [
                {"ID_T3": "BASE_T3", "ID_T3_I": "DIFFERENT_OWNER"}
            ]},
        )
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW)
        codes = {d.code for d in idx.diagnostics}
        assert "owner_derived_mismatch" in codes
        # Edge still present
        assert len(idx.inheritance_edges) == 1

    def test_path_node_reference_mismatch(self, tmp_path):
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path, classification="m4o_alias_json", id_t3="T3A", id_node="N1",
            content={"M4RCH_T3_ALIAS_RES": [
                {"ALIAS": "ALX", "ID_NODE": "N_OTHER", "ID_TI": "N1", "ID_ALIAS_T3": "T3A"}
            ]},
        )
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW)
        codes = {d.code for d in idx.diagnostics}
        assert "path_node_reference_mismatch" in codes
        assert len(idx.alias_bindings) == 1
        b = idx.alias_bindings[0]
        assert b.path_node_reference == "N1"
        assert b.id_node == "N_OTHER"


# ── duplicates and conflicts ──────────────────────────────────────────────

class TestDuplicatesAndConflicts:
    def _make_two_node_files(self, tmp_path, rows_a, rows_b):
        corpus = tmp_path / "corpus"
        # Two files under the same T3A NODE N1 path
        dir_a = corpus / "CP" / "META4OBJECT" / "T3A" / "NODE" / "N1"
        dir_b = corpus / "CP" / "META4OBJECT" / "T3A" / "NODE" / "N1B"
        dir_a.mkdir(parents=True)
        dir_b.mkdir(parents=True)
        (dir_a / "a.json").write_bytes(json.dumps({"M4RCH_NODES": rows_a}).encode())
        (dir_b / "b.json").write_bytes(json.dumps({"M4RCH_NODES": rows_b}).encode())
        manifest_path = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus, output_path=manifest_path, corpus_id="tc", now=FIXED_NOW)
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        return build_m4o_node_index(corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW)

    def test_duplicate_node_binding(self, tmp_path):
        row = {"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "TI1", "IS_ROOT": 0}
        idx = self._make_two_node_files(tmp_path, [row], [row])
        codes = {d.code for d in idx.diagnostics}
        assert "duplicate_node_binding" in codes
        # Both bindings present
        assert len([b for b in idx.node_bindings if b.content_id_node == "N1"]) == 2

    def test_conflicting_node_binding(self, tmp_path):
        row_a = {"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "TI1", "IS_ROOT": 0}
        row_b = {"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "TI_OTHER", "IS_ROOT": 0}
        idx = self._make_two_node_files(tmp_path, [row_a], [row_b])
        codes = {d.code for d in idx.diagnostics}
        assert "conflicting_node_binding" in codes

    def test_alias_duplicate(self, tmp_path):
        corpus = tmp_path / "corpus"
        dir_a = corpus / "CP" / "META4OBJECT" / "T3A" / "M4O ALIAS RESOLUTION" / "N1"
        dir_b = corpus / "CP" / "META4OBJECT" / "T3A" / "M4O ALIAS RESOLUTION" / "N1B"
        dir_a.mkdir(parents=True)
        dir_b.mkdir(parents=True)
        row = {"ALIAS": "ALX", "ID_NODE": "N1", "ID_TI": "TI1", "ID_ALIAS_T3": "T3A"}
        (dir_a / "a.json").write_bytes(json.dumps({"M4RCH_T3_ALIAS_RES": [row]}).encode())
        (dir_b / "b.json").write_bytes(json.dumps({"M4RCH_T3_ALIAS_RES": [row]}).encode())
        manifest_path = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus, output_path=manifest_path, corpus_id="tc", now=FIXED_NOW)
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW)
        codes = {d.code for d in idx.diagnostics}
        assert "duplicate_alias_binding" in codes

    def test_inheritance_edge_duplicate(self, tmp_path):
        corpus = tmp_path / "corpus"
        dir_a = corpus / "CP" / "META4OBJECT" / "T3A" / "MAPPING META4OBJECT" / "T3A"
        dir_a.mkdir(parents=True)
        row = {"ID_T3": "BASE", "ID_T3_I": "T3A"}
        # Put two rows in the same file
        (dir_a / "mapping.json").write_bytes(json.dumps({"SPR_DIN_OBJECTS": [row, row]}).encode())
        manifest_path = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus, output_path=manifest_path, corpus_id="tc", now=FIXED_NOW)
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW)
        codes = {d.code for d in idx.diagnostics}
        assert "duplicate_inheritance_edge" in codes

    def test_duplicate_and_conflict_not_mixed(self, tmp_path):
        """One extra binding generates exactly one diagnostic (not both duplicate and conflict)."""
        row_ref = {"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "TI1", "IS_ROOT": 0}
        row_dup = {"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "TI1", "IS_ROOT": 0}
        idx = self._make_two_node_files(tmp_path, [row_ref], [row_dup])
        # Only one extra binding → exactly one diagnostic
        dups = [d for d in idx.diagnostics if d.code in ("duplicate_node_binding", "conflicting_node_binding")]
        assert len(dups) == 1
        assert dups[0].code == "duplicate_node_binding"


# ── mapping extraction ────────────────────────────────────────────────────

class TestMappingExtraction:
    def test_owner_equals_derived(self, tmp_path):
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path, classification="m4o_mapping_json", id_t3="T3A", id_node=None,
            content={"SPR_DIN_OBJECTS": [{"ID_T3": "BASE_T3", "ID_T3_I": "T3A"}]},
        )
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW)
        assert len(idx.inheritance_edges) == 1
        e = idx.inheritance_edges[0]
        assert e.base_id_t3 == "BASE_T3"
        assert e.derived_id_t3 == "T3A"
        assert e.owner_id_t3 == "T3A"
        codes = {d.code for d in idx.diagnostics}
        assert "owner_derived_mismatch" not in codes

    def test_multiple_rows(self, tmp_path):
        corpus, manifest_path = _make_corpus_with_single_entry(
            tmp_path, classification="m4o_mapping_json", id_t3="T3A", id_node=None,
            content={"SPR_DIN_OBJECTS": [
                {"ID_T3": "BASE1", "ID_T3_I": "T3A"},
                {"ID_T3": "BASE2", "ID_T3_I": "T3A"},
            ]},
        )
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW)
        assert len(idx.inheritance_edges) == 2


# ── security: path escape ─────────────────────────────────────────────────

class TestResourcePathEscape:
    def test_path_escape_produces_diagnostic(self, tmp_path):
        """A FileEntry whose resolved path escapes corpus_root triggers resource_path_escape."""
        corpus_root = tmp_path / "corpus"
        corpus_root.mkdir()
        # Craft an entry with a path that resolves outside corpus_root
        entry = FileEntry(
            path="../outside.json",
            sha256="a" * 64,
            size_bytes=0,
            extension=".json",
            source_root=None,
            classification="m4o_node_json",
            m4o_structure=M4oStructure(id_t3="T3A", id_node="N1"),
        )
        diagnostics: list[Diagnostic] = []
        ok, doc, sha = _read_resource(corpus_root, entry, diagnostics)

        assert not ok
        assert doc is None
        assert sha is None
        assert len(diagnostics) == 1
        assert diagnostics[0].code == "resource_path_escape"
        assert diagnostics[0].severity == "error"

    def test_path_escape_full_index_contract(self, tmp_path):
        """A path-escape entry propagates correctly through the full index build.

        Verifies: diagnostic fields, summary counters, and empty binding lists.
        A valid corpus manifest never contains '..' paths, so we construct one
        directly to exercise this defence without going through create_inventory.
        """
        corpus_root = tmp_path / "corpus"
        corpus_root.mkdir()

        escape_entry = FileEntry(
            path="../outside.json",
            sha256="b" * 64,
            size_bytes=0,
            extension=".json",
            source_root="CP",
            classification="m4o_node_json",
            m4o_structure=M4oStructure(id_t3="T3X", id_node="NX"),
        )
        manifest = CorpusManifest(
            schema_version="1.1",
            corpus_id="test-escape",
            created_at="2026-06-24T12:00:00+00:00",
            root=RootInfo(label=str(corpus_root)),
            git=GitInfo(commit=None, dirty=None),
            included_source_roots=["CP"],
            files=[escape_entry],
            summary=CorpusSummary(
                total_files=1,
                total_bytes=0,
                structured_files=1,
                unstructured_files=0,
            ),
        )
        manifest_ref = CorpusManifestRef(
            corpus_id="test-escape",
            corpus_schema_version="1.1",
            sha256="c" * 64,
            size_bytes=0,
        )

        idx = build_m4o_node_index(
            corpus_root=corpus_root,
            manifest=manifest,
            manifest_ref=manifest_ref,
            now=FIXED_NOW,
            generator_version=FIXED_GENERATOR_VERSION,
        )

        # Diagnostic contract
        assert len(idx.diagnostics) == 1
        diag = idx.diagnostics[0]
        assert diag.code == "resource_path_escape"
        assert diag.severity == "error"
        assert diag.table is None
        assert diag.row_index is None

        # Summary contract: 1 selected, 1 failed, 0 parsed
        s = idx.summary
        assert s.selected_file_count == 1
        assert s.failed_file_count == 1
        assert s.successfully_parsed_file_count == 0

        # No facts emitted
        assert idx.node_bindings == []
        assert idx.alias_bindings == []
        assert idx.inheritance_edges == []


# ── UTF-8 con BOM ─────────────────────────────────────────────────────────

class TestUtf8Bom:
    def test_utf8_bom_accepted(self, tmp_path):
        """A resource encoded as UTF-8 with BOM is parsed correctly without invalid_encoding."""
        corpus = tmp_path / "corpus"
        dir_ = corpus / "CP" / "META4OBJECT" / "T3A" / "NODE" / "N1"
        dir_.mkdir(parents=True)
        content = {"M4RCH_NODES": [{"ID_T3": "T3A", "ID_NODE": "N1", "ID_TI": "TI1", "IS_ROOT": 0}]}
        bom = b"\xef\xbb\xbf"
        raw = bom + json.dumps(content).encode("utf-8")
        (dir_ / "data.json").write_bytes(raw)
        manifest_path = tmp_path / "manifest.json"
        code, msgs = create_inventory(corpus_root=corpus, output_path=manifest_path,
                                      corpus_id="tc", now=FIXED_NOW)
        assert code == 0, msgs
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(
            corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW,
        )
        codes = {d.code for d in idx.diagnostics}
        assert "invalid_encoding" not in codes
        assert len(idx.node_bindings) == 1
        assert idx.summary.successfully_parsed_file_count == 1


# ── alias conflictivo ─────────────────────────────────────────────────────

class TestConflictingAliasBinding:
    def test_conflicting_alias_binding(self, tmp_path):
        """Two AliasBindings for same (owner_id_t3, alias) but different content → conflicting_alias_binding."""
        corpus = tmp_path / "corpus"
        dir_a = corpus / "CP" / "META4OBJECT" / "T3A" / "M4O ALIAS RESOLUTION" / "N1"
        dir_b = corpus / "CP" / "META4OBJECT" / "T3A" / "M4O ALIAS RESOLUTION" / "N1B"
        dir_a.mkdir(parents=True)
        dir_b.mkdir(parents=True)
        # Same alias key (T3A, ALX) but different id_node → conflict
        row_ref = {"ALIAS": "ALX", "ID_NODE": "N1", "ID_TI": "TI1", "ID_ALIAS_T3": "T3A"}
        row_alt = {"ALIAS": "ALX", "ID_NODE": "N_OTHER", "ID_TI": "TI1", "ID_ALIAS_T3": "T3A"}
        (dir_a / "a.json").write_bytes(json.dumps({"M4RCH_T3_ALIAS_RES": [row_ref]}).encode())
        (dir_b / "b.json").write_bytes(json.dumps({"M4RCH_T3_ALIAS_RES": [row_alt]}).encode())
        manifest_path = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus, output_path=manifest_path, corpus_id="tc", now=FIXED_NOW)
        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        idx = build_m4o_node_index(corpus_root=corpus, manifest=manifest, manifest_ref=ref, now=FIXED_NOW)

        codes = {d.code for d in idx.diagnostics}
        assert "conflicting_alias_binding" in codes
        assert "duplicate_alias_binding" not in codes
        # Both bindings are preserved
        alx = [b for b in idx.alias_bindings if b.alias == "ALX" and b.owner_id_t3 == "T3A"]
        assert len(alx) == 2
        # Exactly one conflicting_alias_binding diagnostic for this key
        conflict_diags = [d for d in idx.diagnostics if d.code == "conflicting_alias_binding"]
        assert len(conflict_diags) == 1
        assert conflict_diags[0].severity == "error"
