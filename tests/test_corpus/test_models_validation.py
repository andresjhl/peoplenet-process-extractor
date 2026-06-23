"""Tests for corpus manifest validation."""


from peoplenet_process_extractor.corpus.inventory import build_summary
from peoplenet_process_extractor.corpus.models import (
    CorpusManifest,
    FileEntry,
    GitInfo,
    Ln4Structure,
    RootInfo,
)
from peoplenet_process_extractor.corpus.validation import validate_manifest


def _minimal_entry(
    path: str = "CP/NODE STRUCTURE/O/ITEM/METHOD/M/RULES/M#R1#2020_01_01.ln4",
    classification: str = "structured_ln4",
    size: int = 100,
    source_root: str | None = "CP",
    structure: Ln4Structure | None = None,
) -> FileEntry:
    if structure is None and classification == "structured_ln4":
        structure = Ln4Structure(meta4object="O", item_type="METHOD", item_name="M", rule_id="R1", rule_date="2020_01_01")
    return FileEntry(
        path=path,
        sha256="a" * 64,
        size_bytes=size,
        extension=".ln4",
        source_root=source_root,
        classification=classification,
        structure=structure,
    )


def _valid_manifest(files: list[FileEntry] | None = None) -> CorpusManifest:
    if files is None:
        files = [_minimal_entry()]
    summary = build_summary(files)
    return CorpusManifest(
        schema_version="1.0",
        corpus_id="test-corpus",
        created_at="2026-06-23T12:00:00+00:00",
        root=RootInfo(label="corpus"),
        git=GitInfo(commit=None, dirty=None),
        included_source_roots=["CP"],
        files=files,
        summary=summary,
    )


class TestSchemaVersion:
    def test_valid(self):
        m = _valid_manifest()
        assert validate_manifest(m) == []

    def test_invalid_version(self):
        m = _valid_manifest()
        m.schema_version = "2.0"
        errors = validate_manifest(m)
        assert any(e.code == "unsupported_schema_version" for e in errors)

    def test_empty_version(self):
        m = _valid_manifest()
        m.schema_version = ""
        errors = validate_manifest(m)
        assert any(e.code == "unsupported_schema_version" for e in errors)


class TestCorpusId:
    def test_empty_corpus_id(self):
        m = _valid_manifest()
        m.corpus_id = ""
        errors = validate_manifest(m)
        assert any(e.code == "empty_corpus_id" for e in errors)

    def test_whitespace_corpus_id(self):
        m = _valid_manifest()
        m.corpus_id = "   "
        errors = validate_manifest(m)
        assert any(e.code == "empty_corpus_id" for e in errors)


class TestTimestamp:
    def test_invalid_timestamp(self):
        m = _valid_manifest()
        m.created_at = "not-a-date"
        errors = validate_manifest(m)
        assert any(e.code == "invalid_created_at" for e in errors)

    def test_timestamp_without_timezone(self):
        m = _valid_manifest()
        m.created_at = "2026-06-23T12:00:00"
        errors = validate_manifest(m)
        assert any(e.code == "created_at_missing_timezone" for e in errors)

    def test_timestamp_with_z(self):
        m = _valid_manifest()
        m.created_at = "2026-06-23T12:00:00Z"
        assert validate_manifest(m) == []

    def test_timestamp_with_offset_rejected(self):
        m = _valid_manifest()
        m.created_at = "2026-06-23T14:00:00+02:00"
        errors = validate_manifest(m)
        assert any(e.code == "created_at_not_utc" for e in errors)

    def test_timestamp_negative_offset_rejected(self):
        m = _valid_manifest()
        m.created_at = "2026-06-23T07:00:00-05:00"
        errors = validate_manifest(m)
        assert any(e.code == "created_at_not_utc" for e in errors)

    def test_timestamp_utc_zero_offset_valid(self):
        m = _valid_manifest()
        m.created_at = "2026-06-23T12:00:00+00:00"
        assert validate_manifest(m) == []


class TestFilePaths:
    def test_absolute_path_unix(self):
        entry = _minimal_entry(path="/absolute/path.ln4", source_root=None, classification="unstructured_ln4", structure=None)
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "absolute_path" for e in errors)

    def test_path_traversal(self):
        entry = _minimal_entry(path="../escape.ln4", source_root=None, classification="unstructured_ln4", structure=None)
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "path_traversal" for e in errors)

    def test_backslash_in_path(self):
        entry = _minimal_entry(
            path="CP\\NODE STRUCTURE\\O\\ITEM\\METHOD\\M\\RULES\\M#R1#2020_01_01.ln4",
            classification="structured_ln4",
        )
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "backslash_in_path" for e in errors)

    def test_duplicate_path(self):
        e1 = _minimal_entry()
        e2 = _minimal_entry()
        m = _valid_manifest([e1, e2])
        m.summary = build_summary([e1, e2])
        errors = validate_manifest(m)
        assert any(e.code == "duplicate_file_path" for e in errors)

    def test_files_not_sorted(self):
        e1 = _minimal_entry(path="b.ln4", classification="unstructured_ln4", source_root=None, structure=None)
        e2 = _minimal_entry(path="a.ln4", classification="unstructured_ln4", source_root=None, structure=None)
        m = _valid_manifest([e1, e2])
        m.summary = build_summary([e1, e2])
        errors = validate_manifest(m)
        assert any(e.code == "files_not_sorted" for e in errors)


class TestHashAndSize:
    def test_invalid_hash(self):
        entry = _minimal_entry()
        entry.sha256 = "not-a-hash"
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "invalid_sha256" for e in errors)

    def test_negative_size(self):
        entry = _minimal_entry()
        entry.size_bytes = -1
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "negative_size" for e in errors)


class TestClassification:
    def test_invalid_classification(self):
        entry = _minimal_entry(classification="totally_wrong")
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "invalid_classification" for e in errors)

    def test_structured_ln4_requires_structure(self):
        entry = _minimal_entry(classification="structured_ln4")
        entry.structure = None
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "missing_structure" for e in errors)

    def test_unstructured_ln4_no_structure(self):
        entry = _minimal_entry(
            path="outside.ln4", classification="unstructured_ln4",
            source_root=None, structure=None
        )
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        assert validate_manifest(m) == []

    def test_non_structured_with_structure_is_invalid(self):
        entry = _minimal_entry(
            path="outside.ln4", classification="unstructured_ln4",
            source_root=None
        )
        entry.structure = Ln4Structure(meta4object="O", item_type="M", item_name="N")
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "unexpected_structure" for e in errors)

    def test_extension_must_be_lowercase(self):
        entry = _minimal_entry(path="outside.ln4", classification="unstructured_ln4", source_root=None, structure=None)
        entry.extension = ".LN4"
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "extension_not_lowercase" for e in errors)


class TestGitValidation:
    def test_invalid_commit_hash(self):
        m = _valid_manifest()
        m.git = GitInfo(commit="not-a-hash", dirty=False)
        errors = validate_manifest(m)
        assert any(e.code == "invalid_git_commit" for e in errors)

    def test_valid_sha1_commit(self):
        m = _valid_manifest()
        m.git = GitInfo(commit="a" * 40, dirty=False)
        assert validate_manifest(m) == []

    def test_valid_sha256_commit(self):
        m = _valid_manifest()
        m.git = GitInfo(commit="b" * 64, dirty=True)
        assert validate_manifest(m) == []

    def test_null_commit_and_dirty_valid(self):
        m = _valid_manifest()
        m.git = GitInfo(commit=None, dirty=None)
        assert validate_manifest(m) == []


class TestSummaryConsistency:
    def test_mismatch_total_files(self):
        m = _valid_manifest()
        m.summary.total_files = 999
        errors = validate_manifest(m)
        assert any(e.code == "summary_mismatch" and "total_files" in e.message for e in errors)

    def test_mismatch_total_bytes(self):
        m = _valid_manifest()
        m.summary.total_bytes = 999999
        errors = validate_manifest(m)
        assert any(e.code == "summary_mismatch" and "total_bytes" in e.message for e in errors)

    def test_mismatch_structured_files(self):
        m = _valid_manifest()
        m.summary.structured_files = 0
        errors = validate_manifest(m)
        assert any(e.code == "summary_mismatch" and "structured_files" in e.message for e in errors)

    def test_mismatch_by_classification(self):
        m = _valid_manifest()
        m.summary.by_classification = {"wrong": 1}
        errors = validate_manifest(m)
        assert any(e.code == "summary_mismatch" and "by_classification" in e.message for e in errors)


class TestIncludedSourceRoots:
    def test_duplicate_source_root(self):
        m = _valid_manifest()
        m.included_source_roots = ["CP", "CP"]
        errors = validate_manifest(m)
        assert any(e.code == "duplicate_source_root" for e in errors)

    def test_empty_string_source_root(self):
        m = _valid_manifest()
        m.included_source_roots = [""]
        errors = validate_manifest(m)
        assert any(e.code == "empty_source_root" for e in errors)


class TestExtensionPathCoherence:
    def test_extension_mismatch_ln4_vs_json(self):
        entry = _minimal_entry()
        entry.extension = ".json"
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "extension_path_mismatch" for e in errors)

    def test_extension_matches_path(self):
        entry = _minimal_entry()
        assert validate_manifest(_valid_manifest([entry])) == []

    def test_extension_empty_for_no_extension_file(self):
        entry = _minimal_entry(
            path="CP/some/file",
            classification="other_supported",
            source_root="CP",
            structure=None,
        )
        entry.extension = ""
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        assert validate_manifest(m) == []

    def test_extension_wrong_for_no_extension_file(self):
        entry = _minimal_entry(
            path="CP/some/file",
            classification="other_supported",
            source_root="CP",
            structure=None,
        )
        entry.extension = ".txt"
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "extension_path_mismatch" for e in errors)


class TestSourceRootCoherence:
    def test_root_file_with_null_source_root_valid(self):
        entry = _minimal_entry(
            path="outside.ln4",
            classification="unstructured_ln4",
            source_root=None,
            structure=None,
        )
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        assert validate_manifest(m) == []

    def test_root_file_with_non_null_source_root_invalid(self):
        entry = _minimal_entry(
            path="outside.ln4",
            classification="unstructured_ln4",
            source_root="CP",
            structure=None,
        )
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "source_root_mismatch" for e in errors)

    def test_subdir_file_source_root_must_match_first_component(self):
        entry = _minimal_entry()
        entry.source_root = "GTO"
        m = _valid_manifest([entry])
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "source_root_mismatch" for e in errors)

    def test_subdir_file_source_root_not_in_scope(self):
        entry = _minimal_entry(
            path="GTO/file.ln4",
            classification="unstructured_ln4",
            source_root="GTO",
            structure=None,
        )
        m = _valid_manifest([entry])
        m.included_source_roots = ["CP"]
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "source_root_not_in_scope" for e in errors)

    def test_subdir_file_in_scope_valid(self):
        entry = _minimal_entry()
        m = _valid_manifest([entry])
        assert validate_manifest(m) == []

    def test_empty_scope_rejects_subdir_file(self):
        """included_source_roots=[] with a non-null source_root is always invalid."""
        entry = _minimal_entry(
            path="CP/file.ln4",
            classification="unstructured_ln4",
            source_root="CP",
            structure=None,
        )
        m = _valid_manifest([entry])
        m.included_source_roots = []
        m.summary = build_summary([entry])
        errors = validate_manifest(m)
        assert any(e.code == "source_root_not_in_scope" for e in errors)
