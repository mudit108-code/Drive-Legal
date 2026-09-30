"""National Lok Adalat challan settlement concession estimator and schedule guide.

Self-contained feature module: models, data loading, logic and API router live
here so this feature never edits app_core.py, api.py or models.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

import app_core
from app_core import CalculatorInputError, NATIONAL_FINES, _read_json


# --- National Lok Adalat Models (Legal Services Authorities Act 1987) ---

class LokAdalatScheduleModel(BaseModel):
    """National Lok Adalat framework, quarterly dates, and state SLSA policies."""
    model_config = ConfigDict(frozen=True)

    title: str
    statutory_basis: str
    authority: str
    award_finality: str
    quarterly_calendar: list[dict[str, Any]]
    state_policies: dict[str, Any]
    non_compoundable_offences: list[str]


class LokAdalatConcessionRequest(BaseModel):
    """Request payload to estimate Lok Adalat challan settlement relief."""
    model_config = ConfigDict(extra="forbid")

    violation_keys: list[str] = Field(..., min_length=1, description="List of violation keys from national fines")
    state: str = Field("Delhi", description="State or UT where challans were issued")


class LokAdalatConcessionResponse(BaseModel):
    """Estimated Lok Adalat financial relief, waiver percentage, and procedure."""
    model_config = ConfigDict(frozen=True)

    state: str
    slsa_name: str
    token_portal: str
    offence_count: int
    total_nominal_fine: float
    compoundable_fine_sum: float
    non_compoundable_fine_sum: float
    estimated_lok_adalat_payable: float
    estimated_savings: float
    effective_concession_pct: float
    state_standard_concession_pct: float
    compoundable_items: list[dict[str, Any]]
    non_compoundable_items: list[dict[str, Any]]
    procedural_steps: list[str]
    statutory_basis: str
    award_finality: str


# ---------------------------------------------------------------------------
# National Lok Adalat Challan Settlement & Concession Engine (Legal Services Authorities Act 1987)
# ---------------------------------------------------------------------------

LOK_ADALAT_RULES: dict[str, Any] = _read_json("lok_adalat_rules.json")


def get_lok_adalat_schedules() -> dict[str, Any]:
    """Return National Lok Adalat quarterly schedules, legal authority, and SLSA state policies."""
    return {
        "title": LOK_ADALAT_RULES["title"],
        "statutory_basis": LOK_ADALAT_RULES["statutory_basis"],
        "authority": LOK_ADALAT_RULES["authority"],
        "award_finality": LOK_ADALAT_RULES["award_finality"],
        "quarterly_calendar": LOK_ADALAT_RULES["quarterly_calendar"],
        "state_policies": LOK_ADALAT_RULES["state_concession_policies"],
        "non_compoundable_offences": LOK_ADALAT_RULES["non_compoundable_offences"],
    }


def calculate_lok_adalat_concession(
    violation_keys: list[str],
    state: str = "Delhi",
) -> dict[str, Any]:
    """Estimate Lok Adalat financial relief, waiver percentage, and procedural settlement steps.

    Args:
        violation_keys: List of offence keys from NATIONAL_FINES.
        state: State where challans were issued (e.g. 'Delhi', 'Karnataka', 'Maharashtra').

    Returns:
        dict with total nominal fine, compoundable sum, non-compoundable sum,
        estimated Lok Adalat payable, savings, and procedural guidance.
    """
    if not violation_keys:
        raise CalculatorInputError("violation_keys must be a non-empty list.")

    invalid = [k for k in violation_keys if k not in NATIONAL_FINES]
    if invalid:
        raise CalculatorInputError(f"Unknown violation keys: {invalid!r}")
    state_norm = state.strip()
    policies = LOK_ADALAT_RULES.get("state_concession_policies", {})
    policy = policies.get(state_norm, policies.get("DEFAULT", {}))
    concession_pct = policy.get("average_concession_pct", 50.0)

    non_compoundable_set = set(LOK_ADALAT_RULES.get("non_compoundable_offences", []))

    total_nominal = 0.0
    compoundable_sum = 0.0
    non_compoundable_sum = 0.0
    compoundable_items = []
    non_compoundable_items = []

    for key in violation_keys:
        rec = NATIONAL_FINES[key]
        fine = float(rec["fine"])
        total_nominal += fine

        if key in non_compoundable_set or rec.get("dl_suspension_risk") == "automatic":
            non_compoundable_sum += fine
            non_compoundable_items.append({
                "violation_key": key,
                "description": rec["description"],
                "fine": fine,
                "ineligibility_reason": "Non-compoundable criminal offence or mandatory DL suspension under MVA. Must be tried before regular court.",
            })
        else:
            compoundable_sum += fine
            compoundable_items.append({
                "violation_key": key,
                "description": rec["description"],
                "nominal_fine": fine,
                "estimated_settlement": round(fine * (1.0 - (concession_pct / 100.0)), 2),
            })

    estimated_compoundable_payable = round(compoundable_sum * (1.0 - (concession_pct / 100.0)), 2)
    estimated_total_payable = round(estimated_compoundable_payable + non_compoundable_sum, 2)
    total_savings = round(total_nominal - estimated_total_payable, 2)
    effective_concession_pct = round((total_savings / total_nominal) * 100.0, 1) if total_nominal > 0 else 0.0

    procedural_steps = [
        "1. Check Pending Challans: Visit Parivahan e-Challan portal to verify notice numbers and vehicle registration.",
        f"2. Online Token Booking: Access the {policy.get('slsa_name', 'SLSA')} Lok Adalat portal ({policy.get('token_portal', 'https://nalsa.gov.in')}) 7-10 days before the scheduled Lok Adalat date.",
        "3. Download Token Slip: Print your token slip containing designated Court Complex, Bench Number, and allocated time slot.",
        "4. Appearance & Disposal: Present the token slip before the Lok Adalat bench. Pay the compromised token amount digitally or at the court counter to receive a formal Final Disposal Award under Section 21 Legal Services Authorities Act (no further appeal/prosecution)."
    ]

    return {
        "state": state_norm,
        "slsa_name": policy.get("slsa_name", "State Legal Services Authority"),
        "token_portal": policy.get("token_portal", "https://nalsa.gov.in"),
        "offence_count": len(violation_keys),
        "total_nominal_fine": total_nominal,
        "compoundable_fine_sum": compoundable_sum,
        "non_compoundable_fine_sum": non_compoundable_sum,
        "estimated_lok_adalat_payable": estimated_total_payable,
        "estimated_savings": total_savings,
        "effective_concession_pct": effective_concession_pct,
        "state_standard_concession_pct": concession_pct,
        "compoundable_items": compoundable_items,
        "non_compoundable_items": non_compoundable_items,
        "procedural_steps": procedural_steps,
        "statutory_basis": LOK_ADALAT_RULES["statutory_basis"],
        "award_finality": LOK_ADALAT_RULES["award_finality"],
    }


router = APIRouter()


@router.get(
    "/api/v1/lok-adalat/schedules",
    response_model=LokAdalatScheduleModel,
    tags=["lok_adalat"],
    summary="National Lok Adalat Quarterly Calendar and State SLSA Policies",
)
def get_lok_adalat_schedules_endpoint() -> LokAdalatScheduleModel:
    """Retrieve National Lok Adalat calendar quarters, legal authority, and state concession rates."""
    data = get_lok_adalat_schedules()
    return LokAdalatScheduleModel.model_validate(data)


@router.post(
    "/api/v1/lok-adalat/concession-estimate",
    response_model=LokAdalatConcessionResponse,
    tags=["lok_adalat"],
    summary="Estimate National Lok Adalat Challan Settlement Concession and Procedures",
)
def calculate_lok_adalat_concession_endpoint(
    payload: LokAdalatConcessionRequest,
) -> LokAdalatConcessionResponse:
    """Estimate financial waiver and compromise settlement amount for pending traffic challans at National Lok Adalat."""
    try:
        res = calculate_lok_adalat_concession(
            violation_keys=payload.violation_keys,
            state=payload.state,
        )
        return LokAdalatConcessionResponse.model_validate(res)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lok Adalat concession error: {exc}",
        ) from exc
