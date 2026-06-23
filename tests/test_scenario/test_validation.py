from peoplenet_process_extractor.scenario.enums import Source, Status
from peoplenet_process_extractor.scenario.models import (
    AnalysisScope,
    EntryPoint,
    Process,
    PropertyBinding,
    RuntimeValue,
    Scenario,
    ScopeMethod,
    TypedValue,
)
from peoplenet_process_extractor.scenario.validation import validate


def _minimal(**overrides) -> Scenario:
    defaults = dict(
        schema_version="1.0",
        scenario_id="test-scenario",
        process=Process(id="MY_PROC", source=Source.MANUAL_DERIVATION, status=Status.DERIVED),
        entry_point=EntryPoint(
            meta4object="OBJ",
            node="NODE",
            method="METHOD",
            arguments=[],
        ),
    )
    defaults.update(overrides)
    return Scenario(**defaults)


def _codes(scenario: Scenario) -> list[str]:
    return [e.code for e in validate(scenario)]


def test_valid_scenario_no_errors():
    assert _codes(_minimal()) == []


def test_unsupported_schema_version():
    s = _minimal(schema_version="2.0")
    assert "unsupported_schema_version" in _codes(s)


def test_empty_scenario_id():
    s = _minimal(scenario_id="")
    assert "empty_scenario_id" in _codes(s)


def test_whitespace_scenario_id():
    s = _minimal(scenario_id="   ")
    assert "empty_scenario_id" in _codes(s)


def test_empty_process_id():
    s = _minimal(
        process=Process(id="", source=Source.MANUAL_DERIVATION, status=Status.DERIVED)
    )
    assert "empty_process_id" in _codes(s)


# ---------------------------------------------------------------------------
# process.source / process.status catalog validation (Fix 1)
# ---------------------------------------------------------------------------


def test_invalid_process_source():
    s = _minimal(
        process=Process(id="MY_PROC", source="not_a_valid_source", status=Status.DERIVED)
    )
    assert "invalid_source" in _codes(s)


def test_invalid_process_status():
    s = _minimal(
        process=Process(id="MY_PROC", source=Source.MANUAL_DERIVATION, status="not_a_valid_status")
    )
    assert "invalid_status" in _codes(s)


def test_valid_process_source_not_flagged():
    s = _minimal(
        process=Process(id="MY_PROC", source=Source.MANUAL_DERIVATION, status=Status.DERIVED)
    )
    assert "invalid_source" not in _codes(s)
    assert "invalid_status" not in _codes(s)


# ---------------------------------------------------------------------------
# entry_point validation
# ---------------------------------------------------------------------------


def test_empty_entry_meta4object():
    s = _minimal(
        entry_point=EntryPoint(meta4object="", node="N", method="M", arguments=[])
    )
    assert "empty_entry_meta4object" in _codes(s)


def test_empty_entry_node():
    s = _minimal(
        entry_point=EntryPoint(meta4object="OBJ", node="", method="M", arguments=[])
    )
    assert "empty_entry_node" in _codes(s)


def test_empty_entry_method():
    s = _minimal(
        entry_point=EntryPoint(meta4object="OBJ", node="N", method="", arguments=[])
    )
    assert "empty_entry_method" in _codes(s)


# ---------------------------------------------------------------------------
# duplicate name checks
# ---------------------------------------------------------------------------


def test_duplicate_entry_input_name():
    tv = TypedValue(name="P_FOO", value="x", type="string",
                    source=Source.FRONTEND_CALL, status=Status.OBSERVED)
    s = _minimal(entry_inputs=[tv, tv])
    assert "duplicate_entry_inputs_name" in _codes(s)


def test_duplicate_flag_name():
    flag = TypedValue(name="MY_FLAG", value=True, type="boolean",
                      source=Source.MANUAL_DERIVATION, status=Status.DERIVED)
    s = _minimal(flags=[flag, flag])
    assert "duplicate_flags_name" in _codes(s)


def test_duplicate_runtime_value_name():
    rv = RuntimeValue(name="VAL", value=1, type="integer",
                      source=Source.SOURCE_CODE, status=Status.DERIVED)
    s = _minimal(runtime_values=[rv, rv])
    assert "duplicate_runtime_values_name" in _codes(s)


def test_duplicate_configuration_name():
    cfg = TypedValue(name="CONF", value="x", type="string",
                     source=Source.DEFAULT, status=Status.ASSUMED)
    s = _minimal(configuration=[cfg, cfg])
    assert "duplicate_configuration_name" in _codes(s)


# ---------------------------------------------------------------------------
# collection source / status catalog checks
# ---------------------------------------------------------------------------


def test_invalid_source_in_entry_inputs():
    tv = TypedValue(name="P_FOO", value="x", type="string",
                    source="not_a_valid_source", status=Status.OBSERVED)
    s = _minimal(entry_inputs=[tv])
    assert "invalid_source" in _codes(s)


def test_invalid_status_in_entry_inputs():
    tv = TypedValue(name="P_FOO", value="x", type="string",
                    source=Source.FRONTEND_CALL, status="not_a_valid_status")
    s = _minimal(entry_inputs=[tv])
    assert "invalid_status" in _codes(s)


# ---------------------------------------------------------------------------
# analysis_scope.methods source / status catalog checks (Fix 1)
# ---------------------------------------------------------------------------


def test_invalid_scope_method_source():
    m = ScopeMethod(name="MY_METHOD", source="bad_source", status=Status.DERIVED)
    s = _minimal(analysis_scope=AnalysisScope(methods=[m]))
    assert "invalid_source" in _codes(s)


def test_invalid_scope_method_status():
    m = ScopeMethod(name="MY_METHOD", source=Source.MANUAL_DERIVATION, status="bad_status")
    s = _minimal(analysis_scope=AnalysisScope(methods=[m]))
    assert "invalid_status" in _codes(s)


def test_valid_scope_method_not_flagged():
    m = ScopeMethod(name="MY_METHOD", source=Source.MANUAL_DERIVATION, status=Status.DERIVED)
    s = _minimal(analysis_scope=AnalysisScope(methods=[m]))
    assert "invalid_source" not in _codes(s)
    assert "invalid_status" not in _codes(s)


# ---------------------------------------------------------------------------
# binding validation
# ---------------------------------------------------------------------------


def test_empty_binding_property():
    b = PropertyBinding(property="", input="P_FOO")
    s = _minimal(property_bindings=[b])
    assert "empty_binding_property" in _codes(s)


def test_empty_binding_input():
    b = PropertyBinding(property="PROP", input="")
    s = _minimal(property_bindings=[b])
    assert "empty_binding_input" in _codes(s)


def test_empty_scope_method_name():
    m = ScopeMethod(name="", source=Source.MANUAL_DERIVATION, status=Status.DERIVED)
    s = _minimal(analysis_scope=AnalysisScope(methods=[m]))
    assert "empty_scope_method_name" in _codes(s)


# ---------------------------------------------------------------------------
# P_ID_FLUJO coherence
# ---------------------------------------------------------------------------


def test_process_id_mismatch_p_id_flujo():
    tv = TypedValue(
        name="P_ID_FLUJO",
        value="DIFFERENT",
        type="string",
        source=Source.FRONTEND_CALL,
        status=Status.OBSERVED,
    )
    s = _minimal(
        process=Process(id="MY_PROC", source=Source.MANUAL_DERIVATION, status=Status.DERIVED),
        entry_inputs=[tv],
    )
    assert "process_id_mismatch" in _codes(s)


def test_no_error_when_p_id_flujo_matches():
    tv = TypedValue(
        name="P_ID_FLUJO",
        value="MY_PROC",
        type="string",
        source=Source.FRONTEND_CALL,
        status=Status.OBSERVED,
    )
    s = _minimal(
        process=Process(id="MY_PROC", source=Source.MANUAL_DERIVATION, status=Status.DERIVED),
        entry_inputs=[tv],
    )
    assert "process_id_mismatch" not in _codes(s)


def test_binding_to_unobserved_input_is_not_an_error():
    b = PropertyBinding(property="PROP", input="P_UNOBSERVED")
    s = _minimal(property_bindings=[b])
    assert _codes(s) == []
