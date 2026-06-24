"""Tests for validation and verification of reference extractions."""
from __future__ import annotations

import json


from peoplenet_process_extractor.references.models import (
    FORMAT,
    SCHEMA_VERSION,
    ExtractionSummary,
    FileResult,
    Generator,
    Reference,
    ReferenceExtraction,
    SourceRef,
)
from peoplenet_process_extractor.references.validation import (
    validate_extraction_model,
    verify_extraction,
)

from .conftest import FIXED_NOW


def _minimal_reference(sha256: str, start: int = 0, end: int = 20) -> Reference:
    return Reference(
        id=f"ref:{sha256}:{start}:{end}",
        kind="call",
        function_name="Call",
        status="observed",
        source_file_id=1,
        path="CP/test.ln4",
        source_file_sha256=sha256,
        start_offset=start,
        end_offset=end,
        line_start=1,
        column_start=1,
        line_end=1,
        column_end=20,
        raw_expression='Call(x, "Y")',
        raw_arguments='x, "Y"',
        arguments=[],
        parser_rule="ln4_call_v1",
        diagnostics=[],
    )


_FAKE_SHA = "a" * 64
_IDX_SHA = "b" * 64


def _minimal_extraction(files=None) -> ReferenceExtraction:
    if files is None:
        files = []
    files_processed = sum(1 for f in files if f.status == "processed")
    file_errors = sum(1 for f in files if f.status == "error")
    all_refs = [r for f in files for r in f.references]
    files_with_calls = sum(1 for f in files if f.status == "processed" and f.references)
    observed = sum(1 for r in all_refs if r.status == "observed")
    malformed = sum(1 for r in all_refs if r.status == "malformed")

    return ReferenceExtraction(
        format=FORMAT,
        schema_version=SCHEMA_VERSION,
        generator=Generator(name="peoplenet-process-extractor", version="0.1.0"),
        created_at=FIXED_NOW.isoformat(),
        source_manifest=SourceRef(sha256=_FAKE_SHA, size_bytes=100),
        source_index=SourceRef(sha256=_IDX_SHA, size_bytes=200),
        summary=ExtractionSummary(
            files_total=len(files),
            files_processed=files_processed,
            files_with_calls=files_with_calls,
            calls_total=len(all_refs),
            observed=observed,
            partially_parsed=0,
            ambiguous=0,
            malformed=malformed,
            unsupported=0,
            file_errors=file_errors,
        ),
        files=files,
    )


class TestValidateExtractionModel:
    def test_valid_empty_extraction(self):
        extraction = _minimal_extraction()
        errors = validate_extraction_model(extraction)
        assert errors == []

    def test_wrong_format(self):
        extraction = _minimal_extraction()
        extraction.format = "wrong-format"
        errors = validate_extraction_model(extraction)
        assert any("format" in e for e in errors)

    def test_wrong_schema_version(self):
        extraction = _minimal_extraction()
        extraction.schema_version = 999
        errors = validate_extraction_model(extraction)
        assert any("schema_version" in e for e in errors)

    def test_empty_generator_name(self):
        extraction = _minimal_extraction()
        extraction.generator.name = ""
        errors = validate_extraction_model(extraction)
        assert any("generator.name" in e for e in errors)

    def test_empty_generator_version(self):
        extraction = _minimal_extraction()
        extraction.generator.version = ""
        errors = validate_extraction_model(extraction)
        assert any("generator.version" in e for e in errors)

    def test_valid_with_references(self):
        ref = _minimal_reference(_FAKE_SHA, 0, 12)
        ref.raw_expression = 'Call(x, "Y")'
        file_result = FileResult(
            path="CP/test.ln4",
            source_file_id=1,
            source_file_sha256=_FAKE_SHA,
            encoding="utf-8",
            line_ending="lf",
            status="processed",
            references=[ref],
        )
        extraction = _minimal_extraction([file_result])
        errors = validate_extraction_model(extraction)
        assert errors == []

    def test_summary_files_total_mismatch(self):
        extraction = _minimal_extraction()
        extraction.summary.files_total = 99
        errors = validate_extraction_model(extraction)
        assert any("files_total" in e for e in errors)

    def test_summary_calls_total_mismatch(self):
        ref = _minimal_reference(_FAKE_SHA, 0, 12)
        file_result = FileResult(
            path="CP/test.ln4",
            source_file_id=1,
            source_file_sha256=_FAKE_SHA,
            encoding="utf-8",
            line_ending="lf",
            status="processed",
            references=[ref],
        )
        extraction = _minimal_extraction([file_result])
        extraction.summary.calls_total = 99
        errors = validate_extraction_model(extraction)
        assert any("calls_total" in e for e in errors)

    def test_invalid_reference_status(self):
        ref = _minimal_reference(_FAKE_SHA, 0, 12)
        ref.status = "invalid_status"
        file_result = FileResult(
            path="CP/test.ln4",
            source_file_id=1,
            source_file_sha256=_FAKE_SHA,
            encoding="utf-8",
            line_ending="lf",
            status="processed",
            references=[ref],
        )
        extraction = _minimal_extraction([file_result])
        # Fix summary to match
        extraction.summary.files_total = 1
        extraction.summary.files_processed = 1
        extraction.summary.files_with_calls = 1
        extraction.summary.calls_total = 1
        errors = validate_extraction_model(extraction)
        assert any("status" in e for e in errors)

    def test_invalid_reference_kind(self):
        ref = _minimal_reference(_FAKE_SHA, 0, 12)
        ref.kind = "unknown"
        file_result = FileResult(
            path="CP/test.ln4",
            source_file_id=1,
            source_file_sha256=_FAKE_SHA,
            encoding="utf-8",
            line_ending="lf",
            status="processed",
            references=[ref],
        )
        extraction = _minimal_extraction([file_result])
        extraction.summary.files_total = 1
        extraction.summary.files_processed = 1
        extraction.summary.files_with_calls = 1
        extraction.summary.calls_total = 1
        errors = validate_extraction_model(extraction)
        assert any("kind" in e for e in errors)

    def test_duplicate_reference_id(self):
        ref1 = _minimal_reference(_FAKE_SHA, 0, 12)
        ref2 = _minimal_reference(_FAKE_SHA, 0, 12)  # same id
        file_result = FileResult(
            path="CP/test.ln4",
            source_file_id=1,
            source_file_sha256=_FAKE_SHA,
            encoding="utf-8",
            line_ending="lf",
            status="processed",
            references=[ref1, ref2],
        )
        extraction = _minimal_extraction([file_result])
        extraction.summary.files_total = 1
        extraction.summary.files_processed = 1
        extraction.summary.files_with_calls = 1
        extraction.summary.calls_total = 2
        extraction.summary.observed = 2
        errors = validate_extraction_model(extraction)
        assert any("Duplicate" in e or "duplicate" in e.lower() for e in errors)

    def test_negative_start_offset(self):
        ref = _minimal_reference(_FAKE_SHA, -1, 10)
        ref.id = f"ref:{_FAKE_SHA}:-1:10"
        file_result = FileResult(
            path="CP/test.ln4",
            source_file_id=1,
            source_file_sha256=_FAKE_SHA,
            encoding="utf-8",
            line_ending="lf",
            status="processed",
            references=[ref],
        )
        extraction = _minimal_extraction([file_result])
        extraction.summary.files_total = 1
        extraction.summary.files_processed = 1
        extraction.summary.files_with_calls = 1
        extraction.summary.calls_total = 1
        errors = validate_extraction_model(extraction)
        assert any("start_offset" in e and "negative" in e for e in errors)

    def test_start_offset_gte_end_offset(self):
        ref = _minimal_reference(_FAKE_SHA, 10, 5)
        ref.id = f"ref:{_FAKE_SHA}:10:5"
        file_result = FileResult(
            path="CP/test.ln4",
            source_file_id=1,
            source_file_sha256=_FAKE_SHA,
            encoding="utf-8",
            line_ending="lf",
            status="processed",
            references=[ref],
        )
        extraction = _minimal_extraction([file_result])
        extraction.summary.files_total = 1
        extraction.summary.files_processed = 1
        extraction.summary.files_with_calls = 1
        extraction.summary.calls_total = 1
        errors = validate_extraction_model(extraction)
        assert any("start_offset" in e and "end_offset" in e for e in errors)

    def test_id_formula_mismatch(self):
        ref = _minimal_reference(_FAKE_SHA, 0, 12)
        ref.id = "ref:wronghash:0:12"
        file_result = FileResult(
            path="CP/test.ln4",
            source_file_id=1,
            source_file_sha256=_FAKE_SHA,
            encoding="utf-8",
            line_ending="lf",
            status="processed",
            references=[ref],
        )
        extraction = _minimal_extraction([file_result])
        extraction.summary.files_total = 1
        extraction.summary.files_processed = 1
        extraction.summary.files_with_calls = 1
        extraction.summary.calls_total = 1
        errors = validate_extraction_model(extraction)
        assert any("id" in e.lower() and "mismatch" in e.lower() for e in errors)

    def test_files_not_sorted_by_path(self):
        f1 = FileResult(
            path="CP/z.ln4",
            source_file_id=2,
            source_file_sha256=_FAKE_SHA,
            encoding="utf-8",
            line_ending="lf",
            status="processed",
        )
        f2 = FileResult(
            path="CP/a.ln4",
            source_file_id=1,
            source_file_sha256=_FAKE_SHA,
            encoding="utf-8",
            line_ending="lf",
            status="processed",
        )
        extraction = _minimal_extraction([f1, f2])
        errors = validate_extraction_model(extraction)
        assert any("sorted" in e for e in errors)


class TestVerifyExtraction:
    def test_valid_extraction_verifies(
        self,
        non_git_corpus,
        corpus_manifest,
        built_index,
        built_extraction,
    ):
        code, msgs = verify_extraction(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            extraction_path=built_extraction,
        )
        assert code == 0, msgs

    def test_tampered_manifest_sha256_fails(
        self,
        non_git_corpus,
        corpus_manifest,
        built_index,
        built_extraction,
        tmp_path,
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["source_manifest"]["sha256"] = "a" * 64
        tampered = tmp_path / "tampered.json"
        tampered.write_bytes(json.dumps(data).encode("utf-8"))

        code, msgs = verify_extraction(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            extraction_path=tampered,
        )
        assert code != 0

    def test_tampered_index_sha256_fails(
        self,
        non_git_corpus,
        corpus_manifest,
        built_index,
        built_extraction,
        tmp_path,
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["source_index"]["sha256"] = "b" * 64
        tampered = tmp_path / "tampered.json"
        tampered.write_bytes(json.dumps(data).encode("utf-8"))

        code, msgs = verify_extraction(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            extraction_path=tampered,
        )
        assert code != 0

    def test_tampered_raw_expression_fails(
        self,
        non_git_corpus,
        corpus_manifest,
        built_index,
        built_extraction,
        tmp_path,
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        # Find a file with references
        for f in data["files"]:
            if f["references"]:
                f["references"][0]["raw_expression"] = "TAMPERED"
                break
        tampered = tmp_path / "tampered.json"
        tampered.write_bytes(json.dumps(data).encode("utf-8"))

        code, msgs = verify_extraction(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            extraction_path=tampered,
        )
        assert code != 0

    def test_wrong_start_offset_fails(
        self,
        non_git_corpus,
        corpus_manifest,
        built_index,
        built_extraction,
        tmp_path,
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        for f in data["files"]:
            if f["references"]:
                f["references"][0]["start_offset"] = 9999
                break
        tampered = tmp_path / "tampered.json"
        tampered.write_bytes(json.dumps(data).encode("utf-8"))

        code, msgs = verify_extraction(
            corpus_root=non_git_corpus,
            manifest_path=corpus_manifest,
            index_path=built_index,
            extraction_path=tampered,
        )
        assert code != 0


# ---------------------------------------------------------------------------
# Helpers shared by exhaustive tests
# ---------------------------------------------------------------------------

def _first_file_with_refs_and_args(data: dict) -> tuple[int, int, int]:
    """Return (file_idx, ref_idx, 0) of the first reference that has arguments."""
    for fi, f in enumerate(data["files"]):
        for ri, r in enumerate(f["references"]):
            if r["arguments"]:
                return fi, ri, 0
    raise ValueError("No reference with arguments found in fixture")


def _first_file_with_multiple_refs(data: dict) -> int | None:
    """Return the index of the first file with >= 2 references."""
    for fi, f in enumerate(data["files"]):
        if len(f["references"]) >= 2:
            return fi
    return None


def _tamper_and_verify(
    data: dict,
    tmp_path: object,
    non_git_corpus: object,
    corpus_manifest: object,
    built_index: object,
) -> tuple[int, list[str]]:
    import pathlib
    p = pathlib.Path(str(tmp_path)) / "tampered.json"
    p.write_bytes(json.dumps(data).encode("utf-8"))
    return verify_extraction(
        corpus_root=non_git_corpus,
        manifest_path=corpus_manifest,
        index_path=built_index,
        extraction_path=p,
    )


class TestVerifyExhaustiveFieldTampering:
    """
    One test per field at file/reference/argument level.
    Each test mutates exactly one field and asserts that verify detects it.
    """

    # ---- File-level fields ----

    def test_file_encoding_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        orig = data["files"][fi]["encoding"]
        data["files"][fi]["encoding"] = "utf-8-bom" if orig == "utf-8" else "utf-8"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_file_line_ending_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        orig = data["files"][fi]["line_ending"]
        data["files"][fi]["line_ending"] = "crlf" if orig == "lf" else "lf"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_file_source_file_sha256_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        data["files"][fi]["source_file_sha256"] = "a" * 64
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    # ---- Reference-level fields ----

    def test_ref_raw_arguments_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        data["files"][fi]["references"][ri]["raw_arguments"] = "TAMPERED"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_ref_line_end_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        data["files"][fi]["references"][ri]["line_end"] = 9999
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_ref_column_end_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        data["files"][fi]["references"][ri]["column_end"] = 9999
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_ref_source_file_id_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        orig = data["files"][fi]["references"][ri]["source_file_id"]
        data["files"][fi]["references"][ri]["source_file_id"] = orig + 9999
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_ref_path_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        data["files"][fi]["references"][ri]["path"] = "TAMPERED/PATH.ln4"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_ref_status_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        orig = data["files"][fi]["references"][ri]["status"]
        data["files"][fi]["references"][ri]["status"] = (
            "malformed" if orig == "observed" else "observed"
        )
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_ref_diagnostics_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        orig = data["files"][fi]["references"][ri]["diagnostics"]
        data["files"][fi]["references"][ri]["diagnostics"] = (
            [] if orig else ["unclosed_parenthesis"]
        )
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_ref_parser_rule_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        data["files"][fi]["references"][ri]["parser_rule"] = "TAMPERED_RULE"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_ref_function_name_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        data["files"][fi]["references"][ri]["function_name"] = "TAMPERED"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_ref_kind_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        data["files"][fi]["references"][ri]["kind"] = "TAMPERED"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    # ---- Argument-level fields ----

    def test_arg_raw_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        data["files"][fi]["references"][ri]["arguments"][ai]["raw"] = "TAMPERED"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_arg_kind_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        orig = data["files"][fi]["references"][ri]["arguments"][ai]["kind"]
        data["files"][fi]["references"][ri]["arguments"][ai]["kind"] = (
            "expression" if orig != "expression" else "identifier"
        )
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_arg_literal_value_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi = ri = ai = None
        for _fi, f in enumerate(data["files"]):
            for _ri, r in enumerate(f["references"]):
                for _ai, a in enumerate(r["arguments"]):
                    if a["kind"] == "string_literal":
                        fi, ri, ai = _fi, _ri, _ai
                        break
                if fi is not None:
                    break
            if fi is not None:
                break
        if fi is None:
            import pytest
            pytest.skip("No string_literal argument found in fixture")
        data["files"][fi]["references"][ri]["arguments"][ai]["literal_value"] = "TAMPERED"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_arg_position_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        orig = data["files"][fi]["references"][ri]["arguments"][ai]["position"]
        data["files"][fi]["references"][ri]["arguments"][ai]["position"] = orig + 99
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_arg_status_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi, ri, ai = _first_file_with_refs_and_args(data)
        orig = data["files"][fi]["references"][ri]["arguments"][ai]["status"]
        data["files"][fi]["references"][ri]["arguments"][ai]["status"] = (
            "unparsed" if orig == "parsed" else "parsed"
        )
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs


class TestVerifyRemovedAddedReferences:
    """
    Verify detects when a reference was removed from the artifact or
    a spurious reference was injected.
    """

    def test_removed_reference_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        """Pop one reference from a multi-ref file; verify must detect the missing ref."""
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi = _first_file_with_multiple_refs(data)
        if fi is None:
            import pytest
            pytest.skip("No file with multiple references in fixture")
        removed = data["files"][fi]["references"].pop()
        status = removed["status"]
        data["summary"]["calls_total"] -= 1
        data["summary"][status] = data["summary"].get(status, 1) - 1
        if not data["files"][fi]["references"]:
            data["summary"]["files_with_calls"] -= 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_added_reference_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        """Inject a spurious reference into the artifact; verify must detect the extra ref."""
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fi = None
        for _fi, f in enumerate(data["files"]):
            if f["references"]:
                fi = _fi
                break
        if fi is None:
            import pytest
            pytest.skip("No file with references in fixture")
        original = data["files"][fi]["references"][-1]
        fake_start = original["end_offset"] + 1000
        fake_end = fake_start + len(original["raw_expression"])
        fake_sha = original["source_file_sha256"]
        spurious = dict(original)
        spurious["start_offset"] = fake_start
        spurious["end_offset"] = fake_end
        spurious["id"] = f"ref:{fake_sha}:{fake_start}:{fake_end}"
        data["files"][fi]["references"].append(spurious)
        status = spurious["status"]
        data["summary"]["calls_total"] += 1
        data["summary"][status] = data["summary"].get(status, 0) + 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs


class TestVerifyRootFieldTampering:
    """
    One test per root-level field that verify must now compare.

    Each test mutates exactly one root field and asserts that verify detects it.
    """

    def test_generator_name_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["generator"]["name"] = "TAMPERED-GENERATOR"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_generator_version_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["generator"]["version"] = "9.9.9-tampered"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_created_at_invalid_format_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["created_at"] = "not-a-date"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_created_at_no_timezone_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["created_at"] = "2026-06-24T12:00:00"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_created_at_non_utc_offset_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["created_at"] = "2026-06-24T12:00:00+05:00"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_created_at_z_suffix_accepted(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        """Z suffix in a stored artifact is accepted: fromisoformat() normalizes Z and
        +00:00 to the same UTC datetime.  Both pass the UTC check in _parse_utc_created_at."""
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        original = data["created_at"]
        assert original.endswith("+00:00"), f"Fixture created_at not in +00:00 form: {original}"
        data["created_at"] = original[:-6] + "Z"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code == 0, f"Z suffix should be accepted as equivalent to +00:00: {msgs}"

    def test_created_at_different_valid_utc_is_accepted(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        """A different but syntactically valid UTC timestamp passes format validation.
        created_at records when the extractor ran; it is independent of manifest.created_at.
        Integrity against external tampering is guaranteed by the artifact SHA-256 stored
        in run-manifest-v1, not by verify_extraction()."""
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["created_at"] = "2030-01-01T00:00:00+00:00"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code == 0, (
            "A valid UTC timestamp independent of manifest.created_at must be accepted; "
            f"got: {msgs}"
        )

    def test_source_manifest_size_bytes_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["source_manifest"]["size_bytes"] = 9999999
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_source_index_size_bytes_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["source_index"]["size_bytes"] = 9999999
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_summary_files_total_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["summary"]["files_total"] += 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_summary_files_processed_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["summary"]["files_processed"] += 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_summary_files_with_calls_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["summary"]["files_with_calls"] += 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_summary_calls_total_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["summary"]["calls_total"] += 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_summary_observed_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["summary"]["observed"] += 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_summary_partially_parsed_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["summary"]["partially_parsed"] += 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_summary_ambiguous_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["summary"]["ambiguous"] += 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_summary_malformed_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["summary"]["malformed"] += 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_summary_unsupported_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["summary"]["unsupported"] += 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_summary_file_errors_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["summary"]["file_errors"] += 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs


class TestVerifyFileLevelTampering:
    """
    Tests that verify detects tampering of file-level fields:
    source_file_id, status, errors, file count, file order.
    """

    def test_file_source_file_id_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["files"][0]["source_file_id"] += 9999
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_file_status_tampered_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        for f in data["files"]:
            if f["status"] == "processed":
                f["status"] = "error"
                break
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_file_errors_injected_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        """Inject a fake error entry into a processed file; verify must detect the mismatch."""
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        for f in data["files"]:
            if f["status"] == "processed":
                f["errors"] = [{"code": "file_not_found", "message": "injected", "evidence": None}]
                break
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_file_removed_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        """Remove one file from the extraction; verify must detect the missing file."""
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        if len(data["files"]) < 2:
            import pytest
            pytest.skip("Need at least 2 files to test removal")
        data["files"].pop(0)
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_file_extra_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        """Inject a file path not in the index; verify must detect the extra file."""
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        fake = {
            "path": "ZZZZ_FAKE/injected.ln4",
            "source_file_id": 99999,
            "source_file_sha256": "a" * 64,
            "encoding": "utf-8",
            "line_ending": "lf",
            "status": "processed",
            "errors": [],
            "references": [],
        }
        data["files"].append(fake)
        data["summary"]["files_total"] += 1
        data["summary"]["files_processed"] += 1
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs

    def test_files_order_swapped_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        """Swap two files out of sort order; verify must detect the ordering violation."""
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        if len(data["files"]) < 2:
            import pytest
            pytest.skip("Need at least 2 files to test order swap")
        data["files"][0], data["files"][1] = data["files"][1], data["files"][0]
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs


class TestVerifyCreatedAtSemantics:
    """
    created_at records when the extractor ran; it is independent of manifest.created_at.

    verify_extraction() only checks that created_at is a valid UTC ISO-8601 timestamp
    (catches format errors and non-UTC offsets).  It does NOT compare created_at against
    the manifest or any other external timestamp because:

    * manifest.created_at and extraction.created_at represent distinct events in the
      pipeline (corpus snapshot vs. extractor run) and legitimately differ.
    * Integrity against external tampering of the entire artifact is guaranteed by
      recording the artifact's SHA-256 in run-manifest-v1, not by verify_extraction().
    """

    def test_extraction_after_manifest_is_valid(self, non_git_corpus, tmp_path):
        """An extraction built later than the manifest (different created_at) must pass."""
        from datetime import timedelta
        from peoplenet_process_extractor.corpus.service import create_inventory
        from peoplenet_process_extractor.index.builder import build_index
        from peoplenet_process_extractor.references.extraction import extract_references
        from peoplenet_process_extractor.references.validation import verify_extraction
        from .conftest import FIXED_NOW

        manifest = tmp_path / "manifest.json"
        create_inventory(
            corpus_root=non_git_corpus, output_path=manifest,
            corpus_id="x", now=FIXED_NOW,
        )
        db = tmp_path / "index.sqlite"
        build_index(
            corpus_root=non_git_corpus, manifest_path=manifest,
            output_path=db, now=FIXED_NOW,
        )
        # Build extraction 30 days after the manifest — a legitimate re-run
        later = FIXED_NOW + timedelta(days=30)
        out = tmp_path / "extraction.json"
        extract_references(
            corpus_root=non_git_corpus, manifest_path=manifest,
            index_path=db, output_path=out, now=later,
        )

        code, msgs = verify_extraction(
            corpus_root=non_git_corpus, manifest_path=manifest,
            index_path=db, extraction_path=out,
        )
        assert code == 0, (
            "Extraction created after the manifest must be valid; "
            f"manifest.created_at={FIXED_NOW.isoformat()!r}, "
            f"extraction.created_at={later.isoformat()!r}; msgs={msgs}"
        )

    def test_created_at_no_dependency_on_manifest_timestamp(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        """Replacing created_at with any other valid UTC timestamp passes.
        The value is self-consistent (format OK, UTC OK) and independent of manifest."""
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["created_at"] = "2030-01-01T00:00:00+00:00"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code == 0, (
            "Any valid UTC created_at must be accepted independent of manifest.created_at; "
            f"msgs={msgs}"
        )

    def test_created_at_z_equivalent_to_plus00(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        """Z and +00:00 representing the same instant are both accepted."""
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        original = data["created_at"]
        assert original.endswith("+00:00")
        data["created_at"] = original[:-6] + "Z"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code == 0, f"Z suffix must be accepted: {msgs}"

    def test_created_at_no_timezone_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["created_at"] = "2026-06-24T12:00:00"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs
        assert any("created_at" in m for m in msgs)

    def test_created_at_non_utc_offset_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["created_at"] = "2026-06-24T14:00:00+02:00"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs
        assert any("created_at" in m for m in msgs)

    def test_created_at_invalid_format_fails(
        self, non_git_corpus, corpus_manifest, built_index, built_extraction, tmp_path
    ):
        data = json.loads(built_extraction.read_text(encoding="utf-8"))
        data["created_at"] = "not-a-date"
        code, msgs = _tamper_and_verify(data, tmp_path, non_git_corpus, corpus_manifest, built_index)
        assert code != 0, msgs
        assert any("created_at" in m for m in msgs)

    def test_reextraction_with_same_created_at_produces_same_model(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        """Re-extracting with the same now produces a byte-identical artifact."""
        from peoplenet_process_extractor.references.extraction import extract_references
        from .conftest import FIXED_NOW

        out1 = tmp_path / "ext1.json"
        out2 = tmp_path / "ext2.json"
        extract_references(
            corpus_root=non_git_corpus, manifest_path=corpus_manifest,
            index_path=built_index, output_path=out1, now=FIXED_NOW,
        )
        extract_references(
            corpus_root=non_git_corpus, manifest_path=corpus_manifest,
            index_path=built_index, output_path=out2, now=FIXED_NOW,
        )
        assert out1.read_bytes() == out2.read_bytes(), (
            "Two extractions with identical now produce different output"
        )
