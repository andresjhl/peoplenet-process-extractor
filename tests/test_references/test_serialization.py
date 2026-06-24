"""Tests for serialization and deserialization of reference extractions."""
from __future__ import annotations

import json

import pytest

from peoplenet_process_extractor.references.models import (
    FORMAT,
    SCHEMA_VERSION,
    ExtractionSummary,
    FileResult,
    Generator,
    ReferenceExtraction,
    SourceRef,
)
from peoplenet_process_extractor.references.serialization import (
    DeserializationError,
    deserialize_extraction,
    serialize_extraction,
)

from .conftest import FIXED_NOW

_FAKE_SHA = "a" * 64
_IDX_SHA = "b" * 64


def _empty_extraction() -> ReferenceExtraction:
    return ReferenceExtraction(
        format=FORMAT,
        schema_version=SCHEMA_VERSION,
        generator=Generator(name="peoplenet-process-extractor", version="0.1.0"),
        created_at=FIXED_NOW.isoformat(),
        source_manifest=SourceRef(sha256=_FAKE_SHA, size_bytes=100),
        source_index=SourceRef(sha256=_IDX_SHA, size_bytes=200),
        summary=ExtractionSummary(
            files_total=0,
            files_processed=0,
            files_with_calls=0,
            calls_total=0,
            observed=0,
            partially_parsed=0,
            ambiguous=0,
            malformed=0,
            unsupported=0,
            file_errors=0,
        ),
        files=[],
    )


class TestSerialize:
    def test_trailing_newline(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        assert text.endswith("\n")

    def test_no_crlf(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        assert "\r\n" not in text

    def test_two_space_indent(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        lines = text.splitlines()
        # Second line should be indented with 2 spaces
        assert any(line.startswith("  ") for line in lines)

    def test_utf8_no_bom(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        raw = text.encode("utf-8")
        assert not raw.startswith(b"\xef\xbb\xbf")

    def test_valid_json(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        data = json.loads(text)
        assert isinstance(data, dict)

    def test_null_fields_serialized_as_null(self):
        ext = _empty_extraction()
        ext.files = [
            FileResult(
                path="test.ln4",
                source_file_id=1,
                source_file_sha256=None,
                encoding=None,
                line_ending=None,
                status="error",
                errors=[],
                references=[],
            )
        ]
        ext.summary.files_total = 1
        ext.summary.file_errors = 1
        text = serialize_extraction(ext)
        data = json.loads(text)
        assert data["files"][0]["source_file_sha256"] is None
        assert data["files"][0]["encoding"] is None
        assert data["files"][0]["line_ending"] is None

    def test_empty_lists_serialized_as_empty(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        data = json.loads(text)
        assert data["files"] == []

    def test_key_order_correct(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        data = json.loads(text)
        keys = list(data.keys())
        expected_order = [
            "format", "schema_version", "generator", "created_at",
            "source_manifest", "source_index", "summary", "files"
        ]
        assert keys == expected_order


class TestDeserialize:
    def test_round_trip(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        ext2 = deserialize_extraction(text)
        text2 = serialize_extraction(ext2)
        assert text == text2

    def test_round_trip_bytes_identical(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        ext2 = deserialize_extraction(text)
        text2 = serialize_extraction(ext2)
        assert text.encode("utf-8") == text2.encode("utf-8")

    def test_invalid_json_raises(self):
        with pytest.raises(DeserializationError):
            deserialize_extraction("not json")

    def test_wrong_top_level_raises(self):
        with pytest.raises(DeserializationError):
            deserialize_extraction("[1, 2, 3]")

    def test_missing_field_raises(self):
        data = {"format": FORMAT}  # missing many required fields
        with pytest.raises(DeserializationError):
            deserialize_extraction(json.dumps(data))

    def test_format_preserved(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        ext2 = deserialize_extraction(text)
        assert ext2.format == FORMAT

    def test_schema_version_preserved(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        ext2 = deserialize_extraction(text)
        assert ext2.schema_version == SCHEMA_VERSION

    def test_created_at_preserved(self):
        ext = _empty_extraction()
        text = serialize_extraction(ext)
        ext2 = deserialize_extraction(text)
        assert ext2.created_at == FIXED_NOW.isoformat()

    def test_null_file_fields_preserved(self):
        ext = _empty_extraction()
        ext.files = [
            FileResult(
                path="test.ln4",
                source_file_id=1,
                source_file_sha256=None,
                encoding=None,
                line_ending=None,
                status="error",
                errors=[],
                references=[],
            )
        ]
        ext.summary.files_total = 1
        ext.summary.file_errors = 1
        text = serialize_extraction(ext)
        ext2 = deserialize_extraction(text)
        assert ext2.files[0].source_file_sha256 is None
        assert ext2.files[0].encoding is None
        assert ext2.files[0].line_ending is None
