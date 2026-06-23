"""Tests for corpus manifest serialization round-trip."""
import json

import pytest

from peoplenet_process_extractor.corpus.inventory import build_summary
from peoplenet_process_extractor.corpus.models import (
    CorpusManifest,
    FileEntry,
    GitInfo,
    Ln4Structure,
    RootInfo,
)
from peoplenet_process_extractor.corpus.serialization import (
    DeserializationError,
    deserialize_manifest,
    serialize_manifest,
)


def _ln4_entry() -> FileEntry:
    return FileEntry(
        path="CP/NODE STRUCTURE/O/ITEM/METHOD/M/RULES/M#R1#2020_01_01.ln4",
        sha256="a" * 64,
        size_bytes=100,
        extension=".ln4",
        source_root="CP",
        classification="structured_ln4",
        structure=Ln4Structure(
            meta4object="O",
            item_type="METHOD",
            item_name="M",
            rule_id="R1",
            rule_date="2020_01_01",
        ),
        warnings=[],
    )


def _valid_manifest() -> CorpusManifest:
    files = [_ln4_entry()]
    return CorpusManifest(
        schema_version="1.0",
        corpus_id="test-corpus",
        created_at="2026-06-23T12:00:00+00:00",
        root=RootInfo(label="corpus"),
        git=GitInfo(commit=None, dirty=None),
        included_source_roots=["CP"],
        files=files,
        summary=build_summary(files),
        warnings=[],
        errors=[],
    )


class TestRoundTrip:
    def test_full_round_trip(self):
        original = _valid_manifest()
        text = serialize_manifest(original)
        restored, errors = deserialize_manifest(text)
        assert errors == []
        assert restored.schema_version == original.schema_version
        assert restored.corpus_id == original.corpus_id
        assert restored.created_at == original.created_at
        assert restored.root.label == original.root.label
        assert restored.git.commit == original.git.commit
        assert restored.git.dirty == original.git.dirty
        assert restored.included_source_roots == original.included_source_roots
        assert len(restored.files) == len(original.files)

    def test_file_entry_round_trip(self):
        original = _valid_manifest()
        text = serialize_manifest(original)
        restored, _ = deserialize_manifest(text)
        f = restored.files[0]
        orig_f = original.files[0]
        assert f.path == orig_f.path
        assert f.sha256 == orig_f.sha256
        assert f.size_bytes == orig_f.size_bytes
        assert f.extension == orig_f.extension
        assert f.source_root == orig_f.source_root
        assert f.classification == orig_f.classification

    def test_structure_round_trip(self):
        original = _valid_manifest()
        text = serialize_manifest(original)
        restored, _ = deserialize_manifest(text)
        s = restored.files[0].structure
        orig_s = original.files[0].structure
        assert s is not None and orig_s is not None
        assert s.meta4object == orig_s.meta4object
        assert s.item_type == orig_s.item_type
        assert s.item_name == orig_s.item_name
        assert s.rule_id == orig_s.rule_id
        assert s.rule_date == orig_s.rule_date

    def test_null_structure_preserved(self):
        files = [FileEntry(
            path="outside.ln4", sha256="b" * 64, size_bytes=10,
            extension=".ln4", source_root=None, classification="unstructured_ln4",
            structure=None,
        )]
        m = CorpusManifest(
            schema_version="1.0", corpus_id="x", created_at="2026-06-23T00:00:00Z",
            root=RootInfo(label="x"), git=GitInfo(commit=None, dirty=None),
            included_source_roots=[], files=files, summary=build_summary(files),
        )
        text = serialize_manifest(m)
        restored, _ = deserialize_manifest(text)
        assert restored.files[0].structure is None

    def test_null_source_root_preserved(self):
        files = [FileEntry(
            path="root.ln4", sha256="c" * 64, size_bytes=5,
            extension=".ln4", source_root=None, classification="unstructured_ln4",
        )]
        m = CorpusManifest(
            schema_version="1.0", corpus_id="x", created_at="2026-06-23T00:00:00Z",
            root=RootInfo(label="x"), git=GitInfo(commit=None, dirty=None),
            included_source_roots=[], files=files, summary=build_summary(files),
        )
        text = serialize_manifest(m)
        restored, _ = deserialize_manifest(text)
        assert restored.files[0].source_root is None

    def test_null_git_fields_preserved(self):
        m = _valid_manifest()
        m.git = GitInfo(commit=None, dirty=None)
        text = serialize_manifest(m)
        data = json.loads(text)
        assert data["git"]["commit"] is None
        assert data["git"]["dirty"] is None

    def test_output_ends_with_newline(self):
        text = serialize_manifest(_valid_manifest())
        assert text.endswith("\n")

    def test_output_is_deterministic(self):
        m = _valid_manifest()
        assert serialize_manifest(m) == serialize_manifest(m)

    def test_summary_included(self):
        text = serialize_manifest(_valid_manifest())
        data = json.loads(text)
        assert "summary" in data
        assert data["summary"]["total_files"] == 1


class TestDeserializationErrors:
    def test_invalid_json(self):
        with pytest.raises(DeserializationError, match="Invalid JSON"):
            deserialize_manifest("not json {")

    def test_json_array_not_object(self):
        with pytest.raises(DeserializationError, match="JSON object"):
            deserialize_manifest("[]")

    def test_missing_field(self):
        with pytest.raises(DeserializationError):
            deserialize_manifest('{"schema_version": "1.0"}')

    def test_wrong_type_for_size(self):
        m = _valid_manifest()
        data = json.loads(serialize_manifest(m))
        data["files"][0]["size_bytes"] = "not-an-int"
        with pytest.raises(DeserializationError):
            deserialize_manifest(json.dumps(data))

    def test_wrong_type_for_git_dirty(self):
        m = _valid_manifest()
        data = json.loads(serialize_manifest(m))
        data["git"]["dirty"] = "yes"
        with pytest.raises(DeserializationError):
            deserialize_manifest(json.dumps(data))

    def test_unsupported_version_returns_validation_error(self):
        m = _valid_manifest()
        data = json.loads(serialize_manifest(m))
        data["schema_version"] = "9.9"
        _, errors = deserialize_manifest(json.dumps(data))
        assert any(e.code == "unsupported_schema_version" for e in errors)

    def test_invalid_hash_returns_validation_error(self):
        m = _valid_manifest()
        data = json.loads(serialize_manifest(m))
        data["files"][0]["sha256"] = "short"
        _, errors = deserialize_manifest(json.dumps(data))
        assert any(e.code == "invalid_sha256" for e in errors)
