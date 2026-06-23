"""
Read-only queries for structural-index-v1.

All queries use parameterized SQL — column/table names are internal constants,
not derived from user input.  No free-form SQL is exposed.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileRow:
    path: str
    sha256: str
    size_bytes: int
    extension: str
    source_root: str | None
    classification: str
    warning_count: int


@dataclass
class ElementRow:
    path: str
    source_root: str | None
    meta4object: str
    item_type: str
    item_name: str
    rule_id: str | None
    rule_date: str | None


@dataclass
class StatsResult:
    total_files: int
    structured_files: int
    unstructured_files: int
    by_classification: dict[str, int]
    by_source_root: dict[str, int]
    by_item_type: dict[str, int]


def _open_ro(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def query_files(
    db_path: Path,
    *,
    path: str | None = None,
    classification: str | None = None,
    source_root: str | None = None,
    extension: str | None = None,
) -> list[FileRow]:
    """
    Return source_files rows matching the given filters, ordered by path.
    All filters are optional and combined with AND.
    """
    clauses: list[str] = []
    params: list[object] = []

    if path is not None:
        clauses.append("path = ?")
        params.append(path)
    if classification is not None:
        clauses.append("classification = ?")
        params.append(classification)
    if source_root is not None:
        clauses.append("source_root = ?")
        params.append(source_root)
    if extension is not None:
        clauses.append("extension = ?")
        params.append(extension)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT path, sha256, size_bytes, extension, source_root, classification, warning_count
        FROM source_files
        {where}
        ORDER BY path
    """

    con = _open_ro(db_path)
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()

    return [
        FileRow(
            path=r[0],
            sha256=r[1],
            size_bytes=r[2],
            extension=r[3],
            source_root=r[4],
            classification=r[5],
            warning_count=r[6],
        )
        for r in rows
    ]


def query_elements(
    db_path: Path,
    *,
    meta4object: str | None = None,
    item_type: str | None = None,
    item_name: str | None = None,
    rule_id: str | None = None,
    source_root: str | None = None,
) -> list[ElementRow]:
    """
    Return structural_elements joined with source_files, matching filters.

    Ordered by (meta4object, item_type, item_name, rule_id, path).
    All filters are optional and combined with AND.
    """
    clauses: list[str] = []
    params: list[object] = []

    if meta4object is not None:
        clauses.append("se.meta4object = ?")
        params.append(meta4object)
    if item_type is not None:
        clauses.append("se.item_type = ?")
        params.append(item_type)
    if item_name is not None:
        clauses.append("se.item_name = ?")
        params.append(item_name)
    if rule_id is not None:
        clauses.append("se.rule_id = ?")
        params.append(rule_id)
    if source_root is not None:
        clauses.append("sf.source_root = ?")
        params.append(source_root)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT sf.path, sf.source_root,
               se.meta4object, se.item_type, se.item_name, se.rule_id, se.rule_date
        FROM structural_elements se
        JOIN source_files sf ON sf.id = se.source_file_id
        {where}
        ORDER BY se.meta4object, se.item_type, se.item_name,
                 COALESCE(se.rule_id, ''), sf.path
    """

    con = _open_ro(db_path)
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()

    return [
        ElementRow(
            path=r[0],
            source_root=r[1],
            meta4object=r[2],
            item_type=r[3],
            item_name=r[4],
            rule_id=r[5],
            rule_date=r[6],
        )
        for r in rows
    ]


def query_stats(db_path: Path) -> StatsResult:
    """Return aggregate statistics from the index."""
    con = _open_ro(db_path)
    try:
        meta_row = con.execute(
            "SELECT total_files, structured_files, unstructured_files FROM index_metadata WHERE id = 1"
        ).fetchone()
        total = meta_row[0] if meta_row else 0
        structured = meta_row[1] if meta_row else 0
        unstructured = meta_row[2] if meta_row else 0

        class_rows = con.execute(
            "SELECT classification, COUNT(*) FROM source_files GROUP BY classification ORDER BY classification"
        ).fetchall()
        by_classification = {r[0]: r[1] for r in class_rows}

        root_rows = con.execute(
            "SELECT COALESCE(source_root, ''), COUNT(*) FROM source_files "
            "GROUP BY source_root ORDER BY source_root"
        ).fetchall()
        by_source_root = {r[0]: r[1] for r in root_rows}

        type_rows = con.execute(
            "SELECT item_type, COUNT(*) FROM structural_elements GROUP BY item_type ORDER BY item_type"
        ).fetchall()
        by_item_type = {r[0]: r[1] for r in type_rows}
    finally:
        con.close()

    return StatsResult(
        total_files=total,
        structured_files=structured,
        unstructured_files=unstructured,
        by_classification=by_classification,
        by_source_root=by_source_root,
        by_item_type=by_item_type,
    )


def read_metadata(db_path: Path) -> dict[str, object]:
    """Return the single index_metadata row as a dict (for verify and export)."""
    con = _open_ro(db_path)
    try:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM index_metadata WHERE id = 1").fetchone()
        if row is None:
            return {}
        return dict(row)
    finally:
        con.close()


def logical_export(db_path: Path) -> dict[str, object]:
    """
    Return the complete deterministic logical representation of the index.

    Designed for reproducibility comparisons and golden tests.  All data that
    uniquely describes the index content is included, with two exceptions:

    Excluded from *metadata* (environment-dependent, not derivable from the corpus):
      - ``id``                 — metadata row PK, always 1, carries no information.
      - ``corpus_git_commit``  — depends on the live git state of the corpus.
      - ``corpus_git_dirty``   — depends on the live git state of the corpus.

    All other metadata fields are included:
      ``generator_version``, ``index_created_at``, ``index_format``,
      ``schema_version``, ``generator_name``, ``corpus_id``,
      ``corpus_manifest_sha256``, ``corpus_manifest_size_bytes``,
      ``corpus_created_at``, ``total_files``, ``structured_files``,
      ``unstructured_files``, ``build_status``.

    Each ``source_files`` entry includes the stable ``id`` (assigned in ascending
    path order), all scalar columns, and a ``warnings`` list of
    ``{"sequence": N, "message": "..."}`` objects ordered by sequence.
    """
    meta = read_metadata(db_path)

    # Exclude only the fields that are environment-dependent.
    # corpus_manifest_sha256/size_bytes, generator_version, and index_created_at
    # are all deterministic when the build uses a fixed clock and a non-git corpus.
    _UNSTABLE = {"id", "corpus_git_commit", "corpus_git_dirty"}
    stable_meta = {k: v for k, v in meta.items() if k not in _UNSTABLE}

    elements = query_elements(db_path)

    con = _open_ro(db_path)
    try:
        sf_rows = con.execute(
            """
            SELECT id, path, sha256, size_bytes, extension,
                   source_root, classification, warning_count
            FROM source_files
            ORDER BY path
            """
        ).fetchall()

        fw_rows = con.execute(
            """
            SELECT sf.path, fw.sequence, fw.message
            FROM file_warnings fw
            JOIN source_files sf ON sf.id = fw.source_file_id
            ORDER BY sf.path, fw.sequence
            """
        ).fetchall()
    finally:
        con.close()

    warnings_by_path: dict[str, list[dict[str, object]]] = {}
    for path, seq, msg in fw_rows:
        warnings_by_path.setdefault(path, []).append({"sequence": seq, "message": msg})

    return {
        "metadata": stable_meta,
        "source_files": [
            {
                "id": row[0],
                "path": row[1],
                "sha256": row[2],
                "size_bytes": row[3],
                "extension": row[4],
                "source_root": row[5],
                "classification": row[6],
                "warning_count": row[7],
                "warnings": warnings_by_path.get(row[1], []),
            }
            for row in sf_rows
        ],
        "structural_elements": [
            {
                "path": e.path,
                "meta4object": e.meta4object,
                "item_type": e.item_type,
                "item_name": e.item_name,
                "rule_id": e.rule_id,
                "rule_date": e.rule_date,
            }
            for e in elements
        ],
    }
