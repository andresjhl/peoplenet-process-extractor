"""
High-level index service: build and verify a structural-index-v1.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..corpus.serialization import DeserializationError, deserialize_manifest
from ..manifest.hashing import compute_file_hash_and_size
from .builder import build_index
from .queries import logical_export, query_elements, query_files, query_stats, read_metadata
from .validation import validate_index


def build_index_service(
    corpus_root: Path,
    manifest_path: Path,
    output_path: Path,
    force: bool = False,
    now: datetime | None = None,
) -> tuple[int, list[str]]:
    """Delegate to builder.build_index."""
    return build_index(
        corpus_root=corpus_root,
        manifest_path=manifest_path,
        output_path=output_path,
        force=force,
        now=now,
    )


def verify_index_service(
    corpus_root: Path,
    manifest_path: Path,
    db_path: Path,
) -> tuple[int, list[str]]:
    """
    Verify a structural-index-v1 database against a corpus and manifest.

    Checks:
    1. Manifest is valid.
    2. Corpus matches manifest (exact-scope).
    3. SQLite integrity.
    4. Manifest SHA-256 and size match what is stored.
    5. Metadata consistency.
    6. All entries present, no extra rows.

    Returns (exit_code, messages).
    """
    messages: list[str] = []

    # Load and validate manifest.
    if not manifest_path.exists():
        messages.append(f"Error: manifest not found: '{manifest_path}'.")
        return 1, messages

    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        messages.append(f"Error reading manifest: {exc}")
        return 1, messages

    try:
        manifest, val_errors = deserialize_manifest(manifest_text)
    except DeserializationError as exc:
        messages.append(f"Error: manifest is not valid: {exc}")
        return 1, messages

    if val_errors:
        for err in val_errors:
            messages.append(f"Validation error [{err.code}]: {err.message}")
        messages.append("Error: manifest failed validation.")
        return 1, messages

    # Verify corpus coherence.
    from ..corpus.service import verify_corpus
    verify_code, _diff, verify_msgs = verify_corpus(corpus_root, manifest_path)
    if verify_code != 0:
        messages.append("Error: corpus does not match manifest.")
        for m in verify_msgs:
            messages.append(f"  {m}")
        return 1, messages

    # Hash the manifest file.
    try:
        manifest_sha256, manifest_size = compute_file_hash_and_size(manifest_path)
    except OSError as exc:
        messages.append(f"Error hashing manifest: {exc}")
        return 1, messages

    # Verify database exists.
    if not db_path.exists():
        messages.append(f"Error: database not found: '{db_path}'.")
        return 1, messages

    # Run structural validation.
    errors = validate_index(db_path, manifest=manifest, manifest_sha256=manifest_sha256)
    if errors:
        for err in errors:
            messages.append(f"Error: {err}")
        return 1, messages

    # Verify stored manifest size matches.
    meta = read_metadata(db_path)
    stored_size = meta.get("corpus_manifest_size_bytes")
    if stored_size != manifest_size:
        messages.append(
            f"Error: manifest size mismatch: stored={stored_size}, actual={manifest_size}."
        )
        return 1, messages

    messages.append("Index is valid.")
    total = meta.get("total_files", 0)
    messages.append(f"  {total} files verified.")
    return 0, messages


__all__ = [
    "build_index_service",
    "verify_index_service",
    "logical_export",
    "query_files",
    "query_elements",
    "query_stats",
]
