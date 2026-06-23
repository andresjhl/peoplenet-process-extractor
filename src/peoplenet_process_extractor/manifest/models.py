from dataclasses import dataclass, field

SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})


@dataclass
class ScenarioRef:
    path: str
    sha256: str
    size_bytes: int
    scenario_id: str
    schema_version: str


@dataclass
class SourceFile:
    id: str
    kind: str
    path: str
    sha256: str | None
    size_bytes: int | None
    exists: bool
    required: bool
    description: str | None = None


@dataclass
class Tool:
    id: str
    name: str
    version: str
    command: str | None = None
    git_commit: str | None = None
    schema_info: str | None = None


@dataclass
class Artifact:
    id: str
    kind: str
    path: str
    sha256: str | None
    size_bytes: int | None
    producer: str | None
    derived_from: list[str] = field(default_factory=list)
    status: str = "planned"


@dataclass
class Event:
    sequence: int
    type: str
    timestamp: str
    message: str
    reference_id: str | None = None


@dataclass
class ManifestEntry:
    code: str
    message: str
    reference_id: str | None = None


@dataclass
class RunManifest:
    schema_version: str
    run_id: str
    status: str
    scenario: ScenarioRef
    sources: list[SourceFile] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    warnings: list[ManifestEntry] = field(default_factory=list)
    errors: list[ManifestEntry] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
