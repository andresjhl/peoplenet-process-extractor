"""Tests for corpus inventory service (create_inventory, verify_corpus)."""
import json
from pathlib import Path

import pytest

from peoplenet_process_extractor.corpus.service import create_inventory, verify_corpus

FIXTURE_CORPUS = Path(__file__).parent.parent / "fixtures" / "corpus"


class TestCreateInventory:
    def test_creates_valid_manifest(self, tmp_path):
        output = tmp_path / "manifest.json"
        code, messages = create_inventory(
            corpus_root=FIXTURE_CORPUS,
            output_path=output,
        )
        assert code == 0
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["schema_version"] == "1.0"
        assert data["summary"]["total_files"] > 0

    def test_no_absolute_paths_in_manifest(self, tmp_path):
        output = tmp_path / "manifest.json"
        create_inventory(corpus_root=FIXTURE_CORPUS, output_path=output)
        data = json.loads(output.read_text())
        for f in data["files"]:
            assert not f["path"].startswith("/")
            assert not (len(f["path"]) >= 2 and f["path"][1] == ":")
        # corpus root must not appear in the manifest
        root_str = str(FIXTURE_CORPUS).replace("\\", "/")
        manifest_text = output.read_text()
        assert root_str not in manifest_text

    def test_no_overwrite_without_force(self, tmp_path):
        output = tmp_path / "manifest.json"
        output.write_text("{}")
        code, messages = create_inventory(
            corpus_root=FIXTURE_CORPUS,
            output_path=output,
        )
        assert code != 0
        assert any("--force" in m or "already exists" in m for m in messages)
        # Original content must be preserved
        assert output.read_text() == "{}"

    def test_force_overwrites(self, tmp_path):
        output = tmp_path / "manifest.json"
        output.write_text("{}")
        code, messages = create_inventory(
            corpus_root=FIXTURE_CORPUS,
            output_path=output,
            force=True,
        )
        assert code == 0
        data = json.loads(output.read_text())
        assert "schema_version" in data

    def test_explicit_corpus_id(self, tmp_path):
        output = tmp_path / "manifest.json"
        create_inventory(
            corpus_root=FIXTURE_CORPUS,
            output_path=output,
            corpus_id="my-custom-id",
        )
        data = json.loads(output.read_text())
        assert data["corpus_id"] == "my-custom-id"

    def test_derived_corpus_id(self, tmp_path):
        output = tmp_path / "manifest.json"
        create_inventory(corpus_root=FIXTURE_CORPUS, output_path=output)
        data = json.loads(output.read_text())
        assert data["corpus_id"] == FIXTURE_CORPUS.name.lower()

    def test_source_root_filter(self, tmp_path):
        output = tmp_path / "manifest.json"
        code, messages = create_inventory(
            corpus_root=FIXTURE_CORPUS,
            output_path=output,
            source_roots=["CP"],
        )
        assert code == 0
        data = json.loads(output.read_text())
        assert data["included_source_roots"] == ["CP"]
        for f in data["files"]:
            assert f["source_root"] == "CP"

    def test_nonexistent_source_root_fails(self, tmp_path):
        output = tmp_path / "manifest.json"
        code, messages = create_inventory(
            corpus_root=FIXTURE_CORPUS,
            output_path=output,
            source_roots=["DOES_NOT_EXIST"],
        )
        assert code != 0
        assert any("DOES_NOT_EXIST" in m for m in messages)
        assert not output.exists()

    def test_nonexistent_corpus_fails(self, tmp_path):
        output = tmp_path / "manifest.json"
        code, messages = create_inventory(
            corpus_root=tmp_path / "nonexistent",
            output_path=output,
        )
        assert code != 0
        assert not output.exists()

    def test_symlink_corpus_fails(self, tmp_path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link = tmp_path / "link"
        try:
            link.symlink_to(real_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Cannot create symlinks in this environment")
        output = tmp_path / "manifest.json"
        code, messages = create_inventory(corpus_root=link, output_path=output)
        assert code != 0
        assert any("symlink" in m.lower() for m in messages)

    def test_no_partial_output_on_failure(self, tmp_path):
        output = tmp_path / "manifest.json"
        code, _ = create_inventory(
            corpus_root=tmp_path / "nonexistent",
            output_path=output,
        )
        assert code != 0
        assert not output.exists()

    def test_corpus_root_not_in_json(self, tmp_path):
        output = tmp_path / "manifest.json"
        create_inventory(corpus_root=FIXTURE_CORPUS, output_path=output)
        text = output.read_text()
        # The absolute path of the corpus root must not appear verbatim in the JSON.
        corpus_str = str(FIXTURE_CORPUS)
        assert corpus_str not in text

    def test_files_sorted_in_output(self, tmp_path):
        output = tmp_path / "manifest.json"
        create_inventory(corpus_root=FIXTURE_CORPUS, output_path=output)
        data = json.loads(output.read_text())
        paths = [f["path"] for f in data["files"]]
        assert paths == sorted(paths)

    def test_empty_corpus(self, tmp_path):
        empty = tmp_path / "empty_corpus"
        empty.mkdir()
        output = tmp_path / "manifest.json"
        code, messages = create_inventory(corpus_root=empty, output_path=output)
        assert code == 0
        data = json.loads(output.read_text())
        assert data["summary"]["total_files"] == 0

    def test_deterministic_output(self, tmp_path):
        out1 = tmp_path / "m1.json"
        out2 = tmp_path / "m2.json"
        now = __import__("datetime").datetime(2026, 6, 23, 12, 0, 0, tzinfo=__import__("datetime").timezone.utc)
        create_inventory(corpus_root=FIXTURE_CORPUS, output_path=out1, now=now)
        create_inventory(corpus_root=FIXTURE_CORPUS, output_path=out2, force=True, now=now)
        # Sort-stable and hash-stable: same files → same content
        d1 = json.loads(out1.read_text())
        d2 = json.loads(out2.read_text())
        assert d1["files"] == d2["files"]
        assert d1["summary"] == d2["summary"]


class TestVerifyCorpus:
    def _create(self, tmp_path, source_roots=None):
        output = tmp_path / "manifest.json"
        code, _ = create_inventory(
            corpus_root=FIXTURE_CORPUS,
            output_path=output,
            source_roots=source_roots,
        )
        assert code == 0
        return output

    def test_unchanged_corpus(self, tmp_path):
        manifest = self._create(tmp_path)
        code, diff, messages = verify_corpus(FIXTURE_CORPUS, manifest)
        assert code == 0
        assert diff is not None
        assert not diff.has_changes

    def test_added_file(self, tmp_path):
        # Build a corpus copy without a file, then add the file.
        corpus_copy = tmp_path / "corpus_copy"
        import shutil
        shutil.copytree(FIXTURE_CORPUS, corpus_copy)

        manifest_path = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus_copy, output_path=manifest_path)

        # Add a new file.
        new_file = corpus_copy / "new_file.ln4"
        new_file.write_text("new content")

        code, diff, messages = verify_corpus(corpus_copy, manifest_path)
        assert code != 0
        assert diff is not None
        assert any("new_file.ln4" in a for a in diff.added)

    def test_removed_file(self, tmp_path):
        corpus_copy = tmp_path / "corpus_copy"
        import shutil
        shutil.copytree(FIXTURE_CORPUS, corpus_copy)

        manifest_path = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus_copy, output_path=manifest_path)

        # Remove a file.
        (corpus_copy / "outside_structure.ln4").unlink()

        code, diff, messages = verify_corpus(corpus_copy, manifest_path)
        assert code != 0
        assert diff is not None
        assert any("outside_structure.ln4" in r for r in diff.removed)

    def test_modified_file(self, tmp_path):
        corpus_copy = tmp_path / "corpus_copy"
        import shutil
        shutil.copytree(FIXTURE_CORPUS, corpus_copy)

        manifest_path = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus_copy, output_path=manifest_path)

        # Modify a file.
        target = corpus_copy / "outside_structure.ln4"
        target.write_text("completely different content")

        code, diff, messages = verify_corpus(corpus_copy, manifest_path)
        assert code != 0
        assert any("outside_structure.ln4" in m.path for m in diff.modified)
        mod = next(m for m in diff.modified if "outside_structure.ln4" in m.path)
        assert mod.changes.hash_changed

    def test_invalid_manifest_json(self, tmp_path):
        manifest_path = tmp_path / "bad.json"
        manifest_path.write_text("not valid json {")
        code, diff, messages = verify_corpus(FIXTURE_CORPUS, manifest_path)
        assert code != 0
        assert diff is None

    def test_nonexistent_corpus(self, tmp_path):
        manifest_path = self._create(tmp_path)
        code, diff, messages = verify_corpus(tmp_path / "nonexistent", manifest_path)
        assert code != 0
        assert diff is None

    def test_nonexistent_manifest(self, tmp_path):
        code, diff, messages = verify_corpus(FIXTURE_CORPUS, tmp_path / "no_manifest.json")
        assert code != 0
        assert diff is None

    def test_verify_from_different_cwd(self, tmp_path, monkeypatch):
        """Verify that paths resolve correctly regardless of cwd."""
        manifest_path = self._create(tmp_path)
        monkeypatch.chdir(tmp_path)
        code, diff, _ = verify_corpus(FIXTURE_CORPUS, manifest_path)
        assert code == 0

    def test_manipulated_manifest_hash(self, tmp_path):
        import shutil
        corpus_copy = tmp_path / "corpus_copy"
        shutil.copytree(FIXTURE_CORPUS, corpus_copy)
        manifest_path = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus_copy, output_path=manifest_path)

        # Tamper with the manifest — change a hash.
        data = json.loads(manifest_path.read_text())
        data["files"][0]["sha256"] = "b" * 64
        # Recompute summary to pass validation
        data["summary"]["total_files"] = data["summary"]["total_files"]  # keep same
        manifest_path.write_text(json.dumps(data, indent=2))

        code, diff, messages = verify_corpus(corpus_copy, manifest_path)
        # Either validation fails (summary mismatch) or verify detects modification
        assert code != 0

    def test_lf_crlf_difference_detected(self, tmp_path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        lf_file = corpus / "test.ln4"
        lf_file.write_bytes(b"content\n")

        manifest_path = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus, output_path=manifest_path)

        # Change LF to CRLF.
        lf_file.write_bytes(b"content\r\n")

        code, diff, messages = verify_corpus(corpus, manifest_path)
        assert code != 0
        assert diff is not None
        assert diff.has_changes

    def test_new_root_outside_scope_not_surfaced(self, tmp_path):
        """A new first-level directory outside included_source_roots is not detected."""
        import shutil
        corpus_copy = tmp_path / "corpus_copy"
        shutil.copytree(FIXTURE_CORPUS, corpus_copy)

        manifest_path = tmp_path / "manifest.json"
        code, _ = create_inventory(
            corpus_root=corpus_copy,
            output_path=manifest_path,
            source_roots=["CP"],
        )
        assert code == 0

        new_root = corpus_copy / "NEW_ROOT"
        new_root.mkdir()
        (new_root / "file.ln4").write_text("out of scope content")

        code, diff, messages = verify_corpus(corpus_copy, manifest_path)
        assert code == 0
        assert diff is not None
        assert not diff.has_changes


class TestMultipleSourceRootsFiltering:
    """Finding 5: multi-filter produces exactly the expected paths."""

    def _make_corpus(self, tmp_path: Path) -> Path:
        corpus = tmp_path / "corpus"
        (corpus / "CP").mkdir(parents=True)
        (corpus / "GTO").mkdir()
        (corpus / "OTHER").mkdir()
        (corpus / "CP" / "cp_file.ln4").write_text("cp content")
        (corpus / "GTO" / "gto_file.ln4").write_text("gto content")
        (corpus / "OTHER" / "other_file.ln4").write_text("other content")
        (corpus / "root_file.ln4").write_text("root content")
        return corpus

    def test_multi_filter_exact_paths(self, tmp_path):
        """--source-root CP GTO inventories exactly CP and GTO files, nothing else."""
        corpus = self._make_corpus(tmp_path)
        output = tmp_path / "manifest.json"
        code, messages = create_inventory(
            corpus_root=corpus,
            output_path=output,
            source_roots=["CP", "GTO"],
        )
        assert code == 0, f"create_inventory failed: {messages}"
        data = json.loads(output.read_text())
        paths = sorted(f["path"] for f in data["files"])
        assert paths == ["CP/cp_file.ln4", "GTO/gto_file.ln4"]
        assert "OTHER/other_file.ln4" not in paths
        assert "root_file.ln4" not in paths
        assert data["included_source_roots"] == ["CP", "GTO"]

    def test_multi_filter_sorted_regardless_of_cli_order(self, tmp_path):
        """included_source_roots is always sorted, regardless of argument order."""
        corpus = self._make_corpus(tmp_path)
        output = tmp_path / "manifest.json"
        create_inventory(
            corpus_root=corpus,
            output_path=output,
            source_roots=["GTO", "CP"],  # Reversed
        )
        data = json.loads(output.read_text())
        assert data["included_source_roots"] == ["CP", "GTO"]


class TestDuplicateSourceRootFilter:
    """Finding 6: duplicate --source-root values are normalized silently."""

    def _make_cp_corpus(self, tmp_path: Path) -> Path:
        corpus = tmp_path / "corpus"
        (corpus / "CP").mkdir(parents=True)
        (corpus / "CP" / "file.ln4").write_text("cp content")
        return corpus

    def test_duplicate_normalizes_to_single_root(self, tmp_path):
        """source_roots=['CP','CP'] produces included_source_roots=['CP']."""
        corpus = self._make_cp_corpus(tmp_path)
        output = tmp_path / "manifest.json"
        code, messages = create_inventory(
            corpus_root=corpus,
            output_path=output,
            source_roots=["CP", "CP"],
        )
        assert code == 0, f"Failed: {messages}"
        data = json.loads(output.read_text())
        assert data["included_source_roots"] == ["CP"]

    def test_duplicate_no_duplicate_files(self, tmp_path):
        """No file is inventoried more than once when the root is repeated."""
        corpus = self._make_cp_corpus(tmp_path)
        output = tmp_path / "manifest.json"
        create_inventory(
            corpus_root=corpus,
            output_path=output,
            source_roots=["CP", "CP"],
        )
        data = json.loads(output.read_text())
        paths = [f["path"] for f in data["files"]]
        assert paths.count("CP/file.ln4") == 1
        assert len(paths) == len(set(paths))


class TestRootOnlyVerify:
    """
    Verify semantics when included_source_roots=[].

    A root-only snapshot contains exclusively files directly at the corpus root.
    During verify, subdirectory files (including new physical roots) must be ignored.
    """

    def _make_root_only_corpus(self, tmp_path: Path) -> Path:
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "root_file.ln4").write_text("root content")
        return corpus

    def _create_root_only_manifest(self, corpus: Path, output: Path) -> None:
        code, messages = create_inventory(corpus_root=corpus, output_path=output)
        assert code == 0, f"create_inventory failed: {messages}"
        data = json.loads(output.read_text())
        # Confirm the manifest correctly records no source roots.
        assert data["included_source_roots"] == []

    def test_case_a_root_only_unchanged(self, tmp_path):
        """Case A: root-only corpus without changes → verify returns 0."""
        corpus = self._make_root_only_corpus(tmp_path)
        manifest = tmp_path / "manifest.json"
        self._create_root_only_manifest(corpus, manifest)

        code, diff, messages = verify_corpus(corpus, manifest)
        assert code == 0, f"Expected no changes: {messages}"
        assert diff is not None
        assert not diff.has_changes

    def test_case_b_new_physical_root_ignored(self, tmp_path):
        """Case B: new subdirectory appears after snapshot → verify still returns 0."""
        corpus = self._make_root_only_corpus(tmp_path)
        manifest = tmp_path / "manifest.json"
        self._create_root_only_manifest(corpus, manifest)

        # Add a new first-level directory with a file.
        (corpus / "CP").mkdir()
        (corpus / "CP" / "cp_file.ln4").write_text("new subdir content")

        code, diff, messages = verify_corpus(corpus, manifest)
        assert code == 0, f"New physical root should be ignored: {messages}"
        assert diff is not None
        assert not diff.has_changes

    def test_case_c_new_root_file_detected_as_added(self, tmp_path):
        """Case C: new file directly at corpus root → detected as added."""
        corpus = self._make_root_only_corpus(tmp_path)
        manifest = tmp_path / "manifest.json"
        self._create_root_only_manifest(corpus, manifest)

        (corpus / "another_root_file.ln4").write_text("another root file")

        code, diff, messages = verify_corpus(corpus, manifest)
        assert code != 0
        assert diff is not None
        assert any("another_root_file.ln4" in a for a in diff.added)

    def test_case_d_modified_root_file_detected(self, tmp_path):
        """Case D: existing root file modified → detected as modified."""
        corpus = self._make_root_only_corpus(tmp_path)
        manifest = tmp_path / "manifest.json"
        self._create_root_only_manifest(corpus, manifest)

        (corpus / "root_file.ln4").write_text("completely different content")

        code, diff, messages = verify_corpus(corpus, manifest)
        assert code != 0
        assert diff is not None
        assert any("root_file.ln4" in m.path for m in diff.modified)

    def test_case_e_removed_root_file_detected(self, tmp_path):
        """Case E: existing root file removed → detected as removed."""
        corpus = self._make_root_only_corpus(tmp_path)
        manifest = tmp_path / "manifest.json"
        self._create_root_only_manifest(corpus, manifest)

        (corpus / "root_file.ln4").unlink()

        code, diff, messages = verify_corpus(corpus, manifest)
        assert code != 0
        assert diff is not None
        assert any("root_file.ln4" in r for r in diff.removed)
