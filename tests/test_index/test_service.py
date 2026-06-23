"""Tests for index service: build_index_service, verify_index_service."""
from __future__ import annotations

import shutil
from pathlib import Path


from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.index.service import build_index_service, verify_index_service

from .conftest import FIXTURE_CORPUS, FIXED_NOW


class TestBuildIndexService:
    def test_success(self, tmp_path):
        manifest = tmp_path / "manifest.json"
        code, _ = create_inventory(corpus_root=FIXTURE_CORPUS, output_path=manifest, corpus_id="ic", now=FIXED_NOW)
        assert code == 0
        db = tmp_path / "idx.sqlite"
        code, msgs = build_index_service(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        assert code == 0
        assert db.exists()


class TestVerifyIndexService:
    def test_valid_index(self, built_index, corpus_manifest):
        code, msgs = verify_index_service(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=corpus_manifest,
            db_path=built_index,
        )
        assert code == 0, f"verify failed: {msgs}"
        assert any("valid" in m.lower() for m in msgs)

    def test_nonexistent_db(self, corpus_manifest):
        code, msgs = verify_index_service(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=corpus_manifest,
            db_path=Path("/nonexistent/path.sqlite"),
        )
        assert code != 0
        assert any("not found" in m.lower() or "error" in m.lower() for m in msgs)

    def test_nonexistent_manifest(self, built_index):
        code, msgs = verify_index_service(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=Path("/nonexistent/manifest.json"),
            db_path=built_index,
        )
        assert code != 0

    def test_invalid_manifest(self, built_index, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json")
        code, msgs = verify_index_service(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=bad,
            db_path=built_index,
        )
        assert code != 0

    def test_different_manifest_detected(self, built_index, tmp_path):
        """A different valid manifest (different corpus_id) should fail hash check."""
        other_manifest = tmp_path / "other.json"
        code, _ = create_inventory(
            corpus_root=FIXTURE_CORPUS,
            output_path=other_manifest,
            corpus_id="different-corpus",
            now=FIXED_NOW,
        )
        assert code == 0
        code, msgs = verify_index_service(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=other_manifest,
            db_path=built_index,
        )
        assert code != 0

    def test_corrupted_corpus_fails(self, tmp_path):
        corpus_copy = tmp_path / "corpus_copy"
        shutil.copytree(FIXTURE_CORPUS, corpus_copy)
        manifest = tmp_path / "manifest.json"
        code, _ = create_inventory(corpus_root=corpus_copy, output_path=manifest, corpus_id="ic", now=FIXED_NOW)
        assert code == 0
        db = tmp_path / "idx.sqlite"
        from peoplenet_process_extractor.index.builder import build_index
        code, _ = build_index(corpus_root=corpus_copy, manifest_path=manifest, output_path=db, now=FIXED_NOW)
        assert code == 0

        # Corrupt the corpus.
        (corpus_copy / "small.bin").write_bytes(b"corrupted content!!")

        code, msgs = verify_index_service(
            corpus_root=corpus_copy,
            manifest_path=manifest,
            db_path=db,
        )
        assert code != 0
