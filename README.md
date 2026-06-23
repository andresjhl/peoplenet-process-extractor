# peoplenet-process-extractor

Tooling to analyse functional processes implemented in PeopleNet/Meta4 LN4 and generate
reliable specifications for re-implementation in Groovy.

## Status

**Increment 3 — Corpus inventory (`corpus-manifest-v1`) implemented.**

Increments 1 (`scenario-v1`) and 2 (`run-manifest-v1`) are also complete.
Remaining pipeline phases (discovery, intermediate model, semantic interpretation, rendering)
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
  --corpus-root C:\dev\meta4_ai_tools\peoplenet_src \
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
  --corpus-root C:\dev\meta4_ai_tools\peoplenet_src \
  corpus-manifest.json
```

Detects added, removed, and modified files (by SHA-256 hash).

**Scope:** Only files within the source roots recorded in `included_source_roots` are
checked. New first-level directories outside that scope are not surfaced as additions.

Exit code `0` if the corpus matches the manifest exactly, non-zero on any difference.

## Documentation

- [Pipeline overview](docs/architecture/pipeline-overview.md)
- [Corpus lifecycle](docs/architecture/corpus-lifecycle.md)
- [Run lifecycle](docs/architecture/run-lifecycle.md)
- [Schema: corpus-manifest-v1](docs/schemas/corpus-manifest-v1.md)
- [Schema: run-manifest-v1](docs/schemas/run-manifest-v1.md)
- [Schema: scenario-v1](docs/schemas/scenario-v1.md)
- [ADR-0003: Corpus inventory decision](docs/decisions/ADR-0003-corpus-inventory.md)
- [ADR-0002: Run manifest decision](docs/decisions/ADR-0002-run-manifest.md)
- [ADR-0001: Scenario contract decision](docs/decisions/ADR-0001-scenario-contract.md)
