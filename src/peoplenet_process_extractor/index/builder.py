"""
Transactional builder for structural-index-v1.

Build strategy:
1. Validate inputs.
2. Load and validate the corpus manifest.
3. Verify corpus coherence (reuses corpus.service.verify_corpus).
4. Compute SHA-256 and size of the manifest file.
5. Write to a sibling temp path (<output>.tmp.<pid>).
6. PRAGMA foreign_keys = ON.
7. Create schema inside a single transaction.
8. Insert all rows sorted by path (deterministic IDs).
9. Validate the temp index.
10. Publish via os.replace().
11. Clean up temp on any failure.

--force behaviour: temp is built and validated fully before replacing the
existing output, so a build failure leaves the previous database intact.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from importlib.metadata import version as _pkg_version
    _GENERATOR_VERSION = _pkg_version("peoplenet-process-extractor")
except Exception:
    _GENERATOR_VERSION = "unknown"

from ..corpus.serialization import DeserializationError, deserialize_manifest
from ..corpus.service import verify_corpus
from ..manifest.hashing import compute_file_hash_and_size
from .schema import (
    CREATE_FILE_WARNINGS,
    CREATE_INDEX_METADATA,
    CREATE_INDEXES,
    CREATE_SOURCE_FILES,
    CREATE_STRUCTURAL_ELEMENTS,
    GENERATOR_NAME,
    INDEX_FORMAT,
    SCHEMA_VERSION,
)
from .validation import validate_index


def build_index(
    corpus_root: Path,
    manifest_path: Path,
    output_path: Path,
    force: bool = False,
    now: datetime | None = None,
) -> tuple[int, list[str]]:
    """
    Build a structural-index-v1 SQLite database.

    Returns (exit_code, messages).
    exit_code 0 = success; non-zero = error.
    Never leaves a partial database or temp file on failure.
    """
    messages: list[str] = []

    # ── input validation ────────────────────────────────────────────────────

    if not corpus_root.exists() or not corpus_root.is_dir():
        messages.append(f"Error: corpus root '{corpus_root}' is not a directory.")
        return 1, messages

    if corpus_root.is_symlink():
        messages.append(f"Error: corpus root '{corpus_root}' is a symlink.")
        return 1, messages

    if not manifest_path.exists():
        messages.append(f"Error: manifest not found: '{manifest_path}'.")
        return 1, messages

    if output_path.exists() and not force:
        messages.append(
            f"Error: output already exists: '{output_path}'. Use --force to overwrite."
        )
        return 1, messages

    # ── load and validate manifest ──────────────────────────────────────────

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
        messages.append("Error: manifest failed validation; cannot build index.")
        return 1, messages

    # ── verify corpus coherence ─────────────────────────────────────────────

    verify_code, _diff, verify_msgs = verify_corpus(corpus_root, manifest_path)
    if verify_code != 0:
        messages.append("Error: corpus does not match manifest; cannot build index.")
        for m in verify_msgs:
            messages.append(f"  {m}")
        return 1, messages

    # ── hash the manifest file ──────────────────────────────────────────────

    try:
        manifest_sha256, manifest_size = compute_file_hash_and_size(manifest_path)
    except OSError as exc:
        messages.append(f"Error hashing manifest: {exc}")
        return 1, messages

    # ── prepare timestamp ───────────────────────────────────────────────────

    ts = now or datetime.now(timezone.utc)
    index_created_at = ts.isoformat()

    # ── build to temp path ──────────────────────────────────────────────────

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None

    try:
        fd, tmp_str = tempfile.mkstemp(
            dir=output_path.parent,
            prefix=".structural-index-",
            suffix=".tmp",
        )
        os.close(fd)
        tmp_path = Path(tmp_str)

        _build_sqlite(
            tmp_path=tmp_path,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            manifest_size=manifest_size,
            index_created_at=index_created_at,
        )

        # Validate before publishing.
        val_result = validate_index(tmp_path, manifest=manifest, manifest_sha256=manifest_sha256)
        if val_result:
            for err in val_result:
                messages.append(f"Error: index validation failed: {err}")
            return 1, messages

        # Atomic publish.
        os.replace(tmp_path, output_path)
        tmp_path = None

    except Exception as exc:
        messages.append(f"Error building index: {exc}")
        return 1, messages
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            _cleanup_sidecars(tmp_path)

    n = len(manifest.files)
    messages.append(f"Structural index written to '{output_path}'.")
    messages.append(f"  {n} files indexed.")
    return 0, messages


def _cleanup_sidecars(path: Path) -> None:
    """Remove WAL/SHM sidecar files that SQLite may leave beside a database path."""
    for suffix in ("-wal", "-shm"):
        sidecar = path.parent / (path.name + suffix)
        try:
            sidecar.unlink(missing_ok=True)
        except OSError:
            pass


def _build_sqlite(
    tmp_path: Path,
    manifest: object,
    manifest_sha256: str,
    manifest_size: int,
    index_created_at: str,
) -> None:
    """Create the full schema and insert all data in a single transaction."""
    con = sqlite3.connect(str(tmp_path))
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = DELETE")

        with con:
            # Schema.
            con.execute(CREATE_INDEX_METADATA)
            con.execute(CREATE_SOURCE_FILES)
            con.execute(CREATE_STRUCTURAL_ELEMENTS)
            con.execute(CREATE_FILE_WARNINGS)
            for idx_sql in CREATE_INDEXES:
                con.execute(idx_sql)

            # Sort files by path for deterministic IDs.
            sorted_files = sorted(manifest.files, key=lambda f: f.path)

            # Insert source_files.
            file_id_map: dict[str, int] = {}
            for idx, entry in enumerate(sorted_files, start=1):
                file_id_map[entry.path] = idx
                con.execute(
                    """
                    INSERT INTO source_files
                        (id, path, sha256, size_bytes, extension, source_root, classification, warning_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        idx,
                        entry.path,
                        entry.sha256,
                        entry.size_bytes,
                        entry.extension,
                        entry.source_root,
                        entry.classification,
                        len(entry.warnings),
                    ),
                )

                # Insert warnings for this file.
                for seq, warning_msg in enumerate(entry.warnings):
                    con.execute(
                        """
                        INSERT INTO file_warnings (source_file_id, sequence, message)
                        VALUES (?, ?, ?)
                        """,
                        (idx, seq, warning_msg),
                    )

                # Insert structural element if classified as structured_ln4.
                if entry.classification == "structured_ln4" and entry.structure is not None:
                    s = entry.structure
                    con.execute(
                        """
                        INSERT INTO structural_elements
                            (source_file_id, meta4object, item_type, item_name, rule_id, rule_date)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (idx, s.meta4object, s.item_type, s.item_name, s.rule_id, s.rule_date),
                    )

            # Count files.
            total_files = len(sorted_files)
            structured = sum(
                1 for e in sorted_files if e.classification == "structured_ln4"
            )
            unstructured = sum(
                1 for e in sorted_files if e.classification == "unstructured_ln4"
            )

            # Git info.
            git_commit = manifest.git.commit if manifest.git else None
            git_dirty_raw = manifest.git.dirty if manifest.git else None
            git_dirty = int(git_dirty_raw) if git_dirty_raw is not None else None

            # Insert metadata.
            con.execute(
                """
                INSERT INTO index_metadata (
                    id, index_format, schema_version, generator_name, generator_version,
                    corpus_id, corpus_manifest_sha256, corpus_manifest_size_bytes,
                    corpus_created_at, index_created_at,
                    corpus_git_commit, corpus_git_dirty,
                    total_files, structured_files, unstructured_files, build_status
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'complete')
                """,
                (
                    INDEX_FORMAT,
                    SCHEMA_VERSION,
                    GENERATOR_NAME,
                    _GENERATOR_VERSION,
                    manifest.corpus_id,
                    manifest_sha256,
                    manifest_size,
                    manifest.created_at,
                    index_created_at,
                    git_commit,
                    git_dirty,
                    total_files,
                    structured,
                    unstructured,
                ),
            )
    finally:
        con.close()
