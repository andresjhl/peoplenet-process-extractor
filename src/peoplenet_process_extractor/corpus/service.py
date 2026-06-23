"""
High-level corpus inventory service.

Decisions documented here:
- A requested source root that does not exist is a blocking error (the declared
  scope cannot be fulfilled).
- A file that cannot be read is a blocking error (the manifest would be incomplete).
- included_source_roots in the manifest reflects only the source roots that were
  actually traversed (filtered or discovered).
- verify reuses the root scope from the manifest (included_source_roots).
  corpus verify checks exclusively the scope recorded in included_source_roots.
  New roots outside that scope are not reported as differences.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .comparison import CorpusDiff, compare_manifests
from .git_info import get_git_info
from .inventory import build_summary, walk_corpus
from .models import CorpusManifest, RootInfo
from .serialization import DeserializationError, deserialize_manifest, serialize_manifest
from .validation import validate_manifest


def build_corpus_id(corpus_root: Path) -> str:
    """
    Derive a deterministic corpus_id from the corpus root directory name.

    The id is the directory name, lower-cased, with spaces replaced by hyphens.
    """
    name = corpus_root.name or corpus_root.resolve().name
    return name.lower().replace(" ", "-")


def create_inventory(
    corpus_root: Path,
    output_path: Path,
    corpus_id: str | None = None,
    source_roots: list[str] | None = None,
    force: bool = False,
    now: datetime | None = None,
) -> tuple[int, list[str]]:
    """
    Build a corpus-manifest-v1 and write it to output_path.

    Returns (exit_code, messages) where messages are human-readable lines.
    exit_code 0 = success, non-zero = error.

    Errors:
    - corpus_root is not a directory.
    - corpus_root is a symlink.
    - output_path exists and force is False.
    - A requested source_root does not exist.
    - A file cannot be read.
    """
    messages: list[str] = []

    # Validate corpus root.
    if corpus_root.is_symlink():
        messages.append(f"Error: corpus root '{corpus_root}' is a symlink. Use a real directory.")
        return 1, messages
    if not corpus_root.exists():
        messages.append(f"Error: corpus root '{corpus_root}' does not exist.")
        return 1, messages
    if not corpus_root.is_dir():
        messages.append(f"Error: corpus root '{corpus_root}' is not a directory.")
        return 1, messages

    # Check output.
    if output_path.exists() and not force:
        messages.append(
            f"Error: output file already exists: '{output_path}'. Use --force to overwrite."
        )
        return 1, messages

    corpus_id = corpus_id or build_corpus_id(corpus_root)

    # Normalize: deduplicate and sort for deterministic output.
    if source_roots is not None:
        source_roots = sorted(set(source_roots))

    # Walk and classify.
    entries, walk_warnings, walk_errors = walk_corpus(corpus_root, source_roots)
    if walk_errors:
        for err in walk_errors:
            messages.append(f"Error: {err}")
        return 1, messages

    # Determine included_source_roots.
    if source_roots is not None:
        included_roots = list(source_roots)  # Already normalized.
    else:
        # Discover from entries.
        seen: list[str] = []
        seen_set: set[str] = set()
        for e in entries:
            if e.source_root and e.source_root not in seen_set:
                seen.append(e.source_root)
                seen_set.add(e.source_root)
        included_roots = sorted(seen)

    # Git info.
    git_info, git_warnings = get_git_info(corpus_root)
    all_warnings = list(walk_warnings) + list(git_warnings)

    # Timestamp.
    ts = now or datetime.now(timezone.utc)
    created_at = ts.isoformat()

    summary = build_summary(entries)

    manifest = CorpusManifest(
        schema_version="1.0",
        corpus_id=corpus_id,
        created_at=created_at,
        root=RootInfo(label=corpus_root.name or str(corpus_root)),
        git=git_info,
        included_source_roots=included_roots,
        files=entries,
        summary=summary,
        warnings=all_warnings,
        errors=[],
    )

    # Validate before writing.
    errors = validate_manifest(manifest)
    if errors:
        for err in errors:
            messages.append(f"Validation error [{err.code}]: {err.message}")
        return 1, messages

    text = serialize_manifest(manifest)

    # Write atomically.
    try:
        _write_atomic(text, output_path)
    except OSError as exc:
        messages.append(f"Error writing output: {exc}")
        return 1, messages

    messages.append(f"Corpus manifest written to '{output_path}'.")
    messages.append(f"  {summary.total_files} files, {summary.total_bytes} bytes.")
    if all_warnings:
        for w in all_warnings:
            messages.append(f"  Warning: {w}")
    return 0, messages


def verify_corpus(
    corpus_root: Path,
    manifest_path: Path,
    now: datetime | None = None,
) -> tuple[int, CorpusDiff | None, list[str]]:
    """
    Load a corpus manifest and compare against the current state of corpus_root.

    Returns (exit_code, diff, messages).
    - exit_code 0: corpus matches manifest exactly.
    - exit_code 1: differences found or error.
    - diff is None on error.

    Scope: uses the included_source_roots from the manifest to limit the scan.
    """
    messages: list[str] = []

    # Load manifest.
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        messages.append(f"Error reading manifest: {exc}")
        return 1, None, messages

    try:
        manifest, errors = deserialize_manifest(text)
    except DeserializationError as exc:
        messages.append(f"Error: manifest is not valid JSON or has structural errors: {exc}")
        return 1, None, messages

    if errors:
        for err in errors:
            messages.append(f"Validation error [{err.code}]: {err.message}")
        messages.append("Error: manifest failed validation; cannot verify corpus.")
        return 1, None, messages

    # Validate corpus root.
    if corpus_root.is_symlink():
        messages.append(f"Error: corpus root '{corpus_root}' is a symlink.")
        return 1, None, messages
    if not corpus_root.is_dir():
        messages.append(f"Error: corpus root '{corpus_root}' is not a directory.")
        return 1, None, messages

    # Re-inventory using the manifest's scope.
    # Root-level files (source_root=None) are in scope only when the original
    # inventory included them. Walk the full corpus and post-filter so that:
    # - Root files are included iff the manifest contains any root-level file.
    # - Subdirectory files are included iff their source_root is in included_source_roots.
    # This correctly handles the case where a full (unfiltered) inventory included root
    # files alongside named source roots.
    manifest_has_root_files = any(e.source_root is None for e in manifest.files)
    scope = set(manifest.included_source_roots)

    current_entries, walk_warnings, walk_errors = walk_corpus(corpus_root, None)

    if walk_errors:
        for err in walk_errors:
            messages.append(f"Error: {err}")
        return 1, None, messages

    for w in walk_warnings:
        messages.append(f"Warning: {w}")

    current_entries = [
        e for e in current_entries
        if (e.source_root is None and manifest_has_root_files)
        or (e.source_root is not None and e.source_root in scope)
    ]

    diff = compare_manifests(manifest.files, current_entries)

    if not diff.has_changes:
        messages.append("Corpus matches manifest exactly.")
        messages.append(f"  {len(diff.unchanged)} files verified.")
        return 0, diff, messages

    # Report changes.
    if diff.added:
        messages.append(f"Added ({len(diff.added)}):")
        for p in diff.added:
            messages.append(f"  + {p}")
    if diff.removed:
        messages.append(f"Removed ({len(diff.removed)}):")
        for p in diff.removed:
            messages.append(f"  - {p}")
    if diff.modified:
        messages.append(f"Modified ({len(diff.modified)}):")
        for m in diff.modified:
            changes = []
            if m.changes.hash_changed:
                changes.append("hash")
            if m.changes.size_changed:
                changes.append("size")
            if m.changes.classification_changed:
                changes.append("classification")
            if m.changes.structure_changed:
                changes.append("structure")
            messages.append(f"  ~ {m.path} [{', '.join(changes)}]")
    if diff.unchanged:
        messages.append(f"Unchanged: {len(diff.unchanged)} files.")

    return 1, diff, messages


def _write_atomic(text: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp: str | None = None
    try:
        fd, tmp = tempfile.mkstemp(dir=dest.parent, suffix=".tmp")
        os.close(fd)
        Path(tmp).write_text(text, encoding="utf-8")
        Path(tmp).replace(dest)
        tmp = None
    finally:
        if tmp is not None:
            try:
                Path(tmp).unlink(missing_ok=True)
            except OSError:
                pass
