from dataclasses import dataclass, field

SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})


@dataclass
class Ln4Structure:
    meta4object: str
    item_type: str
    item_name: str
    rule_id: str | None = None
    rule_date: str | None = None


@dataclass
class FileEntry:
    path: str
    sha256: str
    size_bytes: int
    extension: str
    source_root: str | None
    classification: str
    structure: Ln4Structure | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class GitInfo:
    commit: str | None
    dirty: bool | None


@dataclass
class RootInfo:
    label: str
    path_policy: str = "relative"


@dataclass
class CorpusSummary:
    total_files: int
    total_bytes: int
    structured_files: int
    unstructured_files: int
    by_source_root: dict[str, int] = field(default_factory=dict)
    by_extension: dict[str, int] = field(default_factory=dict)
    by_classification: dict[str, int] = field(default_factory=dict)


@dataclass
class CorpusManifest:
    schema_version: str
    corpus_id: str
    created_at: str
    root: RootInfo
    git: GitInfo
    included_source_roots: list[str]
    files: list[FileEntry]
    summary: CorpusSummary
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
