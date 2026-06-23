# corpus-manifest-v1

## Purpose

`corpus-manifest-v1` is a versioned, deterministic inventory of a PeopleNet corpus directory.
It records exactly which files are present, their hashes and sizes, their classification,
and their parsed PeopleNet structure when applicable.

The manifest is the stable contract between:

```
corpus físico
→ corpus-manifest-v1
→ futuro índice SQLite
→ futuro descubrimiento
→ futuro análisis
```

The manifest is generated once per corpus snapshot and can be regenerated later to detect
additions, removals, and modifications.

---

## Schema version

Only version `1.0` is supported.  A different value causes an explicit error on load.

---

## Top-level structure

```json
{
  "schema_version": "1.0",
  "corpus_id": "peoplenet-corpus",
  "created_at": "2026-06-23T14:30:00+00:00",
  "root": {
    "label": "peoplenet_src",
    "path_policy": "relative"
  },
  "git": {
    "commit": "abc123...",
    "dirty": false
  },
  "included_source_roots": ["CP", "GTO"],
  "files": [...],
  "summary": {...},
  "warnings": [],
  "errors": []
}
```

### `corpus_id`

- Required, non-empty.
- Identifies the corpus independently of location.
- Derived from the directory name by default (lower-cased, spaces replaced with hyphens).
- Overridable via `--corpus-id`.
- Not a UUID — it is meant to be human-readable and stable.

### `created_at`

- UTC ISO 8601 timestamp (e.g. `2026-06-23T14:30:00+00:00` or `2026-06-23T14:30:00Z`).
- Only UTC is accepted: `Z` or `+00:00`. Non-zero offsets (`+02:00`, `-05:00`) are rejected.
- Records when the inventory was generated, not the corpus content date.
- Injected in tests to avoid non-determinism.
- Not used as content identity.

### `root`

| Field         | Description                                                |
|---------------|------------------------------------------------------------|
| `label`       | Name of the corpus root directory (not an absolute path).  |
| `path_policy` | Always `"relative"`. All paths are relative to this root.  |

The absolute path of the corpus root is **never stored in the manifest**.

### `git`

| Field    | Description                                                       |
|----------|-------------------------------------------------------------------|
| `commit` | Full SHA-1 commit hash of HEAD, or `null` if unavailable.         |
| `dirty`  | `true` if the working tree has uncommitted changes, `null` if unknown. |

Git information is **optional and non-blocking**.  If `git` is not installed or the corpus
is not inside a repository, both fields are `null` and a warning is added.

Remote URLs, user identity, and credentials are never stored.

### `included_source_roots`

List of first-level subdirectory names that were traversed.  Empty when all files are at the
corpus root or no subdirectory structure exists.  When `--source-root` filters are specified,
only the requested roots appear here.

### `warnings` and `errors`

- `warnings`: non-fatal issues encountered during inventory (e.g. symlinks skipped, git unavailable).
- `errors`: populated by future pipeline phases; typically empty in a fresh inventory.

---

## File entries

Each element of `files` describes one inventoried file:

```json
{
  "path": "GTO/NODE STRUCTURE/GLB_OBJ/ITEM/METHOD/GLB_METHOD/RULES/GLB_METHOD#R1#1800_01_01.ln4",
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "size_bytes": 391,
  "extension": ".ln4",
  "source_root": "GTO",
  "classification": "structured_ln4",
  "structure": {
    "meta4object": "GLB_OBJ",
    "item_type": "METHOD",
    "item_name": "GLB_METHOD",
    "rule_id": "R1",
    "rule_date": "1800_01_01"
  },
  "warnings": []
}
```

### `path`

- Relative to the corpus root.
- Uses `/` separators (portable).
- Preserves original case and spaces.
- Never starts with `/` or a Windows drive letter.
- Never contains `..`.

### `sha256`

SHA-256 hex digest of the file's raw bytes.  Computed incrementally (chunk-by-chunk).
Line endings are **not normalized** — a file with CRLF has a different hash than the same
content with LF.

### `extension`

Lowercase file extension including the leading `.` (e.g. `.ln4`, `.json`).
Files without an extension use an empty string `""`.
The original filename is preserved; only the `extension` field is normalized to lowercase.

### `source_root`

First path component when the file is inside a subdirectory.  `null` for files at the corpus root.
In the summary's `by_source_root`, `null` source roots use the key `""`.

**Coherence rules (validated on load):**
- File with single-component path → `source_root` must be `null`.
- File with multi-component path → `source_root` must equal the first component exactly.
- Non-null `source_root` must appear in `included_source_roots`.

### `classification`

| Value             | Meaning                                                          |
|-------------------|------------------------------------------------------------------|
| `structured_ln4`  | `.ln4` file whose path fully matches the PeopleNet structure.    |
| `unstructured_ln4`| `.ln4` file that does not match the known structure.             |
| `metadata_json`   | File named `metadata.json` at any depth.                         |
| `other_supported` | Any other file included in the inventory (`.json`, `.bin`, etc.) |
| `ignored`         | File included in the manifest but excluded from detailed analysis (e.g. `.pyc`, `.db`). |

The classification is deterministic: the same path always produces the same classification.

### `structure`

Present only for `structured_ln4` files; `null` otherwise.

| Field          | Description                                  |
|----------------|----------------------------------------------|
| `meta4object`  | Third path component after `NODE STRUCTURE`. |
| `item_type`    | Fifth path component (e.g. `METHOD`, `CONCEPT`). |
| `item_name`    | Sixth path component.                        |
| `rule_id`      | Second `#`-separated token in the filename, or `null`. |
| `rule_date`    | Third `#`-separated token in the filename, or `null`. |

When `rule_id` or `rule_date` cannot be extracted (e.g. filename has no `#`), a warning is
added to the file's `warnings` list and those fields are `null`.

---

## PeopleNet recognized structure

A `.ln4` file is classified as `structured_ln4` when its path matches **exactly** 8 components:

```
<source_root>/NODE STRUCTURE/<meta4object>/ITEM/<item_type>/<item_name>/RULES/<rule_file>.ln4
```

- Component labels `NODE STRUCTURE`, `ITEM`, and `RULES` are case-sensitive.
- `<item_type>` is not restricted to `METHOD`; any non-empty value is accepted.
- Path depth must be exactly 8 (no nested directories inside `RULES`).
- A file that satisfies everything except the rule filename format is still `structured_ln4`
  (with `rule_id=null`, `rule_date=null`, and a per-file warning).

---

## Unstructured LN4 files

`.ln4` files that do not match the structured pattern are classified as `unstructured_ln4`.
They are **never discarded**; they appear in `files` with `structure=null`.
This includes files at the corpus root (`source_root=null`) and files inside source roots
that do not follow the `NODE STRUCTURE` hierarchy.

---

## Source roots

Any first-level subdirectory is a candidate source root.  Known roots (`CP`, `GTO`, `OTROS`)
are not hardcoded; the system discovers them by traversal.

When `--source-root` is specified on the CLI, only those roots are inventoried.
A requested root that does not exist causes an error (the declared scope cannot be fulfilled).
Duplicate values are normalized (equivalent to specifying the root once).
The resulting `included_source_roots` list is always sorted alphabetically.

---

## Hashing

SHA-256 is computed over raw bytes, incrementally (64 KB chunks).
No encoding conversion, no line-ending normalization.
Reuses `peoplenet_process_extractor.manifest.hashing.compute_file_hash_and_size`.

---

## Summary

```json
{
  "total_files": 10,
  "total_bytes": 4096,
  "structured_files": 6,
  "unstructured_files": 2,
  "by_source_root": {"": 2, "CP": 4, "GTO": 2, "UNKNOWN_ROOT": 2},
  "by_extension": {".json": 1, ".ln4": 9},
  "by_classification": {
    "metadata_json": 1,
    "other_supported": 1,
    "structured_ln4": 6,
    "unstructured_ln4": 2
  }
}
```

**Counting policy:**

- `total_files` includes ALL classifications, including `ignored`.
- `total_bytes` includes ALL files.
- `structured_files` counts only `structured_ln4`.
- `unstructured_files` counts only `unstructured_ln4`.
- `by_source_root` uses `""` (empty string) as key for files with `source_root=null`.
- Dicts are serialized with sorted keys for determinism.

**Validation:** When loading a manifest, the summary is recomputed from the `files` list and
compared to the stored summary.  A mismatch causes a validation error.
The summary is informational; the `files` list is authoritative.

---

## Ordering

Files are sorted by their `path` field (ascending, lexicographic) before serialization.
The same corpus always produces the same file order regardless of filesystem ordering.
`mtime` is never used for ordering or identity.

---

## Ignored files and directories

**Directories skipped entirely** (not traversed):
`.git`, `.venv`, `__pycache__`, `node_modules`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`

**Files classified as `ignored`** (included in manifest with minimal analysis):
Files with extensions: `.pyc`, `.db`, `.sqlite`, `.sqlite3`, `.db-journal`, `.db-shm`, `.db-wal`, `.log`, `.tmp`

**Symlinks** are not followed.  A symlink item at the file or directory level emits a warning
and is excluded from the inventory.  The manifest never silently follows a symlink out of the
corpus root.

---

## Serialization

- JSON UTF-8, 2-space indent, trailing newline.
- `null` fields are serialized as `null` (never omitted).
- Empty lists serialize as `[]`.
- Round trip is lossless.

---

## Validation rules (summary)

| Rule                     | Code                        |
|--------------------------|-----------------------------|
| Schema version supported | `unsupported_schema_version`|
| `corpus_id` non-empty    | `empty_corpus_id`           |
| `created_at` valid ISO   | `invalid_created_at`        |
| `created_at` has TZ      | `created_at_missing_timezone`|
| `created_at` is UTC      | `created_at_not_utc`        |
| `root.path_policy=relative` | `invalid_path_policy`    |
| No absolute paths        | `absolute_path`             |
| No `..` traversal        | `path_traversal`            |
| Forward slashes only     | `backslash_in_path`         |
| Unique paths             | `duplicate_file_path`       |
| Files sorted             | `files_not_sorted`          |
| Valid SHA-256            | `invalid_sha256`            |
| Non-negative size        | `negative_size`             |
| Valid classification     | `invalid_classification`    |
| structure ↔ classification coherence | `missing_structure`, `unexpected_structure` |
| Extension lowercase      | `extension_not_lowercase`   |
| Extension matches path   | `extension_path_mismatch`   |
| `source_root` matches path | `source_root_mismatch`    |
| `source_root` within scope | `source_root_not_in_scope`|
| Git commit format        | `invalid_git_commit`        |
| Unique source roots      | `duplicate_source_root`     |
| Summary matches files    | `summary_mismatch`          |

---

## `corpus verify` scope

`corpus verify` re-inventories using exactly the source roots recorded in
`included_source_roots`.  It does **not** expand scope to discover new first-level
directories that were not inventoried originally.

| Scenario | Result |
|----------|--------|
| File added inside an inventoried root | Detected as `added` |
| File removed from an inventoried root | Detected as `removed` |
| File modified inside an inventoried root | Detected as `modified` |
| New first-level directory outside `included_source_roots` | **Not detected** |

This is a documented limitation.  To surface new roots, re-run `corpus inventory` without
a `--source-root` filter and compare the resulting manifests.

---

## Integration with run-manifest-v1

A corpus manifest can be registered as a `configuration` source in a `run-manifest-v1`:

```json
{
  "id": "corpus-snapshot-001",
  "kind": "configuration",
  "path": "inputs/corpus-manifest.json",
  "sha256": "...",
  "size_bytes": 12345,
  "exists": true,
  "required": true,
  "description": "Corpus inventory snapshot: commit abc123, dirty=false"
}
```

The run does **not** register each individual `.ln4` file; the corpus manifest acts as the
aggregated snapshot.  The Git commit from the corpus manifest can be included in the description
field for traceability.

Adding a `corpus_manifest` source kind to `run-manifest-v1` is deferred to a future ADR.
