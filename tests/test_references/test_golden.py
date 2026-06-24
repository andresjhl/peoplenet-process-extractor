"""Golden tests for reference-extraction-v1."""
from __future__ import annotations

import json
import shutil
from pathlib import Path


from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.index.builder import build_index
from peoplenet_process_extractor.references.extraction import extract_references

from .conftest import FIXTURE_CORPUS, FIXED_NOW

GOLDEN_PATH = Path(__file__).parent.parent / "golden" / "reference-extraction-v1.json"


def _build_extraction(tmp_path: Path) -> Path:
    """Build an extraction from a non-git copy of the fixture corpus with FIXED_NOW."""
    corpus = tmp_path / "corpus"
    shutil.copytree(FIXTURE_CORPUS, corpus)

    manifest = tmp_path / "corpus-manifest.json"
    code, msgs = create_inventory(
        corpus_root=corpus,
        output_path=manifest,
        corpus_id="references-corpus",
        now=FIXED_NOW,
    )
    assert code == 0, f"create_inventory failed: {msgs}"

    db = tmp_path / "structural-index.sqlite"
    code, msgs = build_index(
        corpus_root=corpus,
        manifest_path=manifest,
        output_path=db,
        now=FIXED_NOW,
    )
    assert code == 0, f"build_index failed: {msgs}"

    out = tmp_path / "reference-extraction.json"
    code, msgs = extract_references(
        corpus_root=corpus,
        manifest_path=manifest,
        index_path=db,
        output_path=out,
        now=FIXED_NOW,
    )
    assert code == 0, f"extract_references failed: {msgs}"
    return out


class TestGoldenFile:
    def test_golden_file_exists(self):
        assert GOLDEN_PATH.exists(), f"Golden file not found: {GOLDEN_PATH}"

    def test_golden_matches(self, tmp_path):
        """Build extraction and compare against committed golden (excluding env-dependent fields)."""
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        out = _build_extraction(tmp_path)
        actual = json.loads(out.read_text(encoding="utf-8"))

        # generator.version is the installed package version — varies by environment
        # Strip it for comparison
        def strip_env_fields(data):
            d = dict(data)
            if "generator" in d:
                d["generator"] = {k: v for k, v in d["generator"].items() if k != "version"}
            return d

        golden_stripped = strip_env_fields(golden)
        actual_stripped = strip_env_fields(actual)
        assert actual_stripped == golden_stripped, (
            "Extraction does not match golden. "
            "If fixtures changed, regenerate with: uv run python tmp/generate_golden_references.py"
        )

    def test_golden_has_calls(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        assert golden["summary"]["calls_total"] > 0

    def test_golden_has_file_without_calls(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        files_no_calls = [f for f in golden["files"] if not f["references"]]
        assert files_no_calls, "Golden must include files with zero calls"

    def test_golden_has_malformed(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        malformed = [
            r
            for f in golden["files"]
            for r in f["references"]
            if r["status"] == "malformed"
        ]
        assert malformed, "Golden must contain at least one malformed reference"

    def test_golden_paths_use_forward_slashes(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        for f in golden["files"]:
            assert "\\" not in f["path"], f"Backslash in path: {f['path']!r}"

    def test_golden_has_crlf_file(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        crlf_files = [f for f in golden["files"] if f["line_ending"] == "crlf"]
        assert crlf_files, "Golden must include a CRLF file"

    def test_golden_has_bom_file(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        bom_files = [f for f in golden["files"] if f["encoding"] == "utf-8-bom"]
        assert bom_files, "Golden must include a UTF-8 BOM file"

    def test_golden_files_sorted_by_path(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        paths = [f["path"] for f in golden["files"]]
        assert paths == sorted(paths), "Files in golden are not sorted by path"

    def test_golden_references_sorted_by_start_offset(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        for f in golden["files"]:
            offsets = [r["start_offset"] for r in f["references"]]
            assert offsets == sorted(offsets), (
                f"References not sorted by start_offset in {f['path']}"
            )

    def test_golden_reference_ids_unique(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        ids = [r["id"] for f in golden["files"] for r in f["references"]]
        assert len(ids) == len(set(ids)), "Duplicate reference IDs in golden"

    def test_golden_no_crlf_in_json(self):
        raw = GOLDEN_PATH.read_bytes()
        assert b"\r\n" not in raw, "Golden file contains CRLF bytes"

    def test_golden_trailing_newline(self):
        text = GOLDEN_PATH.read_text(encoding="utf-8")
        assert text.endswith("\n"), "Golden file does not end with newline"
