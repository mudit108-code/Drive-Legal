"""Import-safe application core for DriveLegal India.

The Streamlit UI lives in app.py. This module owns data loading, validation,
and calculator behavior so it can be tested without rendering a Streamlit page.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

EXPECTED_STATES = frozenset(
    {
        "Andhra Pradesh",
        "Arunachal Pradesh",
        "Assam",
        "Bihar",
        "Chhattisgarh",
        "Goa",
        "Gujarat",
        "Haryana",
        "Himachal Pradesh",
        "Jharkhand",
        "Karnataka",
        "Kerala",
        "Madhya Pradesh",
        "Maharashtra",
        "Manipur",
        "Meghalaya",
        "Mizoram",
        "Nagaland",
        "Odisha",
        "Punjab",
        "Rajasthan",
        "Sikkim",
        "Tamil Nadu",
        "Telangana",
        "Tripura",
        "Uttar Pradesh",
        "Uttarakhand",
        "West Bengal",
    }
)
EXPECTED_UNION_TERRITORIES = frozenset(
    {
        "Andaman and Nicobar Islands",
        "Chandigarh",
        "Dadra and Nagar Haveli and Daman and Diu",
        "Delhi",
        "Jammu and Kashmir",
        "Ladakh",
        "Lakshadweep",
        "Puducherry",
    }
)
EXPECTED_LOCATIONS = EXPECTED_STATES | EXPECTED_UNION_TERRITORIES


class DataValidationError(ValueError):
    """Raised when the bundled offline data does not satisfy the schema."""


class CalculatorInputError(ValueError):
    """Raised when a calculator selection or quantity is invalid."""


def _read_json(filename: str) -> Any:
    path = DATA_DIR / filename
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise DataValidationError(f"Required offline data file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DataValidationError(f"Offline data file is invalid JSON: {path}: {exc}") from exc


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DataValidationError(message)


def _validate_legal_sections(legal_sections: Any) -> None:
    _require(isinstance(legal_sections, list) and legal_sections, "legal_sections must be a non-empty array")
    sections = []
    for index, record in enumerate(legal_sections):
        _require(isinstance(record, dict), f"legal section {index} must be an object")
        for field in ("section", "title", "description"):
            _require(
                isinstance(record.get(field), str) and record[field].strip(),
                f"legal section {index} is missing {field}",
            )
        sections.append(record["section"])
    _require(len(sections) == len(set(sections)), "legal section identifiers must be unique")


def _validate_citizen_rights(citizen_rights: Any) -> None:
    _require(isinstance(citizen_rights, list) and citizen_rights, "citizen_rights must be a non-empty array")
    ids = []
    for index, record in enumerate(citizen_rights):
        _require(isinstance(record, dict), f"citizen right {index} must be an object")
        for field in ("id", "title", "statutory_basis", "summary", "key_provisions"):
            _require(
                bool(record.get(field)),
                f"citizen right {index} is missing {field}",
            )
        _require(
            isinstance(record["key_provisions"], list) and record["key_provisions"],
            f"key_provisions must be a non-empty list in citizen right {index}",
        )
        ids.append(record["id"])
    _require(len(ids) == len(set(ids)), "citizen right IDs must be unique")


def validate_data(
    national_fines: dict[str, dict[str, Any]],
    vehicle_types: dict[str, float],
    state_data: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    """Validate the complete offline data package before the app renders."""
    required_fine_fields = {
        "description", "fine", "imprisonment", "rule_section", "penalty_section",
        "allowed_vehicle_types", "repeat_policy", "fine_basis", "apply_vehicle_multiplier",
        "source_status", "source_ids", "legal_note",
    }
    allowed_repeat_policies = {"explicit", "not_applicable", "reference_only"}
    allowed_fine_bases = {"fixed", "per_excess_passenger", "base_plus_excess_tonne"}
    _require(isinstance(metadata, dict), "metadata must be an object")
    sources = metadata.get("sources", [])

    _require(isinstance(national_fines, dict) and national_fines, "national_fines must be a non-empty object")
    _require(isinstance(vehicle_types, dict) and vehicle_types, "vehicle_types must be a non-empty object")
    _require(
        isinstance(state_data, dict) and set(state_data) == EXPECTED_LOCATIONS,
        "state_data must contain the expected 28 states and 8 Union Territories",
    )
    _require(metadata.get("schema_version") == 2, "metadata schema_version must be 2")
    _require(isinstance(metadata.get("last_reviewed"), str) and metadata["last_reviewed"].strip(), "metadata must include last_reviewed")
    _require(isinstance(metadata.get("disclaimer"), str) and metadata["disclaimer"].strip(), "metadata must include disclaimer")
    _require(isinstance(sources, list) and sources, "metadata must contain at least one source")
    source_ids = set()
    for source in sources:
        _require(isinstance(source, dict), "each metadata source must be an object")
        for field in ("id", "title", "url"):
            _require(isinstance(source.get(field), str) and source[field].strip(), f"metadata source field missing: {field}")
        _require(source["id"] not in source_ids, f"duplicate metadata source ID: {source['id']}")
        _require(urlparse(source["url"]).scheme == "https" and urlparse(source["url"]).netloc, f"metadata source URL must use HTTPS: {source['id']}")
        source_ids.add(source["id"])

    for vehicle, multiplier in vehicle_types.items():
        _require(isinstance(vehicle, str) and vehicle.strip(), "vehicle type names must be non-empty strings")
        _require(
            isinstance(multiplier, (int, float)) and not isinstance(multiplier, bool) and math.isfinite(multiplier) and 0 < multiplier <= 2,
            f"invalid multiplier for {vehicle}",
        )

    for key, record in national_fines.items():
        _require(isinstance(record, dict), f"fine record {key} must be an object")
        missing = required_fine_fields - record.keys()
        _require(not missing, f"fine record {key} is missing fields: {sorted(missing)}")
        _require(isinstance(record["description"], str) and record["description"].strip(), f"fine description missing for {key}")
        _require(
            isinstance(record["fine"], (int, float)) and not isinstance(record["fine"], bool)
            and math.isfinite(record["fine"]) and record["fine"] >= 0,
            f"invalid fine for {key}",
        )
        _require(record["repeat_policy"] in allowed_repeat_policies, f"invalid repeat policy for {key}")
        _require(record["fine_basis"] in allowed_fine_bases, f"invalid fine basis for {key}")
        _require(isinstance(record["imprisonment"], (str, type(None))), f"invalid imprisonment value for {key}")
        _require(isinstance(record["rule_section"], str) and record["rule_section"].strip(), f"rule section missing for {key}")
        _require(isinstance(record["penalty_section"], str) and record["penalty_section"].strip(), f"penalty section missing for {key}")
        _require(isinstance(record["apply_vehicle_multiplier"], bool), f"vehicle multiplier flag must be Boolean for {key}")
        if "apply_state_surcharge" in record:
            _require(isinstance(record["apply_state_surcharge"], bool), f"state surcharge flag must be Boolean for {key}")
        _require(record["source_status"] in {"act_reference", "reference_only"}, f"invalid source status for {key}")
        _require(isinstance(record["legal_note"], str) and record["legal_note"].strip(), f"legal note missing for {key}")
        _require(
            isinstance(record["allowed_vehicle_types"], list)
            and record["allowed_vehicle_types"]
            and len(record["allowed_vehicle_types"]) == len(set(record["allowed_vehicle_types"]))
            and all(isinstance(vehicle, str) and vehicle.strip() for vehicle in record["allowed_vehicle_types"]),
            f"vehicle applicability is invalid for {key}",
        )
        _require(set(record["allowed_vehicle_types"]).issubset(vehicle_types), f"unknown vehicle type in {key}")
        _require(
            isinstance(record["source_ids"], list)
            and record["source_ids"]
            and len(record["source_ids"]) == len(set(record["source_ids"]))
            and all(isinstance(source_id, str) and source_id.strip() for source_id in record["source_ids"])
            and set(record["source_ids"]).issubset(source_ids),
            f"invalid source IDs for {key}",
        )
        if record["repeat_policy"] == "explicit":
            _require(
                "repeat_fine" in record
                and isinstance(record["repeat_fine"], (int, float))
                and not isinstance(record["repeat_fine"], bool)
                and math.isfinite(record["repeat_fine"])
                and record["repeat_fine"] >= 0,
                f"explicit repeat fine missing for {key}",
            )
        if record["fine_basis"] == "per_excess_passenger":
            _require(
                record.get("quantity_field") == "excess_passengers"
                and isinstance(record.get("quantity_label"), str)
                and record["quantity_label"].strip(),
                f"passenger quantity field is incomplete for {key}",
            )
        if record["fine_basis"] == "base_plus_excess_tonne":
            _require(
                record.get("quantity_field") == "excess_tonnes"
                and isinstance(record.get("quantity_label"), str)
                and record["quantity_label"].strip(),
                f"tonnage quantity field is incomplete for {key}",
            )
            _require(
                isinstance(record.get("extra_unit_fine"), (int, float))
                and not isinstance(record["extra_unit_fine"], bool)
                and math.isfinite(record["extra_unit_fine"])
                and record["extra_unit_fine"] > 0,
                f"extra-tonne fine missing for {key}",
            )

    required_state_fields = {
        "surcharge", "notes", "helmet_law", "speed_city", "speed_highway",
        "source_status", "source_ids", "legal_note", "notification_id",
        "effective_date", "jurisdiction", "compounding_schedule",
    }
    for state, record in state_data.items():
        _require(isinstance(record, dict), f"state record {state} must be an object")
        missing = required_state_fields - record.keys()
        _require(not missing, f"state record {state} is missing fields: {sorted(missing)}")
        _require(
            isinstance(record["surcharge"], (int, float))
            and not isinstance(record["surcharge"], bool)
            and math.isfinite(record["surcharge"])
            and 0 <= record["surcharge"] < 1,
            f"invalid surcharge for {state}",
        )
        _require(
            isinstance(record["speed_city"], (int, float))
            and not isinstance(record["speed_city"], bool)
            and math.isfinite(record["speed_city"])
            and isinstance(record["speed_highway"], (int, float))
            and not isinstance(record["speed_highway"], bool)
            and math.isfinite(record["speed_highway"])
            and 0 < record["speed_city"] < record["speed_highway"] < 300,
            f"invalid speed limits for {state}",
        )
        _require(
            isinstance(record["notes"], list)
            and record["notes"]
            and all(isinstance(note, str) and note.strip() for note in record["notes"]),
            f"notes missing for {state}",
        )
        _require(isinstance(record["helmet_law"], str) and record["helmet_law"].strip(), f"helmet law missing for {state}")
        _require(record["source_status"] in {"act_reference", "reference_only", "state_notification"}, f"invalid source status for {state}")
        _require(isinstance(record["legal_note"], str) and record["legal_note"].strip(), f"legal note missing for {state}")
        _require(
            isinstance(record["source_ids"], list)
            and record["source_ids"]
            and len(record["source_ids"]) == len(set(record["source_ids"]))
            and all(isinstance(source_id, str) and source_id.strip() for source_id in record["source_ids"])
            and set(record["source_ids"]).issubset(source_ids),
            f"invalid source IDs for {state}",
        )
        if record.get("notification_id") is not None:
            _require(isinstance(record["notification_id"], str) and record["notification_id"].strip(), f"notification_id must be a non-empty string for {state}")
        if record.get("effective_date") is not None:
            _require(
                isinstance(record["effective_date"], str)
                and len(record["effective_date"]) == 10
                and record["effective_date"][:4].isdigit()
                and record["effective_date"][4] == "-"
                and record["effective_date"][5:7].isdigit()
                and record["effective_date"][7] == "-"
                and record["effective_date"][8:].isdigit(),
                f"effective_date must be in YYYY-MM-DD format for {state}",
            )
        if record.get("jurisdiction") is not None:
            _require(isinstance(record["jurisdiction"], str) and record["jurisdiction"].strip(), f"jurisdiction must be a non-empty string for {state}")
        if record.get("compounding_schedule") is not None:
            _require(isinstance(record["compounding_schedule"], dict) and record["compounding_schedule"], f"compounding_schedule must be a non-empty dict for {state}")
            for v_key, amount in record["compounding_schedule"].items():
                _require(v_key in national_fines, f"unknown violation {v_key} in compounding_schedule for {state}")
                _require(
                    isinstance(amount, (int, float)) and not isinstance(amount, bool) and math.isfinite(amount) and amount > 0,
                    f"invalid compounding amount for {v_key} in {state}",
                )

    descriptions = [record["description"] for record in national_fines.values()]
    _require(len(descriptions) == len(set(descriptions)), "violation descriptions must be unique for the selector")


def load_data() -> tuple[dict[str, Any], dict[str, float], dict[str, Any], dict[str, Any]]:
    national_fines = _read_json("national_fines.json")
    vehicle_types = _read_json("vehicle_types.json")
    state_data = _read_json("state_data.json")
    metadata = _read_json("metadata.json")
    validate_data(national_fines, vehicle_types, state_data, metadata)
    return national_fines, vehicle_types, state_data, metadata


NATIONAL_FINES, VEHICLE_TYPES, STATE_DATA, METADATA = load_data()
LEGAL_SECTIONS = _read_json("legal_sections.json")
_validate_legal_sections(LEGAL_SECTIONS)
CITIZEN_RIGHTS = _read_json("citizen_rights.json")
_validate_citizen_rights(CITIZEN_RIGHTS)
ALL_STATES = sorted(STATE_DATA)


def get_source_details(source_ids: list[str]) -> list[dict[str, str]]:
    """Resolve bundled source IDs into safe, display-ready metadata."""
    source_by_id = {source["id"]: source for source in METADATA["sources"]}
    unknown = [source_id for source_id in source_ids if source_id not in source_by_id]
    if unknown:
        raise DataValidationError(f"Unknown source IDs: {sorted(set(unknown))}")
    return [
        {
            "id": source_by_id[source_id]["id"],
            "title": source_by_id[source_id]["title"],
            "url": source_by_id[source_id]["url"],
        }
        for source_id in source_ids
    ]


def get_violation_options() -> dict[str, str]:
    return {record["description"]: key for key, record in NATIONAL_FINES.items()}


def get_allowed_vehicle_types(violation_key: str) -> list[str]:
    try:
        return NATIONAL_FINES[violation_key]["allowed_vehicle_types"]
    except KeyError as exc:
        raise CalculatorInputError(f"Unknown violation: {violation_key}") from exc


def get_state_compounding_info(state: str, violation_key: str | None = None) -> dict[str, Any] | None:
    """Retrieve verified state compounding schedule and provenance if available."""
    if state not in STATE_DATA:
        raise CalculatorInputError(f"Unknown state or Union Territory: {state}")
    record = STATE_DATA[state]
    schedule = record.get("compounding_schedule")
    if not schedule:
        return None
    if violation_key is not None:
        if violation_key not in NATIONAL_FINES:
            raise CalculatorInputError(f"Unknown violation: {violation_key}")
        if violation_key not in schedule:
            return None
        return {
            "state": state,
            "jurisdiction": record.get("jurisdiction"),
            "notification_id": record.get("notification_id"),
            "effective_date": record.get("effective_date"),
            "compounding_fee": schedule[violation_key],
        }
    return {
        "state": state,
        "jurisdiction": record.get("jurisdiction"),
        "notification_id": record.get("notification_id"),
        "effective_date": record.get("effective_date"),
        "schedule": dict(schedule),
    }


def get_compounding_comparison_matrix(
    violation_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Generate a structured inter-state comparison of Section 200 compounding fees."""
    compounding_states = sorted(
        [state for state, data in STATE_DATA.items() if data.get("compounding_schedule")]
    )
    if not compounding_states:
        return {"states": [], "rows": []}

    if violation_keys is None:
        all_compounded_keys = set()
        for state in compounding_states:
            all_compounded_keys.update(STATE_DATA[state]["compounding_schedule"].keys())
        selected_keys = [k for k in NATIONAL_FINES if k in all_compounded_keys]
    else:
        for k in violation_keys:
            if k not in NATIONAL_FINES:
                raise CalculatorInputError(f"Unknown violation: {k}")
        selected_keys = violation_keys

    rows = []
    for k in selected_keys:
        fine_record = NATIONAL_FINES[k]
        row: dict[str, Any] = {
            "violation_key": k,
            "description": fine_record["description"],
            "penalty_section": fine_record["penalty_section"],
            "central_fine": fine_record["fine"],
            "state_fees": {},
        }
        for state in compounding_states:
            fee = STATE_DATA[state]["compounding_schedule"].get(k)
            row["state_fees"][state] = fee
        rows.append(row)

    return {
        "states": compounding_states,
        "rows": rows,
    }


def _validate_quantity(record: dict[str, Any], quantity: float | int | None) -> float:
    basis = record["fine_basis"]
    if basis == "fixed":
        if quantity is not None:
            raise CalculatorInputError(f"{record['description']} does not accept a quantity")
        return 0.0
    if quantity is None:
        raise CalculatorInputError(f"{record['description']} requires a quantity")
    if isinstance(quantity, bool):
        raise CalculatorInputError("Quantity must be numeric and not Boolean")
    try:
        numeric = float(quantity)
    except (TypeError, ValueError) as exc:
        raise CalculatorInputError("Quantity must be numeric") from exc
    if not math.isfinite(numeric):
        raise CalculatorInputError("Quantity must be finite")
    if numeric < 0:
        raise CalculatorInputError("Quantity cannot be negative")
    if basis == "per_excess_passenger" and not numeric.is_integer():
        raise CalculatorInputError("Excess passengers must be a whole number")
    if basis == "per_excess_passenger" and numeric < 1:
        raise CalculatorInputError("At least one excess passenger is required")
    if basis == "base_plus_excess_tonne" and numeric < 0:
        raise CalculatorInputError("Excess tonnes cannot be negative")
    return numeric


def calculate_fine(
    violation_key: str,
    vehicle_key: str,
    state: str,
    repeat: bool = False,
    quantity: float | int | None = None,
) -> dict[str, Any]:
    """Calculate a reference amount with explicit legal-data semantics.

    The bundled legal fine is not multiplied by vehicle type unless the data
    record explicitly opts in. Current legal records use vehicle type to filter
    applicability, not to invent a different statutory fine.
    """
    if not isinstance(repeat, bool):
        raise CalculatorInputError("Repeat must be Boolean")
    if violation_key not in NATIONAL_FINES:
        raise CalculatorInputError(f"Unknown violation: {violation_key}")
    if vehicle_key not in VEHICLE_TYPES:
        raise CalculatorInputError(f"Unknown vehicle type: {vehicle_key}")
    if state not in STATE_DATA:
        raise CalculatorInputError(f"Unknown state or Union Territory: {state}")

    record = NATIONAL_FINES[violation_key]
    allowed = record["allowed_vehicle_types"]
    if vehicle_key not in allowed:
        raise CalculatorInputError(f"{record['description']} is not applicable to {vehicle_key}")
    if record["repeat_policy"] == "not_applicable" and repeat:
        raise CalculatorInputError(f"Repeat-offence calculation does not apply to {record['description']}")
    if record["repeat_policy"] == "reference_only" and repeat:
        raise CalculatorInputError(f"Repeat-offence calculation is not available for {record['description']}")

    numeric_quantity = _validate_quantity(record, quantity)
    if record["fine_basis"] == "per_excess_passenger":
        reference_fine = record["fine"] * numeric_quantity
    elif record["fine_basis"] == "base_plus_excess_tonne":
        reference_fine = record["fine"] + record["extra_unit_fine"] * numeric_quantity
    else:
        reference_fine = record["fine"]

    repeat_penalty = 0.0
    applied_repeat_fine = None
    if repeat and record["repeat_policy"] == "explicit":
        applied_repeat_fine = record["repeat_fine"]
        reference_fine = applied_repeat_fine

    multiplier = VEHICLE_TYPES[vehicle_key] if record["apply_vehicle_multiplier"] else 1.0
    adjusted = reference_fine * multiplier
    state_surcharge_rate = STATE_DATA[state]["surcharge"]
    state_surcharge = adjusted * state_surcharge_rate if record.get("apply_state_surcharge", False) else 0.0
    total = round(adjusted + state_surcharge + repeat_penalty, 2)

    compounding_info = get_state_compounding_info(state, violation_key)

    return {
        "base_fine": round(reference_fine, 2),
        "vehicle_adjustment": round(adjusted - reference_fine, 2),
        "vehicle_multiplier": multiplier,
        "vehicle_multiplier_applied": record["apply_vehicle_multiplier"],
        "state_surcharge": round(state_surcharge, 2),
        "state_surcharge_rate": state_surcharge_rate,
        "state_surcharge_applied": bool(record.get("apply_state_surcharge", False)),
        "repeat_penalty": round(repeat_penalty, 2),
        "total": total,
        "rule_section": record["rule_section"],
        "penalty_section": record["penalty_section"],
        "imprisonment": record["imprisonment"],
        "quantity": numeric_quantity,
        "repeat_applied": bool(repeat),
        "explicit_repeat_fine": applied_repeat_fine,
        "legal_note": record.get("legal_note"),
        "source_status": record["source_status"],
        "source_ids": list(record["source_ids"]),
        "sources": get_source_details(record["source_ids"]),
        "fine_basis": record["fine_basis"],
        "compounding_fee": compounding_info["compounding_fee"] if compounding_info else None,
        "compounding_notification_id": compounding_info["notification_id"] if compounding_info else None,
        "compounding_effective_date": compounding_info["effective_date"] if compounding_info else None,
        "compounding_jurisdiction": compounding_info["jurisdiction"] if compounding_info else None,
    }


def calculate_multi_fine(
    items: list[dict[str, Any]],
    state: str,
) -> dict[str, Any]:
    """Calculate a consolidated reference summary for multiple simultaneous offences."""
    if not isinstance(items, list) or not items:
        raise CalculatorInputError("At least one offence item is required for multi-offence calculation")
    if state not in STATE_DATA:
        raise CalculatorInputError(f"Unknown state or Union Territory: {state}")

    results = []
    total_amount = 0.0
    total_base = 0.0
    total_vehicle_adjustment = 0.0
    total_state_surcharge = 0.0
    total_repeat_penalty = 0.0
    total_compounding = 0.0
    has_compounding_items = False

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CalculatorInputError(f"Item {index} must be a dictionary")
        v_key = item.get("violation_key")
        veh_key = item.get("vehicle_key")
        repeat = item.get("repeat", False)
        quantity = item.get("quantity")

        if not v_key or not veh_key:
            raise CalculatorInputError(f"Item {index} is missing violation_key or vehicle_key")

        res = calculate_fine(v_key, veh_key, state, repeat=repeat, quantity=quantity)
        results.append(res)

        total_amount += res["total"]
        total_base += res["base_fine"]
        total_vehicle_adjustment += res["vehicle_adjustment"]
        total_state_surcharge += res["state_surcharge"]
        total_repeat_penalty += res["repeat_penalty"]

        if res.get("compounding_fee") is not None:
            total_compounding += res["compounding_fee"]
            has_compounding_items = True

    return {
        "state": state,
        "items": results,
        "item_count": len(results),
        "total_base_fine": round(total_base, 2),
        "total_vehicle_adjustment": round(total_vehicle_adjustment, 2),
        "total_state_surcharge": round(total_state_surcharge, 2),
        "total_repeat_penalty": round(total_repeat_penalty, 2),
        "grand_total": round(total_amount, 2),
        "has_compounding_items": has_compounding_items,
        "total_compounding_fee": round(total_compounding, 2) if has_compounding_items else None,
    }
