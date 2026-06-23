import importlib.metadata
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..scenario.serialization import deserialize_scenario
from ..scenario.validation import validate as validate_scenario
from .enums import ArtifactStatus, EventType, RunStatus, SourceKind
from .hashing import compute_file_hash_and_size
from .models import Event, RunManifest, ScenarioRef, SourceFile, Tool
from .serialization import deserialize_manifest, serialize_manifest
from .validation import validate as validate_manifest


class RunError(Exception):
    pass


class ScenarioValidationError(RunError):
    pass


class RunDirectoryError(RunError):
    pass


class ManifestParseError(RunError):
    pass


# ---------------------------------------------------------------------------
# Clock / token helpers (injectable for tests)
# ---------------------------------------------------------------------------


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_token() -> str:
    return uuid.uuid4().hex


def _format_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _tool_version() -> str:
    try:
        return importlib.metadata.version("peoplenet-process-extractor")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


# ---------------------------------------------------------------------------
# run_id generation
# ---------------------------------------------------------------------------


def generate_run_id(*, _clock_fn=None, _token_fn=None) -> str:
    dt = (_clock_fn or _default_clock)()
    token = (_token_fn or _default_token)()
    date_part = dt.strftime("%Y%m%d")
    suffix = token[:8]
    return f"run-{date_part}-{suffix}"


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


def write_manifest_atomic(manifest: RunManifest, dest: Path) -> None:
    text = serialize_manifest(manifest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dest.parent, suffix=".tmp")
        os.close(fd)
        Path(tmp_path).write_text(text, encoding="utf-8")
        Path(tmp_path).replace(dest)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Safe --force helpers
# ---------------------------------------------------------------------------

_MANAGED_ENTRIES = frozenset({"run-manifest.json", "inputs", "artifacts", "reports"})


def _is_clean_managed_run(run_dir: Path, run_id: str) -> str | None:
    """
    Return an error description if run_dir cannot be safely replaced, or None if it can.

    A run is replaceable only when:
    - It contains run-manifest.json.
    - That manifest is valid.
    - Its run_id matches the directory name.
    - No unknown files or directories exist at the root of run_dir.
    """
    manifest_path = run_dir / "run-manifest.json"
    if not manifest_path.is_file():
        return "does not contain run-manifest.json"

    try:
        text = manifest_path.read_text(encoding="utf-8")
        manifest = deserialize_manifest(text)
    except Exception as exc:
        return f"run-manifest.json is not parseable: {exc}"

    m_errors = validate_manifest(manifest)
    if m_errors:
        codes = ", ".join(e.code for e in m_errors[:3])
        return f"run-manifest.json has validation errors: {codes}"

    if manifest.run_id != run_id:
        return (
            f"manifest run_id {manifest.run_id!r} does not match "
            f"directory name {run_id!r}"
        )

    unknown = sorted(
        item.name for item in run_dir.iterdir() if item.name not in _MANAGED_ENTRIES
    )
    if unknown:
        return f"directory contains unknown entries: {unknown}"

    return None


def _publish_staging(staging: Path, final: Path) -> None:
    """
    Replace final with staging atomically.

    If final does not exist, simply renames staging to final.
    If final exists, backs it up, renames staging to final, then deletes the backup.
    Restores the backup on failure.
    """
    if not final.exists():
        staging.rename(final)
        return

    backup = final.parent / f".{final.name}.backup-{uuid.uuid4().hex[:8]}"
    final.rename(backup)
    try:
        staging.rename(final)
        # Published successfully; clean up backup.
        try:
            shutil.rmtree(backup)
        except OSError:
            pass
    except Exception:
        # Publication failed; restore backup so the previous run is not lost.
        if not final.exists():
            try:
                backup.rename(final)
            except OSError:
                pass
        elif backup.exists():
            try:
                shutil.rmtree(backup)
            except OSError:
                pass
        raise


# ---------------------------------------------------------------------------
# create_run
# ---------------------------------------------------------------------------


def create_run(
    scenario_path: Path,
    runs_root: Path,
    run_id: str | None = None,
    *,
    force: bool = False,
    _clock_fn=None,
    _token_fn=None,
) -> RunManifest:
    """
    Create a new run directory from a scenario file.

    The final run directory is runs_root / run_id.  Building happens in a
    staging directory (sibling of the final directory), so the previous run
    is never touched until staging is fully built and validated.

    Steps:
    1. Reject symlink scenario files.
    2. Load and validate scenario-v1.
    3. Resolve or generate run_id.
    4. If run_dir exists without --force: error.
       If run_dir exists with --force: verify it is a clean managed run.
    5. Build in staging dir (runs_root / .<run_id>.staging-<suffix>).
    6. Validate the built manifest.
    7. Publish staging → run_dir (atomic rename with backup/restore).
    """
    clock_fn = _clock_fn or _default_clock
    token_fn = _token_fn or _default_token

    # 1. Reject symlinks — do not follow external symlinks to scenario files.
    if scenario_path.is_symlink():
        raise ScenarioValidationError(
            f"Scenario must be a regular file, not a symlink: {scenario_path}"
        )

    # 2. Load and validate scenario
    try:
        raw = scenario_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ScenarioValidationError(f"Scenario file not found: {scenario_path}")
    except OSError as exc:
        raise ScenarioValidationError(f"Could not read scenario: {exc}")

    try:
        scenario = deserialize_scenario(raw)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        raise ScenarioValidationError(f"Could not parse scenario: {exc}")

    s_errors = validate_scenario(scenario)
    if s_errors:
        detail = "; ".join(f"{e.code}: {e.message}" for e in s_errors)
        raise ScenarioValidationError(f"Scenario validation failed: {detail}")

    # 3. Resolve run_id
    now_dt = clock_fn()
    now_ts = _format_ts(now_dt)
    token = token_fn()

    if run_id is None:
        date_part = now_dt.strftime("%Y%m%d")
        run_id = f"run-{date_part}-{token[:8]}"

    run_dir = runs_root / run_id

    # 4. Check existing run directory
    if run_dir.exists():
        if not force:
            raise RunDirectoryError(
                f"Run directory already exists: {run_dir}. "
                "Use --force to overwrite an existing managed run."
            )
        reason = _is_clean_managed_run(run_dir, run_id)
        if reason:
            raise RunDirectoryError(
                f"Cannot force-overwrite {run_dir}: {reason}"
            )

    # 5. Build in staging directory
    staging_suffix = token[8:16] if len(token) >= 16 else uuid.uuid4().hex[:8]
    staging_dir = runs_root / f".{run_id}.staging-{staging_suffix}"
    staging_dir_created = False

    try:
        inputs_dir = staging_dir / "inputs"
        inputs_dir.mkdir(parents=True)
        staging_dir_created = True
        (staging_dir / "artifacts").mkdir()
        (staging_dir / "reports").mkdir()

        dest_scenario = inputs_dir / "scenario.json"
        shutil.copy2(scenario_path, dest_scenario)

        sha256, size_bytes = compute_file_hash_and_size(dest_scenario)

        tool = Tool(
            id="peoplenet-process-extractor",
            name="peoplenet-process-extractor",
            version=_tool_version(),
            command="peoplenet-process-extractor manifest create",
        )

        scenario_source = SourceFile(
            id="scenario",
            kind=SourceKind.SCENARIO.value,
            path="inputs/scenario.json",
            sha256=sha256,
            size_bytes=size_bytes,
            exists=True,
            required=True,
            description="Scenario v1 used for this run",
        )

        scenario_ref = ScenarioRef(
            path="inputs/scenario.json",
            sha256=sha256,
            size_bytes=size_bytes,
            scenario_id=scenario.scenario_id,
            schema_version=scenario.schema_version,
        )

        event = Event(
            sequence=1,
            type=EventType.PREPARED.value,
            timestamp=now_ts,
            message=f"Run {run_id!r} prepared",
        )

        manifest = RunManifest(
            schema_version="1.0",
            run_id=run_id,
            status=RunStatus.PREPARED.value,
            scenario=scenario_ref,
            sources=[scenario_source],
            tools=[tool],
            artifacts=[],
            events=[event],
        )

        # 6. Guard-validate before publishing.
        m_errors = validate_manifest(manifest)
        if m_errors:
            detail = "; ".join(f"{e.code}: {e.message}" for e in m_errors)
            raise RunError(f"Internal manifest validation failed: {detail}")

        write_manifest_atomic(manifest, staging_dir / "run-manifest.json")

    except Exception:
        if staging_dir_created and staging_dir.exists():
            try:
                shutil.rmtree(staging_dir)
            except OSError:
                pass
        raise

    # 7. Publish staging → final run directory.
    try:
        _publish_staging(staging_dir, run_dir)
    except Exception:
        if staging_dir.exists():
            try:
                shutil.rmtree(staging_dir)
            except OSError:
                pass
        raise

    return manifest


# ---------------------------------------------------------------------------
# verify_run
# ---------------------------------------------------------------------------


@dataclass
class VerifyIssue:
    kind: str
    path: str | None
    message: str


@dataclass
class VerifyResult:
    manifest: RunManifest
    issues: list[VerifyIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def _check_verify_path(
    raw_path: Path,
    rel_path: str,
    run_dir_resolved: Path,
    issues: list[VerifyIssue],
    label: str,
) -> bool:
    """
    Reject symlinks and paths that resolve outside the run directory.
    Returns True if the path is safe to read.
    """
    if raw_path.is_symlink():
        issues.append(VerifyIssue(
            kind="symlink",
            path=rel_path,
            message=f"{label}: path is a symlink, which is not allowed",
        ))
        return False
    try:
        raw_path.resolve().relative_to(run_dir_resolved)
    except ValueError:
        issues.append(VerifyIssue(
            kind="path_escape",
            path=rel_path,
            message=f"{label}: resolved path is outside the run directory",
        ))
        return False
    return True


def verify_run(manifest_path: Path) -> VerifyResult:
    """
    Load and structurally validate the manifest, then verify file integrity.

    Does NOT modify the manifest. Returns a VerifyResult with any issues found.
    """
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ManifestParseError(f"Manifest file not found: {manifest_path}")
    except OSError as exc:
        raise ManifestParseError(f"Could not read manifest: {exc}")

    try:
        manifest = deserialize_manifest(text)
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        raise ManifestParseError(f"Could not parse manifest: {exc}")

    issues: list[VerifyIssue] = []

    # Structural validation first — file checks are meaningless with a broken manifest.
    m_errors = validate_manifest(manifest)
    if m_errors:
        for e in m_errors:
            issues.append(VerifyIssue(
                kind="validation_error",
                path=None,
                message=f"{e.code}: {e.message}",
            ))
        return VerifyResult(manifest=manifest, issues=issues)

    run_dir = manifest_path.parent
    run_dir_resolved = run_dir.resolve()

    def resolve(rel_path: str) -> Path:
        return run_dir / rel_path.replace("/", os.sep)

    # Verify scenario file (once — structural validation ensures the scenario source
    # entry mirrors these exact path/sha256/size_bytes values).
    scen_rel = manifest.scenario.path
    scen_path = resolve(scen_rel)
    if _check_verify_path(scen_path, scen_rel, run_dir_resolved, issues, "scenario"):
        if not scen_path.is_file():
            issues.append(VerifyIssue(
                kind="missing",
                path=scen_rel,
                message=f"Scenario file missing: {scen_rel}",
            ))
        else:
            sha256, size_bytes = compute_file_hash_and_size(scen_path)
            if size_bytes != manifest.scenario.size_bytes:
                issues.append(VerifyIssue(
                    kind="size_mismatch",
                    path=scen_rel,
                    message=(
                        f"Scenario size mismatch: "
                        f"expected {manifest.scenario.size_bytes}, got {size_bytes}"
                    ),
                ))
            if sha256 != manifest.scenario.sha256:
                issues.append(VerifyIssue(
                    kind="hash_mismatch",
                    path=scen_rel,
                    message=(
                        f"Scenario hash mismatch: "
                        f"expected {manifest.scenario.sha256}, got {sha256}"
                    ),
                ))

    # Verify non-scenario sources.
    # The scenario source is intentionally skipped here: structural validation already
    # guarantees its path/sha256/size_bytes match manifest.scenario, and the file was
    # verified above via the scenario ref — no double verification needed.
    for src in manifest.sources:
        if src.kind == SourceKind.SCENARIO.value:
            continue
        src_path = resolve(src.path)
        if not _check_verify_path(src_path, src.path, run_dir_resolved, issues, f"source {src.id!r}"):
            continue
        if not src_path.is_file():
            if src.required or src.sha256 is not None:
                issues.append(VerifyIssue(
                    kind="missing",
                    path=src.path,
                    message=f"Source {src.id!r} missing: {src.path}",
                ))
        elif src.sha256 is not None:
            sha256, size_bytes = compute_file_hash_and_size(src_path)
            if src.size_bytes is not None and size_bytes != src.size_bytes:
                issues.append(VerifyIssue(
                    kind="size_mismatch",
                    path=src.path,
                    message=f"Source {src.id!r} size mismatch: expected {src.size_bytes}, got {size_bytes}",
                ))
            if sha256 != src.sha256:
                issues.append(VerifyIssue(
                    kind="hash_mismatch",
                    path=src.path,
                    message=f"Source {src.id!r} hash mismatch",
                ))

    # Verify artifacts that should exist.
    for art in manifest.artifacts:
        if art.status in (ArtifactStatus.PLANNED.value, ArtifactStatus.FAILED.value):
            continue
        art_path = resolve(art.path)
        if not _check_verify_path(art_path, art.path, run_dir_resolved, issues, f"artifact {art.id!r}"):
            continue
        if not art_path.is_file():
            issues.append(VerifyIssue(
                kind="missing",
                path=art.path,
                message=f"Artifact {art.id!r} missing: {art.path}",
            ))
        elif art.sha256 is not None:
            sha256, size_bytes = compute_file_hash_and_size(art_path)
            if art.size_bytes is not None and size_bytes != art.size_bytes:
                issues.append(VerifyIssue(
                    kind="size_mismatch",
                    path=art.path,
                    message=f"Artifact {art.id!r} size mismatch: expected {art.size_bytes}, got {size_bytes}",
                ))
            if sha256 != art.sha256:
                issues.append(VerifyIssue(
                    kind="hash_mismatch",
                    path=art.path,
                    message=f"Artifact {art.id!r} hash mismatch",
                ))

    return VerifyResult(manifest=manifest, issues=issues)
