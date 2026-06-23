"""Tests for corpus inventory logic."""
import os
import sys
from pathlib import Path

import pytest

from peoplenet_process_extractor.corpus.enums import Classification
from peoplenet_process_extractor.corpus.inventory import (
    build_summary,
    classify_file,
    walk_corpus,
)
from peoplenet_process_extractor.corpus.models import FileEntry

FIXTURE_CORPUS = Path(__file__).parent.parent / "fixtures" / "corpus"


class TestClassifyFile:
    def test_structured_ln4(self):
        from peoplenet_process_extractor.corpus.models import Ln4Structure
        structure = Ln4Structure(meta4object="O", item_type="METHOD", item_name="M")
        assert classify_file("CP/NODE STRUCTURE/O/ITEM/METHOD/M/RULES/M#R1#2020.ln4", structure) == Classification.STRUCTURED_LN4

    def test_unstructured_ln4_no_structure(self):
        assert classify_file("outside.ln4", None) == Classification.UNSTRUCTURED_LN4

    def test_metadata_json(self):
        assert classify_file("metadata.json", None) == Classification.METADATA_JSON

    def test_metadata_json_in_subdirectory(self):
        # metadata.json inside a folder is also classified as metadata_json
        assert classify_file("CP/metadata.json", None) == Classification.METADATA_JSON

    def test_other_json(self):
        assert classify_file("config.json", None) == Classification.OTHER_SUPPORTED

    def test_binary_file(self):
        assert classify_file("small.bin", None) == Classification.OTHER_SUPPORTED

    def test_ignored_pyc(self):
        assert classify_file("module.pyc", None) == Classification.IGNORED

    def test_ignored_db(self):
        assert classify_file("index.db", None) == Classification.IGNORED

    def test_ignored_log(self):
        assert classify_file("app.log", None) == Classification.IGNORED

    def test_ignored_tmp(self):
        assert classify_file("file.tmp", None) == Classification.IGNORED

    def test_no_extension_file(self):
        assert classify_file("Makefile", None) == Classification.OTHER_SUPPORTED


class TestBuildSummary:
    def _entry(self, path, classification, size=100, source_root="CP"):
        return FileEntry(
            path=path,
            sha256="a" * 64,
            size_bytes=size,
            extension=".ln4",
            source_root=source_root,
            classification=classification,
        )

    def test_empty(self):
        s = build_summary([])
        assert s.total_files == 0
        assert s.total_bytes == 0
        assert s.structured_files == 0
        assert s.unstructured_files == 0
        assert s.by_source_root == {}
        assert s.by_extension == {}
        assert s.by_classification == {}

    def test_counts(self):
        entries = [
            self._entry("a.ln4", "structured_ln4", size=200),
            self._entry("b.ln4", "unstructured_ln4", size=300, source_root=None),
        ]
        entries[1].extension = ".ln4"
        s = build_summary(entries)
        assert s.total_files == 2
        assert s.total_bytes == 500
        assert s.structured_files == 1
        assert s.unstructured_files == 1

    def test_source_root_null_key(self):
        e = FileEntry(
            path="file.ln4",
            sha256="a" * 64,
            size_bytes=10,
            extension=".ln4",
            source_root=None,
            classification="unstructured_ln4",
        )
        s = build_summary([e])
        assert "" in s.by_source_root
        assert s.by_source_root[""] == 1

    def test_ignored_counts_in_total(self):
        e = FileEntry(
            path="junk.db",
            sha256="b" * 64,
            size_bytes=50,
            extension=".db",
            source_root="CP",
            classification="ignored",
        )
        s = build_summary([e])
        assert s.total_files == 1
        assert s.structured_files == 0
        assert s.unstructured_files == 0

    def test_by_extension_sorted(self):
        entries = [
            FileEntry(path="b.ln4", sha256="a" * 64, size_bytes=1, extension=".ln4", source_root="CP", classification="structured_ln4"),
            FileEntry(path="a.json", sha256="b" * 64, size_bytes=2, extension=".json", source_root="CP", classification="metadata_json"),
        ]
        s = build_summary(entries)
        keys = list(s.by_extension.keys())
        assert keys == sorted(keys)

    def test_by_classification_sorted(self):
        entries = [
            FileEntry(path="b.ln4", sha256="a" * 64, size_bytes=1, extension=".ln4", source_root="CP", classification="unstructured_ln4"),
            FileEntry(path="a.ln4", sha256="b" * 64, size_bytes=2, extension=".ln4", source_root="CP", classification="structured_ln4"),
        ]
        s = build_summary(entries)
        keys = list(s.by_classification.keys())
        assert keys == sorted(keys)


class TestWalkCorpus:
    def test_full_walk(self):
        entries, warnings, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        paths = [e.path for e in entries]
        # Should find structured files in CP, GTO, UNKNOWN_ROOT
        assert any("CP/" in p for p in paths)
        assert any("GTO/" in p for p in paths)
        assert any("UNKNOWN_ROOT/" in p for p in paths)
        # Should find files at corpus root
        assert any("outside_structure.ln4" == p for p in paths)

    def test_walk_sorted(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        paths = [e.path for e in entries]
        assert paths == sorted(paths)

    def test_no_absolute_paths(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        for e in entries:
            assert not e.path.startswith("/")
            assert not (len(e.path) >= 2 and e.path[1] == ":")

    def test_paths_use_forward_slashes(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        for e in entries:
            assert "\\" not in e.path

    def test_source_root_filter_cp_only(self):
        entries, warnings, errors = walk_corpus(FIXTURE_CORPUS, ["CP"])
        assert errors == []
        assert all(e.source_root == "CP" for e in entries), (
            "Expected all entries to have source_root='CP' when filter is active"
        )

    def test_root_files_excluded_when_filter_active(self):
        entries_all, _, errors_all = walk_corpus(FIXTURE_CORPUS, None)
        assert errors_all == []
        entries_filtered, _, errors_filtered = walk_corpus(FIXTURE_CORPUS, ["CP"])
        assert errors_filtered == []
        root_files_in_all = [e for e in entries_all if e.source_root is None]
        root_files_in_filtered = [e for e in entries_filtered if e.source_root is None]
        assert len(root_files_in_all) > 0, "Fixture must have files at corpus root"
        assert len(root_files_in_filtered) == 0

    def test_root_files_included_without_filter(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        root_files = [e for e in entries if e.source_root is None]
        assert len(root_files) > 0

    def test_source_root_filter_nonexistent(self):
        entries, warnings, errors = walk_corpus(FIXTURE_CORPUS, ["NONEXISTENT_ROOT"])
        assert errors
        assert any("NONEXISTENT_ROOT" in err for err in errors)
        assert entries == []

    def test_structured_ln4_has_structure(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, ["CP"])
        assert errors == []
        structured = [e for e in entries if e.classification == Classification.STRUCTURED_LN4.value]
        for e in structured:
            assert e.structure is not None

    def test_unstructured_ln4_no_structure(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        unstructured = [e for e in entries if e.classification == Classification.UNSTRUCTURED_LN4.value]
        for e in unstructured:
            assert e.structure is None

    def test_outside_structure_file(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        outside = next((e for e in entries if e.path == "outside_structure.ln4"), None)
        assert outside is not None
        assert outside.source_root is None
        assert outside.classification == Classification.UNSTRUCTURED_LN4.value

    def test_metadata_json_classified(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        meta = next((e for e in entries if e.path == "metadata.json"), None)
        assert meta is not None
        assert meta.classification == Classification.METADATA_JSON.value

    def test_binary_file_other_supported(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        binary = next((e for e in entries if e.path == "small.bin"), None)
        assert binary is not None
        assert binary.classification == Classification.OTHER_SUPPORTED.value

    def test_file_with_spaces_in_name(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        spaced = next((e for e in entries if "name with spaces" in e.path), None)
        assert spaced is not None

    def test_hash_is_sha256_hex(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        import re
        sha256_re = re.compile(r"^[0-9a-f]{64}$")
        for e in entries:
            assert sha256_re.match(e.sha256), f"Invalid hash for {e.path}: {e.sha256}"

    def test_size_matches_actual_file(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, None)
        assert errors == []
        for e in entries:
            abs_path = FIXTURE_CORPUS / e.path.replace("/", os.sep)
            expected = abs_path.stat().st_size
            assert e.size_bytes == expected, f"Size mismatch for {e.path}"

    def test_empty_corpus(self, tmp_path):
        entries, warnings, errors = walk_corpus(tmp_path, None)
        assert errors == []
        assert entries == []

    @pytest.mark.skipif(sys.platform != "win32" or os.name != "nt", reason="Symlink creation may require privileges")
    def test_symlink_not_followed(self, tmp_path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "file.ln4").write_text("content")
        link = tmp_path / "link_dir"
        try:
            link.symlink_to(real_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Cannot create symlinks in this environment")
        entries, warnings, errors = walk_corpus(tmp_path, None)
        assert not any("link_dir" in e.path for e in entries)
        assert any("link_dir" in w for w in warnings)

    def test_skip_pycache(self, tmp_path):
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "module.cpython-312.pyc").write_bytes(b"bytecode")
        (tmp_path / "valid.ln4").write_text("valid")
        entries, _, errors = walk_corpus(tmp_path, None)
        assert errors == []
        assert not any("__pycache__" in e.path for e in entries)

    def test_skip_git_dir(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main")
        (tmp_path / "valid.ln4").write_text("valid")
        entries, _, errors = walk_corpus(tmp_path, None)
        assert errors == []
        assert not any(".git" in e.path for e in entries)

    def test_deterministic_across_calls(self):
        entries1, _, _ = walk_corpus(FIXTURE_CORPUS, None)
        entries2, _, _ = walk_corpus(FIXTURE_CORPUS, None)
        assert [e.path for e in entries1] == [e.path for e in entries2]
        assert [e.sha256 for e in entries1] == [e.sha256 for e in entries2]

    def test_incomplete_rule_name_warns(self):
        entries, _, errors = walk_corpus(FIXTURE_CORPUS, ["CP"])
        assert errors == []
        incomplete = [e for e in entries if "INCOMPLETE_METHOD" in e.path]
        # Still structured_ln4 (path matches) but with warning about rule name
        for e in incomplete:
            assert e.classification == Classification.STRUCTURED_LN4.value
            assert e.structure is not None
            assert e.structure.rule_id is None
            assert len(e.warnings) > 0

    def test_crlf_file_different_hash_than_lf(self, tmp_path):
        lf_file = tmp_path / "lf.ln4"
        crlf_file = tmp_path / "crlf.ln4"
        lf_file.write_bytes(b"line1\nline2\n")
        crlf_file.write_bytes(b"line1\r\nline2\r\n")
        entries, _, _ = walk_corpus(tmp_path, None)
        hashes = {e.path: e.sha256 for e in entries}
        assert hashes["lf.ln4"] != hashes["crlf.ln4"]
