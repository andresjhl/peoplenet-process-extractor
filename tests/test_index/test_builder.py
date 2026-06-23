"""Tests for index builder: construction, transactional safety, --force, scope."""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.index.builder import build_index
from peoplenet_process_extractor.index.validation import validate_index

FIXTURE_CORPUS = Path(__file__).parent.parent / "fixtures" / "index_corpus"
FIXED_NOW = datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc)


def _make_manifest(tmp_path, corpus=None, source_roots=None, corpus_id="index-corpus"):
    corpus = corpus or FIXTURE_CORPUS
    manifest = tmp_path / "corpus-manifest.json"
    code, msgs = create_inventory(
        corpus_root=corpus,
        output_path=manifest,
        corpus_id=corpus_id,
        source_roots=source_roots,
        now=FIXED_NOW,
    )
    assert code == 0, f"create_inventory failed: {msgs}"
    return manifest


class TestBuildSuccess:
    def test_builds_valid_index(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        db = tmp_path / "index.sqlite"
        code, msgs = build_index(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        assert code == 0, f"build_index failed: {msgs}"
        assert db.exists()
        errors = validate_index(db)
        assert errors == []

    def test_no_temp_files_after_success(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        db = tmp_path / "index.sqlite"
        build_index(corpus_root=FIXTURE_CORPUS, manifest_path=manifest, output_path=db, now=FIXED_NOW)
        # Only the output and manifest should exist, no .tmp files.
        leftover = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
        assert leftover == []

    def test_message_on_success(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        db = tmp_path / "index.sqlite"
        code, msgs = build_index(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        assert code == 0
        assert any("index.sqlite" in m for m in msgs)


class TestBuildErrors:
    def test_invalid_manifest_fails(self, tmp_path):
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text("not json {")
        db = tmp_path / "index.sqlite"
        code, msgs = build_index(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=bad_manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        assert code != 0
        assert not db.exists()

    def test_nonexistent_manifest_fails(self, tmp_path):
        db = tmp_path / "index.sqlite"
        code, msgs = build_index(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=tmp_path / "no_manifest.json",
            output_path=db,
            now=FIXED_NOW,
        )
        assert code != 0
        assert not db.exists()

    def test_nonexistent_corpus_fails(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        db = tmp_path / "index.sqlite"
        code, msgs = build_index(
            corpus_root=tmp_path / "nonexistent",
            manifest_path=manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        assert code != 0
        assert not db.exists()

    def test_corpus_mismatch_fails(self, tmp_path):
        manifest = _make_manifest(tmp_path)

        # Modify the corpus (add a new file).
        corpus_copy = tmp_path / "corpus_copy"
        shutil.copytree(FIXTURE_CORPUS, corpus_copy)
        (corpus_copy / "extra_file.ln4").write_text("extra content")

        db = tmp_path / "index.sqlite"
        code, msgs = build_index(
            corpus_root=corpus_copy,
            manifest_path=manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        assert code != 0
        assert not db.exists()

    def test_output_exists_without_force(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        db = tmp_path / "index.sqlite"
        db.write_text("existing")
        code, msgs = build_index(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        assert code != 0
        assert db.read_text() == "existing"

    def test_no_partial_db_on_manifest_error(self, tmp_path):
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text("{}")
        db = tmp_path / "index.sqlite"
        code, _ = build_index(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=bad_manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        assert code != 0
        assert not db.exists()

    def test_no_temp_files_on_failure(self, tmp_path):
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text("not json")
        db = tmp_path / "index.sqlite"
        build_index(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=bad_manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        leftover = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
        assert leftover == []


class TestForce:
    def test_force_replaces_existing(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        db = tmp_path / "index.sqlite"
        build_index(corpus_root=FIXTURE_CORPUS, manifest_path=manifest, output_path=db, now=FIXED_NOW)

        code, msgs = build_index(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=manifest,
            output_path=db,
            force=True,
            now=FIXED_NOW,
        )
        assert code == 0
        errors = validate_index(db)
        assert errors == []

    def test_force_preserves_previous_on_build_failure(self, tmp_path):
        # Build a valid index first.
        manifest = _make_manifest(tmp_path)
        db = tmp_path / "index.sqlite"
        code, _ = build_index(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        assert code == 0
        original_size = db.stat().st_size

        # Try to force-rebuild with an invalid manifest.
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text("not json {")
        code, _ = build_index(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=bad_manifest,
            output_path=db,
            force=True,
            now=FIXED_NOW,
        )
        assert code != 0
        # Previous database must be intact.
        assert db.stat().st_size == original_size
        errors = validate_index(db)
        assert errors == []

    def test_no_temp_files_after_force_success(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        db = tmp_path / "index.sqlite"
        build_index(corpus_root=FIXTURE_CORPUS, manifest_path=manifest, output_path=db, now=FIXED_NOW)
        build_index(corpus_root=FIXTURE_CORPUS, manifest_path=manifest, output_path=db, force=True, now=FIXED_NOW)
        leftover = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
        assert leftover == []


class TestNoSidecars:
    """WAL and SHM sidecar files must never be left beside the output or temp path."""

    def _sidecar_files(self, directory: Path) -> list[Path]:
        return [p for p in directory.iterdir() if p.name.endswith(("-wal", "-shm"))]

    def test_no_wal_shm_after_success(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        db = tmp_path / "index.sqlite"
        code, msgs = build_index(
            corpus_root=FIXTURE_CORPUS, manifest_path=manifest, output_path=db, now=FIXED_NOW
        )
        assert code == 0
        assert self._sidecar_files(tmp_path) == []

    def test_no_wal_shm_after_build_failure(self, tmp_path):
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text("not json")
        db = tmp_path / "index.sqlite"
        build_index(
            corpus_root=FIXTURE_CORPUS, manifest_path=bad_manifest, output_path=db, now=FIXED_NOW
        )
        assert self._sidecar_files(tmp_path) == []

    def test_no_wal_shm_after_force_success(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        db = tmp_path / "index.sqlite"
        build_index(corpus_root=FIXTURE_CORPUS, manifest_path=manifest, output_path=db, now=FIXED_NOW)
        build_index(
            corpus_root=FIXTURE_CORPUS, manifest_path=manifest, output_path=db,
            force=True, now=FIXED_NOW
        )
        assert self._sidecar_files(tmp_path) == []


class TestScopeCompatibility:
    def test_root_only_corpus(self, tmp_path):
        """A corpus with only root-level files builds correctly."""
        root_corpus = tmp_path / "root_corpus"
        root_corpus.mkdir()
        (root_corpus / "only_root.ln4").write_text("root content")

        manifest = tmp_path / "manifest.json"
        code, _ = create_inventory(corpus_root=root_corpus, output_path=manifest, now=FIXED_NOW)
        assert code == 0

        db = tmp_path / "index.sqlite"
        code, msgs = build_index(
            corpus_root=root_corpus,
            manifest_path=manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        assert code == 0, f"build failed: {msgs}"
        errors = validate_index(db)
        assert errors == []

    def test_cp_filter_only_indexes_cp_files(self, tmp_path):
        manifest = _make_manifest(tmp_path, source_roots=["CP"])
        db = tmp_path / "index.sqlite"
        code, msgs = build_index(
            corpus_root=FIXTURE_CORPUS,
            manifest_path=manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        assert code == 0, f"build failed: {msgs}"

        con = sqlite3.connect(str(db))
        try:
            rows = con.execute("SELECT path FROM source_files").fetchall()
        finally:
            con.close()

        paths = {r[0] for r in rows}
        for p in paths:
            assert p.startswith("CP/"), f"Non-CP file in CP-filtered index: {p}"

    def test_no_new_root_outside_scope(self, tmp_path):
        """After building with CP filter, a new physical GTO root is not indexed."""
        corpus_copy = tmp_path / "corpus_copy"
        shutil.copytree(FIXTURE_CORPUS, corpus_copy)
        manifest = _make_manifest(tmp_path, corpus=corpus_copy, source_roots=["CP"])

        # Add a new root outside scope.
        new_root = corpus_copy / "NEW_ROOT"
        new_root.mkdir()
        (new_root / "new_file.ln4").write_text("out of scope")

        db = tmp_path / "index.sqlite"
        code, msgs = build_index(
            corpus_root=corpus_copy,
            manifest_path=manifest,
            output_path=db,
            now=FIXED_NOW,
        )
        # This should succeed because NEW_ROOT is outside CP scope.
        assert code == 0, f"build failed: {msgs}"

        con = sqlite3.connect(str(db))
        try:
            rows = con.execute("SELECT path FROM source_files WHERE source_root = 'NEW_ROOT'").fetchall()
        finally:
            con.close()
        assert rows == [], "NEW_ROOT files must not be indexed"
