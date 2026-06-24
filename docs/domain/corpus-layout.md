# Corpus Layout

This document describes the confirmed path patterns of the PeopleNet corpus and the
identifiers extracted from each segment. It complements the structural model described in
[peoplenet-structural-model.md](peoplenet-structural-model.md).

Related documents:
- [PeopleNet structural model](peoplenet-structural-model.md)
- [LN4 call resolution](ln4-call-resolution.md)
- [corpus-manifest-v1 schema](../schemas/corpus-manifest-v1.md)
- [structural-index-v1 schema](../schemas/structural-index-v1.md)
- [ADR-0006 — Manifest as single source of inventory](../decisions/ADR-0006-manifest-single-source.md)
- [ADR-0007 — Keep Meta4Object node index separate](../decisions/ADR-0007-m4object-node-index-separate.md)

---

## Epistemological classification

Statements in this document are classified using the same scheme as
[peoplenet-structural-model.md](peoplenet-structural-model.md):
**observed**, **derived**, **inferred**, **ambiguous**, **unresolved**.

---

## Node structure hierarchy

**Status: observed**

```
<source_root>/
└── NODE STRUCTURE/
    └── <ID_TI>/
        └── ITEM/
            └── <TYPE>/
                └── <ITEM_NAME>/
                    └── RULES/
                        └── <rule>.ln4
```

### Path segments

| Segment | Identifier extracted | Description |
|---------|---------------------|-------------|
| `<source_root>` | `source_root` | First-level subdirectory (e.g. `CP`, `GTO`). `null` for corpus-root files. |
| `NODE STRUCTURE` | — | Fixed label; case-sensitive. |
| `<ID_TI>` | `ID_TI` (stored as `structural_elements.meta4object`) | Node structure identifier. |
| `ITEM` | — | Fixed label; case-sensitive. |
| `<TYPE>` | `item_type` | Element category (e.g. `METHOD`, `CONCEPT`, `VALIDATION`). Not restricted to a closed list. |
| `<ITEM_NAME>` | `item_name` | Name of the specific element. |
| `RULES` | — | Fixed label; case-sensitive. |
| `<rule>.ln4` | `rule_id`, `rule_date` | Rule filename. Parsed as `<ITEM_NAME>#<rule_id>#<rule_date>.ln4`. |

### Artefact consumers

| Field | Populated by | Stored in |
|-------|-------------|-----------|
| `ID_TI` | `corpus inventory` (path parser) | `corpus-manifest-v1` → `structure.meta4object`; `structural-index-v1` → `structural_elements.meta4object` |
| `item_type` | `corpus inventory` | Same as above |
| `item_name` | `corpus inventory` | Same as above |
| `rule_id`, `rule_date` | `corpus inventory` | Same as above |

### Status

- **Inventoried:** yes — all matching files are classified as `structured_ln4`.
- **Content interpreted:** partially — the path is parsed; the LN4 content is extracted by
  `reference-extraction-v1` (INC-0005) for `Call()` references, but full semantic analysis
  is pending.
- **Artefact consumer:** `structural-index-v1` (current); future `reference-extraction-v1`
  targets (resolved).

---

## Meta4Object node resources

**Status: observed**

```
<source_root>/
└── META4OBJECT/
    └── <ID_T3>/
        └── NODE/
            └── <ID_NODE>/
                └── <file>.json
```

### Path segments

| Segment | Identifier extracted | Description |
|---------|---------------------|-------------|
| `<source_root>` | `source_root` | First-level subdirectory. |
| `META4OBJECT` | — | Fixed label; case-sensitive. |
| `<ID_T3>` | `id_t3` | Meta4Object identifier. |
| `NODE` | — | Fixed label; case-sensitive. |
| `<ID_NODE>` | `id_node` | Logical node identifier within the Meta4Object model. |
| `<file>.json` | — | JSON resource file; filename is not structurally significant beyond extension. |

### Database table: `M4RCH_NODES`

The JSON content of these files corresponds to rows in the internal table `M4RCH_NODES`.

| Column | Corresponds to |
|--------|---------------|
| `ID_T3` | `m4o_structure.id_t3` from manifest |
| `ID_NODE` | `m4o_structure.id_node` from manifest |
| `ID_TI` | Node structure identifier (links to `NODE STRUCTURE/<ID_TI>`) |
| `IS_ROOT` | Whether this is a root node of the Meta4Object model |

**`ID_NODE` and `ID_TI` are distinct** — see [peoplenet-structural-model.md](peoplenet-structural-model.md#critical-distinction-id_node-vs-id_ti).

### Status

- **Inventoried:** yes — files are classified as `m4o_node_json` in `corpus-manifest-v1` (schema 1.1).
- **Content interpreted:** not yet — file content is not read by the current pipeline.
- **Artefact consumer:** future `m4object-node-index-v1` (INC-0007).

---

## Alias resolution resources

**Status: observed**

```
<source_root>/
└── META4OBJECT/
    └── <ID_T3>/
        └── M4O ALIAS RESOLUTION/
            └── <ID_NODE>/
                └── <file>.json
```

### Path segments

| Segment | Identifier extracted | Description |
|---------|---------------------|-------------|
| `<source_root>` | `source_root` | First-level subdirectory. |
| `META4OBJECT` | — | Fixed label; case-sensitive. |
| `<ID_T3>` | `id_t3` | Meta4Object that owns this alias table. |
| `M4O ALIAS RESOLUTION` | — | Fixed label; case-sensitive; includes the space. |
| `<ID_NODE>` | `id_node` | The node identifier associated with this alias table. |
| `<file>.json` | — | JSON resource file. |

### Database table: `M4RCH_T3_ALIAS_RES`

| Column | Meaning |
|--------|---------|
| `ALIAS` | The alias label used as a reference in LN4 code |
| `ID_NODE` | Resolved logical node identifier |
| `ID_TI` | Resolved node structure identifier (links to `NODE STRUCTURE/<ID_TI>`) |
| `ID_ALIAS_T3` | The Meta4Object owning the aliased node (may differ from the outer `ID_T3`) |

### Status

- **Inventoried:** yes — files are classified as `m4o_alias_json` in `corpus-manifest-v1` (schema 1.1).
- **Content interpreted:** not yet — file content is not read by the current pipeline.
- **Artefact consumer:** future `m4object-node-index-v1` (INC-0007).

---

## Mapping of Meta4Objects

**Status: observed** (path structure, table, field alignment); **derived** (semantic interpretation of base vs. derived direction); **unresolved** (universal confirmation across full corpus)

```
<source_root>/
└── META4OBJECT/
    └── <OWNER_ID_T3>/
        └── MAPPING META4OBJECT/
            └── <OWNER_ID_T3>/
                └── <file>.json
```

`OWNER_ID_T3` denotes the owner (derived) Meta4Object — the object that *has* the mapping.
The label `<OWNER_ID_T3>` is used here to distinguish this component from the `ID_T3` column
in `SPR_DIN_OBJECTS`, which identifies the *base* Meta4Object (see table below).

Note: the inner `<OWNER_ID_T3>` must exactly equal the outer `<OWNER_ID_T3>`. A mismatch
causes a `malformed_m4o_mapping_path` warning and the file is classified as `other_supported`.
The manifest stores this value as `m4o_structure.id_t3`.

### Path segments

| Segment | Identifier extracted | Description |
|---------|---------------------|-------------|
| `<source_root>` | `source_root` | First-level subdirectory. |
| `META4OBJECT` | — | Fixed label; case-sensitive. |
| `<OWNER_ID_T3>` | `id_t3` | The owner (derived) Meta4Object. Corresponds to `SPR_DIN_OBJECTS.ID_T3_I`, **not** to `SPR_DIN_OBJECTS.ID_T3` (base). |
| `MAPPING META4OBJECT` | — | Fixed label; case-sensitive; includes the space. |
| `<OWNER_ID_T3>` (inner) | — | Must match the outer `<OWNER_ID_T3>`; validated by path parser. |
| `<file>.json` | — | JSON resource file. |

### Database table: `SPR_DIN_OBJECTS`

| Column | Meaning | Path correspondence |
|--------|---------|---------------------|
| `ID_T3` | Base Meta4Object identifier | Not present in the path |
| `ID_T3_I` | Owner (derived) Meta4Object identifier | `OWNER_ID_T3` (= `m4o_structure.id_t3`) |

**Observed coherence:** `OWNER_ID_T3 == SPR_DIN_OBJECTS.ID_T3_I`.
The manifest field `m4o_structure.id_t3` captures `OWNER_ID_T3`, which corresponds to
`ID_T3_I` in the table, not to `ID_T3`.

**The semantic interpretation that `ID_T3` is the base and `ID_T3_I` is the derived/owner
is derived from the observed field alignment between path components and table columns.
Whether this direction holds universally across the full corpus is unresolved until
INC-0007 reads the actual JSON file content.**

### Status

- **Inventoried:** yes — files are classified as `m4o_mapping_json` in `corpus-manifest-v1` (schema 1.1).
- **Content interpreted:** not yet — file content is not read by the current pipeline.
- **Artefact consumer:** future `m4object-node-index-v1` (INC-0007).

---

## Support status table

| Resource | Inventoried | Content interpreted | Artefact consumer |
|----------|:-----------:|:-------------------:|-------------------|
| `NODE STRUCTURE` LN4 files | yes | partially | `structural-index-v1`, `reference-extraction-v1` |
| `META4OBJECT/NODE` JSON files | yes | not yet | future `m4object-node-index-v1` |
| `M4O ALIAS RESOLUTION` JSON files | yes | not yet | future `m4object-node-index-v1` |
| `MAPPING META4OBJECT` JSON files | yes | not yet | future `m4object-node-index-v1` |

---

## Classification depth constraint

**Status: observed**

All three META4OBJECT path patterns require exactly 6 path components (depth = 6).
Files at a different depth under `META4OBJECT/` are classified as `other_supported` without
a warning (unknown sub-patterns are silently tolerated to allow corpus evolution).

A violation of the depth constraint combined with recognizable prefix labels produces a
warning code (`malformed_m4o_node_path`, `malformed_m4o_alias_path`, `malformed_m4o_mapping_path`).

---

## What is not yet known

The following aspects of the corpus layout are **unresolved**:

- Whether there are additional sub-patterns under `META4OBJECT/` not yet encountered.
- The exact content schema of the `M4RCH_NODES`, `M4RCH_T3_ALIAS_RES`, and `SPR_DIN_OBJECTS`
  JSON files (field names, data types, optional fields).
- Whether `ID_NODE` values are globally unique across Meta4Objects or only locally unique
  within one `ID_T3`.
- Whether the same `ID_TI` node structure can appear under multiple `source_root` entries.
