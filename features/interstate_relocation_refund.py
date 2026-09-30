"""Inter-state vehicle relocation 12-month rule auditor and pro-rata road tax refund calculator (Sec 47 & 48 MVA).

Self-contained feature module: models, data loading, logic and API router live
here so this feature never edits app_core.py, api.py or models.py.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

import app_core
from app_core import CalculatorInputError, _read_json, _require


# --- Inter-State Vehicle Relocation & Road Tax Refund Models ---
class InterstateRelocationAuditRequest(BaseModel):
    """Input payload to evaluate vehicle inter-state stay compliance under Sec 47 MVA."""
    model_config = ConfigDict(extra="forbid")

    origin_state: str = Field(..., min_length=2, max_length=50)
    destination_state: str = Field(..., min_length=2, max_length=50)
    stay_duration_months: int = Field(..., ge=0, le=240)
    has_noc: bool = False


class InterstateRelocationAuditResponse(BaseModel):
    """Compliance audit under Section 47 (12-month rule) and Section 48 (NOC)."""
    model_config = ConfigDict(frozen=True)

    origin_state: str
    destination_state: str
    stay_duration_months: int
    grace_period_months: int
    is_within_grace_period: bool
    re_registration_required: bool
    status_code: Literal["INTRA_STATE_OPERATION", "WITHIN_STATUTORY_GRACE_PERIOD", "RE_REGISTRATION_MANDATORY"]
    legal_advisory: str
    noc_status_advisory: str
    required_documents: list[str]
    statutory_provisions: dict[str, str]


class RoadTaxRefundRequest(BaseModel):
    """Input payload to compute pro-rata road tax refund."""
    model_config = ConfigDict(extra="forbid")

    original_road_tax_paid: float = Field(..., gt=0)
    vehicle_age_months: int = Field(..., ge=0, le=300)
    origin_state: str = Field(..., min_length=2, max_length=50)
    destination_state: str = Field(..., min_length=2, max_length=50)


class RoadTaxRefundResponse(BaseModel):
    """Pro-rata refund calculation for parent state motor vehicle tax."""
    model_config = ConfigDict(frozen=True)

    origin_state: str
    destination_state: str
    original_road_tax_paid: float
    vehicle_age_months: int
    statutory_lifespan_months: int
    unused_lifespan_months: int
    refund_percentage: float
    eligible_refund_amount: float
    advisory: str
    claim_procedure: str


def _validate_interstate_relocation_rules(data: Any) -> None:
    _require(isinstance(data, dict), "interstate_relocation_rules must be an object")
    _require("statutory_framework" in data and isinstance(data["statutory_framework"], dict), "missing statutory_framework")
    _require("procedural_rules" in data and isinstance(data["procedural_rules"], dict), "missing procedural_rules")


INTERSTATE_RELOCATION_RULES = _read_json("interstate_relocation_rules.json")
_validate_interstate_relocation_rules(INTERSTATE_RELOCATION_RULES)


# ---------------------------------------------------------------------------
# Inter-State Vehicle Relocation (Sec 47/48 MVA) & Road Tax Refund Engine
# ---------------------------------------------------------------------------
def audit_interstate_relocation_status(
    stay_duration_months: int,
    has_noc: bool,
    origin_state: str,
    destination_state: str,
) -> dict[str, Any]:
    """Audit vehicle stay duration and re-registration compliance under Section 47 & 48 MVA 1988."""
    if not isinstance(stay_duration_months, int) or stay_duration_months < 0:
        raise CalculatorInputError("Stay duration must be a non-negative integer of months.")
    if not isinstance(origin_state, str) or not origin_state.strip():
        raise CalculatorInputError("Origin state must be a non-empty string.")
    if not isinstance(destination_state, str) or not destination_state.strip():
        raise CalculatorInputError("Destination state must be a non-empty string.")

    rules = INTERSTATE_RELOCATION_RULES
    framework = rules.get("statutory_framework", {})
    procedural = rules.get("procedural_rules", {})
    grace_period = procedural.get("interstate_grace_period_months", 12)

    is_same_state = origin_state.strip().lower() == destination_state.strip().lower()

    if is_same_state:
        status_code = "INTRA_STATE_OPERATION"
        re_registration_required = False
        advisory = f"Both origin and destination are {origin_state.strip()}. No Section 47 inter-state re-registration is required."
    elif stay_duration_months <= grace_period:
        status_code = "WITHIN_STATUTORY_GRACE_PERIOD"
        re_registration_required = False
        advisory = (
            f"Under Section 47 MVA 1988, your vehicle can lawfully operate in {destination_state.strip()} "
            f"for up to {grace_period} months without local re-registration or paying destination road tax. "
            "Retain documentary proof of entry (FASTag logs, toll receipts, or packers-and-movers consignment)."
        )
    else:
        status_code = "RE_REGISTRATION_MANDATORY"
        re_registration_required = True
        advisory = (
            f"Stay duration ({stay_duration_months} months) exceeds the statutory {grace_period}-month limit. "
            f"Under Section 47 MVA 1988, you are statutorily required to obtain a new registration mark from "
            f"{destination_state.strip()} RTO and pay local road tax."
        )

    noc_advisory = ""
    if not is_same_state and re_registration_required:
        if has_noc:
            noc_advisory = "Form 28 NOC is available. Submit Form 27 along with NOC and vehicle fitness to destination RTO."
        else:
            noc_advisory = (
                f"Form 28 NOC from {origin_state.strip()} RTO is mandatory. Under Section 48(3) MVA, if the origin RTO "
                "fails to refuse the NOC within 30 days of application, it is legally deemed to be granted."
            )

    return {
        "origin_state": origin_state.strip(),
        "destination_state": destination_state.strip(),
        "stay_duration_months": stay_duration_months,
        "grace_period_months": grace_period,
        "is_within_grace_period": stay_duration_months <= grace_period and not is_same_state,
        "re_registration_required": re_registration_required,
        "status_code": status_code,
        "legal_advisory": advisory,
        "noc_status_advisory": noc_advisory,
        "required_documents": procedural.get("required_documents", []),
        "statutory_provisions": {
            "section_47": framework.get("section_47", ""),
            "section_48": framework.get("section_48", ""),
        },
    }


def calculate_road_tax_refund(
    original_road_tax_paid: float,
    vehicle_age_months: int,
    origin_state: str,
    destination_state: str,
) -> dict[str, Any]:
    """Calculate pro-rata road tax refund from parent state upon re-registration."""
    if not isinstance(original_road_tax_paid, (int, float)) or original_road_tax_paid <= 0:
        raise CalculatorInputError("Original road tax paid must be a positive number.")
    if not isinstance(vehicle_age_months, int) or vehicle_age_months < 0:
        raise CalculatorInputError("Vehicle age in months must be a non-negative integer.")

    rules = INTERSTATE_RELOCATION_RULES
    statutory_lifespan = rules.get("statutory_framework", {}).get("statutory_lifespan_months", 180)

    if vehicle_age_months >= statutory_lifespan:
        refund_amount = 0.0
        refund_pct = 0.0
        unused_months = 0
        advisory = (
            f"Vehicle age ({vehicle_age_months} months) has reached or exceeded the 15-year statutory lifespan "
            f"({statutory_lifespan} months). No pro-rata road tax refund is payable under state taxation rules."
        )
    else:
        unused_months = statutory_lifespan - vehicle_age_months
        refund_fraction = unused_months / float(statutory_lifespan)
        refund_amount = round(original_road_tax_paid * refund_fraction, 2)
        refund_pct = round(refund_fraction * 100.0, 1)
        advisory = (
            f"Statutorily eligible to claim ₹{refund_amount:,.2f} ({refund_pct}% of original tax) from {origin_state.strip()} "
            f"RTO for {unused_months} remaining months of vehicle lifespan upon submitting proof of re-registration in {destination_state.strip()}."
        )

    return {
        "origin_state": origin_state.strip(),
        "destination_state": destination_state.strip(),
        "original_road_tax_paid": float(original_road_tax_paid),
        "vehicle_age_months": vehicle_age_months,
        "statutory_lifespan_months": statutory_lifespan,
        "unused_lifespan_months": unused_months,
        "refund_percentage": refund_pct,
        "eligible_refund_amount": refund_amount,
        "advisory": advisory,
        "claim_procedure": (
            f"Apply to {origin_state.strip()} RTO using Form DT / Tax Refund Application attaching original RC surrender receipt, "
            f"Form 28 NOC, and receipt of road tax paid in {destination_state.strip()}."
        ),
    }


router = APIRouter()


@router.post(
    "/api/v1/relocation/audit-stay",
    response_model=InterstateRelocationAuditResponse,
    tags=["relocation"],
    summary="Audit Inter-State Vehicle Relocation Compliance (Sec 47 & 48 MVA)",
)
def audit_relocation_endpoint(request: InterstateRelocationAuditRequest) -> InterstateRelocationAuditResponse:
    """Audit 12-month legal operational grace period and Form 28 NOC requirements for inter-state vehicles."""
    try:
        result = audit_interstate_relocation_status(
            stay_duration_months=request.stay_duration_months,
            has_noc=request.has_noc,
            origin_state=request.origin_state,
            destination_state=request.destination_state,
        )
        return InterstateRelocationAuditResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/relocation/calculate-tax-refund",
    response_model=RoadTaxRefundResponse,
    tags=["relocation"],
    summary="Calculate Pro-Rata Road Tax Refund from Parent State",
)
def calculate_tax_refund_endpoint(request: RoadTaxRefundRequest) -> RoadTaxRefundResponse:
    """Calculate pro-rata refund of lifetime road tax paid in origin state for remaining 15-year vehicle life."""
    try:
        result = calculate_road_tax_refund(
            original_road_tax_paid=request.original_road_tax_paid,
            vehicle_age_months=request.vehicle_age_months,
            origin_state=request.origin_state,
            destination_state=request.destination_state,
        )
        return RoadTaxRefundResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
