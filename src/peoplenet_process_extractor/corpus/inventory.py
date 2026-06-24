from pathlib import Path

from ..manifest.hashing import compute_file_hash_and_size
from .enums import Classification
from .models import CorpusSummary, FileEntry, Ln4Structure
from .path_parsing import normalize_path, parse_m4o_path, parse_peoplenet_path

_M4O_CLASSIFICATIONS: frozenset[str] = frozenset({
    Classification.M4O_NODE_JSON.value,
    Classification.M4O_ALIAS_JSON.value,
    Classification.M4O_MAPPING_JSON.value,
})

# When the final classification is one of these, M4O warnings from parse_m4o_path are dropped
# because a higher-priority rule (ignored, ln4, metadata_json) won instead.
_M4O_DRIVEN_CLASSES: frozenset[str] = _M4O_CLASSIFICATIONS | {Classification.OTHER_SUPPORTED.value}

# Extensions classified as ignored (included in manifest but not analyzed).
_IGNORED_EXTENSIONS: frozenset[str] = frozenset(
    {".pyc", ".db", ".sqlite", ".sqlite3", ".db-journal", ".db-shm", ".db-wal", ".log", ".tmp"}
)

# Directory names skipped entirely during traversal (never inventoried).
_SKIP_DIRS: frozenset[str] = frozenset(
    {".git", ".venv", "__pycache__", "node_modules", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
)


def classify_file(rel_path: str, structure: Ln4Structure | None) -> Classification:
    """
    Determine the Classification for a file given its path and parsed structure.

    Classification rules (in priority order):
    1. Extension in _IGNORED_EXTENSIONS → ignored
    2. Extension '.ln4' + structure present → structured_ln4
    3. Extension '.ln4' (no structure) → unstructured_ln4
    4. Filename 'metadata.json' (any location) → metadata_json
    5. m4o_node_json / m4o_alias_json / m4o_mapping_json (via parse_m4o_path)
    6. other_supported
    """
    parts = normalize_path(rel_path).split("/")
    filename = parts[-1]
    ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""

    if ext in _IGNORED_EXTENSIONS:
        return Classification.IGNORED
    if ext == ".ln4":
        return Classification.STRUCTURED_LN4 if structure is not None else Classification.UNSTRUCTURED_LN4
    if filename == "metadata.json":
        return Classification.METADATA_JSON
    m4o_cls, _, _ = parse_m4o_path(rel_path)
    return m4o_cls


def build_file_entry(abs_path: Path, rel_path: str) -> FileEntry:
    """
    Hash abs_path and construct a FileEntry for it.

    Raises OSError if the file cannot be read.
    """
    sha256, size_bytes = compute_file_hash_and_size(abs_path)
    source_root, ln4_structure, ln4_warnings = parse_peoplenet_path(rel_path)
    _, m4o_structure, m4o_warnings = parse_m4o_path(rel_path)
    classification = classify_file(rel_path, ln4_structure)

    # m4o_structure is only kept when the file is actually classified as an M4O resource.
    if classification.value not in _M4O_CLASSIFICATIONS:
        m4o_structure = None

    # M4O warnings are only meaningful when the M4O path detection determined the
    # classification (M4O classes or other_supported from a malformed M4O path).
    # Drop them when a higher-priority rule (ignored, ln4, metadata_json) won instead.
    final_m4o_warnings = list(m4o_warnings) if classification.value in _M4O_DRIVEN_CLASSES else []

    parts = normalize_path(rel_path).split("/")
    filename = parts[-1]
    ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""

    return FileEntry(
        path=rel_path,
        sha256=sha256,
        size_bytes=size_bytes,
        extension=ext,
        source_root=source_root,
        classification=classification.value,
        structure=ln4_structure,
        m4o_structure=m4o_structure,
        warnings=list(ln4_warnings) + final_m4o_warnings,
    )


def walk_corpus(
    corpus_root: Path,
    included_roots: list[str] | None,
) -> tuple[list[FileEntry], list[str], list[str]]:
    """
    Walk corpus_root and build FileEntry list.

    Args:
        corpus_root: Absolute path to the corpus directory.
        included_roots: If provided, only these first-level subdirectories are traversed.
                        Files directly at the corpus root are excluded when a filter is active.

    Returns:
        (entries, warnings, errors)
        - entries: sorted by normalized path
        - warnings: non-fatal issues (symlinks, git unavailable, etc.)
        - errors: files that could not be read (unrecoverable)

    Decision: a file that cannot be read raises an error.  The caller decides
    whether to abort or record the error in the manifest.
    """
    warnings: list[str] = []
    errors: list[str] = []
    entries: list[FileEntry] = []

    # Validate included_roots against what actually exists.
    if included_roots:
        for root_name in included_roots:
            root_dir = corpus_root / root_name
            if not root_dir.exists():
                errors.append(
                    f"Requested source root '{root_name}' does not exist in corpus."
                )
        if errors:
            return [], warnings, errors

    for item in _iter_corpus(corpus_root, corpus_root, included_roots, warnings):
        abs_path, rel_path, is_symlink = item
        if is_symlink:
            warnings.append(f"Skipping symlink: {rel_path}")
            continue
        try:
            entry = build_file_entry(abs_path, rel_path)
            entries.append(entry)
        except OSError as exc:
            errors.append(f"Cannot read file '{rel_path}': {exc}")

    if errors:
        return [], warnings, errors

    entries.sort(key=lambda e: e.path)
    return entries, warnings, errors


def _iter_corpus(
    corpus_root: Path,
    current_dir: Path,
    included_roots: list[str] | None,
    warnings: list[str],
) -> list[tuple[Path, str, bool]]:
    """
    Recursively yield (abs_path, rel_path, is_symlink) for items in current_dir.

    Skips:
    - Directories in _SKIP_DIRS
    - Symlink directories (emit warning and skip)
    """
    results = []
    try:
        items = sorted(current_dir.iterdir(), key=lambda p: p.name)
    except PermissionError as exc:
        warnings.append(f"Cannot read directory '{current_dir}': {exc}")
        return results

    for item in items:
        rel = _make_rel_path(corpus_root, item)

        if item.is_symlink():
            results.append((item, rel, True))
            continue

        if item.is_dir():
            if item.name in _SKIP_DIRS:
                continue
            # At the top level, filter by included_roots if specified.
            if current_dir == corpus_root and included_roots is not None:
                if item.name not in included_roots:
                    continue
            results.extend(_iter_corpus(corpus_root, item, included_roots, warnings))
        elif item.is_file():
            # When a root filter is active, skip files directly at the corpus root.
            if current_dir == corpus_root and included_roots is not None:
                continue
            results.append((item, rel, False))
        # Non-regular, non-dir, non-symlink items (devices, etc.) are silently skipped.

    return results


def _make_rel_path(corpus_root: Path, item: Path) -> str:
    """Return corpus-relative path with forward slashes."""
    try:
        rel = item.relative_to(corpus_root)
    except ValueError:
        rel = item
    return normalize_path(str(rel))


def build_summary(entries: list[FileEntry]) -> CorpusSummary:
    """
    Compute a CorpusSummary from a list of FileEntry objects.

    Counting policy:
    - total_files includes ALL classifications (including 'ignored').
    - total_bytes includes ALL files.
    - structured_files counts only 'structured_ln4'.
    - unstructured_files counts only 'unstructured_ln4'.
    - by_source_root uses "" for files with source_root=None.
    - by_extension and by_classification cover all entries.
    """
    total_files = len(entries)
    total_bytes = sum(e.size_bytes for e in entries)
    structured_files = sum(1 for e in entries if e.classification == Classification.STRUCTURED_LN4.value)
    unstructured_files = sum(1 for e in entries if e.classification == Classification.UNSTRUCTURED_LN4.value)

    by_source_root: dict[str, int] = {}
    by_extension: dict[str, int] = {}
    by_classification: dict[str, int] = {}

    for entry in entries:
        root_key = entry.source_root if entry.source_root is not None else ""
        by_source_root[root_key] = by_source_root.get(root_key, 0) + 1
        by_extension[entry.extension] = by_extension.get(entry.extension, 0) + 1
        by_classification[entry.classification] = by_classification.get(entry.classification, 0) + 1

    return CorpusSummary(
        total_files=total_files,
        total_bytes=total_bytes,
        structured_files=structured_files,
        unstructured_files=unstructured_files,
        by_source_root=dict(sorted(by_source_root.items())),
        by_extension=dict(sorted(by_extension.items())),
        by_classification=dict(sorted(by_classification.items())),
    )
