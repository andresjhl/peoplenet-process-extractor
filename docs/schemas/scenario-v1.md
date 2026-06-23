# Schema: scenario-v1

## Purpose

`scenario-v1` is a structured, versionable representation of a single functional scenario
to be analysed. It captures what is known, what is assumed, and what is unknown at the start
of an analysis, using closed catalogues for provenance and status.

## Schema Version

Every scenario document must include:

```json
"schema_version": "1.0"
```

Only version `1.0` is currently supported. Any other value is a validation error.

---

## Top-Level Structure

```json
{
  "schema_version": "1.0",
  "scenario_id": "11-jorn-store-u",
  "process": { ... },
  "entry_point": { ... },
  "entry_inputs": [ ... ],
  "property_bindings": [ ... ],
  "runtime_values": [ ... ],
  "flags": [ ... ],
  "configuration": [ ... ],
  "analysis_scope": { "methods": [ ... ] },
  "notes": [ ... ],
  "source_files": { ... }
}
```

---

## Fields

### `scenario_id`

A non-empty string that uniquely identifies the scenario. Must not be blank.

When derived automatically from `process.id`, the rule is:
1. Lowercase the string.
2. Replace every run of non-alphanumeric characters with a single `-`.
3. Strip leading and trailing `-`.

Example: `11_JORN_STORE_U` → `11-jorn-store-u`.

The same input always produces the same ID (deterministic, no timestamps, no UUIDs).

---

### `process`

The functional process being analysed.

```json
{
  "id": "11_JORN_STORE_U",
  "source": "manual_derivation",
  "status": "derived"
}
```

| Field    | Type   | Description                                 |
|----------|--------|---------------------------------------------|
| `id`     | string | Functional process identifier. Must not be blank. |
| `source` | Source | How the process ID was determined.          |
| `status` | Status | Degree of certainty.                        |

---

### `entry_point`

Where execution begins.

```json
{
  "meta4object": "GLB_11_G_PA_PC_V1",
  "node": "GLB_G_PA_PC",
  "method": "GLB_M_PC_EXE",
  "arguments": ["STEP_SAVE"]
}
```

| Field          | Type         | Description                                          |
|----------------|--------------|------------------------------------------------------|
| `meta4object`  | string       | LN4 object name. Must not be blank.                  |
| `node`         | string       | Node within the object. Must not be blank.           |
| `method`       | string       | Method name, without arguments. Must not be blank.   |
| `arguments`    | list[any]    | Literal arguments: strings, integers, floats, booleans, null. |

The legacy format `GLB_M_PC_EXE("STEP_SAVE")` is parsed into `method` + `arguments`.
Only simple literal arguments are supported. Complex LN4 expressions are not parsed —
the raw string is preserved with a warning.

---

### `entry_inputs`

Values observed in the initial HTTP call captured from the browser.

Each element:

```json
{
  "name": "P_ID_FLUJO",
  "value": "11_JORN_STORE_U",
  "type": "string",
  "source": "frontend_call",
  "status": "observed"
}
```

| Field    | Type   | Description                                    |
|----------|--------|------------------------------------------------|
| `name`   | string | Parameter name. Must be unique within the list. |
| `value`  | any    | Exact value as received (type is preserved).   |
| `type`   | string | JSON type name: `string`, `integer`, `float`, `boolean`, `null`, `array`, `object`. |
| `source` | Source | Always `frontend_call` when migrated from legacy. |
| `status` | Status | Always `observed` when migrated from legacy.   |

String values are never automatically converted to numbers.

---

### `property_bindings`

Relationships between LN4 properties and the inputs or variables that supply their values.

```json
{
  "property": "GLB_COND_HOR_SRZ",
  "input": "P_14"
}
```

| Field      | Type   | Description                                    |
|------------|--------|------------------------------------------------|
| `property` | string | LN4 property name. Must not be blank.          |
| `input`    | string | Name of the supplying input or variable. Must not be blank. |

A binding may reference an input that is not present in `entry_inputs`. This means the value
is assigned during execution (not at entry). This is a **warning**, not an error.
The binding is preserved; no null value is invented.

---

### `runtime_values`

Values calculated or assigned during execution, not observed at entry.

```json
{
  "name": "MY_VAR",
  "value": 42,
  "type": "integer",
  "source": "source_code",
  "status": "derived",
  "evidence": "GLB_M_COMPUTE line 47",
  "expression": "P_X + P_Y"
}
```

`evidence` and `expression` are optional. The legacy adapter does not populate this section
automatically. No runtime values are invented from unresolved bindings.

---

### `flags`

Boolean or scalar values manually determined by the analyser.

```json
{
  "name": "GLB_CK_CAMB_EMPRESA",
  "value": false,
  "type": "boolean",
  "source": "manual_derivation",
  "status": "derived"
}
```

Names must be unique within the list.

---

### `configuration`

System or process configuration parameters, separate from runtime or input values.

Structure is the same as `entry_inputs`. The legacy adapter leaves this section empty.
Names must be unique within the list.

---

### `analysis_scope`

The set of LN4 methods manually selected for analysis.

```json
{
  "methods": [
    {
      "name": "GLB_M_PC_EXE",
      "source": "manual_derivation",
      "status": "derived",
      "reason": null
    }
  ]
}
```

Method names must not be blank. `reason` is optional and is not invented by the adapter.

---

### `notes`

Free-text notes from the analyser, preserved literally.

```json
["Proceso de cambio de jornada para tienda."]
```

Notes are not interpreted as facts, flags, or decisions.

---

### `source_files`

References to the artefacts from which the scenario was built.

```json
{
  "legacy_file": "tests/fixtures/scenarios/legacy_peoplenet_call.json",
  "original_call": null,
  "hash": null,
  "source_type": "legacy_peoplenet_call"
}
```

---

## Optional Field Serialization Policy

All fields defined by this schema are always present in the serialized JSON output,
regardless of whether a value was supplied.

- **Optional scalar fields** with no value are serialized as `null`. They are never omitted
  from the output. Examples: `RuntimeValue.evidence`, `RuntimeValue.expression`,
  `ScopeMethod.reason`, `source_files.original_call`, `source_files.hash`.
- **Optional collection fields** with no elements are serialized as empty arrays (`[]`) or
  empty objects (`{}`), never as `null`. Examples: `runtime_values`, `configuration`,
  `analysis_scope.methods`, `notes`, `entry_inputs`, `property_bindings`, `flags`.

Consumers can rely on every schema key being present. Key-presence checks are unnecessary.

This policy is consistent across all sections and is verified by the golden fixture
(`tests/fixtures/scenarios/expected_scenario_v1.json`).

---

## Catalogues

### Source (provenance)

| Value               | Meaning                                              |
|---------------------|------------------------------------------------------|
| `frontend_call`     | Observed in a captured HTTP call from the browser.   |
| `sql_query`         | Extracted from a SQL query or result.                |
| `database_trace`    | Obtained from a database execution trace.            |
| `source_code`       | Read directly from LN4 source code.                  |
| `manual_derivation` | Determined by the analyser without direct evidence.  |
| `default`           | Assigned as a system default value.                  |
| `unknown`           | Provenance could not be determined.                  |

### Status (certainty)

| Value            | Meaning                                              |
|------------------|------------------------------------------------------|
| `observed`       | Directly observed in a captured artefact.            |
| `derived`        | Inferred from evidence, not directly observed.       |
| `assumed`        | Assumed without evidence; may need verification.     |
| `unknown`        | Certainty could not be determined.                   |
| `not_applicable` | The concept does not apply to this element.          |

Only values in these catalogues are accepted. Arbitrary strings are validation errors.

---

## Validation Rules

1. `schema_version` must be `"1.0"`.
2. `scenario_id` must not be blank.
3. `process.id` must not be blank.
4. `entry_point.meta4object` must not be blank.
5. `entry_point.node` must not be blank.
6. `entry_point.method` must not be blank.
7. `entry_inputs` names must be unique.
8. `flags` names must be unique.
9. `runtime_values` names must be unique.
10. `configuration` names must be unique.
11. All `source` values must be from the Source catalogue.
12. All `status` values must be from the Status catalogue.
13. `property_bindings` elements must have non-blank `property` and `input`.
14. `analysis_scope.methods` names must not be blank.
15. Legacy blocks (`inputs`, `flags`, etc.) must be the expected JSON type.
16. The legacy file must be syntactically valid JSON.
17. If `entry_inputs` contains `P_ID_FLUJO`, its value must match `process.id`. This is a blocking error.
18. A binding referencing an input not present in `entry_inputs` is a **warning**, not an error.

---

## Bindings to Non-Observed Inputs

A property binding may reference an input such as `P_14` that does not appear in
`entry_inputs`. This is expected: the value may be assigned internally during execution,
obtained from another source, or calculated.

The adapter:
- preserves the binding;
- emits a `binding_input_not_observed` warning;
- does **not** create a `P_14 = null` entry in `entry_inputs` or `runtime_values`;
- does **not** invent a runtime value.

---

## Collection Ordering

All arrays in a scenario document (`entry_inputs`, `property_bindings`, `runtime_values`,
`flags`, `configuration`, `analysis_scope.methods`, `notes`) preserve **insertion order**
as encountered in the source material.

When migrating from a legacy `peoplenet_call.json`, the order of items within each
section follows the order of keys or elements in the original file. Python's `json.loads`
preserves JSON object key order and list element order, and the adapter does not sort or
reorder items.

Consequences:

- **Same input → same output order.** Given identical source text, the adapter always
  produces identical output (deterministic per input).
- **Reordered input → different output order.** Two legacy files that are semantically
  equivalent but whose keys appear in a different order will produce scenario files with
  elements in a different order. There is no normalisation step.
- **Canonical ordering is out of scope.** Alphabetical or semantic sorting of collection
  elements is not a goal of this contract version. If stable ordering across sources is
  required, it must be handled at a higher layer.

---

## Legacy Compatibility

The legacy `peoplenet_call.json` format maps as follows:

| Legacy field   | scenario-v1 location              | Default applied                |
|----------------|-----------------------------------|--------------------------------|
| `meta4object`  | `entry_point.meta4object`         | —                              |
| `nodo`         | `entry_point.node`                | —                              |
| `metodo`       | `entry_point.method` + `arguments`| parsed; original kept on error |
| `proceso`      | `process.id`                      | `source=manual_derivation`, `status=derived` |
| `inputs`       | `entry_inputs`                    | `source=frontend_call`, `status=observed`    |
| `propiedades`  | `property_bindings`               | —                              |
| `flags`        | `flags`                           | `source=manual_derivation`, `status=derived` |
| `metodos`      | `analysis_scope.methods`          | `source=manual_derivation`, `status=derived` |
| `notas`        | `notes`                           | —                              |

Unknown legacy fields are reported in the migration report but are not silently discarded.
