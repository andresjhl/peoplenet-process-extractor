"""Tests for the corpus CLI commands."""
import json
from pathlib import Path

import pytest

from peoplenet_process_extractor.cli import main

FIXTURE_CORPUS = Path(__file__).parent.parent / "fixtures" / "corpus"


def _run(*args: str) -> int:
    return main(list(args))


class TestCliHelp:
    def test_top_level_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            _run("--help")
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "corpus" in out

    def test_corpus_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            _run("corpus", "--help")
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "inventory" in out
        assert "verify" in out

    def test_corpus_inventory_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            _run("corpus", "inventory", "--help")
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "--corpus-root" in out
        assert "--output" in out

    def test_corpus_verify_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            _run("corpus", "verify", "--help")
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "--corpus-root" in out


class TestCorpusInventoryCli:
    def test_basic_inventory(self, tmp_path):
        output = tmp_path / "manifest.json"
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--output", str(output),
        )
        assert code == 0
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["schema_version"] == "1.0"

    def test_no_overwrite_without_force(self, tmp_path):
        output = tmp_path / "manifest.json"
        output.write_text("{}")
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--output", str(output),
        )
        assert code != 0
        assert output.read_text() == "{}"

    def test_force_overwrites(self, tmp_path):
        output = tmp_path / "manifest.json"
        output.write_text("{}")
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--output", str(output),
            "--force",
        )
        assert code == 0
        data = json.loads(output.read_text())
        assert "schema_version" in data

    def test_nonexistent_corpus_fails(self, tmp_path):
        output = tmp_path / "manifest.json"
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(tmp_path / "nonexistent"),
            "--output", str(output),
        )
        assert code != 0
        assert not output.exists()

    def test_source_root_filter(self, tmp_path):
        output = tmp_path / "manifest.json"
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--output", str(output),
            "--source-root", "CP",
        )
        assert code == 0
        data = json.loads(output.read_text())
        assert data["included_source_roots"] == ["CP"]

    def test_multiple_source_root_filters(self, tmp_path):
        output = tmp_path / "manifest.json"
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--output", str(output),
            "--source-root", "CP",
            "--source-root", "GTO",
        )
        assert code == 0
        data = json.loads(output.read_text())
        assert set(data["included_source_roots"]) == {"CP", "GTO"}

    def test_nonexistent_source_root_fails(self, tmp_path):
        output = tmp_path / "manifest.json"
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--output", str(output),
            "--source-root", "NONEXISTENT",
        )
        assert code != 0
        assert not output.exists()

    def test_custom_corpus_id(self, tmp_path):
        output = tmp_path / "manifest.json"
        _run(
            "corpus", "inventory",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--output", str(output),
            "--corpus-id", "custom-id",
        )
        data = json.loads(output.read_text())
        assert data["corpus_id"] == "custom-id"

    def test_no_absolute_paths_in_output(self, tmp_path):
        output = tmp_path / "manifest.json"
        _run(
            "corpus", "inventory",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--output", str(output),
        )
        text = output.read_text()
        corpus_abs = str(FIXTURE_CORPUS).replace("\\", "/")
        assert corpus_abs not in text

    def test_exit_code_zero_on_success(self, tmp_path):
        output = tmp_path / "manifest.json"
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--output", str(output),
        )
        assert code == 0

    def test_exit_code_nonzero_on_error(self, tmp_path):
        output = tmp_path / "manifest.json"
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(tmp_path / "nope"),
            "--output", str(output),
        )
        assert code != 0


class TestCorpusVerifyCli:
    def _make_manifest(self, tmp_path, **kwargs):
        output = tmp_path / "manifest.json"
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(FIXTURE_CORPUS),
            "--output", str(output),
            *[item for k, v in kwargs.items() for item in [f"--{k}", v]],
        )
        assert code == 0
        return output

    def test_verify_unchanged(self, tmp_path):
        manifest = self._make_manifest(tmp_path)
        code = _run(
            "corpus", "verify",
            "--corpus-root", str(FIXTURE_CORPUS),
            str(manifest),
        )
        assert code == 0

    def test_verify_invalid_manifest_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not valid json")
        code = _run(
            "corpus", "verify",
            "--corpus-root", str(FIXTURE_CORPUS),
            str(bad),
        )
        assert code != 0

    def test_verify_nonexistent_corpus(self, tmp_path):
        manifest = self._make_manifest(tmp_path)
        code = _run(
            "corpus", "verify",
            "--corpus-root", str(tmp_path / "nonexistent"),
            str(manifest),
        )
        assert code != 0

    def test_verify_detects_modification(self, tmp_path):
        import shutil
        corpus_copy = tmp_path / "corpus_copy"
        shutil.copytree(FIXTURE_CORPUS, corpus_copy)

        manifest = tmp_path / "manifest.json"
        _run(
            "corpus", "inventory",
            "--corpus-root", str(corpus_copy),
            "--output", str(manifest),
        )

        (corpus_copy / "outside_structure.ln4").write_text("changed content")

        code = _run(
            "corpus", "verify",
            "--corpus-root", str(corpus_copy),
            str(manifest),
        )
        assert code != 0


class TestMultiFilterCli:
    """Finding 5: multi-filter CLI tests with exact path verification."""

    def _make_corpus(self, tmp_path: Path) -> Path:
        corpus = tmp_path / "corpus"
        (corpus / "CP").mkdir(parents=True)
        (corpus / "GTO").mkdir()
        (corpus / "OTHER").mkdir()
        (corpus / "CP" / "cp_file.ln4").write_text("cp content")
        (corpus / "GTO" / "gto_file.ln4").write_text("gto content")
        (corpus / "OTHER" / "other_file.ln4").write_text("other content")
        (corpus / "root_file.ln4").write_text("root content")
        return corpus

    def test_multi_filter_exact_paths_and_roots(self, tmp_path):
        """--source-root CP --source-root GTO inventories exactly CP and GTO, nothing else."""
        corpus = self._make_corpus(tmp_path)
        output = tmp_path / "manifest.json"
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(corpus),
            "--output", str(output),
            "--source-root", "CP",
            "--source-root", "GTO",
        )
        assert code == 0
        data = json.loads(output.read_text())
        paths = sorted(f["path"] for f in data["files"])
        assert paths == ["CP/cp_file.ln4", "GTO/gto_file.ln4"]
        assert "OTHER/other_file.ln4" not in paths
        assert "root_file.ln4" not in paths
        assert data["included_source_roots"] == ["CP", "GTO"]


class TestDuplicateFilterCli:
    """Finding 6: duplicate --source-root values via CLI are normalized."""

    def test_duplicate_source_root_normalizes(self, tmp_path):
        """--source-root CP --source-root CP produces included_source_roots=['CP'], no error."""
        corpus = tmp_path / "corpus"
        (corpus / "CP").mkdir(parents=True)
        (corpus / "CP" / "file.ln4").write_text("cp content")
        output = tmp_path / "manifest.json"
        code = _run(
            "corpus", "inventory",
            "--corpus-root", str(corpus),
            "--output", str(output),
            "--source-root", "CP",
            "--source-root", "CP",
        )
        assert code == 0
        data = json.loads(output.read_text())
        assert data["included_source_roots"] == ["CP"]
        assert len(data["files"]) == 1


class TestNoRegressionOtherCommands:
    def test_scenario_migrate_still_works(self, tmp_path):
        input_file = Path(__file__).parent.parent / "fixtures" / "scenarios" / "legacy_peoplenet_call.json"
        output = tmp_path / "scenario.json"
        code = _run("scenario", "migrate", str(input_file), "--output", str(output))
        assert code == 0
        assert output.exists()

    def test_manifest_command_still_present(self, capsys):
        with pytest.raises(SystemExit):
            _run("manifest", "--help")
        out = capsys.readouterr().out
        assert "create" in out or "verify" in out
