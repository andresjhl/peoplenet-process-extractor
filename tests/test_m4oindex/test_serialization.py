"""Tests for serialization.py: serialize/deserialize round-trip, canonical format."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
from peoplenet_process_extractor.m4oindex.extraction import build_m4o_node_index
from peoplenet_process_extractor.m4oindex.serialization import (
    DeserializationError,
    deserialize_index,
    serialize_index,
)

from .conftest import FIXTURE_CORPUS, FIXED_NOW, FIXED_GENERATOR_VERSION, load_manifest_ref


def _build_index(tmp_path: Path):
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


class TestRoundTrip:
    def test_round_trip_is_identity(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        rt = deserialize_index(text)
        assert serialize_index(rt) == text

    def test_trailing_newline(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        assert text.endswith("\n")

    def test_no_crlf(self, tmp_path):
        idx = _build_index(tmp_path)
        assert b"\r\n" not in serialize_index(idx).encode("utf-8")

    def test_two_spaces_indent(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        parsed = json.loads(text)
        reformatted = json.dumps(parsed, indent=2, ensure_ascii=False) + "\n"
        assert text == reformatted

    def test_is_root_bool_serialized_as_json_bool(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        raw = json.loads(text)
        for b in raw["node_bindings"]:
            ir = b["is_root"]
            assert ir is None or isinstance(ir, bool)

    def test_is_root_none_serialized_as_null(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        raw = json.loads(text)
        for b in raw["node_bindings"]:
            if b["is_root"] is None:
                assert "null" in text  # confirms null is in the output

    def test_source_manifest_sha256_included(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        raw = json.loads(text)
        assert "sha256" in raw["source_manifest"]
        assert len(raw["source_manifest"]["sha256"]) == 64

    def test_evidence_sha256_included(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        raw = json.loads(text)
        for b in raw["node_bindings"]:
            assert len(b["evidence"]["sha256"]) == 64


class TestDeserializationErrors:
    def test_invalid_json(self):
        with pytest.raises(DeserializationError, match="Invalid JSON"):
            deserialize_index("not json {")

    def test_root_is_list(self):
        with pytest.raises(DeserializationError):
            deserialize_index("[]")

    def test_root_is_string(self):
        with pytest.raises(DeserializationError):
            deserialize_index('"a string"')

    def test_missing_format_field(self):
        with pytest.raises(DeserializationError):
            deserialize_index(json.dumps({"schema_version": 1}))

    def test_is_root_wrong_type(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        raw = json.loads(text)
        if raw["node_bindings"]:
            raw["node_bindings"][0]["is_root"] = "yes"
            with pytest.raises(DeserializationError):
                deserialize_index(json.dumps(raw))

    def test_unknown_format(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        raw = json.loads(text)
        raw["format"] = "m4object-node-index-v99"
        with pytest.raises(DeserializationError, match="Unsupported format"):
            deserialize_index(json.dumps(raw))

    def test_unknown_schema_version(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        raw = json.loads(text)
        raw["schema_version"] = 99
        with pytest.raises(DeserializationError, match="Unsupported schema_version"):
            deserialize_index(json.dumps(raw))

    def test_missing_summary_field(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        raw = json.loads(text)
        del raw["summary"]["node_binding_count"]
        with pytest.raises(DeserializationError):
            deserialize_index(json.dumps(raw))

    def test_row_index_wrong_type(self, tmp_path):
        idx = _build_index(tmp_path)
        text = serialize_index(idx)
        raw = json.loads(text)
        if raw["diagnostics"]:
            raw["diagnostics"][0]["row_index"] = "bad"
            with pytest.raises(DeserializationError):
                deserialize_index(json.dumps(raw))
