"""Import-safe application core for DriveLegal India.

The Streamlit UI lives in app.py. This module owns data loading, validation,
and calculator behavior so it can be tested without rendering a Streamlit page.
"""

from __future__ import annotations

import json
import math
import re
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


def _validate_rto_directory(rto_dir: Any) -> None:
    _require(isinstance(rto_dir, dict), "rto_directory must be an object")
    _require("state_codes" in rto_dir and isinstance(rto_dir["state_codes"], dict), "state_codes must be an object")
    _require("bh_series" in rto_dir and isinstance(rto_dir["bh_series"], dict), "bh_series must be an object")
    _require("rto_divisions" in rto_dir and isinstance(rto_dir["rto_divisions"], dict), "rto_divisions must be an object")


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
RTO_DIRECTORY = _read_json("rto_directory.json")
_validate_rto_directory(RTO_DIRECTORY)
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


def search_legal_sections(query: str) -> list[dict[str, Any]]:
    """Search traffic laws catalogue by section number, title, or description."""
    q = query.lower().strip()
    if not q:
        return list(LEGAL_SECTIONS)
    return [
        sec
        for sec in LEGAL_SECTIONS
        if q in sec.get("section", "").lower()
        or q in sec.get("title", "").lower()
        or q in sec.get("description", "").lower()
    ]



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


DISPUTE_CATEGORIES = {
    "digilocker_rejection": {
        "title": "Refusal of DigiLocker / mParivahan Electronic Documents",
        "statutory_authority": "Rule 139 CMVR 1989 read with MoRTH Notification RT-11036/64/2017-MVL and Section 4 IT Act 2000",
        "grounds": (
            "The inspecting officer refused to acknowledge or accept original electronic vehicle documents "
            "(Driving Licence / Registration Certificate / Insurance) presented via the Government of India's "
            "DigiLocker / mParivahan mobile applications, in contravention of Rule 139 of the Central Motor Vehicles Rules "
            "and statutory binding MoRTH notifications."
        ),
        "prayer": (
            "It is respectfully requested that the impugned e-challan be immediately withdrawn and cancelled, "
            "as electronic documents presented in DigiLocker carry full statutory equivalence to physical documents."
        ),
    },
    "unapplied_compounding": {
        "title": "Failure to Apply Section 200 State Compounding Gazette Rate",
        "statutory_authority": "Section 200 Motor Vehicles Act 1988 and relevant State Gazette Notification",
        "grounds": (
            "The issued e-challan levied the maximum central statutory fine without applying the compounding reduction "
            "specifically notified by the State Government under Section 200 of the Motor Vehicles Act 1988."
        ),
        "prayer": (
            "It is respectfully requested that the challan amount be revised downward in accordance with the official "
            "State Gazette Notification issued under Section 200 MVA, or rectified on the e-Challan portal."
        ),
    },
    "grace_period_demand": {
        "title": "Denial of 15-Day Document Production Grace Period",
        "statutory_authority": "Section 130(1) & 130(4) Motor Vehicles Act 1988 read with Rule 139 CMVR",
        "grounds": (
            "The motorist was not provided the statutory 15-day window to produce physical vehicle documents at the "
            "police station or designated enforcement authority, and was summarily penalized on the spot."
        ),
        "prayer": (
            "It is requested that the citizen be afforded the statutory 15-day period under Section 130(4) to produce "
            "valid original documents, and upon satisfactory verification, the challan be dropped."
        ),
    },
    "wrong_vehicle_or_cloned_plate": {
        "title": "Mismatched Vehicle, Incorrect OCR, or Suspected Cloned Plate",
        "statutory_authority": "Section 136A MVA 1988 (Electronic Monitoring) & Principles of Natural Justice",
        "grounds": (
            "The alleged offence was recorded incorrectly against the vehicle registration due to automated camera OCR "
            "errors, mismatched vehicle make/model, or unauthorized duplicate/cloned number plate usage by an unknown third party."
        ),
        "prayer": (
            "It is requested that photographic and video evidence captured by the ANPR camera system be manually examined "
            "to verify vehicle make, model, and chassis characteristics, and the erroneous challan be revoked."
        ),
    },
}


def generate_dispute_representation(
    citizen_name: str,
    vehicle_number: str,
    challan_number: str,
    challan_date: str,
    state: str,
    issuing_authority: str,
    dispute_type: str,
    violation_key: str | None = None,
    additional_facts: str | None = None,
) -> str:
    """Generate a formal statutory representation letter to dispute an erroneous or improper e-challan."""
    for field_name, val in [
        ("citizen_name", citizen_name),
        ("vehicle_number", vehicle_number),
        ("challan_number", challan_number),
        ("challan_date", challan_date),
        ("state", state),
        ("issuing_authority", issuing_authority),
        ("dispute_type", dispute_type),
    ]:
        if not isinstance(val, str) or not val.strip():
            raise CalculatorInputError(f"Field '{field_name}' must be a non-empty string")

    if state not in STATE_DATA:
        raise CalculatorInputError(f"Unknown state or Union Territory: {state}")

    if dispute_type not in DISPUTE_CATEGORIES:
        raise CalculatorInputError(
            f"Unknown dispute type '{dispute_type}'. Allowed types: {sorted(DISPUTE_CATEGORIES.keys())}"
        )

    dispute_meta = DISPUTE_CATEGORIES[dispute_type]
    state_rec = STATE_DATA[state]
    gazette_ref = ""
    if dispute_type == "unapplied_compounding" and state_rec.get("notification_id"):
        gazette_ref = (
            f"\n- State Gazette Notification: {state_rec['notification_id']} "
            f"(Effective Date: {state_rec.get('effective_date', 'N/A')}, Jurisdiction: {state_rec.get('jurisdiction', state)})"
        )

    offence_detail = ""
    if violation_key:
        if violation_key not in NATIONAL_FINES:
            raise CalculatorInputError(f"Unknown violation: {violation_key}")
        fine_rec = NATIONAL_FINES[violation_key]
        offence_detail = (
            f"\nAlleged Offence: {fine_rec['description']} "
            f"(Rule Section: {fine_rec['rule_section']}, Charging Section: {fine_rec['penalty_section']}, Reference Base Fine: ₹{fine_rec['fine']:,})"
        )

    additional_section = ""
    if additional_facts and additional_facts.strip():
        additional_section = f"\nAdditional Facts & Narrative:\n{additional_facts.strip()}\n"

    letter = f"""FORMAL LEGAL REPRESENTATION / GRIEVANCE UNDER THE MOTOR VEHICLES ACT, 1988
================================================================================

To,
The Competent Enforcement Authority / Grievance Redressal Cell,
{issuing_authority.strip()},
{state}.

Subject: Formal Representation against erroneous/improper e-Challan No. {challan_number.strip()}
Reference: Vehicle Registration No.: {vehicle_number.strip().upper()}
Date of Impugned Challan: {challan_date.strip()}
Grievance Category: {dispute_meta['title']}

Respected Authority,

I, {citizen_name.strip()}, hereby submit this formal statutory representation with respect to the above-referenced e-challan issued against my motor vehicle.

1. STATEMENT OF FACTS:
On {challan_date.strip()}, the aforementioned e-challan was generated against vehicle registration {vehicle_number.strip().upper()} under the jurisdiction of {issuing_authority.strip()}.{offence_detail}

2. STATUTORY GROUNDS & LEGAL DEFENCE:
{dispute_meta['grounds']}

Statutory Basis:
- Primary Legal Authority: {dispute_meta['statutory_authority']}{gazette_ref}
{additional_section}
3. PRAYER / RELIEF SOUGHT:
In light of the statutory provisions, binding MoRTH notifications, and state government gazette orders cited above, {dispute_meta['prayer']}

I reserve the right to seek further judicial remedies before the Hon'ble Virtual Court or regular jurisdictional Metropolitan / Judicial Magistrate if this arbitrary challan is not rectified administratively.

Yours sincerely,

_______________________________
Name: {citizen_name.strip()}
Vehicle No: {vehicle_number.strip().upper()}
Date: {challan_date.strip()}
State: {state}
Generated via DriveLegal India (Civic Legal Tech Platform)
"""
    return letter.strip()


def audit_challan_batch(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit a batch of commercial fleet or transport challans against Section 200 state compounding rates.

    Detects overcharges where central statutory maximums were levied despite valid state compounding schedules,
    identifies non-compoundable offences requiring court adjudication, and aggregates financial audit totals.
    """
    if not isinstance(records, list) or not records:
        raise CalculatorInputError("At least one challan record is required for fleet batch audit")

    audited_rows = []
    total_paid = 0.0
    total_legally_due = 0.0
    total_overcharge = 0.0
    overcharged_count = 0
    compliant_count = 0
    court_only_count = 0
    undercharged_count = 0

    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise CalculatorInputError(f"Record {idx} must be a dictionary")

        challan_id = str(rec.get("challan_id") or f"CH-{idx+1}").strip()
        veh_no = str(rec.get("vehicle_number") or f"VEH-{idx+1}").strip().upper()
        veh_type = str(rec.get("vehicle_type") or "").strip()
        state = str(rec.get("state") or "").strip()
        v_key = str(rec.get("violation_key") or "").strip()

        try:
            amount_paid = float(rec.get("amount_paid", 0.0))
        except (TypeError, ValueError) as exc:
            raise CalculatorInputError(f"Record {idx} ({challan_id}) has invalid numeric amount_paid") from exc

        if not math.isfinite(amount_paid) or amount_paid < 0:
            raise CalculatorInputError(f"Record {idx} ({challan_id}) amount_paid must be a finite non-negative number")

        quantity = rec.get("quantity")
        repeat = bool(rec.get("repeat", False))

        calc_res = calculate_fine(v_key, veh_type, state, repeat=repeat, quantity=quantity)
        fine_rec = NATIONAL_FINES[v_key]
        compounded_fee = calc_res.get("compounding_fee")

        if compounded_fee is not None:
            legally_due = float(compounded_fee)
        else:
            legally_due = float(calc_res["total"])

        diff = round(amount_paid - legally_due, 2)
        if compounded_fee is None and fine_rec.get("repeat_policy") == "explicit" and v_key == "drunk_driving":
            audit_status = "COURT_ONLY"
            notes = "Non-compoundable under Section 200 MVA; court adjudication mandatory."
            court_only_count += 1
        elif diff > 0:
            audit_status = "OVERCHARGED"
            notes = f"Overcharged by ₹{diff:,.2f}; state compounding rate (₹{legally_due:,.2f}) was not applied."
            overcharged_count += 1
            total_overcharge += diff
        elif diff == 0:
            audit_status = "COMPLIANT"
            notes = "Challan amount accurately matches legal statutory/compounding rate."
            compliant_count += 1
        else:
            audit_status = "UNDERCHARGED"
            notes = f"Paid ₹{amount_paid:,.2f}, below statutory rate of ₹{legally_due:,.2f}."
            undercharged_count += 1

        total_paid += amount_paid
        total_legally_due += legally_due

        audited_rows.append({
            "challan_id": challan_id,
            "vehicle_number": veh_no,
            "vehicle_type": veh_type,
            "violation_key": v_key,
            "violation_description": fine_rec["description"],
            "state": state,
            "amount_paid": round(amount_paid, 2),
            "statutory_fine": round(calc_res["total"], 2),
            "compounded_fine": compounded_fee,
            "legally_due": round(legally_due, 2),
            "overcharge_amount": max(0.0, diff),
            "audit_status": audit_status,
            "notification_id": calc_res.get("compounding_notification_id"),
            "notes": notes,
        })

    return {
        "total_challans_audited": len(audited_rows),
        "total_amount_paid": round(total_paid, 2),
        "total_legally_due": round(total_legally_due, 2),
        "total_potential_overcharges": round(total_overcharge, 2),
        "overcharged_count": overcharged_count,
        "compliant_count": compliant_count,
        "court_only_count": court_only_count,
        "undercharged_count": undercharged_count,
        "records": audited_rows,
    }

def parse_vehicle_registration(registration_number: str) -> dict[str, Any]:
    """Parse and resolve an Indian vehicle registration number or Bharat (BH) Series.

    Identifies State, RTO division, registration year (for BH), series, and
    provides the corresponding jurisdiction information.
    """
    if not isinstance(registration_number, str):
        raise CalculatorInputError("Vehicle registration number must be a string.")

    cleaned = re.sub(r"[^A-Za-z0-9]", "", registration_number).upper()
    if not cleaned:
        return {
            "input_registration": registration_number,
            "normalized_registration": "",
            "is_valid": False,
            "is_bh_series": False,
            "registration_year": None,
            "state_code": None,
            "state_name": None,
            "rto_code": None,
            "rto_name": None,
            "series_code": None,
            "vehicle_unique_number": None,
            "jurisdiction_type": "unknown",
            "statutory_note": "Registration number cannot be empty.",
        }

    # 1. Check for Central Bharat (BH) Series: YY BH #### XX
    bh_match = re.match(r"^(\d{2})BH(\d{4})([A-Z]{1,2})$", cleaned)
    if bh_match:
        yy, num, series = bh_match.groups()
        full_year = f"20{yy}"
        bh_info = RTO_DIRECTORY.get("bh_series", {})
        return {
            "input_registration": registration_number,
            "normalized_registration": cleaned,
            "is_valid": True,
            "is_bh_series": True,
            "registration_year": full_year,
            "state_code": "BH",
            "state_name": bh_info.get("default_state_for_rules", "Delhi"),
            "rto_code": "BH",
            "rto_name": bh_info.get("name", "Bharat Series (BH)"),
            "series_code": series,
            "vehicle_unique_number": num,
            "jurisdiction_type": "central_bh",
            "statutory_note": (
                f"Registered in {full_year} under Central Bharat Series (Notification G.S.R. 594(E)). "
                "Exempt from interstate re-registration under Rule 51B of Central Motor Vehicles Rules."
            ),
        }

    # 2. Check for Standard State Series: SS DD [SSS] ####
    state_match = re.match(r"^([A-Z]{2})(\d{1,2})([A-Z]{0,3})(\d{1,4})$", cleaned)
    if state_match:
        st_code, rto_num, series, num = state_match.groups()
        rto_num_padded = rto_num.zfill(2)
        state_codes = RTO_DIRECTORY.get("state_codes", {})
        rto_divs = RTO_DIRECTORY.get("rto_divisions", {}).get(st_code, {})

        if st_code in state_codes:
            state_name = state_codes[st_code]
            rto_name = rto_divs.get(rto_num_padded) or rto_divs.get(rto_num) or f"RTO District {rto_num_padded}"
            return {
                "input_registration": registration_number,
                "normalized_registration": cleaned,
                "is_valid": True,
                "is_bh_series": False,
                "registration_year": None,
                "state_code": st_code,
                "state_name": state_name,
                "rto_code": rto_num_padded,
                "rto_name": rto_name,
                "series_code": series if series else None,
                "vehicle_unique_number": num,
                "jurisdiction_type": "state",
                "statutory_note": f"Registered in {state_name} under RTO {rto_name} ({st_code}-{rto_num_padded}).",
            }

    return {
        "input_registration": registration_number,
        "normalized_registration": cleaned,
        "is_valid": False,
        "is_bh_series": False,
        "registration_year": None,
        "state_code": None,
        "state_name": None,
        "rto_code": None,
        "rto_name": None,
        "series_code": None,
        "vehicle_unique_number": None,
        "jurisdiction_type": "unknown",
        "statutory_note": "Registration format not recognized under standard State or Bharat (BH) formats.",
    }

def generate_dispute_representation_html(
    citizen_name: str,
    vehicle_number: str,
    challan_number: str,
    challan_date: str,
    state: str,
    issuing_authority: str,
    dispute_type: str,
    violation_key: str | None = None,
    additional_facts: str | None = None,
) -> str:
    """Generate a clean, printable court/commissioner-formatted HTML legal representation notice."""
    plain_text = generate_dispute_representation(
        citizen_name=citizen_name,
        vehicle_number=vehicle_number,
        challan_number=challan_number,
        challan_date=challan_date,
        state=state,
        issuing_authority=issuing_authority,
        dispute_type=dispute_type,
        violation_key=violation_key,
        additional_facts=additional_facts,
    )
    meta = DISPUTE_CATEGORIES.get(dispute_type, {})

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Legal Representation - {challan_number}</title>
<style>
  body {{ font-family: 'Times New Roman', Times, serif; line-height: 1.6; color: #111; margin: 40px; }}
  .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 12px; margin-bottom: 24px; }}
  .header h2 {{ margin: 0; text-transform: uppercase; font-size: 1.3rem; letter-spacing: 1px; }}
  .header p {{ margin: 4px 0 0; font-size: 0.95rem; color: #444; }}
  .meta-box {{ background: #f9f9f9; border: 1px solid #ddd; padding: 12px 18px; margin-bottom: 20px; font-size: 0.95rem; }}
  .meta-box table {{ width: 100%; border-collapse: collapse; }}
  .meta-box td {{ padding: 4px 8px; vertical-align: top; }}
  .content {{ font-size: 1rem; text-align: justify; }}
  .citations {{ background: #f4f6f9; border-left: 4px solid #1a237e; padding: 10px 15px; margin: 15px 0; font-size: 0.95rem; }}
  .signature {{ margin-top: 50px; display: flex; justify-content: space-between; }}
  .sig-line {{ border-top: 1px solid #333; width: 220px; text-align: center; padding-top: 6px; font-weight: bold; }}
  @media print {{
    body {{ margin: 15mm 20mm; }}
    .no-print {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h2>Statutory Representation & Legal Dispute Notice</h2>
  <p>Under the Motor Vehicles Act, 1988 (as amended) & Central Motor Vehicles Rules, 1989</p>
</div>

<div class="meta-box">
  <table>
    <tr><td><strong>To:</strong> {issuing_authority}</td><td><strong>Date:</strong> {challan_date}</td></tr>
    <tr><td><strong>Applicant:</strong> {citizen_name}</td><td><strong>State / UT:</strong> {state}</td></tr>
    <tr><td><strong>Vehicle No:</strong> {vehicle_number}</td><td><strong>Challan No:</strong> {challan_number}</td></tr>
    <tr><td colspan="2"><strong>Grounds:</strong> {meta.get('title', dispute_type)}</td></tr>
  </table>
</div>

<div class="content">
  <p><strong>SUBJECT:</strong> FORMAL REPRESENTATION AGAINST UNJUSTIFIED E-CHALLAN NO. {challan_number} ISSUED FOR VEHICLE {vehicle_number}.</p>
  
  <p>Respected Authority,</p>
  
  <p>I, <strong>{citizen_name}</strong>, registered owner/driver of motor vehicle bearing registration number <strong>{vehicle_number}</strong>, hereby submit this formal legal representation challenging the validity of e-Challan No. <strong>{challan_number}</strong> dated <strong>{challan_date}</strong> issued by your jurisdiction.</p>

  <div class="citations">
    <strong>STATUTORY BASIS & LEGAL PROVISIONS:</strong><br>
    {meta.get('statutory_authority', 'Motor Vehicles Act, 1988')}
  </div>

  <p><strong>GROUNDS OF REPRESENTATION:</strong></p>
  <p>{meta.get('grounds', '')}</p>
"""
    if additional_facts and additional_facts.strip():
        html_content += f"""
  <p><strong>PARTICULAR FACTS OF THE INCIDENT:</strong></p>
  <p>{additional_facts.strip()}</p>
"""

    html_content += f"""
  <p><strong>PRAYER / RELIEF SOUGHT:</strong></p>
  <p>In light of the statutory mandates, binding notifications, and lack of sustainable legal basis for the penalty as charged, it is respectfully prayed that your office may:</p>
  <ul>
    <li>Review the digital and video/photographic records associated with Challan No. {challan_number}.</li>
    <li>Revoke, cancel, or re-compound the fine in strict compliance with the statutory provisions cited above.</li>
    <li>Provide written communication of the disposal of this grievance.</li>
  </ul>

  <div class="signature">
    <div>Date: {challan_date}<br>Place: {state}</div>
    <div>
      <div class="sig-line">{citizen_name}</div>
      Applicant / Motorist
    </div>
  </div>
</div>
</body>
</html>"""
    return html_content

