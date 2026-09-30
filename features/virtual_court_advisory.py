"""Virtual Courts (vcourts.gov.in) challan resolution and contest advisory engine (Sec 208 MVA).

Self-contained feature module: models, data loading, logic and API router live
here so this feature never edits app_core.py, api.py or models.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

import app_core
from app_core import CalculatorInputError, NATIONAL_FINES, _read_json


# --- Virtual Courts Advisory Models (Sec 208 MVA) ---

class VirtualCourtJurisdictionModel(BaseModel):
    """Virtual Court deployment and procedural operational profile for a State/UT."""
    model_config = ConfigDict(frozen=True)

    state: str
    virtual_court_name: str
    is_active: bool
    online_plea_available: bool
    contest_transfer_court: str
    summons_window_days: int
    portal_domain: str
    special_notes: str


class VirtualCourtContestGroundModel(BaseModel):
    """Statutory grounds to contest a traffic challan before Virtual/Regular Court."""
    model_config = ConfigDict(frozen=True)

    code: str
    name: str
    statutory_basis: str
    success_likelihood: str
    recommendation: str


class VirtualCourtAdvisoryRequest(BaseModel):
    """Request payload to get Virtual Court advisory."""
    model_config = ConfigDict(extra="forbid")

    state: str = Field(..., min_length=2, description="State or UT where challan was issued")
    violation_key: str = Field(..., min_length=2, description="Key of the violation from national catalogue")
    days_since_notice: int = Field(0, ge=0, description="Days elapsed since challan generation")
    has_photo_evidence: bool = Field(True, description="Whether clear photographic evidence is attached")
    contest_ground: str | None = Field(None, description="Optional ground code if contesting")


class VirtualCourtAdvisoryResponse(BaseModel):
    """Statutory recommendation and procedural advice for Virtual Court notice."""
    model_config = ConfigDict(frozen=True)

    state: str
    violation_key: str
    violation_name: str
    virtual_court_available: bool
    virtual_court_name: str
    portal_url: str
    days_since_notice: int
    summons_window_days: int
    is_window_active: bool
    recommended_action: str
    detailed_recommendation: str
    contest_advisable: bool
    contest_transfer_court: str
    contest_grounds: list[dict[str, Any]]
    statutory_basis: str


# ---------------------------------------------------------------------------
# Virtual Courts (vcourts.gov.in) Challan Resolution & Contest Advisory (Sec 208 MVA)
# ---------------------------------------------------------------------------

VIRTUAL_COURT_RULES: dict[str, Any] = _read_json("virtual_court_rules.json")


def get_virtual_court_jurisdictions() -> list[dict[str, Any]]:
    """Return all states and UTs with operational Virtual Traffic Courts under Sec 208 MVA."""
    jurisdictions = VIRTUAL_COURT_RULES.get("jurisdictions", {})
    return [
        {
            "state": state,
            "virtual_court_name": info["virtual_court_name"],
            "is_active": info["is_active"],
            "online_plea_available": info["online_plea_available"],
            "contest_transfer_court": info["contest_transfer_court"],
            "summons_window_days": info["summons_window_days"],
            "portal_domain": info["portal_domain"],
            "special_notes": info["special_notes"],
        }
        for state, info in sorted(jurisdictions.items())
    ]


def get_virtual_court_advisory(
    state: str,
    violation_key: str,
    days_since_notice: int,
    has_photo_evidence: bool = True,
    contest_ground: str | None = None,
) -> dict[str, Any]:
    """Provide statutory Virtual Court (vcourts.gov.in) advisory for an e-challan notice.

    Advises whether the citizen should plead guilty online, contest before a regular
    magistrate under CMVR Rule 167A / Sec 136A, or attend physically.

    Args:
        state: State or Union Territory name (e.g. 'Delhi', 'Maharashtra').
        violation_key: Offence key from NATIONAL_FINES.
        days_since_notice: Days elapsed since e-challan generation date.
        has_photo_evidence: Whether photographic evidence was supplied with the challan.
        contest_ground: Optional contest ground code (e.g. 'missing_or_blurred_plate').

    Returns:
        dict with recommended course of action, statutory rights, timeline status, and procedures.
    """
    if violation_key not in NATIONAL_FINES:
        raise CalculatorInputError(f"Unknown violation key: {violation_key!r}")
    if days_since_notice < 0:
        raise CalculatorInputError(f"days_since_notice cannot be negative: {days_since_notice}")

    state_norm = state.strip()
    jurisdictions = VIRTUAL_COURT_RULES.get("jurisdictions", {})
    is_vcourt_active = state_norm in jurisdictions
    vc_info = jurisdictions.get(state_norm, {})

    window_days = vc_info.get("summons_window_days", 90)
    is_window_active = days_since_notice <= window_days

    # Check violation risk
    rec = NATIONAL_FINES[violation_key]
    dl_risk = rec.get("dl_suspension_risk", "none")

    # Evaluate contest grounds if specified
    contest_details = None
    if contest_ground:
        for g in VIRTUAL_COURT_RULES.get("grounds_to_contest", []):
            if g["code"] == contest_ground:
                contest_details = g
                break

    # Decision Matrix
    if dl_risk == "automatic":
        action = "Mandatory Physical Court Appearance (DL Revocation Risk)"
        recommendation = (
            f"This offence ({rec['description']}) carries mandatory DL disqualification or imprisonment. "
            "It cannot be settled via summary online plea on vcourts.gov.in. "
            "Engage a traffic advocate immediately and prepare for hearing before the Metropolitan Magistrate."
        )
        contest_advisable = True
    elif not has_photo_evidence:
        action = "Contest Notice Before Magistrate (Defective Evidence)"
        recommendation = (
            "CMVR Rule 167A(4) mandates that electronic monitoring records must contain clear "
            "photographic proof showing the vehicle registration mark, location coordinates, and date/time. "
            "Because photographic proof is missing or defective, this notice lacks sustainable legal proof under "
            "Section 136A MVA. Choose 'Contest' on vcourts.gov.in to transfer to regular court."
        )
        contest_advisable = True
    elif contest_details:
        action = f"Contest on Grounds: {contest_details['name']}"
        recommendation = (
            f"{contest_details['recommendation']} "
            f"Statutory Authority: {contest_details['statutory_basis']} "
            f"(Likelihood of Success: {contest_details['success_likelihood']})."
        )
        contest_advisable = True
    elif not is_window_active:
        action = "Physical Summons Escalation / Regular Court Appearance"
        recommendation = (
            f"The notice was received {days_since_notice} days ago, exceeding the {window_days}-day "
            "Virtual Court settlement window. The file has likely been transferred to the concerned "
            f"Metropolitan Magistrate / CJM Court for issuing physical summons or bailable warrants under Sec 208 MVA."
        )
        contest_advisable = True
    else:
        action = "Plead Guilty & Settle Online via vcourts.gov.in"
        recommendation = (
            "The photographic proof is on record and the offence is compoundable. "
            "Pleading guilty online through the Virtual Court portal (vcourts.gov.in) allows you to "
            "settle the fine digitally without visiting a court premises, saving judicial time and legal fees."
        )
        contest_advisable = False

    return {
        "state": state_norm,
        "violation_key": violation_key,
        "violation_name": rec["description"],
        "virtual_court_available": is_vcourt_active,
        "virtual_court_name": vc_info.get("virtual_court_name", "Regular Magistrate Court (No Virtual Court in State)"),
        "portal_url": VIRTUAL_COURT_RULES["portal_url"] if is_vcourt_active else "https://echallan.parivahan.gov.in",
        "days_since_notice": days_since_notice,
        "summons_window_days": window_days,
        "is_window_active": is_window_active,
        "recommended_action": action,
        "detailed_recommendation": recommendation,
        "contest_advisable": contest_advisable,
        "contest_transfer_court": vc_info.get("contest_transfer_court", "Jurisdictional CJM / Judicial Magistrate Court"),
        "contest_grounds": VIRTUAL_COURT_RULES.get("grounds_to_contest", []),
        "statutory_basis": VIRTUAL_COURT_RULES["statutory_basis"],
    }


router = APIRouter()


@router.get(
    "/api/v1/virtual-court/jurisdictions",
    response_model=list[VirtualCourtJurisdictionModel],
    tags=["virtual_court"],
    summary="Active Virtual Court Jurisdictions and Operational Rules (Sec 208 MVA)",
)
def get_virtual_court_jurisdictions_endpoint() -> list[VirtualCourtJurisdictionModel]:
    """List all States/UTs with deployed Virtual Traffic Courts, summons windows, and transfer courts."""
    jurisdictions = get_virtual_court_jurisdictions()
    return [VirtualCourtJurisdictionModel.model_validate(j) for j in jurisdictions]


@router.post(
    "/api/v1/virtual-court/advisory",
    response_model=VirtualCourtAdvisoryResponse,
    tags=["virtual_court"],
    summary="Virtual Court (vcourts.gov.in) Challan Resolution & Contest Advisory",
)
def get_virtual_court_advisory_endpoint(
    payload: VirtualCourtAdvisoryRequest,
) -> VirtualCourtAdvisoryResponse:
    """Analyze a traffic challan notice and return statutory advice on whether to plead guilty online
    via vcourts.gov.in, contest under CMVR Rule 167A before a regular magistrate, or prepare for summons."""
    try:
        advisory = get_virtual_court_advisory(
            state=payload.state,
            violation_key=payload.violation_key,
            days_since_notice=payload.days_since_notice,
            has_photo_evidence=payload.has_photo_evidence,
            contest_ground=payload.contest_ground,
        )
        return VirtualCourtAdvisoryResponse.model_validate(advisory)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Virtual Court advisory error: {exc}",
        ) from exc
