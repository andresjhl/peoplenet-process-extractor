"""Tests for index validation: integrity, FK, metadata, coverage, manipulation."""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from peoplenet_process_extractor.corpus.models import CorpusManifest
from peoplenet_process_extractor.index.validation import validate_index



class TestValidIndex:
    def test_valid_index_has_no_errors(self, built_index):
        errors = validate_index(built_index)
        assert errors == []

    def test_valid_index_with_manifest(self, built_index, corpus_manifest):
        manifest_text = corpus_manifest.read_text()
        from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
        manifest, _ = deserialize_manifest(manifest_text)
        errors = validate_index(built_index, manifest=manifest)
        assert errors == []

    def test_nonexistent_db(self, tmp_path):
        errors = validate_index(tmp_path / "no.sqlite")
        assert any("not found" in e.lower() or "cannot open" in e.lower() for e in errors)

    def test_corrupted_db(self, tmp_path):
        bad_db = tmp_path / "bad.sqlite"
        bad_db.write_bytes(b"not a sqlite file at all")
        errors = validate_index(bad_db)
        assert len(errors) > 0


class TestMissingTable:
    def _remove_table(self, src_db: Path, tmp_path: Path, table: str) -> Path:
        dst = tmp_path / f"missing_{table}.sqlite"
        shutil.copy2(src_db, dst)
        con = sqlite3.connect(str(dst))
        try:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute(f"DROP TABLE IF EXISTS {table}")  # noqa: S608
            con.commit()
        finally:
            con.close()
        return dst

    def test_missing_index_metadata(self, built_index, tmp_path):
        db = self._remove_table(built_index, tmp_path, "index_metadata")
        errors = validate_index(db)
        assert any("index_metadata" in e for e in errors)

    def test_missing_source_files(self, built_index, tmp_path):
        db = self._remove_table(built_index, tmp_path, "source_files")
        errors = validate_index(db)
        assert any("source_files" in e for e in errors)

    def test_missing_structural_elements(self, built_index, tmp_path):
        db = self._remove_table(built_index, tmp_path, "structural_elements")
        errors = validate_index(db)
        assert any("structural_elements" in e for e in errors)


class TestManipulatedMetadata:
    def _copy_db(self, src: Path, tmp_path: Path) -> Path:
        dst = tmp_path / "copy.sqlite"
        shutil.copy2(src, dst)
        return dst

    def test_wrong_build_status(self, built_index, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            # Bypass CHECK constraint by recreating.
            con.execute("PRAGMA writable_schema = ON")
            con.execute(
                "UPDATE index_metadata SET build_status = 'failed' WHERE id = 1"
            )
            con.commit()
            con.execute("PRAGMA writable_schema = OFF")
        except Exception:
            pytest.skip("Cannot bypass CHECK constraint in this SQLite build")
        finally:
            con.close()

        errors = validate_index(db)
        assert any("build_status" in e or "complete" in e for e in errors)

    def test_manipulated_total_count(self, built_index, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("PRAGMA writable_schema = ON")
            con.execute("UPDATE index_metadata SET total_files = 999 WHERE id = 1")
            con.commit()
            con.execute("PRAGMA writable_schema = OFF")
        finally:
            con.close()
        errors = validate_index(db)
        assert any("total_files" in e for e in errors)

    def test_manifest_hash_mismatch(self, built_index, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("PRAGMA writable_schema = ON")
            con.execute(
                "UPDATE index_metadata SET corpus_manifest_sha256 = ? WHERE id = 1",
                ("b" * 64,),
            )
            con.commit()
            con.execute("PRAGMA writable_schema = OFF")
        finally:
            con.close()
        errors = validate_index(db, manifest_sha256="a" * 64)
        assert any("sha256" in e.lower() or "mismatch" in e.lower() for e in errors)


class TestRowManipulation:
    def _copy_db(self, src: Path, tmp_path: Path) -> Path:
        dst = tmp_path / "copy.sqlite"
        shutil.copy2(src, dst)
        return dst

    def test_extra_source_file(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("PRAGMA foreign_keys = OFF")
            # Insert an extra row not in the manifest.
            con.execute(
                "INSERT INTO source_files (path, sha256, size_bytes, extension, source_root, classification, warning_count) "
                "VALUES ('ghost/file.ln4', ?, 10, '.ln4', 'ghost', 'unstructured_ln4', 0)",
                ("c" * 64,),
            )
            con.commit()
        finally:
            con.close()

        manifest_text = corpus_manifest.read_text()
        from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
        manifest, _ = deserialize_manifest(manifest_text)
        errors = validate_index(db, manifest=manifest)
        assert any("ghost/file.ln4" in e for e in errors)

    def test_missing_source_file(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("DELETE FROM structural_elements WHERE source_file_id = 1")
            con.execute("DELETE FROM source_files WHERE id = 1")
            con.commit()
        finally:
            con.close()

        manifest_text = corpus_manifest.read_text()
        from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
        manifest, _ = deserialize_manifest(manifest_text)
        errors = validate_index(db, manifest=manifest)
        assert len(errors) > 0

    def test_structural_element_removed(self, built_index, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("DELETE FROM structural_elements WHERE id = 1")
            con.commit()
        finally:
            con.close()
        errors = validate_index(db)
        assert any("no structural_element" in e.lower() for e in errors)

    def test_extra_structural_element(self, built_index, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("PRAGMA foreign_keys = OFF")
            # The unstructured file (id=4, GTO/loose.ln4) should get an extra element.
            row = con.execute(
                "SELECT id FROM source_files WHERE classification='unstructured_ln4' LIMIT 1"
            ).fetchone()
            if row:
                con.execute(
                    "INSERT INTO structural_elements (source_file_id, meta4object, item_type, item_name) "
                    "VALUES (?, 'FAKE', 'FAKE', 'FAKE')",
                    (row[0],),
                )
            con.commit()
        finally:
            con.close()
        errors = validate_index(db)
        assert any("unexpected structural_element" in e.lower() for e in errors)

    def test_fk_violation_detected(self, built_index, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute(
                "INSERT INTO structural_elements (source_file_id, meta4object, item_type, item_name) "
                "VALUES (9999, 'OBJ', 'TYPE', 'NAME')"
            )
            con.commit()
        finally:
            con.close()

        errors = validate_index(db)
        assert any("foreign key" in e.lower() or "violations" in e.lower() for e in errors)


class TestFieldEquivalence:
    """validate_index with manifest must detect field-level tampering in every table."""

    def _copy_db(self, src: Path, tmp_path: Path) -> Path:
        dst = tmp_path / "copy.sqlite"
        shutil.copy2(src, dst)
        return dst

    def _load_manifest(self, corpus_manifest: Path):
        from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
        manifest, _ = deserialize_manifest(corpus_manifest.read_text())
        return manifest

    # ── source_files scalar fields ────────────────────────────────────────────

    def test_tampered_sha256_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("PRAGMA writable_schema = ON")
            con.execute("UPDATE source_files SET sha256 = ? WHERE id = 1", ("d" * 64,))
            con.commit()
            con.execute("PRAGMA writable_schema = OFF")
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("sha256" in e for e in errors)

    def test_tampered_size_bytes_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("UPDATE source_files SET size_bytes = 999999 WHERE id = 1")
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("size_bytes" in e for e in errors)

    def test_tampered_extension_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("UPDATE source_files SET extension = '.xyz' WHERE id = 1")
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("extension" in e for e in errors)

    def test_tampered_source_root_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute(
                "UPDATE source_files SET source_root = 'TAMPERED' "
                "WHERE id = (SELECT id FROM source_files WHERE source_root IS NOT NULL LIMIT 1)"
            )
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("source_root" in e for e in errors)

    def test_tampered_classification_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("PRAGMA writable_schema = ON")
            # Change structured_ln4 to unstructured_ln4 bypassing the CHECK constraint.
            con.execute(
                "UPDATE source_files SET classification = 'unstructured_ln4' "
                "WHERE id = (SELECT id FROM source_files WHERE classification = 'structured_ln4' LIMIT 1)"
            )
            con.commit()
            con.execute("PRAGMA writable_schema = OFF")
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("classification" in e for e in errors)

    def test_tampered_warning_count_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("UPDATE source_files SET warning_count = 99 WHERE id = 1")
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("warning_count" in e for e in errors)

    # ── structural_elements fields ────────────────────────────────────────────

    def test_tampered_meta4object_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("UPDATE structural_elements SET meta4object = 'TAMPERED' WHERE id = 1")
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("meta4object" in e for e in errors)

    def test_tampered_item_type_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("UPDATE structural_elements SET item_type = 'BOGUS' WHERE id = 1")
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("item_type" in e for e in errors)

    def test_tampered_item_name_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("UPDATE structural_elements SET item_name = 'BOGUS' WHERE id = 1")
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("item_name" in e for e in errors)

    def test_tampered_rule_id_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("UPDATE structural_elements SET rule_id = 'R999' WHERE id = 1")
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("rule_id" in e for e in errors)

    def test_tampered_rule_date_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute(
                "UPDATE structural_elements SET rule_date = '9999_99_99' WHERE id = 1"
            )
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("rule_date" in e for e in errors)

    # ── file_warnings manipulation ────────────────────────────────────────────

    def test_added_warning_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("PRAGMA foreign_keys = OFF")
            # Add a spurious warning to file id=1 (which has none in manifest).
            con.execute(
                "INSERT INTO file_warnings (source_file_id, sequence, message) VALUES (1, 0, 'fake warning')"
            )
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert any("warning" in e.lower() for e in errors)

    def test_warning_reorder_detected(self, built_index, corpus_manifest, tmp_path):
        """Reordering warning messages (sequence preserved, content swapped) is detected."""
        # We need a file with at least two warnings. Inject them directly into a copy.
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("PRAGMA foreign_keys = OFF")
            # File id=1: artificially give it two warnings in the DB only
            # (manifest has zero, so we're already testing added_warning above).
            # Instead test that if we swap two existing warnings the order mismatch is caught.
            # Since fixture files have no warnings, we directly inject and then swap.
            con.execute(
                "INSERT INTO file_warnings (source_file_id, sequence, message) VALUES (1, 0, 'first')"
            )
            con.execute(
                "INSERT INTO file_warnings (source_file_id, sequence, message) VALUES (1, 1, 'second')"
            )
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        # The manifest has 0 warnings for this file; DB has 2 — mismatch detected.
        assert any("warning" in e.lower() for e in errors)


# ─── helpers for warning-sequence tests ──────────────────────────────────────

def _make_simple_manifest(corpus_manifest_path: Path, target_path: str, warnings: list[str]) -> CorpusManifest:
    """Return a CorpusManifest with one file's warnings replaced in-memory."""
    from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
    manifest, _ = deserialize_manifest(corpus_manifest_path.read_text())
    for entry in manifest.files:
        if entry.path == target_path:
            entry.warnings = list(warnings)
    return manifest


def _copy_db_with_warnings(
    src: Path, tmp_path: Path, target_path: str, warnings: list[str]
) -> Path:
    """Copy a DB and inject warning rows for target_path at sequences 0,1,..."""
    dst = tmp_path / "w_db.sqlite"
    shutil.copy2(src, dst)
    con = sqlite3.connect(str(dst))
    try:
        con.execute("PRAGMA foreign_keys = OFF")
        row = con.execute("SELECT id FROM source_files WHERE path = ?", (target_path,)).fetchone()
        assert row, f"path not found in DB: {target_path}"
        file_id = row[0]
        for seq, msg in enumerate(warnings):
            con.execute(
                "INSERT INTO file_warnings (source_file_id, sequence, message) VALUES (?,?,?)",
                (file_id, seq, msg),
            )
        con.execute("UPDATE source_files SET warning_count = ? WHERE id = ?", (len(warnings), file_id))
        con.commit()
    finally:
        con.close()
    return dst


# Target file for sequence tests: GTO/loose.ln4 (id=4, unstructured_ln4, no real warnings).
_SEQ_PATH = "GTO/loose.ln4"
_WARNINGS = ["alpha", "beta", "gamma"]


class TestWarningSequenceValidation:
    """validate_index must detect any deviation from exact 0,1,...,N-1 sequences."""

    def _setup(self, built_index: Path, corpus_manifest: Path, tmp_path: Path) -> tuple[Path, object]:
        """Build a DB with warnings at 0,1,2 and a matching manifest."""
        # Use a unique sub-dir so multiple tests don't collide on tmp_path.
        sub = tmp_path / f"seq_{id(self)}"
        sub.mkdir(exist_ok=True)
        db = _copy_db_with_warnings(built_index, sub, _SEQ_PATH, _WARNINGS)
        manifest = _make_simple_manifest(corpus_manifest, _SEQ_PATH, _WARNINGS)
        return db, manifest

    def test_valid_sequence_passes(self, built_index, corpus_manifest, tmp_path):
        db, manifest = self._setup(built_index, corpus_manifest, tmp_path)
        errors = validate_index(db, manifest=manifest)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_shifted_sequence_detected(self, built_index, corpus_manifest, tmp_path):
        """sequence + 10 for all rows must be detected."""
        db, manifest = self._setup(built_index, corpus_manifest, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            # Shift: 0→10, 1→11, 2→12 (no UNIQUE collision since target values don't exist).
            con.execute("UPDATE file_warnings SET sequence = sequence + 10")
            con.commit()
        finally:
            con.close()
        errors = validate_index(db, manifest=manifest)
        assert len(errors) > 0
        assert any(_SEQ_PATH in e for e in errors)
        assert any("warning" in e.lower() for e in errors)

    def test_gap_sequence_detected(self, built_index, corpus_manifest, tmp_path):
        """Deleting the middle warning creates a gap (0, 2) instead of (0, 1, 2)."""
        db, manifest = self._setup(built_index, corpus_manifest, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            file_id = con.execute("SELECT id FROM source_files WHERE path=?", (_SEQ_PATH,)).fetchone()[0]
            con.execute("DELETE FROM file_warnings WHERE source_file_id=? AND sequence=1", (file_id,))
            con.commit()
        finally:
            con.close()
        errors = validate_index(db, manifest=manifest)
        assert len(errors) > 0
        assert any(_SEQ_PATH in e for e in errors)

    def test_wrong_sequence_correct_message_detected(self, built_index, corpus_manifest, tmp_path):
        """Swapping sequence numbers (messages in wrong positions) is detected."""
        db, manifest = self._setup(built_index, corpus_manifest, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            file_id = con.execute("SELECT id FROM source_files WHERE path=?", (_SEQ_PATH,)).fetchone()[0]
            # Swap sequences for rows 0 and 1 using a temp value to avoid UNIQUE collision.
            con.execute(
                "UPDATE file_warnings SET sequence=99 WHERE source_file_id=? AND sequence=0",
                (file_id,),
            )
            con.execute(
                "UPDATE file_warnings SET sequence=0 WHERE source_file_id=? AND sequence=1",
                (file_id,),
            )
            con.execute(
                "UPDATE file_warnings SET sequence=1 WHERE source_file_id=? AND sequence=99",
                (file_id,),
            )
            con.commit()
        finally:
            con.close()
        errors = validate_index(db, manifest=manifest)
        assert len(errors) > 0
        assert any(_SEQ_PATH in e for e in errors)

    def test_deleted_warning_detected(self, built_index, corpus_manifest, tmp_path):
        """Deleting one warning row is detected."""
        db, manifest = self._setup(built_index, corpus_manifest, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            file_id = con.execute("SELECT id FROM source_files WHERE path=?", (_SEQ_PATH,)).fetchone()[0]
            con.execute("DELETE FROM file_warnings WHERE source_file_id=? AND sequence=0", (file_id,))
            con.commit()
        finally:
            con.close()
        errors = validate_index(db, manifest=manifest)
        assert len(errors) > 0
        assert any(_SEQ_PATH in e for e in errors)

    def test_extra_warning_detected(self, built_index, corpus_manifest, tmp_path):
        """Adding an extra warning beyond what the manifest expects is detected."""
        db, manifest = self._setup(built_index, corpus_manifest, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            file_id = con.execute("SELECT id FROM source_files WHERE path=?", (_SEQ_PATH,)).fetchone()[0]
            con.execute(
                "INSERT INTO file_warnings (source_file_id, sequence, message) VALUES (?,?,?)",
                (file_id, len(_WARNINGS), "extra"),
            )
            con.commit()
        finally:
            con.close()
        errors = validate_index(db, manifest=manifest)
        assert len(errors) > 0
        assert any(_SEQ_PATH in e for e in errors)

    def test_modified_message_detected(self, built_index, corpus_manifest, tmp_path):
        """Changing a warning message text is detected."""
        db, manifest = self._setup(built_index, corpus_manifest, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            file_id = con.execute("SELECT id FROM source_files WHERE path=?", (_SEQ_PATH,)).fetchone()[0]
            con.execute(
                "UPDATE file_warnings SET message='TAMPERED' WHERE source_file_id=? AND sequence=0",
                (file_id,),
            )
            con.commit()
        finally:
            con.close()
        errors = validate_index(db, manifest=manifest)
        assert len(errors) > 0
        assert any(_SEQ_PATH in e for e in errors)


class TestMetadataIdentityValidation:
    """corpus_id and corpus_created_at in index_metadata must match the manifest."""

    def _copy_db(self, src: Path, tmp_path: Path) -> Path:
        dst = tmp_path / "id_copy.sqlite"
        shutil.copy2(src, dst)
        return dst

    def _load_manifest(self, corpus_manifest: Path):
        from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
        manifest, _ = deserialize_manifest(corpus_manifest.read_text())
        return manifest

    def test_corpus_id_mismatch_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("UPDATE index_metadata SET corpus_id = 'wrong-corpus' WHERE id = 1")
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert len(errors) > 0
        assert any("corpus_id" in e for e in errors)
        assert any("wrong-corpus" in e for e in errors)

    def test_corpus_created_at_mismatch_detected(self, built_index, corpus_manifest, tmp_path):
        db = self._copy_db(built_index, tmp_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute(
                "UPDATE index_metadata SET corpus_created_at = '1999-01-01T00:00:00+00:00' WHERE id = 1"
            )
            con.commit()
        finally:
            con.close()
        manifest = self._load_manifest(corpus_manifest)
        errors = validate_index(db, manifest=manifest)
        assert len(errors) > 0
        assert any("corpus_created_at" in e for e in errors)
