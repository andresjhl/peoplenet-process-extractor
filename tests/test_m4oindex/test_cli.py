"""CLI tests for m4object-node-index commands."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from peoplenet_process_extractor.cli import main

from .conftest import FIXTURE_CORPUS, FIXED_NOW


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    """Copy fixture corpus and create manifest; return (corpus, manifest_path)."""
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURE_CORPUS, corpus)
    from peoplenet_process_extractor.corpus.service import create_inventory
    manifest_path = tmp_path / "manifest.json"
    create_inventory(corpus_root=corpus, output_path=manifest_path,
                     corpus_id="node-index-corpus", now=FIXED_NOW)
    return corpus, manifest_path


class TestBuildCommand:
    def test_build_exits_zero(self, tmp_path):
        corpus, manifest = _setup(tmp_path)
        output = tmp_path / "index.json"
        rc = main([
            "m4object-node-index", "build",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--output", str(output),
            "--created-at", "2026-06-24T12:00:00+00:00",
        ])
        assert rc == 0

    def test_build_creates_file(self, tmp_path):
        corpus, manifest = _setup(tmp_path)
        output = tmp_path / "index.json"
        main([
            "m4object-node-index", "build",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--output", str(output),
            "--created-at", "2026-06-24T12:00:00+00:00",
        ])
        assert output.exists()

    def test_build_output_valid_format(self, tmp_path):
        corpus, manifest = _setup(tmp_path)
        output = tmp_path / "index.json"
        main([
            "m4object-node-index", "build",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--output", str(output),
        ])
        raw = json.loads(output.read_text(encoding="utf-8"))
        assert raw["format"] == "m4object-node-index-v1"
        assert raw["schema_version"] == 1

    def test_build_fails_if_output_exists(self, tmp_path):
        corpus, manifest = _setup(tmp_path)
        output = tmp_path / "index.json"
        output.write_text("{}", encoding="utf-8")
        rc = main([
            "m4object-node-index", "build",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--output", str(output),
        ])
        assert rc == 1

    def test_build_force_overwrites(self, tmp_path):
        corpus, manifest = _setup(tmp_path)
        output = tmp_path / "index.json"
        output.write_text("{}", encoding="utf-8")
        rc = main([
            "m4object-node-index", "build",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--output", str(output),
            "--force",
        ])
        assert rc == 0

    def test_build_invalid_created_at(self, tmp_path, capsys):
        corpus, manifest = _setup(tmp_path)
        output = tmp_path / "index.json"
        rc = main([
            "m4object-node-index", "build",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--output", str(output),
            "--created-at", "not-a-date",
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    def test_build_non_utc_created_at(self, tmp_path, capsys):
        corpus, manifest = _setup(tmp_path)
        output = tmp_path / "index.json"
        rc = main([
            "m4object-node-index", "build",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--output", str(output),
            "--created-at", "2026-06-24T12:00:00+02:00",
        ])
        assert rc == 1

    def test_build_fixed_created_at_deterministic(self, tmp_path):
        corpus, manifest = _setup(tmp_path)
        out1 = tmp_path / "idx1.json"
        out2 = tmp_path / "idx2.json"
        args = [
            "m4object-node-index", "build",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--created-at", "2026-06-24T12:00:00+00:00",
        ]
        main(args + ["--output", str(out1)])
        main(args + ["--output", str(out2)])
        assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")


class TestVerifyCommand:
    def _build_index(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        corpus, manifest = _setup(tmp_path)
        output = tmp_path / "index.json"
        main([
            "m4object-node-index", "build",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--output", str(output),
            "--created-at", "2026-06-24T12:00:00+00:00",
        ])
        return corpus, manifest, output

    def test_verify_succeeds(self, tmp_path):
        corpus, manifest, output = self._build_index(tmp_path)
        rc = main([
            "m4object-node-index", "verify",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--index", str(output),
        ])
        assert rc == 0

    def test_verify_fails_on_manifest_drift(self, tmp_path):
        corpus, manifest, output = self._build_index(tmp_path)
        manifest.write_bytes(manifest.read_bytes() + b" ")
        rc = main([
            "m4object-node-index", "verify",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--index", str(output),
        ])
        assert rc == 1

    def test_verify_fails_on_missing_index(self, tmp_path):
        corpus, manifest, _ = self._build_index(tmp_path)
        rc = main([
            "m4object-node-index", "verify",
            "--corpus-root", str(corpus),
            "--corpus-manifest", str(manifest),
            "--index", str(tmp_path / "nonexistent.json"),
        ])
        assert rc == 1


class TestHelpCommand:
    def test_build_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["m4object-node-index", "build", "--help"])
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "corpus-root" in captured.out

    def test_verify_help(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["m4object-node-index", "verify", "--help"])
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "corpus-manifest" in captured.out
