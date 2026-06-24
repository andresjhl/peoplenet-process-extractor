"""
High-level service for m4object-node-index-v1.

build_node_index:
  load manifest → validate → compute manifest_ref → build model →
  validate model → serialize → round-trip → write atomically.

verify_node_index:
  Phase 1 — manifest identity (hash + size).
  Phase 2 — exact reconstruction and byte-level comparison.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path

from ..corpus.serialization import DeserializationError as CorpusDeserError, deserialize_manifest
from .extraction import build_m4o_node_index
from .models import CorpusManifestRef
from .serialization import DeserializationError, deserialize_index, serialize_index
from .validation import validate_index_model


def _compute_manifest_ref(manifest_path: Path, manifest_bytes: bytes | None = None) -> tuple[CorpusManifestRef, bytes]:
    """
    Compute CorpusManifestRef from the physical manifest file.

    Returns (ref, raw_bytes). The caller may pass pre-read bytes to avoid double-reading.
    """
    if manifest_bytes is None:
        manifest_bytes = manifest_path.read_bytes()
    sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    size = len(manifest_bytes)

    # We need corpus_id and schema_version from the manifest content.
    # Parse without full validation since we need the fields.
    text = manifest_bytes.decode("utf-8")
    manifest, _ = deserialize_manifest(text)
    return CorpusManifestRef(
        corpus_id=manifest.corpus_id,
        corpus_schema_version=manifest.schema_version,
        sha256=sha256,
        size_bytes=size,
    ), manifest_bytes


def build_node_index(
    corpus_root: Path,
    manifest_path: Path,
    output_path: Path,
    force: bool = False,
    now: datetime | None = None,
) -> tuple[int, list[str]]:
    """
    Build m4object-node-index-v1 and write it atomically to output_path.

    Returns (exit_code, messages).
    """
    messages: list[str] = []

    if output_path.exists() and not force:
        messages.append(
            f"Error: output file already exists: '{output_path}'. Use --force to overwrite."
        )
        return 1, messages

    # Load and validate manifest
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        messages.append(f"Error reading manifest: {exc}")
        return 1, messages

    try:
        manifest_text = manifest_bytes.decode("utf-8")
        manifest, val_errors = deserialize_manifest(manifest_text)
    except (CorpusDeserError, UnicodeDecodeError) as exc:
        messages.append(f"Error: manifest is not valid: {exc}")
        return 1, messages

    if val_errors:
        for err in val_errors:
            messages.append(f"Manifest validation error [{err.code}]: {err.message}")
        messages.append("Error: manifest failed validation. Cannot build index.")
        return 1, messages

    # Compute manifest ref from physical bytes
    try:
        manifest_ref, _ = _compute_manifest_ref(manifest_path, manifest_bytes)
    except Exception as exc:
        messages.append(f"Error computing manifest reference: {exc}")
        return 1, messages

    # Build model
    index = build_m4o_node_index(
        corpus_root=corpus_root,
        manifest=manifest,
        manifest_ref=manifest_ref,
        now=now,
    )

    # Validate model
    model_errors = validate_index_model(index)
    if model_errors:
        for err in model_errors:
            messages.append(f"Internal model error: {err}")
        messages.append("Error: index model failed validation (internal error).")
        return 1, messages

    # Serialize + round-trip
    first_text = serialize_index(index)
    try:
        rt_index = deserialize_index(first_text)
    except DeserializationError as exc:
        messages.append(f"Error: round-trip deserialization failed: {exc}")
        return 1, messages

    rt_errors = validate_index_model(rt_index)
    if rt_errors:
        messages.append("Error: round-trip model failed validation (internal error).")
        return 1, messages

    second_text = serialize_index(rt_index)
    if first_text != second_text:
        messages.append("Error: round-trip text mismatch (internal error).")
        return 1, messages

    # Write atomically
    try:
        _write_atomic(first_text, output_path)
    except OSError as exc:
        messages.append(f"Error writing output: {exc}")
        return 1, messages

    s = index.summary
    messages.append(f"m4object-node-index-v1 written to '{output_path}'.")
    messages.append(
        f"  {s.selected_file_count} files selected, "
        f"{s.successfully_parsed_file_count} parsed, "
        f"{s.failed_file_count} failed."
    )
    messages.append(
        f"  {s.node_binding_count} node bindings, "
        f"{s.alias_binding_count} alias bindings, "
        f"{s.inheritance_edge_count} inheritance edges."
    )
    if s.diagnostic_count:
        messages.append(f"  {s.diagnostic_count} diagnostics.")
    return 0, messages


def verify_node_index(
    corpus_root: Path,
    manifest_path: Path,
    index_path: Path,
) -> tuple[int, list[str]]:
    """
    Verify an m4object-node-index-v1 artifact against its source manifest.

    Phase 1: manifest identity (hash + size check).
    Phase 2: exact reconstruction and byte-level comparison.

    Returns (exit_code, messages).
    """
    messages: list[str] = []

    # ── Load stored index ────────────────────────────────────────────────
    try:
        stored_text = index_path.read_text(encoding="utf-8")
    except OSError as exc:
        messages.append(f"Error reading index: {exc}")
        return 1, messages

    try:
        stored_index = deserialize_index(stored_text)
    except DeserializationError as exc:
        messages.append(f"Error: index is not valid: {exc}")
        return 1, messages

    # Canonical form check
    canonical_text = serialize_index(stored_index)
    if canonical_text != stored_text:
        messages.append("Error: stored index is not in canonical form.")
        return 1, messages

    model_errors = validate_index_model(stored_index)
    if model_errors:
        for err in model_errors:
            messages.append(f"Error: stored index model: {err}")
        return 1, messages

    # ── Phase 1: manifest identity ────────────────────────────────────────
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        messages.append(f"Error reading manifest: {exc}")
        return 1, messages

    actual_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    actual_size = len(manifest_bytes)

    stored_ref = stored_index.source_manifest
    if stored_ref.sha256 != actual_sha256:
        messages.append(
            f"Error: manifest SHA-256 drift: "
            f"stored={stored_ref.sha256}, actual={actual_sha256}."
        )
        return 1, messages
    if stored_ref.size_bytes != actual_size:
        messages.append(
            f"Error: manifest size drift: "
            f"stored={stored_ref.size_bytes}, actual={actual_size}."
        )
        return 1, messages

    # ── Phase 2: exact reconstruction ────────────────────────────────────
    try:
        manifest_text = manifest_bytes.decode("utf-8")
        manifest, val_errors = deserialize_manifest(manifest_text)
    except (CorpusDeserError, UnicodeDecodeError) as exc:
        messages.append(f"Error loading manifest: {exc}")
        return 1, messages

    if val_errors:
        messages.append("Error: manifest failed validation.")
        return 1, messages

    # Reconstruct using stored created_at and generator version
    try:
        stored_dt = datetime.fromisoformat(stored_index.created_at)
    except ValueError as exc:
        messages.append(f"Error: stored created_at is not parseable: {exc}")
        return 1, messages

    manifest_ref = CorpusManifestRef(
        corpus_id=stored_ref.corpus_id,
        corpus_schema_version=stored_ref.corpus_schema_version,
        sha256=actual_sha256,
        size_bytes=actual_size,
    )

    rebuilt = build_m4o_node_index(
        corpus_root=corpus_root,
        manifest=manifest,
        manifest_ref=manifest_ref,
        now=stored_dt,
        generator_version=stored_index.generator.version,
    )

    rebuilt_text = serialize_index(rebuilt)
    if rebuilt_text != stored_text:
        messages.append("Error: rebuilt index does not match stored index (drift detected).")
        return 1, messages

    s = stored_index.summary
    messages.append("m4object-node-index-v1 is valid.")
    messages.append(
        f"  {s.selected_file_count} files, "
        f"{s.node_binding_count} node bindings, "
        f"{s.alias_binding_count} alias bindings, "
        f"{s.inheritance_edge_count} inheritance edges verified."
    )
    return 0, messages


def _write_atomic(text: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp: str | None = None
    try:
        fd, tmp = tempfile.mkstemp(dir=dest.parent, suffix=".tmp")
        os.close(fd)
        Path(tmp).write_bytes(text.encode("utf-8"))
        Path(tmp).replace(dest)
        tmp = None
    finally:
        if tmp is not None:
            try:
                Path(tmp).unlink(missing_ok=True)
            except OSError:
                pass
