# ADR-0005: Reference Extraction v1

**Status**: Accepted
**Date**: 2026-06-24
**Increment**: INC-0005

## Context

The PeopleNet corpus contains LN4 source files that invoke other objects via `Call()` expressions. Before resolving those calls or building a dependency graph, we need a reliable, reproducible, verifiable catalog of every `Call()` expression in the corpus.

The primary use case is: given a corpus of LN4 files, produce a JSON artifact listing every `Call(target, method)` (and variants) found, with exact source positions, raw text, and argument breakdown.

## Decision

Implement a standalone `reference-extraction-v1` extractor that:
1. Reads from the existing `structural-index-v1` (which already catalogs all `structured_ln4` files)
2. Scans each file with a deterministic character-level state machine
3. Produces a canonical JSON artifact

## Why a deterministic character-level scanner over a single regex

A single regex cannot handle:
- Nested `Call()` expressions inside arguments
- String literals that may contain `Call(...)` text
- Line comments (`'` tick, `//`) that may contain `Call(...)` text
- Block comments (`/* ... */`) spanning multiple lines
- Correct line/column tracking after each character

A state machine (NORMAL / IN_STRING / IN_LINE_COMMENT / IN_BLOCK_COMMENT) handles all of these cleanly and is easier to test in isolation.

### Why not a full LN4 grammar

Writing a full LN4 grammar (e.g., using `lark` or `antlr`) would:
- Add an external dependency
- Require maintenance as LN4 syntax evolves
- Be much slower (parsing the full grammar for every file)

Since we only care about `Call()` expressions, a targeted scanner is sufficient and simpler.

## Why separate extraction from resolution

Resolution (matching `Call(target, method)` to a structural element) requires the full index of all objects. Extraction is purely local to each file. Separating them:
- Keeps each step independently verifiable
- Allows the extraction to be re-run without rebuilding the index
- Makes the pipeline composable (INC-0006 takes the extraction as input)
- Avoids coupling the extraction to the resolution algorithm (which may change)

## Why JSON (not SQLite)

The extraction artifact:
- Is read-only after creation
- Benefits from human readability for debugging
- Does not need efficient random-access queries across millions of rows
- Needs to be diffable in version control (golden tests)

SQLite is appropriate for the structural index (which supports complex queries), but JSON is sufficient for the extraction.

## Why the artifact includes all structured_ln4 files (even those with zero calls)

Completeness: an analyst can verify that a file was processed and found no calls. This distinguishes "processed and found nothing" from "never processed". It also makes coverage checks trivial (count files, not just files-with-calls).

## Why the index SHA-256 is stored in the artifact

Verifiability: the artifact records exactly which index it was built from. If the index is rebuilt from a modified manifest, re-running `references verify` will detect the mismatch and fail.

## Why `Call` is case-sensitive

The LN4 corpus evidence shows exclusively `Call` (mixed case). `call` and `CALL` are not observed. Making the detection case-sensitive avoids false positives on identifiers like `CALLBACK` or `Callable`.

## Why `Call` requires a word boundary

Without a word boundary check, `MyCall(...)` would be detected as a call. The check ensures only standalone `Call` keywords are detected.

## Known Limitations

- No escape sequences in strings: the scanner does not handle `\"` inside a string literal. No such patterns were observed in the corpus evidence.
- `Call` is the only keyword detected: `Callp`, `CallList`, etc. are explicitly excluded.
- No support for multi-line string literals spanning a comment boundary.
- Column tracking treats `\r` as a column character (not a line break). This is correct for the CRLF convention used in some files.

## Alternatives Considered

| Alternative | Rejected Because |
|-------------|-----------------|
| Single regex | Cannot handle nested structures, comments, or strings correctly |
| Full LN4 grammar | External dependency, overkill for extracting only `Call()` |
| SQLite output | JSON is simpler, more human-readable, sufficient for the use case |
| Including non-structured files | Only `structured_ln4` files contain `Call()` expressions |
| Resolving calls in the same step | Couples two distinct concerns; complicates testing |

## Reserved States and Diagnostics

The schema defines a superset of codes to allow future increments to extend the artifact without breaking consumers that validate against `VALID_STATUSES` and `VALID_DIAGNOSTIC_CODES`.

**INC-0005 produces only:**

| Category | Codes produced |
|----------|---------------|
| Reference status | `observed`, `malformed` |
| Argument kinds | `string_literal`, `numeric_literal`, `identifier`, `expression`, `empty` |
| File error codes | `file_not_found`, `hash_mismatch`, `decode_error`, `parser_failure` |
| Diagnostic codes | `unclosed_parenthesis`, `unterminated_string` |

**Reserved (schema-valid but not emitted by INC-0005):**

| Category | Reserved codes |
|----------|---------------|
| Reference status | `partially_parsed`, `ambiguous`, `unsupported` |
| File error codes | `unsupported_encoding` |
| Diagnostic codes | `unexpected_end_of_file` |

Downstream consumers must tolerate all schema-valid codes, not just those produced today.

## created_at Semantics

`extraction.created_at` records **when the extractor ran**, not when the corpus snapshot was taken. It is independent of `corpus-manifest.created_at` and legitimately differs when extraction is re-run after a manifest was built.

`references verify` validates only that `created_at` is a well-formed UTC ISO-8601 timestamp:
- Accepts both `+00:00` and `Z` suffixes (they represent the same UTC instant).
- Rejects missing timezone, invalid format, or non-UTC offsets.
- Does **not** compare against `manifest.created_at`.

Protection against external tampering (e.g. silently changing `created_at` to a different UTC instant without altering any other field) is provided by recording the artifact's SHA-256 in `run-manifest-v1`. The `--created-at` flag enables byte-for-byte reproducibility across runs.

## Consequences

- The extraction is deterministic and reproducible given identical inputs.
- Downstream tools (INC-0006 resolution, INC-0007 graph) take this artifact as input.
- The artifact is independent of the corpus's git state (only content hashes matter).
- Adding new `Call()` variants requires updating the scanner and regenerating the golden.
- The golden test guards against regressions in call detection.
