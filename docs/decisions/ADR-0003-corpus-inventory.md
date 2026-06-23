# ADR-0003 — Versioned Corpus Inventory

## Status

Accepted

## Date

2026-06-23

## Problem

The prototype (`meta4_ai_tools`) builds a SQLite index by walking `peoplenet_src` directly.
This creates several problems:

- The identity of the corpus is implicit inside the SQLite database.
- Staleness detection uses file count and `mtime`, not content hashes.
- There is no standalone record of which files were present and what they contained.
- Inventory, path parsing, and call extraction are coupled in one step.
- It is impossible to distinguish a corpus change from a logic change in the indexer.
- Reproducibility depends on the current state of an external directory.

## Decision

Implement a **versioned corpus inventory** (`corpus-manifest-v1`) that:

1. Walks the corpus without modifying or copying it.
2. Records each file's relative path, SHA-256 hash, size, classification, and PeopleNet structure.
3. Generates a deterministic summary.
4. Records optional Git metadata about the corpus repository.
5. Supports comparison between two inventory snapshots.
6. Provides `corpus inventory` and `corpus verify` CLI commands.

## Key design decisions

### D1 — Corpus stays external

The corpus is not copied into this repository.  The manifest captures a snapshot reference.
This avoids bloat and preserves the corpus as a separate, authoritative source.

### D2 — Hashes as primary identity

`mtime` is not stored in the manifest and not used as evidence of change.
SHA-256 over raw bytes is the sole mechanism for detecting content modifications.
This eliminates false positives from filesystem metadata changes (copies, syncs, etc.).

### D3 — Relative paths only

Absolute paths are never stored in the manifest.  The corpus can be moved or cloned without
invalidating the manifest's path records.  The CLI accepts an absolute `--corpus-root` at
runtime but does not persist it.

### D4 — Unstructured files are preserved

`.ln4` files outside the recognized PeopleNet path structure are classified as
`unstructured_ln4` and included in the manifest.  Discarding them would silently hide
corpus content; explicit preservation makes the inventory complete and auditable.

### D5 — Strict scope for `verify`

`corpus verify` re-inventories using exactly the source roots recorded in the manifest
(`included_source_roots`).  It does not silently expand scope to new roots.
New first-level directories visible outside that scope are not surfaced as changes in the
default verify path.  This is documented as a known limitation.

### D6 — Non-existent requested root is a blocking error

When `--source-root` specifies a root that does not exist, the inventory fails.
Rationale: the caller declared an exact scope; generating a manifest that silently omits
it would create a false sense of completeness.

### D7 — Unreadable file is a blocking error

A file that cannot be read (permission denied, I/O error) causes the inventory to fail.
Rationale: a manifest that appears complete but silently skips files is dangerous.
Partial manifests are never written.

### D8 — Summary recomputed on validation

When a manifest is loaded, the summary is recomputed from the `files` list and compared
to the stored summary.  A mismatch is a validation error.  This catches:
- Manual edits to the manifest.
- Serialization bugs.
- Truncated writes.

The `files` list is always the authoritative source; the summary is derived.

### D9 — No commit needed for Git info

Git metadata is recorded opportunistically.  If `git` is not available or the corpus is
not inside a repository, `commit=null` and `dirty=null` are stored and a warning is emitted.
The inventory does not fail.

---

## Alternatives considered

### A1 — Index directly (no manifest step)

Build the SQLite index directly from the filesystem.  Rejected because:
- No stable contract between corpus state and index.
- Cannot detect corpus drift without re-indexing.
- Couples discovery logic to indexing logic.

### A2 — Copy corpus into repository

Include the corpus as a git submodule or vendored directory.  Rejected because:
- The corpus is large and proprietary.
- It would permanently couple this tool to one specific corpus version.
- The tool should work with any corpus provided at runtime.

### A3 — Use only `mtime` for change detection

Fast but unreliable.  `mtime` changes when a file is copied, synced, or touched without
changing its content.  SHA-256 is more expensive but unambiguous.

### A4 — Invent `corpus_manifest` source kind in `run-manifest-v1`

Extending `run-manifest-v1`'s `SourceKind` enum was considered.  Deferred: the existing
`configuration` kind is sufficient for tracking the corpus manifest as a run input,
and schema changes require broader review.

---

## Consequences

**Positive:**
- Any future indexer can consume a corpus manifest rather than re-walking the filesystem.
- `corpus verify` provides instant drift detection.
- The manifest is portable and can be version-controlled separately from the corpus.
- Reproducing an analysis requires only the manifest hash, not the full corpus path.

**Negative / Limitations:**
- Generating a manifest requires reading every inventoried file (for hashing).  Large corpora will be slower.
- `corpus verify` with exact scope will not surface new first-level roots automatically.
- Git metadata depends on the `git` binary being present.

---

## Out of scope

- SQLite index.
- LN4 content extraction.
- Call graph or dependency resolution.
- Incremental / watcher-based updates.
- Heuristic rename detection.
- Multi-version manifest migration.
- Directory-level hashing.
- Submodule analysis.
