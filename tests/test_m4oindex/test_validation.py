"""Tests for validate_index_model."""
from __future__ import annotations

import shutil
from pathlib import Path

from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
from peoplenet_process_extractor.m4oindex.extraction import build_m4o_node_index
from peoplenet_process_extractor.m4oindex.models import (
    CorpusManifestRef,
    Diagnostic,
    Generator,
    M4oEvidence,
    M4oNodeIndex,
    NodeBinding,
    NodeIndexSummary,
)
from peoplenet_process_extractor.m4oindex.validation import validate_index_model

from .conftest import FIXTURE_CORPUS, FIXED_NOW, FIXED_GENERATOR_VERSION, load_manifest_ref


def _build_valid_index(tmp_path: Path) -> M4oNodeIndex:
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURE_CORPUS, corpus)
    manifest_path = tmp_path / "manifest.json"
    create_inventory(corpus_root=corpus, output_path=manifest_path,
                     corpus_id="node-index-corpus", now=FIXED_NOW)
    ref = load_manifest_ref(manifest_path)
    manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
    return build_m4o_node_index(
        corpus_root=corpus, manifest=manifest, manifest_ref=ref,
        now=FIXED_NOW, generator_version=FIXED_GENERATOR_VERSION,
    )


def _minimal_valid_index() -> M4oNodeIndex:
    return M4oNodeIndex(
        format="m4object-node-index-v1",
        schema_version=1,
        generator=Generator(name="peoplenet-process-extractor", version="0.1.0"),
        created_at="2026-06-24T12:00:00+00:00",
        source_manifest=CorpusManifestRef(
            corpus_id="test",
            corpus_schema_version="1.1",
            sha256="a" * 64,
            size_bytes=100,
        ),
        node_bindings=[],
        alias_bindings=[],
        inheritance_edges=[],
        diagnostics=[],
        summary=NodeIndexSummary(
            selected_file_count=0,
            successfully_parsed_file_count=0,
            failed_file_count=0,
            node_binding_count=0,
            alias_binding_count=0,
            inheritance_edge_count=0,
            diagnostic_count=0,
        ),
    )


class TestValidArtifact:
    def test_fixture_index_is_valid(self, tmp_path):
        idx = _build_valid_index(tmp_path)
        errors = validate_index_model(idx)
        assert errors == []

    def test_minimal_index_is_valid(self):
        idx = _minimal_valid_index()
        errors = validate_index_model(idx)
        assert errors == []


class TestFormatAndVersion:
    def test_wrong_format(self):
        idx = _minimal_valid_index()
        idx.format = "wrong-format"
        errors = validate_index_model(idx)
        assert any("format" in e for e in errors)

    def test_wrong_schema_version(self):
        idx = _minimal_valid_index()
        idx.schema_version = 99
        errors = validate_index_model(idx)
        assert any("schema_version" in e for e in errors)

    def test_empty_generator_name(self):
        idx = _minimal_valid_index()
        idx.generator.name = ""
        errors = validate_index_model(idx)
        assert any("generator.name" in e for e in errors)

    def test_invalid_created_at(self):
        idx = _minimal_valid_index()
        idx.created_at = "not-a-date"
        errors = validate_index_model(idx)
        assert any("created_at" in e for e in errors)

    def test_non_utc_created_at(self):
        idx = _minimal_valid_index()
        idx.created_at = "2026-06-24T12:00:00+02:00"
        errors = validate_index_model(idx)
        assert any("created_at" in e for e in errors)

    def test_invalid_sha256(self):
        idx = _minimal_valid_index()
        idx.source_manifest = CorpusManifestRef("c", "1.1", "zzz", 100)
        errors = validate_index_model(idx)
        assert any("sha256" in e for e in errors)

    def test_negative_size(self):
        idx = _minimal_valid_index()
        idx.source_manifest = CorpusManifestRef("c", "1.1", "a" * 64, -1)
        errors = validate_index_model(idx)
        assert any("size_bytes" in e for e in errors)


class TestSummaryValidation:
    def test_node_count_mismatch(self):
        idx = _minimal_valid_index()
        idx.summary.node_binding_count = 5
        errors = validate_index_model(idx)
        assert any("node_binding_count" in e for e in errors)

    def test_parsed_plus_failed_neq_selected(self):
        idx = _minimal_valid_index()
        idx.summary.selected_file_count = 3
        idx.summary.successfully_parsed_file_count = 1
        idx.summary.failed_file_count = 1  # 1+1 != 3
        errors = validate_index_model(idx)
        assert any("invariant" in e for e in errors)

    def test_negative_counter(self):
        idx = _minimal_valid_index()
        idx.summary.diagnostic_count = -1
        errors = validate_index_model(idx)
        assert any("negative" in e for e in errors)


class TestOrderValidation:
    def test_node_bindings_out_of_order(self, tmp_path):
        idx = _build_valid_index(tmp_path)
        if len(idx.node_bindings) >= 2:
            # Reverse to break order
            idx.node_bindings = list(reversed(idx.node_bindings))
            idx.summary.node_binding_count = len(idx.node_bindings)
            errors = validate_index_model(idx)
            assert any("canonical order" in e for e in errors)

    def test_diagnostics_out_of_order(self, tmp_path):
        idx = _build_valid_index(tmp_path)
        if len(idx.diagnostics) >= 2:
            idx.diagnostics = list(reversed(idx.diagnostics))
            idx.summary.diagnostic_count = len(idx.diagnostics)
            errors = validate_index_model(idx)
            assert any("canonical order" in e for e in errors)


class TestIsRootNoneRequiresDiagnostic:
    def test_is_root_none_without_diagnostic_is_error(self, tmp_path):
        idx = _build_valid_index(tmp_path)
        # Manually inject a NodeBinding with is_root=None without a diagnostic
        evidence = M4oEvidence(
            path="CP/META4OBJECT/T3A/NODE/N1/f.json",
            sha256="b" * 64,
            classification="m4o_node_json",
            table="M4RCH_NODES",
            row_index=0,
        )
        bad_binding = NodeBinding(
            owner_id_t3="T3A", path_id_node="N1", content_id_t3="T3A",
            content_id_node="N1", id_ti="N1", is_root=None, evidence=evidence,
        )
        idx.node_bindings.append(bad_binding)
        idx.node_bindings.sort(key=lambda b: (b.owner_id_t3, b.content_id_node, b.evidence.path, b.evidence.row_index))
        idx.summary.node_binding_count = len(idx.node_bindings)
        errors = validate_index_model(idx)
        assert any("is_root=None" in e for e in errors)


class TestDiagnosticValidation:
    def test_unknown_code(self):
        idx = _minimal_valid_index()
        idx.diagnostics.append(Diagnostic(
            code="unknown_code", severity="error",
            path="p", table=None, row_index=None, message="m",
        ))
        idx.summary.diagnostic_count = 1
        errors = validate_index_model(idx)
        assert any("unknown_code" in e for e in errors)

    def test_row_index_set_when_table_none(self):
        idx = _minimal_valid_index()
        idx.diagnostics.append(Diagnostic(
            code="resource_read_error", severity="error",
            path="p", table=None, row_index=5, message="m",
        ))
        idx.summary.diagnostic_count = 1
        errors = validate_index_model(idx)
        assert any("row_index" in e for e in errors)

    def test_negative_row_index(self):
        idx = _minimal_valid_index()
        idx.diagnostics.append(Diagnostic(
            code="missing_required_field", severity="error",
            path="p", table="M4RCH_NODES", row_index=-1, message="m",
        ))
        idx.summary.diagnostic_count = 1
        errors = validate_index_model(idx)
        assert any("negative" in e for e in errors)

    def test_empty_path(self):
        idx = _minimal_valid_index()
        idx.diagnostics.append(Diagnostic(
            code="resource_read_error", severity="error",
            path="", table=None, row_index=None, message="m",
        ))
        idx.summary.diagnostic_count = 1
        errors = validate_index_model(idx)
        assert any("path" in e for e in errors)
