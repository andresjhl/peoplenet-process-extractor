from dataclasses import dataclass, field
from typing import Any

from .enums import Source, Status

SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})


@dataclass
class Process:
    id: str
    source: Source
    status: Status


@dataclass
class EntryPoint:
    meta4object: str
    node: str
    method: str
    arguments: list[Any] = field(default_factory=list)


@dataclass
class TypedValue:
    name: str
    value: Any
    type: str
    source: Source
    status: Status


@dataclass
class PropertyBinding:
    property: str
    input: str


@dataclass
class RuntimeValue:
    name: str
    value: Any
    type: str
    source: Source
    status: Status
    evidence: str | None = None
    expression: str | None = None


@dataclass
class ScopeMethod:
    name: str
    source: Source
    status: Status
    reason: str | None = None


@dataclass
class AnalysisScope:
    methods: list[ScopeMethod] = field(default_factory=list)


@dataclass
class SourceRef:
    legacy_file: str | None = None
    original_call: str | None = None
    hash: str | None = None
    source_type: str | None = None


@dataclass
class Scenario:
    schema_version: str
    scenario_id: str
    process: Process
    entry_point: EntryPoint
    entry_inputs: list[TypedValue] = field(default_factory=list)
    property_bindings: list[PropertyBinding] = field(default_factory=list)
    runtime_values: list[RuntimeValue] = field(default_factory=list)
    flags: list[TypedValue] = field(default_factory=list)
    configuration: list[TypedValue] = field(default_factory=list)
    analysis_scope: AnalysisScope = field(default_factory=AnalysisScope)
    notes: list[str] = field(default_factory=list)
    source_files: SourceRef = field(default_factory=SourceRef)
