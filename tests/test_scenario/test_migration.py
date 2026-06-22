import json
from pathlib import Path


from peoplenet_process_extractor.scenario.enums import Source, Status
from peoplenet_process_extractor.scenario.migration import (
    MigrationReport,
    derive_scenario_id,
    migrate_from_legacy,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "scenarios"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# derive_scenario_id
# ---------------------------------------------------------------------------


def test_derive_scenario_id_underscores():
    assert derive_scenario_id("11_JORN_STORE_U") == "11-jorn-store-u"


def test_derive_scenario_id_already_clean():
    assert derive_scenario_id("myprocess") == "myprocess"


def test_derive_scenario_id_spaces():
    assert derive_scenario_id("MY PROCESS") == "my-process"


# ---------------------------------------------------------------------------
# process migration
# ---------------------------------------------------------------------------


def test_process_id_migrated():
    legacy = _load("legacy_peoplenet_call.json")
    scenario, _ = migrate_from_legacy(legacy)
    assert scenario.process.id == "11_JORN_STORE_U"


def test_process_source_default():
    scenario, _ = migrate_from_legacy({"proceso": "FOO"})
    assert scenario.process.source == Source.MANUAL_DERIVATION


def test_process_status_default():
    scenario, _ = migrate_from_legacy({"proceso": "FOO"})
    assert scenario.process.status == Status.DERIVED


def test_process_default_in_report():
    _, report = migrate_from_legacy({"proceso": "FOO"})
    fields = [d.field for d in report.defaults_applied]
    assert "process.source" in fields
    assert "process.status" in fields


# ---------------------------------------------------------------------------
# entry_point
# ---------------------------------------------------------------------------


def test_entry_point_fields():
    legacy = _load("legacy_peoplenet_call.json")
    scenario, _ = migrate_from_legacy(legacy)
    ep = scenario.entry_point
    assert ep.meta4object == "GLB_11_G_PA_PC_V1"
    assert ep.node == "GLB_G_PA_PC"
    assert ep.method == "GLB_M_PC_EXE"
    assert ep.arguments == ["STEP_SAVE"]


def test_entry_point_fields_in_migrated_list():
    _, report = migrate_from_legacy(_load("legacy_peoplenet_call.json"))
    assert "meta4object" in report.migrated_fields
    assert "nodo" in report.migrated_fields
    assert "metodo" in report.migrated_fields


# ---------------------------------------------------------------------------
# entry_inputs
# ---------------------------------------------------------------------------


def test_inputs_migrated():
    legacy = _load("legacy_peoplenet_call.json")
    scenario, _ = migrate_from_legacy(legacy)
    names = [i.name for i in scenario.entry_inputs]
    assert "P_ID_FLUJO" in names
    assert "P_DATE" in names
    assert "P_NUM_STORE" in names
    assert "P_ACTIVE" in names


def test_input_source_and_status():
    scenario, _ = migrate_from_legacy({"proceso": "X", "inputs": {"P_FOO": "bar"}})
    inp = scenario.entry_inputs[0]
    assert inp.source == Source.FRONTEND_CALL
    assert inp.status == Status.OBSERVED


def test_input_types_preserved():
    legacy = _load("legacy_peoplenet_call.json")
    scenario, _ = migrate_from_legacy(legacy)
    by_name = {i.name: i for i in scenario.entry_inputs}
    assert by_name["P_ID_FLUJO"].type == "string"
    assert by_name["P_NUM_STORE"].type == "integer"
    assert by_name["P_ACTIVE"].type == "boolean"


def test_string_not_converted_to_number():
    scenario, _ = migrate_from_legacy({"proceso": "X", "inputs": {"P_NUM": "42"}})
    inp = next(i for i in scenario.entry_inputs if i.name == "P_NUM")
    assert inp.value == "42"
    assert inp.type == "string"


# ---------------------------------------------------------------------------
# property_bindings
# ---------------------------------------------------------------------------


def test_bindings_migrated():
    legacy = _load("legacy_peoplenet_call.json")
    scenario, _ = migrate_from_legacy(legacy)
    props = [b.property for b in scenario.property_bindings]
    assert "GLB_COND_HOR_SRZ" in props


def test_binding_to_unobserved_input_warning():
    legacy = _load("runtime_input_binding.json")
    _, report = migrate_from_legacy(legacy)
    codes = [w.code for w in report.warnings]
    assert "binding_input_not_observed" in codes


def test_binding_to_unobserved_input_no_null():
    legacy = _load("runtime_input_binding.json")
    scenario, _ = migrate_from_legacy(legacy)
    input_names = {i.name for i in scenario.entry_inputs}
    assert "P_14" not in input_names


def test_binding_preserved_when_input_absent():
    legacy = _load("runtime_input_binding.json")
    scenario, _ = migrate_from_legacy(legacy)
    props = [b.property for b in scenario.property_bindings]
    assert "GLB_COND_HOR_SRZ" in props


def test_binding_migration_is_valid():
    legacy = _load("runtime_input_binding.json")
    _, report = migrate_from_legacy(legacy)
    assert not report.has_errors


# ---------------------------------------------------------------------------
# flags
# ---------------------------------------------------------------------------


def test_flags_migrated():
    legacy = _load("legacy_peoplenet_call.json")
    scenario, _ = migrate_from_legacy(legacy)
    names = [f.name for f in scenario.flags]
    assert "GLB_CK_CAMB_EMPRESA" in names
    assert "GLB_CK_HOR_SRZ" in names


def test_flag_source_default():
    scenario, _ = migrate_from_legacy({"proceso": "X", "flags": {"MY_FLAG": True}})
    assert scenario.flags[0].source == Source.MANUAL_DERIVATION


def test_flag_status_default():
    scenario, _ = migrate_from_legacy({"proceso": "X", "flags": {"MY_FLAG": True}})
    assert scenario.flags[0].status == Status.DERIVED


def test_flag_defaults_in_report():
    _, report = migrate_from_legacy({"proceso": "X", "flags": {"F": False}})
    fields = [d.field for d in report.defaults_applied]
    assert "flags.*.source" in fields
    assert "flags.*.status" in fields


# ---------------------------------------------------------------------------
# analysis_scope.methods
# ---------------------------------------------------------------------------


def test_methods_migrated():
    legacy = _load("legacy_peoplenet_call.json")
    scenario, _ = migrate_from_legacy(legacy)
    names = [m.name for m in scenario.analysis_scope.methods]
    assert "GLB_M_PC_EXE" in names
    assert "GLB_M_PA_VAL_STORE" in names


def test_methods_source_status_defaults():
    scenario, _ = migrate_from_legacy({"proceso": "X", "metodos": ["MY_METHOD"]})
    m = scenario.analysis_scope.methods[0]
    assert m.source == Source.MANUAL_DERIVATION
    assert m.status == Status.DERIVED
    assert m.reason is None


# ---------------------------------------------------------------------------
# notes
# ---------------------------------------------------------------------------


def test_notes_preserved_literally():
    legacy = _load("legacy_peoplenet_call.json")
    scenario, _ = migrate_from_legacy(legacy)
    assert "Proceso de cambio de jornada para tienda." in scenario.notes


# ---------------------------------------------------------------------------
# unknown fields
# ---------------------------------------------------------------------------


def test_unknown_field_reported():
    _, report = migrate_from_legacy({"proceso": "X", "unknown_custom": "value"})
    assert "unknown_custom" in report.unknown_legacy_fields


def test_unknown_field_warning():
    _, report = migrate_from_legacy({"proceso": "X", "extra": 1})
    codes = [w.code for w in report.warnings]
    assert "unknown_legacy_field" in codes


# ---------------------------------------------------------------------------
# scenario_id
# ---------------------------------------------------------------------------


def test_scenario_id_derived_from_process():
    scenario, _ = migrate_from_legacy({"proceso": "11_JORN_STORE_U"})
    assert scenario.scenario_id == "11-jorn-store-u"


def test_scenario_id_override():
    scenario, _ = migrate_from_legacy({"proceso": "X"}, scenario_id="custom-id")
    assert scenario.scenario_id == "custom-id"


def test_scenario_id_derivation_recorded():
    _, report = migrate_from_legacy({"proceso": "MY_PROC"})
    decisions_text = " ".join(report.decisions)
    assert "scenario_id" in decisions_text


# ---------------------------------------------------------------------------
# report structure
# ---------------------------------------------------------------------------


def test_report_has_migrated_fields():
    _, report = migrate_from_legacy(_load("legacy_peoplenet_call.json"))
    for field in ["proceso", "meta4object", "nodo", "metodo", "inputs", "flags", "metodos", "notas"]:
        assert field in report.migrated_fields


def test_report_is_migration_report_instance():
    _, report = migrate_from_legacy({})
    assert isinstance(report, MigrationReport)


# ---------------------------------------------------------------------------
# invalid types in legacy blocks
# ---------------------------------------------------------------------------


def test_invalid_type_inputs_not_dict():
    _, report = migrate_from_legacy({"proceso": "X", "inputs": ["a", "b"]})
    codes = [e.code for e in report.errors]
    assert "invalid_type" in codes


def test_invalid_type_flags_not_dict():
    _, report = migrate_from_legacy({"proceso": "X", "flags": "yes"})
    codes = [e.code for e in report.errors]
    assert "invalid_type" in codes


def test_invalid_type_metodos_not_list():
    _, report = migrate_from_legacy({"proceso": "X", "metodos": "GLB_M"})
    codes = [e.code for e in report.errors]
    assert "invalid_type" in codes


# ---------------------------------------------------------------------------
# process_id mismatch (P_ID_FLUJO)
# ---------------------------------------------------------------------------


def test_process_mismatch_migration_not_blocking():
    # After Fix 2: migration itself does NOT raise process_id_mismatch as an error.
    # The error is owned exclusively by validate(). Migration only records a contradiction.
    legacy = _load("invalid_process_mismatch.json")
    _, report = migrate_from_legacy(legacy)
    assert not report.has_errors
    codes = [e.code for e in report.errors]
    assert "process_id_mismatch" not in codes


def test_process_mismatch_exactly_one_error_combined():
    # validate() is the sole authority: combining migrate_from_legacy + validate
    # must produce exactly one process_id_mismatch error, not two.
    from peoplenet_process_extractor.scenario.migration import MigrationError
    from peoplenet_process_extractor.scenario.validation import validate

    legacy = _load("invalid_process_mismatch.json")
    scenario, report = migrate_from_legacy(legacy)
    for verr in validate(scenario):
        report.errors.append(MigrationError(code=verr.code, message=verr.message))

    mismatch_count = sum(1 for e in report.errors if e.code == "process_id_mismatch")
    assert mismatch_count == 1


def test_process_mismatch_contradiction_recorded():
    legacy = _load("invalid_process_mismatch.json")
    _, report = migrate_from_legacy(legacy)
    assert report.contradictions
