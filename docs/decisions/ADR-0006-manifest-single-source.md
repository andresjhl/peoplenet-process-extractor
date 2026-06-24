# ADR-0006 — Manifest as the Single Source of Corpus Inventory

**Status:** Accepted  
**Date:** 2026-06-24

---

## Context

The pipeline now produces several derived artefacts from a PeopleNet corpus:
`structural-index-v1`, `reference-extraction-v1`, and the forthcoming
`m4object-node-index-v1`. Each of these must discover which corpus files to process and
obtain their paths, hashes, and structural metadata.

An alternative approach would allow each extractor or index builder to walk the corpus
directory independently and derive its own view of the corpus content.

---

## Problem

Without a single authoritative source of corpus inventory:

- Each extractor would implement its own traversal and path-parsing logic, creating
  duplicate code with divergence risk.
- Two extractors run at different times could see a different set of files if the corpus
  is modified between runs.
- It would be impossible to verify that all derived artefacts were built from exactly the
  same corpus snapshot.
- Drift between the physical corpus and a derived artefact would go undetected until it
  surfaced as a content error in a downstream phase.
- There would be no stable identity to check for reproducibility.

---

## Decision

All derived artefacts in this pipeline consume entries from `corpus-manifest-v1` as the
sole source of corpus inventory. Specifically:

1. **No index or extractor discovers resources by traversing the corpus directly.** The only
   pipeline component permitted to walk the corpus filesystem is `corpus inventory`.
2. **The manifest records paths, SHA-256 hashes, sizes, classifications, and structural
   metadata** derived from path parsing. This information is authoritative for downstream
   consumers.
3. **Physical file access after inventory is gated on manifest entries.** A file not present
   in the manifest is not processed by any downstream phase, even if it exists on disk.
4. **Resource identity is verified when warranted.** Before processing a file whose content
   matters, downstream consumers re-hash the physical file and compare against the manifest
   hash to detect drift.
5. **Changes to the manifest propagate to all derived artefacts.** When the manifest is
   updated (e.g. new corpus snapshot), all downstream artefacts must be rebuilt.

---

## Motivation

- **Reproducibility:** given the same manifest, two independent runs of any downstream phase
  see the same universe of files, in the same order, with the same identity.
- **Traceability:** each derived artefact records the SHA-256 of the manifest it was built
  from, creating an unambiguous chain of custody.
- **Drift detection:** if the physical corpus changes after inventory, `corpus verify` detects
  it. Downstream consumers that re-hash files at processing time detect individual file drift.
- **Separation of concerns:** discovery (corpus inventory) and extraction (all subsequent
  phases) are distinct steps with distinct responsibilities.
- **No duplicate path-parsing logic:** the path parser runs once, in `corpus inventory`.
  Downstream phases receive already-classified, already-parsed metadata.
- **Consistent corpus view:** all phases built from the same manifest agree on exactly which
  files exist, regardless of when they run.

---

## Consequences

**Positive:**

- Downstream phases are isolated from filesystem variability.
- Adding a new resource type requires first adding support in the manifest (INC-0006 is the
  template: new classifications, path parser extension, schema bump).
- The manifest SHA-256 stored in each derived artefact enables independent verification of
  the full pipeline chain.

**Negative / constraints:**

- New resource types must be supported in the manifest *before* they can be consumed by
  downstream phases. This means a schema increment is required before a new index can be built.
- Index and artefact versions depend on the manifest schema version. A manifest schema change
  may force a rebuild of all derived artefacts.
- The manifest must be regenerated whenever the corpus changes meaningfully. There is no
  incremental update path for the manifest itself; it is rebuilt in full.

---

## Alternatives rejected

### A1 — Each extractor traverses the corpus directly

Every phase walks `PEOPLENET_CORPUS_ROOT` independently. Fast to prototype.

**Rejected:** Duplicate traversal and path-parsing logic; risk of divergent corpus views
between phases; no reproducibility guarantee; no stable inventory to check drift against.

### A2 — Ad hoc discovery by file extension or folder name

Each phase discovers files it needs by extension (`.json`, `.ln4`) or folder prefix
(`META4OBJECT/`, `NODE STRUCTURE/`).

**Rejected:** Recreates classification logic outside the manifest; produces a different corpus
view depending on which phase runs and when; no hash-based identity; duplicates the work
already done by `corpus inventory`.

### A3 — Use the manifest only as a final report, not as input

Generate the manifest after all extractions complete, as a summary document.

**Rejected:** Defeats the purpose. Downstream phases would have no stable input identity.
The manifest exists precisely to be consumed by subsequent phases, not to record what they did.

---

## Related

- [ADR-0003 — Versioned Corpus Inventory](ADR-0003-corpus-inventory.md)
- [ADR-0004 — Structural Index Decision](ADR-0004-structural-index.md)
- [corpus-manifest-v1 schema](../schemas/corpus-manifest-v1.md)
- [ADR-0007 — Keep Meta4Object node index separate](ADR-0007-m4object-node-index-separate.md)
