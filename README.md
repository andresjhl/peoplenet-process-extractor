# peoplenet-process-extractor

Tooling to analyse functional processes implemented in PeopleNet/Meta4 LN4 and generate
reliable specifications for re-implementation in Groovy.

## Status

**Increment 5 — Reference extraction (`reference-extraction-v1`) implemented.**

Increments 1 (`scenario-v1`), 2 (`run-manifest-v1`), 3 (`corpus-manifest-v1`), and 4 (`structural-index-v1`) are also complete.
Remaining pipeline phases (call resolution, dependency graph, semantic interpretation, rendering)
are not yet implemented. See [docs/architecture/pipeline-overview.md](docs/architecture/pipeline-overview.md).

## Installation

```bash
uv sync
```

## Verification

```bash
uv run pytest -q
uv run ruff check .
```


## External PeopleNet corpus

The real PeopleNet corpus is external to this repository and must be treated as
read-only. Automated tests use only anonymized fixtures and never require the
real corpus.

Set the local corpus location in PowerShell:

```powershell
[Environment]::SetEnvironmentVariable(
    "PEOPLENET_CORPUS_ROOT",
    "C:\path\to\peoplenet_src",
    "User"
)
```

Check the variable:

```powershell
$env:PEOPLENET_CORPUS_ROOT
Test-Path $env:PEOPLENET_CORPUS_ROOT
```

Validate the local environment from the repository root:

```powershell
python scripts/check_local_environment.py
```

An optional template for machine-local configuration is available at
`config/local.example.toml`. Do not commit `config/local.toml`.

## Migrate a legacy call

Canonical form:

```bash
uv run peoplenet-process-extractor scenario migrate \
  path/to/peoplenet_call.json \
  --output scenario.json \
  --report migration-report.json
```

Options:

- `--scenario-id ID` — override the derived scenario ID (default: derived from `process.id`).
- `--force` — overwrite existing output files.

Exit code `0` on success, non-zero on any error.

## Create a run manifest

```bash
uv run peoplenet-process-extractor manifest create \
  --scenario scenario.json \
  --runs-root runs \
  --run-id run-20260623-001
```

Options:

- `--run-id ID` — explicit run ID (auto-generated if omitted).
- `--force` — overwrite an existing *managed* run (valid manifest, matching run_id, no unknown files).

This creates:

```
runs/run-20260623-001/
├── run-manifest.json
├── inputs/scenario.json
├── artifacts/
└── reports/
```

The final directory is always `<runs-root>/<run-id>`. Build happens in a staging directory
so the previous run is never touched until the new one is fully validated.

Exit code `0` on success, non-zero on any error.

## Verify a run manifest

```bash
uv run peoplenet-process-extractor manifest verify \
  runs/run-20260623-001/run-manifest.json
```

Recomputes SHA-256 hashes and sizes of all registered files and reports discrepancies.

Exit code `0` if everything matches, non-zero on any inconsistency.

## Build a corpus inventory

```bash
uv run peoplenet-process-extractor corpus inventory \
  --corpus-root $env:PEOPLENET_CORPUS_ROOT \
  --output corpus-manifest.json
```

Options:

- `--corpus-id ID` — override the derived corpus ID (default: directory name).
- `--source-root NAME` — include only this first-level root (repeatable; all discovered by default).
- `--force` — overwrite an existing output file.

Exit code `0` on success, non-zero on any error.

## Verify a corpus inventory

```bash
uv run peoplenet-process-extractor corpus verify \
  --corpus-root $env:PEOPLENET_CORPUS_ROOT \
  corpus-manifest.json
```

Detects added, removed, and modified files (by SHA-256 hash).

**Scope:** Only files within the source roots recorded in `included_source_roots` are
checked. New first-level directories outside that scope are not surfaced as additions.

Exit code `0` if the corpus matches the manifest exactly, non-zero on any difference.

## Build a structural index

```bash
uv run peoplenet-process-extractor index build \
  --corpus-root $env:PEOPLENET_CORPUS_ROOT \
  --corpus-manifest corpus-manifest.json \
  --output structural-index.sqlite
```

Options:

- `--force` — overwrite an existing output file.

Verifies the corpus against the manifest before building. Exit code `0` on success.

## Verify a structural index

```bash
uv run peoplenet-process-extractor index verify \
  --corpus-root $env:PEOPLENET_CORPUS_ROOT \
  --corpus-manifest corpus-manifest.json \
  --database structural-index.sqlite
```

Exit code `0` if the index is valid and matches the corpus and manifest exactly.

## Query a structural index

```bash
# List files by classification
uv run peoplenet-process-extractor index query files \
  --database structural-index.sqlite \
  --classification unstructured_ln4

# Find structural elements
uv run peoplenet-process-extractor index query elements \
  --database structural-index.sqlite \
  --meta4object MY_OBJECT \
  --item-type METHOD

# Statistics
uv run peoplenet-process-extractor index query stats \
  --database structural-index.sqlite
```

Add `--json` to any query command for machine-readable output.

## Extract Call() references

```bash
uv run peoplenet-process-extractor references extract \
  --corpus-root $env:PEOPLENET_CORPUS_ROOT \
  --corpus-manifest corpus-manifest.json \
  --index structural-index.sqlite \
  --output reference-extraction.json
```

Options:

- `--force` — overwrite an existing output file.
- `--created-at ISO8601_UTC` — fix the `created_at` timestamp for reproducible output (optional).

Scans all `structured_ln4` files for `Call()` expressions and produces a canonical JSON artifact.

### Reproducible extraction

Two runs with identical inputs and the same `--created-at` value produce byte-identical output:

```bash
uv run peoplenet-process-extractor references extract \
  --corpus-root $env:PEOPLENET_CORPUS_ROOT \
  --corpus-manifest corpus-manifest.json \
  --index structural-index.sqlite \
  --output reference-extraction.json \
  --created-at 2026-06-24T12:00:00Z
```

Both `Z` and `+00:00` are accepted as UTC suffixes and produce identical artifacts. Non-UTC offsets and timestamps without a timezone are rejected. Without `--created-at`, the current UTC time is used.

`created_at` records when the extractor ran; it is independent of `corpus-manifest.created_at`. `references verify` checks that `created_at` is a valid UTC timestamp. Integrity against external tampering of the field is guaranteed by the artifact's SHA-256 recorded in `run-manifest-v1`.

Exit code `0` on success, non-zero on any error.

## Verify a reference extraction

```bash
uv run peoplenet-process-extractor references verify \
  --corpus-root $env:PEOPLENET_CORPUS_ROOT \
  --corpus-manifest corpus-manifest.json \
  --index structural-index.sqlite \
  --references reference-extraction.json
```

Performs a full physical check: re-hashes sources, re-verifies corpus, and confirms every `raw_expression` matches the text at its recorded offset.

Exit code `0` if valid, non-zero on any inconsistency.

## Query a reference extraction

```bash
# All references
uv run peoplenet-process-extractor references query \
  --references reference-extraction.json

# Filter by status
uv run peoplenet-process-extractor references query \
  --references reference-extraction.json \
  --status malformed

# Filter by file path
uv run peoplenet-process-extractor references query \
  --references reference-extraction.json \
  --path "CP/NODE STRUCTURE/OBJ/ITEM/METHOD/METH/RULES/METH#R1#1800_01_01.ln4"

# Machine-readable JSON output
uv run peoplenet-process-extractor references query \
  --references reference-extraction.json \
  --json
```

Filter options: `--path`, `--status`, `--function-name`, `--kind`.

## Documentation

- [Pipeline overview](docs/architecture/pipeline-overview.md)
- [Reference extraction lifecycle](docs/architecture/reference-extraction-lifecycle.md)
- [Index lifecycle](docs/architecture/index-lifecycle.md)
- [Corpus lifecycle](docs/architecture/corpus-lifecycle.md)
- [Run lifecycle](docs/architecture/run-lifecycle.md)
- [Schema: reference-extraction-v1](docs/schemas/reference-extraction-v1.md)
- [Schema: structural-index-v1](docs/schemas/structural-index-v1.md)
- [Schema: corpus-manifest-v1](docs/schemas/corpus-manifest-v1.md)
- [Schema: run-manifest-v1](docs/schemas/run-manifest-v1.md)
- [Schema: scenario-v1](docs/schemas/scenario-v1.md)
- [ADR-0005: Reference extraction decision](docs/decisions/ADR-0005-reference-extraction.md)
- [ADR-0004: Structural index decision](docs/decisions/ADR-0004-structural-index.md)
- [ADR-0003: Corpus inventory decision](docs/decisions/ADR-0003-corpus-inventory.md)
- [ADR-0002: Run manifest decision](docs/decisions/ADR-0002-run-manifest.md)
- [ADR-0001: Scenario contract decision](docs/decisions/ADR-0001-scenario-contract.md)
