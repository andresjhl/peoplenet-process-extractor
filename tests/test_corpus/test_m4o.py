"""Tests for INC-0006: META4OBJECT resource support in corpus-manifest-v1."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from peoplenet_process_extractor.corpus.comparison import compare_file_entries
from peoplenet_process_extractor.corpus.enums import Classification
from peoplenet_process_extractor.corpus.inventory import build_summary, classify_file
from peoplenet_process_extractor.corpus.models import (
    CorpusManifest,
    FileEntry,
    GitInfo,
    M4oStructure,
    RootInfo,
)
from peoplenet_process_extractor.corpus.path_parsing import parse_m4o_path
from peoplenet_process_extractor.corpus.serialization import (
    deserialize_manifest,
    serialize_manifest,
)
from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.corpus.validation import validate_manifest

M4O_FIXTURE = Path(__file__).parent.parent / "fixtures" / "m4o_manifest_corpus"
GOLDEN_PATH = Path(__file__).parent.parent / "golden" / "m4o-corpus-manifest-v1.json"
FIXED_NOW = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)


# ── helpers ───────────────────────────────────────────────────────────────────


def _m4o_entry(
    path: str,
    classification: str,
    id_t3: str,
    id_node: str | None = None,
    source_root: str = "CP",
    sha256: str | None = None,
) -> FileEntry:
    return FileEntry(
        path=path,
        sha256=(sha256 or "a" * 64),
        size_bytes=2,
        extension=".json",
        source_root=source_root,
        classification=classification,
        m4o_structure=M4oStructure(id_t3=id_t3, id_node=id_node),
    )


def _valid_m4o_manifest(files: list[FileEntry] | None = None) -> CorpusManifest:
    if files is None:
        files = [
            _m4o_entry(
                "CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json",
                "m4o_node_json",
                id_t3="OBJ_T3_A",
                id_node="NODE_X",
            )
        ]
    return CorpusManifest(
        schema_version="1.1",
        corpus_id="test-m4o",
        created_at="2026-06-24T12:00:00+00:00",
        root=RootInfo(label="m4o_manifest_corpus"),
        git=GitInfo(commit=None, dirty=None),
        included_source_roots=["CP"],
        files=files,
        summary=build_summary(files),
    )


# ── Path parsing ──────────────────────────────────────────────────────────────


class TestParseMm4oPathNode:
    def test_valid_node(self):
        cls, m4o, warnings = parse_m4o_path("CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json")
        assert cls == Classification.M4O_NODE_JSON
        assert m4o is not None
        assert m4o.id_t3 == "OBJ_T3_A"
        assert m4o.id_node == "NODE_X"
        assert warnings == []

    def test_valid_alias(self):
        cls, m4o, warnings = parse_m4o_path(
            "CP/META4OBJECT/OBJ_T3_A/M4O ALIAS RESOLUTION/NODE_X/node_x.json"
        )
        assert cls == Classification.M4O_ALIAS_JSON
        assert m4o is not None
        assert m4o.id_t3 == "OBJ_T3_A"
        assert m4o.id_node == "NODE_X"
        assert warnings == []

    def test_valid_mapping(self):
        cls, m4o, warnings = parse_m4o_path(
            "CP/META4OBJECT/OBJ_T3_A/MAPPING META4OBJECT/OBJ_T3_A/obj_t3_a.json"
        )
        assert cls == Classification.M4O_MAPPING_JSON
        assert m4o is not None
        assert m4o.id_t3 == "OBJ_T3_A"
        assert m4o.id_node is None
        assert warnings == []

    def test_mapping_mismatched_id_t3(self):
        cls, m4o, warnings = parse_m4o_path(
            "CP/META4OBJECT/OBJ_T3_A/MAPPING META4OBJECT/OBJ_T3_B/obj_t3_a.json"
        )
        assert cls == Classification.OTHER_SUPPORTED
        assert m4o is None
        assert "malformed_m4o_mapping_path" in warnings

    def test_node_missing_id_node_level(self):
        # source_root/META4OBJECT/ID_T3/NODE/file.json — missing ID_NODE level
        cls, m4o, warnings = parse_m4o_path("CP/META4OBJECT/OBJ_T3_A/NODE/file.json")
        assert cls == Classification.OTHER_SUPPORTED
        assert m4o is None
        assert "malformed_m4o_node_path" in warnings

    def test_alias_missing_id_node_level(self):
        cls, m4o, warnings = parse_m4o_path(
            "CP/META4OBJECT/OBJ_T3_A/M4O ALIAS RESOLUTION/file.json"
        )
        assert cls == Classification.OTHER_SUPPORTED
        assert m4o is None
        assert "malformed_m4o_alias_path" in warnings

    def test_t3_root_json_no_warning(self):
        # The root JSON of a T3 is out of scope but not a warning.
        cls, m4o, warnings = parse_m4o_path("CP/META4OBJECT/OBJ_T3_A/obj_t3_a.json")
        assert cls == Classification.OTHER_SUPPORTED
        assert m4o is None
        assert warnings == []

    def test_unknown_subdirectory_no_warning(self):
        cls, m4o, warnings = parse_m4o_path(
            "CP/META4OBJECT/OBJ_T3_A/ANOTHER_RESOURCE/X/file.json"
        )
        assert cls == Classification.OTHER_SUPPORTED
        assert m4o is None
        assert warnings == []

    def test_non_m4o_path(self):
        cls, m4o, warnings = parse_m4o_path("CP/NODE STRUCTURE/OBJ/ITEM/METHOD/M/RULES/M#R1#2020.ln4")
        assert cls == Classification.OTHER_SUPPORTED
        assert m4o is None
        assert warnings == []

    def test_windows_path_normalized(self):
        cls, m4o, warnings = parse_m4o_path(
            "CP\\META4OBJECT\\OBJ_T3_A\\NODE\\NODE_X\\node_x.json"
        )
        assert cls == Classification.M4O_NODE_JSON
        assert m4o is not None
        assert m4o.id_t3 == "OBJ_T3_A"
        assert m4o.id_node == "NODE_X"


# ── Inventory and classification ──────────────────────────────────────────────


class TestClassifyFileM4o:
    def test_m4o_node_json(self):
        assert classify_file("CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json", None) == Classification.M4O_NODE_JSON

    def test_m4o_alias_json(self):
        assert classify_file(
            "CP/META4OBJECT/OBJ_T3_A/M4O ALIAS RESOLUTION/NODE_X/node_x.json", None
        ) == Classification.M4O_ALIAS_JSON

    def test_m4o_mapping_json(self):
        assert classify_file(
            "CP/META4OBJECT/OBJ_T3_A/MAPPING META4OBJECT/OBJ_T3_A/obj_t3_a.json", None
        ) == Classification.M4O_MAPPING_JSON

    def test_invalid_mapping_other_supported(self):
        assert classify_file(
            "CP/META4OBJECT/OBJ_T3_A/MAPPING META4OBJECT/OBJ_T3_B/obj.json", None
        ) == Classification.OTHER_SUPPORTED

    def test_unknown_subdirectory_other_supported_no_warning(self):
        assert classify_file(
            "CP/META4OBJECT/OBJ_T3_A/ANOTHER_RESOURCE/X/file.json", None
        ) == Classification.OTHER_SUPPORTED

    def test_non_json_in_m4o_other_supported(self):
        assert classify_file("CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.txt", None) == Classification.OTHER_SUPPORTED

    def test_metadata_json_priority_over_m4o(self):
        # metadata.json inside META4OBJECT still gets metadata_json (priority 4 > 5-7)
        assert classify_file(
            "CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/metadata.json", None
        ) == Classification.METADATA_JSON


# ── Serialization round trips ─────────────────────────────────────────────────


class TestM4oSerialization:
    def _round_trip(self, files: list[FileEntry]) -> list[FileEntry]:
        m = _valid_m4o_manifest(files)
        text = serialize_manifest(m)
        restored, errors = deserialize_manifest(text)
        assert errors == [], f"Unexpected validation errors: {errors}"
        return restored.files

    def test_node_round_trip(self):
        entry = _m4o_entry(
            "CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json",
            "m4o_node_json", id_t3="OBJ_T3_A", id_node="NODE_X",
        )
        restored = self._round_trip([entry])[0]
        assert restored.classification == "m4o_node_json"
        assert restored.m4o_structure is not None
        assert restored.m4o_structure.id_t3 == "OBJ_T3_A"
        assert restored.m4o_structure.id_node == "NODE_X"

    def test_alias_round_trip(self):
        entry = _m4o_entry(
            "CP/META4OBJECT/OBJ_T3_A/M4O ALIAS RESOLUTION/NODE_X/node_x.json",
            "m4o_alias_json", id_t3="OBJ_T3_A", id_node="NODE_X",
        )
        restored = self._round_trip([entry])[0]
        assert restored.classification == "m4o_alias_json"
        assert restored.m4o_structure is not None
        assert restored.m4o_structure.id_node == "NODE_X"

    def test_mapping_round_trip(self):
        entry = _m4o_entry(
            "CP/META4OBJECT/OBJ_T3_A/MAPPING META4OBJECT/OBJ_T3_A/obj_t3_a.json",
            "m4o_mapping_json", id_t3="OBJ_T3_A", id_node=None,
        )
        restored = self._round_trip([entry])[0]
        assert restored.classification == "m4o_mapping_json"
        assert restored.m4o_structure is not None
        assert restored.m4o_structure.id_t3 == "OBJ_T3_A"
        assert restored.m4o_structure.id_node is None

    def test_null_m4o_structure_preserved(self):
        files = [FileEntry(
            path="CP/some.json", sha256="b" * 64, size_bytes=2,
            extension=".json", source_root="CP", classification="other_supported",
        )]
        m = CorpusManifest(
            schema_version="1.1", corpus_id="x", created_at="2026-06-24T00:00:00Z",
            root=RootInfo(label="x"), git=GitInfo(commit=None, dirty=None),
            included_source_roots=["CP"], files=files, summary=build_summary(files),
        )
        text = serialize_manifest(m)
        data = json.loads(text)
        assert data["files"][0]["m4o_structure"] is None
        restored, _ = deserialize_manifest(text)
        assert restored.files[0].m4o_structure is None

    def test_read_schema_1_0_without_m4o_structure_field(self):
        """Manifests without m4o_structure field (schema 1.0) deserialize with m4o_structure=None."""
        files = [FileEntry(
            path="CP/some.ln4", sha256="c" * 64, size_bytes=5,
            extension=".ln4", source_root="CP", classification="unstructured_ln4",
        )]
        m = CorpusManifest(
            schema_version="1.0", corpus_id="x", created_at="2026-06-24T00:00:00Z",
            root=RootInfo(label="x"), git=GitInfo(commit=None, dirty=None),
            included_source_roots=["CP"], files=files, summary=build_summary(files),
        )
        text = serialize_manifest(m)
        # Strip m4o_structure from the JSON to simulate a real 1.0 manifest.
        data = json.loads(text)
        for f in data["files"]:
            f.pop("m4o_structure", None)
        text_v1 = json.dumps(data)
        restored, errors = deserialize_manifest(text_v1)
        assert errors == []
        assert restored.files[0].m4o_structure is None

    def test_schema_version_written_as_1_1(self):
        text = serialize_manifest(_valid_m4o_manifest())
        data = json.loads(text)
        assert data["schema_version"] == "1.1"

    def test_m4o_structure_present_in_output_json(self):
        text = serialize_manifest(_valid_m4o_manifest())
        data = json.loads(text)
        f = data["files"][0]
        assert "m4o_structure" in f
        assert f["m4o_structure"]["id_t3"] == "OBJ_T3_A"
        assert f["m4o_structure"]["id_node"] == "NODE_X"


# ── Validation ────────────────────────────────────────────────────────────────


class TestM4oValidation:
    def _entry_other(self, path: str = "CP/some.json") -> FileEntry:
        return FileEntry(
            path=path, sha256="a" * 64, size_bytes=2,
            extension=".json", source_root="CP", classification="other_supported",
        )

    def test_valid_node_passes(self):
        m = _valid_m4o_manifest()
        assert validate_manifest(m) == []

    def test_m4o_node_without_m4o_structure(self):
        entry = FileEntry(
            path="CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json",
            sha256="a" * 64, size_bytes=2, extension=".json",
            source_root="CP", classification="m4o_node_json",
            m4o_structure=None,
        )
        m = _valid_m4o_manifest([entry])
        errors = validate_manifest(m)
        assert any(e.code == "missing_m4o_structure" for e in errors)

    def test_other_supported_with_m4o_structure(self):
        entry = FileEntry(
            path="CP/some.json", sha256="a" * 64, size_bytes=2,
            extension=".json", source_root="CP", classification="other_supported",
            m4o_structure=M4oStructure(id_t3="OBJ_T3_A", id_node=None),
        )
        m = _valid_m4o_manifest([entry])
        errors = validate_manifest(m)
        assert any(e.code == "unexpected_m4o_structure" for e in errors)

    def test_node_without_id_node(self):
        entry = FileEntry(
            path="CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json",
            sha256="a" * 64, size_bytes=2, extension=".json",
            source_root="CP", classification="m4o_node_json",
            m4o_structure=M4oStructure(id_t3="OBJ_T3_A", id_node=None),
        )
        m = _valid_m4o_manifest([entry])
        errors = validate_manifest(m)
        assert any(e.code == "missing_id_node_for_m4o_resource" for e in errors)

    def test_alias_without_id_node(self):
        entry = FileEntry(
            path="CP/META4OBJECT/OBJ_T3_A/M4O ALIAS RESOLUTION/NODE_X/node_x.json",
            sha256="a" * 64, size_bytes=2, extension=".json",
            source_root="CP", classification="m4o_alias_json",
            m4o_structure=M4oStructure(id_t3="OBJ_T3_A", id_node=None),
        )
        m = _valid_m4o_manifest([entry])
        errors = validate_manifest(m)
        assert any(e.code == "missing_id_node_for_m4o_resource" for e in errors)

    def test_mapping_with_id_node(self):
        entry = FileEntry(
            path="CP/META4OBJECT/OBJ_T3_A/MAPPING META4OBJECT/OBJ_T3_A/obj_t3_a.json",
            sha256="a" * 64, size_bytes=2, extension=".json",
            source_root="CP", classification="m4o_mapping_json",
            m4o_structure=M4oStructure(id_t3="OBJ_T3_A", id_node="SHOULD_BE_NONE"),
        )
        m = _valid_m4o_manifest([entry])
        errors = validate_manifest(m)
        assert any(e.code == "mapping_m4o_structure_has_id_node" for e in errors)

    def test_empty_id_t3_rejected(self):
        entry = FileEntry(
            path="CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json",
            sha256="a" * 64, size_bytes=2, extension=".json",
            source_root="CP", classification="m4o_node_json",
            m4o_structure=M4oStructure(id_t3="", id_node="NODE_X"),
        )
        m = _valid_m4o_manifest([entry])
        errors = validate_manifest(m)
        assert any(e.code == "empty_m4o_id_t3" for e in errors)

    def test_structured_ln4_with_m4o_structure_rejected(self):
        from peoplenet_process_extractor.corpus.models import Ln4Structure
        entry = FileEntry(
            path="CP/NODE STRUCTURE/OBJ/ITEM/METHOD/M/RULES/M#R1#2020_01_01.ln4",
            sha256="a" * 64, size_bytes=100, extension=".ln4",
            source_root="CP", classification="structured_ln4",
            structure=Ln4Structure(meta4object="OBJ", item_type="METHOD", item_name="M",
                                   rule_id="R1", rule_date="2020_01_01"),
            m4o_structure=M4oStructure(id_t3="OBJ_T3_A", id_node=None),
        )
        m = CorpusManifest(
            schema_version="1.1", corpus_id="test", created_at="2026-06-24T00:00:00Z",
            root=RootInfo(label="x"), git=GitInfo(commit=None, dirty=None),
            included_source_roots=["CP"], files=[entry], summary=build_summary([entry]),
        )
        errors = validate_manifest(m)
        assert any(e.code == "unexpected_m4o_structure" for e in errors)


# ── Comparison ────────────────────────────────────────────────────────────────


class TestM4oComparison:
    def _node_entry(self, id_t3: str, id_node: str, sha256: str = "a" * 64) -> FileEntry:
        return _m4o_entry(
            "CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json",
            "m4o_node_json", id_t3=id_t3, id_node=id_node, sha256=sha256,
        )

    def test_identical_m4o_entries_no_change(self):
        e = self._node_entry("OBJ_T3_A", "NODE_X")
        mod = compare_file_entries(e, e)
        assert mod is None

    def test_id_t3_change_detected(self):
        old = self._node_entry("OBJ_T3_A", "NODE_X")
        new = self._node_entry("OBJ_T3_B", "NODE_X")
        mod = compare_file_entries(old, new)
        assert mod is not None
        assert mod.structure_changed

    def test_id_node_change_detected(self):
        old = self._node_entry("OBJ_T3_A", "NODE_X")
        new = self._node_entry("OBJ_T3_A", "NODE_Y")
        mod = compare_file_entries(old, new)
        assert mod is not None
        assert mod.structure_changed

    def test_classification_change_detected(self):
        old = _m4o_entry(
            "CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json",
            "m4o_node_json", id_t3="OBJ_T3_A", id_node="NODE_X",
        )
        new = FileEntry(
            path="CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json",
            sha256="a" * 64, size_bytes=2, extension=".json",
            source_root="CP", classification="other_supported",
        )
        mod = compare_file_entries(old, new)
        assert mod is not None
        assert mod.classification_changed

    def test_stable_equality(self):
        e = self._node_entry("OBJ_T3_A", "NODE_X")
        # Copy with identical data — no diff
        e2 = _m4o_entry(
            "CP/META4OBJECT/OBJ_T3_A/NODE/NODE_X/node_x.json",
            "m4o_node_json", id_t3="OBJ_T3_A", id_node="NODE_X",
        )
        assert compare_file_entries(e, e2) is None


# ── Service integration ───────────────────────────────────────────────────────


class TestM4oServiceIntegration:
    def _build(self, tmp_path: Path) -> tuple[int, dict]:
        corpus = tmp_path / "corpus"
        shutil.copytree(M4O_FIXTURE, corpus)
        output = tmp_path / "manifest.json"
        code, msgs = create_inventory(
            corpus_root=corpus,
            output_path=output,
            corpus_id="m4o-manifest-corpus",
            now=FIXED_NOW,
        )
        data = json.loads(output.read_text()) if output.exists() else {}
        return code, data

    def test_inventory_succeeds(self, tmp_path):
        code, data = self._build(tmp_path)
        assert code == 0
        assert data.get("schema_version") == "1.1"

    def test_by_classification_includes_m4o_types(self, tmp_path):
        _, data = self._build(tmp_path)
        by_cls = data["summary"]["by_classification"]
        assert "m4o_node_json" in by_cls
        assert "m4o_alias_json" in by_cls
        assert "m4o_mapping_json" in by_cls

    def test_node_files_counted(self, tmp_path):
        _, data = self._build(tmp_path)
        by_cls = data["summary"]["by_classification"]
        # NODE_X in OBJ_T3_A, NODE_Y in OBJ_T3_A, NODE_Z in OBJ_T3_B = 3 nodes
        assert by_cls.get("m4o_node_json", 0) == 3

    def test_alias_files_counted(self, tmp_path):
        _, data = self._build(tmp_path)
        by_cls = data["summary"]["by_classification"]
        assert by_cls.get("m4o_alias_json", 0) == 1

    def test_mapping_files_counted_valid_only(self, tmp_path):
        _, data = self._build(tmp_path)
        by_cls = data["summary"]["by_classification"]
        # Only the OBJ_T3_A mapping is valid; OBJ_T3_B mapping is other_supported
        assert by_cls.get("m4o_mapping_json", 0) == 1

    def test_malformed_mapping_is_other_supported(self, tmp_path):
        _, data = self._build(tmp_path)
        files = {f["path"]: f for f in data["files"]}
        malformed_key = next(
            p for p in files if "OBJ_T3_B" in p and "MAPPING" in p and p.endswith(".json")
        )
        assert files[malformed_key]["classification"] == "other_supported"
        assert files[malformed_key]["m4o_structure"] is None

    def test_unknown_resource_no_warning(self, tmp_path):
        _, data = self._build(tmp_path)
        files = {f["path"]: f for f in data["files"]}
        other_key = next(p for p in files if "OTHER_RESOURCE" in p)
        assert files[other_key]["classification"] == "other_supported"
        assert files[other_key]["warnings"] == []

    def test_valid_mapping_has_null_id_node(self, tmp_path):
        _, data = self._build(tmp_path)
        files = {f["path"]: f for f in data["files"]}
        mapping_key = next(
            p for p in files
            if "MAPPING META4OBJECT/OBJ_T3_A" in p and p.endswith(".json")
        )
        assert files[mapping_key]["classification"] == "m4o_mapping_json"
        m4o = files[mapping_key]["m4o_structure"]
        assert m4o is not None
        assert m4o["id_t3"] == "OBJ_T3_A"
        assert m4o["id_node"] is None

    def test_deterministic_output(self, tmp_path):
        corpus = tmp_path / "corpus"
        shutil.copytree(M4O_FIXTURE, corpus)
        out1 = tmp_path / "m1.json"
        out2 = tmp_path / "m2.json"
        create_inventory(corpus_root=corpus, output_path=out1,
                         corpus_id="m4o-manifest-corpus", now=FIXED_NOW)
        create_inventory(corpus_root=corpus, output_path=out2, force=True,
                         corpus_id="m4o-manifest-corpus", now=FIXED_NOW)
        assert out1.read_text() == out2.read_text()


# ── Golden ────────────────────────────────────────────────────────────────────


class TestM4oGolden:
    def test_golden_file_exists(self):
        assert GOLDEN_PATH.exists(), f"Golden file not found: {GOLDEN_PATH}"

    def test_golden_matches_fixture(self, tmp_path):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        corpus = tmp_path / "corpus"
        shutil.copytree(M4O_FIXTURE, corpus)
        output = tmp_path / "manifest.json"
        code, msgs = create_inventory(
            corpus_root=corpus,
            output_path=output,
            corpus_id="m4o-manifest-corpus",
            now=FIXED_NOW,
        )
        assert code == 0, f"create_inventory failed: {msgs}"
        actual = json.loads(output.read_text(encoding="utf-8"))
        assert actual == golden, (
            "M4O corpus manifest does not match golden. "
            "If fixture changed, regenerate with: "
            "uv run python scripts/generate_m4o_golden.py"
        )

    def test_golden_not_overwritten_by_test(self, tmp_path):
        assert GOLDEN_PATH.exists(), "Golden must already exist"
        mtime_before = GOLDEN_PATH.stat().st_mtime
        # Run a full build into tmp, not into the golden path
        corpus = tmp_path / "corpus"
        shutil.copytree(M4O_FIXTURE, corpus)
        output = tmp_path / "manifest.json"
        create_inventory(corpus_root=corpus, output_path=output,
                         corpus_id="m4o-manifest-corpus", now=FIXED_NOW)
        mtime_after = GOLDEN_PATH.stat().st_mtime
        assert mtime_before == mtime_after, "Test must not overwrite the golden file"

    def test_golden_schema_version_1_1(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        assert golden["schema_version"] == "1.1"

    def test_golden_has_m4o_node(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        m4o_nodes = [f for f in golden["files"] if f["classification"] == "m4o_node_json"]
        assert len(m4o_nodes) >= 1

    def test_golden_files_sorted(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        paths = [f["path"] for f in golden["files"]]
        assert paths == sorted(paths)

    def test_golden_no_absolute_paths(self):
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        for f in golden["files"]:
            assert not f["path"].startswith("/")
            assert not (len(f["path"]) >= 2 and f["path"][1] == ":")
