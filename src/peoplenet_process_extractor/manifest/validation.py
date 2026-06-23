import re
from dataclasses import dataclass
from datetime import datetime

from .enums import ArtifactKind, ArtifactStatus, EventType, RunStatus, SourceKind
from .models import SUPPORTED_SCHEMA_VERSIONS, RunManifest

# Exactly 64 lowercase hex characters.
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Safe directory name: starts with alphanumeric, then alphanumeric / dots / underscores / hyphens.
# No path separators, no OS-special characters.
_RUN_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


@dataclass
class ValidationError:
    code: str
    message: str
    field: str | None = None


def validate(manifest: RunManifest) -> list[ValidationError]:
    errors: list[ValidationError] = []

    _check_schema_version(manifest, errors)
    _check_run_id(manifest, errors)
    _check_status(manifest, errors)
    _check_scenario_ref(manifest, errors)

    source_ids = _check_sources(manifest, errors)
    tool_ids = _check_tools(manifest, errors)
    artifact_ids = _check_artifacts(manifest, errors, tool_ids)

    # Global ID uniqueness: sources and artifacts share one namespace.
    _check_global_id_uniqueness(source_ids, artifact_ids, errors)

    _check_scenario_source_consistency(manifest, errors)
    _check_derived_from(manifest, errors, source_ids | artifact_ids)
    _check_events(manifest, errors, source_ids | artifact_ids | tool_ids)
    _check_status_constraints(manifest, errors)
    _check_timestamps(manifest, errors)

    return errors


# ---------------------------------------------------------------------------
# Top-level fields
# ---------------------------------------------------------------------------


def _check_schema_version(manifest: RunManifest, errors: list[ValidationError]) -> None:
    if manifest.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(ValidationError(
            code="unsupported_schema_version",
            message=(
                f"schema_version {manifest.schema_version!r} is not supported. "
                f"Supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
            ),
            field="schema_version",
        ))


def _check_run_id(manifest: RunManifest, errors: list[ValidationError]) -> None:
    if not manifest.run_id:
        errors.append(ValidationError(
            code="empty_run_id",
            message="run_id must not be empty",
            field="run_id",
        ))
    elif not _RUN_ID_RE.match(manifest.run_id):
        errors.append(ValidationError(
            code="invalid_run_id",
            message=f"run_id {manifest.run_id!r} is not safe as a directory name",
            field="run_id",
        ))


def _check_status(manifest: RunManifest, errors: list[ValidationError]) -> None:
    try:
        RunStatus(manifest.status)
    except ValueError:
        errors.append(ValidationError(
            code="invalid_run_status",
            message=f"status {manifest.status!r} is not a valid RunStatus",
            field="status",
        ))


# ---------------------------------------------------------------------------
# Scenario reference
# ---------------------------------------------------------------------------


def _check_scenario_ref(manifest: RunManifest, errors: list[ValidationError]) -> None:
    _portable_path("scenario.path", manifest.scenario.path, errors)
    _sha256_field("scenario.sha256", manifest.scenario.sha256, errors, required=True)
    if manifest.scenario.size_bytes < 0:
        errors.append(ValidationError(
            code="negative_size",
            message="scenario.size_bytes must be non-negative",
            field="scenario.size_bytes",
        ))


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


def _check_sources(manifest: RunManifest, errors: list[ValidationError]) -> set[str]:
    seen: set[str] = set()
    for i, src in enumerate(manifest.sources):
        prefix = f"sources[{i}]"
        if src.id in seen:
            errors.append(ValidationError(
                code="duplicate_source_id",
                message=f"Duplicate source id {src.id!r}",
                field=f"{prefix}.id",
            ))
        seen.add(src.id)

        _enum_field(f"{prefix}.kind", src.kind, SourceKind, "invalid_source_kind", errors)
        _portable_path(f"{prefix}.path", src.path, errors)
        _sha256_field(f"{prefix}.sha256", src.sha256, errors, required=False)
        _size_field(f"{prefix}.size_bytes", src.size_bytes, errors, required=False)

        if src.exists:
            if src.sha256 is None:
                errors.append(ValidationError(
                    code="missing_hash",
                    message=f"{prefix}: sha256 is required when exists=true",
                    field=f"{prefix}.sha256",
                ))
            if src.size_bytes is None:
                errors.append(ValidationError(
                    code="missing_size",
                    message=f"{prefix}: size_bytes is required when exists=true",
                    field=f"{prefix}.size_bytes",
                ))

    return seen


# ---------------------------------------------------------------------------
# Scenario-source consistency
# ---------------------------------------------------------------------------


def _check_scenario_source_consistency(
    manifest: RunManifest, errors: list[ValidationError]
) -> None:
    """
    Exactly one source must have kind='scenario', and its path/sha256/size_bytes
    must match manifest.scenario exactly.
    """
    scen_sources = [s for s in manifest.sources if s.kind == SourceKind.SCENARIO.value]

    if len(scen_sources) == 0:
        errors.append(ValidationError(
            code="no_scenario_source",
            message=(
                "sources must contain exactly one entry with kind='scenario' "
                "matching the scenario block"
            ),
            field="sources",
        ))
        return

    if len(scen_sources) > 1:
        errors.append(ValidationError(
            code="multiple_scenario_sources",
            message=(
                f"sources contains {len(scen_sources)} entries with kind='scenario', "
                "expected exactly one"
            ),
            field="sources",
        ))
        return

    src = scen_sources[0]
    if src.path != manifest.scenario.path:
        errors.append(ValidationError(
            code="scenario_source_path_mismatch",
            message=(
                f"scenario source path {src.path!r} does not match "
                f"scenario.path {manifest.scenario.path!r}"
            ),
            field="sources",
        ))
    if src.sha256 != manifest.scenario.sha256:
        errors.append(ValidationError(
            code="scenario_source_sha256_mismatch",
            message=(
                f"scenario source sha256 does not match scenario.sha256 "
                f"({src.sha256!r} vs {manifest.scenario.sha256!r})"
            ),
            field="sources",
        ))
    if src.size_bytes != manifest.scenario.size_bytes:
        errors.append(ValidationError(
            code="scenario_source_size_mismatch",
            message=(
                f"scenario source size_bytes {src.size_bytes} does not match "
                f"scenario.size_bytes {manifest.scenario.size_bytes}"
            ),
            field="sources",
        ))


# ---------------------------------------------------------------------------
# Global ID uniqueness (sources + artifacts share one namespace)
# ---------------------------------------------------------------------------


def _check_global_id_uniqueness(
    source_ids: set[str],
    artifact_ids: set[str],
    errors: list[ValidationError],
) -> None:
    overlap = source_ids & artifact_ids
    for shared_id in sorted(overlap):
        errors.append(ValidationError(
            code="duplicate_global_id",
            message=(
                f"ID {shared_id!r} is used by both a source and an artifact. "
                "Source and artifact IDs share a single namespace."
            ),
            field="id",
        ))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def _check_tools(manifest: RunManifest, errors: list[ValidationError]) -> set[str]:
    seen: set[str] = set()
    for i, tool in enumerate(manifest.tools):
        prefix = f"tools[{i}]"
        if tool.id in seen:
            errors.append(ValidationError(
                code="duplicate_tool_id",
                message=f"Duplicate tool id {tool.id!r}",
                field=f"{prefix}.id",
            ))
        seen.add(tool.id)
    return seen


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def _check_artifacts(
    manifest: RunManifest,
    errors: list[ValidationError],
    tool_ids: set[str],
) -> set[str]:
    seen: set[str] = set()
    for i, art in enumerate(manifest.artifacts):
        prefix = f"artifacts[{i}]"
        if art.id in seen:
            errors.append(ValidationError(
                code="duplicate_artifact_id",
                message=f"Duplicate artifact id {art.id!r}",
                field=f"{prefix}.id",
            ))
        seen.add(art.id)

        _enum_field(f"{prefix}.kind", art.kind, ArtifactKind, "invalid_artifact_kind", errors)
        _enum_field(f"{prefix}.status", art.status, ArtifactStatus, "invalid_artifact_status", errors)
        _portable_path(f"{prefix}.path", art.path, errors)
        _sha256_field(f"{prefix}.sha256", art.sha256, errors, required=False)
        _size_field(f"{prefix}.size_bytes", art.size_bytes, errors, required=False)

        if art.status == ArtifactStatus.GENERATED.value:
            if art.sha256 is None:
                errors.append(ValidationError(
                    code="missing_hash",
                    message=f"{prefix}: sha256 is required when status=generated",
                    field=f"{prefix}.sha256",
                ))
            if art.size_bytes is None:
                errors.append(ValidationError(
                    code="missing_size",
                    message=f"{prefix}: size_bytes is required when status=generated",
                    field=f"{prefix}.size_bytes",
                ))

        if art.producer is not None and art.producer not in tool_ids:
            errors.append(ValidationError(
                code="unknown_producer",
                message=f"{prefix}.producer {art.producer!r} does not reference a known tool",
                field=f"{prefix}.producer",
            ))

    return seen


# ---------------------------------------------------------------------------
# derived_from cross-references
# ---------------------------------------------------------------------------


def _check_derived_from(
    manifest: RunManifest,
    errors: list[ValidationError],
    provenance_ids: set[str],
) -> None:
    for i, art in enumerate(manifest.artifacts):
        seen_refs: set[str] = set()
        for ref_id in art.derived_from:
            if ref_id == art.id:
                errors.append(ValidationError(
                    code="self_reference_in_derived_from",
                    message=f"artifacts[{i}].derived_from contains self-reference {ref_id!r}",
                    field=f"artifacts[{i}].derived_from",
                ))
                seen_refs.add(ref_id)
                continue

            if ref_id in seen_refs:
                errors.append(ValidationError(
                    code="duplicate_derived_from",
                    message=f"artifacts[{i}].derived_from contains duplicate id {ref_id!r}",
                    field=f"artifacts[{i}].derived_from",
                ))
            seen_refs.add(ref_id)

            if ref_id not in provenance_ids:
                errors.append(ValidationError(
                    code="unknown_derived_from",
                    message=(
                        f"artifacts[{i}].derived_from references unknown id {ref_id!r}. "
                        "Must reference a source or artifact id."
                    ),
                    field=f"artifacts[{i}].derived_from",
                ))


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def _check_events(
    manifest: RunManifest,
    errors: list[ValidationError],
    all_ids: set[str],
) -> None:
    last_seq = 0
    seen_seqs: set[int] = set()

    for i, evt in enumerate(manifest.events):
        prefix = f"events[{i}]"
        seq = evt.sequence
        seq_valid = True

        # Type guard must come first: numeric comparisons on non-int values raise TypeError.
        # bool is a subclass of int in Python, so it must be excluded explicitly.
        if not isinstance(seq, int) or isinstance(seq, bool):
            seq_valid = False
            errors.append(ValidationError(
                code="invalid_event_sequence",
                message=(
                    f"{prefix}.sequence must be a positive integer, "
                    f"got {seq!r} ({type(seq).__name__})"
                ),
                field=f"{prefix}.sequence",
            ))
        elif seq <= 0:
            seq_valid = False
            errors.append(ValidationError(
                code="invalid_event_sequence",
                message=f"{prefix}.sequence must be a positive integer, got {seq!r}",
                field=f"{prefix}.sequence",
            ))
        elif seq in seen_seqs:
            seq_valid = False
            errors.append(ValidationError(
                code="duplicate_event_sequence",
                message=f"{prefix}.sequence {seq} is not unique",
                field=f"{prefix}.sequence",
            ))
        elif seq <= last_seq:
            seq_valid = False
            errors.append(ValidationError(
                code="non_increasing_sequence",
                message=(
                    f"{prefix}.sequence {seq} is not strictly greater than "
                    f"the previous sequence {last_seq}"
                ),
                field=f"{prefix}.sequence",
            ))

        if seq_valid:
            last_seq = seq
            seen_seqs.add(seq)
        # Invalid-type entries are intentionally excluded from seen_seqs so that
        # subsequent events are not incorrectly flagged as duplicates of an invalid entry.

        _enum_field(f"{prefix}.type", evt.type, EventType, "invalid_event_type", errors)

        if not _parse_iso_utc(evt.timestamp):
            errors.append(ValidationError(
                code="invalid_event_timestamp",
                message=(
                    f"{prefix}.timestamp {evt.timestamp!r} is not a valid "
                    "ISO 8601 timestamp with explicit timezone"
                ),
                field=f"{prefix}.timestamp",
            ))

        if evt.reference_id is not None and evt.reference_id not in all_ids:
            errors.append(ValidationError(
                code="unknown_event_reference",
                message=(
                    f"{prefix}.reference_id {evt.reference_id!r} does not reference "
                    "a known source, artifact, or tool"
                ),
                field=f"{prefix}.reference_id",
            ))


# ---------------------------------------------------------------------------
# Status-level constraints
# ---------------------------------------------------------------------------


def _check_status_constraints(manifest: RunManifest, errors: list[ValidationError]) -> None:
    error_events = [e for e in manifest.events if e.type == EventType.ERROR.value]

    if manifest.status == RunStatus.SUCCEEDED.value:
        if manifest.errors or error_events:
            errors.append(ValidationError(
                code="succeeded_with_errors",
                message="status 'succeeded' is incompatible with errors or error events",
                field="status",
            ))

    if manifest.status == RunStatus.FAILED.value:
        if not manifest.errors and not error_events:
            errors.append(ValidationError(
                code="failed_without_errors",
                message="status 'failed' requires at least one error or error event",
                field="status",
            ))


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


def _check_timestamps(manifest: RunManifest, errors: list[ValidationError]) -> None:
    started = None
    finished = None

    if manifest.started_at:
        started = _parse_iso_utc(manifest.started_at)
        if started is None:
            errors.append(ValidationError(
                code="invalid_timestamp",
                message=(
                    f"started_at {manifest.started_at!r} is not a valid "
                    "ISO 8601 timestamp with explicit timezone"
                ),
                field="started_at",
            ))

    if manifest.finished_at:
        finished = _parse_iso_utc(manifest.finished_at)
        if finished is None:
            errors.append(ValidationError(
                code="invalid_timestamp",
                message=(
                    f"finished_at {manifest.finished_at!r} is not a valid "
                    "ISO 8601 timestamp with explicit timezone"
                ),
                field="finished_at",
            ))

    if started is not None and finished is not None:
        if finished < started:
            errors.append(ValidationError(
                code="incoherent_timestamps",
                message="finished_at is before started_at",
                field="finished_at",
            ))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _parse_iso_utc(value: str) -> datetime | None:
    """
    Parse ISO 8601 timestamp with required explicit timezone.
    Accepts 'Z' suffix and offset forms like '+05:30'.
    Returns None if value is not a valid timezone-aware timestamp.
    """
    s = value
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None  # naive timestamps are rejected
    return dt


def _enum_field(
    field: str,
    value: str,
    cls: type,
    code: str,
    errors: list[ValidationError],
) -> None:
    try:
        cls(value)
    except ValueError:
        valid = [m.value for m in cls]
        errors.append(ValidationError(
            code=code,
            message=f"{field} {value!r} is not valid. Valid values: {valid}",
            field=field,
        ))


def _sha256_field(
    field: str,
    value: str | None,
    errors: list[ValidationError],
    *,
    required: bool,
) -> None:
    if value is None:
        if required:
            errors.append(ValidationError(
                code="missing_hash",
                message=f"{field} is required but missing",
                field=field,
            ))
        return
    if not _SHA256_RE.match(value):
        errors.append(ValidationError(
            code="invalid_sha256",
            message=f"{field} {value!r} is not a valid SHA-256 hex string (64 lowercase hex chars)",
            field=field,
        ))


def _size_field(
    field: str,
    value: int | None,
    errors: list[ValidationError],
    *,
    required: bool,
) -> None:
    if value is None:
        if required:
            errors.append(ValidationError(
                code="missing_size",
                message=f"{field} is required but missing",
                field=field,
            ))
        return
    if value < 0:
        errors.append(ValidationError(
            code="negative_size",
            message=f"{field} must be non-negative, got {value}",
            field=field,
        ))


def _portable_path(field: str, path: str, errors: list[ValidationError]) -> None:
    if not path:
        return
    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
        errors.append(ValidationError(
            code="absolute_path",
            message=f"{field} must be a relative path, got: {path!r}",
            field=field,
        ))
        return
    if "\\" in path:
        errors.append(ValidationError(
            code="non_portable_path",
            message=f"{field} must use '/' separators, got: {path!r}",
            field=field,
        ))
    parts = path.replace("\\", "/").split("/")
    if ".." in parts:
        errors.append(ValidationError(
            code="path_traversal",
            message=f"{field} must not contain '..': {path!r}",
            field=field,
        ))
