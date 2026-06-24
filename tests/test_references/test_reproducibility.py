"""Tests for reproducibility of reference extraction output."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.index.builder import build_index
from peoplenet_process_extractor.references.extraction import extract_references

from .conftest import FIXTURE_CORPUS, FIXED_NOW


def _build_full_extraction(tmp_path: Path, run_id: str = "run") -> Path:
    """Build corpus, index, and extraction in a non-git temp directory."""
    corpus = tmp_path / run_id / "corpus"
    shutil.copytree(FIXTURE_CORPUS, corpus)

    manifest = tmp_path / run_id / "manifest.json"
    code, msgs = create_inventory(
        corpus_root=corpus,
        output_path=manifest,
        corpus_id="references-corpus",
        now=FIXED_NOW,
    )
    assert code == 0, msgs

    db = tmp_path / run_id / "index.sqlite"
    code, msgs = build_index(
        corpus_root=corpus,
        manifest_path=manifest,
        output_path=db,
        now=FIXED_NOW,
    )
    assert code == 0, msgs

    out = tmp_path / run_id / "extraction.json"
    code, msgs = extract_references(
        corpus_root=corpus,
        manifest_path=manifest,
        index_path=db,
        output_path=out,
        force=False,
        now=FIXED_NOW,
    )
    assert code == 0, msgs
    return out


class TestReproducibility:
    def test_two_extractions_byte_identical(self, tmp_path):
        out1 = _build_full_extraction(tmp_path, "run1")
        out2 = _build_full_extraction(tmp_path, "run2")
        assert out1.read_bytes() == out2.read_bytes(), (
            "Two extractions from identical inputs are not byte-identical"
        )

    def test_sha256_matches(self, tmp_path):
        out1 = _build_full_extraction(tmp_path, "run1")
        out2 = _build_full_extraction(tmp_path, "run2")
        sha1 = hashlib.sha256(out1.read_bytes()).hexdigest()
        sha2 = hashlib.sha256(out2.read_bytes()).hexdigest()
        assert sha1 == sha2

    def test_no_crlf_in_output(self, tmp_path):
        out = _build_full_extraction(tmp_path)
        raw = out.read_bytes()
        assert b"\r\n" not in raw, "Extraction JSON contains CRLF bytes"

    def test_paths_use_forward_slashes(self, tmp_path):
        out = _build_full_extraction(tmp_path)
        data = json.loads(out.read_text(encoding="utf-8"))
        for f in data["files"]:
            assert "\\" not in f["path"], f"Backslash in path: {f['path']!r}"

    def test_reference_ids_stable(self, tmp_path):
        out1 = _build_full_extraction(tmp_path, "run1")
        out2 = _build_full_extraction(tmp_path, "run2")
        data1 = json.loads(out1.read_text(encoding="utf-8"))
        data2 = json.loads(out2.read_text(encoding="utf-8"))
        ids1 = sorted(r["id"] for f in data1["files"] for r in f["references"])
        ids2 = sorted(r["id"] for f in data2["files"] for r in f["references"])
        assert ids1 == ids2

    def test_files_ordered_by_path(self, tmp_path):
        out = _build_full_extraction(tmp_path)
        data = json.loads(out.read_text(encoding="utf-8"))
        paths = [f["path"] for f in data["files"]]
        assert paths == sorted(paths)

    def test_references_ordered_by_start_offset(self, tmp_path):
        out = _build_full_extraction(tmp_path)
        data = json.loads(out.read_text(encoding="utf-8"))
        for f in data["files"]:
            offsets = [r["start_offset"] for r in f["references"]]
            assert offsets == sorted(offsets), f"References not sorted in {f['path']}"

    def test_lf_only_in_output(self, tmp_path):
        out = _build_full_extraction(tmp_path)
        text = out.read_text(encoding="utf-8")
        assert "\r" not in text, "Extraction contains \\r"


class TestOsReplaceFailure:
    """
    If os.replace raises during the atomic write, the previous output must
    be left intact and the temp file must be cleaned up.
    """

    def test_os_replace_failure_previous_output_intact(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path, monkeypatch
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
        original_bytes = out.read_bytes()

        # Force os.replace to raise on the next call
        import os as _os

        def bad_replace(src, dst):
            raise OSError("simulated replace failure")

        monkeypatch.setattr(_os, "replace", bad_replace)

        code2, msgs2 = extract_references(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            output_path=out,
            force=True,
            now=FIXED_NOW,
        )
        assert code2 != 0

        # Previous output is untouched
        assert out.read_bytes() == original_bytes

        # No temp files left behind
        temp_files = list(out.parent.glob(".reference-extraction-*.tmp"))
        assert len(temp_files) == 0
