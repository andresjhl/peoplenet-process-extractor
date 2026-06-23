# Pipeline Overview

This document describes the intended architecture of the `peoplenet-process-extractor` system.

## Objective

Analyse functional processes implemented in PeopleNet/Meta4 LN4 and generate reliable specifications that enable another AI to re-implement them in Groovy.

## Phases

```
sources
  → preparation (scenario contract)
  → discovery (elements and dependencies)
  → intermediate model (versioned structured data)
  → validation (structural and semantic checks)
  → semantic interpretation (LLM, controlled and auditable)
  → rendering (deterministic Markdown from structured data)
```

### 1. Sources

Raw artefacts: captured HTTP calls, SQL traces, LN4 source code, manual observations.

### 2. Preparation — Scenario Contract

The starting point for any analysis. Implemented in this increment as `scenario-v1`.

A scenario captures:

- what process is being analysed;
- where execution enters;
- what values were observed at entry;
- what the analyser has manually determined (flags, methods to trace);
- what is still unknown.

**This is the only phase implemented so far.**

### 3. Discovery

Static and dynamic discovery of LN4 elements: methods, properties, conditions, integrations.
Not yet implemented.

### 4. Intermediate Model

A versioned, machine-readable representation of all extracted facts.
Not yet implemented.

### 5. Validation

Structural checks (types, completeness, internal consistency) and semantic checks
(business rules, LN4 constraints).
Partially implemented as part of the scenario contract validation.

### 6. Semantic Interpretation

LLM-assisted interpretation of ambiguous facts: naming conventions, implicit conditions,
undocumented behaviour. Controlled and auditable — LLM output is never treated as ground truth
without evidence.
Not yet implemented.

### 7. Rendering

Deterministic Markdown generation from the intermediate model.
Markdown is **not** generated directly from LN4 source or from LLM free-form output.
Not yet implemented.

## Design Principles

- Discovered facts are strictly separated from derived or assumed facts.
- Every value carries a `source` and a `status`.
- Uncertainty is declared explicitly, never hidden.
- The LLM is used only where human interpretation would be required — never as a parser or executor.
- The original corpus is never modified.
- Generated artefacts are kept separate from source artefacts.

## What the Legacy Repository Is

The `meta4_ai_tools` repository is a prototype and reference. It is **not** the architecture
being followed here. Specific artefacts (captured calls, SQL traces) may be used as input,
but its code is not replicated.
