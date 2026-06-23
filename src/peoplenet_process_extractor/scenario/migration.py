import re
from dataclasses import dataclass, field
from typing import Any

from .enums import Source, Status
from .models import (
    AnalysisScope,
    EntryPoint,
    Process,
    PropertyBinding,
    Scenario,
    ScopeMethod,
    SourceRef,
    TypedValue,
)
from .parsing import parse_entry_method


@dataclass
class DefaultApplied:
    field: str
    value: str


@dataclass
class MigrationWarning:
    code: str
    message: str


@dataclass
class MigrationError:
    code: str
    message: str


@dataclass
class MigrationReport:
    migrated_fields: list[str] = field(default_factory=list)
    defaults_applied: list[DefaultApplied] = field(default_factory=list)
    warnings: list[MigrationWarning] = field(default_factory=list)
    unknown_legacy_fields: list[str] = field(default_factory=list)
    errors: list[MigrationError] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


_KNOWN_LEGACY_FIELDS = {
    "meta4object",
    "nodo",
    "metodo",
    "proceso",
    "inputs",
    "propiedades",
    "flags",
    "metodos",
    "notas",
}

_SCENARIO_ID_RE = re.compile(r"[^a-z0-9]+")


def derive_scenario_id(process_id: str) -> str:
    """Lowercase process_id and replace non-alphanumeric runs with '-'."""
    return _SCENARIO_ID_RE.sub("-", process_id.lower()).strip("-")


def _json_type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def migrate_from_legacy(
    legacy: dict[str, Any],
    *,
    scenario_id: str | None = None,
    legacy_file: str | None = None,
) -> tuple[Scenario, MigrationReport]:
    """Adapt a legacy peoplenet_call dict to a Scenario and a MigrationReport."""
    report = MigrationReport()

    for key in legacy:
        if key not in _KNOWN_LEGACY_FIELDS:
            report.unknown_legacy_fields.append(key)
            report.warnings.append(
                MigrationWarning(
                    code="unknown_legacy_field",
                    message=f"Unknown legacy field {key!r} was not migrated into the scenario",
                )
            )

    # --- process ---
    raw_proceso = legacy.get("proceso", "")
    if not isinstance(raw_proceso, str):
        report.errors.append(
            MigrationError(
                code="invalid_type",
                message=f"'proceso' must be a string, got {type(raw_proceso).__name__}",
            )
        )
        raw_proceso = ""

    process = Process(id=raw_proceso, source=Source.MANUAL_DERIVATION, status=Status.DERIVED)
    report.migrated_fields.append("proceso")
    report.defaults_applied += [
        DefaultApplied("process.source", "manual_derivation"),
        DefaultApplied("process.status", "derived"),
    ]
    report.decisions.append(
        "process.source set to 'manual_derivation' and process.status set to 'derived' "
        "because the legacy format does not distinguish observed from derived process IDs"
    )

    # --- entry_point ---
    raw_meta4object = legacy.get("meta4object", "")
    raw_nodo = legacy.get("nodo", "")
    raw_metodo = legacy.get("metodo", "")

    for field_name, value in [
        ("meta4object", raw_meta4object),
        ("nodo", raw_nodo),
        ("metodo", raw_metodo),
    ]:
        if not isinstance(value, str):
            report.errors.append(
                MigrationError(
                    code="invalid_type",
                    message=f"'{field_name}' must be a string, got {type(value).__name__}",
                )
            )

    raw_meta4object = raw_meta4object if isinstance(raw_meta4object, str) else ""
    raw_nodo = raw_nodo if isinstance(raw_nodo, str) else ""
    raw_metodo = raw_metodo if isinstance(raw_metodo, str) else ""

    entry_method = ""
    entry_args: list[Any] = []
    if raw_metodo:
        try:
            entry_method, entry_args = parse_entry_method(raw_metodo)
        except ValueError as exc:
            report.warnings.append(
                MigrationWarning(
                    code="unparseable_entry_method",
                    message=(
                        f"Could not parse entry method {raw_metodo!r}: {exc}. "
                        "Original value preserved in entry_point.method."
                    ),
                )
            )
            entry_method = raw_metodo

    entry_point = EntryPoint(
        meta4object=raw_meta4object,
        node=raw_nodo,
        method=entry_method,
        arguments=entry_args,
    )
    report.migrated_fields += ["meta4object", "nodo", "metodo"]

    # --- entry_inputs ---
    raw_inputs = legacy.get("inputs", {})
    if not isinstance(raw_inputs, dict):
        report.errors.append(
            MigrationError(
                code="invalid_type",
                message=f"'inputs' must be a dict, got {type(raw_inputs).__name__}",
            )
        )
        raw_inputs = {}

    entry_inputs: list[TypedValue] = [
        TypedValue(
            name=name,
            value=value,
            type=_json_type_name(value),
            source=Source.FRONTEND_CALL,
            status=Status.OBSERVED,
        )
        for name, value in raw_inputs.items()
    ]
    report.migrated_fields.append("inputs")
    if raw_inputs:
        report.defaults_applied += [
            DefaultApplied("entry_inputs.*.source", "frontend_call"),
            DefaultApplied("entry_inputs.*.status", "observed"),
        ]

    # --- property_bindings ---
    raw_propiedades = legacy.get("propiedades", [])
    if not isinstance(raw_propiedades, list):
        report.errors.append(
            MigrationError(
                code="invalid_type",
                message=f"'propiedades' must be a list, got {type(raw_propiedades).__name__}",
            )
        )
        raw_propiedades = []

    observed_names = {inp.name for inp in entry_inputs}
    property_bindings: list[PropertyBinding] = []
    for item in raw_propiedades:
        if not isinstance(item, dict):
            report.warnings.append(
                MigrationWarning(
                    code="invalid_binding_item",
                    message=f"Property binding item is not a dict: {item!r}",
                )
            )
            continue
        prop = item.get("propiedad", "")
        inp_name = item.get("input", "")
        if inp_name and inp_name not in observed_names:
            report.warnings.append(
                MigrationWarning(
                    code="binding_input_not_observed",
                    message=(
                        f"{inp_name!r} is referenced by a property binding on {prop!r} "
                        "but is not present in entry_inputs. "
                        "Binding preserved; no null value has been created."
                    ),
                )
            )
        property_bindings.append(PropertyBinding(property=prop, input=inp_name))
    report.migrated_fields.append("propiedades")

    # --- flags ---
    raw_flags = legacy.get("flags", {})
    if not isinstance(raw_flags, dict):
        report.errors.append(
            MigrationError(
                code="invalid_type",
                message=f"'flags' must be a dict, got {type(raw_flags).__name__}",
            )
        )
        raw_flags = {}

    flags: list[TypedValue] = [
        TypedValue(
            name=name,
            value=value,
            type=_json_type_name(value),
            source=Source.MANUAL_DERIVATION,
            status=Status.DERIVED,
        )
        for name, value in raw_flags.items()
    ]
    report.migrated_fields.append("flags")
    if raw_flags:
        report.defaults_applied += [
            DefaultApplied("flags.*.source", "manual_derivation"),
            DefaultApplied("flags.*.status", "derived"),
        ]
        report.decisions.append(
            "flags.source set to 'manual_derivation' and flags.status set to 'derived' "
            "because legacy flags were manually set or corrected outside the frontend call"
        )

    # --- analysis_scope.methods ---
    raw_metodos = legacy.get("metodos", [])
    if not isinstance(raw_metodos, list):
        report.errors.append(
            MigrationError(
                code="invalid_type",
                message=f"'metodos' must be a list, got {type(raw_metodos).__name__}",
            )
        )
        raw_metodos = []

    scope_methods: list[ScopeMethod] = []
    for item in raw_metodos:
        if not isinstance(item, str):
            report.warnings.append(
                MigrationWarning(
                    code="invalid_method_item",
                    message=f"Item in 'metodos' is not a string: {item!r}",
                )
            )
            continue
        scope_methods.append(
            ScopeMethod(name=item, source=Source.MANUAL_DERIVATION, status=Status.DERIVED)
        )
    report.migrated_fields.append("metodos")
    if raw_metodos:
        report.defaults_applied += [
            DefaultApplied("analysis_scope.methods.*.source", "manual_derivation"),
            DefaultApplied("analysis_scope.methods.*.status", "derived"),
        ]

    # --- notes ---
    raw_notas = legacy.get("notas", [])
    if not isinstance(raw_notas, list):
        report.errors.append(
            MigrationError(
                code="invalid_type",
                message=f"'notas' must be a list, got {type(raw_notas).__name__}",
            )
        )
        raw_notas = []

    notes: list[str] = []
    for item in raw_notas:
        if not isinstance(item, str):
            report.warnings.append(
                MigrationWarning(
                    code="invalid_note_item",
                    message=f"Note item is not a string: {item!r}",
                )
            )
        else:
            notes.append(item)
    report.migrated_fields.append("notas")

    # --- scenario_id ---
    if scenario_id is None:
        scenario_id = derive_scenario_id(process.id) if process.id else "unknown"
        report.decisions.append(
            f"scenario_id derived from process.id {process.id!r} as {scenario_id!r} "
            "(rule: lowercase, non-alphanumeric runs replaced by '-')"
        )

    # --- P_ID_FLUJO coherence check ---
    # Record the contradiction here; the blocking error is raised by validate().
    for inp in entry_inputs:
        if inp.name == "P_ID_FLUJO" and str(inp.value) != process.id:
            report.contradictions.append(
                f"process.id={process.id!r} != P_ID_FLUJO={inp.value!r}"
            )

    scenario = Scenario(
        schema_version="1.0",
        scenario_id=scenario_id,
        process=process,
        entry_point=entry_point,
        entry_inputs=entry_inputs,
        property_bindings=property_bindings,
        runtime_values=[],
        flags=flags,
        configuration=[],
        analysis_scope=AnalysisScope(methods=scope_methods),
        notes=notes,
        source_files=SourceRef(
            legacy_file=legacy_file,
            source_type="legacy_peoplenet_call",
        ),
    )

    return scenario, report
