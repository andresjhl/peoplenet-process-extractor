"""Tests for indexed data correctness: files, elements, warnings, IDs."""
from __future__ import annotations

import sqlite3

from .conftest import FIXTURE_CORPUS, FIXED_NOW


class TestAllFilesIndexed:
    def test_all_manifest_files_in_source_files(self, built_index, corpus_manifest):
        import json
        manifest_data = json.loads(corpus_manifest.read_text())
        manifest_paths = {f["path"] for f in manifest_data["files"]}

        con = sqlite3.connect(str(built_index))
        try:
            rows = con.execute("SELECT path FROM source_files").fetchall()
        finally:
            con.close()
        db_paths = {r[0] for r in rows}
        assert manifest_paths == db_paths

    def test_no_extra_files_in_index(self, built_index, corpus_manifest):
        import json
        manifest_data = json.loads(corpus_manifest.read_text())
        manifest_paths = {f["path"] for f in manifest_data["files"]}

        con = sqlite3.connect(str(built_index))
        try:
            rows = con.execute("SELECT path FROM source_files").fetchall()
        finally:
            con.close()
        db_paths = {r[0] for r in rows}
        assert db_paths - manifest_paths == set()


class TestDeterministicIDs:
    def test_ids_match_path_sort_order(self, built_index):
        """IDs are assigned 1..N in ascending path order."""
        con = sqlite3.connect(str(built_index))
        try:
            rows = con.execute("SELECT id, path FROM source_files ORDER BY path").fetchall()
        finally:
            con.close()
        for expected_id, (actual_id, _path) in enumerate(rows, start=1):
            assert actual_id == expected_id

    def test_same_corpus_same_ids(self, tmp_path):
        """Building twice from the same manifest produces the same IDs."""
        from peoplenet_process_extractor.corpus.service import create_inventory
        from peoplenet_process_extractor.index.builder import build_index

        m = tmp_path / "manifest.json"
        create_inventory(corpus_root=FIXTURE_CORPUS, output_path=m, corpus_id="index-corpus", now=FIXED_NOW)

        db1 = tmp_path / "idx1.sqlite"
        db2 = tmp_path / "idx2.sqlite"
        build_index(corpus_root=FIXTURE_CORPUS, manifest_path=m, output_path=db1, now=FIXED_NOW)
        build_index(corpus_root=FIXTURE_CORPUS, manifest_path=m, output_path=db2, now=FIXED_NOW)

        con1 = sqlite3.connect(str(db1))
        con2 = sqlite3.connect(str(db2))
        try:
            rows1 = con1.execute("SELECT id, path FROM source_files ORDER BY id").fetchall()
            rows2 = con2.execute("SELECT id, path FROM source_files ORDER BY id").fetchall()
        finally:
            con1.close()
            con2.close()
        assert rows1 == rows2


class TestStructuredFiles:
    def test_structured_files_have_elements(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            rows = con.execute(
                """
                SELECT sf.path
                FROM source_files sf
                LEFT JOIN structural_elements se ON se.source_file_id = sf.id
                WHERE sf.classification = 'structured_ln4' AND se.id IS NULL
                """
            ).fetchall()
        finally:
            con.close()
        assert rows == [], f"structured_ln4 without element: {rows}"

    def test_correct_structure_for_method(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            row = con.execute(
                """
                SELECT se.meta4object, se.item_type, se.item_name, se.rule_id, se.rule_date
                FROM structural_elements se
                JOIN source_files sf ON sf.id = se.source_file_id
                WHERE sf.path LIKE '%METH_X%'
                """
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        meta4object, item_type, item_name, rule_id, rule_date = row
        assert meta4object == "OBJ_A"
        assert item_type == "METHOD"
        assert item_name == "METH_X"
        assert rule_id == "R1"
        assert rule_date == "2020_01_01"

    def test_correct_structure_for_concept(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            row = con.execute(
                """
                SELECT se.meta4object, se.item_type, se.item_name, se.rule_id, se.rule_date
                FROM structural_elements se
                JOIN source_files sf ON sf.id = se.source_file_id
                WHERE sf.path LIKE '%CONC_Y%'
                """
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        meta4object, item_type, item_name, rule_id, rule_date = row
        assert meta4object == "OBJ_A"
        assert item_type == "CONCEPT"
        assert item_name == "CONC_Y"
        assert rule_id == "R2"
        assert rule_date == "1800_01_01"

    def test_correct_structure_for_validation(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            row = con.execute(
                """
                SELECT se.meta4object, se.item_type, se.item_name, se.rule_id, se.rule_date
                FROM structural_elements se
                JOIN source_files sf ON sf.id = se.source_file_id
                WHERE sf.path LIKE '%VALID_Z%'
                """
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        meta4object, item_type, item_name, rule_id, rule_date = row
        assert meta4object == "OBJ_B"
        assert item_type == "VALIDATION"
        assert item_name == "VALID_Z"
        assert rule_id == "R3"
        assert rule_date == "2023_06_15"


class TestNonStructuredFiles:
    def test_unstructured_has_no_element(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            rows = con.execute(
                """
                SELECT sf.path
                FROM source_files sf
                JOIN structural_elements se ON se.source_file_id = sf.id
                WHERE sf.classification != 'structured_ln4'
                """
            ).fetchall()
        finally:
            con.close()
        assert rows == []

    def test_metadata_json_indexed(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            row = con.execute(
                "SELECT classification, source_root FROM source_files WHERE path = 'metadata.json'"
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        classification, source_root = row
        assert classification == "metadata_json"
        assert source_root is None

    def test_binary_file_indexed(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            row = con.execute(
                "SELECT classification FROM source_files WHERE path = 'small.bin'"
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        assert row[0] == "other_supported"


class TestWarnings:
    def test_warning_count_for_fixture_files(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            rows = con.execute(
                "SELECT path FROM source_files WHERE warning_count > 0"
            ).fetchall()
        finally:
            con.close()
        # METH_W.ln4 has a malformed rule name → one warning; all other files are clean.
        paths = [r[0] for r in rows]
        assert len(paths) == 1
        assert paths[0].endswith("METH_W.ln4")

    def test_warnings_indexed_when_present(self, tmp_path):
        """A file with a malformed rule filename produces a warning that is stored."""
        from peoplenet_process_extractor.corpus.service import create_inventory
        from peoplenet_process_extractor.index.builder import build_index

        corpus = tmp_path / "corpus"
        (corpus / "CP" / "NODE STRUCTURE" / "OBJ" / "ITEM" / "METHOD" / "M" / "RULES").mkdir(
            parents=True
        )
        (corpus / "CP" / "NODE STRUCTURE" / "OBJ" / "ITEM" / "METHOD" / "M" / "RULES" / "NODATE.ln4").write_text(
            "content"
        )

        manifest = tmp_path / "manifest.json"
        code, _ = create_inventory(corpus_root=corpus, output_path=manifest, now=FIXED_NOW)
        assert code == 0

        db = tmp_path / "index.sqlite"
        code, msgs = build_index(corpus_root=corpus, manifest_path=manifest, output_path=db, now=FIXED_NOW)
        assert code == 0, f"build failed: {msgs}"

        con = sqlite3.connect(str(db))
        try:
            rows = con.execute("SELECT path, warning_count FROM source_files").fetchall()
            warn_rows = con.execute("SELECT message FROM file_warnings").fetchall()
        finally:
            con.close()

        nodate_row = next((r for r in rows if "NODATE" in r[0]), None)
        assert nodate_row is not None
        assert nodate_row[1] >= 1
        assert len(warn_rows) >= 1


class TestMetadata:
    def test_metadata_corpus_id(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            row = con.execute("SELECT corpus_id FROM index_metadata WHERE id=1").fetchone()
        finally:
            con.close()
        assert row[0] == "index-corpus"

    def test_metadata_counts(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            meta = con.execute(
                "SELECT total_files, structured_files, unstructured_files FROM index_metadata WHERE id=1"
            ).fetchone()
            actual_total = con.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
            actual_structured = con.execute(
                "SELECT COUNT(*) FROM source_files WHERE classification='structured_ln4'"
            ).fetchone()[0]
            actual_unstructured = con.execute(
                "SELECT COUNT(*) FROM source_files WHERE classification='unstructured_ln4'"
            ).fetchone()[0]
        finally:
            con.close()
        assert meta[0] == actual_total
        assert meta[1] == actual_structured
        assert meta[2] == actual_unstructured

    def test_metadata_counts_correct_values(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            meta = con.execute(
                "SELECT total_files, structured_files, unstructured_files FROM index_metadata WHERE id=1"
            ).fetchone()
        finally:
            con.close()
        assert meta[0] == 7
        assert meta[1] == 4
        assert meta[2] == 1

    def test_metadata_build_status_complete(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            row = con.execute("SELECT build_status FROM index_metadata WHERE id=1").fetchone()
        finally:
            con.close()
        assert row[0] == "complete"

    def test_metadata_index_created_at_fixed(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            row = con.execute("SELECT index_created_at FROM index_metadata WHERE id=1").fetchone()
        finally:
            con.close()
        assert row[0] == "2026-06-23T12:00:00+00:00"

    def test_metadata_manifest_sha256_length(self, built_index):
        con = sqlite3.connect(str(built_index))
        try:
            row = con.execute("SELECT corpus_manifest_sha256 FROM index_metadata WHERE id=1").fetchone()
        finally:
            con.close()
        assert len(row[0]) == 64
