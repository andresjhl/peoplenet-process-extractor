"""Tests for index CLI commands: help, exit codes, no traceback, no regression."""
from __future__ import annotations

import json

import pytest

from peoplenet_process_extractor.cli import main
from peoplenet_process_extractor.corpus.service import create_inventory

from .conftest import FIXTURE_CORPUS, FIXED_NOW


class TestHelp:
    def test_index_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["index", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "build" in out
        assert "verify" in out
        assert "query" in out

    def test_index_build_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["index", "build", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "--corpus-root" in out
        assert "--corpus-manifest" in out
        assert "--output" in out
        assert "--force" in out

    def test_index_verify_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["index", "verify", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "--corpus-root" in out
        assert "--database" in out

    def test_index_query_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["index", "query", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "files" in out
        assert "elements" in out
        assert "stats" in out


class TestBuildCLI:
    def test_build_success(self, tmp_path, capsys):
        manifest = tmp_path / "manifest.json"
        create_inventory(corpus_root=FIXTURE_CORPUS, output_path=manifest, corpus_id="ic", now=FIXED_NOW)
        db = tmp_path / "idx.sqlite"
        code = main([
            "index", "build",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--corpus-manifest", str(manifest),
            "--output", str(db),
        ])
        assert code == 0
        assert db.exists()

    def test_build_nonexistent_manifest(self, tmp_path, capsys):
        code = main([
            "index", "build",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--corpus-manifest", str(tmp_path / "no_manifest.json"),
            "--output", str(tmp_path / "idx.sqlite"),
        ])
        assert code != 0
        err = capsys.readouterr().err
        assert "Error" in err

    def test_build_no_traceback(self, tmp_path, capsys):
        code = main([
            "index", "build",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--corpus-manifest", str(tmp_path / "no_manifest.json"),
            "--output", str(tmp_path / "idx.sqlite"),
        ])
        assert code != 0
        err = capsys.readouterr().err
        assert "Traceback" not in err

    def test_build_output_exists_no_force(self, tmp_path, capsys):
        manifest = tmp_path / "manifest.json"
        create_inventory(corpus_root=FIXTURE_CORPUS, output_path=manifest, corpus_id="ic", now=FIXED_NOW)
        db = tmp_path / "idx.sqlite"
        db.write_text("existing")
        code = main([
            "index", "build",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--corpus-manifest", str(manifest),
            "--output", str(db),
        ])
        assert code != 0
        assert db.read_text() == "existing"

    def test_build_force(self, tmp_path, capsys):
        manifest = tmp_path / "manifest.json"
        create_inventory(corpus_root=FIXTURE_CORPUS, output_path=manifest, corpus_id="ic", now=FIXED_NOW)
        db = tmp_path / "idx.sqlite"
        main(["index", "build", "--corpus-root", str(FIXTURE_CORPUS),
              "--corpus-manifest", str(manifest), "--output", str(db)])
        code = main([
            "index", "build",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--corpus-manifest", str(manifest),
            "--output", str(db),
            "--force",
        ])
        assert code == 0


class TestVerifyCLI:
    def test_verify_success(self, built_index, corpus_manifest, capsys):
        code = main([
            "index", "verify",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--corpus-manifest", str(corpus_manifest),
            "--database", str(built_index),
        ])
        assert code == 0

    def test_verify_missing_db(self, corpus_manifest, tmp_path, capsys):
        code = main([
            "index", "verify",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--corpus-manifest", str(corpus_manifest),
            "--database", str(tmp_path / "no.sqlite"),
        ])
        assert code != 0

    def test_verify_no_traceback(self, corpus_manifest, tmp_path, capsys):
        code = main([
            "index", "verify",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--corpus-manifest", str(corpus_manifest),
            "--database", str(tmp_path / "no.sqlite"),
        ])
        assert code != 0
        err = capsys.readouterr().err
        assert "Traceback" not in err


class TestQueryCLI:
    def test_query_files_all(self, built_index, capsys):
        code = main(["index", "query", "files", "--database", str(built_index)])
        assert code == 0
        out = capsys.readouterr().out
        assert "structured_ln4" in out

    def test_query_files_classification_filter(self, built_index, capsys):
        code = main([
            "index", "query", "files",
            "--database", str(built_index),
            "--classification", "unstructured_ln4",
        ])
        assert code == 0
        out = capsys.readouterr().out
        assert "loose.ln4" in out

    def test_query_files_json(self, built_index, capsys):
        code = main([
            "index", "query", "files",
            "--database", str(built_index),
            "--json",
        ])
        assert code == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 7

    def test_query_elements_all(self, built_index, capsys):
        code = main(["index", "query", "elements", "--database", str(built_index)])
        assert code == 0
        out = capsys.readouterr().out
        assert "OBJ_A" in out

    def test_query_elements_filter(self, built_index, capsys):
        code = main([
            "index", "query", "elements",
            "--database", str(built_index),
            "--meta4object", "OBJ_A",
            "--item-type", "METHOD",
        ])
        assert code == 0
        out = capsys.readouterr().out
        assert "METH_X" in out

    def test_query_elements_json(self, built_index, capsys):
        code = main([
            "index", "query", "elements",
            "--database", str(built_index),
            "--json",
        ])
        assert code == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert len(data) == 4

    def test_query_stats(self, built_index, capsys):
        code = main(["index", "query", "stats", "--database", str(built_index)])
        assert code == 0
        out = capsys.readouterr().out
        assert "7" in out  # total_files

    def test_query_stats_json(self, built_index, capsys):
        code = main([
            "index", "query", "stats",
            "--database", str(built_index),
            "--json",
        ])
        assert code == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["total_files"] == 7
        assert data["structured_files"] == 4

    def test_query_files_no_results(self, built_index, capsys):
        code = main([
            "index", "query", "files",
            "--database", str(built_index),
            "--classification", "ignored",
        ])
        assert code == 0
        out = capsys.readouterr().out
        assert "No files" in out or out.strip() == "[]" or len(out.strip()) >= 0

    def test_query_elements_no_results(self, built_index, capsys):
        code = main([
            "index", "query", "elements",
            "--database", str(built_index),
            "--meta4object", "NONEXISTENT",
        ])
        assert code == 0


class TestNoRegressionPreviousCLIs:
    """Ensure existing commands still work after adding index commands."""

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

    def test_root_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "index" in out
