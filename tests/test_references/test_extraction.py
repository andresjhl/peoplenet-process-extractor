"""Tests for the reference extraction service."""
from __future__ import annotations

import json
import shutil


from peoplenet_process_extractor.references.extraction import extract_references

from .conftest import FIXED_NOW


class TestExtractionSuccess:
    def test_full_extraction_succeeds(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out,
            force=False,
            now=FIXED_NOW,
        )
        assert code == 0, msgs
        assert out.exists()

    def test_output_is_valid_json(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out,
            now=FIXED_NOW,
        )
        assert code == 0, msgs
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["format"] == "reference-extraction-v1"
        assert data["schema_version"] == 1

    def test_files_without_calls_included(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out,
            now=FIXED_NOW,
        )
        assert code == 0, msgs
        data = json.loads(out.read_text(encoding="utf-8"))
        no_call_files = [f for f in data["files"] if not f["references"]]
        # METH_NO_CALLS and CONC_EMPTY should have 0 references
        assert len(no_call_files) >= 2

    def test_files_with_calls_included(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out,
            now=FIXED_NOW,
        )
        assert code == 0, msgs
        data = json.loads(out.read_text(encoding="utf-8"))
        files_with_refs = [f for f in data["files"] if f["references"]]
        assert len(files_with_refs) >= 1

    def test_only_structured_ln4_processed(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out,
            now=FIXED_NOW,
        )
        assert code == 0, msgs
        data = json.loads(out.read_text(encoding="utf-8"))
        # All files should have .ln4 extension in their path
        for f in data["files"]:
            assert f["path"].endswith(".ln4"), f"Unexpected file: {f['path']}"

    def test_reference_ids_deterministic(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out1 = tmp_path / "refs1.json"
        out2 = tmp_path / "refs2.json"
        extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out1,
            now=FIXED_NOW,
        )
        extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out2,
            force=True,
            now=FIXED_NOW,
        )
        data1 = json.loads(out1.read_text(encoding="utf-8"))
        data2 = json.loads(out2.read_text(encoding="utf-8"))
        ids1 = {r["id"] for f in data1["files"] for r in f["references"]}
        ids2 = {r["id"] for f in data2["files"] for r in f["references"]}
        assert ids1 == ids2


class TestExtractionErrors:
    def test_output_exists_without_force_fails(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        out.write_text("existing")
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out,
            force=False,
            now=FIXED_NOW,
        )
        assert code != 0
        assert out.read_text() == "existing"  # not overwritten

    def test_force_overwrites_existing(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        out.write_text("old content")
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out,
            force=True,
            now=FIXED_NOW,
        )
        assert code == 0, msgs
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["format"] == "reference-extraction-v1"

    def test_corpus_root_not_found(self, tmp_path, corpus_manifest, built_index):
        code, msgs = extract_references(
            corpus_root=tmp_path / "nonexistent",
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=tmp_path / "refs.json",
            now=FIXED_NOW,
        )
        assert code != 0
        assert any("not a directory" in m for m in msgs)

    def test_manifest_not_found(self, non_git_corpus, built_index, tmp_path):
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=tmp_path / "nonexistent.json",
            index_path=built_index,
            output_path=tmp_path / "refs.json",
            now=FIXED_NOW,
        )
        assert code != 0

    def test_index_not_found(self, non_git_corpus, corpus_manifest, tmp_path):
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=tmp_path / "nonexistent.sqlite",
            output_path=tmp_path / "refs.json",
            now=FIXED_NOW,
        )
        assert code != 0

    def test_manifest_sha256_mismatch_with_index(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        # Build a different manifest and try to use it with the existing index
        other_manifest = tmp_path / "other-manifest.json"
        shutil.copy(corpus_manifest, other_manifest)
        # Corrupt the copy
        data = json.loads(other_manifest.read_text())
        data["corpus_id"] = "different-corpus"
        other_manifest.write_bytes(json.dumps(data).encode("utf-8"))

        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=other_manifest,
            index_path=built_index,
            output_path=tmp_path / "refs.json",
            now=FIXED_NOW,
        )
        assert code != 0


class TestEncodingDetection:
    def test_utf8_file_encoding(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out,
            now=FIXED_NOW,
        )
        assert code == 0, msgs
        data = json.loads(out.read_text(encoding="utf-8"))
        # Find the BOM file
        bom_files = [f for f in data["files"] if "METH_BOM" in f["path"]]
        assert bom_files
        assert bom_files[0]["encoding"] == "utf-8-bom"

    def test_crlf_file_line_ending(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out,
            now=FIXED_NOW,
        )
        assert code == 0, msgs
        data = json.loads(out.read_text(encoding="utf-8"))
        crlf_files = [f for f in data["files"] if "METH_CRLF" in f["path"]]
        assert crlf_files
        assert crlf_files[0]["line_ending"] == "crlf"

    def test_empty_file_processed_zero_refs(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out,
            now=FIXED_NOW,
        )
        assert code == 0, msgs
        data = json.loads(out.read_text(encoding="utf-8"))
        empty_files = [f for f in data["files"] if "CONC_EMPTY" in f["path"]]
        assert empty_files
        assert empty_files[0]["references"] == []
        assert empty_files[0]["status"] == "processed"


class TestExtractionIndexValidation:
    """
    verify_extraction() is now backed by validate_index() at extract time.
    These tests confirm that a structurally invalid index aborts extraction.
    """

    def test_corrupted_sqlite_index_fails(
        self, non_git_corpus, corpus_manifest, tmp_path
    ):
        bad_db = tmp_path / "bad.sqlite"
        bad_db.write_bytes(b"not a sqlite database at all")
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=bad_db,
            output_path=tmp_path / "refs.json",
            now=FIXED_NOW,
        )
        assert code != 0

    def test_index_built_from_different_manifest_fails(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        # Reuse the existing test from TestExtractionErrors; confirm validate_index
        # also catches a manifest mismatch (sha256 check inside validate_index).
        import json as _json
        other_manifest = tmp_path / "other-manifest.json"
        data = _json.loads(corpus_manifest.read_text())
        data["corpus_id"] = "different-id-for-validate-index-test"
        other_manifest.write_bytes(_json.dumps(data).encode("utf-8"))
        code, msgs = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=other_manifest,
            index_path=built_index,
            output_path=tmp_path / "refs.json",
            now=FIXED_NOW,
        )
        assert code != 0
