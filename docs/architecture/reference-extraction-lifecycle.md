# Reference Extraction Lifecycle

## Pipeline Overview

```
corpus (LN4 source files)
  │
  ▼
corpus inventory (corpus-manifest-v1)
  │  Catalogs all files with sha256, classification, structure
  ▼
structural index (structural-index-v1)
  │  SQLite: source_files, structural_elements, index_metadata
  ▼
reference extraction (reference-extraction-v1)        ← INC-0005
  │  JSON: every Call() expression with position, args, status
  ▼
[call resolution]                                     ← INC-0006 (future)
  │  Match Call(target, method) to structural elements
  ▼
[dependency graph]                                    ← INC-0007+ (future)
     Callers, callees, reachability, impact analysis
```

## Current Increment (INC-0005): Extraction

The `references extract` command:

1. **Validate inputs** — corpus root, manifest path, and index path must all exist.

2. **Load and verify corpus manifest** — deserializes the manifest JSON and verifies the corpus against it (all files present, hashes match). This ensures we are scanning the exact corpus the manifest describes.

3. **Hash manifest and index** — computes SHA-256 and size of both files. These are recorded in the output artifact so that `references verify` can re-check provenance.

4. **Full index validation** — runs `validate_index()` with the loaded manifest and computed manifest SHA-256. This checks: SQLite integrity, schema, counter consistency, and field-by-field correspondence with the manifest (including the `corpus_manifest_sha256` provenance link). Extraction aborts if any check fails.

5. **Get structured_ln4 files** — queries `source_files WHERE classification = 'structured_ln4'` to get the list of files to scan, with their expected SHA-256 values.

6. **Process each file**:
   - Read raw bytes
   - Compute SHA-256 and compare against index (hash_mismatch error if different)
   - Detect encoding (utf-8 or utf-8-bom)
   - Decode with `utf-8-sig` (handles both)
   - Detect line endings (lf / crlf / mixed / none)
   - Scan for `Call()` expressions using the state machine scanner
   - Build Reference objects from scan results

7. **Build and validate model** — constructs a `ReferenceExtraction` dataclass and validates all fields, counters, and ID formulas.

8. **Serialize canonically** — UTF-8, 2-space indent, LF endings, trailing newline.

9. **Write atomically** — write to temp file, validate the temp file, then `os.replace()` to publish. On any failure, the temp file is deleted.

## Scanner State Machine

The scanner processes text character by character in one of four states:

```
         '  or  //       /*
NORMAL ──────────────► IN_LINE_COMMENT
  │                         │ \n
  │ "                       └──────► NORMAL
  │
  ▼                    /*
IN_STRING ────────────► (never: strings don't contain block comments)
  │ "
  └──────► NORMAL

NORMAL ──────────────► IN_BLOCK_COMMENT
         /*                  │ */
                             └──────► NORMAL
```

When in NORMAL state, the scanner looks for `Call` (case-sensitive, word-boundary checked), followed by optional whitespace and `(`. On match:
- `_find_call_extent()` finds the matching `)`, handling nested parens and string content
- The Call's extent is recorded as a `ScanCall`
- The main loop advances only past `Call` (not past the full expression), so inner `Call()` expressions inside arguments are naturally re-discovered

## File Error Handling

Each file is processed independently. If a file fails (read error, hash mismatch, decode error, scanner crash), a `FileError` record is added to its `FileResult` and the status is set to `"error"`. This does not abort the entire extraction — other files continue to be processed.

## Verification

`references verify` performs a full physical check by re-extracting in memory and comparing every deterministic field:

1. Loads the extraction JSON and validates format/version.
2. Re-hashes the manifest and index files, comparing against stored `source_manifest` and `source_index` values.
3. Re-verifies the corpus against the manifest (all files present, hashes match).
4. Runs the full structural validation of the index (`validate_index()`) — integrity, schema, counters, manifest correspondence.
5. Validates `created_at` is a parseable UTC ISO-8601 timestamp (accepts both `+00:00` and `Z`; rejects missing timezone, non-UTC offsets, invalid format). `created_at` is not compared against `manifest.created_at` — they record distinct events and legitimately differ when extraction is re-run later.
6. Queries the index for the list of structured_ln4 files, re-extracts all of them in memory, and checks coverage (no missing or extra paths).
7. Compares root-level fields against re-extracted values:
   - `generator.name` and `generator.version` against the installed package constants
   - All 10 `summary` counters against `_build_summary()` on re-extracted files
8. For every file (including error files): compares all file-level fields against re-extracted values:
   - `source_file_id`, `source_file_sha256`, `encoding`, `line_ending`, `status`
   - `errors` list (ordered, field-by-field: `code`, `message`, `evidence`)
   - Reference count (detects removed or added references); skipped if either file has non-processed status
   - Per-reference: `id`, `kind`, `function_name`, `status`, `source_file_id`, `path`, `source_file_sha256`, `start_offset`, `end_offset`, `line_start`, `column_start`, `line_end`, `column_end`, `raw_expression`, `raw_arguments`, `parser_rule`, `diagnostics`
   - Per-argument: `position`, `raw`, `kind`, `literal_value`, `status`
9. Validates all field constraints and counter consistency via `validate_extraction_model()`.

## Future Phases

### INC-0006: Call Resolution

Takes `reference-extraction-v1` and `structural-index-v1` as inputs.
Maps each `Call(target, method)` to a `source_file_id` in the structural index.
Produces a `call-resolution-v1` artifact.

### INC-0007+: Dependency Graph

Takes resolved calls as input.
Builds caller/callee adjacency, reachability, impact sets.
May produce a graph database or adjacency JSON.

## Artifact Provenance Chain

```
corpus bytes
  └── sha256 per file ──► corpus-manifest-v1.json
        sha256, size ──────────────────────────────► structural-index-v1.sqlite
                                sha256, size ──────────────────────────────────► reference-extraction-v1.json
```

Each artifact stores the SHA-256 and size of its upstream inputs, creating a verifiable chain from source bytes to final output.
