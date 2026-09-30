"""Commercial driver rest-hours fatigue auditor (MTWA 1961) and HAZCHEM transport safety diagnostic (CMVR 129-137).

Self-contained feature module: models, data loading, logic and API router live
here so this feature never edits app_core.py, api.py or models.py.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

import app_core
from app_core import CalculatorInputError, _read_json, _require


# --- Commercial Driver Rest Hours & HAZCHEM Carriage Models ---
class DriverHoursViolationItem(BaseModel):
    """Specific statutory working hours violation under MTWA 1961."""
    model_config = ConfigDict(frozen=True)

    section: str
    issue: str
    severity: Literal["HIGH", "CRITICAL"]


class DriverFatigueAuditRequest(BaseModel):
    """Input payload to audit commercial driver working hours."""
    model_config = ConfigDict(extra="forbid")

    continuous_driving_hours: float = Field(..., ge=0)
    daily_working_hours: float = Field(..., ge=0)
    weekly_working_hours: float = Field(..., ge=0)
    rest_interval_minutes: int = Field(..., ge=0)
    is_long_distance: bool = False


class DriverFatigueAuditResponse(BaseModel):
    """Compliance result of driver fatigue and rest hours audit."""
    model_config = ConfigDict(frozen=True)

    continuous_driving_hours: float
    daily_working_hours: float
    weekly_working_hours: float
    rest_interval_minutes: int
    is_long_distance: bool
    compliance_status: Literal["COMPLIANT", "MODERATE_FATIGUE_RISK", "UNLAWFUL_EXCESSIVE_HOURS"]
    statutory_limits: dict[str, float]
    violations_count: int
    violations: list[DriverHoursViolationItem]
    safety_advisory: str
    statutory_authority: dict[str, str]


class HazchemChecklistItem(BaseModel):
    """Specific HAZCHEM safety equipment verification item."""
    model_config = ConfigDict(frozen=True)

    item: str
    rule: str
    satisfied: bool
    weight: int


class HazchemCarriageAuditRequest(BaseModel):
    """Input payload to audit dangerous goods transport compliance."""
    model_config = ConfigDict(extra="forbid")

    un_class_id: int = Field(..., ge=1, le=9)
    has_eip_display: bool = False
    has_tremcard: bool = False
    has_hazardous_dl_endorsement: bool = False
    has_spark_arrester: bool = False
    has_fire_extinguisher: bool = False


class HazchemCarriageAuditResponse(BaseModel):
    """Hazardous goods transport compliance audit response."""
    model_config = ConfigDict(frozen=True)

    un_class_id: int
    hazard_class_name: str
    cargo_example: str
    compliance_score: int = Field(..., ge=0, le=100)
    compliance_status: Literal["FULLY_COMPLIANT", "SERIOUS_SAFETY_DEFICIT", "CRITICAL_PROSECUTION_RISK"]
    checklist: list[HazchemChecklistItem]
    missing_items: list[str]
    statutory_advisory: str
    penalty_risk: str
    statutory_authority: dict[str, str]


def _validate_transport_worker_regulations(data: Any) -> None:
    _require(isinstance(data, dict), "transport_worker_regulations must be an object")
    _require("statutory_framework" in data and isinstance(data["statutory_framework"], dict), "missing statutory_framework")
    _require("statutory_limits" in data and isinstance(data["statutory_limits"], dict), "missing statutory_limits")


def _validate_hazchem_safety_rules(data: Any) -> None:
    _require(isinstance(data, dict), "hazchem_safety_rules must be an object")
    _require("statutory_framework" in data and isinstance(data["statutory_framework"], dict), "missing statutory_framework")
    _require("un_hazard_classes" in data and isinstance(data["un_hazard_classes"], dict), "missing un_hazard_classes")


TRANSPORT_WORKER_REGULATIONS = _read_json("transport_worker_regulations.json")
_validate_transport_worker_regulations(TRANSPORT_WORKER_REGULATIONS)
HAZCHEM_SAFETY_RULES = _read_json("hazchem_safety_rules.json")
_validate_hazchem_safety_rules(HAZCHEM_SAFETY_RULES)


# ---------------------------------------------------------------------------
# Commercial Driver Fatigue (MTWA 1961) & HAZCHEM Carriage Diagnostic
# ---------------------------------------------------------------------------
def audit_driver_fatigue_hours(
    continuous_driving_hours: float,
    daily_working_hours: float,
    weekly_working_hours: float,
    rest_interval_minutes: int,
    is_long_distance: bool = False,
) -> dict[str, Any]:
    """Audit commercial driver working hours and fatigue compliance under Motor Transport Workers Act 1961."""
    if not isinstance(continuous_driving_hours, (int, float)) or continuous_driving_hours < 0:
        raise CalculatorInputError("Continuous driving hours must be a non-negative number.")
    if not isinstance(daily_working_hours, (int, float)) or daily_working_hours < 0:
        raise CalculatorInputError("Daily working hours must be a non-negative number.")
    if not isinstance(weekly_working_hours, (int, float)) or weekly_working_hours < 0:
        raise CalculatorInputError("Weekly working hours must be a non-negative number.")
    if not isinstance(rest_interval_minutes, int) or rest_interval_minutes < 0:
        raise CalculatorInputError("Rest interval must be a non-negative integer of minutes.")

    rules = TRANSPORT_WORKER_REGULATIONS
    limits = rules.get("statutory_limits", {})
    max_continuous = limits.get("max_continuous_driving_hours", 5.0)
    min_rest = limits.get("min_rest_interval_minutes", 30)
    max_daily = limits.get("max_daily_hours_long_distance", 10.0) if is_long_distance else limits.get("max_daily_hours_standard", 8.0)
    max_weekly = limits.get("max_weekly_hours", 48.0)

    violations = []
    if continuous_driving_hours > max_continuous and rest_interval_minutes < min_rest:
        violations.append({
            "section": "Section 15, Motor Transport Workers Act, 1961",
            "issue": f"Continuous driving ({continuous_driving_hours}h) exceeds the statutory 5.0-hour limit without at least 30 minutes rest (recorded: {rest_interval_minutes}m).",
            "severity": "CRITICAL",
        })

    if daily_working_hours > max_daily:
        violations.append({
            "section": "Section 13, Motor Transport Workers Act, 1961",
            "issue": f"Daily hours ({daily_working_hours}h) exceed statutory daily limit ({max_daily}h for {'long-distance' if is_long_distance else 'standard'} routes).",
            "severity": "HIGH",
        })

    if weekly_working_hours > max_weekly:
        violations.append({
            "section": "Section 13, Motor Transport Workers Act, 1961",
            "issue": f"Weekly working hours ({weekly_working_hours}h) exceed the statutory 48.0-hour weekly ceiling.",
            "severity": "HIGH",
        })

    if not violations:
        compliance_status = "COMPLIANT"
        safety_advisory = "Working hours and rest intervals satisfy statutory limits under the Motor Transport Workers Act, 1961."
    elif len(violations) == 1 and violations[0]["severity"] == "HIGH":
        compliance_status = "MODERATE_FATIGUE_RISK"
        safety_advisory = "Driver hours exceed statutory limits. Provide immediate compensatory rest to mitigate crash risk."
    else:
        compliance_status = "UNLAWFUL_EXCESSIVE_HOURS"
        safety_advisory = (
            "Severe violation of statutory rest mandates. Operating under these conditions invites employer prosecution "
            "under Section 31 MTWA and constitutes gross negligence in the event of an accident."
        )

    return {
        "continuous_driving_hours": float(continuous_driving_hours),
        "daily_working_hours": float(daily_working_hours),
        "weekly_working_hours": float(weekly_working_hours),
        "rest_interval_minutes": rest_interval_minutes,
        "is_long_distance": is_long_distance,
        "compliance_status": compliance_status,
        "statutory_limits": {
            "max_continuous_hours": max_continuous,
            "min_rest_minutes": min_rest,
            "max_daily_hours": max_daily,
            "max_weekly_hours": max_weekly,
        },
        "violations_count": len(violations),
        "violations": violations,
        "safety_advisory": safety_advisory,
        "statutory_authority": rules.get("statutory_framework", {}),
    }


def audit_hazchem_carriage_compliance(
    un_class_id: int,
    has_eip_display: bool,
    has_tremcard: bool,
    has_hazardous_dl_endorsement: bool,
    has_spark_arrester: bool,
    has_fire_extinguisher: bool,
) -> dict[str, Any]:
    """Audit vehicle and driver compliance for hazardous materials transport under CMVR Rules 129 to 137."""
    rules = HAZCHEM_SAFETY_RULES
    classes = rules.get("un_hazard_classes", {})
    weights = rules.get("safety_equipment_weights", {})
    class_key = str(un_class_id)

    if class_key not in classes:
        raise CalculatorInputError(f"Invalid UN Class ID: {un_class_id}. Valid classes are 1 through 9.")

    class_info = classes[class_key]
    checklist = [
        {"item": "Emergency Information Panel (EIP)", "rule": "CMVR Rule 129", "satisfied": has_eip_display, "weight": weights.get("has_eip_display", 25)},
        {"item": "Transport Emergency Card (TREMCARD)", "rule": "CMVR Rule 131", "satisfied": has_tremcard, "weight": weights.get("has_tremcard", 20)},
        {"item": "Rule 9 Hazardous DL Endorsement", "rule": "CMVR Rule 9", "satisfied": has_hazardous_dl_endorsement, "weight": weights.get("has_hazardous_dl_endorsement", 25)},
        {"item": "Spark Arrester", "rule": "CMVR Rule 133", "satisfied": has_spark_arrester, "weight": weights.get("has_spark_arrester", 15)},
        {"item": "Serviceable Fire Extinguisher", "rule": "CMVR Rule 134", "satisfied": has_fire_extinguisher, "weight": weights.get("has_fire_extinguisher", 15)},
    ]

    total_score = sum(item["weight"] for item in checklist if item["satisfied"])
    deficiencies = [item["item"] for item in checklist if not item["satisfied"]]

    if total_score == 100:
        compliance_status = "FULLY_COMPLIANT"
        advisory = "Vehicle and driver satisfy all statutory safety equipment and certification mandates under CMVR Rules 129-137."
        penalty_risk = "None"
    elif total_score >= 60:
        compliance_status = "SERIOUS_SAFETY_DEFICIT"
        advisory = f"Missing mandatory equipment: {', '.join(deficiencies)}. Rectify before vehicle dispatch."
        penalty_risk = "Vehicle detention and compounding under CMVR Rules 129-137."
    else:
        compliance_status = "CRITICAL_PROSECUTION_RISK"
        advisory = (
            f"Critically deficient carriage of UN Class {un_class_id} ({class_info['name']}). "
            "Presents immediate public danger. Liable to ₹10,000 fine, 1 year imprisonment under Sec 190(3) MVA, and seizure."
        )
        penalty_risk = "Section 190(3) MVA 1988 (fine up to ₹10,000 and/or imprisonment up to 1 year)."

    return {
        "un_class_id": un_class_id,
        "hazard_class_name": class_info["name"],
        "cargo_example": class_info["example"],
        "compliance_score": total_score,
        "compliance_status": compliance_status,
        "checklist": checklist,
        "missing_items": deficiencies,
        "statutory_advisory": advisory,
        "penalty_risk": penalty_risk,
        "statutory_authority": rules.get("statutory_framework", {}),
    }


router = APIRouter()


@router.post(
    "/api/v1/commercial/audit-driver-hours",
    response_model=DriverFatigueAuditResponse,
    tags=["commercial_compliance"],
    summary="Audit Commercial Driver Rest Hours & Fatigue (MTWA 1961)",
)
def audit_driver_hours_endpoint(request: DriverFatigueAuditRequest) -> DriverFatigueAuditResponse:
    """Audit driver continuous hours and rest intervals against Motor Transport Workers Act statutory limits."""
    try:
        result = audit_driver_fatigue_hours(
            continuous_driving_hours=request.continuous_driving_hours,
            daily_working_hours=request.daily_working_hours,
            weekly_working_hours=request.weekly_working_hours,
            rest_interval_minutes=request.rest_interval_minutes,
            is_long_distance=request.is_long_distance,
        )
        return DriverFatigueAuditResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/commercial/audit-hazchem-carriage",
    response_model=HazchemCarriageAuditResponse,
    tags=["commercial_compliance"],
    summary="Audit HAZCHEM Carriage Safety Equipment (CMVR Rules 129-137)",
)
def audit_hazchem_endpoint(request: HazchemCarriageAuditRequest) -> HazchemCarriageAuditResponse:
    """Audit hazardous materials transport against UN Classes 1-9, EIP, TREMCARD, and Rule 9 endorsements."""
    try:
        result = audit_hazchem_carriage_compliance(
            un_class_id=request.un_class_id,
            has_eip_display=request.has_eip_display,
            has_tremcard=request.has_tremcard,
            has_hazardous_dl_endorsement=request.has_hazardous_dl_endorsement,
            has_spark_arrester=request.has_spark_arrester,
            has_fire_extinguisher=request.has_fire_extinguisher,
        )
        return HazchemCarriageAuditResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
