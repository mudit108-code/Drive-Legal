"""Women motorist statutory safeguards and Good Samaritan immunity generator (Sec 46(4) CrPC/35 BNSS, Sec 134A MVA).

Self-contained feature module: models, data loading, logic and API router live
here so this feature never edits app_core.py, api.py or models.py.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

import app_core
from app_core import CalculatorInputError, _read_json, _require


# --- Women Motorist Safeguards & Good Samaritan Models ---
class WomenProtectiveRuleItem(BaseModel):
    """Specific statutory safeguard item for women motorists."""
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    statutory_citation: str
    rule: str
    citizen_instruction: str


class WomenDriverSafeguardRequest(BaseModel):
    """Input payload to evaluate women motorist rights."""
    model_config = ConfigDict(extra="forbid")

    is_night_time: bool = False
    female_officer_present: bool = True
    alone_in_vehicle: bool = False


class WomenDriverSafeguardResponse(BaseModel):
    """Response detailing on-road rights and emergency legal directives."""
    model_config = ConfigDict(frozen=True)

    is_night_time: bool
    female_officer_present: bool
    alone_in_vehicle: bool
    advisory_level: Literal["STANDARD_PROCEDURE", "ELEVATED_CAUTION", "CRITICAL_SAFEGUARD_ALERT"]
    action_summary: str
    immediate_actions: list[str]
    applicable_safeguards: list[WomenProtectiveRuleItem]
    statutory_references: dict[str, str]


class GoodSamaritanCharterItem(BaseModel):
    """Statutory guarantee clause under Good Samaritan regulations."""
    model_config = ConfigDict(frozen=True)

    guarantee_id: str
    title: str
    statutory_basis: str
    clause: str


class GoodSamaritanCertificateRequest(BaseModel):
    """Input payload to generate Good Samaritan Immunity Certificate."""
    model_config = ConfigDict(extra="forbid")

    rescuer_name: str = Field(..., min_length=2, max_length=100)
    accident_location: str = Field(..., min_length=3, max_length=200)
    incident_date: str = Field(..., min_length=4, max_length=50)
    hospital_name: str = Field(..., min_length=2, max_length=150)
    victim_transported: bool = True


class GoodSamaritanCertificateResponse(BaseModel):
    """Formal Immunity Notice and Charter for Good Samaritans."""
    model_config = ConfigDict(frozen=True)

    rescuer_name: str
    accident_location: str
    incident_date: str
    hospital_name: str
    victim_transported: bool
    notice_text: str
    statutory_clauses: list[GoodSamaritanCharterItem]
    supreme_court_citation: str
    statutory_basis: str


def _validate_women_safeguards(data: Any) -> None:
    _require(isinstance(data, dict), "women_driver_protections must be an object")
    _require("statutory_references" in data and isinstance(data["statutory_references"], dict), "missing statutory_references")
    _require("protective_rules" in data and isinstance(data["protective_rules"], list), "missing protective_rules")


def _validate_good_samaritan_charter(data: Any) -> None:
    _require(isinstance(data, dict), "good_samaritan_charter must be an object")
    _require("statutory_framework" in data and isinstance(data["statutory_framework"], dict), "missing statutory_framework")
    _require("charter_guarantees" in data and isinstance(data["charter_guarantees"], list), "missing charter_guarantees")


WOMEN_DRIVER_PROTECTIONS = _read_json("women_driver_protections.json")
_validate_women_safeguards(WOMEN_DRIVER_PROTECTIONS)
GOOD_SAMARITAN_CHARTER = _read_json("good_samaritan_charter.json")
_validate_good_samaritan_charter(GOOD_SAMARITAN_CHARTER)


# ---------------------------------------------------------------------------
# Women Motorist Statutory Safeguards & Good Samaritan Charter
# ---------------------------------------------------------------------------
def get_women_motorist_safeguards(
    is_night_time: bool,
    female_officer_present: bool,
    alone_in_vehicle: bool = False,
) -> dict[str, Any]:
    """Evaluate statutory safeguards and on-road rights for women motorists."""
    if not isinstance(is_night_time, bool) or not isinstance(female_officer_present, bool):
        raise CalculatorInputError("Inputs is_night_time and female_officer_present must be boolean.")

    rules = WOMEN_DRIVER_PROTECTIONS
    refs = rules.get("statutory_references", {})
    all_rules = rules.get("protective_rules", [])

    immediate_actions = []
    applicable_safeguards = []

    if is_night_time and not female_officer_present:
        advisory_level = "CRITICAL_SAFEGUARD_ALERT"
        action_summary = (
            "Under Section 46(4) CrPC / Section 35(1) BNSS, you CANNOT be arrested or forced out of your vehicle "
            "by male police officers at night. Keep doors locked, lower window slightly, demand a female officer, "
            "and immediately call 112 / 1091."
        )
        immediate_actions.extend([
            "Lock all vehicle doors and keep windows rolled up.",
            "Firmly state: 'Under Section 46(4) CrPC / Section 35 BNSS, I require a female officer to be present.'",
            "Call 112 (National Emergency) or 1091 (Women Helpline) and share your live location.",
            "Turn on your smartphone camera or dashboard camera.",
        ])
    elif not female_officer_present:
        advisory_level = "ELEVATED_CAUTION"
        action_summary = (
            "During daytime, male officers can inspect driving documents, but physical search of a female driver "
            "or passenger can only be conducted by a female officer (Sec 51(2) CrPC / Sec 49(2) BNSS)."
        )
        immediate_actions.extend([
            "Display documents via DigiLocker / mParivahan without handing over physical phone.",
            "Refuse physical frisking unless a female officer is present.",
        ])
    else:
        advisory_level = "STANDARD_PROCEDURE"
        action_summary = "A female officer is present. Comply with lawful document inspection and verification."
        immediate_actions.extend([
            "Verify the officer's name and rank tag.",
            "Present digital or physical driving documents.",
        ])

    for r in all_rules:
        applicable_safeguards.append({
            "id": r["id"],
            "title": r["title"],
            "statutory_citation": r["statutory_citation"],
            "rule": r["rule"],
            "citizen_instruction": r["citizen_instruction"],
        })

    return {
        "is_night_time": is_night_time,
        "female_officer_present": female_officer_present,
        "alone_in_vehicle": alone_in_vehicle,
        "advisory_level": advisory_level,
        "action_summary": action_summary,
        "immediate_actions": immediate_actions,
        "applicable_safeguards": applicable_safeguards,
        "statutory_references": refs,
    }


def generate_good_samaritan_certificate(
    rescuer_name: str,
    accident_location: str,
    incident_date: str,
    hospital_name: str,
    victim_transported: bool = True,
) -> dict[str, Any]:
    """Generate a formal Statutory Good Samaritan Immunity Notice under Section 134A MVA & MoRTH S.O. 2187(E)."""
    for field, val in [
        ("Rescuer Name", rescuer_name),
        ("Accident Location", accident_location),
        ("Incident Date", incident_date),
        ("Hospital Name", hospital_name),
    ]:
        if not isinstance(val, str) or not val.strip():
            raise CalculatorInputError(f"{field} must be a non-empty string.")

    rules = GOOD_SAMARITAN_CHARTER
    framework = rules.get("statutory_framework", {})
    guarantees = rules.get("charter_guarantees", [])

    notice_text = (
        "================================================================================\n"
        "       OFFICIAL STATUTORY NOTICE: GOOD SAMARITAN IMMUNITY CHARTER\n"
        "             Pursuant to Section 134A, Motor Vehicles Act, 1988\n"
        "         and Central Government Notification MoRTH S.O. 2187(E)\n"
        "================================================================================\n\n"
        f"DATE OF INCIDENT: {incident_date.strip()}\n"
        f"LOCATION OF ACCIDENT: {accident_location.strip()}\n"
        f"RESCUER / ASSISTING CITIZEN: {rescuer_name.strip()}\n"
        f"RECEIVING HOSPITAL: {hospital_name.strip()}\n\n"
        "TO ALL LAW ENFORCEMENT OFFICERS, POLICE PERSONNEL, AND HOSPITAL AUTHORITIES:\n\n"
        "TAKE FORMAL NOTICE THAT:\n"
        f"1. Under Section 134A(1) of the Motor Vehicles Act, 1988, {rescuer_name.strip()} is a legally "
        "recognized 'Good Samaritan' and SHALL NOT BE LIABLE for any civil or criminal action for any injury "
        "or death of the crash victim resulting from emergency assistance rendered in good faith.\n\n"
        "2. As mandated by the Supreme Court of India in SaveLIFE Foundation v. Union of India (2016) 7 SCC 700 "
        "and MoRTH Notification S.O. 2187(E):\n"
        "   - The Good Samaritan CANNOT be detained at the police station or hospital.\n"
        "   - The Good Samaritan is NOT required to reveal their name, phone number, or personal details.\n"
        "   - No hospital shall demand advance payment, registration fee, or deposit from the Good Samaritan.\n"
        "   - Examination as a witness is STRICTLY VOLUNTARY and can only occur at a time and place of the citizen's choice.\n\n"
        "Any violation of these statutory protections by any official constitutes contempt of the Supreme Court of India "
        "and departmental misconduct under Central Civil Services Rules.\n\n"
        f"ISSUED IN THE INTEREST OF CITIZEN PROTECTION UNDER SECTION 134A MVA.\n"
    )

    return {
        "rescuer_name": rescuer_name.strip(),
        "accident_location": accident_location.strip(),
        "incident_date": incident_date.strip(),
        "hospital_name": hospital_name.strip(),
        "victim_transported": victim_transported,
        "notice_text": notice_text,
        "statutory_clauses": guarantees,
        "supreme_court_citation": framework.get("supreme_court_judgment", ""),
        "statutory_basis": framework.get("mva_section", ""),
    }


router = APIRouter()


@router.post(
    "/api/v1/safeguards/women-driver",
    response_model=WomenDriverSafeguardResponse,
    tags=["safeguards"],
    summary="Evaluate Women Motorist On-Road Safeguards (Sec 46(4) CrPC / Sec 35 BNSS)",
)
def get_women_safeguards_endpoint(request: WomenDriverSafeguardRequest) -> WomenDriverSafeguardResponse:
    """Evaluate statutory rights, night-time arrest bans, and immediate actions for women motorists."""
    try:
        result = get_women_motorist_safeguards(
            is_night_time=request.is_night_time,
            female_officer_present=request.female_officer_present,
            alone_in_vehicle=request.alone_in_vehicle,
        )
        return WomenDriverSafeguardResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/safeguards/good-samaritan-charter",
    response_model=GoodSamaritanCertificateResponse,
    tags=["safeguards"],
    summary="Generate Statutory Good Samaritan Immunity Certificate (Sec 134A MVA)",
)
def generate_good_samaritan_endpoint(request: GoodSamaritanCertificateRequest) -> GoodSamaritanCertificateResponse:
    """Generate a formal Good Samaritan Immunity Notice protecting accident rescuers from liability and harassment."""
    try:
        result = generate_good_samaritan_certificate(
            rescuer_name=request.rescuer_name,
            accident_location=request.accident_location,
            incident_date=request.incident_date,
            hospital_name=request.hospital_name,
            victim_transported=request.victim_transported,
        )
        return GoodSamaritanCertificateResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
