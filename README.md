# peoplenet-process-extractor

Tooling to analyse functional processes implemented in PeopleNet/Meta4 LN4 and generate
reliable specifications for re-implementation in Groovy.

## Status

**Increment 1 — Scenario contract (`scenario-v1`) implemented.**

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

```bash
uv run python -m peoplenet_process_extractor.scenario migrate \
  path/to/peoplenet_call.json \
  --output scenario.json \
  --report migration-report.json
```

Options:

- `--scenario-id ID` — override the derived scenario ID (default: derived from `process.id`).
- `--force` — overwrite existing output files.

Exit code `0` on success, non-zero on any error.

## Documentation

- [Pipeline overview](docs/architecture/pipeline-overview.md)
- [Schema: scenario-v1](docs/schemas/scenario-v1.md)
- [ADR-0001: Scenario contract decision](docs/decisions/ADR-0001-scenario-contract.md)
