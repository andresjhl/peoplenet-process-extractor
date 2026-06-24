# LN4 Call Resolution

This document describes the planned model for statically resolving `Call(...)` expressions
in LN4 source files. It captures confirmed rules, known ambiguities, and the intended
incremental approach for INC-0007 and INC-0008.

This document does **not** describe a completed implementation. It describes the intended
design as of INC-0006 close. Nothing here should be read as "already implemented".

Related documents:
- [PeopleNet structural model](peoplenet-structural-model.md)
- [Corpus layout](corpus-layout.md)
- [structural-index-v1 schema](../schemas/structural-index-v1.md)
- [ADR-0006 — Manifest as single source of inventory](../decisions/ADR-0006-manifest-single-source.md)
- [ADR-0007 — Keep Meta4Object node index separate](../decisions/ADR-0007-m4object-node-index-separate.md)
- [INC-0005 — Reference extraction v1](../increments/INC-0005-reference-extraction-v1.md)

---

## Epistemological classification

Statements in this document are classified as:
**observed**, **derived**, **inferred**, **ambiguous**, **unresolved**.

See [peoplenet-structural-model.md](peoplenet-structural-model.md#epistemological-classification).

---

## Conceptual resolution chain

The following chain describes, at a conceptual level, how a `Call(...)` expression should
be resolved to a physical LN4 rule file:

```
Call(...)
  │
  │  1. identify the ID_T3 of the caller's Meta4Object
  ▼
  active Meta4Object context (ID_T3)
  │
  │  2. interpret the node reference argument
  ▼
  candidate node reference (literal or expression)
  │
  │  3. search for the node: own nodes, inherited nodes, aliases
  ▼
  ID_NODE  (logical node identifier)
  │
  │  4. resolve ID_NODE → ID_TI via M4RCH_NODES (or alias table)
  ▼
  ID_TI  (node structure identifier)
  │
  │  5. locate NODE STRUCTURE/<ID_TI>/ITEM/<TYPE>/<NAME>/
  ▼
  structural element  (item_type + item_name)
  │
  │  6. identify the applicable rule among RULES/<rule>.ln4
  ▼
  target LN4 rule file
```

---

## Confirmed rules

The following rules are **observed** in the current pipeline and must be respected by
any future resolver:

### Rule 1 — Do not compare `Call` arguments directly to `structural_elements.meta4object`

**Status: observed**

The first argument of `Call(...)` in LN4 is (when a string literal) a reference to a node
by its *logical identifier*. That identifier belongs to the domain of `ID_NODE`.

The column `structural_elements.meta4object` contains an `ID_TI` (node structure identifier),
not an `ID_NODE`. Comparing the call argument directly against this column would be incorrect.

The correct approach is:
1. Resolve the call argument to an `ID_NODE`.
2. Look up `ID_NODE → ID_TI` in the node index.
3. Then match `ID_TI` against `structural_elements.meta4object`.

### Rule 2 — `structural_elements.meta4object` contains `ID_TI`, not `ID_T3`

**Status: observed** (in the path parser and structural index implementation)

Despite its name, `structural_elements.meta4object` holds the value extracted from
`NODE STRUCTURE/<ID_TI>/...` — that is, the node structure identifier.
It does not hold the Meta4Object name (`ID_T3`).

See [structural-index-v1 — Known semantic naming debt](../schemas/structural-index-v1.md#known-semantic-naming-debt).

### Rule 3 — Resolving the target node and selecting an active rule are separate problems

**Status: derived**

Even once a `Call` argument is mapped to a specific structural element (`ID_TI` + `item_type`
+ `item_name`), choosing among multiple rules for that element (e.g. `R1`, `R2`) is a
distinct step governed by rule-validity logic not yet implemented.

Do not conflate "finding the target" with "selecting which rule applies".

### Rule 4 — Multiple rules may represent different temporal implementations of the same element

**Status: observed**

Multiple `.ln4` files can exist under `RULES/` for the same element (distinguished by `rule_id`
and `rule_date`). These represent historical or conditional implementations of the same
element, not alternative targets.

The `rule_id` and `rule_date` fields in `structural-index-v1` capture this. Rule selection
criteria are **unresolved**.

### Rule 5 — A `Call` argument may be a literal or a dynamic expression

**Status: observed**

The `reference-extraction-v1` artefact classifies `Call` arguments as:
`string_literal`, `numeric_literal`, `identifier`, `expression`, or `empty`.

Only `string_literal` arguments can be directly attempted for static resolution.
Arguments of kind `identifier` or `expression` depend on runtime state and must be
classified as **unresolvable statically**. They must not be invented or guessed.

### Rule 6 — Dynamic references must be left unresolved, not approximated

**Status: derived**

If a `Call` argument cannot be determined statically, the correct output is an explicit
"unresolved" status for that reference, not a best-effort guess.

Inventing a resolution for a dynamic reference would introduce incorrect data into the
pipeline, which downstream phases would inherit silently.

---

## Planned increments

### INC-0007 — Extract node, alias, and inheritance bindings

Scope:
- Read the JSON content of `m4o_node_json`, `m4o_alias_json`, and `m4o_mapping_json` files
  as inventoried by `corpus-manifest-v1`.
- Produce `m4object-node-index-v1`: a structured artefact recording, for each Meta4Object:
  - its own nodes (`ID_NODE → ID_TI`, `IS_ROOT`);
  - its alias table (`ALIAS → ID_NODE`, `ID_TI`, `ID_ALIAS_T3`);
  - its direct inheritance links (derived `ID_T3_I` → base `ID_T3`, from `SPR_DIN_OBJECTS`);

INC-0007 does **not** resolve `Call()` expressions. It only builds the lookup tables
needed for resolution.

### INC-0008 — Resolve node references and Call expressions (not yet designed)

Scope (provisional, subject to revision):
- Consume `reference-extraction-v1`, `structural-index-v1`, and `m4object-node-index-v1`.
- For each `Call(...)` with a resolvable argument, perform the resolution chain described
  above and produce a `call-resolution-v1` artefact.

**INC-0008 is not designed in this document.** Its scope and schema are deferred until
`m4object-node-index-v1` is available and the open questions below are resolved.

---

## Open ambiguities

The following questions must be answered before a complete resolver can be implemented.
They are listed here so that INC-0007 can gather evidence rather than assume answers.

| Question | Status |
|----------|--------|
| When a node exists in the own model AND in a base model AND via an alias, which takes precedence? | unresolved |
| Is inheritance transitive? (base of a base of a base) | unresolved |
| Can aliases chain? (alias A → alias B → ID_NODE) | unresolved |
| When a `Call` argument is an LN4 variable (not a literal), is any static resolution possible? | unresolved |
| Which rule is "active" when multiple rules exist for the same element? | unresolved |
| Can a single `Call` expression legitimately resolve to more than one target element? | ambiguous |
| Are `ID_NODE` values globally unique across all Meta4Objects, or only per `ID_T3`? | unresolved |
| Does inheritance grant access to the full node structure or only selected elements? | unresolved |
| What happens when a node from a base is overridden in a derived Meta4Object? | unresolved |

---

## What this document does not claim

- Aliases are not yet resolved by the pipeline.
- The inheritance graph is not yet constructed.
- `Call()` expressions are not yet resolved by the pipeline.
- Transitive inheritance is not confirmed to exist.
- The exact schema of `M4RCH_NODES`, `M4RCH_T3_ALIAS_RES`, and `SPR_DIN_OBJECTS` records
  is not yet validated against real JSON content.
