# Corpus Lifecycle

This document describes the stages from a physical corpus directory to a future analysis artifact.

---

## Stages

```
corpus físico
  │
  ▼
[corpus inventory]          ← IMPLEMENTED (Increment 3)
  │
  ▼
corpus-manifest-v1.json     ← IMPLEMENTED (Increment 3)
  │
  ▼
[corpus verify]             ← IMPLEMENTED (Increment 3)
  │
  ▼
run-manifest-v1.json        ← IMPLEMENTED (Increment 2)
  │
  ▼
[futuro: indexación SQLite] ← NOT IMPLEMENTED
  │
  ▼
[futuro: descubrimiento]    ← NOT IMPLEMENTED
  │
  ▼
[futuro: análisis LN4]      ← NOT IMPLEMENTED
```

---

## Stage 1 — Physical corpus

The corpus lives in an external directory configured by `PEOPLENET_CORPUS_ROOT`.

- Not copied into this repository.
- Not modified by any pipeline step.
- May optionally be a Git repository.

---

## Stage 2 — `corpus inventory` (IMPLEMENTED)

```bash
uv run peoplenet-process-extractor corpus inventory \
  --corpus-root $env:PEOPLENET_CORPUS_ROOT \
  --output corpus-manifest.json
```

Actions:
1. Validates the corpus root (not a symlink, is a directory).
2. Determines which source roots to include (all by default, or filtered by `--source-root`).
3. Walks the filesystem without following symlinks.
4. Classifies each file.
5. Computes SHA-256 and size for each file.
6. Parses PeopleNet path structure where applicable.
7. Reads optional Git metadata.
8. Builds deterministic summary.
9. Validates the manifest.
10. Writes atomically to the output path.

---

## Stage 3 — `corpus-manifest-v1.json` (IMPLEMENTED)

The manifest is a portable JSON snapshot of the corpus state.

Key invariants:
- No absolute paths.
- Deterministic file order (sorted by path).
- Summary recomputed on load for consistency checking.
- Git info optional, non-blocking.

---

## Stage 4 — `corpus verify` (IMPLEMENTED)

```bash
uv run peoplenet-process-extractor corpus verify \
  --corpus-root $env:PEOPLENET_CORPUS_ROOT \
  corpus-manifest.json
```

Actions:
1. Loads and validates the manifest.
2. Re-inventories the corpus using the scope from `included_source_roots`.
3. Compares: added, removed, modified (hash, size, classification, structure).
4. Returns exit code 0 if identical, non-zero on any difference.

Does not modify the corpus or the manifest.

**Scope:** `corpus verify` checks exactly the scope recorded in `included_source_roots`.
New first-level directories outside that scope are not reported.

---

## Stage 5 — run-manifest-v1 integration (IMPLEMENTED, manual)

A corpus manifest can be registered as a `configuration` source in a run:

```json
{
  "id": "corpus-snapshot",
  "kind": "configuration",
  "path": "inputs/corpus-manifest.json",
  "sha256": "...",
  "size_bytes": 12345,
  "exists": true,
  "required": true
}
```

The `run-manifest-v1` schema does not register individual `.ln4` files.
The corpus manifest acts as the aggregated snapshot.

---

## Stage 6 — Future: SQLite index (NOT IMPLEMENTED)

A future step will consume `corpus-manifest-v1` to build a SQLite index:
- Reads `files` list from manifest.
- Does not re-walk the filesystem independently.
- Can detect corpus drift by comparing against a new manifest.

This step does not exist yet.

---

## Stage 7 — Future: discovery and LN4 analysis (NOT IMPLEMENTED)

Future stages will:
- Parse LN4 content.
- Build a call graph.
- Resolve method dependencies.
- Generate documentation.

These stages are out of scope for Increment 3.

---

## Summary of what is and is not implemented

| Capability                      | Status          |
|---------------------------------|-----------------|
| `corpus inventory` CLI          | Implemented     |
| `corpus verify` CLI             | Implemented     |
| `corpus-manifest-v1` contract   | Implemented     |
| PeopleNet path parsing          | Implemented     |
| SHA-256 hashing                 | Implemented     |
| Git metadata                    | Implemented     |
| Manifest comparison             | Implemented     |
| `run-manifest-v1` integration   | Documented      |
| SQLite index                    | Not implemented |
| LN4 content parsing             | Not implemented |
| Call graph                      | Not implemented |
| Documentation generation        | Not implemented |
