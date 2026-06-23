"""
SQLite DDL for structural-index-v1.

Schema version: 1
IDs in source_files are assigned by stable path order (not random).
IDs are internal bookkeeping; they do not constitute business identity.
"""

INDEX_FORMAT = "structural-index-v1"
SCHEMA_VERSION = 1
GENERATOR_NAME = "peoplenet-process-extractor"

CREATE_INDEX_METADATA = """
CREATE TABLE IF NOT EXISTS index_metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    index_format TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
    generator_name TEXT NOT NULL,
    generator_version TEXT NOT NULL,
    corpus_id TEXT NOT NULL,
    corpus_manifest_sha256 TEXT NOT NULL CHECK (length(corpus_manifest_sha256) = 64),
    corpus_manifest_size_bytes INTEGER NOT NULL CHECK (corpus_manifest_size_bytes >= 0),
    corpus_created_at TEXT NOT NULL,
    index_created_at TEXT NOT NULL,
    corpus_git_commit TEXT,
    corpus_git_dirty INTEGER CHECK (corpus_git_dirty IS NULL OR corpus_git_dirty IN (0, 1)),
    total_files INTEGER NOT NULL CHECK (total_files >= 0),
    structured_files INTEGER NOT NULL CHECK (structured_files >= 0),
    unstructured_files INTEGER NOT NULL CHECK (unstructured_files >= 0),
    build_status TEXT NOT NULL CHECK (build_status IN ('complete', 'failed'))
)
"""

CREATE_SOURCE_FILES = """
CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    extension TEXT NOT NULL,
    source_root TEXT,
    classification TEXT NOT NULL CHECK (classification IN (
        'structured_ln4', 'unstructured_ln4', 'metadata_json', 'other_supported', 'ignored'
    )),
    warning_count INTEGER NOT NULL DEFAULT 0 CHECK (warning_count >= 0)
)
"""

CREATE_STRUCTURAL_ELEMENTS = """
CREATE TABLE IF NOT EXISTS structural_elements (
    id INTEGER PRIMARY KEY,
    source_file_id INTEGER NOT NULL UNIQUE REFERENCES source_files(id),
    meta4object TEXT NOT NULL,
    item_type TEXT NOT NULL,
    item_name TEXT NOT NULL,
    rule_id TEXT,
    rule_date TEXT
)
"""

CREATE_FILE_WARNINGS = """
CREATE TABLE IF NOT EXISTS file_warnings (
    id INTEGER PRIMARY KEY,
    source_file_id INTEGER NOT NULL REFERENCES source_files(id),
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    message TEXT NOT NULL,
    UNIQUE (source_file_id, sequence)
)
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_source_files_classification ON source_files(classification)",
    "CREATE INDEX IF NOT EXISTS idx_source_files_source_root ON source_files(source_root)",
    "CREATE INDEX IF NOT EXISTS idx_structural_elements_meta4object ON structural_elements(meta4object)",
    "CREATE INDEX IF NOT EXISTS idx_structural_elements_item_type ON structural_elements(item_type)",
    "CREATE INDEX IF NOT EXISTS idx_structural_elements_item_name ON structural_elements(item_name)",
    "CREATE INDEX IF NOT EXISTS idx_structural_elements_combined "
    "ON structural_elements(meta4object, item_type, item_name)",
    "CREATE INDEX IF NOT EXISTS idx_file_warnings_source_file_id ON file_warnings(source_file_id)",
]

EXPECTED_TABLES: frozenset[str] = frozenset(
    {"index_metadata", "source_files", "structural_elements", "file_warnings"}
)

EXPECTED_COLUMNS: dict[str, frozenset[str]] = {
    "index_metadata": frozenset({
        "id", "index_format", "schema_version", "generator_name", "generator_version",
        "corpus_id", "corpus_manifest_sha256", "corpus_manifest_size_bytes",
        "corpus_created_at", "index_created_at", "corpus_git_commit", "corpus_git_dirty",
        "total_files", "structured_files", "unstructured_files", "build_status",
    }),
    "source_files": frozenset({
        "id", "path", "sha256", "size_bytes", "extension", "source_root",
        "classification", "warning_count",
    }),
    "structural_elements": frozenset({
        "id", "source_file_id", "meta4object", "item_type", "item_name", "rule_id", "rule_date",
    }),
    "file_warnings": frozenset({
        "id", "source_file_id", "sequence", "message",
    }),
}
