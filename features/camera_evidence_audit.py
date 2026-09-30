"""Speed camera electronic evidence auditor and calibration RTI generator (CMVR 167A, Sec 136A MVA).

Self-contained feature module: models, data loading, logic and API router live
here so this feature never edits app_core.py, api.py or models.py.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

import app_core
from app_core import CalculatorInputError, _read_json, _require


# --- Camera Electronic Evidence & RTI Models (CMVR 167A & Sec 136A MVA) ---
class CameraCriterionItem(BaseModel):
    """Evidentiary checklist item under CMVR Rule 167A."""
    model_config = ConfigDict(frozen=True)

    criterion_id: str
    title: str
    statutory_basis: str
    satisfied: bool
    weight: int
    description: str


class CameraEvidenceAuditRequest(BaseModel):
    """Challan evidence compliance audit payload."""
    model_config = ConfigDict(extra="forbid")

    challan_no: str = Field(..., min_length=2, max_length=50)
    has_clear_plate_photo: bool = False
    has_speed_measurement_proof: bool = False
    has_timestamp_and_gps: bool = False
    has_statutory_citation: bool = False
    has_evidence_act_compliance: bool = False
    has_annual_calibration_status: bool = False


class CameraEvidenceAuditResponse(BaseModel):
    """Result of CMVR Rule 167A evidentiary compliance audit."""
    model_config = ConfigDict(frozen=True)

    challan_no: str
    compliance_score: int = Field(..., ge=0, le=100)
    compliance_status: Literal["FULLY_COMPLIANT", "SUBSTANTIALLY_DEFECTIVE", "FATALLY_DEFECTIVE"]
    evidentiary_standing: str
    challenge_recommended: bool
    passed_criteria_count: int
    failed_criteria_count: int
    passed_items: list[CameraCriterionItem]
    failed_items: list[CameraCriterionItem]
    statutory_authority: dict[str, str]


class CalibrationRTIRequest(BaseModel):
    """Input payload to generate Section 6(1) RTI application for speed camera calibration."""
    model_config = ConfigDict(extra="forbid")

    applicant_name: str = Field(..., min_length=2, max_length=100)
    applicant_address: str = Field(..., min_length=5, max_length=300)
    challan_no: str = Field(..., min_length=2, max_length=50)
    violation_date: str = Field(..., min_length=4, max_length=50)
    camera_location: str = Field(..., min_length=3, max_length=200)
    authority_name: str = Field("Public Information Officer (Traffic Police)", max_length=150)


class CalibrationRTIResponse(BaseModel):
    """Formal generated RTI application document under RTI Act 2005."""
    model_config = ConfigDict(frozen=True)

    challan_no: str
    applicant_name: str
    application_text: str
    questions_included: list[str]
    statutory_fee: str
    legal_recourse: str


def _validate_camera_evidence_rules(rules: Any) -> None:
    _require(isinstance(rules, dict), "camera_evidence_rules must be an object")
    for key in ("statutory_framework", "mandatory_evidentiary_criteria", "rti_application_template"):
        _require(key in rules and isinstance(rules[key], (list, dict)), f"missing {key} in camera_evidence_rules")


CAMERA_EVIDENCE_RULES = _read_json("camera_evidence_rules.json")
_validate_camera_evidence_rules(CAMERA_EVIDENCE_RULES)


# ---------------------------------------------------------------------------
# Camera Electronic Evidence Auditor & RTI Generator (CMVR 167A & Sec 136A MVA)
# ---------------------------------------------------------------------------
def audit_camera_evidence_compliance(
    challan_no: str,
    has_clear_plate_photo: bool,
    has_speed_measurement_proof: bool,
    has_timestamp_and_gps: bool,
    has_statutory_citation: bool,
    has_evidence_act_compliance: bool,
    has_annual_calibration_status: bool,
) -> dict[str, Any]:
    """Audit whether an automated speed camera challan complies with CMVR Rule 167A evidentiary mandates."""
    if not isinstance(challan_no, str) or not challan_no.strip():
        raise CalculatorInputError("Challan number must be a non-empty string.")

    criteria_responses = {
        "clear_plate_photo": has_clear_plate_photo,
        "speed_measurement_proof": has_speed_measurement_proof,
        "timestamp_and_gps": has_timestamp_and_gps,
        "statutory_citation": has_statutory_citation,
        "evidence_act_compliance": has_evidence_act_compliance,
        "annual_calibration_status": has_annual_calibration_status,
    }

    rules = CAMERA_EVIDENCE_RULES
    checklist = rules.get("mandatory_evidentiary_criteria", [])

    total_score = 0
    passed_items = []
    failed_items = []

    for item in checklist:
        cid = item["criterion_id"]
        is_satisfied = bool(criteria_responses.get(cid, False))
        weight = item["weight"]
        entry = {
            "criterion_id": cid,
            "title": item["title"],
            "statutory_basis": item["statutory_basis"],
            "satisfied": is_satisfied,
            "weight": weight,
            "description": item["description"],
        }
        if is_satisfied:
            total_score += weight
            passed_items.append(entry)
        else:
            failed_items.append(entry)

    total_score = min(max(total_score, 0), 100)

    if total_score == 100:
        compliance_status = "FULLY_COMPLIANT"
        evidentiary_standing = "Evidence satisfies prima facie legal scrutiny under CMVR Rule 167A."
        challenge_recommended = False
    elif total_score >= 60:
        compliance_status = "SUBSTANTIALLY_DEFECTIVE"
        evidentiary_standing = "Challan possesses significant procedural evidentiary defects under CMVR Rule 167A(4)."
        challenge_recommended = True
    else:
        compliance_status = "FATALLY_DEFECTIVE"
        evidentiary_standing = "Challan lacks essential evidentiary foundation and is liable to be quashed in court."
        challenge_recommended = True

    return {
        "challan_no": challan_no.strip(),
        "compliance_score": total_score,
        "compliance_status": compliance_status,
        "evidentiary_standing": evidentiary_standing,
        "challenge_recommended": challenge_recommended,
        "passed_criteria_count": len(passed_items),
        "failed_criteria_count": len(failed_items),
        "passed_items": passed_items,
        "failed_items": failed_items,
        "statutory_authority": rules.get("statutory_framework", {}),
    }


def generate_camera_calibration_rti(
    applicant_name: str,
    applicant_address: str,
    challan_no: str,
    violation_date: str,
    camera_location: str,
    authority_name: str = "Public Information Officer (Traffic Police)",
) -> dict[str, Any]:
    """Generate a formal Section 6(1) RTI application demanding speed camera calibration records."""
    for field, val in [
        ("Applicant Name", applicant_name),
        ("Applicant Address", applicant_address),
        ("Challan Number", challan_no),
        ("Violation Date", violation_date),
        ("Camera Location", camera_location),
    ]:
        if not isinstance(val, str) or not val.strip():
            raise CalculatorInputError(f"{field} must be a non-empty string.")

    rules = CAMERA_EVIDENCE_RULES
    tpl = rules.get("rti_application_template", {})
    raw_questions = tpl.get("questions", [])

    formatted_questions = [
        q.format(challan_no=challan_no.strip(), violation_date=violation_date.strip())
        for q in raw_questions
    ]

    rti_body = (
        f"To,\n"
        f"The Public Information Officer (Traffic),\n"
        f"{authority_name.strip()}.\n\n"
        f"Subject: {tpl.get('subject')}\n\n"
        f"Respected Sir/Madam,\n\n"
        f"I am a citizen of India residing at {applicant_address.strip()}. "
        f"Regarding electronic traffic notice/challan no. {challan_no.strip()} issued on {violation_date.strip()} "
        f"alleging speed violation captured by automated camera at {camera_location.strip()}, "
        f"I hereby request the following information under Section 6(1) of the Right to Information Act, 2005:\n\n"
    )

    for i, q in enumerate(formatted_questions, 1):
        rti_body += f"{i}. {q}\n"

    rti_body += (
        f"\nStatutory Fee: {tpl.get('standard_fee', 'Rs 10/-')}.\n"
        f"Kindly furnish the information within 30 days as mandated by Section 7(1) of the RTI Act, 2005.\n\n"
        f"Yours faithfully,\n"
        f"{applicant_name.strip()}\n"
        f"Date: Present\n"
    )

    return {
        "challan_no": challan_no.strip(),
        "applicant_name": applicant_name.strip(),
        "application_text": rti_body,
        "questions_included": formatted_questions,
        "statutory_fee": tpl.get("standard_fee", "Rs 10/-"),
        "legal_recourse": "Section 6(1) and Section 7(1) Right to Information Act, 2005.",
    }


router = APIRouter()


@router.post(
    "/api/v1/evidence/audit-camera-challan",
    response_model=CameraEvidenceAuditResponse,
    tags=["evidence_audit"],
    summary="Audit Speed Camera Challan Evidentiary Compliance (CMVR Rule 167A)",
)
def audit_camera_evidence_endpoint(request: CameraEvidenceAuditRequest) -> CameraEvidenceAuditResponse:
    """Audit whether an automated camera challan complies with statutory evidentiary mandates under CMVR 167A."""
    try:
        result = audit_camera_evidence_compliance(
            challan_no=request.challan_no,
            has_clear_plate_photo=request.has_clear_plate_photo,
            has_speed_measurement_proof=request.has_speed_measurement_proof,
            has_timestamp_and_gps=request.has_timestamp_and_gps,
            has_statutory_citation=request.has_statutory_citation,
            has_evidence_act_compliance=request.has_evidence_act_compliance,
            has_annual_calibration_status=request.has_annual_calibration_status,
        )
        return CameraEvidenceAuditResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/evidence/generate-calibration-rti",
    response_model=CalibrationRTIResponse,
    tags=["evidence_audit"],
    summary="Generate Section 6(1) RTI Application for Speed Camera Calibration",
)
def generate_calibration_rti_endpoint(request: CalibrationRTIRequest) -> CalibrationRTIResponse:
    """Generate a formal, ready-to-file RTI application under Section 6(1) RTI Act demanding camera calibration."""
    try:
        result = generate_camera_calibration_rti(
            applicant_name=request.applicant_name,
            applicant_address=request.applicant_address,
            challan_no=request.challan_no,
            violation_date=request.violation_date,
            camera_location=request.camera_location,
            authority_name=request.authority_name,
        )
        return CalibrationRTIResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
