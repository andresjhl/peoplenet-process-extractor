# ADR-0001 — Scenario Contract (scenario-v1)

**Status:** Accepted  
**Date:** 2026-06-22

---

## Context

The existing `meta4_ai_tools` prototype stores all information about a process call in a single
`peoplenet_call.json` file. That file mixes:

- input values captured from a browser HTTP call;
- flags corrected or added manually;
- calculated intermediate values;
- methods selected manually for analysis;
- the functional process identifier;
- property-to-input bindings;
- technical notes.

This mixture makes it impossible to determine:

- which values were directly observed vs. manually derived;
- which values need to be recalculated if a dependency changes;
- which elements are hypotheses vs. confirmed facts;
- what evidence supports each data point;
- which branches can be evaluated;
- what information is still missing.

Any pipeline built on top of this format cannot distinguish reliable data from assumptions.

---

## Problem

We need a stable, auditable input contract for the analysis pipeline. Without it:

- future analysis steps would inherit all ambiguities from the legacy format;
- LLM-assisted interpretation would have no clean separation between facts and guesses;
- reproducibility of the final Markdown specification would be impossible.

---

## Alternatives Considered

### 1. Keep `peoplenet_call.json` without changes

Fastest to start. Requires no migration work. However, all downstream phases would need to
implement their own ad-hoc disambiguation. Ambiguities would propagate through the entire
pipeline and would be invisible in the final output.

**Rejected:** does not address the core problem.

### 2. Generate Markdown directly from `peoplenet_call.json`

The prototype approach. The LLM would interpret the mixed data and produce a specification.
Fast for a single run, but not reproducible, not auditable, and not correctable without
rerunning the entire pipeline.

**Rejected:** directly contradicts the project principle of using LLM only for semantic
interpretation, never as a parser or data normaliser.

### 3. Introduce a generic, complete model from the start

Design a full data model covering all phases: discovery, dependency graphs, branch analysis,
SQL correlation, etc. Comprehensive but premature — we do not yet know the full scope of
what the pipeline needs.

**Rejected:** over-engineering. Building on a speculative model risks expensive rework when
real requirements emerge.

### 4. Create a minimal, versioned scenario contract

Define only what is needed to describe a single scenario before analysis begins:
process, entry point, observed inputs, manual decisions, and known unknowns. Version the
schema so that future increments can extend it without breaking existing work.

**Adopted.** This is `scenario-v1`.

---

## Decision

Implement `scenario-v1`: a structured, versioned JSON document that separates:

- `entry_inputs`: values directly observed in the browser call (`source=frontend_call`, `status=observed`);
- `flags`: values manually determined by the analyser (`source=manual_derivation`, `status=derived`);
- `runtime_values`: values calculated during execution, populated in future increments;
- `property_bindings`: relationships between properties and supplying inputs, without inventing values;
- `process` and `entry_point`: the functional process and execution entry, with explicit provenance;
- `analysis_scope`: the set of methods manually selected for tracing;
- `notes`: free-text observations, never interpreted as facts;
- `configuration`: system parameters, separate from runtime data.

Every value carries `source` and `status` from closed catalogues. Arbitrary strings in
either field are validation errors.

Implement a one-way adapter from the legacy format. The adapter generates a structured
migration report that documents every default applied, every warning, and every unknown field.

---

## Consequences

**Positive:**

- All downstream phases start from clean, auditable data.
- Provenance and certainty are machine-readable; they do not need to be inferred.
- The schema is versioned; future increments extend it without breaking existing scenarios.
- Migration is transparent: every decision made by the adapter is recorded.
- The golden test ensures the migration output is deterministic and stable.

**Negative / Risks:**

- Migration from the legacy format requires a manual review step to confirm that
  defaults (`manual_derivation`, `derived`) are correct for each scenario.
- The P_ID_FLUJO coherence check is a blocker: if the captured value does not match
  the manually set `proceso` field, the migration fails. This can surface legacy
  inconsistencies that were previously invisible.
- The adapter does not automatically populate `runtime_values`. Any binding to an input
  not present in `entry_inputs` generates a warning; the analyser must decide whether
  the missing value is a runtime assignment, a separate call, or a data error.

---

## Out of Scope for This Increment

- LN4 code parser.
- Discovery of methods, properties, or conditions.
- Branch analysis or condition evaluation.
- SQL correlation or database trace analysis.
- Automatic flag calculation.
- Intermediate model (phases 3–7 of the pipeline).
- Markdown generation.
- Support for multiple schema versions simultaneously.
- Database or API for scenario storage.
- Integration with `meta4_ai_tools`.
