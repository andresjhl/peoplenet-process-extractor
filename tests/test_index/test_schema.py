"""Tests for the SQLite schema: tables, columns, PKs, FKs, indexes, constraints."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from peoplenet_process_extractor.index.schema import (
    CREATE_FILE_WARNINGS,
    CREATE_INDEX_METADATA,
    CREATE_INDEXES,
    CREATE_SOURCE_FILES,
    CREATE_STRUCTURAL_ELEMENTS,
    EXPECTED_COLUMNS,
    EXPECTED_TABLES,
    INDEX_FORMAT,
    SCHEMA_VERSION,
)


@pytest.fixture()
def fresh_db(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "test.sqlite"
    con = sqlite3.connect(str(db))
    con.execute("PRAGMA foreign_keys = ON")
    con.execute(CREATE_INDEX_METADATA)
    con.execute(CREATE_SOURCE_FILES)
    con.execute(CREATE_STRUCTURAL_ELEMENTS)
    con.execute(CREATE_FILE_WARNINGS)
    for idx in CREATE_INDEXES:
        con.execute(idx)
    con.commit()
    return con


class TestExpectedTables:
    def test_all_expected_tables_present(self, fresh_db):
        rows = fresh_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in rows}
        assert EXPECTED_TABLES.issubset(names)

    def test_expected_columns_present(self, fresh_db):
        for table, cols in EXPECTED_COLUMNS.items():
            rows = fresh_db.execute(f"PRAGMA table_info({table})").fetchall()  # noqa: S608
            present = {r[1] for r in rows}
            assert cols.issubset(present), f"Missing columns in {table}: {cols - present}"


class TestIndexes:
    def test_expected_indexes_exist(self, fresh_db):
        rows = fresh_db.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        names = {r[0] for r in rows}
        expected = {
            "idx_source_files_classification",
            "idx_source_files_source_root",
            "idx_structural_elements_meta4object",
            "idx_structural_elements_item_type",
            "idx_structural_elements_item_name",
            "idx_structural_elements_combined",
            "idx_file_warnings_source_file_id",
        }
        assert expected.issubset(names)


class TestConstraints:
    def test_index_metadata_single_row_constraint(self, fresh_db):
        row = (
            1, INDEX_FORMAT, SCHEMA_VERSION, "gen", "0.1", "cid",
            "a" * 64, 100, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00",
            None, None, 1, 1, 0, "complete",
        )
        fresh_db.execute(
            "INSERT INTO index_metadata VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row
        )
        fresh_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO index_metadata VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (2,) + row[1:],
            )

    def test_source_files_path_unique(self, fresh_db):
        fresh_db.execute(
            "INSERT INTO source_files VALUES (1, 'a/b.ln4', ?, 10, '.ln4', 'a', 'structured_ln4', 0)",
            ("b" * 64,),
        )
        fresh_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO source_files VALUES (2, 'a/b.ln4', ?, 10, '.ln4', 'a', 'unstructured_ln4', 0)",
                ("c" * 64,),
            )

    def test_structural_element_source_file_fk(self, fresh_db):
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO structural_elements (source_file_id, meta4object, item_type, item_name) "
                "VALUES (999, 'OBJ', 'METHOD', 'M')"
            )
            fresh_db.commit()

    def test_structural_element_unique_per_file(self, fresh_db):
        fresh_db.execute(
            "INSERT INTO source_files VALUES (1, 'a/b.ln4', ?, 10, '.ln4', 'a', 'structured_ln4', 0)",
            ("b" * 64,),
        )
        fresh_db.execute(
            "INSERT INTO structural_elements (source_file_id, meta4object, item_type, item_name) "
            "VALUES (1, 'OBJ', 'METHOD', 'M')"
        )
        fresh_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO structural_elements (source_file_id, meta4object, item_type, item_name) "
                "VALUES (1, 'OBJ2', 'CONCEPT', 'C')"
            )

    def test_file_warnings_fk(self, fresh_db):
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO file_warnings (source_file_id, sequence, message) VALUES (999, 0, 'w')"
            )
            fresh_db.commit()

    def test_foreign_keys_enabled(self, fresh_db):
        row = fresh_db.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1

    def test_classification_domain_constraint(self, fresh_db):
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO source_files VALUES (1, 'a/b.ln4', ?, 10, '.ln4', 'a', 'invalid_class', 0)",
                ("b" * 64,),
            )
            fresh_db.commit()

    def test_classification_valid_values_accepted(self, fresh_db):
        valid = [
            "structured_ln4", "unstructured_ln4", "metadata_json", "other_supported", "ignored"
        ]
        for i, cls in enumerate(valid, start=1):
            fresh_db.execute(
                "INSERT INTO source_files VALUES (?, ?, ?, 10, '.ln4', NULL, ?, 0)",
                (i, f"file{i}.ln4", "b" * 64, cls),
            )
        fresh_db.commit()  # must not raise

    def test_corpus_git_dirty_domain_constraint(self, fresh_db):
        row = (
            1, INDEX_FORMAT, SCHEMA_VERSION, "gen", "0.1", "cid",
            "a" * 64, 100, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00",
            None, 2, 1, 1, 0, "complete",  # corpus_git_dirty=2 is invalid
        )
        with pytest.raises(sqlite3.IntegrityError):
            fresh_db.execute(
                "INSERT INTO index_metadata VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row
            )
            fresh_db.commit()

    def test_corpus_git_dirty_valid_values(self, fresh_db):
        for dirty_val in (None, 0, 1):
            fresh_db.execute("DELETE FROM index_metadata")
            row = (
                1, INDEX_FORMAT, SCHEMA_VERSION, "gen", "0.1", "cid",
                "a" * 64, 100, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00",
                None, dirty_val, 0, 0, 0, "complete",
            )
            fresh_db.execute(
                "INSERT INTO index_metadata VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row
            )
            fresh_db.commit()  # must not raise
