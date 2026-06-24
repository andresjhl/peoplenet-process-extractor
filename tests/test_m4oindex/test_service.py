"""Tests for service.py: build_node_index and verify_node_index."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from peoplenet_process_extractor.m4oindex.service import build_node_index, verify_node_index
from peoplenet_process_extractor.m4oindex.serialization import deserialize_index, serialize_index

from .conftest import FIXTURE_CORPUS, FIXED_NOW


def _build(tmp_path: Path, force: bool = False) -> tuple[int, list[str], Path, Path]:
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURE_CORPUS, corpus)
    from peoplenet_process_extractor.corpus.service import create_inventory
    manifest_path = tmp_path / "manifest.json"
    create_inventory(corpus_root=corpus, output_path=manifest_path,
                     corpus_id="node-index-corpus", now=FIXED_NOW)
    output = tmp_path / "index.json"
    code, msgs = build_node_index(
        corpus_root=corpus,
        manifest_path=manifest_path,
        output_path=output,
        force=force,
        now=FIXED_NOW,
    )
    return code, msgs, corpus, manifest_path


class TestBuildService:
    def test_build_succeeds(self, tmp_path):
        code, msgs, _, _ = _build(tmp_path)
        assert code == 0, msgs

    def test_output_file_created(self, tmp_path):
        _build(tmp_path)
        assert (tmp_path / "index.json").exists()

    def test_output_is_valid_json(self, tmp_path):
        _build(tmp_path)
        text = (tmp_path / "index.json").read_text(encoding="utf-8")
        obj = json.loads(text)
        assert obj["format"] == "m4object-node-index-v1"

    def test_output_is_canonical(self, tmp_path):
        _build(tmp_path)
        text = (tmp_path / "index.json").read_text(encoding="utf-8")
        idx = deserialize_index(text)
        assert serialize_index(idx) == text

    def test_no_force_fails_when_exists(self, tmp_path):
        # First build succeeds
        code, msgs, corpus, manifest_path = _build(tmp_path)
        assert code == 0
        output = tmp_path / "index.json"
        # Second build without --force must fail because output exists
        code2, msgs2 = build_node_index(
            corpus_root=corpus,
            manifest_path=manifest_path,
            output_path=output,
            force=False,
            now=FIXED_NOW,
        )
        assert code2 == 1
        assert any("already exists" in m for m in msgs2)

    def test_force_overwrites(self, tmp_path):
        # First build
        code, msgs, corpus, manifest_path = _build(tmp_path)
        assert code == 0
        output = tmp_path / "index.json"
        # Second build with --force must succeed
        code2, msgs2 = build_node_index(
            corpus_root=corpus,
            manifest_path=manifest_path,
            output_path=output,
            force=True,
            now=FIXED_NOW,
        )
        assert code2 == 0

    def test_invalid_manifest_fails(self, tmp_path):
        corpus = tmp_path / "corpus"
        shutil.copytree(FIXTURE_CORPUS, corpus)
        bad_manifest = tmp_path / "bad.json"
        bad_manifest.write_text("not json", encoding="utf-8")
        output = tmp_path / "index.json"
        code, msgs = build_node_index(
            corpus_root=corpus,
            manifest_path=bad_manifest,
            output_path=output,
            now=FIXED_NOW,
        )
        assert code == 1
        assert any("valid" in m.lower() or "json" in m.lower() for m in msgs)

    def test_missing_manifest_fails(self, tmp_path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        output = tmp_path / "index.json"
        code, msgs = build_node_index(
            corpus_root=corpus,
            manifest_path=tmp_path / "nonexistent.json",
            output_path=output,
        )
        assert code == 1


class TestVerifyService:
    def _build_and_verify(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        shutil.copytree(FIXTURE_CORPUS, corpus)
        from peoplenet_process_extractor.corpus.service import create_inventory
        manifest_path = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus, output_path=manifest_path,
                         corpus_id="node-index-corpus", now=FIXED_NOW)
        output = tmp_path / "index.json"
        build_node_index(corpus_root=corpus, manifest_path=manifest_path,
                         output_path=output, now=FIXED_NOW)
        return corpus, manifest_path, output

    def test_verify_succeeds(self, tmp_path):
        corpus, manifest_path, output = self._build_and_verify(tmp_path)
        code, msgs = verify_node_index(corpus_root=corpus, manifest_path=manifest_path, index_path=output)
        assert code == 0, msgs

    def test_verify_manifest_hash_drift(self, tmp_path):
        corpus, manifest_path, output = self._build_and_verify(tmp_path)
        # Modify manifest to trigger hash drift
        text = manifest_path.read_text(encoding="utf-8")
        manifest_path.write_text(text + " ", encoding="utf-8")
        code, msgs = verify_node_index(corpus_root=corpus, manifest_path=manifest_path, index_path=output)
        assert code == 1
        assert any("SHA-256" in m or "sha256" in m.lower() or "drift" in m.lower() for m in msgs)

    def test_verify_manifest_size_drift(self, tmp_path):
        corpus, manifest_path, output = self._build_and_verify(tmp_path)
        # Append a byte to change size without necessarily changing hash (different prefix)
        raw = manifest_path.read_bytes()
        # Create a manifest with same sha256 but different size is not straightforward;
        # just verify the error path by writing a different manifest
        manifest_path.write_bytes(raw + b"\n")
        code, msgs = verify_node_index(corpus_root=corpus, manifest_path=manifest_path, index_path=output)
        assert code == 1

    def test_verify_resource_drift(self, tmp_path):
        corpus, manifest_path, output = self._build_and_verify(tmp_path)
        # Modify a corpus file to trigger rebuild difference
        for f in corpus.rglob("nodes.json"):
            original = json.loads(f.read_text(encoding="utf-8"))
            original["M4RCH_NODES"] = []
            f.write_text(json.dumps(original), encoding="utf-8")
            break
        code, msgs = verify_node_index(corpus_root=corpus, manifest_path=manifest_path, index_path=output)
        # Either hash_mismatch or rebuild mismatch → code 1
        assert code == 1

    def test_verify_non_canonical_index(self, tmp_path):
        corpus, manifest_path, output = self._build_and_verify(tmp_path)
        # Add trailing space to break canonical form
        text = output.read_text(encoding="utf-8")
        output.write_text(text.rstrip("\n") + "  \n", encoding="utf-8")
        code, msgs = verify_node_index(corpus_root=corpus, manifest_path=manifest_path, index_path=output)
        assert code == 1
        assert any("canonical" in m.lower() for m in msgs)

    def test_verify_missing_index(self, tmp_path):
        corpus, manifest_path, _ = self._build_and_verify(tmp_path)
        code, msgs = verify_node_index(
            corpus_root=corpus, manifest_path=manifest_path,
            index_path=tmp_path / "nonexistent.json",
        )
        assert code == 1
