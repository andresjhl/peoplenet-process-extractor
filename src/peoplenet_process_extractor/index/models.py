from dataclasses import dataclass


@dataclass
class IndexMetadata:
    index_format: str
    schema_version: int
    generator_name: str
    generator_version: str
    corpus_id: str
    corpus_manifest_sha256: str
    corpus_manifest_size_bytes: int
    corpus_created_at: str
    index_created_at: str
    corpus_git_commit: str | None
    corpus_git_dirty: bool | None
    total_files: int
    structured_files: int
    unstructured_files: int
    build_status: str


@dataclass
class SourceFileRecord:
    id: int
    path: str
    sha256: str
    size_bytes: int
    extension: str
    source_root: str | None
    classification: str
    warning_count: int


@dataclass
class StructuralElementRecord:
    id: int
    source_file_id: int
    meta4object: str
    item_type: str
    item_name: str
    rule_id: str | None
    rule_date: str | None


@dataclass
class FileWarningRecord:
    id: int
    source_file_id: int
    sequence: int
    message: str
