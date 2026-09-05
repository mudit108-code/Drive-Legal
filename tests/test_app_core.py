"""Tests for the import-safe DriveLegal calculator core."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app_core import (
    ALL_STATES,
    CITIZEN_RIGHTS,
    LEGAL_SECTIONS,
    METADATA,
    NATIONAL_FINES,
    STATE_DATA,
    VEHICLE_TYPES,
    CalculatorInputError,
    DataValidationError,
    calculate_fine,
    calculate_multi_fine,
    get_allowed_vehicle_types,
    get_compounding_comparison_matrix,
    get_source_details,
    get_state_compounding_info,
    get_violation_options,
    validate_data,
)


ROOT = Path(__file__).resolve().parent.parent


def test_complete_data_package_is_loaded_from_local_files():
    assert len(NATIONAL_FINES) == 19
    assert len(VEHICLE_TYPES) == 7
    assert len(STATE_DATA) == 36
    assert ALL_STATES == sorted(STATE_DATA)
    for filename, expected in (
        ("national_fines.json", NATIONAL_FINES),
        ("vehicle_types.json", VEHICLE_TYPES),
        ("state_data.json", STATE_DATA),
        ("legal_sections.json", LEGAL_SECTIONS),
        ("citizen_rights.json", CITIZEN_RIGHTS),
    ):
        assert json.loads((ROOT / "data" / filename).read_text(encoding="utf-8")) == expected


def test_every_fine_record_has_required_schema():
    for record in NATIONAL_FINES.values():
        assert record["description"]
        assert record["fine"] >= 0
        assert record["rule_section"]
        assert record["penalty_section"]
        assert record["allowed_vehicle_types"]
        assert set(record["allowed_vehicle_types"]).issubset(VEHICLE_TYPES)
        assert record["source_ids"]
        assert record["legal_note"]
        assert record["fine_basis"] in {"fixed", "per_excess_passenger", "base_plus_excess_tonne"}


def test_all_state_records_have_expected_shape():
    assert set(STATE_DATA) == set(ALL_STATES)
    for state, info in STATE_DATA.items():
        assert 0 <= info["surcharge"] < 1
        assert 0 < info["speed_city"] < info["speed_highway"] < 300
        assert info["notes"]
        assert info["source_status"] in {"reference_only", "state_notification"}
        if info["source_status"] == "state_notification":
            assert info["notification_id"]
            assert info["effective_date"]
            assert info["jurisdiction"]
            assert isinstance(info["compounding_schedule"], dict)
            assert len(info["compounding_schedule"]) > 0


def test_source_ids_resolve_to_display_ready_metadata():
    sources = get_source_details(["mva1988", "mva2019"])
    assert [source["id"] for source in sources] == ["mva1988", "mva2019"]
    assert all(source["title"] and source["url"].startswith("https://") for source in sources)


def test_unknown_source_ids_are_rejected():
    with pytest.raises(DataValidationError, match="Unknown source IDs"):
        get_source_details(["not-in-metadata"])


def test_calculation_result_includes_resolved_sources():
    result = calculate_fine("signal_jump", "Light Motor Vehicle (Car)", "Delhi")
    assert result["source_ids"] == ["mva1988", "mva2019"]
    assert [source["id"] for source in result["sources"]] == result["source_ids"]
    assert all(source["url"].startswith("https://") for source in result["sources"])


def test_red_light_uses_rule_section_119_and_penalty_section_184():
    record = NATIONAL_FINES["signal_jump"]
    assert record["rule_section"] == "119"
    assert record["penalty_section"] == "184"
    assert record["imprisonment"] == "Up to 1 year (or fine, or both)"
    result = calculate_fine("signal_jump", "Light Motor Vehicle (Car)", "Delhi")
    assert result["rule_section"] == "119"
    assert result["penalty_section"] == "184"
    assert result["total"] == 5000


def test_all_national_records_have_record_level_legal_notes():
    assert all(record["legal_note"].strip() for record in NATIONAL_FINES.values())


def test_legal_catalogue_is_loaded_from_bundled_data():
    assert len(LEGAL_SECTIONS) == 18
    assert len({record["section"] for record in LEGAL_SECTIONS}) == len(LEGAL_SECTIONS)
    assert all(record["title"] and record["description"] for record in LEGAL_SECTIONS)


def test_overloading_goods_is_quantity_based_and_not_multiplied_by_vehicle_type():
    result = calculate_fine("overloading_goods", "Heavy Motor Vehicle", "Delhi", quantity=1.5)
    assert result["base_fine"] == 23000
    assert result["total"] == 23000
    assert result["fine_basis"] == "base_plus_excess_tonne"
    assert result["vehicle_multiplier_applied"] is False


def test_overloading_passengers_is_per_excess_passenger():
    result = calculate_fine("overloading_passenger", "Transport / Commercial", "Delhi", quantity=3)
    assert result["base_fine"] == 600
    assert result["total"] == 600
    assert result["fine_basis"] == "per_excess_passenger"


def test_explicit_drunk_driving_repeat_rate_is_not_doubled_again():
    result = calculate_fine("drunk_driving", "Light Motor Vehicle (Car)", "Delhi", repeat=True)
    assert result["base_fine"] == 15000
    assert result["repeat_penalty"] == 0
    assert result["total"] == 15000
    assert result["explicit_repeat_fine"] == 15000


def test_unverified_repeat_policy_is_not_calculated():
    result = calculate_fine("signal_jump", "Light Motor Vehicle (Car)", "Goa", repeat=False)
    assert result["total"] == 5000
    assert result["repeat_penalty"] == 0
    with pytest.raises(CalculatorInputError, match="not available"):
        calculate_fine("signal_jump", "Light Motor Vehicle (Car)", "Goa", repeat=True)


def test_current_records_do_not_use_unsupported_generic_repeat_policy():
    assert all(record["repeat_policy"] != "toggle" for record in NATIONAL_FINES.values())


def test_state_surcharge_is_rounded_to_two_decimal_places():
    result = calculate_fine("no_parking", "Two-Wheeler (≤ 50cc)", "Kerala")
    assert result["base_fine"] == 500
    assert result["state_surcharge_rate"] == 0.05
    assert result["state_surcharge"] == 0
    assert result["state_surcharge_applied"] is False
    assert result["total"] == 500
    assert isinstance(result["total"], float)
    assert round(result["total"], 2) == result["total"]


def test_invalid_vehicle_and_violation_combinations_are_rejected():
    assert "Light Motor Vehicle (Car)" not in get_allowed_vehicle_types("no_helmet")
    with pytest.raises(CalculatorInputError, match="not applicable"):
        calculate_fine("no_helmet", "Light Motor Vehicle (Car)", "Delhi")
    with pytest.raises(CalculatorInputError, match="not applicable"):
        calculate_fine("overloading_goods", "Two-Wheeler (> 50cc)", "Delhi", quantity=1)


def test_quantity_validation_is_strict():
    with pytest.raises(CalculatorInputError, match="requires a quantity"):
        calculate_fine("overloading_goods", "Heavy Motor Vehicle", "Delhi")
    with pytest.raises(CalculatorInputError, match="whole number"):
        calculate_fine("overloading_passenger", "Transport / Commercial", "Delhi", quantity=1.5)
    with pytest.raises(CalculatorInputError, match="cannot be negative"):
        calculate_fine("overloading_goods", "Heavy Motor Vehicle", "Delhi", quantity=-1)


def test_non_finite_quantities_are_rejected():
    for quantity in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CalculatorInputError, match="finite"):
            calculate_fine("overloading_goods", "Heavy Motor Vehicle", "Delhi", quantity=quantity)


def test_boolean_quantities_are_rejected():
    with pytest.raises(CalculatorInputError, match="not Boolean"):
        calculate_fine("overloading_passenger", "Transport / Commercial", "Delhi", quantity=True)


def test_fixed_records_reject_repeat_when_not_applicable():
    with pytest.raises(CalculatorInputError, match="does not apply"):
        calculate_fine("no_helmet", "Two-Wheeler (> 50cc)", "Delhi", repeat=True)


def test_violation_labels_are_unique_and_round_trip():
    options = get_violation_options()
    assert len(options) == len(NATIONAL_FINES)
    assert set(options.values()) == set(NATIONAL_FINES)


def test_validation_rejects_invalid_metadata_and_state_count():
    with pytest.raises(DataValidationError):
        validate_data(NATIONAL_FINES, VEHICLE_TYPES, {"Delhi": STATE_DATA["Delhi"]}, METADATA)


def test_validation_rejects_incomplete_source_metadata():
    metadata = {**METADATA, "sources": [{"id": "mva1988", "title": "Missing URL"}]}
    with pytest.raises(DataValidationError, match="metadata source field missing: url"):
        validate_data(NATIONAL_FINES, VEHICLE_TYPES, STATE_DATA, metadata)


def test_validation_rejects_missing_legal_notes():
    fines = {**NATIONAL_FINES, "bad": {**NATIONAL_FINES["no_parking"]}}
    del fines["bad"]["legal_note"]
    with pytest.raises(DataValidationError, match="missing fields"):
        validate_data(fines, VEHICLE_TYPES, STATE_DATA, METADATA)


def test_validation_rejects_non_finite_fines_and_boolean_multipliers():
    fines = {**NATIONAL_FINES, "bad": {**NATIONAL_FINES["no_parking"], "fine": float("inf")}}
    with pytest.raises(DataValidationError, match="invalid fine"):
        validate_data(fines, VEHICLE_TYPES, STATE_DATA, METADATA)

    vehicles = {**VEHICLE_TYPES, "Bad vehicle": True}
    with pytest.raises(DataValidationError, match="invalid multiplier"):
        validate_data(NATIONAL_FINES, vehicles, STATE_DATA, METADATA)


def test_validation_rejects_empty_sources_and_unexpected_locations():
    fines = {**NATIONAL_FINES, "bad": {**NATIONAL_FINES["no_parking"], "source_ids": []}}
    with pytest.raises(DataValidationError, match="invalid source IDs"):
        validate_data(fines, VEHICLE_TYPES, STATE_DATA, METADATA)

    states = {**STATE_DATA}
    states["Not a location"] = states.pop("Delhi")
    with pytest.raises(DataValidationError, match="expected 28 states"):
        validate_data(NATIONAL_FINES, VEHICLE_TYPES, states, METADATA)


def test_validation_rejects_malformed_state_record():
    states = {**STATE_DATA, "Delhi": None}
    with pytest.raises(DataValidationError, match="state record Delhi must be an object"):
        validate_data(NATIONAL_FINES, VEHICLE_TYPES, states, METADATA)


def test_calculator_rejects_non_boolean_repeat_and_fixed_quantities():
    with pytest.raises(CalculatorInputError, match="Repeat must be Boolean"):
        calculate_fine("signal_jump", "Light Motor Vehicle (Car)", "Delhi", repeat="false")
    with pytest.raises(CalculatorInputError, match="does not accept a quantity"):
        calculate_fine("no_parking", "Light Motor Vehicle (Car)", "Delhi", quantity=float("nan"))


def test_state_compounding_info_resolution():
    delhi_info = get_state_compounding_info("Delhi", "no_helmet")
    assert delhi_info is not None
    assert delhi_info["notification_id"] == "F.19(148)/Tpt/Ops/2019/379"
    assert delhi_info["effective_date"] == "2020-03-13"
    assert delhi_info["compounding_fee"] == 1000

    karnataka_helmet = get_state_compounding_info("Karnataka", "no_helmet")
    assert karnataka_helmet["compounding_fee"] == 500

    unverified = get_state_compounding_info("Goa", "no_helmet")
    assert unverified is None

    full_delhi = get_state_compounding_info("Delhi")
    assert "no_helmet" in full_delhi["schedule"]
    assert full_delhi["jurisdiction"] == "National Capital Territory of Delhi"


def test_calculate_fine_includes_compounding_details():
    delhi_res = calculate_fine("no_helmet", "Two-Wheeler (> 50cc)", "Delhi")
    assert delhi_res["compounding_fee"] == 1000
    assert delhi_res["compounding_notification_id"] == "F.19(148)/Tpt/Ops/2019/379"
    assert delhi_res["compounding_effective_date"] == "2020-03-13"

    goa_res = calculate_fine("no_helmet", "Two-Wheeler (> 50cc)", "Goa")
    assert goa_res["compounding_fee"] is None
    assert goa_res["compounding_notification_id"] is None


def test_compounding_validation_rejects_invalid_values():
    bad_states = {**STATE_DATA, "Delhi": {**STATE_DATA["Delhi"], "effective_date": "invalid-date"}}
    with pytest.raises(DataValidationError, match="effective_date must be in YYYY-MM-DD format"):
        validate_data(NATIONAL_FINES, VEHICLE_TYPES, bad_states, METADATA)

    bad_schedule = {**STATE_DATA, "Delhi": {**STATE_DATA["Delhi"], "compounding_schedule": {"unknown_violation": 1000}}}
    with pytest.raises(DataValidationError, match="unknown violation"):
        validate_data(NATIONAL_FINES, VEHICLE_TYPES, bad_schedule, METADATA)

    neg_schedule = {**STATE_DATA, "Delhi": {**STATE_DATA["Delhi"], "compounding_schedule": {"no_helmet": -500}}}
    with pytest.raises(DataValidationError, match="invalid compounding amount"):
        validate_data(NATIONAL_FINES, VEHICLE_TYPES, neg_schedule, METADATA)


def test_catalogue_covers_all_national_fine_penalty_sections():
    catalogue_sections = [law["section"].replace(" ", "") for law in LEGAL_SECTIONS]
    for key, fine_record in NATIONAL_FINES.items():
        clean_penalty = fine_record["penalty_section"].replace(" ", "")
        matched = any(clean_penalty in sec or sec in clean_penalty for sec in catalogue_sections)
        assert matched, f"Penalty section {fine_record['penalty_section']} for {key} is not covered in LEGAL_SECTIONS"


def test_legal_catalogue_search_filters():
    assert len(LEGAL_SECTIONS) == 18

    # Search by section number
    sec_184 = [law for law in LEGAL_SECTIONS if "184" in law["section"]]
    assert len(sec_184) == 1
    assert sec_184[0]["title"] == "Dangerous driving and red-light jumping"

    # Search by keyword in title
    licence_matches = [law for law in LEGAL_SECTIONS if "licence" in law["title"].lower()]
    assert len(licence_matches) >= 1

    # Search by topic in description
    insurance = [law for law in LEGAL_SECTIONS if "third-party insurance" in law["description"].lower()]
    assert len(insurance) == 1
    assert insurance[0]["section"] == "146 / 196"


def test_expanded_state_compounding_resolution():
    # Gujarat
    gujarat_helmet = get_state_compounding_info("Gujarat", "no_helmet")
    assert gujarat_helmet is not None
    assert gujarat_helmet["notification_id"] == "GH/L/30/MVA/102019/1884/Kh"
    assert gujarat_helmet["effective_date"] == "2019-09-11"
    assert gujarat_helmet["compounding_fee"] == 500

    # Tamil Nadu
    tn_helmet = get_state_compounding_info("Tamil Nadu", "no_helmet")
    assert tn_helmet is not None
    assert tn_helmet["notification_id"] == "G.O. (Ms.) No. 445"
    assert tn_helmet["effective_date"] == "2022-10-19"
    assert tn_helmet["compounding_fee"] == 1000

    # Uttar Pradesh
    up_dl = get_state_compounding_info("Uttar Pradesh", "no_dl")
    assert up_dl is not None
    assert up_dl["notification_id"] == "1326/XXX-4-2020-07(11)/2019"
    assert up_dl["effective_date"] == "2020-06-18"
    assert up_dl["compounding_fee"] == 2500


def test_calculate_multi_fine_combines_items():
    items = [
        {"violation_key": "no_helmet", "vehicle_key": "Two-Wheeler (> 50cc)"},
        {"violation_key": "no_dl", "vehicle_key": "Two-Wheeler (> 50cc)"},
        {"violation_key": "signal_jump", "vehicle_key": "Two-Wheeler (> 50cc)"},
    ]
    res = calculate_multi_fine(items, "Delhi")
    assert res["state"] == "Delhi"
    assert res["item_count"] == 3
    assert res["total_base_fine"] == 1000 + 5000 + 5000  # 11000
    assert res["grand_total"] == 11000
    assert res["has_compounding_items"] is True
    assert res["total_compounding_fee"] == 6000  # no_helmet (1000) + signal_jump (5000) in Delhi


def test_calculate_multi_fine_validation_rejects_empty_and_invalid():
    with pytest.raises(CalculatorInputError, match="At least one offence item"):
        calculate_multi_fine([], "Delhi")

    with pytest.raises(CalculatorInputError, match="Unknown state"):
        calculate_multi_fine([{"violation_key": "no_helmet", "vehicle_key": "Two-Wheeler (> 50cc)"}], "Atlantis")

    with pytest.raises(CalculatorInputError, match="missing violation_key or vehicle_key"):
        calculate_multi_fine([{"violation_key": "no_helmet"}], "Delhi")


def test_compounding_state_count_and_metrics():
    compounding_states = [s for s, data in STATE_DATA.items() if data.get("compounding_schedule")]
    assert len(compounding_states) == 6
    assert set(compounding_states) == {"Delhi", "Karnataka", "Maharashtra", "Gujarat", "Tamil Nadu", "Uttar Pradesh"}
    assert len(LEGAL_SECTIONS) == 18
    assert len(NATIONAL_FINES) == 19


def test_citizen_rights_schema_and_content():
    assert len(CITIZEN_RIGHTS) == 5
    ids = [r["id"] for r in CITIZEN_RIGHTS]
    assert len(ids) == len(set(ids))
    assert "digilocker_validity" in ids
    assert "grace_period_15_days" in ids
    assert "virtual_courts" in ids
    assert "grievance_redressal" in ids
    assert "emergency_helplines" in ids

    source_ids = {s["id"] for s in METADATA["sources"]}
    for r in CITIZEN_RIGHTS:
        assert r["title"]
        assert r["statutory_basis"]
        assert r["summary"]
        assert len(r["key_provisions"]) >= 2
        assert r["source_id"] in source_ids


def test_get_compounding_comparison_matrix_structure():
    matrix = get_compounding_comparison_matrix()
    assert len(matrix["states"]) == 6
    assert matrix["states"] == ["Delhi", "Gujarat", "Karnataka", "Maharashtra", "Tamil Nadu", "Uttar Pradesh"]
    assert len(matrix["rows"]) > 0

    helmet_row = next(r for r in matrix["rows"] if r["violation_key"] == "no_helmet")
    assert helmet_row["central_fine"] == 1000
    assert helmet_row["state_fees"]["Delhi"] == 1000
    assert helmet_row["state_fees"]["Gujarat"] == 500
    assert helmet_row["state_fees"]["Karnataka"] == 500
    assert helmet_row["state_fees"]["Maharashtra"] == 500
    assert helmet_row["state_fees"]["Tamil Nadu"] == 1000
    assert helmet_row["state_fees"]["Uttar Pradesh"] == 1000


def test_get_compounding_comparison_matrix_filtering_and_errors():
    filtered = get_compounding_comparison_matrix(violation_keys=["no_helmet", "signal_jump"])
    assert len(filtered["rows"]) == 2
    assert [r["violation_key"] for r in filtered["rows"]] == ["no_helmet", "signal_jump"]

    with pytest.raises(CalculatorInputError, match="Unknown violation"):
        get_compounding_comparison_matrix(violation_keys=["invalid_offence"])
