from dataclasses import dataclass, field

from .models import FileEntry


@dataclass
class FileModification:
    hash_changed: bool = False
    size_changed: bool = False
    classification_changed: bool = False
    structure_changed: bool = False
    old_hash: str | None = None
    new_hash: str | None = None
    old_size: int | None = None
    new_size: int | None = None
    old_classification: str | None = None
    new_classification: str | None = None


@dataclass
class ModifiedFile:
    path: str
    changes: FileModification


@dataclass
class CorpusDiff:
    """
    Result of comparing two corpus manifests.

    A rename is represented as a 'removed' entry + an 'added' entry.
    No heuristic rename detection is performed.
    """

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[ModifiedFile] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.modified)


def compare_file_entries(old: FileEntry, new: FileEntry) -> FileModification | None:
    """
    Compare two FileEntry objects with the same path.

    Returns a FileModification if they differ, None if identical.
    Structure change is detected by comparing the serialized structure fields;
    we do not expose raw Ln4Structure equality directly to callers.
    """
    hash_changed = old.sha256 != new.sha256
    size_changed = old.size_bytes != new.size_bytes
    classification_changed = old.classification != new.classification
    structure_changed = _structure_key(old) != _structure_key(new)

    if not any([hash_changed, size_changed, classification_changed, structure_changed]):
        return None

    return FileModification(
        hash_changed=hash_changed,
        size_changed=size_changed,
        classification_changed=classification_changed,
        structure_changed=structure_changed,
        old_hash=old.sha256 if hash_changed else None,
        new_hash=new.sha256 if hash_changed else None,
        old_size=old.size_bytes if size_changed else None,
        new_size=new.size_bytes if size_changed else None,
        old_classification=old.classification if classification_changed else None,
        new_classification=new.classification if classification_changed else None,
    )


def compare_manifests(
    old_files: list[FileEntry],
    new_files: list[FileEntry],
) -> CorpusDiff:
    """
    Compare two sets of FileEntry objects (already validated and sorted).

    Both lists must be sorted by path — the result lists are also sorted.
    """
    old_map = {e.path: e for e in old_files}
    new_map = {e.path: e for e in new_files}

    old_paths = set(old_map)
    new_paths = set(new_map)

    added = sorted(new_paths - old_paths)
    removed = sorted(old_paths - new_paths)

    modified: list[ModifiedFile] = []
    unchanged: list[str] = []

    for path in sorted(old_paths & new_paths):
        mod = compare_file_entries(old_map[path], new_map[path])
        if mod is not None:
            modified.append(ModifiedFile(path=path, changes=mod))
        else:
            unchanged.append(path)

    modified.sort(key=lambda m: m.path)

    return CorpusDiff(added=added, removed=removed, modified=modified, unchanged=unchanged)


def _structure_key(entry: FileEntry) -> tuple:
    """Comparable key for the structure and m4o_structure fields (mutually exclusive)."""
    if entry.structure is not None:
        s = entry.structure
        return ("ln4", s.meta4object, s.item_type, s.item_name, s.rule_id, s.rule_date)
    if entry.m4o_structure is not None:
        m = entry.m4o_structure
        return ("m4o", m.id_t3, m.id_node)
    return ()
