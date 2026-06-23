# Index Lifecycle

This document describes how a `structural-index-v1` is created, verified, and used within the pipeline.

---

## Pipeline position

```
corpus (physical files)
  │
  ▼
corpus inventory          →  corpus-manifest-v1  (JSON)
  │
  ▼
corpus verify             ←  re-checks physical corpus against manifest
  │                          (exit code 0 = unchanged)
  ▼
index build               →  structural-index-v1  (SQLite)
  │                          (pre-build: calls corpus verify internally)
  ▼
index verify              ←  re-checks index against manifest + corpus
  │
  ▼
index query               ←  files / elements / stats
  │
  ▼  (future)
reference extraction
  │
  ▼  (future)
dependency graph
  │
  ▼  (future)
fact extraction
```

---

## Step-by-step lifecycle

### 1. Corpus inventory

```bash
peoplenet-process-extractor corpus inventory \
  --corpus-root /path/to/corpus \
  --output corpus-manifest.json
```

Produces `corpus-manifest-v1`. Stores relative paths, SHA-256 hashes, sizes, classifications, and structural information derived from the PeopleNet path convention.

### 2. (Optional) Corpus verify

```bash
peoplenet-process-extractor corpus verify \
  --corpus-root /path/to/corpus \
  corpus-manifest.json
```

Confirms that the physical corpus has not changed since the manifest was created. **This step is performed automatically inside `index build`.**

### 3. Index build

```bash
peoplenet-process-extractor index build \
  --corpus-root /path/to/corpus \
  --corpus-manifest corpus-manifest.json \
  --output structural-index.sqlite
```

1. Loads and validates `corpus-manifest.json`.
2. Runs exact-scope corpus verification internally.
3. Hashes `corpus-manifest.json` (SHA-256 + size).
4. Writes a new SQLite to a sibling temporary file.
5. Inserts all data in a single transaction (files sorted by path for deterministic IDs).
6. Validates the temporary index.
7. Publishes via `os.replace()` (atomic on POSIX and Windows).
8. Cleans up the temporary file.

**`--force`**: If the output exists, it is replaced only after the new index is fully built and validated. A build failure leaves the previous index intact.

### 4. Index verify

```bash
peoplenet-process-extractor index verify \
  --corpus-root /path/to/corpus \
  --corpus-manifest corpus-manifest.json \
  --database structural-index.sqlite
```

Checks:
1. Manifest is valid (`corpus-manifest-v1`).
2. Corpus matches manifest exactly (exact-scope).
3. SQLite `PRAGMA integrity_check` passes.
4. `PRAGMA foreign_key_check` passes.
5. All expected tables and columns present.
6. `build_status = 'complete'`.
7. `corpus_manifest_sha256` and `corpus_manifest_size_bytes` match the actual manifest file.
8. All manifest entries are indexed; no extra rows.
9. Structural consistency (every `structured_ln4` has an element; no others do).
10. Counters in metadata match actual row counts.

### 5. Index query (current capabilities)

```bash
# List all unstructured LN4 files in root CP
peoplenet-process-extractor index query files \
  --database structural-index.sqlite \
  --source-root CP \
  --classification unstructured_ln4

# Find all METHOD items in object OBJ_A
peoplenet-process-extractor index query elements \
  --database structural-index.sqlite \
  --meta4object OBJ_A \
  --item-type METHOD

# Aggregated statistics
peoplenet-process-extractor index query stats \
  --database structural-index.sqlite
```

---

## Future steps (not yet implemented)

### Reference extraction (future)

Will read `structural_elements` from the index and open `.ln4` files to extract `Call()` references. Will produce a reference table stored either in the same or a companion SQLite database.

### Dependency graph (future)

Will resolve references to create a directed graph of caller → callee relationships. Will depend on the reference extraction output.

### Fact extraction (future)

Will extract semantic facts from the LN4 content (SQL statements, business rules, validations) for specification generation.

---

## Integration with run-manifest-v1

When the full pipeline is automated, a future `run-manifest-v1` will record:

```json
{
  "inputs": {
    "corpus_manifest": {
      "path": "artifacts/corpus-manifest.json",
      "sha256": "...",
      "size_bytes": ...
    }
  },
  "artifacts": {
    "structural_index": {
      "path": "artifacts/structural-index.sqlite",
      "sha256": "...",
      "size_bytes": ...,
      "derived_from": "corpus_manifest"
    }
  }
}
```

`run-manifest-v1` is not modified by Increment 4. The relationship above is planned for a future increment.

---

## Stale index detection

If the corpus or manifest changes after the index is built, `index verify` will detect it:
- **Modified corpus**: `corpus verify` (run inside `index verify`) will report added/removed/modified files.
- **Different manifest file**: The stored `corpus_manifest_sha256` will not match the current manifest, even if the `corpus_id` is the same.

The recommended workflow is to rebuild the index whenever the manifest changes.
