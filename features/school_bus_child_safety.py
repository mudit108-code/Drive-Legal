"""School bus 15-point safety auditor (AIS-063), child restraint engine (Sec 194B(2)) and low-speed e-bike exemption (CMVR 2(u)).

Self-contained feature module: models, data loading, logic and API router live
here so this feature never edits app_core.py, api.py or models.py.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

import app_core
from app_core import CalculatorInputError, _read_json, _require


# --- School Bus Safety (AIS-063), Child Restraint & Micromobility Models ---
class SchoolBusChecklistItem(BaseModel):
    """Specific school bus safety checklist item."""
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    description: str
    weight: int
    satisfied: bool


class SchoolBusSafetyAuditRequest(BaseModel):
    """Input payload to audit school bus safety compliance."""
    model_config = ConfigDict(extra="forbid")

    bus_registration_no: str = Field(..., min_length=2, max_length=50)
    checklist: dict[str, bool] = Field(default_factory=dict)


class SchoolBusSafetyAuditResponse(BaseModel):
    """School bus safety compliance audit results."""
    model_config = ConfigDict(frozen=True)

    bus_registration_no: str
    compliance_score: int = Field(..., ge=0, le=100)
    compliance_status: Literal["FULLY_COMPLIANT", "DEFECTIVE_NEEDS_RECTIFICATION", "FATAL_SAFETY_HAZARD"]
    passed_items_count: int
    failed_items_count: int
    passed_items: list[SchoolBusChecklistItem]
    failed_items: list[SchoolBusChecklistItem]
    safety_advisory: str
    statutory_authority: dict[str, str]


class ChildRestraintAdvisoryRequest(BaseModel):
    """Input payload to query child safety restraint requirements."""
    model_config = ConfigDict(extra="forbid")

    child_age_years: float = Field(..., ge=0, le=18)
    vehicle_category: str = Field("Car", min_length=2, max_length=50)


class ChildRestraintAdvisoryResponse(BaseModel):
    """Child restraint advisory under Sec 194B(2) MVA & CMVR 138(7)."""
    model_config = ConfigDict(frozen=True)

    child_age_years: float
    vehicle_category: str
    is_two_wheeler: bool
    recommended_system: str
    statutory_mandate: str
    instructions: list[str]
    statutory_penalty: str
    speed_limit_cap_kmh: int | None = None


class MicromobilityExemptionRequest(BaseModel):
    """Input payload to evaluate low-speed electric cycle exemption."""
    model_config = ConfigDict(extra="forbid")

    motor_power_watts: float = Field(..., ge=0)
    max_speed_kmh: float = Field(..., ge=0)


class MicromobilityExemptionResponse(BaseModel):
    """Statutory exemption determination under CMVR Rule 2(u)."""
    model_config = ConfigDict(frozen=True)

    motor_power_watts: float
    max_speed_kmh: float
    is_power_compliant: bool
    is_speed_compliant: bool
    is_exempt_from_mva: bool
    legal_status: Literal["EXEMPT_FROM_MVA", "FULL_MVA_REGULATION_APPLIES"]
    vehicle_classification: str
    legal_advisory: str
    statutory_exemptions: dict[str, bool]
    statutory_framework: dict[str, str]


def _validate_school_bus_standards(data: Any) -> None:
    _require(isinstance(data, dict), "school_bus_standards must be an object")
    _require("statutory_framework" in data and isinstance(data["statutory_framework"], dict), "missing statutory_framework")
    _require("checklist_items" in data and isinstance(data["checklist_items"], list), "missing checklist_items")


def _validate_child_restraint_rules(data: Any) -> None:
    _require(isinstance(data, dict), "child_restraint_rules must be an object")
    _require("statutory_framework" in data and isinstance(data["statutory_framework"], dict), "missing statutory_framework")
    _require("guidelines_by_age" in data and isinstance(data["guidelines_by_age"], dict), "missing guidelines_by_age")


def _validate_micromobility_rules(data: Any) -> None:
    _require(isinstance(data, dict), "micromobility_rules must be an object")
    _require("statutory_framework" in data and isinstance(data["statutory_framework"], dict), "missing statutory_framework")
    _require("statutory_ceilings" in data and isinstance(data["statutory_ceilings"], dict), "missing statutory_ceilings")


SCHOOL_BUS_STANDARDS = _read_json("school_bus_standards.json")
_validate_school_bus_standards(SCHOOL_BUS_STANDARDS)
CHILD_RESTRAINT_RULES = _read_json("child_restraint_rules.json")
_validate_child_restraint_rules(CHILD_RESTRAINT_RULES)
MICROMOBILITY_RULES = _read_json("micromobility_rules.json")
_validate_micromobility_rules(MICROMOBILITY_RULES)


# ---------------------------------------------------------------------------
# School Bus Safety (AIS-063), Child Restraints & Micromobility Exemption Engine
# ---------------------------------------------------------------------------
def audit_school_bus_safety(bus_registration_no: str, checklist: dict[str, bool]) -> dict[str, Any]:
    """Audit school bus safety compliance against AIS-063 and Supreme Court directives."""
    if not isinstance(bus_registration_no, str) or not bus_registration_no.strip():
        raise CalculatorInputError("Bus registration number must be a non-empty string.")
    if not isinstance(checklist, dict):
        raise CalculatorInputError("Checklist must be a dictionary of item responses.")

    rules = SCHOOL_BUS_STANDARDS
    items = rules.get("checklist_items", [])

    passed_items = []
    failed_items = []
    total_score = 0

    for item in items:
        item_id = item["id"]
        satisfied = bool(checklist.get(item_id, False))
        entry = {
            "id": item_id,
            "title": item["title"],
            "description": item["description"],
            "weight": item["weight"],
            "satisfied": satisfied,
        }
        if satisfied:
            total_score += item["weight"]
            passed_items.append(entry)
        else:
            failed_items.append(entry)

    total_score = min(max(total_score, 0), 100)

    if total_score == 100:
        compliance_status = "FULLY_COMPLIANT"
        safety_advisory = "School bus complies with all AIS-063 and Supreme Court safety mandates."
    elif total_score >= 70:
        compliance_status = "DEFECTIVE_NEEDS_RECTIFICATION"
        safety_advisory = "School bus has non-fatal equipment deficiencies. Rectify within 7 days."
    else:
        compliance_status = "FATAL_SAFETY_HAZARD"
        safety_advisory = (
            "Severe non-compliance with school transport safety norms. Vehicle poses grave danger to student passengers "
            "and is liable to immediate impoundment and fitness permit cancellation under Rule 125C CMVR."
        )

    return {
        "bus_registration_no": bus_registration_no.strip(),
        "compliance_score": total_score,
        "compliance_status": compliance_status,
        "passed_items_count": len(passed_items),
        "failed_items_count": len(failed_items),
        "passed_items": passed_items,
        "failed_items": failed_items,
        "safety_advisory": safety_advisory,
        "statutory_authority": rules.get("statutory_framework", {}),
    }


def get_child_restraint_safety_advice(child_age_years: float, vehicle_category: str = "Car") -> dict[str, Any]:
    """Provide statutory child restraint system (CRS) advice and penalty guidelines under Sec 194B(2) MVA."""
    if not isinstance(child_age_years, (int, float)) or child_age_years < 0:
        raise CalculatorInputError("Child age must be a non-negative number.")
    if not isinstance(vehicle_category, str) or not vehicle_category.strip():
        raise CalculatorInputError("Vehicle category must be a non-empty string.")

    rules = CHILD_RESTRAINT_RULES
    framework = rules.get("statutory_framework", {})
    age_guidelines = rules.get("guidelines_by_age", {})
    two_wheeler_rules = rules.get("two_wheeler_pillion_child", {})

    is_two_wheeler = "two" in vehicle_category.lower() or "bike" in vehicle_category.lower() or "scooter" in vehicle_category.lower()

    if is_two_wheeler:
        applicable_mandate = two_wheeler_rules.get("statutory_rule", "Rule 138(7) CMVR 1989")
        if child_age_years < 4.0:
            system_required = "Safety Harness & Child Crash Helmet (BIS/ISI certified)"
            speed_limit_kmh = framework.get("max_two_wheeler_speed_with_child", 40)
            instructions = two_wheeler_rules.get("mandatory_requirements", [])
            penalty = "₹1,000 fine under Sec 194B(2) / Sec 177 MVA plus 3-month DL suspension under Sec 19 MVA."
        else:
            system_required = "Standard Child Crash Helmet (ISI marked)"
            speed_limit_kmh = 50
            instructions = ["Child must wear ISI certified helmet and hold rider securely or use safety footrests."]
            penalty = "Fine under Section 194D MVA (₹1,000) for unhelmeted riding."
    else:
        speed_limit_kmh = None
        if child_age_years < 2.0:
            bracket = age_guidelines.get("infant", {})
        elif child_age_years < 4.0:
            bracket = age_guidelines.get("toddler", {})
        elif child_age_years < 8.0:
            bracket = age_guidelines.get("young_child", {})
        elif child_age_years <= 14.0:
            bracket = age_guidelines.get("adolescent", {})
        else:
            bracket = {
                "age_range": "Above 14 years",
                "recommended_system": "Standard Adult 3-Point Lap-and-Shoulder Seatbelt",
                "mounting": "Any passenger seating position",
                "legal_mandate": "Section 194B(1) MVA 1988 — Standard seatbelt mandate (₹1,000 fine).",
            }
        system_required = bracket.get("recommended_system", "")
        instructions = [bracket.get("mounting", "")]
        penalty = f"₹{framework.get('penalty_amount', 1000)} under Section 194B(2) MVA 1988" if child_age_years <= 14.0 else "Standard seatbelt fine under Sec 194B(1)"
        applicable_mandate = framework.get("mva_section", "")

    return {
        "child_age_years": float(child_age_years),
        "vehicle_category": vehicle_category.strip(),
        "is_two_wheeler": is_two_wheeler,
        "recommended_system": system_required,
        "statutory_mandate": applicable_mandate,
        "instructions": instructions,
        "statutory_penalty": penalty,
        "speed_limit_cap_kmh": speed_limit_kmh,
    }


def evaluate_micromobility_exemption(motor_power_watts: float, max_speed_kmh: float) -> dict[str, Any]:
    """Evaluate whether an electric two-wheeler qualifies as a non-motor vehicle under CMVR Rule 2(u)."""
    if not isinstance(motor_power_watts, (int, float)) or motor_power_watts < 0:
        raise CalculatorInputError("Motor power must be a non-negative number of watts.")
    if not isinstance(max_speed_kmh, (int, float)) or max_speed_kmh < 0:
        raise CalculatorInputError("Maximum speed must be a non-negative number.")

    rules = MICROMOBILITY_RULES
    ceilings = rules.get("statutory_ceilings", {})
    max_power = ceilings.get("max_continuous_rated_power_watts", 250.0)
    max_speed = ceilings.get("max_cut_off_speed_kmh", 25.0)

    is_power_exempt = motor_power_watts <= max_power
    is_speed_exempt = max_speed_kmh <= max_speed
    is_fully_exempt = is_power_exempt and is_speed_exempt

    if is_fully_exempt:
        classification = "Non-Motorised Electric Cycle / Micro-Mobility Vehicle"
        legal_status = "EXEMPT_FROM_MVA"
        advisory = (
            f"Vehicles with motor power <= {max_power}W and cut-off speed <= {max_speed} km/h are excluded from the definition "
            "of 'Motor Vehicle' under CMVR Rule 2(u). No Driving Licence, Registration, or Road Tax can be demanded by traffic police."
        )
        exemptions = rules.get("legal_exemptions", {})
    else:
        classification = "Motor Vehicle (E-Scooter / Electric Motorcycle)"
        legal_status = "FULL_MVA_REGULATION_APPLIES"
        reasons = []
        if not is_power_exempt:
            reasons.append(f"Motor power ({motor_power_watts}W) exceeds the statutory 250W ceiling")
        if not is_speed_exempt:
            reasons.append(f"Maximum design speed ({max_speed_kmh} km/h) exceeds the statutory 25 km/h limit")
        advisory = (
            f"{' and '.join(reasons)}. This vehicle falls squarely within Section 2(28) MVA. Driving Licence, "
            "High Security Registration Plate (HSRP), valid insurance, and ISI helmet are strictly mandatory."
        )
        exemptions = {
            "driving_licence_required": True,
            "registration_number_plate_required": True,
            "motor_vehicle_road_tax": True,
            "mandatory_third_party_insurance": True,
            "mva_helmet_fine_applicable": True,
        }

    return {
        "motor_power_watts": float(motor_power_watts),
        "max_speed_kmh": float(max_speed_kmh),
        "is_power_compliant": is_power_exempt,
        "is_speed_compliant": is_speed_exempt,
        "is_exempt_from_mva": is_fully_exempt,
        "legal_status": legal_status,
        "vehicle_classification": classification,
        "legal_advisory": advisory,
        "statutory_exemptions": exemptions,
        "statutory_framework": rules.get("statutory_framework", {}),
    }


router = APIRouter()


@router.post(
    "/api/v1/safety/school-bus-audit",
    response_model=SchoolBusSafetyAuditResponse,
    tags=["child_safety"],
    summary="Audit School Bus Safety Compliance (AIS-063 & CMVR 125C)",
)
def audit_school_bus_endpoint(request: SchoolBusSafetyAuditRequest) -> SchoolBusSafetyAuditResponse:
    """Audit school bus safety compliance against Supreme Court guidelines, AIS-063, and CMVR Rule 125C."""
    try:
        result = audit_school_bus_safety(
            bus_registration_no=request.bus_registration_no,
            checklist=request.checklist,
        )
        return SchoolBusSafetyAuditResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/safety/child-restraint-advisory",
    response_model=ChildRestraintAdvisoryResponse,
    tags=["child_safety"],
    summary="Get Child Restraint System (CRS) & Two-Wheeler Safety Advice (Sec 194B(2))",
)
def get_child_restraint_endpoint(request: ChildRestraintAdvisoryRequest) -> ChildRestraintAdvisoryResponse:
    """Provide statutory child restraint seat advice and penalty details under Section 194B(2) MVA and CMVR 138(7)."""
    try:
        result = get_child_restraint_safety_advice(
            child_age_years=request.child_age_years,
            vehicle_category=request.vehicle_category,
        )
        return ChildRestraintAdvisoryResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/safety/micromobility-exemption",
    response_model=MicromobilityExemptionResponse,
    tags=["child_safety"],
    summary="Evaluate Low-Speed Electric Vehicle Exemption (CMVR Rule 2(u))",
)
def evaluate_micromobility_endpoint(request: MicromobilityExemptionRequest) -> MicromobilityExemptionResponse:
    """Evaluate whether an e-cycle/scooter (<=250W, <=25km/h) is statutorily exempt from MVA licence and registration."""
    try:
        result = evaluate_micromobility_exemption(
            motor_power_watts=request.motor_power_watts,
            max_speed_kmh=request.max_speed_kmh,
        )
        return MicromobilityExemptionResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
