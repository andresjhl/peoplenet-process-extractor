"""Shared fixtures for test_references."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.index.builder import build_index
from peoplenet_process_extractor.references.extraction import extract_references

FIXTURE_CORPUS = Path(__file__).parent.parent / "fixtures" / "references_corpus"
FIXED_NOW = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def non_git_corpus(tmp_path: Path) -> Path:
    """Copy the fixture corpus to a non-git temp directory."""
    dest = tmp_path / "non_git_corpus"
    shutil.copytree(FIXTURE_CORPUS, dest)
    return dest


@pytest.fixture()
def corpus_manifest(tmp_path: Path, non_git_corpus: Path) -> Path:
    """Build a corpus manifest from the references fixture corpus."""
    manifest = tmp_path / "corpus-manifest.json"
    code, msgs = create_inventory(
        corpus_root=non_git_corpus,
        output_path=manifest,
        corpus_id="references-corpus",
        now=FIXED_NOW,
    )
    assert code == 0, f"create_inventory failed: {msgs}"
    return manifest


@pytest.fixture()
def built_index(tmp_path: Path, non_git_corpus: Path, corpus_manifest: Path) -> Path:
    """Build a structural index from the references fixture corpus."""
    db = tmp_path / "structural-index.sqlite"
    code, msgs = build_index(
        corpus_root=non_git_corpus,
        manifest_path=corpus_manifest,
        output_path=db,
        now=FIXED_NOW,
    )
    assert code == 0, f"build_index failed: {msgs}"
    return db


@pytest.fixture()
def built_extraction(
    tmp_path: Path,
    non_git_corpus: Path,
    corpus_manifest: Path,
    built_index: Path,
) -> Path:
    """Build a reference extraction from the fixture corpus."""
    out = tmp_path / "reference-extraction.json"
    code, msgs = extract_references(
        corpus_root=non_git_corpus,
        manifest_path=corpus_manifest,
        index_path=built_index,
        output_path=out,
        force=False,
        now=FIXED_NOW,
    )
    assert code == 0, f"extract_references failed: {msgs}"
    return out
