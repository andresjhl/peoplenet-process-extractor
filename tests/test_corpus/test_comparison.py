"""Tests for corpus manifest comparison."""

from peoplenet_process_extractor.corpus.comparison import (
    compare_manifests,
)
from peoplenet_process_extractor.corpus.models import FileEntry, Ln4Structure


def _entry(
    path: str,
    sha256: str = "a" * 64,
    size: int = 100,
    classification: str = "structured_ln4",
    source_root: str | None = "CP",
    structure: Ln4Structure | None = None,
) -> FileEntry:
    if structure is None and classification == "structured_ln4":
        structure = Ln4Structure(meta4object="O", item_type="METHOD", item_name="M", rule_id="R1", rule_date="2020")
    return FileEntry(
        path=path,
        sha256=sha256,
        size_bytes=size,
        extension=".ln4",
        source_root=source_root,
        classification=classification,
        structure=structure,
    )


def _path_set(entries: list[FileEntry]) -> set[str]:
    return {e.path for e in entries}


class TestEqualManifests:
    def test_identical_single_file(self):
        e = _entry("a.ln4")
        diff = compare_manifests([e], [e])
        assert not diff.has_changes
        assert diff.unchanged == ["a.ln4"]
        assert diff.added == []
        assert diff.removed == []
        assert diff.modified == []

    def test_identical_multiple_files(self):
        entries = [_entry(f"{i}.ln4") for i in range(3)]
        diff = compare_manifests(entries, entries)
        assert not diff.has_changes
        assert len(diff.unchanged) == 3


class TestAddedFiles:
    def test_single_added(self):
        old = [_entry("a.ln4")]
        new = [_entry("a.ln4"), _entry("b.ln4")]
        diff = compare_manifests(old, new)
        assert diff.has_changes
        assert diff.added == ["b.ln4"]
        assert diff.removed == []

    def test_multiple_added(self):
        new = [_entry("a.ln4"), _entry("b.ln4"), _entry("c.ln4")]
        diff = compare_manifests([], new)
        assert sorted(diff.added) == ["a.ln4", "b.ln4", "c.ln4"]

    def test_added_sorted(self):
        old = [_entry("b.ln4")]
        new = [_entry("a.ln4"), _entry("b.ln4"), _entry("c.ln4")]
        diff = compare_manifests(old, new)
        assert diff.added == sorted(diff.added)


class TestRemovedFiles:
    def test_single_removed(self):
        old = [_entry("a.ln4"), _entry("b.ln4")]
        new = [_entry("a.ln4")]
        diff = compare_manifests(old, new)
        assert diff.has_changes
        assert diff.removed == ["b.ln4"]
        assert diff.added == []

    def test_all_removed(self):
        old = [_entry("a.ln4"), _entry("b.ln4")]
        diff = compare_manifests(old, [])
        assert sorted(diff.removed) == ["a.ln4", "b.ln4"]

    def test_removed_sorted(self):
        old = [_entry("a.ln4"), _entry("b.ln4"), _entry("c.ln4")]
        new = [_entry("b.ln4")]
        diff = compare_manifests(old, new)
        assert diff.removed == sorted(diff.removed)


class TestModifiedFiles:
    def test_hash_changed(self):
        old = [_entry("a.ln4", sha256="a" * 64)]
        new = [_entry("a.ln4", sha256="b" * 64)]
        diff = compare_manifests(old, new)
        assert len(diff.modified) == 1
        assert diff.modified[0].changes.hash_changed
        assert diff.modified[0].changes.old_hash == "a" * 64
        assert diff.modified[0].changes.new_hash == "b" * 64

    def test_size_changed(self):
        old = [_entry("a.ln4", size=100)]
        new = [_entry("a.ln4", size=200)]
        diff = compare_manifests(old, new)
        assert len(diff.modified) == 1
        assert diff.modified[0].changes.size_changed
        assert diff.modified[0].changes.old_size == 100
        assert diff.modified[0].changes.new_size == 200

    def test_classification_changed(self):
        old = [_entry("a.ln4", classification="structured_ln4")]
        new = [_entry("a.ln4", classification="unstructured_ln4", structure=None)]
        diff = compare_manifests(old, new)
        assert len(diff.modified) == 1
        assert diff.modified[0].changes.classification_changed
        assert diff.modified[0].changes.old_classification == "structured_ln4"
        assert diff.modified[0].changes.new_classification == "unstructured_ln4"

    def test_structure_changed(self):
        old_struct = Ln4Structure(meta4object="O", item_type="METHOD", item_name="M", rule_id="R1", rule_date="2020")
        new_struct = Ln4Structure(meta4object="O", item_type="METHOD", item_name="M", rule_id="R2", rule_date="2021")
        old = [_entry("a.ln4", structure=old_struct)]
        new = [_entry("a.ln4", structure=new_struct)]
        diff = compare_manifests(old, new)
        assert len(diff.modified) == 1
        assert diff.modified[0].changes.structure_changed

    def test_unchanged_hash_and_size_no_modification(self):
        e1 = _entry("a.ln4", sha256="a" * 64, size=100)
        e2 = _entry("a.ln4", sha256="a" * 64, size=100)
        diff = compare_manifests([e1], [e2])
        assert not diff.has_changes

    def test_modified_sorted(self):
        old = [_entry("b.ln4", sha256="a" * 64), _entry("a.ln4", sha256="a" * 64)]
        new = [_entry("b.ln4", sha256="b" * 64), _entry("a.ln4", sha256="c" * 64)]
        diff = compare_manifests(old, new)
        paths = [m.path for m in diff.modified]
        assert paths == sorted(paths)


class TestRename:
    def test_rename_as_remove_plus_add(self):
        old = [_entry("old_name.ln4")]
        new = [_entry("new_name.ln4")]
        diff = compare_manifests(old, new)
        assert "old_name.ln4" in diff.removed
        assert "new_name.ln4" in diff.added
        assert diff.modified == []

    def test_has_changes_on_rename(self):
        old = [_entry("old.ln4")]
        new = [_entry("new.ln4")]
        diff = compare_manifests(old, new)
        assert diff.has_changes


class TestEmptyManifests:
    def test_both_empty(self):
        diff = compare_manifests([], [])
        assert not diff.has_changes
        assert diff.added == []
        assert diff.removed == []
        assert diff.unchanged == []
