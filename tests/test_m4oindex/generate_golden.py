"""
Script to regenerate the golden file for m4object-node-index-v1.

Run from the repo root:
    python tests/test_m4oindex/generate_golden.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

# Allow running from repo root: add src and this package's directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from conftest import FIXED_GENERATOR_VERSION, FIXED_NOW, load_manifest_ref  # type: ignore[import-not-found]
from peoplenet_process_extractor.corpus.serialization import deserialize_manifest
from peoplenet_process_extractor.corpus.service import create_inventory
from peoplenet_process_extractor.m4oindex.extraction import build_m4o_node_index
from peoplenet_process_extractor.m4oindex.serialization import serialize_index
from peoplenet_process_extractor.m4oindex.validation import validate_index_model

FIXTURE_CORPUS = Path(__file__).parent.parent / "fixtures" / "m4o_node_index_corpus"
GOLDEN_PATH = Path(__file__).parent.parent / "golden" / "m4object-node-index-v1.json"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        corpus = tmp_path / "corpus"
        shutil.copytree(FIXTURE_CORPUS, corpus)
        manifest_path = tmp_path / "manifest.json"
        code, msgs = create_inventory(
            corpus_root=corpus,
            output_path=manifest_path,
            corpus_id="node-index-corpus",
            now=FIXED_NOW,
        )
        if code != 0:
            print(f"ERROR: create_inventory failed: {msgs}")
            sys.exit(1)

        ref = load_manifest_ref(manifest_path)
        manifest, _ = deserialize_manifest(manifest_path.read_text(encoding="utf-8"))
        index = build_m4o_node_index(
            corpus_root=corpus,
            manifest=manifest,
            manifest_ref=ref,
            now=FIXED_NOW,
            generator_version=FIXED_GENERATOR_VERSION,
        )

        errors = validate_index_model(index)
        if errors:
            print("ERROR: model validation failed:\n" + "\n".join(errors))
            sys.exit(1)

        text = serialize_index(index)
        GOLDEN_PATH.write_bytes(text.encode("utf-8"))
        print(f"Golden written to {GOLDEN_PATH}")
        s = index.summary
        print(f"  {s.selected_file_count} files, {s.node_binding_count} node bindings, "
              f"{s.alias_binding_count} alias bindings, {s.inheritance_edge_count} inheritance edges")
        print(f"  {s.diagnostic_count} diagnostics")


if __name__ == "__main__":
    main()
