"""
Tests via JSON manipulation and CLI for corpus-manifest-v1 validation.

Each test builds a CorpusManifest directly (bypassing create_inventory) to
construct intentionally invalid manifests, then exercises the full
`corpus verify` CLI or the deserialization layer to verify:
  - exit code != 0
  - structured error in stderr (no Traceback, no TypeError)
  - specific error code visible in combined output

Coverage areas:
  - Finding 3: extension validation (mismatch, edge cases, non-string type)
  - Finding 4: source_root coherence (cases A-D, non-string types)
  - Finding 7: created_at field types (number, boolean, null, list)
"""
import json
from pathlib import Path

import pytest

from peoplenet_process_extractor.cli import main
from peoplenet_process_extractor.corpus.inventory import build_summary
from peoplenet_process_extractor.corpus.models import (
    CorpusManifest,
    FileEntry,
    GitInfo,
    RootInfo,
)
from peoplenet_process_extractor.corpus.serialization import serialize_manifest
from peoplenet_process_extractor.corpus.validation import validate_manifest

FIXTURE_CORPUS = Path(__file__).parent.parent / "fixtures" / "corpus"


def _run(*args: str) -> int:
    return main(list(args))


def _entry(
    path: str,
    extension: str,
    source_root,
    classification: str = "unstructured_ln4",
) -> FileEntry:
    return FileEntry(
        path=path,
        sha256="a" * 64,
        size_bytes=100,
        extension=extension,
        source_root=source_root,
        classification=classification,
    )


def _manifest(entry: FileEntry, included_source_roots: list) -> CorpusManifest:
    return CorpusManifest(
        schema_version="1.0",
        corpus_id="test-corpus",
        created_at="2026-06-23T12:00:00+00:00",
        root=RootInfo(label="corpus"),
        git=GitInfo(commit=None, dirty=None),
        included_source_roots=included_source_roots,
        files=[entry],
        summary=build_summary([entry]),
    )


def _write(manifest: CorpusManifest, path: Path) -> Path:
    """Serialize without validation and write to disk."""
    path.write_text(serialize_manifest(manifest), encoding="utf-8")
    return path


def _assert_no_crash(capsys) -> str:
    """Read captured output; assert no Traceback or TypeError; return combined string."""
    out, err = capsys.readouterr()
    combined = out + err
    assert "Traceback" not in combined, f"Traceback found in output:\n{combined}"
    assert "TypeError" not in combined, f"TypeError found in output:\n{combined}"
    return combined


# ── Finding 3 — extension validation ──────────────────────────────────────


class TestExtensionJsonCli:
    """extension field validation from JSON and CLI (corpus verify)."""

    def _cp_entry(self) -> FileEntry:
        return _entry("CP/file.ln4", ".ln4", "CP")

    def test_extension_mismatch_exit_code(self, tmp_path):
        """extension='.json' for a .ln4 path → exit code != 0."""
        e = self._cp_entry()
        e.extension = ".json"
        mpath = _write(_manifest(e, ["CP"]), tmp_path / "manifest.json")
        code = _run("corpus", "verify", "--corpus-root", str(FIXTURE_CORPUS), str(mpath))
        assert code != 0

    def test_extension_mismatch_error_in_output(self, tmp_path, capsys):
        """extension='.json' for a .ln4 path → 'extension_path_mismatch' visible in output."""
        e = self._cp_entry()
        e.extension = ".json"
        mpath = _write(_manifest(e, ["CP"]), tmp_path / "manifest.json")
        _run("corpus", "verify", "--corpus-root", str(FIXTURE_CORPUS), str(mpath))
        combined = _assert_no_crash(capsys)
        assert "extension_path_mismatch" in combined

    def test_extension_mismatch_path_visible(self, tmp_path, capsys):
        """Affected path appears in the error message."""
        e = self._cp_entry()
        e.extension = ".json"
        mpath = _write(_manifest(e, ["CP"]), tmp_path / "manifest.json")
        _run("corpus", "verify", "--corpus-root", str(FIXTURE_CORPUS), str(mpath))
        combined = _assert_no_crash(capsys)
        assert "CP/file.ln4" in combined

    def test_uppercase_filename_lowercase_extension_valid(self):
        """Path 'CP/FILE.LN4' with extension='.ln4' is valid (suffix lowercased)."""
        e = _entry("CP/FILE.LN4", ".ln4", "CP")
        errors = validate_manifest(_manifest(e, ["CP"]))
        assert not any(err.code == "extension_path_mismatch" for err in errors)

    def test_multi_dot_filename_extension_valid(self):
        """Path 'CP/archive.test.ln4' with extension='.ln4' uses last dot segment."""
        e = _entry("CP/archive.test.ln4", ".ln4", "CP")
        errors = validate_manifest(_manifest(e, ["CP"]))
        assert not any(err.code == "extension_path_mismatch" for err in errors)

    def test_no_extension_empty_string_valid(self):
        """File without extension uses '' for the extension field."""
        e = _entry("CP/Makefile", "", "CP", classification="other_supported")
        errors = validate_manifest(_manifest(e, ["CP"]))
        assert not any(err.code == "extension_path_mismatch" for err in errors)

    def test_non_string_extension_structured_error(self, tmp_path, capsys):
        """extension=42 → structured DeserializationError, no crash."""
        e = self._cp_entry()
        m = _manifest(e, ["CP"])
        data = json.loads(serialize_manifest(m))
        data["files"][0]["extension"] = 42
        mpath = tmp_path / "manifest.json"
        mpath.write_text(json.dumps(data))

        code = _run("corpus", "verify", "--corpus-root", str(FIXTURE_CORPUS), str(mpath))
        assert code != 0
        combined = _assert_no_crash(capsys)
        assert "Field 'extension' must be a string" in combined

    @pytest.mark.parametrize("bad_value,expected_fragment", [
        (True, "Field 'extension' must be a string"),
        (None, "required field 'extension'"),
        ([".ln4"], "Field 'extension' must be a string"),
        ({".ln4": 1}, "Field 'extension' must be a string"),
    ])
    def test_non_string_extension_all_types(self, tmp_path, capsys, bad_value, expected_fragment):
        """boolean, null, list, object for extension → specific structured error, no crash."""
        e = self._cp_entry()
        m = _manifest(e, ["CP"])
        data = json.loads(serialize_manifest(m))
        data["files"][0]["extension"] = bad_value
        mpath = tmp_path / "manifest.json"
        mpath.write_text(json.dumps(data))

        code = _run("corpus", "verify", "--corpus-root", str(FIXTURE_CORPUS), str(mpath))
        assert code != 0
        combined = _assert_no_crash(capsys)
        assert expected_fragment in combined


# ── Finding 4 — source_root coherence ─────────────────────────────────────


class TestSourceRootJsonCli:
    """source_root coherence validation via JSON and CLI (corpus verify)."""

    def _verify(self, tmp_path: Path, m: CorpusManifest, capsys) -> tuple[int, str]:
        mpath = _write(m, tmp_path / "manifest.json")
        code = _run("corpus", "verify", "--corpus-root", str(FIXTURE_CORPUS), str(mpath))
        combined = _assert_no_crash(capsys)
        return code, combined

    def test_case_a_source_root_vs_path(self, tmp_path, capsys):
        """Case A: path='CP/file.ln4', source_root='GTO', included=['CP','GTO'] → mismatch."""
        e = _entry("CP/file.ln4", ".ln4", "GTO")
        code, combined = self._verify(tmp_path, _manifest(e, ["CP", "GTO"]), capsys)
        assert code != 0
        assert "source_root_mismatch" in combined

    def test_case_b_null_source_root_for_subdir(self, tmp_path, capsys):
        """Case B: path='CP/file.ln4', source_root=null → source_root_mismatch."""
        e = _entry("CP/file.ln4", ".ln4", None)
        code, combined = self._verify(tmp_path, _manifest(e, ["CP"]), capsys)
        assert code != 0
        assert "source_root_mismatch" in combined

    def test_case_c_empty_scope_rejects_subdir_file(self, tmp_path, capsys):
        """Case C: path='CP/file.ln4', source_root='CP', included=[] → not_in_scope."""
        e = _entry("CP/file.ln4", ".ln4", "CP")
        code, combined = self._verify(tmp_path, _manifest(e, []), capsys)
        assert code != 0
        assert "source_root_not_in_scope" in combined

    def test_case_d_root_file_with_non_null_source_root(self, tmp_path, capsys):
        """Case D: path='root_file.ln4', source_root='CP' → source_root_mismatch."""
        e = _entry("root_file.ln4", ".ln4", "CP")
        code, combined = self._verify(tmp_path, _manifest(e, ["CP"]), capsys)
        assert code != 0
        assert "source_root_mismatch" in combined

    @pytest.mark.parametrize("bad_value", [42, True, [], {"a": 1}])
    def test_source_root_type_errors(self, tmp_path, capsys, bad_value):
        """Non-string non-null source_root → DeserializationError, no crash."""
        e = _entry("CP/file.ln4", ".ln4", "CP")
        m = _manifest(e, ["CP"])
        data = json.loads(serialize_manifest(m))
        data["files"][0]["source_root"] = bad_value
        mpath = tmp_path / "manifest.json"
        mpath.write_text(json.dumps(data))

        code = _run("corpus", "verify", "--corpus-root", str(FIXTURE_CORPUS), str(mpath))
        assert code != 0
        _assert_no_crash(capsys)


# ── Finding 7 — created_at field types ────────────────────────────────────


class TestCreatedAtTypes:
    """Non-string created_at values → structured error, no crash."""

    @pytest.mark.parametrize("bad_value,expected_fragment", [
        (42, "Field 'created_at' must be a string"),
        (True, "Field 'created_at' must be a string"),
        (None, "required field 'created_at'"),
        (["2026", "01", "01"], "Field 'created_at' must be a string"),
        ({}, "Field 'created_at' must be a string"),
    ])
    def test_non_string_created_at(self, tmp_path, capsys, bad_value, expected_fragment):
        """number, boolean, null, list, object for created_at → specific structured error, no crash."""
        e = _entry("CP/file.ln4", ".ln4", "CP")
        m = _manifest(e, ["CP"])
        data = json.loads(serialize_manifest(m))
        data["created_at"] = bad_value
        mpath = tmp_path / "manifest.json"
        mpath.write_text(json.dumps(data))

        code = _run("corpus", "verify", "--corpus-root", str(FIXTURE_CORPUS), str(mpath))
        assert code != 0
        combined = _assert_no_crash(capsys)
        assert expected_fragment in combined
