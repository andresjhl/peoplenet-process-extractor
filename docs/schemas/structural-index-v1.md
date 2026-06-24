# Schema: structural-index-v1

## Purpose

A versioned SQLite database that persists the structural information already present in a `corpus-manifest-v1` in a queryable form. It does not analyse file content or derive new information — all structural data comes directly from the manifest.

---

## Identity

| Field | Value |
|---|---|
| `index_format` | `structural-index-v1` |
| `schema_version` | `1` |

---

## Tables

### `index_metadata` (one row)

Stores build provenance and aggregate counters.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK, CHECK(id=1) | Always 1; enforces single-row constraint |
| `index_format` | TEXT | NOT NULL | `structural-index-v1` |
| `schema_version` | INTEGER | NOT NULL, CHECK(≥1) | `1` |
| `generator_name` | TEXT | NOT NULL | `peoplenet-process-extractor` |
| `generator_version` | TEXT | NOT NULL | Package version at build time |
| `corpus_id` | TEXT | NOT NULL | From the manifest |
| `corpus_manifest_sha256` | TEXT | NOT NULL, CHECK(len=64) | SHA-256 of the manifest file bytes |
| `corpus_manifest_size_bytes` | INTEGER | NOT NULL, CHECK(≥0) | Size of the manifest file |
| `corpus_created_at` | TEXT | NOT NULL | ISO 8601 timestamp from the manifest |
| `index_created_at` | TEXT | NOT NULL | ISO 8601 UTC timestamp of this build |
| `corpus_git_commit` | TEXT | nullable | Git commit of the corpus at inventory time |
| `corpus_git_dirty` | INTEGER | nullable | 1 if dirty, 0 if clean, NULL if unknown |
| `total_files` | INTEGER | NOT NULL, CHECK(≥0) | Count of all `source_files` rows |
| `structured_files` | INTEGER | NOT NULL, CHECK(≥0) | Count of `structured_ln4` rows |
| `unstructured_files` | INTEGER | NOT NULL, CHECK(≥0) | Count of `unstructured_ln4` rows |
| `build_status` | TEXT | NOT NULL, CHECK IN ('complete','failed') | Always `complete` in a published index |

### `source_files` (one row per manifest entry)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Assigned in ascending path sort order (1..N) |
| `path` | TEXT | NOT NULL, UNIQUE | Corpus-relative path with `/` separators |
| `sha256` | TEXT | NOT NULL, CHECK(len=64) | SHA-256 hex from the manifest |
| `size_bytes` | INTEGER | NOT NULL, CHECK(≥0) | File size from the manifest |
| `extension` | TEXT | NOT NULL | Lowercase extension (e.g. `.ln4`) or empty string |
| `source_root` | TEXT | nullable | First path component; NULL for corpus-root files |
| `classification` | TEXT | NOT NULL | One of: `structured_ln4`, `unstructured_ln4`, `metadata_json`, `other_supported`, `ignored` |
| `warning_count` | INTEGER | NOT NULL DEFAULT 0, CHECK(≥0) | Count of parse warnings for this file |

### `structural_elements` (one row per `structured_ln4` file)

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-assigned |
| `source_file_id` | INTEGER | NOT NULL, UNIQUE, FK→source_files | One element per file maximum |
| `meta4object` | TEXT | NOT NULL | Legacy field name; contains the node structure identifier (ID_TI). |
| `item_type` | TEXT | NOT NULL | e.g. `METHOD`, `CONCEPT`, `VALIDATION` |
| `item_name` | TEXT | NOT NULL | Name of the item |
| `rule_id` | TEXT | nullable | e.g. `R1` |
| `rule_date` | TEXT | nullable | e.g. `2020_01_01` |

### `file_warnings` (zero or more rows per file)

Stores per-file parse warnings from the manifest. Empty for most files.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PK | Auto-assigned |
| `source_file_id` | INTEGER | NOT NULL, FK→source_files | The file that generated this warning |
| `sequence` | INTEGER | NOT NULL, CHECK(≥0) | 0-based order within the file's warnings |
| `message` | TEXT | NOT NULL | Warning text |
| — | — | UNIQUE(source_file_id, sequence) | No duplicate positions |

---

## Indexes

| Name | Table | Columns | Purpose |
|---|---|---|---|
| `idx_source_files_classification` | `source_files` | `classification` | Filter by file type |
| `idx_source_files_source_root` | `source_files` | `source_root` | Filter by source root |
| `idx_structural_elements_meta4object` | `structural_elements` | `meta4object` | Filter by node structure identifier (ID_TI) |
| `idx_structural_elements_item_type` | `structural_elements` | `item_type` | Filter by item type |
| `idx_structural_elements_item_name` | `structural_elements` | `item_name` | Filter by item name |
| `idx_structural_elements_combined` | `structural_elements` | `(meta4object, item_type, item_name)` | Combined node structure+type+name queries |
| `idx_file_warnings_source_file_id` | `file_warnings` | `source_file_id` | Fast lookup of warnings per file |

---

## Constraints

- Foreign keys are enforced at the application level by issuing `PRAGMA foreign_keys = ON` on every connection. They are not stored in the database file.
- Every `structured_ln4` file must have exactly one row in `structural_elements`. No other file may have a structural element.
- `build_status` must be `complete` in any published index.
- Counter fields in `index_metadata` must match the actual row counts in `source_files`.

---

## Identity

`corpus_manifest_sha256` and `corpus_manifest_size_bytes` allow downstream consumers to detect that a different manifest file was substituted, even if it has the same `corpus_id`. The combination is checked by `index verify`.

---

## Exact-scope

The index represents exactly the files declared in `included_source_roots` of the manifest at build time:

- `included_source_roots = ["CP"]` → only CP files are indexed.
- `included_source_roots = []` → only corpus-root-level files are indexed.
- `included_source_roots = ["CP", "GTO"]` → only CP and GTO files are indexed.

No re-discovery is performed at build time. The builder does not traverse the corpus beyond what is needed for the mandatory pre-build verification.

---

## Reproducibility

Given the same manifest, the same corpus, and a fixed build timestamp, the logical content of the index (tables and rows) is identical across independent builds. Row IDs in `source_files` are assigned in ascending path order (1..N), making them deterministic.

The physical SQLite file (byte-for-byte) may differ because SQLite may embed internal metadata that varies. Use `logical_export()` for reproducibility comparisons.

---

## Queries available

| Command | Description |
|---|---|
| `index query files` | Filter source files by path, classification, source root, extension |
| `index query elements` | Filter structural elements by meta4object, item_type, item_name, rule_id, source_root |
| `index query stats` | Aggregated counts by classification, source root, item type |

All queries use parameterised SQL. No free-form SQL is exposed.

### Stats: source root representation

Files at the corpus root level (no first-level subdirectory) have `source_root = NULL` in the database. The stats output represents them as follows:

| Output mode | Value |
|---|---|
| `--json` | `""` (empty string) |
| text (default) | `(corpus root)` |

This convention is consistent with SQLite's `COALESCE(source_root, '')` in the stats query and the display label substituted in the CLI text renderer.

---

## Anonimised example

```
source_files:
  id=1  path="CP/NODE STRUCTURE/OBJ_A/ITEM/METHOD/METH_X/RULES/METH_X#R1#2020_01_01.ln4"
        classification=structured_ln4  source_root=CP
  id=2  path="GTO/loose.ln4"  classification=unstructured_ln4  source_root=GTO
  id=3  path="metadata.json"  classification=metadata_json     source_root=null

structural_elements:
  source_file_id=1  meta4object=OBJ_A  item_type=METHOD  item_name=METH_X
                    rule_id=R1  rule_date=2020_01_01
```

---

## Known semantic naming debt

The column `structural_elements.meta4object` was named after the legacy prototype convention.
Its actual content is the identifier extracted from the third path component of:

```
<source_root>/NODE STRUCTURE/<ID_TI>/ITEM/<item_type>/<item_name>/RULES/<rule>.ln4
```

**Status: observed** (in the path parser and corpus inventory implementation).

That identifier is `ID_TI` — the *node structure identifier* — not the Meta4Object name
(`ID_T3`). The two are distinct concepts in the PeopleNet domain. See
[peoplenet-structural-model.md](../domain/peoplenet-structural-model.md#critical-distinction-id_node-vs-id_ti).

The field is **not renamed in this schema version** for the following reasons:

- `structural-index-v1` is a versioned contract consumed by `reference-extraction-v1` and
  other downstream phases. A field rename is a breaking change.
- The renaming must be coordinated with all consumers and treated as a schema version bump.

**Consumers of `structural_elements.meta4object` must interpret its value as `ID_TI`**
(node structure identifier), not as `ID_T3` (Meta4Object name). In particular, a `Call()`
argument must never be compared directly against this column — the argument references
`ID_NODE`, which requires a separate lookup step to reach `ID_TI`.

A future schema version may rename this column to `node_structure_id` or equivalent.

---

## Out of scope

- Parsing LN4 content.
- Extracting `Call()` references.
- Full-text search.
- Incremental updates.
- Multiple corpora per database.
- ORM or REST API.
