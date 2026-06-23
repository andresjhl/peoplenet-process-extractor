from dataclasses import dataclass

from .enums import Source, Status
from .models import SUPPORTED_SCHEMA_VERSIONS, Scenario


@dataclass
class ValidationError:
    code: str
    message: str
    field: str | None = None


def validate(scenario: Scenario) -> list[ValidationError]:
    errors: list[ValidationError] = []

    if scenario.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            ValidationError(
                code="unsupported_schema_version",
                message=(
                    f"schema_version {scenario.schema_version!r} is not supported. "
                    f"Supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
                ),
                field="schema_version",
            )
        )

    if not scenario.scenario_id.strip():
        errors.append(
            ValidationError(
                code="empty_scenario_id",
                message="scenario_id must not be empty",
                field="scenario_id",
            )
        )

    if not scenario.process.id.strip():
        errors.append(
            ValidationError(
                code="empty_process_id",
                message="process.id must not be empty",
                field="process.id",
            )
        )

    _check_catalog("process.source", scenario.process.source, errors)
    _check_catalog("process.status", scenario.process.status, errors, kind="status")

    if not scenario.entry_point.meta4object.strip():
        errors.append(
            ValidationError(
                code="empty_entry_meta4object",
                message="entry_point.meta4object must not be empty",
                field="entry_point.meta4object",
            )
        )

    if not scenario.entry_point.node.strip():
        errors.append(
            ValidationError(
                code="empty_entry_node",
                message="entry_point.node must not be empty",
                field="entry_point.node",
            )
        )

    if not scenario.entry_point.method.strip():
        errors.append(
            ValidationError(
                code="empty_entry_method",
                message="entry_point.method must not be empty",
                field="entry_point.method",
            )
        )

    _check_name_duplicates(scenario.entry_inputs, "entry_inputs", errors)
    _check_name_duplicates(scenario.flags, "flags", errors)
    _check_name_duplicates(scenario.runtime_values, "runtime_values", errors)
    _check_name_duplicates(scenario.configuration, "configuration", errors)

    for collection_name, collection in [
        ("entry_inputs", scenario.entry_inputs),
        ("flags", scenario.flags),
        ("runtime_values", scenario.runtime_values),
        ("configuration", scenario.configuration),
    ]:
        for item in collection:
            _check_catalog(
                f"{collection_name}.{item.name}.source", item.source, errors
            )
            _check_catalog(
                f"{collection_name}.{item.name}.status", item.status, errors, kind="status"
            )

    for i, binding in enumerate(scenario.property_bindings):
        if not binding.property.strip():
            errors.append(
                ValidationError(
                    code="empty_binding_property",
                    message=f"property_bindings[{i}].property must not be empty",
                    field=f"property_bindings[{i}].property",
                )
            )
        if not binding.input.strip():
            errors.append(
                ValidationError(
                    code="empty_binding_input",
                    message=f"property_bindings[{i}].input must not be empty",
                    field=f"property_bindings[{i}].input",
                )
            )

    for i, method in enumerate(scenario.analysis_scope.methods):
        if not method.name.strip():
            errors.append(
                ValidationError(
                    code="empty_scope_method_name",
                    message=f"analysis_scope.methods[{i}].name must not be empty",
                    field=f"analysis_scope.methods[{i}].name",
                )
            )
        _check_catalog(
            f"analysis_scope.methods[{i}].source", method.source, errors
        )
        _check_catalog(
            f"analysis_scope.methods[{i}].status", method.status, errors, kind="status"
        )

    for inp in scenario.entry_inputs:
        if inp.name == "P_ID_FLUJO" and str(inp.value) != scenario.process.id:
            errors.append(
                ValidationError(
                    code="process_id_mismatch",
                    message=(
                        f"entry_inputs.P_ID_FLUJO={inp.value!r} does not match "
                        f"process.id={scenario.process.id!r}"
                    ),
                    field="process.id",
                )
            )

    return errors


def _check_catalog(
    field_path: str,
    value: object,
    errors: list[ValidationError],
    *,
    kind: str = "source",
) -> None:
    cls = Source if kind == "source" else Status
    code = "invalid_source" if kind == "source" else "invalid_status"
    label = "Source" if kind == "source" else "Status"
    try:
        cls(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        errors.append(
            ValidationError(
                code=code,
                message=f"{field_path} {value!r} is not a valid {label}",
                field=field_path,
            )
        )


def _check_name_duplicates(
    collection: list,
    collection_name: str,
    errors: list[ValidationError],
) -> None:
    seen: set[str] = set()
    for item in collection:
        if item.name in seen:
            errors.append(
                ValidationError(
                    code=f"duplicate_{collection_name}_name",
                    message=f"Duplicate name {item.name!r} in {collection_name}",
                    field=collection_name,
                )
            )
        seen.add(item.name)
