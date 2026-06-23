import re
from dataclasses import dataclass
from datetime import datetime

from .enums import Classification
from .inventory import build_summary
from .models import CorpusManifest, FileEntry, GitInfo, SUPPORTED_SCHEMA_VERSIONS

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VALID_EXTENSION_RE = re.compile(r"^\.[a-z0-9]+$|^$")


@dataclass
class ValidationError:
    code: str
    message: str


def validate_manifest(manifest: CorpusManifest) -> list[ValidationError]:
    """
    Validate a CorpusManifest for structural correctness.

    Returns a list of ValidationError.  An empty list means the manifest is valid.
    The summary is validated by recomputing it from the files list and comparing.
    """
    errors: list[ValidationError] = []

    _check_schema_version(manifest, errors)
    _check_corpus_id(manifest, errors)
    _check_created_at(manifest, errors)
    _check_root(manifest, errors)
    _check_git(manifest.git, errors)
    _check_included_source_roots(manifest, errors)
    _check_files(manifest.files, manifest.included_source_roots, errors)
    _check_summary_consistency(manifest, errors)

    return errors


# ── individual checkers ────────────────────────────────────────────────────


def _check_schema_version(manifest: CorpusManifest, errors: list[ValidationError]) -> None:
    if manifest.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            ValidationError(
                code="unsupported_schema_version",
                message=(
                    f"Schema version '{manifest.schema_version}' is not supported. "
                    f"Supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}."
                ),
            )
        )


def _check_corpus_id(manifest: CorpusManifest, errors: list[ValidationError]) -> None:
    if not manifest.corpus_id or not manifest.corpus_id.strip():
        errors.append(
            ValidationError(
                code="empty_corpus_id",
                message="corpus_id must not be empty.",
            )
        )


def _check_created_at(manifest: CorpusManifest, errors: list[ValidationError]) -> None:
    ts = manifest.created_at
    if not ts:
        errors.append(
            ValidationError(code="missing_created_at", message="created_at is required.")
        )
        return
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        errors.append(
            ValidationError(
                code="invalid_created_at",
                message=f"created_at '{ts}' is not valid ISO 8601.",
            )
        )
        return
    if dt.tzinfo is None:
        errors.append(
            ValidationError(
                code="created_at_missing_timezone",
                message=f"created_at '{ts}' must include a timezone offset.",
            )
        )
        return
    utc_offset = dt.utcoffset()
    if utc_offset is not None and utc_offset.total_seconds() != 0:
        errors.append(
            ValidationError(
                code="created_at_not_utc",
                message=f"created_at '{ts}' must be UTC (Z or +00:00), got non-zero offset.",
            )
        )


def _check_root(manifest: CorpusManifest, errors: list[ValidationError]) -> None:
    if not manifest.root.label or not manifest.root.label.strip():
        errors.append(
            ValidationError(code="empty_root_label", message="root.label must not be empty.")
        )
    if manifest.root.path_policy != "relative":
        errors.append(
            ValidationError(
                code="invalid_path_policy",
                message=f"root.path_policy must be 'relative', got '{manifest.root.path_policy}'.",
            )
        )


def _check_git(git: GitInfo, errors: list[ValidationError]) -> None:
    if git.commit is not None:
        if not _SHA256_RE.match(git.commit) and not re.match(r"^[0-9a-f]{40}$", git.commit):
            errors.append(
                ValidationError(
                    code="invalid_git_commit",
                    message=f"git.commit '{git.commit}' does not look like a valid SHA-1 or SHA-256 hash.",
                )
            )
    if git.dirty is not None and not isinstance(git.dirty, bool):
        errors.append(
            ValidationError(
                code="invalid_git_dirty",
                message="git.dirty must be a boolean or null.",
            )
        )


def _check_included_source_roots(
    manifest: CorpusManifest, errors: list[ValidationError]
) -> None:
    seen: set[str] = set()
    for root in manifest.included_source_roots:
        if not root or not root.strip():
            errors.append(
                ValidationError(
                    code="empty_source_root",
                    message="included_source_roots must not contain empty strings.",
                )
            )
        elif root in seen:
            errors.append(
                ValidationError(
                    code="duplicate_source_root",
                    message=f"Duplicate source root: '{root}'.",
                )
            )
        seen.add(root)


def _check_files(
    files: list[FileEntry], included_source_roots: list[str], errors: list[ValidationError]
) -> None:
    seen_paths: set[str] = set()
    for entry in files:
        _check_file_entry(entry, included_source_roots, errors)
        if entry.path in seen_paths:
            errors.append(
                ValidationError(
                    code="duplicate_file_path",
                    message=f"Duplicate file path: '{entry.path}'.",
                )
            )
        seen_paths.add(entry.path)

    # Verify ordering.
    paths = [e.path for e in files]
    if paths != sorted(paths):
        errors.append(
            ValidationError(
                code="files_not_sorted",
                message="files list is not sorted by path.",
            )
        )


def _check_file_entry(
    entry: FileEntry, included_source_roots: list[str], errors: list[ValidationError]
) -> None:
    path = entry.path

    # Path must be relative (no leading slash, no Windows drive letters).
    if path.startswith("/") or (len(path) >= 2 and path[1] == ":"):
        errors.append(
            ValidationError(
                code="absolute_path",
                message=f"File path must be relative: '{path}'.",
            )
        )
    # Path must not contain traversal.
    parts = path.replace("\\", "/").split("/")
    if ".." in parts:
        errors.append(
            ValidationError(
                code="path_traversal",
                message=f"File path contains '..': '{path}'.",
            )
        )
    # Path must use forward slashes only.
    if "\\" in path:
        errors.append(
            ValidationError(
                code="backslash_in_path",
                message=f"File path must use '/' separators: '{path}'.",
            )
        )

    # Hash.
    if not _SHA256_RE.match(entry.sha256):
        errors.append(
            ValidationError(
                code="invalid_sha256",
                message=f"sha256 '{entry.sha256}' is not a valid hex SHA-256 for '{path}'.",
            )
        )

    # Size.
    if entry.size_bytes < 0:
        errors.append(
            ValidationError(
                code="negative_size",
                message=f"size_bytes must not be negative for '{path}'.",
            )
        )

    # Classification must be a valid enum value.
    valid_classifications = {c.value for c in Classification}
    if entry.classification not in valid_classifications:
        errors.append(
            ValidationError(
                code="invalid_classification",
                message=f"Unknown classification '{entry.classification}' for '{path}'.",
            )
        )
    else:
        # Structure coherence.
        _check_structure_coherence(entry, errors)

    # Extension must be lowercase.
    if entry.extension != entry.extension.lower():
        errors.append(
            ValidationError(
                code="extension_not_lowercase",
                message=f"extension '{entry.extension}' must be lowercase for '{path}'.",
            )
        )

    # Extension must match the actual path suffix.
    filename = path.replace("\\", "/").rsplit("/", 1)[-1]
    expected_ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
    if entry.extension != expected_ext:
        errors.append(
            ValidationError(
                code="extension_path_mismatch",
                message=(
                    f"extension '{entry.extension}' does not match path suffix "
                    f"'{expected_ext}' for '{path}'."
                ),
            )
        )

    _check_source_root_coherence(entry, included_source_roots, errors)


def _check_structure_coherence(entry: FileEntry, errors: list[ValidationError]) -> None:
    """structured_ln4 must have structure; others must not."""
    if entry.classification == Classification.STRUCTURED_LN4.value:
        if entry.structure is None:
            errors.append(
                ValidationError(
                    code="missing_structure",
                    message=(
                        f"File '{entry.path}' has classification 'structured_ln4' "
                        "but no structure."
                    ),
                )
            )
    else:
        if entry.structure is not None:
            errors.append(
                ValidationError(
                    code="unexpected_structure",
                    message=(
                        f"File '{entry.path}' has classification '{entry.classification}' "
                        "but a non-null structure."
                    ),
                )
            )


def _check_source_root_coherence(
    entry: FileEntry, included_source_roots: list[str], errors: list[ValidationError]
) -> None:
    """Validate source_root consistency with path and included_source_roots scope."""
    parts = entry.path.replace("\\", "/").split("/")

    if len(parts) == 1:
        # File at corpus root — source_root must be None.
        if entry.source_root is not None:
            errors.append(
                ValidationError(
                    code="source_root_mismatch",
                    message=(
                        f"File at corpus root '{entry.path}' must have source_root=null, "
                        f"got '{entry.source_root}'."
                    ),
                )
            )
    else:
        # File inside a subdirectory — source_root must match first component.
        expected = parts[0]
        if entry.source_root != expected:
            errors.append(
                ValidationError(
                    code="source_root_mismatch",
                    message=(
                        f"source_root '{entry.source_root}' does not match first path "
                        f"component '{expected}' for '{entry.path}'."
                    ),
                )
            )
        # Non-null source_root must be within the declared scope (always enforced).
        if (
            entry.source_root is not None
            and entry.source_root not in included_source_roots
        ):
            errors.append(
                ValidationError(
                    code="source_root_not_in_scope",
                    message=(
                        f"source_root '{entry.source_root}' is not in "
                        f"included_source_roots for '{entry.path}'."
                    ),
                )
            )


def _check_summary_consistency(
    manifest: CorpusManifest, errors: list[ValidationError]
) -> None:
    """Recompute summary from files and compare with stored summary."""
    computed = build_summary(manifest.files)
    stored = manifest.summary

    def _mismatch(field: str, stored_val: object, computed_val: object) -> None:
        errors.append(
            ValidationError(
                code="summary_mismatch",
                message=(
                    f"summary.{field} mismatch: stored={stored_val!r}, "
                    f"computed={computed_val!r}."
                ),
            )
        )

    if stored.total_files != computed.total_files:
        _mismatch("total_files", stored.total_files, computed.total_files)
    if stored.total_bytes != computed.total_bytes:
        _mismatch("total_bytes", stored.total_bytes, computed.total_bytes)
    if stored.structured_files != computed.structured_files:
        _mismatch("structured_files", stored.structured_files, computed.structured_files)
    if stored.unstructured_files != computed.unstructured_files:
        _mismatch("unstructured_files", stored.unstructured_files, computed.unstructured_files)
    if stored.by_source_root != computed.by_source_root:
        _mismatch("by_source_root", stored.by_source_root, computed.by_source_root)
    if stored.by_extension != computed.by_extension:
        _mismatch("by_extension", stored.by_extension, computed.by_extension)
    if stored.by_classification != computed.by_classification:
        _mismatch("by_classification", stored.by_classification, computed.by_classification)
