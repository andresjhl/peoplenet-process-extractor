# m4object-node-index-v1

## Purpose

`m4object-node-index-v1` is a versioned, deterministic extraction of structural bindings
from the `META4OBJECT/` hierarchy of a PeopleNet corpus.

It consumes entries classified as `m4o_node_json`, `m4o_alias_json`, and `m4o_mapping_json`
from a validated `corpus-manifest-v1` and records:

- **Node bindings** — mapping of `ID_NODE` to `ID_TI` within a Meta4Object (`M4RCH_NODES`).
- **Alias bindings** — alias-to-node mappings (`M4RCH_T3_ALIAS_RES`).
- **Inheritance edges** — direct base/derived object relationships (`SPR_DIN_OBJECTS`).
- **Evidence** — per-row traceability to the exact resource, table, and row.
- **Diagnostics** — structured diagnostics with codes and severities.
- **Summary** — aggregated counters.
- **Manifest reference** — SHA-256 and size of the source manifest.

Related documents:
- [corpus-manifest-v1 schema](corpus-manifest-v1.md)
- [PeopleNet structural model](../domain/peoplenet-structural-model.md)
- [ADR-0007 — Keep Meta4Object node index separate](../decisions/ADR-0007-m4object-node-index-separate.md)
- [INC-0007 — m4object-node-index-v1 increment](../increments/INC-0007-m4object-node-index-v1.md)

---

## Constants

```python
FORMAT = "m4object-node-index-v1"
SCHEMA_VERSION = 1
GENERATOR_NAME = "peoplenet-process-extractor"
```

---

## Top-level structure

```json
{
  "format": "m4object-node-index-v1",
  "schema_version": 1,
  "generator": { "name": "...", "version": "..." },
  "created_at": "2026-06-24T12:00:00+00:00",
  "source_manifest": {
    "corpus_id": "...",
    "corpus_schema_version": "1.1",
    "sha256": "64-char hex",
    "size_bytes": 12345
  },
  "node_bindings": [...],
  "alias_bindings": [...],
  "inheritance_edges": [...],
  "diagnostics": [...],
  "summary": { ... }
}
```

### `format`

Always `"m4object-node-index-v1"`. Required.

### `schema_version`

Always `1` (integer). Required.

### `generator`

| Field     | Description                         |
|-----------|-------------------------------------|
| `name`    | Always `"peoplenet-process-extractor"`. |
| `version` | Package version string at build time. |

### `created_at`

UTC ISO-8601 timestamp. Accepts `+00:00` or `Z`. Injected via `--created-at` for
reproducibility. Naive or non-UTC timestamps are rejected.

### `source_manifest`

Reference to the `corpus-manifest-v1` file used as input:

| Field                   | Description                                          |
|-------------------------|------------------------------------------------------|
| `corpus_id`             | From `corpus-manifest-v1.corpus_id`.                 |
| `corpus_schema_version` | From `corpus-manifest-v1.schema_version`.            |
| `sha256`                | SHA-256 of the manifest file bytes (64 hex chars).   |
| `size_bytes`            | Size in bytes of the manifest file (non-negative).   |

The hash is computed from the physical file bytes before loading, and stored for
drift detection in `verify`.

---

## Evidence

Every binding and edge carries an evidence record that traces it to its exact source.

```json
{
  "path": "CP/META4OBJECT/T3A/NODE/N1/nodes.json",
  "sha256": "64-char hex",
  "classification": "m4o_node_json",
  "table": "M4RCH_NODES",
  "row_index": 0
}
```

| Field            | Description                                                       |
|------------------|-------------------------------------------------------------------|
| `path`           | Relative path of the `FileEntry` in the manifest.                 |
| `sha256`         | SHA-256 of the resource, verified before reading.                 |
| `classification` | M4O classification from the manifest.                             |
| `table`          | Source JSON table name.                                           |
| `row_index`      | 0-based index into the table array.                               |

---

## Node bindings

Source: `classification = m4o_node_json`, table `M4RCH_NODES`.

```json
{
  "owner_id_t3": "OBJ_ALPHA",
  "path_id_node": "NODE_SEC",
  "content_id_t3": "OBJ_ALPHA",
  "content_id_node": "NODE_SEC",
  "id_ti": "NODE_SEC",
  "is_root": false,
  "evidence": { ... }
}
```

| Field             | Source                                     | Description                                         |
|-------------------|--------------------------------------------|-----------------------------------------------------|
| `owner_id_t3`     | Path: `META4OBJECT/<ID_T3>/...`            | Meta4Object identifier from filesystem path.         |
| `path_id_node`    | Path: `.../NODE/<ID_NODE>/...`             | Node identifier from filesystem path.                |
| `content_id_t3`   | `M4RCH_NODES[].ID_T3`                     | Meta4Object identifier from JSON content.            |
| `content_id_node` | `M4RCH_NODES[].ID_NODE`                   | Node identifier from JSON content.                   |
| `id_ti`           | `M4RCH_NODES[].ID_TI`                     | Node structure identifier (links to `NODE STRUCTURE/`). |
| `is_root`         | `M4RCH_NODES[].IS_ROOT` (normalized)      | `true`, `false`, or `null` if not normalizable.     |

**Critical distinction:** `content_id_node` and `id_ti` are **separate concepts**. When `ID_NODE == ID_TI` the node's logical identity coincides with its structure name, but this is not guaranteed. Root nodes with `ID_NODE != ID_TI` have been observed.

**Consistency diagnostics:**
- `owner_id_t3 != content_id_t3` → `id_t3_mismatch` (warning)
- `path_id_node != content_id_node` → `id_node_mismatch` (warning)

---

## Alias bindings

Source: `classification = m4o_alias_json`, table `M4RCH_T3_ALIAS_RES`.

```json
{
  "owner_id_t3": "OBJ_ALPHA",
  "path_node_reference": "NODE_SEC",
  "alias": "ALIAS_X",
  "id_node": "NODE_SEC",
  "id_ti": "NODE_SEC",
  "id_alias_t3": "OBJ_ALPHA",
  "evidence": { ... }
}
```

| Field                | Source                                        | Description                                   |
|----------------------|-----------------------------------------------|-----------------------------------------------|
| `owner_id_t3`        | Path: `META4OBJECT/<ID_T3>/...`               | Meta4Object identifier from path.             |
| `path_node_reference`| Path: `.../M4O ALIAS RESOLUTION/<component>/` | Path component; semantics not fully confirmed. |
| `alias`              | `M4RCH_T3_ALIAS_RES[].ALIAS`                 | Alias label used in calls or references.      |
| `id_node`            | `M4RCH_T3_ALIAS_RES[].ID_NODE`               | Resolved logical node identifier.             |
| `id_ti`              | `M4RCH_T3_ALIAS_RES[].ID_TI`                 | Resolved node structure identifier.           |
| `id_alias_t3`        | `M4RCH_T3_ALIAS_RES[].ID_ALIAS_T3`           | Meta4Object owning the aliased node.          |

**Ambiguity note:** The exact semantic of `path_node_reference` (the path component under
`M4O ALIAS RESOLUTION/`) is not yet fully confirmed. The field name is intentionally neutral.

**Consistency diagnostic:**
- `path_node_reference != id_node` → `path_node_reference_mismatch` (warning)

---

## Inheritance edges

Source: `classification = m4o_mapping_json`, table `SPR_DIN_OBJECTS`.

```json
{
  "owner_id_t3": "OBJ_ALPHA",
  "base_id_t3": "OBJ_BASE",
  "derived_id_t3": "OBJ_ALPHA",
  "evidence": { ... }
}
```

| Field           | Source                           | Description                                            |
|-----------------|----------------------------------|--------------------------------------------------------|
| `owner_id_t3`   | Path: `META4OBJECT/<ID_T3>/...`  | Meta4Object identifier from path (the MAPPING owner).  |
| `base_id_t3`    | `SPR_DIN_OBJECTS[].ID_T3`        | Base Meta4Object.                                      |
| `derived_id_t3` | `SPR_DIN_OBJECTS[].ID_T3_I`      | Derived/owner Meta4Object.                             |

**Epistemology:** The interpretation that `ID_T3` is base and `ID_T3_I` is derived is
**observed** (coherence: `owner_id_t3 == derived_id_t3` in all examined files) and
**derived** (the semantic: derived inherits from base). Universal confirmation is **unresolved**.

**Consistency diagnostic:**
- `owner_id_t3 != derived_id_t3` → `owner_derived_mismatch` (warning)

---

## IS_ROOT normalization

`IS_ROOT` accepts the following representations:

| Input | Normalized |
|-------|-----------|
| `true` (bool) | `true` |
| `false` (bool) | `false` |
| `1` (int) | `true` |
| `0` (int) | `false` |
| `"1"` (string) | `true` |
| `"0"` (string) | `false` |
| anything else | `null` + `invalid_is_root` warning |

`bool` is checked before `int` because `bool` is a subclass of `int` in Python.

---

## Diagnostics

Each diagnostic describes a structural or consistency issue:

```json
{
  "code": "id_t3_mismatch",
  "severity": "warning",
  "path": "CP/META4OBJECT/OBJ_ALPHA/NODE/NODE_SEC/nodes.json",
  "table": "M4RCH_NODES",
  "row_index": 0,
  "message": "Row 0: path owner_id_t3='OBJ_ALPHA' differs from content ID_T3='OTHER'."
}
```

### Severity table

| Code | Severity |
|------|----------|
| `resource_read_error` | error |
| `resource_hash_mismatch` | error |
| `resource_path_escape` | error |
| `invalid_encoding` | error |
| `invalid_json` | error |
| `invalid_document_type` | error |
| `missing_table` | warning |
| `invalid_table_type` | error |
| `invalid_row_type` | error |
| `missing_required_field` | error |
| `empty_required_field` | error |
| `invalid_field_type` | error |
| `invalid_is_root` | warning |
| `id_t3_mismatch` | warning |
| `id_node_mismatch` | warning |
| `path_node_reference_mismatch` | warning |
| `owner_derived_mismatch` | warning |
| `duplicate_node_binding` | warning |
| `duplicate_alias_binding` | warning |
| `duplicate_inheritance_edge` | warning |
| `conflicting_node_binding` | error |
| `conflicting_alias_binding` | error |

### `DIAGNOSTIC_LEVELS` (not serialized)

Each code maps to exactly one structural level. This mapping is a property of the code
catalog and is **never serialized** in the index file.

| Level | Codes |
|-------|-------|
| `resource` | `resource_read_error`, `resource_hash_mismatch`, `resource_path_escape`, `invalid_encoding` |
| `document` | `invalid_json`, `invalid_document_type` |
| `table` | `missing_table`, `invalid_table_type` |
| `row` | `invalid_row_type`, `missing_required_field`, `empty_required_field`, `invalid_field_type`, `invalid_is_root` |
| `consistency` | `id_t3_mismatch`, `id_node_mismatch`, `path_node_reference_mismatch`, `owner_derived_mismatch`, `conflicting_node_binding`, `conflicting_alias_binding` |
| `duplicate` | `duplicate_node_binding`, `duplicate_alias_binding`, `duplicate_inheritance_edge` |

### Diagnostic scope

- Resource/document level failures prevent extraction from that file.
- Table/row/consistency/duplicate diagnostics do not abort the index build.
- An `error` severity diagnostic does not abort the build; it is always recorded.

---

## Duplicate and conflict detection

When multiple bindings share the same logical key, the deterministic algorithm:

1. Sorts all bindings by `(evidence.path, evidence.row_index)`.
2. Uses the first binding in each group as the reference.
3. For each additional binding in the group:
   - If content matches the reference → `duplicate_*` (warning).
   - If content differs → `conflicting_*` (error).
4. Emits exactly one diagnostic per additional binding.

**Keys:**
- `NodeBinding`: `(owner_id_t3, content_id_node)`
- `AliasBinding`: `(owner_id_t3, alias)`
- `InheritanceEdge`: `(base_id_t3, derived_id_t3)`

All bindings are preserved regardless of duplicate/conflict status.

---

## Summary

```json
{
  "selected_file_count": 5,
  "successfully_parsed_file_count": 5,
  "failed_file_count": 0,
  "node_binding_count": 4,
  "alias_binding_count": 1,
  "inheritance_edge_count": 1,
  "diagnostic_count": 2
}
```

**Invariant:** `successfully_parsed_file_count + failed_file_count == selected_file_count`

`successfully_parsed_file_count` counts files that were read, decoded, parsed as JSON,
and had a dict root. A file that passed these stages but had table or row errors still
counts as successfully parsed.

---

## Canonical order

| List | Sort key |
|------|----------|
| `node_bindings` | `(owner_id_t3, content_id_node, evidence.path, evidence.row_index)` |
| `alias_bindings` | `(owner_id_t3, alias, evidence.path, evidence.row_index)` |
| `inheritance_edges` | `(base_id_t3, derived_id_t3, evidence.path, evidence.row_index)` |
| `diagnostics` | `(path, table or "", row_index or -1, code)` |

---

## Serialization

- JSON UTF-8, 2-space indent, trailing newline.
- No BOM in output.
- `null` fields serialized as `null` (never omitted).
- Empty lists serialize as `[]`.
- `is_root`: `true`, `false`, or `null`.
- Key order follows dataclass field order (deterministic).

### Source file encoding

Source M4O JSON files are decoded as **UTF-8 with optional BOM** (`utf-8-sig`).
Files that are not valid UTF-8 produce `invalid_encoding` diagnostics.

---

## Publication

The artifact is written **atomically** using `mkstemp` + `replace` in the output directory.
The build aborts (without writing) if:
- The manifest is invalid.
- The model fails validation.
- The round-trip check fails.
- The output exists and `--force` is not set.

---

## Verify

Verification is performed in **two phases**:

### Phase 1 — Manifest identity

1. Read and deserialize the stored index.
2. Check its canonical form (`serialize(deserialize(stored)) == stored`).
3. Compute current hash and size of the manifest file.
4. Compare against `source_manifest.sha256` and `source_manifest.size_bytes`.
5. If they differ → exit 1 (manifest drift; no reconstruction attempted).

### Phase 2 — Exact reconstruction

1. Load and validate the manifest.
2. Reconstruct using stored `created_at` and `generator.version`.
3. Serialize the rebuilt index.
4. Compare byte-by-byte against the stored text.

The comparison is exact: hashes, timestamps, diagnostics, evidence, and all bindings
are included. No fields are neutralized or excluded.

---

## Epistemology of inheritance

The mapping `ID_T3` (base) → `ID_T3_I` (derived/owner) in `SPR_DIN_OBJECTS` is:

- **Observed:** The outer path `OWNER_ID_T3` consistently equals `ID_T3_I`.
- **Derived:** `ID_T3` is inferred to be the base Meta4Object because the file lives
  under the derived object's `MAPPING META4OBJECT/` directory.
- **Unresolved:** Whether this semantic holds universally across all corpus entries.

The index records the raw field values; resolution semantics are left to downstream consumers.

---

## Ambiguity of `path_node_reference`

The path component extracted from `M4O ALIAS RESOLUTION/<component>/` is stored as
`path_node_reference`. Its exact semantic (whether it is always `ID_NODE`, an alias label,
or something else) is **not yet fully confirmed**. The field name is intentionally neutral.
When `path_node_reference != id_node`, a `path_node_reference_mismatch` warning is emitted
and both values are preserved.

---

## Out of scope

The following are explicitly excluded from `m4object-node-index-v1`:

- Resolution of `Call()` or `ChannelCall()` expressions.
- Effective alias resolution (chained aliases).
- Transitive inheritance (base of a base).
- Precedence rules between own nodes, inherited nodes, and aliases.
- Querying `ID_TI` against `structural-index-v1`.
- Active rule selection when multiple rules exist for the same element.
- JSON general root of the T3.
- Other tables beyond `M4RCH_NODES`, `M4RCH_T3_ALIAS_RES`, `SPR_DIN_OBJECTS`.
- Markdown, Groovy, LLM processing.
- Automatic integration with `run-manifest-v1`.
- A `compare` command.
