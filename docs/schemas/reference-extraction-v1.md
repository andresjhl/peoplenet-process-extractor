# reference-extraction-v1 Schema

## Overview

`reference-extraction-v1` is a JSON artifact that captures all `Call()` expressions found in the `structured_ln4` files of a corpus. It is the third artifact in the extraction pipeline, produced after the corpus manifest and structural index.

## Purpose

To provide a reproducible, verifiable record of every inter-object call found in the LN4 source code, suitable for downstream analysis (dependency graphs, impact analysis, dead-code detection).

## Inputs

| Input | Description |
|-------|-------------|
| `--corpus-root` | Root directory of the LN4 source corpus |
| `--corpus-manifest` | `corpus-manifest-v1` JSON file describing the corpus |
| `--index` | `structural-index-v1` SQLite database built from the manifest |

The extraction verifies that the index was built from the exact manifest before proceeding.

## JSON Structure

### Top-level object

```json
{
  "format": "reference-extraction-v1",
  "schema_version": 1,
  "generator": { "name": "...", "version": "..." },
  "created_at": "2026-06-24T12:00:00+00:00",
  "source_manifest": { "sha256": "...", "size_bytes": 1234 },
  "source_index": { "sha256": "...", "size_bytes": 5678 },
  "summary": { ... },
  "files": [ ... ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `format` | string | Always `"reference-extraction-v1"` |
| `schema_version` | int | Always `1` |
| `generator` | object | Tool name and version that produced this file |
| `created_at` | string | ISO-8601 UTC timestamp recording when the extractor ran (e.g. `2026-06-24T12:00:00+00:00` or `2026-06-24T12:00:00Z`). Independent of `corpus-manifest.created_at`. |
| `source_manifest` | object | SHA-256 and size of the corpus manifest used |
| `source_index` | object | SHA-256 and size of the structural index used |
| `summary` | object | Aggregate counts (see below) |
| `files` | array | Per-file results, sorted by `path` |

### summary object

```json
{
  "files_total": 10,
  "files_processed": 9,
  "files_with_calls": 5,
  "calls_total": 42,
  "observed": 40,
  "partially_parsed": 0,
  "ambiguous": 0,
  "malformed": 2,
  "unsupported": 0,
  "file_errors": 1
}
```

### files array entry

```json
{
  "path": "CP/NODE STRUCTURE/OBJ/ITEM/METHOD/METH/RULES/METH#R1#1800_01_01.ln4",
  "source_file_id": 3,
  "source_file_sha256": "abcdef...",
  "encoding": "utf-8",
  "line_ending": "lf",
  "status": "processed",
  "errors": [],
  "references": [ ... ]
}
```

| Field | Type | Values |
|-------|------|--------|
| `path` | string | Forward-slash path relative to corpus root |
| `source_file_id` | int | ID from structural index |
| `source_file_sha256` | string or null | SHA-256 of the file bytes; null on read error |
| `encoding` | string or null | `"utf-8"` or `"utf-8-bom"` |
| `line_ending` | string or null | `"lf"`, `"crlf"`, `"mixed"`, or `"none"` |
| `status` | string | `"processed"` or `"error"` |
| `errors` | array | FileError objects; empty if status=processed |
| `references` | array | Reference objects, sorted by `start_offset` |

### references array entry

```json
{
  "id": "ref:abcdef...:42:65",
  "kind": "call",
  "function_name": "Call",
  "status": "observed",
  "source_file_id": 3,
  "path": "CP/.../METH#R1#1800_01_01.ln4",
  "source_file_sha256": "abcdef...",
  "start_offset": 42,
  "end_offset": 65,
  "line_start": 5,
  "column_start": 3,
  "line_end": 5,
  "column_end": 25,
  "raw_expression": "Call(nodeId, \"METHOD\")",
  "raw_arguments": "nodeId, \"METHOD\"",
  "arguments": [ ... ],
  "parser_rule": "ln4_call_v1",
  "diagnostics": []
}
```

### arguments array entry

```json
{
  "position": 0,
  "raw": "nodeId",
  "kind": "identifier",
  "literal_value": null,
  "status": "parsed"
}
```

## Status Values

The tables below distinguish codes **produced** by the INC-0005 scanner from those that are **reserved** for future increments. Reserved codes appear in `VALID_STATUSES` / `VALID_DIAGNOSTIC_CODES` so that artifacts from later increments remain forward-compatible, but the INC-0005 scanner never emits them.

### Reference statuses

| Status | Produced by INC-0005 | Meaning |
|--------|----------------------|---------|
| `observed` | yes | Call found with matching parentheses and parseable arguments |
| `malformed` | yes | Call found but parentheses never closed (end-of-file) |
| `partially_parsed` | **reserved** | Call found but some arguments could not be classified |
| `ambiguous` | **reserved** | Multiple interpretations possible |
| `unsupported` | **reserved** | Call form not handled by current parser version |

### Argument kinds

| Kind | Produced by INC-0005 | Meaning |
|------|----------------------|---------|
| `string_literal` | yes | Starts and ends with `"` |
| `numeric_literal` | yes | Pure numeric (`[0-9]+(\.[0-9]+)?`) |
| `identifier` | yes | Simple name (`[A-Za-z_][A-Za-z0-9_]*`) |
| `expression` | yes | Any other non-empty content |
| `empty` | yes | Empty or whitespace-only |

### File error codes

| Code | Produced by INC-0005 | Meaning |
|------|----------------------|---------|
| `file_not_found` | yes | File listed in index cannot be read |
| `hash_mismatch` | yes | File on disk has different SHA-256 than index |
| `decode_error` | yes | File bytes cannot be decoded as UTF-8 |
| `parser_failure` | yes | Scanner raised an unexpected exception |
| `unsupported_encoding` | **reserved** | Encoding not supported by future parser versions |

### Diagnostic codes (on references)

| Code | Produced by INC-0005 | Meaning |
|------|----------------------|---------|
| `unclosed_parenthesis` | yes | Scan reached end of file without finding closing `)` |
| `unterminated_string` | yes | String literal inside arguments was not closed |
| `unexpected_end_of_file` | **reserved** | End of file encountered unexpectedly (future use) |

## Position Conventions

- **Offsets**: 0-based character indices into the decoded Unicode text string. `text[start_offset:end_offset] == raw_expression`.
- **Lines**: 1-based, counting `\n` characters.
- **Columns**: 1-based, Unicode code points. `\n` increments the line counter and resets the column to 1. `\r` is counted as a column character (not a line break by itself).

## Encoding Conventions

Files are read as bytes first. The SHA-256 is computed over the raw bytes. Then:
- If the first 3 bytes are `EF BB BF` (UTF-8 BOM), the encoding is `"utf-8-bom"`.
- Otherwise, the encoding is `"utf-8"`.

Decoding uses `utf-8-sig` (which strips the BOM if present).

## Line Ending Handling

After decoding, the dominant line ending is detected from the Unicode text:
- `"crlf"`: all newlines are `\r\n`
- `"lf"`: all newlines are `\n` (with no preceding `\r`)
- `"mixed"`: both `\r\n` and bare `\n` present
- `"none"`: no newline characters found

The scanner does NOT normalize line endings before processing. CRLF files are scanned correctly with line/column positions matching the CRLF-inclusive text.

## Reference ID Format

```
ref:{source_file_sha256}:{start_offset}:{end_offset}
```

Example: `ref:abcdef0123456789...:{start}:{end}`

The ID is deterministic, stable across runs, and unique within an extraction (because a given file's byte content determines its SHA-256, and two calls in the same file cannot share the same offsets).

## Reproducibility Requirements

Given identical inputs (corpus root, manifest, index) and the same timestamp (`--created-at`):
1. The output JSON bytes are bit-for-bit identical.
2. All paths use forward slashes (`/`), not backslashes.
3. Output encoding is UTF-8 without BOM.
4. Line endings in the JSON file are LF (never CRLF).
5. A trailing newline is always present.
6. Files are sorted by `path`.
7. References within a file are sorted by `start_offset` (then `end_offset`).

The `--created-at` flag accepts both `Z` and `+00:00` as UTC suffixes (e.g. `2026-06-24T12:00:00Z` and `2026-06-24T12:00:00+00:00` are equivalent). Both produce byte-identical output. Non-UTC offsets and bare timestamps without timezone are rejected.

### Integrity of created_at

`references verify` validates that `created_at` is a well-formed UTC ISO-8601 timestamp (catching invalid formats and non-UTC offsets). It does **not** compare `created_at` against `corpus-manifest.created_at`, because those two timestamps record distinct events — the corpus snapshot and the extractor run — and legitimately differ when extraction is performed after the manifest was built. Protection against external tampering of the entire artifact is provided by recording the artifact's SHA-256 in `run-manifest-v1`.

## Out of Scope

The following are NOT part of this increment:

- **Call resolution**: matching `Call(target, method)` against structural elements. This is INC-0006.
- **Callers/callees graph**: computing who calls whom.
- **SQLite storage**: references are stored in JSON only.
- **Full LN4 grammar**: only `Call()` expressions are extracted.
- **LLM-based parsing**: all parsing is rule-based and deterministic.
