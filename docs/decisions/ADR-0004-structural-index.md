# ADR-0004: Structural Index Decision

**Status:** Accepted
**Date:** 2026-06-23

---

## Context

After generating a `corpus-manifest-v1`, the pipeline needs an efficient way to query:
- Which files exist and what their classification is.
- Which LN4 files are structured and what their meta4object / item type / item name / rule is.
- Aggregate counts and breakdowns.

The manifest itself is a JSON file. As the corpus grows (thousands of files), scanning the JSON for every query becomes expensive. A persistent, queryable store is needed before the extraction phase can proceed.

---

## Decision

Implement a SQLite database called `structural-index-v1` that:
1. Consumes a `corpus-manifest-v1` (not the corpus directly).
2. Stores exactly the information already present in the manifest in relational tables.
3. Is built transactionally; never leaves a partial file.
4. Is verified before use by re-checking the manifest SHA-256.

---

## Why SQLite

| Option | Pros | Cons |
|---|---|---|
| JSON direct | Zero code | Full scan for every query; no indexes; 100 KB+ parses |
| SQLite | Fast indexed queries; standard library; ACID transactions; FK constraints | Binary file (not diff-friendly); physical bytes not reproducible |
| SQLite + ORM (SQLAlchemy) | Pythonic API | New dependency; adds abstraction that hides SQL; harder to audit |
| DuckDB / other | Columnar; fast analytics | New dependency; overkill for this size |

SQLite is already available in Python's standard library (`sqlite3`), has mature support for foreign keys and `PRAGMA integrity_check`, and is sufficient for the expected corpus size (tens of thousands of files).

---

## Why the index consumes the manifest, not the corpus

The manifest is the canonical representation of the corpus snapshot. It:
- Has been validated by `corpus inventory`.
- Has been verified against the physical corpus by `corpus verify`.
- Contains all structural information already derived by the path parser.

Re-deriving structure from paths at index-build time would duplicate the path-parsing logic and could introduce divergence. The index builder calls `corpus verify` once before building, then reads exclusively from the manifest.

---

## Why not recrawl the corpus at build time

Re-crawling would:
- Risk incorporating new files added after the manifest was created.
- Require re-parsing all paths.
- Defeat the purpose of the manifest as the single authoritative snapshot.

The builder is allowed to access the corpus only for the mandatory pre-build `corpus verify`.

---

## Why files and structural_elements are separate tables

`source_files` holds all files (6 classifications). `structural_elements` holds only `structured_ln4` files. Separating them makes two things easy:
- "All files in root GTO" — one table, one filter.
- "All METHOD items in object OBJ_A" — join tables, two filters.

A single table with nullable structure columns would require many NULL checks and would make the structural constraint (`structured_ln4` ↔ element) harder to enforce.

---

## Why no LN4 analysis in this increment

The structural index stores what the file system and path conventions already tell us (meta4object, item_type, item_name, rule_id, rule_date). LN4 content analysis (extracting `Call()` references, resolving method bodies) is a separate future increment. Adding it now would couple the index to the LN4 parser, which is not yet implemented.

---

## Alternatives considered

| Alternative | Reason rejected |
|---|---|
| Append-only log | No random access; no FK enforcement |
| Full rebuild as JSON snapshot | No indexes; O(N) for every query |
| Incremental index update | Complexity not justified; rebuild is fast enough |
| Multiple corpus databases | Out of scope; one index per manifest |

---

## Consequences

- The pipeline now has an efficient queryable layer between `corpus-manifest-v1` and future extraction phases.
- Downstream consumers must validate the index before use (SHA-256 of manifest stored in index metadata).
- Physical SQLite bytes are not reproducible across builds (page allocation, internal SQLite metadata). Use `logical_export()` for content comparisons in tests. WAL mode was considered and rejected — the index uses DELETE journal mode to avoid leaving `.db-wal`/`.db-shm` sidecar files beside the output.
- The index must be rebuilt when the manifest changes (no merge strategy).

---

## Risks

- SQLite is not suitable if the corpus ever exceeds ~10 M files (page cache pressure). At that scale, a columnar store (DuckDB) would be preferred.
- The single-file design means concurrent writes are not possible. Not a concern for the current single-process pipeline.

---

## Out of scope

- Incremental updates.
- Multiple corpora per database.
- Full-text search (FTS5).
- LN4 content extraction.
- Call graph construction.
