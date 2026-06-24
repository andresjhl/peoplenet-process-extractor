# PeopleNet Structural Model

This document consolidates domain knowledge about the structural model used in PeopleNet/Meta4
corpora. It is intended as a shared reference for pipeline implementers before approaching
INC-0007 and beyond.

Related documents:
- [Corpus layout](corpus-layout.md)
- [LN4 call resolution](ln4-call-resolution.md)
- [corpus-manifest-v1 schema](../schemas/corpus-manifest-v1.md)
- [structural-index-v1 schema](../schemas/structural-index-v1.md)
- [ADR-0006 — Manifest as single source of inventory](../decisions/ADR-0006-manifest-single-source.md)
- [ADR-0007 — Keep Meta4Object node index separate](../decisions/ADR-0007-m4object-node-index-separate.md)
- [INC-0006 — META4OBJECT resources in corpus-manifest-v1](../increments/INC-0006-m4object-resources-manifest-v1.md)

---

## Epistemological classification

Statements in this document are classified as:

| Label | Meaning |
|-------|---------|
| **observed** | Directly confirmed by reading corpus paths, JSON files, or implemented code. |
| **derived** | Logically inferred from two or more observed facts. |
| **inferred** | Plausible interpretation with partial evidence; not yet confirmed. |
| **ambiguous** | Observed evidence admits more than one interpretation. |
| **unresolved** | Actively unknown; no reliable evidence available yet. |

---

## Overview: the structural hierarchy

The following hierarchy describes the conceptual model as understood before INC-0007.

```
Meta4Object
  ID_T3
    │
    │  contains / inherits-from / references
    ▼
  Node
  ID_NODE
    │
    │  links to
    ▼
  Node Structure
  ID_TI
    │
    │  contains
    ▼
  Element
  ITEM/<TYPE>/<NAME>
    │
    │  associated with
    ▼
  LN4 Rules
  RULES/<rule>.ln4
```

Each level is explained in detail below.

---

## Identifiers

### `ID_T3` — Meta4Object identifier

**Status: observed**

The identifier of a Meta4Object. Appears as the third path component under
`META4OBJECT/` in the corpus:

```
<source_root>/META4OBJECT/<ID_T3>/...
```

Evidence: `m4o_structure.id_t3` field populated by the corpus inventory for
`m4o_node_json`, `m4o_alias_json`, and `m4o_mapping_json` entries.
See [corpus-manifest-v1 schema](../schemas/corpus-manifest-v1.md) — `m4o_structure`.

`ID_T3` values are non-empty strings; blank values cause a validation warning
(`malformed_m4o_node_path` or equivalent).

---

### `ID_NODE` — Node identifier

**Status: observed**

The logical identifier of a node *within* the model of a given Meta4Object.
Appears as the fifth path component under `META4OBJECT/<ID_T3>/NODE/` and
`META4OBJECT/<ID_T3>/M4O ALIAS RESOLUTION/`:

```
<source_root>/META4OBJECT/<ID_T3>/NODE/<ID_NODE>/<file>.json
<source_root>/META4OBJECT/<ID_T3>/M4O ALIAS RESOLUTION/<ID_NODE>/<file>.json
```

Evidence: `m4o_structure.id_node` field in the manifest; table `M4RCH_NODES`
column `ID_NODE`; table `M4RCH_T3_ALIAS_RES` column `ID_NODE`.

`ID_NODE` is `null` for `MAPPING META4OBJECT` entries (those entries describe
object-to-object relationships, not individual nodes).

---

### `ID_TI` — Node structure identifier

**Status: observed**

The identifier of the *structure* of a node, stored under `NODE STRUCTURE/`:

```
<source_root>/NODE STRUCTURE/<ID_TI>/ITEM/<TYPE>/<NAME>/RULES/<rule>.ln4
```

`ID_TI` is extracted as the third path component after `NODE STRUCTURE`.
It is the primary key used to locate the physical files that implement a node's elements.

Evidence:
- `corpus-manifest-v1` field `structure.meta4object` (see [naming debt note](#naming-debt-in-structural-index-v1)).
- `structural-index-v1` table `structural_elements`, column `meta4object`.
- Database table `M4RCH_NODES`, column `ID_TI`.
- Database table `M4RCH_T3_ALIAS_RES`, column `ID_TI`.

---

## Critical distinction: `ID_NODE` vs `ID_TI`

**`ID_NODE` and `ID_TI` are distinct concepts.**

| Concept | Scope | Source in corpus |
|---------|-------|-----------------|
| `ID_NODE` | Logical identity of a node within a Meta4Object model | `META4OBJECT/<ID_T3>/NODE/<ID_NODE>/` |
| `ID_TI` | Identity of the physical node structure (set of elements and rules) | `NODE STRUCTURE/<ID_TI>/ITEM/...` |

**Status: observed** — Both identifiers appear in `M4RCH_NODES` as separate columns.

**They may coincide textually in some cases (inferred).** When a node is not shared or aliased,
its logical name often matches its structure name. However, this coincidence cannot be assumed.

**Root nodes where `ID_NODE != ID_TI` have been observed (observed).** This is the clearest
evidence that the two concepts are independent.

A given `ID_TI` (node structure) may be referenced from different contexts (inferred), meaning
that more than one logical node could share the same underlying structure.

---

## Meta4Object derivation and node access

### Derived Meta4Objects

**Status: observed** (path structure, table, field alignment); **derived** (base/derived semantic); **unresolved** (universal confirmation)

A Meta4Object can be marked as derived from another (base) Meta4Object.
This relationship is recorded in:

```
<source_root>/META4OBJECT/<OWNER_ID_T3>/MAPPING META4OBJECT/<OWNER_ID_T3>/<file>.json
```

`OWNER_ID_T3` is the outer path component — the owner (derived) Meta4Object that holds this
mapping file. It is stored as `m4o_structure.id_t3` in the manifest.

Table `SPR_DIN_OBJECTS` contains the corresponding rows. The observed field alignment is:

| Path / manifest | `SPR_DIN_OBJECTS` column | Semantic role |
|-----------------|--------------------------|---------------|
| `OWNER_ID_T3` (`m4o_structure.id_t3`) | `ID_T3_I` | Owner / derived Meta4Object |
| (not in path) | `ID_T3` | Base Meta4Object |

**Observed coherence:** `OWNER_ID_T3 == SPR_DIN_OBJECTS.ID_T3_I`.

The semantic interpretation that `ID_T3` is base and `ID_T3_I` is derived/owner is a
**derived** conclusion. Whether this holds universally is **unresolved** until INC-0007
reads the actual JSON content. See
[corpus-layout.md — Mapping of Meta4Objects](corpus-layout.md#mapping-of-meta4objects).

**A derived Meta4Object may access nodes defined in its base Meta4Object (inferred).**
The exact traversal rules (whether access is transitive, whether overrides are possible)
are **unresolved**.

---

### Alias resolution

**Status: observed** (existence of the mechanism); **unresolved** (precedence rules)

Alias entries exist under:

```
<source_root>/META4OBJECT/<ID_T3>/M4O ALIAS RESOLUTION/<ID_NODE>/<file>.json
```

Table `M4RCH_T3_ALIAS_RES` records:

| Column | Meaning |
|--------|---------|
| `ALIAS` | The alias label used in a call or reference |
| `ID_NODE` | The resolved logical node identifier |
| `ID_TI` | The resolved node structure identifier |
| `ID_ALIAS_T3` | The Meta4Object that owns the aliased node |

An alias relates a logical reference label to an `ID_NODE` and `ID_TI` pair (observed).

Chained aliases (an alias pointing to another alias) and their resolution order are
**unresolved**.

---

## Naming debt in `structural-index-v1`

The column `structural_elements.meta4object` in `structural-index-v1` is named after a
historical convention from the legacy prototype. Its actual semantic content is the
**`ID_TI`** extracted from the path `NODE STRUCTURE/<ID_TI>/ITEM/...`.

**This is documented naming debt.** The field name does not change in the current schema
version because `structural-index-v1` is a versioned contract. Consumers of this field
must interpret it as `ID_TI` (node structure identifier), not as the Meta4Object name
(`ID_T3`).

See also: [structural-index-v1 — Known semantic naming debt](../schemas/structural-index-v1.md#known-semantic-naming-debt).

---

## Open questions for INC-0007

The following points are **unresolved** and must not be assumed to be implemented:

- Precedence rule when a node exists in own model, in base model, and via alias simultaneously.
- Whether inheritance is transitive (base of a base).
- Whether aliases can chain (alias pointing to an alias).
- Whether `Call` arguments that are LN4 variables (not string literals) can be resolved statically.
- Rule validity criteria: when multiple rules exist for the same element, which is active.
- Whether a single `Call` expression can match multiple valid target elements.
- Runtime-dependent references: `Call` arguments computed at runtime cannot be statically resolved.
