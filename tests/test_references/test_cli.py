"""Tests for the references CLI commands."""
from __future__ import annotations

import json

import pytest

from peoplenet_process_extractor.cli import main



class TestHelp:
    def test_references_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["references", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "extract" in out

    def test_extract_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["references", "extract", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "--corpus-root" in out

    def test_verify_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["references", "verify", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "--corpus-root" in out

    def test_query_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["references", "query", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "--references" in out


class TestPreviousCLIsStillWork:
    def test_scenario_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["scenario", "--help"])
        assert exc_info.value.code == 0

    def test_manifest_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["manifest", "--help"])
        assert exc_info.value.code == 0

    def test_corpus_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["corpus", "--help"])
        assert exc_info.value.code == 0

    def test_index_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["index", "--help"])
        assert exc_info.value.code == 0


class TestExtractCommand:
    def test_full_extract(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        rc = main([
            "references", "extract",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--output", str(out),
        ])
        assert rc == 0
        assert out.exists()

    def test_extract_output_exists_without_force(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        out.write_text("existing")
        rc = main([
            "references", "extract",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--output", str(out),
        ])
        assert rc != 0
        assert out.read_text() == "existing"

    def test_extract_force_overwrites(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        out = tmp_path / "refs.json"
        out.write_text("old")
        rc = main([
            "references", "extract",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--output", str(out),
            "--force",
        ])
        assert rc == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["format"] == "reference-extraction-v1"

    def test_created_at_flag_same_value_byte_identical(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        ts = "2026-06-24T12:00:00+00:00"
        out1 = tmp_path / "refs1.json"
        out2 = tmp_path / "refs2.json"
        rc1 = main([
            "references", "extract",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--output", str(out1),
            "--created-at", ts,
        ])
        assert rc1 == 0
        rc2 = main([
            "references", "extract",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--output", str(out2),
            "--created-at", ts,
        ])
        assert rc2 == 0
        assert out1.read_bytes() == out2.read_bytes(), (
            "Two runs with --created-at identical value produced different output"
        )

    def test_created_at_invalid_not_utc_fails(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        rc = main([
            "references", "extract",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--output", str(tmp_path / "refs.json"),
            "--created-at", "2026-06-24T12:00:00+02:00",
        ])
        assert rc != 0

    def test_created_at_invalid_format_fails(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        rc = main([
            "references", "extract",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--output", str(tmp_path / "refs.json"),
            "--created-at", "not-a-timestamp",
        ])
        assert rc != 0

    def test_created_at_z_suffix_accepted(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        """The Z UTC suffix must be accepted as equivalent to +00:00."""
        out = tmp_path / "refs.json"
        rc = main([
            "references", "extract",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--output", str(out),
            "--created-at", "2026-06-24T12:00:00Z",
        ])
        assert rc == 0
        assert out.exists()

    def test_created_at_z_and_plus00_byte_identical(
        self, non_git_corpus, corpus_manifest, built_index, tmp_path
    ):
        """Z and +00:00 at the same instant must produce byte-identical output."""
        ts_z = "2026-06-24T12:00:00Z"
        ts_plus = "2026-06-24T12:00:00+00:00"
        out_z = tmp_path / "refs_z.json"
        out_plus = tmp_path / "refs_plus.json"
        rc1 = main([
            "references", "extract",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--output", str(out_z),
            "--created-at", ts_z,
        ])
        assert rc1 == 0
        rc2 = main([
            "references", "extract",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--output", str(out_plus),
            "--created-at", ts_plus,
        ])
        assert rc2 == 0
        assert out_z.read_bytes() == out_plus.read_bytes(), (
            "Z and +00:00 at the same instant should produce byte-identical output"
        )


class TestVerifyCommand:
    def test_verify_valid(
        self,
        non_git_corpus,
        corpus_manifest,
        built_index,
        built_extraction,
    ):
        rc = main([
            "references", "verify",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--references", str(built_extraction),
        ])
        assert rc == 0

    def test_verify_tampered_fails(
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

        rc = main([
            "references", "verify",
            "--corpus-root", str(non_git_corpus),
            "--corpus-manifest", str(corpus_manifest),
            "--index", str(built_index),
            "--references", str(tampered),
        ])
        assert rc != 0


class TestQueryCommand:
    def test_query_no_filters(self, built_extraction, capsys):
        rc = main([
            "references", "query",
            "--references", str(built_extraction),
        ])
        assert rc == 0

    def test_query_status_filter(self, built_extraction, capsys):
        rc = main([
            "references", "query",
            "--references", str(built_extraction),
            "--status", "observed",
        ])
        assert rc == 0

    def test_query_json_output(self, built_extraction, capsys):
        rc = main([
            "references", "query",
            "--references", str(built_extraction),
            "--json",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)

    def test_query_json_structure(self, built_extraction, capsys):
        rc = main([
            "references", "query",
            "--references", str(built_extraction),
            "--json",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        if data:
            row = data[0]
            assert "path" in row
            assert "reference_id" in row
            assert "status" in row
            assert "raw_expression" in row

    def test_query_status_malformed_filter(self, built_extraction, capsys):
        rc = main([
            "references", "query",
            "--references", str(built_extraction),
            "--status", "malformed",
            "--json",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        for row in data:
            assert row["status"] == "malformed"
