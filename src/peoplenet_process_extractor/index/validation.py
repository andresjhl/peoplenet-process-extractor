"""
Validation for structural-index-v1 SQLite databases.

Checks performed:
- File exists and SQLite can be opened.
- PRAGMA integrity_check returns 'ok'.
- PRAGMA foreign_key_check returns no rows.
- Expected tables and columns present.
- Exactly one row in index_metadata.
- build_status = 'complete'.
- index_format and schema_version match expected values.
- All paths are unique.
- All hashes are 64-char hex strings.
- All sizes are non-negative.
- Every structured_ln4 source_file has exactly one structural_element.
- No non-structured source_file has a structural_element.
- Counters in metadata match actual row counts.
- When manifest is provided: all manifest entries are indexed, no extra rows.
- When manifest_sha256 is provided: stored hash matches.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .schema import (
    EXPECTED_COLUMNS,
    EXPECTED_TABLES,
    INDEX_FORMAT,
    SCHEMA_VERSION,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_VALID_CLASSIFICATIONS = frozenset({
    "structured_ln4", "unstructured_ln4", "metadata_json", "other_supported", "ignored",
})


def validate_index(
    db_path: Path,
    manifest: object | None = None,
    manifest_sha256: str | None = None,
) -> list[str]:
    """
    Validate a structural-index-v1 database.

    Returns a list of error strings. Empty list means the index is valid.
    """
    errors: list[str] = []

    if not db_path.exists():
        return [f"Database not found: '{db_path}'."]

    try:
        con = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    except sqlite3.OperationalError as exc:
        return [f"Cannot open database: {exc}"]

    try:
        con.execute("PRAGMA foreign_keys = ON")
        _check_integrity(con, errors)
        if errors:
            return errors
        _check_foreign_keys(con, errors)
        _check_tables(con, errors)
        if errors:
            return errors
        _check_columns(con, errors)
        if errors:
            return errors
        _check_metadata_row(con, errors)
        if errors:
            return errors
        _check_source_files(con, errors)
        _check_structural_consistency(con, errors)
        _check_counter_consistency(con, errors)
        if manifest is not None:
            _check_manifest_coverage(con, manifest, errors)
            _check_manifest_equivalence(con, manifest, errors)
        if manifest_sha256 is not None:
            _check_manifest_hash(con, manifest_sha256, errors)
    finally:
        con.close()

    return errors


def _check_integrity(con: sqlite3.Connection, errors: list[str]) -> None:
    try:
        row = con.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as exc:
        errors.append(f"SQLite integrity_check failed: {exc}")
        return
    if row is None or row[0] != "ok":
        result = row[0] if row else "no result"
        errors.append(f"SQLite integrity_check failed: {result}")


def _check_foreign_keys(con: sqlite3.Connection, errors: list[str]) -> None:
    rows = con.execute("PRAGMA foreign_key_check").fetchall()
    if rows:
        errors.append(f"Foreign key violations found: {len(rows)} row(s).")


def _check_tables(con: sqlite3.Connection, errors: list[str]) -> None:
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    present = {r[0] for r in rows}
    for table in EXPECTED_TABLES:
        if table not in present:
            errors.append(f"Missing table: '{table}'.")


def _check_columns(con: sqlite3.Connection, errors: list[str]) -> None:
    for table, expected_cols in EXPECTED_COLUMNS.items():
        try:
            rows = con.execute(f"PRAGMA table_info({table})").fetchall()  # noqa: S608
        except sqlite3.OperationalError:
            continue
        present = {r[1] for r in rows}
        for col in expected_cols:
            if col not in present:
                errors.append(f"Missing column: '{table}.{col}'.")


def _check_metadata_row(con: sqlite3.Connection, errors: list[str]) -> None:
    rows = con.execute("SELECT COUNT(*) FROM index_metadata").fetchone()
    count = rows[0] if rows else 0
    if count != 1:
        errors.append(f"index_metadata must have exactly 1 row, found {count}.")
        return

    row = con.execute(
        """
        SELECT index_format, schema_version, build_status,
               corpus_manifest_sha256, total_files, structured_files, unstructured_files
        FROM index_metadata WHERE id = 1
        """
    ).fetchone()

    if row is None:
        errors.append("index_metadata row with id=1 not found.")
        return

    idx_format, schema_ver, build_status, manifest_hash, total, structured, unstructured = row

    if idx_format != INDEX_FORMAT:
        errors.append(
            f"Unsupported index_format '{idx_format}'. Expected '{INDEX_FORMAT}'."
        )
    if schema_ver != SCHEMA_VERSION:
        errors.append(
            f"Unsupported schema_version {schema_ver}. Expected {SCHEMA_VERSION}."
        )
    if build_status != "complete":
        errors.append(f"build_status is '{build_status}', expected 'complete'.")
    if not _SHA256_RE.match(manifest_hash or ""):
        errors.append(
            f"corpus_manifest_sha256 '{manifest_hash}' is not a valid 64-char hex string."
        )
    if total < 0:
        errors.append(f"total_files is negative: {total}.")
    if structured < 0:
        errors.append(f"structured_files is negative: {structured}.")
    if unstructured < 0:
        errors.append(f"unstructured_files is negative: {unstructured}.")

    git_dirty_row = con.execute(
        "SELECT corpus_git_dirty FROM index_metadata WHERE id = 1"
    ).fetchone()
    if git_dirty_row:
        git_dirty = git_dirty_row[0]
        if git_dirty is not None and git_dirty not in (0, 1):
            errors.append(
                f"corpus_git_dirty must be 0, 1, or NULL; got {git_dirty!r}."
            )


def _check_source_files(con: sqlite3.Connection, errors: list[str]) -> None:
    rows = con.execute(
        "SELECT path, sha256, size_bytes, classification FROM source_files"
    ).fetchall()

    seen_paths: set[str] = set()
    for path, sha256, size_bytes, classification in rows:
        if path in seen_paths:
            errors.append(f"Duplicate path in source_files: '{path}'.")
        seen_paths.add(path)
        if not _SHA256_RE.match(sha256 or ""):
            errors.append(f"Invalid sha256 for '{path}': '{sha256}'.")
        if size_bytes < 0:
            errors.append(f"Negative size_bytes for '{path}': {size_bytes}.")
        if classification not in _VALID_CLASSIFICATIONS:
            errors.append(f"Invalid classification for '{path}': '{classification}'.")


def _check_structural_consistency(con: sqlite3.Connection, errors: list[str]) -> None:
    # Every structured_ln4 must have exactly one structural_element.
    missing = con.execute(
        """
        SELECT sf.path
        FROM source_files sf
        LEFT JOIN structural_elements se ON se.source_file_id = sf.id
        WHERE sf.classification = 'structured_ln4' AND se.id IS NULL
        """
    ).fetchall()
    for (path,) in missing:
        errors.append(f"structured_ln4 file has no structural_element: '{path}'.")

    # No non-structured file may have a structural_element.
    extra = con.execute(
        """
        SELECT sf.path
        FROM source_files sf
        JOIN structural_elements se ON se.source_file_id = sf.id
        WHERE sf.classification != 'structured_ln4'
        """
    ).fetchall()
    for (path,) in extra:
        errors.append(
            f"Non-structured file '{path}' has an unexpected structural_element."
        )


def _check_counter_consistency(con: sqlite3.Connection, errors: list[str]) -> None:
    actual_total = con.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
    actual_structured = con.execute(
        "SELECT COUNT(*) FROM source_files WHERE classification = 'structured_ln4'"
    ).fetchone()[0]
    actual_unstructured = con.execute(
        "SELECT COUNT(*) FROM source_files WHERE classification = 'unstructured_ln4'"
    ).fetchone()[0]

    row = con.execute(
        "SELECT total_files, structured_files, unstructured_files FROM index_metadata WHERE id = 1"
    ).fetchone()
    if row is None:
        return

    stored_total, stored_structured, stored_unstructured = row
    if stored_total != actual_total:
        errors.append(
            f"Metadata total_files={stored_total} but source_files has {actual_total} rows."
        )
    if stored_structured != actual_structured:
        errors.append(
            f"Metadata structured_files={stored_structured} "
            f"but source_files has {actual_structured} structured_ln4 rows."
        )
    if stored_unstructured != actual_unstructured:
        errors.append(
            f"Metadata unstructured_files={stored_unstructured} "
            f"but source_files has {actual_unstructured} unstructured_ln4 rows."
        )


def _check_manifest_coverage(con: sqlite3.Connection, manifest: object, errors: list[str]) -> None:
    manifest_paths = {entry.path for entry in manifest.files}
    db_paths_rows = con.execute("SELECT path FROM source_files").fetchall()
    db_paths = {r[0] for r in db_paths_rows}

    missing = manifest_paths - db_paths
    for path in sorted(missing):
        errors.append(f"Manifest entry not indexed: '{path}'.")

    extra = db_paths - manifest_paths
    for path in sorted(extra):
        errors.append(f"Indexed path not in manifest: '{path}'.")


def _check_manifest_hash(con: sqlite3.Connection, expected_sha256: str, errors: list[str]) -> None:
    row = con.execute(
        "SELECT corpus_manifest_sha256 FROM index_metadata WHERE id = 1"
    ).fetchone()
    if row is None:
        return
    stored = row[0]
    if stored != expected_sha256:
        errors.append(
            f"Manifest SHA-256 mismatch: stored='{stored}', expected='{expected_sha256}'."
        )


def _check_manifest_equivalence(
    con: sqlite3.Connection, manifest: object, errors: list[str]
) -> None:
    """Field-by-field comparison between manifest entries and every indexed row."""
    # --- source_files ---
    sf_rows = con.execute(
        "SELECT path, sha256, size_bytes, extension, source_root, classification, warning_count "
        "FROM source_files"
    ).fetchall()
    db_files: dict[str, tuple] = {
        r[0]: r[1:] for r in sf_rows
    }

    # --- structural_elements by path ---
    se_rows = con.execute(
        """
        SELECT sf.path, se.meta4object, se.item_type, se.item_name, se.rule_id, se.rule_date
        FROM structural_elements se
        JOIN source_files sf ON sf.id = se.source_file_id
        """
    ).fetchall()
    db_elements: dict[str, tuple] = {r[0]: r[1:] for r in se_rows}

    # --- file_warnings by path: fetch (sequence, message) tuples in sequence order ---
    fw_rows = con.execute(
        """
        SELECT sf.path, fw.sequence, fw.message
        FROM file_warnings fw
        JOIN source_files sf ON sf.id = fw.source_file_id
        ORDER BY sf.path, fw.sequence
        """
    ).fetchall()
    db_warnings: dict[str, list[tuple[int, str]]] = {}
    for path, seq, msg in fw_rows:
        db_warnings.setdefault(path, []).append((seq, msg))

    # --- index_metadata identity fields ---
    meta_row = con.execute(
        "SELECT corpus_id, corpus_created_at FROM index_metadata WHERE id = 1"
    ).fetchone()
    if meta_row:
        stored_corpus_id, stored_created_at = meta_row
        if stored_corpus_id != manifest.corpus_id:
            errors.append(
                f"index_metadata.corpus_id mismatch: "
                f"manifest={manifest.corpus_id!r}, index={stored_corpus_id!r}."
            )
        if stored_created_at != manifest.created_at:
            errors.append(
                f"index_metadata.corpus_created_at mismatch: "
                f"manifest={manifest.created_at!r}, index={stored_created_at!r}."
            )

    for entry in manifest.files:
        path = entry.path
        if path not in db_files:
            continue  # already reported by _check_manifest_coverage

        sha256, size_bytes, extension, source_root, classification, warning_count = db_files[path]

        for field, expected, actual in [
            ("sha256", entry.sha256, sha256),
            ("size_bytes", entry.size_bytes, size_bytes),
            ("extension", entry.extension, extension),
            ("source_root", entry.source_root, source_root),
            ("classification", entry.classification, classification),
            ("warning_count", len(entry.warnings), warning_count),
        ]:
            if expected != actual:
                errors.append(
                    f"Field mismatch for '{path}': {field}: "
                    f"manifest={expected!r}, index={actual!r}."
                )

        # Check structural element fields for structured_ln4.
        if entry.classification == "structured_ln4" and entry.structure is not None:
            if path in db_elements:
                meta4object, item_type, item_name, rule_id, rule_date = db_elements[path]
                s = entry.structure
                for field, expected, actual in [
                    ("meta4object", s.meta4object, meta4object),
                    ("item_type", s.item_type, item_type),
                    ("item_name", s.item_name, item_name),
                    ("rule_id", s.rule_id, rule_id),
                    ("rule_date", s.rule_date, rule_date),
                ]:
                    if expected != actual:
                        errors.append(
                            f"Structural field mismatch for '{path}': {field}: "
                            f"manifest={expected!r}, index={actual!r}."
                        )

        # Compare warnings as (sequence, message) tuples; expected sequence is 0,1,...,N-1.
        expected_tuples = list(enumerate(entry.warnings))  # [(0,msg0),(1,msg1),...]
        actual_tuples = db_warnings.get(path, [])
        if expected_tuples != actual_tuples:
            errors.append(
                f"Warnings mismatch for '{path}': "
                f"expected {expected_tuples!r}, got {actual_tuples!r}."
            )
