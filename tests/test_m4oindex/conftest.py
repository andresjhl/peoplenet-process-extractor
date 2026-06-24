"""Shared test fixtures for test_m4oindex."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
from peoplenet_process_extractor.m4oindex.models import (
    CorpusManifestRef,
    M4oEvidence,
)

FIXTURE_CORPUS = Path(__file__).parent.parent / "fixtures" / "m4o_node_index_corpus"
GOLDEN_PATH = Path(__file__).parent.parent / "golden" / "m4object-node-index-v1.json"

FIXED_NOW = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
FIXED_GENERATOR_VERSION = "0.1.0"


def make_manifest(tmp_path: Path, corpus: Path | None = None) -> tuple[Path, Path]:
    """
    Build a corpus manifest from the fixture corpus and return (corpus_path, manifest_path).
    """
    src = corpus or FIXTURE_CORPUS
    manifest_path = tmp_path / "corpus-manifest.json"
    code, msgs = create_inventory(
        corpus_root=src,
        output_path=manifest_path,
        corpus_id="node-index-corpus",
        now=FIXED_NOW,
    )
    assert code == 0, f"create_inventory failed: {msgs}"
    return src, manifest_path


def load_manifest_ref(manifest_path: Path) -> CorpusManifestRef:
    raw = manifest_path.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    manifest, _ = deserialize_manifest(text)
    return CorpusManifestRef(
        corpus_id=manifest.corpus_id,
        corpus_schema_version=manifest.schema_version,
        sha256=sha256,
        size_bytes=len(raw),
    )


def make_evidence(
    path: str,
    classification: str,
    table: str,
    row_index: int,
    sha256: str = "a" * 64,
) -> M4oEvidence:
    return M4oEvidence(
        path=path,
        sha256=sha256,
        classification=classification,
        table=table,
        row_index=row_index,
    )
