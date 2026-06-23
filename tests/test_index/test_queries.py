"""Tests for index queries: files, elements, stats, ordering, injection safety."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.index.builder import build_index
from peoplenet_process_extractor.index.queries import query_elements, query_files, query_stats

FIXTURE_CORPUS = Path(__file__).parent.parent / "fixtures" / "index_corpus"
FIXED_NOW = datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc)


def _build_at_path(db_path: Path, tmp_path: Path) -> Path:
    """Build a valid index at an arbitrary db_path using the standard fixture corpus."""
    manifest = tmp_path / "manifest.json"
    code, msgs = create_inventory(
        corpus_root=FIXTURE_CORPUS, output_path=manifest, corpus_id="qtest", now=FIXED_NOW
    )
    assert code == 0, msgs
    code, msgs = build_index(
        corpus_root=FIXTURE_CORPUS, manifest_path=manifest, output_path=db_path, now=FIXED_NOW
    )
    assert code == 0, msgs
    return db_path


class TestQueryFiles:
    def test_no_filter_returns_all(self, built_index):
        rows = query_files(built_index)
        assert len(rows) == 7

    def test_ordered_by_path(self, built_index):
        rows = query_files(built_index)
        paths = [r.path for r in rows]
        assert paths == sorted(paths)

    def test_filter_by_classification_structured(self, built_index):
        rows = query_files(built_index, classification="structured_ln4")
        assert all(r.classification == "structured_ln4" for r in rows)
        assert len(rows) == 4

    def test_filter_by_classification_unstructured(self, built_index):
        rows = query_files(built_index, classification="unstructured_ln4")
        assert len(rows) == 1
        assert rows[0].path == "GTO/loose.ln4"

    def test_filter_by_source_root_cp(self, built_index):
        rows = query_files(built_index, source_root="CP")
        assert all(r.source_root == "CP" for r in rows)
        assert len(rows) == 3

    def test_filter_by_source_root_gto(self, built_index):
        rows = query_files(built_index, source_root="GTO")
        assert all(r.source_root == "GTO" for r in rows)
        assert len(rows) == 2

    def test_filter_by_extension(self, built_index):
        rows = query_files(built_index, extension=".ln4")
        assert all(r.extension == ".ln4" for r in rows)
        assert len(rows) == 5

    def test_filter_by_exact_path(self, built_index):
        rows = query_files(built_index, path="GTO/loose.ln4")
        assert len(rows) == 1
        assert rows[0].path == "GTO/loose.ln4"

    def test_no_results_returns_empty(self, built_index):
        rows = query_files(built_index, classification="ignored")
        assert rows == []

    def test_combined_filter(self, built_index):
        rows = query_files(built_index, source_root="CP", extension=".ln4")
        assert len(rows) == 3
        assert all(r.source_root == "CP" for r in rows)
        assert all(r.extension == ".ln4" for r in rows)

    def test_injection_treated_as_value(self, built_index):
        """SQL injection attempt in classification filter returns no rows, not an error."""
        rows = query_files(built_index, classification="structured_ln4' OR '1'='1")
        assert rows == []

    def test_single_quote_in_path(self, built_index):
        """Single quote in path value is handled safely."""
        rows = query_files(built_index, path="doesn't/exist.ln4")
        assert rows == []


class TestQueryElements:
    def test_no_filter_returns_all_structured(self, built_index):
        rows = query_elements(built_index)
        assert len(rows) == 4

    def test_ordered_by_meta4object_type_name(self, built_index):
        rows = query_elements(built_index)
        keys = [(r.meta4object, r.item_type, r.item_name) for r in rows]
        assert keys == sorted(keys)

    def test_filter_by_meta4object(self, built_index):
        rows = query_elements(built_index, meta4object="OBJ_A")
        assert all(r.meta4object == "OBJ_A" for r in rows)
        assert len(rows) == 3

    def test_filter_by_item_type(self, built_index):
        rows = query_elements(built_index, item_type="METHOD")
        assert all(r.item_type == "METHOD" for r in rows)
        assert len(rows) == 2
        assert rows[0].item_name == "METH_W"
        assert rows[1].item_name == "METH_X"

    def test_filter_by_item_name(self, built_index):
        rows = query_elements(built_index, item_name="CONC_Y")
        assert len(rows) == 1
        assert rows[0].meta4object == "OBJ_A"
        assert rows[0].item_type == "CONCEPT"

    def test_filter_by_rule_id(self, built_index):
        rows = query_elements(built_index, rule_id="R3")
        assert len(rows) == 1
        assert rows[0].item_name == "VALID_Z"

    def test_filter_by_source_root(self, built_index):
        rows = query_elements(built_index, source_root="GTO")
        assert all(r.source_root == "GTO" for r in rows)
        assert len(rows) == 1

    def test_combined_filter(self, built_index):
        rows = query_elements(built_index, meta4object="OBJ_A", item_type="CONCEPT")
        assert len(rows) == 1
        assert rows[0].item_name == "CONC_Y"

    def test_no_results(self, built_index):
        rows = query_elements(built_index, meta4object="NONEXISTENT")
        assert rows == []

    def test_injection_treated_as_value(self, built_index):
        rows = query_elements(built_index, meta4object="OBJ_A' OR '1'='1")
        assert rows == []

    def test_deterministic_order(self, built_index):
        """Two identical queries return rows in the same order."""
        rows1 = query_elements(built_index)
        rows2 = query_elements(built_index)
        assert [(r.meta4object, r.item_type, r.item_name) for r in rows1] == \
               [(r.meta4object, r.item_type, r.item_name) for r in rows2]


class TestQueryStats:
    def test_stats_total(self, built_index):
        stats = query_stats(built_index)
        assert stats.total_files == 7

    def test_stats_structured(self, built_index):
        stats = query_stats(built_index)
        assert stats.structured_files == 4

    def test_stats_unstructured(self, built_index):
        stats = query_stats(built_index)
        assert stats.unstructured_files == 1

    def test_stats_by_classification(self, built_index):
        stats = query_stats(built_index)
        assert stats.by_classification.get("structured_ln4") == 4
        assert stats.by_classification.get("unstructured_ln4") == 1
        assert stats.by_classification.get("metadata_json") == 1
        assert stats.by_classification.get("other_supported") == 1

    def test_stats_by_source_root(self, built_index):
        stats = query_stats(built_index)
        assert stats.by_source_root.get("CP") == 3
        assert stats.by_source_root.get("GTO") == 2
        # Root files (source_root=None) map to empty string key.
        assert stats.by_source_root.get("") == 2

    def test_stats_by_item_type(self, built_index):
        stats = query_stats(built_index)
        assert stats.by_item_type.get("CONCEPT") == 1
        assert stats.by_item_type.get("METHOD") == 2
        assert stats.by_item_type.get("VALIDATION") == 1


class TestSpecialPathDatabases:
    """DB paths with #, spaces, and non-ASCII must open correctly via URI encoding."""

    def test_db_path_with_hash(self, tmp_path):
        sub = tmp_path / "sub#dir"
        sub.mkdir()
        db = _build_at_path(sub / "index.sqlite", tmp_path)
        rows = query_files(db)
        assert len(rows) == 7

    def test_db_path_with_spaces(self, tmp_path):
        sub = tmp_path / "my index dir"
        sub.mkdir()
        db = _build_at_path(sub / "index.sqlite", tmp_path)
        rows = query_files(db)
        assert len(rows) == 7

    def test_db_path_with_non_ascii(self, tmp_path):
        sub = tmp_path / "índice"
        sub.mkdir()
        db = _build_at_path(sub / "index.sqlite", tmp_path)
        rows = query_files(db)
        assert len(rows) == 7

    def test_db_path_with_hash_elements(self, tmp_path):
        sub = tmp_path / "dir#one"
        sub.mkdir()
        db = _build_at_path(sub / "index.sqlite", tmp_path)
        elems = query_elements(db)
        assert len(elems) == 4

    def test_db_path_with_hash_stats(self, tmp_path):
        sub = tmp_path / "dir#two"
        sub.mkdir()
        db = _build_at_path(sub / "index.sqlite", tmp_path)
        stats = query_stats(db)
        assert stats.total_files == 7
