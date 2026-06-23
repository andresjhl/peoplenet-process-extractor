"""Tests for logical reproducibility and the golden test."""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.index.builder import build_index
from peoplenet_process_extractor.index.queries import logical_export

from .conftest import FIXTURE_CORPUS, FIXED_NOW

GOLDEN_PATH = Path(__file__).parent.parent / "golden" / "structural-index-v1.json"

# Path of the fixture file that carries a real warning (malformed rule name).
_WARNING_PATH = "CP/NODE STRUCTURE/OBJ_A/ITEM/METHOD/METH_W/RULES/METH_W.ln4"


def _build_non_git_index(tmp_path: Path) -> tuple[Path, Path]:
    """
    Copy the fixture corpus to a temp directory that is not under any git repo,
    then build a manifest and index.  This makes corpus_manifest_sha256,
    corpus_manifest_size_bytes, and index_created_at deterministic across
    environments (no git state, fixed clock via FIXED_NOW).
    """
    non_git_corpus = tmp_path / "non_git_corpus"
    shutil.copytree(FIXTURE_CORPUS, non_git_corpus)
    manifest = tmp_path / "manifest.json"
    code, msgs = create_inventory(
        corpus_root=non_git_corpus,
        output_path=manifest,
        corpus_id="index-corpus",
        now=FIXED_NOW,
    )
    assert code == 0, msgs
    db = tmp_path / "idx.sqlite"
    code, msgs = build_index(
        corpus_root=non_git_corpus, manifest_path=manifest, output_path=db, now=FIXED_NOW
    )
    assert code == 0, msgs
    return manifest, db


class TestLogicalReproducibility:
    def test_two_builds_same_logical_content(self, tmp_path):
        manifest, db1 = _build_non_git_index(tmp_path)

        db2 = tmp_path / "idx2.sqlite"
        code, msgs = build_index(
            corpus_root=tmp_path / "non_git_corpus",
            manifest_path=manifest,
            output_path=db2,
            now=FIXED_NOW,
        )
        assert code == 0, msgs

        exp1 = logical_export(db1)
        exp2 = logical_export(db2)

        assert exp1["source_files"] == exp2["source_files"]
        assert exp1["structural_elements"] == exp2["structural_elements"]
        assert exp1["metadata"]["corpus_manifest_sha256"] == exp2["metadata"]["corpus_manifest_sha256"]
        assert exp1["metadata"]["corpus_manifest_size_bytes"] == exp2["metadata"]["corpus_manifest_size_bytes"]
        assert exp1["metadata"]["index_created_at"] == exp2["metadata"]["index_created_at"]

    def test_same_content_regardless_of_insertion_order(self, tmp_path):
        """Files are always in path order regardless of filesystem traversal order."""
        _, db = _build_non_git_index(tmp_path)
        files = logical_export(db)["source_files"]
        paths = [f["path"] for f in files]
        assert paths == sorted(paths)

    def test_elements_deterministic_order(self, tmp_path):
        _, db = _build_non_git_index(tmp_path)
        elements = logical_export(db)["structural_elements"]
        keys = [(e["meta4object"], e["item_type"], e["item_name"]) for e in elements]
        assert keys == sorted(keys)


class TestGolden:
    def test_golden_file_exists(self):
        assert GOLDEN_PATH.exists(), f"Golden file not found: {GOLDEN_PATH}"

    def test_matches_golden(self, tmp_path):
        """
        Build from a non-git copy of the fixture corpus so all deterministic
        fields (corpus_manifest_sha256/size, index_created_at) can be compared
        against the stored golden.  Only generator_version and git-state fields
        are excluded — they vary by environment.
        """
        golden = json.loads(GOLDEN_PATH.read_text())
        _, db = _build_non_git_index(tmp_path)
        export = logical_export(db)

        # generator_version is the installed package version — varies by environment.
        # corpus_git_commit / corpus_git_dirty depend on the live git state.
        _ENV_FIELDS = {"corpus_git_commit", "corpus_git_dirty", "generator_version"}
        golden_meta = {k: v for k, v in golden["metadata"].items() if k not in _ENV_FIELDS}
        actual_meta = {k: v for k, v in export["metadata"].items() if k not in _ENV_FIELDS}
        assert actual_meta == golden_meta, (
            f"Metadata mismatch:\nactual  = {actual_meta}\ngolden  = {golden_meta}"
        )

        assert export["source_files"] == golden["source_files"], "source_files mismatch"
        assert export["structural_elements"] == golden["structural_elements"], "structural_elements mismatch"

    def test_golden_has_warning_file(self):
        """The stored golden must contain the real warning from METH_W.ln4."""
        golden = json.loads(GOLDEN_PATH.read_text())
        warning_files = [f for f in golden["source_files"] if f["warnings"]]
        assert len(warning_files) >= 1, "Golden must have at least one file with warnings"
        meth_w = next((f for f in golden["source_files"] if f["path"] == _WARNING_PATH), None)
        assert meth_w is not None, f"Expected {_WARNING_PATH!r} in golden source_files"
        assert meth_w["warning_count"] == 1
        assert len(meth_w["warnings"]) == 1
        w = meth_w["warnings"][0]
        assert w["sequence"] == 0
        assert "METH_W.ln4" in w["message"]
        assert "separators" in w["message"]

    def test_golden_has_id_field(self):
        """Every source_files entry in the stored golden must have an id."""
        golden = json.loads(GOLDEN_PATH.read_text())
        for entry in golden["source_files"]:
            assert "id" in entry, f"Missing id in golden entry: {entry['path']!r}"

    def test_golden_ids_match_path_order(self):
        """IDs in the golden must be 1..N in ascending path order."""
        golden = json.loads(GOLDEN_PATH.read_text())
        files = golden["source_files"]
        paths = [f["path"] for f in files]
        assert paths == sorted(paths), "golden source_files are not in path order"
        for i, f in enumerate(files, start=1):
            assert f["id"] == i, f"Expected id={i} for {f['path']!r}, got id={f['id']}"

    def test_golden_has_index_created_at(self):
        """index_created_at must be present in the stored golden metadata."""
        golden = json.loads(GOLDEN_PATH.read_text())
        assert "index_created_at" in golden["metadata"]
        assert golden["metadata"]["index_created_at"] == FIXED_NOW.isoformat()

    def test_golden_has_generator_version(self):
        """generator_version must be present in the stored golden metadata."""
        golden = json.loads(GOLDEN_PATH.read_text())
        assert "generator_version" in golden["metadata"]
        assert isinstance(golden["metadata"]["generator_version"], str)
        assert len(golden["metadata"]["generator_version"]) > 0


class TestExportFieldPresence:
    """Verify that logical_export() always includes each required field."""

    def test_generator_version_present(self, tmp_path):
        _, db = _build_non_git_index(tmp_path)
        meta = logical_export(db)["metadata"]
        assert "generator_version" in meta
        assert isinstance(meta["generator_version"], str)
        assert len(meta["generator_version"]) > 0

    def test_index_created_at_present_and_fixed(self, tmp_path):
        _, db = _build_non_git_index(tmp_path)
        meta = logical_export(db)["metadata"]
        assert "index_created_at" in meta
        assert meta["index_created_at"] == FIXED_NOW.isoformat()

    def test_source_file_ids_present(self, tmp_path):
        _, db = _build_non_git_index(tmp_path)
        files = logical_export(db)["source_files"]
        assert all("id" in f for f in files)

    def test_source_file_ids_match_path_order(self, tmp_path):
        """IDs must be 1..N in ascending path order."""
        _, db = _build_non_git_index(tmp_path)
        files = logical_export(db)["source_files"]
        paths = [f["path"] for f in files]
        assert paths == sorted(paths)
        for i, f in enumerate(files, start=1):
            assert f["id"] == i, f"Expected id={i} for {f['path']!r}, got {f['id']}"

    def test_warnings_exported_as_objects(self, tmp_path):
        """Warnings must be exported as {sequence, message} objects, not plain strings."""
        _, db = _build_non_git_index(tmp_path)
        files = logical_export(db)["source_files"]
        meth_w = next(f for f in files if f["path"] == _WARNING_PATH)
        assert meth_w["warnings"] != [], "METH_W.ln4 must have warnings"
        for w in meth_w["warnings"]:
            assert isinstance(w, dict), "Each warning must be a dict"
            assert "sequence" in w
            assert "message" in w
            assert isinstance(w["sequence"], int)
            assert isinstance(w["message"], str)

    def test_warning_sequence_value(self, tmp_path):
        """The single warning on METH_W.ln4 must have sequence=0."""
        _, db = _build_non_git_index(tmp_path)
        files = logical_export(db)["source_files"]
        meth_w = next(f for f in files if f["path"] == _WARNING_PATH)
        assert meth_w["warnings"][0]["sequence"] == 0


class TestExportDetectsTampering:
    """
    Verify that logical_export() output differs when index data is tampered.
    All tests build two exports: one clean, one after direct DB mutation.
    """

    def _open_rw(self, db_path: Path) -> sqlite3.Connection:
        con = sqlite3.connect(str(db_path))
        con.execute("PRAGMA foreign_keys = OFF")
        return con

    def test_changed_source_file_id_detected(self, tmp_path):
        """Swapping two file IDs changes the exported id field."""
        _, db = _build_non_git_index(tmp_path)
        clean = logical_export(db)
        con = self._open_rw(db)
        # Swap id=1 and id=2 via a temp id to avoid UNIQUE conflicts.
        con.execute("UPDATE source_files SET id = 99 WHERE id = 1")
        con.execute("UPDATE source_files SET id = 1 WHERE id = 2")
        con.execute("UPDATE source_files SET id = 2 WHERE id = 99")
        con.commit()
        con.close()
        tampered = logical_export(db)
        assert clean["source_files"] != tampered["source_files"]

    def test_changed_generator_version_detected(self, tmp_path):
        """A generator_version change in index_metadata is reflected in the export."""
        _, db = _build_non_git_index(tmp_path)
        clean = logical_export(db)
        con = self._open_rw(db)
        con.execute("UPDATE index_metadata SET generator_version = 'TAMPERED' WHERE id = 1")
        con.commit()
        con.close()
        tampered = logical_export(db)
        assert clean["metadata"]["generator_version"] != tampered["metadata"]["generator_version"]
        assert tampered["metadata"]["generator_version"] == "TAMPERED"

    def test_changed_index_created_at_detected(self, tmp_path):
        """An index_created_at change in index_metadata is reflected in the export."""
        _, db = _build_non_git_index(tmp_path)
        clean = logical_export(db)
        con = self._open_rw(db)
        con.execute(
            "UPDATE index_metadata SET index_created_at = '1999-01-01T00:00:00+00:00' WHERE id = 1"
        )
        con.commit()
        con.close()
        tampered = logical_export(db)
        assert clean["metadata"]["index_created_at"] != tampered["metadata"]["index_created_at"]
        assert tampered["metadata"]["index_created_at"] == "1999-01-01T00:00:00+00:00"

    def _file_id(self, db: Path, path: str) -> int:
        con = sqlite3.connect(str(db))
        fid = con.execute("SELECT id FROM source_files WHERE path = ?", (path,)).fetchone()[0]
        con.close()
        return fid

    def test_changed_warning_sequence_detected(self, tmp_path):
        """Shifting a warning sequence by 10 changes the exported warnings."""
        _, db = _build_non_git_index(tmp_path)
        clean = logical_export(db)
        fid = self._file_id(db, _WARNING_PATH)
        con = self._open_rw(db)
        con.execute(
            "UPDATE file_warnings SET sequence = sequence + 10 WHERE source_file_id = ?", (fid,)
        )
        con.commit()
        con.close()
        tampered = logical_export(db)
        clean_file = next(f for f in clean["source_files"] if f["path"] == _WARNING_PATH)
        tampered_file = next(f for f in tampered["source_files"] if f["path"] == _WARNING_PATH)
        assert clean_file["warnings"] != tampered_file["warnings"]
        assert tampered_file["warnings"][0]["sequence"] == 10

    def test_changed_warning_message_detected(self, tmp_path):
        """Changing a warning message changes the exported warnings."""
        _, db = _build_non_git_index(tmp_path)
        clean = logical_export(db)
        fid = self._file_id(db, _WARNING_PATH)
        con = self._open_rw(db)
        con.execute(
            "UPDATE file_warnings SET message = 'TAMPERED' WHERE source_file_id = ?", (fid,)
        )
        con.commit()
        con.close()
        tampered = logical_export(db)
        clean_file = next(f for f in clean["source_files"] if f["path"] == _WARNING_PATH)
        tampered_file = next(f for f in tampered["source_files"] if f["path"] == _WARNING_PATH)
        assert clean_file["warnings"] != tampered_file["warnings"]
        assert tampered_file["warnings"][0]["message"] == "TAMPERED"

    def test_deleted_warning_detected(self, tmp_path):
        """Deleting a warning row reduces the exported warnings list."""
        _, db = _build_non_git_index(tmp_path)
        clean = logical_export(db)
        fid = self._file_id(db, _WARNING_PATH)
        con = self._open_rw(db)
        con.execute("DELETE FROM file_warnings WHERE source_file_id = ?", (fid,))
        con.commit()
        con.close()
        tampered = logical_export(db)
        clean_file = next(f for f in clean["source_files"] if f["path"] == _WARNING_PATH)
        tampered_file = next(f for f in tampered["source_files"] if f["path"] == _WARNING_PATH)
        assert clean_file["warnings"] != tampered_file["warnings"]
        assert len(clean_file["warnings"]) == 1
        assert tampered_file["warnings"] == []

    def test_extra_warning_detected(self, tmp_path):
        """Inserting an extra warning row changes the exported warnings list."""
        _, db = _build_non_git_index(tmp_path)
        clean = logical_export(db)
        fid = self._file_id(db, _WARNING_PATH)
        con = self._open_rw(db)
        con.execute(
            "INSERT INTO file_warnings(source_file_id, sequence, message) VALUES (?, 1, 'extra')",
            (fid,),
        )
        con.commit()
        con.close()
        tampered = logical_export(db)
        clean_file = next(f for f in clean["source_files"] if f["path"] == _WARNING_PATH)
        tampered_file = next(f for f in tampered["source_files"] if f["path"] == _WARNING_PATH)
        assert clean_file["warnings"] != tampered_file["warnings"]
        assert len(tampered_file["warnings"]) == 2
        assert tampered_file["warnings"][1] == {"sequence": 1, "message": "extra"}
