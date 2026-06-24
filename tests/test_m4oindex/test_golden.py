"""
Golden test for m4object-node-index-v1.

The golden file is byte-identical to the output produced by building the index
from the fixture corpus with FIXED_NOW and FIXED_GENERATOR_VERSION.

To regenerate the golden file manually:
    python tests/test_m4oindex/generate_golden.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
from peoplenet_process_extractor.m4oindex.extraction import build_m4o_node_index
from peoplenet_process_extractor.m4oindex.serialization import serialize_index
from peoplenet_process_extractor.m4oindex.validation import validate_index_model

from .conftest import FIXTURE_CORPUS, FIXED_GENERATOR_VERSION, FIXED_NOW, GOLDEN_PATH, load_manifest_ref


def _build_index_text(tmp_path: Path) -> str:
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURE_CORPUS, corpus)
    manifest_path = tmp_path / "manifest.json"
    create_inventory(
        corpus_root=corpus,
        output_path=manifest_path,
        corpus_id="node-index-corpus",
        now=FIXED_NOW,
    )
    ref = load_manifest_ref(manifest_path)
    manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
    index = build_m4o_node_index(
        corpus_root=corpus,
        manifest=manifest,
        manifest_ref=ref,
        now=FIXED_NOW,
        generator_version=FIXED_GENERATOR_VERSION,
    )
    errors = validate_index_model(index)
    assert errors == [], f"Index failed validation: {errors}"
    return serialize_index(index)


class TestGoldenFile:
    def test_golden_exists(self):
        assert GOLDEN_PATH.exists(), (
            f"Golden file not found: {GOLDEN_PATH}. "
            "Run tests/test_m4oindex/generate_golden.py to create it."
        )

    def test_golden_matches(self, tmp_path):
        stored = GOLDEN_PATH.read_text(encoding="utf-8")
        actual = _build_index_text(tmp_path)
        assert actual == stored, (
            "Index does not match golden. "
            "If fixtures changed, regenerate with: python tests/test_m4oindex/generate_golden.py"
        )

    def test_golden_has_correct_format(self):
        raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        assert raw["format"] == "m4object-node-index-v1"
        assert raw["schema_version"] == 1

    def test_golden_has_node_bindings(self):
        raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        assert raw["summary"]["node_binding_count"] > 0

    def test_golden_has_alias_bindings(self):
        raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        assert raw["summary"]["alias_binding_count"] > 0

    def test_golden_has_inheritance_edges(self):
        raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        assert raw["summary"]["inheritance_edge_count"] > 0

    def test_golden_node_with_id_node_eq_id_ti(self):
        raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        equal = [b for b in raw["node_bindings"] if b["content_id_node"] == b["id_ti"]]
        assert equal, "Golden must contain a node where ID_NODE == ID_TI"

    def test_golden_node_with_id_node_ne_id_ti(self):
        raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        diff = [b for b in raw["node_bindings"] if b["content_id_node"] != b["id_ti"]]
        assert diff, "Golden must contain a root node where ID_NODE != ID_TI"

    def test_golden_source_manifest_sha256_present(self):
        raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        sha = raw["source_manifest"]["sha256"]
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)

    def test_golden_evidence_sha256_present(self):
        raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        for b in raw["node_bindings"]:
            sha = b["evidence"]["sha256"]
            assert len(sha) == 64

    def test_golden_node_bindings_sorted(self):
        raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        keys = [(b["owner_id_t3"], b["content_id_node"],
                 b["evidence"]["path"], b["evidence"]["row_index"])
                for b in raw["node_bindings"]]
        assert keys == sorted(keys)

    def test_golden_diagnostics_sorted(self):
        raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        keys = [(d["path"], d["table"] or "", d["row_index"] if d["row_index"] is not None else -1, d["code"])
                for d in raw["diagnostics"]]
        assert keys == sorted(keys)

    def test_golden_trailing_newline(self):
        text = GOLDEN_PATH.read_text(encoding="utf-8")
        assert text.endswith("\n")

    def test_golden_no_crlf(self):
        raw = GOLDEN_PATH.read_bytes()
        assert b"\r\n" not in raw

    def test_golden_summary_invariant(self):
        raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        s = raw["summary"]
        assert s["successfully_parsed_file_count"] + s["failed_file_count"] == s["selected_file_count"]

    def test_golden_is_canonical_json(self):
        text = GOLDEN_PATH.read_text(encoding="utf-8")
        reformatted = json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\n"
        assert text == reformatted
