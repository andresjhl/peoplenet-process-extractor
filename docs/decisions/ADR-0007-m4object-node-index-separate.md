# ADR-0007 — Keep the Meta4Object Node Index Separate from the Structural Index

**Status:** Accepted  
**Date:** 2026-06-24

---

## Context

The pipeline currently has `structural-index-v1` (INC-0004), a SQLite database that stores
file classifications and structural elements derived from `NODE STRUCTURE/<ID_TI>/...` paths.

INC-0007 will need to extract and store information from a different part of the corpus:
the `META4OBJECT/` hierarchy, which contains node definitions (`NODE`), alias tables
(`M4O ALIAS RESOLUTION`), and object-to-object mappings (`MAPPING META4OBJECT`).

A question arises: should this Meta4Object information be added to `structural-index-v1`,
or should a new, separate artefact be built?

---

## Decision

A new artefact, `m4object-node-index-v1`, will be built in INC-0007. It will be kept
entirely separate from `structural-index-v1`.

`structural-index-v1` represents:
- File classifications and structural metadata from `NODE STRUCTURE/<ID_TI>/...` paths.
- One row per `structured_ln4` file in `structural_elements`.
- Key fields: `ID_TI` (as `meta4object`), `item_type`, `item_name`, `rule_id`, `rule_date`.

`m4object-node-index-v1` will represent (scope for INC-0007):
- `ID_T3` — the Meta4Object identifier.
- `ID_NODE` — the logical node identifier within a Meta4Object.
- `ID_TI` — the node structure identifier that links to `NODE STRUCTURE/`.
- Own nodes: nodes directly defined in a given Meta4Object.
- Aliases: mappings from alias labels to `ID_NODE` and `ID_TI`.
- Direct inheritance links: object-to-object base/derived relationships.
- Evidence fields and diagnostic information for unresolved or ambiguous entries.

The two indices will not be merged. Resolving a `Call()` expression will require consuming
both indices explicitly and performing an explicit linking step `ID_NODE → ID_TI → structural element`.

---

## Motivation

- **Different domains:** `structural-index-v1` models the physical structure of element files
  (`NODE STRUCTURE/` paths). `m4object-node-index-v1` models the logical structure of objects
  (node membership, alias tables, inheritance). These are related but distinct concerns.
- **Different sources:** the structural index is built from `.ln4` path metadata (no file
  content read). The node index requires reading JSON content from `m4o_node_json`,
  `m4o_alias_json`, and `m4o_mapping_json` files.
- **Independent evolution:** the structural index schema is stable and versioned as `v1`.
  The node index will evolve as INC-0007 and INC-0008 add resolution capabilities.
  Coupling them would force both to change together.
- **Layered validation:** each index can be verified independently. A validation error in the
  node index does not invalidate the structural index and vice versa.
- **Explicit resolution phase:** combining both indices into one would encourage implicit
  resolution logic inside the index builder. Keeping them separate forces resolution to be
  an explicit, auditable step (planned for INC-0008).
- **No Meta4Object semantics in the structural index:** `structural-index-v1` does not know
  about nodes, aliases, or inheritance. Adding that knowledge would violate its scope and
  make it harder to reason about.

---

## Consequences

**Positive:**

- Each index has a single, well-defined responsibility.
- `structural-index-v1` remains unchanged and its existing consumers are unaffected.
- `m4object-node-index-v1` can introduce its own schema, versioning, and validation
  without constraining the structural index.
- The resolution step (`ID_NODE → ID_TI → structural element`) is explicit and testable
  as a separate pipeline phase.

**Negative / constraints:**

- Call resolution (INC-0008) must consume two indices and perform a join step. This adds
  complexity to the resolution phase but makes it auditable.
- A shared corpus identity must be preserved across both indices. Both must reference the
  same `corpus-manifest-v1` snapshot (same SHA-256).
- The explicit linking step `ID_NODE → ID_TI → structural_elements.meta4object` must be
  implemented in INC-0008. This step cannot be skipped or shortcut.

---

## Alternatives rejected

### A1 — Extend `structural-index-v1` with node and alias tables

Add new tables (`nodes`, `aliases`, `inheritance`) directly to `structural-index-v1` schema.

**Rejected:** The structural index models `NODE STRUCTURE/` paths. Node tables model
`META4OBJECT/` paths. Mixing both domains in one database creates a schema whose responsibility
cannot be stated cleanly. It also breaks the scope guarantee of `structural-index-v1`
("stores exactly what the manifest already tells us about file structure").

### A2 — Build a single unified call-resolution index directly

Skip `m4object-node-index-v1` and build a `call-resolution-v1` index that combines structural
elements, node bindings, and resolved calls in one step.

**Rejected:** Premature. Before resolving calls, the node bindings must be extracted and
validated. Building them in a single step makes it impossible to verify intermediate results,
debug extraction failures, or reuse the node index for purposes other than call resolution.

### A3 — Resolve calls during reference extraction

Extend `reference-extraction-v1` (INC-0005) to resolve each `Call()` reference as it is
extracted, without a separate index.

**Rejected:** Reference extraction reads `.ln4` files and detects `Call()` positions.
It does not have access to the Meta4Object model. Adding resolution would couple the scanner
to the domain model, making it harder to test, harder to reason about, and impossible to
re-run extraction independently of resolution.

---

## Related

- [ADR-0004 — Structural Index Decision](ADR-0004-structural-index.md)
- [ADR-0005 — Reference Extraction](ADR-0005-reference-extraction.md)
- [ADR-0006 — Manifest as single source of inventory](ADR-0006-manifest-single-source.md)
- [structural-index-v1 schema](../schemas/structural-index-v1.md)
- [PeopleNet structural model](../domain/peoplenet-structural-model.md)
- [LN4 call resolution](../domain/ln4-call-resolution.md)
