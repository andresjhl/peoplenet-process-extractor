"""Shared fixtures for test_index."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.index.builder import build_index

FIXTURE_CORPUS = Path(__file__).parent.parent / "fixtures" / "index_corpus"
FIXED_NOW = datetime(2026, 6, 23, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def corpus_manifest(tmp_path: Path) -> Path:
    """Build a corpus manifest from the index fixture corpus."""
    manifest = tmp_path / "corpus-manifest.json"
    code, msgs = create_inventory(
        corpus_root=FIXTURE_CORPUS,
        output_path=manifest,
        corpus_id="index-corpus",
        now=FIXED_NOW,
    )
    assert code == 0, f"create_inventory failed: {msgs}"
    return manifest


@pytest.fixture()
def built_index(tmp_path: Path, corpus_manifest: Path) -> Path:
    """Build a structural index from the index fixture corpus."""
    db = tmp_path / "structural-index.sqlite"
    code, msgs = build_index(
        corpus_root=FIXTURE_CORPUS,
        manifest_path=corpus_manifest,
        output_path=db,
        now=FIXED_NOW,
    )
    assert code == 0, f"build_index failed: {msgs}"
    return db
