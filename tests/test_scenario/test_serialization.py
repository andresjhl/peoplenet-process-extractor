import json
from pathlib import Path

from peoplenet_process_extractor.scenario.migration import migrate_from_legacy
from peoplenet_process_extractor.scenario.serialization import (
    deserialize_scenario,
    scenario_to_dict,
    serialize_scenario,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "scenarios"


def _load_legacy() -> dict:
    return json.loads(
        (FIXTURE_DIR / "legacy_peoplenet_call.json").read_text(encoding="utf-8")
    )


def test_round_trip_no_loss():
    legacy = _load_legacy()
    scenario, _ = migrate_from_legacy(legacy, legacy_file="tests/fixtures/scenarios/legacy_peoplenet_call.json")
    serialized = serialize_scenario(scenario)
    restored = deserialize_scenario(serialized)
    assert serialize_scenario(restored) == serialized


def test_round_trip_preserves_types():
    legacy = _load_legacy()
    scenario, _ = migrate_from_legacy(legacy)
    restored = deserialize_scenario(serialize_scenario(scenario))
    by_name = {i.name: i for i in restored.entry_inputs}
    assert by_name["P_NUM_STORE"].value == 42
    assert isinstance(by_name["P_NUM_STORE"].value, int)
    assert by_name["P_ACTIVE"].value is True
    assert isinstance(by_name["P_ACTIVE"].value, bool)


def test_output_ends_with_newline():
    scenario, _ = migrate_from_legacy({"proceso": "X", "meta4object": "O", "nodo": "N", "metodo": "M()"})
    assert serialize_scenario(scenario).endswith("\n")


def test_output_is_valid_json():
    legacy = _load_legacy()
    scenario, _ = migrate_from_legacy(legacy)
    data = json.loads(serialize_scenario(scenario))
    assert data["schema_version"] == "1.0"


def test_output_is_deterministic():
    legacy = _load_legacy()
    s1, _ = migrate_from_legacy(legacy, legacy_file="tests/fixtures/scenarios/legacy_peoplenet_call.json")
    s2, _ = migrate_from_legacy(legacy, legacy_file="tests/fixtures/scenarios/legacy_peoplenet_call.json")
    assert serialize_scenario(s1) == serialize_scenario(s2)


def test_enum_values_serialized_as_strings():
    legacy = _load_legacy()
    scenario, _ = migrate_from_legacy(legacy)
    data = scenario_to_dict(scenario)
    assert data["process"]["source"] == "manual_derivation"
    assert data["process"]["status"] == "derived"


def test_none_values_serialized_as_null():
    legacy = _load_legacy()
    scenario, _ = migrate_from_legacy(legacy)
    serialized = serialize_scenario(scenario)
    data = json.loads(serialized)
    assert data["source_files"]["original_call"] is None
    assert data["source_files"]["hash"] is None


def test_runtime_value_evidence_serialized_as_null():
    # Fix 5: optional fields evidence/expression must always appear in output (as null when absent),
    # so consumers can rely on a stable key set rather than checking for key presence.
    from peoplenet_process_extractor.scenario.enums import Source, Status
    from peoplenet_process_extractor.scenario.models import (
        EntryPoint,
        Process,
        RuntimeValue,
        Scenario,
    )

    rv = RuntimeValue(
        name="VAL",
        value=42,
        type="integer",
        source=Source.SOURCE_CODE,
        status=Status.DERIVED,
        evidence=None,
        expression=None,
    )
    scenario = Scenario(
        schema_version="1.0",
        scenario_id="test",
        process=Process(id="PROC", source=Source.MANUAL_DERIVATION, status=Status.DERIVED),
        entry_point=EntryPoint(meta4object="OBJ", node="N", method="M"),
        runtime_values=[rv],
    )
    data = scenario_to_dict(scenario)
    rv_dict = data["runtime_values"][0]
    assert "evidence" in rv_dict
    assert rv_dict["evidence"] is None
    assert "expression" in rv_dict
    assert rv_dict["expression"] is None


def test_golden_match():
    """Regression: migration output must match the committed expected fixture.

    Manual review record (2026-06-22):
    expected_scenario_v1.json was verified field-by-field against legacy_peoplenet_call.json,
    docs/schemas/scenario-v1.md, and the migration rules. It was NOT regenerated from the
    implementation after that point. Specific checks performed:
    - scenario_id "11-jorn-store-u" ← derive_scenario_id("11_JORN_STORE_U") ✓
    - process: id/source/status match manual_derivation + derived defaults ✓
    - entry_point: method "GLB_M_PC_EXE", arguments ["STEP_SAVE"] parsed from legacy metodo ✓
    - entry_inputs: 4 items, insertion order preserved, types preserved (42→integer, true→boolean,
      "2024-01-15" kept as string — not parsed as date) ✓
    - property_bindings: P_14 binding preserved with warning (not in inputs), order preserved ✓
    - runtime_values: [] (adapter does not populate; null policy does not affect empty list) ✓
    - flags: insertion order GLB_CK_CAMB_EMPRESA→false, GLB_CK_HOR_SRZ→true ✓
    - analysis_scope.methods: reason serialized as null per optional-field policy ✓
    - source_files: legacy_file set, original_call/hash null per optional-field policy ✓
    - configuration: [] — not populated by adapter ✓
    - notes: preserved literally, no interpretation ✓
    """
    legacy = _load_legacy()
    scenario, _ = migrate_from_legacy(
        legacy,
        legacy_file="tests/fixtures/scenarios/legacy_peoplenet_call.json",
    )
    actual = serialize_scenario(scenario)
    expected = (FIXTURE_DIR / "expected_scenario_v1.json").read_text(encoding="utf-8")
    assert actual == expected
