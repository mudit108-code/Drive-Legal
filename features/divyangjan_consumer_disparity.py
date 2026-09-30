"""Divyangjan adapted-vehicle rights (Sec 2(1) & 52 MVA), Lemon Law defect notice (CPA 2019) and state leniency index (Sec 200).

Self-contained feature module: models, data loading, logic and API router live
here so this feature never edits app_core.py, api.py or models.py.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

import app_core
from app_core import (
    CalculatorInputError,
    NATIONAL_FINES,
    STATE_DATA,
    _read_json,
    _require,
)


# --- Divyangjan Adapted Vehicle, Lemon Law Notice & State Leniency Models ---
class DivyangjanBenefitsRequest(BaseModel):
    """Parameters to evaluate Divyangjan adapted vehicle statutory benefits and concessions."""
    model_config = ConfigDict(extra="forbid")

    vehicle_ex_showroom: float = Field(..., gt=0, description="Ex-showroom vehicle price in INR")
    engine_cc: int = Field(..., ge=0, description="Engine displacement in cubic centimeters")
    fuel_type: Literal["petrol", "diesel", "cng", "electric"] = Field(..., description="Vehicle fuel type")
    length_mm: int = Field(..., gt=0, description="Overall vehicle length in millimeters")
    state: str = Field(..., min_length=1, description="Registration State or Union Territory")
    disability_pct: float = Field(..., ge=0.0, le=100.0, description="Benchmark physical disability percentage")


class DivyangjanBenefitsResponse(BaseModel):
    """Statutory rights, tax waivers, and concessions for Divyangjan adapted vehicle."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    benchmark_disability_satisfied: bool
    gst_concession_eligible: bool
    estimated_gst_savings: float
    road_tax_exemption_pct: float
    estimated_road_tax_savings: float
    total_estimated_concession: float
    toll_exemption_eligible: bool
    alteration_immunity_statute: str
    disqualification_reasons: list[str]
    required_checklist: list[str]


class LemonNoticeRequest(BaseModel):
    """Parameters to generate a formal statutory legal notice under CPA 2019 for defective vehicles."""
    model_config = ConfigDict(extra="forbid")

    owner_name: str = Field(..., min_length=1)
    owner_address: str = Field(..., min_length=1)
    manufacturer_name: str = Field(..., min_length=1)
    dealer_name: str = Field(..., min_length=1)
    dealer_address: str = Field(..., min_length=1)
    vehicle_make_model: str = Field(..., min_length=1)
    vin_or_chassis: str = Field(..., min_length=1)
    purchase_date: str = Field(..., min_length=1)
    purchase_price: float = Field(..., gt=0)
    defect_category: str = Field(..., min_length=1)
    repair_attempts_count: int = Field(..., ge=0)
    days_out_of_service: int = Field(..., ge=0)
    defect_description: str = Field(..., min_length=1)
    remedy_sought: str = Field(..., min_length=1)


class LemonNoticeResponse(BaseModel):
    """Statutory lemon law legal notice and Consumer Commission jurisdiction details."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    notice_text: str
    pecuniary_forum: str
    claim_amount: float
    is_lemon_threshold_met: bool
    statutory_citations: list[str]
    cure_period_days: int


class StateLeniencyRankItem(BaseModel):
    """Individual state ranking and score within the Section 200 compounding leniency index."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int
    state: str
    jurisdiction: str | None = None
    notification_id: str | None = None
    effective_date: str | None = None
    compoundable_violations_count: int
    central_total: float
    state_compounded_total: float
    relief_pct: float
    leniency_score: float


class StateLeniencyIndexResponse(BaseModel):
    """Pan-India State Compounding Leniency Index and Ranking."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_notified_states: int
    average_leniency_score: float
    most_lenient_state: str
    strictest_state: str
    rankings: list[StateLeniencyRankItem]


def _validate_divyangjan_motorist_rights(data: Any) -> None:
    _require(isinstance(data, dict), "divyangjan_motorist_rights must be an object")
    _require("gst_concession" in data and isinstance(data["gst_concession"], dict), "gst_concession must be an object")
    _require("road_tax_exemptions" in data and isinstance(data["road_tax_exemptions"], dict), "road_tax_exemptions must be an object")
    _require("toll_exemption" in data and isinstance(data["toll_exemption"], dict), "toll_exemption must be an object")
    _require("alteration_immunity" in data and isinstance(data["alteration_immunity"], dict), "alteration_immunity must be an object")
    _require("checklist" in data and isinstance(data["checklist"], list), "checklist must be a list")


def _validate_consumer_defect_rules(data: Any) -> None:
    _require(isinstance(data, dict), "consumer_defect_rules must be an object")
    _require("statutory_framework" in data and isinstance(data["statutory_framework"], dict), "statutory_framework must be an object")
    _require("pecuniary_jurisdiction" in data and isinstance(data["pecuniary_jurisdiction"], dict), "pecuniary_jurisdiction must be an object")
    _require("defect_categories" in data and isinstance(data["defect_categories"], dict), "defect_categories must be an object")
    _require("notice_standards" in data and isinstance(data["notice_standards"], dict), "notice_standards must be an object")


DIVYANGJAN_MOTORIST_RIGHTS = _read_json("divyangjan_motorist_rights.json")
_validate_divyangjan_motorist_rights(DIVYANGJAN_MOTORIST_RIGHTS)
CONSUMER_DEFECT_RULES = _read_json("consumer_defect_rules.json")
_validate_consumer_defect_rules(CONSUMER_DEFECT_RULES)


# ---------------------------------------------------------------------------
# Divyangjan Adapted Vehicle, Lemon Law Notice & State Leniency Index
# ---------------------------------------------------------------------------
def calculate_divyangjan_concessions(
    vehicle_ex_showroom: float,
    engine_cc: int,
    fuel_type: str,
    length_mm: int,
    state: str,
    disability_pct: float,
) -> dict[str, Any]:
    """Evaluate Divyangjan adapted vehicle statutory rights, GST concessions, and state exemptions.
    
    Statutory Authority:
    - Section 2(1) MVA 1988 (Definition of Adapted Vehicle)
    - Proviso to Section 52(1) MVA 1988 (Alteration immunity against Sec 182A(4))
    - MoF Notification No. 14/2019-Central Tax (Rate) (18% Concessional GST)
    - Rule 11, National Highways Fee Rules 2008 (100% Toll Exemption)
    - Relevant State Motor Vehicles Taxation Acts (Road Tax Waiver)
    """
    if not isinstance(vehicle_ex_showroom, (int, float)) or vehicle_ex_showroom <= 0 or not math.isfinite(vehicle_ex_showroom):
        raise CalculatorInputError("vehicle_ex_showroom must be a positive finite number")
    if not isinstance(engine_cc, int) or engine_cc < 0:
        raise CalculatorInputError("engine_cc must be a non-negative integer")
    if not isinstance(length_mm, int) or length_mm <= 0:
        raise CalculatorInputError("length_mm must be a positive integer")
    if not isinstance(disability_pct, (int, float)) or not (0 <= disability_pct <= 100) or not math.isfinite(disability_pct):
        raise CalculatorInputError("disability_pct must be between 0 and 100")
    if state not in STATE_DATA:
        raise CalculatorInputError(f"Unknown state or Union Territory: {state}")
    
    fuel_normalized = fuel_type.strip().lower()
    allowed_fuels = {"petrol", "diesel", "cng", "electric"}
    if fuel_normalized not in allowed_fuels:
        raise CalculatorInputError(f"Invalid fuel_type: {fuel_type!r}. Allowed: {sorted(allowed_fuels)}")
    
    gst_rules = DIVYANGJAN_MOTORIST_RIGHTS["gst_concession"]
    min_disability = gst_rules["min_disability_pct"]
    benchmark_satisfied = disability_pct >= min_disability
    
    disqualification_reasons: list[str] = []
    if not benchmark_satisfied:
        disqualification_reasons.append(
            f"Physical disability is {disability_pct}%, which is below the statutory benchmark of {min_disability}% under RPwD Act 2016."
        )
    
    fuel_limits = gst_rules["eligible_fuel_rules"].get(fuel_normalized, {})
    max_cc = fuel_limits.get("max_engine_cc", 0)
    max_len = fuel_limits.get("max_length_mm", 4000)
    
    if length_mm > max_len:
        disqualification_reasons.append(
            f"Vehicle length ({length_mm} mm) exceeds the maximum ceiling of {max_len} mm permitted for 18% GST concession."
        )
    
    if fuel_normalized in ("petrol", "cng") and engine_cc > max_cc:
        disqualification_reasons.append(
            f"Engine capacity ({engine_cc} cc) exceeds the 1200 cc limit for petrol/CNG passenger vehicles."
        )
    elif fuel_normalized == "diesel" and engine_cc > max_cc:
        disqualification_reasons.append(
            f"Engine capacity ({engine_cc} cc) exceeds the 1500 cc limit for diesel passenger vehicles."
        )
    
    gst_eligible = benchmark_satisfied and len(disqualification_reasons) == 0
    estimated_gst_savings = 0.0
    if gst_eligible:
        base_price = vehicle_ex_showroom / 1.28
        estimated_gst_savings = round(base_price * 0.10, 2)
    
    road_tax_rules = DIVYANGJAN_MOTORIST_RIGHTS["road_tax_exemptions"]
    state_exemption_info = road_tax_rules.get(state)
    road_tax_exemption_pct = 0.0
    estimated_road_tax_savings = 0.0
    if benchmark_satisfied:
        if state_exemption_info:
            road_tax_exemption_pct = state_exemption_info.get("exemption_pct", 100.0)
            estimated_road_tax_savings = round(vehicle_ex_showroom * 0.10 * (road_tax_exemption_pct / 100.0), 2)
        else:
            road_tax_exemption_pct = 100.0
            estimated_road_tax_savings = round(vehicle_ex_showroom * 0.10, 2)
            
    total_estimated_concession = round(estimated_gst_savings + estimated_road_tax_savings, 2)
    toll_eligible = benchmark_satisfied
    
    immunity_statute = (
        f"{DIVYANGJAN_MOTORIST_RIGHTS['alteration_immunity']['statutory_basis']}: "
        f"{DIVYANGJAN_MOTORIST_RIGHTS['alteration_immunity']['details']}"
    )
    
    return {
        "benchmark_disability_satisfied": benchmark_satisfied,
        "gst_concession_eligible": gst_eligible,
        "estimated_gst_savings": estimated_gst_savings,
        "road_tax_exemption_pct": road_tax_exemption_pct,
        "estimated_road_tax_savings": estimated_road_tax_savings,
        "total_estimated_concession": total_estimated_concession,
        "toll_exemption_eligible": toll_eligible,
        "alteration_immunity_statute": immunity_statute,
        "disqualification_reasons": disqualification_reasons,
        "required_checklist": list(DIVYANGJAN_MOTORIST_RIGHTS["checklist"]),
    }


def generate_lemon_law_notice(
    owner_name: str,
    owner_address: str,
    manufacturer_name: str,
    dealer_name: str,
    dealer_address: str,
    vehicle_make_model: str,
    vin_or_chassis: str,
    purchase_date: str,
    purchase_price: float,
    defect_category: str,
    repair_attempts_count: int,
    days_out_of_service: int,
    defect_description: str,
    remedy_sought: str,
) -> dict[str, Any]:
    """Generate a formal statutory legal notice under the Consumer Protection Act, 2019 for defective automobiles.
    
    Statutory Framework:
    - Section 2(10) CPA 2019 (Definition of Defect)
    - Chapter VI, Section 84 CPA 2019 (Manufacturer Product Liability)
    - Section 86 CPA 2019 (Product Service Provider / Dealer Liability)
    - Section 35 CPA 2019 (Filing Consumer Grievance before Commission)
    - Section 39 CPA 2019 (Statutory Powers to Order Replacement/Refund)
    """
    for field_name, val in [
        ("owner_name", owner_name),
        ("owner_address", owner_address),
        ("manufacturer_name", manufacturer_name),
        ("dealer_name", dealer_name),
        ("dealer_address", dealer_address),
        ("vehicle_make_model", vehicle_make_model),
        ("vin_or_chassis", vin_or_chassis),
        ("purchase_date", purchase_date),
        ("defect_description", defect_description),
        ("remedy_sought", remedy_sought),
    ]:
        if not isinstance(val, str) or not val.strip():
            raise CalculatorInputError(f"{field_name} must be a non-empty string")
    
    if not isinstance(purchase_price, (int, float)) or purchase_price <= 0 or not math.isfinite(purchase_price):
        raise CalculatorInputError("purchase_price must be a positive finite number")
    if not isinstance(repair_attempts_count, int) or repair_attempts_count < 0:
        raise CalculatorInputError("repair_attempts_count must be a non-negative integer")
    if not isinstance(days_out_of_service, int) or days_out_of_service < 0:
        raise CalculatorInputError("days_out_of_service must be a non-negative integer")
    
    categories = CONSUMER_DEFECT_RULES["defect_categories"]
    if defect_category not in categories:
        raise CalculatorInputError(
            f"Invalid defect_category: {defect_category!r}. Allowed: {sorted(categories)}"
        )
    
    cat_info = categories[defect_category]
    is_lemon_threshold = (
        repair_attempts_count >= 3
        or days_out_of_service >= 30
        or cat_info["severity"] in ("critical", "life_threatening")
    )
    
    pecuniary = CONSUMER_DEFECT_RULES["pecuniary_jurisdiction"]
    if purchase_price <= pecuniary["District Commission"]["max_claim_amount"]:
        forum = pecuniary["District Commission"]["description"]
    elif purchase_price <= pecuniary["State Commission"]["max_claim_amount"]:
        forum = pecuniary["State Commission"]["description"]
    else:
        forum = pecuniary["National Commission"]["description"]
    
    cure_days = CONSUMER_DEFECT_RULES["notice_standards"]["statutory_cure_period_days"]
    
    statutory_citations = [
        "Section 2(10), Consumer Protection Act, 2019 (Definition of Inherent Defect)",
        "Section 84, Consumer Protection Act, 2019 (Manufacturer Product Liability)",
        "Section 86, Consumer Protection Act, 2019 (Dealer / Service Provider Joint Liability)",
        "Section 35 & 39, Consumer Protection Act, 2019 (Complaint & Mandatory Reliefs)",
        cat_info["benchmark_citations"],
    ]
    
    notice_text = f"""REGISTERED POST WITH ACKNOWLEDGEMENT DUE / SPEED POST / LEGAL NOTICE

Date: {purchase_date} (Transaction Reference)
To:
1. THE MANAGING DIRECTOR / GRIEVANCE OFFICER
   {manufacturer_name}
   (Product Manufacturer)

2. THE PRINCIPAL OFFICER / PROPRIETOR
   {dealer_name}
   {dealer_address}
   (Authorized Dealer / Product Service Provider)

FROM:
{owner_name}
{owner_address}

SUBJECT: STATUTORY LEGAL NOTICE UNDER SECTION 84 READ WITH SECTIONS 2(10), 35, AND 86 OF THE CONSUMER PROTECTION ACT, 2019 FOR INHERENT MANUFACTURING DEFECT IN VEHICLE {vehicle_make_model} (VIN: {vin_or_chassis})

Sir/Madam,

Under instructions and on behalf of my client/myself, {owner_name}, this statutory notice is hereby served upon you:

1. THE VEHICLE & TRANSACTION:
   That the Complainant purchased a brand-new vehicle model '{vehicle_make_model}', bearing VIN/Chassis Number '{vin_or_chassis}', from your authorized dealership '{dealer_name}' on {purchase_date} for a valuable consideration of Rs. {purchase_price:,.2f}/-.

2. NATURE OF INHERENT DEFECT & PRODUCT LIABILITY:
   That within the warranty period, the subject vehicle developed recurring and persistent defects classified under '{cat_info['title']}'.
   Specific factual details: {defect_description}
   The vehicle has undergone {repair_attempts_count} repeated unsuccessful repair attempts at your authorized service center and has remained completely unroadworthy and out of service for {days_out_of_service} cumulative days.

3. STATUTORY BREACH UNDER CPA 2019:
   Under Section 84 of the Consumer Protection Act, 2019, a product manufacturer is strictly liable in a product liability action for harm caused by a product suffering from a manufacturing defect, design flaw, or non-conformity with express warranty. The recurring breakdown violates Section 2(10) of the Act and constitutes grave deficiency of service under Section 2(11).
   Judicial Precedent: {cat_info['benchmark_citations']}

4. DEMAND FOR REMEDY:
   The Complainant hereby calls upon you, jointly and severally, to fulfill the following remedy within a statutory cure period of {cure_days} days from the receipt of this notice:
   - Remedy Demand: {remedy_sought}
   - Payment of Rs. 2,00,000/- towards compensatory damages for mental agony, harassment, and alternative commute expenditure incurred during {days_out_of_service} days of vehicle downtime.

5. NOTICE OF LEGAL ACTION:
   Take notice that should you fail or neglect to comply with the requisitions of this notice within {cure_days} days, the Complainant shall file an appropriate consumer complaint before the competent {forum} under Section 35 of the Consumer Protection Act, 2019, seeking an order under Section 39 for complete refund/replacement along with 18% p.a. interest, litigation costs, and exemplary punitive damages, entirely at your risk, cost, and legal peril.

Yours faithfully,

{owner_name}
(Complainant / Consumer)
"""

    return {
        "notice_text": notice_text.strip(),
        "pecuniary_forum": forum,
        "claim_amount": float(purchase_price),
        "is_lemon_threshold_met": is_lemon_threshold,
        "statutory_citations": statutory_citations,
        "cure_period_days": cure_days,
    }


def get_state_compounding_leniency_index() -> dict[str, Any]:
    """Calculate the Pan-India State Compounding Leniency Index and Ranking.
    
    Statutory Grounding:
    - Section 200, Motor Vehicles Act, 1988 (State powers of compounding).
    
    Measures the degree to which individual State Governments have reduced traffic penalty
    burdens below the Central MVA 2019 baseline schedules, ranking states from most lenient to strictest.
    """
    rankings: list[dict[str, Any]] = []
    
    for state_name, state_rec in STATE_DATA.items():
        schedule = state_rec.get("compounding_schedule")
        if not schedule or not isinstance(schedule, dict):
            continue
        
        shared_violations = [v for v in schedule if v in NATIONAL_FINES]
        if not shared_violations:
            continue
        
        central_sum = sum(float(NATIONAL_FINES[v]["fine"]) for v in shared_violations)
        state_sum = sum(float(schedule[v]) for v in shared_violations)
        
        if central_sum > 0:
            relief_pct = round(((central_sum - state_sum) / central_sum) * 100.0, 2)
        else:
            relief_pct = 0.0
        
        leniency_score = round(max(0.0, min(100.0, relief_pct)), 2)
        
        rankings.append({
            "state": state_name,
            "jurisdiction": state_rec.get("jurisdiction"),
            "notification_id": state_rec.get("notification_id"),
            "effective_date": state_rec.get("effective_date"),
            "compoundable_violations_count": len(shared_violations),
            "central_total": round(central_sum, 2),
            "state_compounded_total": round(state_sum, 2),
            "relief_pct": relief_pct,
            "leniency_score": leniency_score,
        })
    
    rankings.sort(key=lambda x: (-x["leniency_score"], x["state"]))
    for rank_idx, item in enumerate(rankings, start=1):
        item["rank"] = rank_idx
    
    total_states = len(rankings)
    avg_score = round(sum(r["leniency_score"] for r in rankings) / total_states, 2) if total_states > 0 else 0.0
    most_lenient = rankings[0]["state"] if rankings else "N/A"
    strictest = rankings[-1]["state"] if rankings else "N/A"
    
    return {
        "total_notified_states": total_states,
        "average_leniency_score": avg_score,
        "most_lenient_state": most_lenient,
        "strictest_state": strictest,
        "rankings": rankings,
    }


router = APIRouter()


@router.post(
    "/api/v1/consumer/divyangjan-benefits",
    response_model=DivyangjanBenefitsResponse,
    tags=["consumer_protection"],
    summary="Evaluate Divyangjan Adapted Vehicle GST Concession & Road Tax Exemptions",
)
def evaluate_divyangjan_benefits_endpoint(payload: DivyangjanBenefitsRequest) -> DivyangjanBenefitsResponse:
    """Evaluate 18% concessional GST, 100% road tax waiver, toll exemption, and Sec 52 alteration immunity."""
    try:
        res = calculate_divyangjan_concessions(
            vehicle_ex_showroom=payload.vehicle_ex_showroom,
            engine_cc=payload.engine_cc,
            fuel_type=payload.fuel_type,
            length_mm=payload.length_mm,
            state=payload.state,
            disability_pct=payload.disability_pct,
        )
        return DivyangjanBenefitsResponse.model_validate(res)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/consumer/generate-lemon-notice",
    response_model=LemonNoticeResponse,
    tags=["consumer_protection"],
    summary="Generate Statutory Lemon Law Legal Notice under CPA 2019",
)
def generate_lemon_notice_endpoint(payload: LemonNoticeRequest) -> LemonNoticeResponse:
    """Generate formal 15-day statutory legal notice to OEM/dealer under Sections 84 & 35 CPA 2019."""
    try:
        res = generate_lemon_law_notice(
            owner_name=payload.owner_name,
            owner_address=payload.owner_address,
            manufacturer_name=payload.manufacturer_name,
            dealer_name=payload.dealer_name,
            dealer_address=payload.dealer_address,
            vehicle_make_model=payload.vehicle_make_model,
            vin_or_chassis=payload.vin_or_chassis,
            purchase_date=payload.purchase_date,
            purchase_price=payload.purchase_price,
            defect_category=payload.defect_category,
            repair_attempts_count=payload.repair_attempts_count,
            days_out_of_service=payload.days_out_of_service,
            defect_description=payload.defect_description,
            remedy_sought=payload.remedy_sought,
        )
        return LemonNoticeResponse.model_validate(res)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/api/v1/consumer/state-leniency-index",
    response_model=StateLeniencyIndexResponse,
    tags=["consumer_protection"],
    summary="Pan-India State Compounding Leniency Index and Rankings",
)
def get_state_leniency_index_endpoint() -> StateLeniencyIndexResponse:
    """Retrieve Pan-India State Compounding Leniency Index, rankings, and concession metrics under Section 200 MVA."""
    res = get_state_compounding_leniency_index()
    return StateLeniencyIndexResponse.model_validate(res)
