"""National Vehicle Scrappage (V-VCSF) certificate rebate and EV green-plate privilege calculator.

Self-contained feature module: models, data loading, logic and API router live
here so this feature never edits app_core.py, api.py or models.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    status,
)
from pydantic import BaseModel, ConfigDict, Field

import app_core
from app_core import CalculatorInputError, _read_json, _require


# --- Vehicle Scrappage Policy & EV Concession Models ---
class ScrappageIncentiveRequest(BaseModel):
    """Input payload to compute vehicle scrappage Certificate of Deposit (CoD) benefits."""
    model_config = ConfigDict(extra="forbid")

    vehicle_type: str = Field(..., min_length=2, max_length=50)
    new_vehicle_ex_showroom: float = Field(..., gt=0)
    state: str = Field(..., min_length=2, max_length=50)
    vehicle_age_years: int = Field(..., ge=0, le=100)
    is_transport: bool = False


class ScrappageIncentiveResponse(BaseModel):
    """Vehicle scrappage incentives, rebates, and fee waivers under MoRTH G.S.R. 653(E)."""
    model_config = ConfigDict(frozen=True)

    vehicle_type: str
    new_vehicle_ex_showroom: float
    state: str
    vehicle_age_years: int
    is_transport: bool
    is_eligible: bool
    minimum_scrappage_age: int
    scrap_value_estimate: float
    oem_discount_estimate: float
    estimated_road_tax: float
    road_tax_rebate: float
    road_tax_rebate_pct: float
    registration_fee_waiver: float
    total_financial_benefits: float
    statutory_advisory: str
    statutory_authority: dict[str, str]


class EVConcessionsResponse(BaseModel):
    """Statutory privileges and tax concessions for Electric Vehicles (Green Plate)."""
    model_config = ConfigDict(frozen=True)

    state: str
    vehicle_category: str
    policy_name: str
    road_tax_concession_pct: float
    registration_fee_concession_pct: float
    permit_exemption_active: bool
    zero_emission_urban_delivery: bool
    green_plate_specification: str
    statutory_permit_exemption_basis: str
    legal_advisory: str


def _validate_scrappage_rates(data: Any) -> None:
    _require(isinstance(data, dict), "scrappage_rates must be an object")
    _require("scrappage_parameters" in data and isinstance(data["scrappage_parameters"], dict), "missing scrappage_parameters")
    _require("registration_fee_benchmarks" in data and isinstance(data["registration_fee_benchmarks"], dict), "missing registration_fee_benchmarks")


def _validate_ev_state_incentives(data: Any) -> None:
    _require(isinstance(data, dict), "ev_state_incentives must be an object")
    _require("statutory_framework" in data and isinstance(data["statutory_framework"], dict), "missing statutory_framework")
    _require("state_incentives" in data and isinstance(data["state_incentives"], dict), "missing state_incentives")


SCRAPPAGE_RATES = _read_json("scrappage_rates.json")
_validate_scrappage_rates(SCRAPPAGE_RATES)
EV_STATE_INCENTIVES = _read_json("ev_state_incentives.json")
_validate_ev_state_incentives(EV_STATE_INCENTIVES)


# ---------------------------------------------------------------------------
# National Vehicle Scrappage Policy (V-VCSF) & EV Green Plate Engine
# ---------------------------------------------------------------------------
def calculate_scrappage_incentives(
    vehicle_type: str,
    new_vehicle_ex_showroom: float,
    state: str,
    vehicle_age_years: int,
    is_transport: bool = False,
) -> dict[str, Any]:
    """Calculate Certificate of Deposit (CoD) financial incentives under National Vehicle Scrappage Policy."""
    if not isinstance(new_vehicle_ex_showroom, (int, float)) or new_vehicle_ex_showroom <= 0:
        raise CalculatorInputError("New vehicle ex-showroom price must be a positive number.")
    if not isinstance(vehicle_age_years, int) or vehicle_age_years < 0:
        raise CalculatorInputError("Vehicle age must be a non-negative integer.")
    if not isinstance(vehicle_type, str) or not vehicle_type.strip():
        raise CalculatorInputError("Vehicle type must be a non-empty string.")

    rules = SCRAPPAGE_RATES
    params = rules.get("scrappage_parameters", {})
    benchmarks = rules.get("registration_fee_benchmarks", {})
    tax_rates = rules.get("estimated_road_tax_rates_pct", {})

    min_age = params.get("min_age_years_transport", 10) if is_transport else params.get("min_age_years_non_transport", 15)
    is_eligible = vehicle_age_years >= min_age

    scrap_rate = params.get("scrap_value_rate_pct", 5.0) / 100.0
    oem_rate = params.get("oem_discount_rate_pct", 5.0) / 100.0
    road_tax_rebate_pct = params.get("road_tax_rebate_transport_pct", 15.0) if is_transport else params.get("road_tax_rebate_non_transport_pct", 25.0)

    scrap_value = round(new_vehicle_ex_showroom * scrap_rate, 2)
    oem_discount = round(new_vehicle_ex_showroom * oem_rate, 2)

    st_tax_rate = tax_rates.get(state, tax_rates.get("default", 10.0)) / 100.0
    estimated_road_tax = round(new_vehicle_ex_showroom * st_tax_rate, 2)
    road_tax_rebate = round(estimated_road_tax * (road_tax_rebate_pct / 100.0), 2)

    reg_fee_waiver = float(benchmarks.get(vehicle_type, benchmarks.get("Light Motor Vehicle (Car)", 1000)))

    total_benefits = round(scrap_value + oem_discount + road_tax_rebate + reg_fee_waiver, 2)

    if not is_eligible:
        advisory = (
            f"Vehicle age ({vehicle_age_years} years) does not meet the minimum statutory threshold "
            f"({min_age} years) for voluntary scrappage incentives under MoRTH G.S.R. 653(E)."
        )
    else:
        advisory = (
            f"Eligible for Certificate of Deposit (CoD). You can avail ₹{total_benefits:,.2f} in total financial "
            f"rebates against the purchase of a new vehicle across scrap value, OEM discount, road tax concession, "
            f"and registration fee waiver (CMVR Rule 52)."
        )

    return {
        "vehicle_type": vehicle_type,
        "new_vehicle_ex_showroom": float(new_vehicle_ex_showroom),
        "state": state,
        "vehicle_age_years": vehicle_age_years,
        "is_transport": is_transport,
        "is_eligible": is_eligible,
        "minimum_scrappage_age": min_age,
        "scrap_value_estimate": scrap_value,
        "oem_discount_estimate": oem_discount,
        "estimated_road_tax": estimated_road_tax,
        "road_tax_rebate": road_tax_rebate,
        "road_tax_rebate_pct": road_tax_rebate_pct,
        "registration_fee_waiver": reg_fee_waiver,
        "total_financial_benefits": total_benefits,
        "statutory_advisory": advisory,
        "statutory_authority": rules.get("statutory_framework", {}),
    }


def get_ev_privileges_and_concessions(state: str, vehicle_category: str = "Two-Wheeler") -> dict[str, Any]:
    """Retrieve statutory privileges and tax concessions for Electric Vehicles (Green Plate)."""
    rules = EV_STATE_INCENTIVES
    framework = rules.get("statutory_framework", {})
    states = rules.get("state_incentives", {})

    st_info = states.get(state, states.get("default", {}))

    return {
        "state": state,
        "vehicle_category": vehicle_category,
        "policy_name": st_info.get("policy_name", "National EV Guidelines"),
        "road_tax_concession_pct": float(st_info.get("road_tax_concession_pct", 100.0)),
        "registration_fee_concession_pct": float(st_info.get("registration_fee_concession_pct", 100.0)),
        "permit_exemption_active": bool(st_info.get("permit_exemption_active", True)),
        "zero_emission_urban_delivery": bool(st_info.get("zero_emission_urban_delivery", True)),
        "green_plate_specification": framework.get("green_plate_specification", ""),
        "statutory_permit_exemption_basis": framework.get("permit_exemption_provision", ""),
        "legal_advisory": (
            "Electric Vehicles bearing green registration plates are exempt from commercial permit mandates "
            "under Section 66(1) MVA per MoRTH S.O. 3064(E), and enjoy preferential road tax and city entry concessions."
        ),
    }


router = APIRouter()


@router.post(
    "/api/v1/green/scrappage-incentives",
    response_model=ScrappageIncentiveResponse,
    tags=["green_mobility"],
    summary="Compute National Scrappage Policy (V-VCSF) Rebates and CoD Benefits",
)
def compute_scrappage_endpoint(request: ScrappageIncentiveRequest) -> ScrappageIncentiveResponse:
    """Calculate scrap value, OEM discount, road tax concession, and registration fee waivers under MoRTH G.S.R. 653(E)."""
    try:
        result = calculate_scrappage_incentives(
            vehicle_type=request.vehicle_type,
            new_vehicle_ex_showroom=request.new_vehicle_ex_showroom,
            state=request.state,
            vehicle_age_years=request.vehicle_age_years,
            is_transport=request.is_transport,
        )
        return ScrappageIncentiveResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/api/v1/green/ev-privileges",
    response_model=EVConcessionsResponse,
    tags=["green_mobility"],
    summary="Get EV Green Number Plate Statutory Privileges and State Tax Concessions",
)
def get_ev_privileges_endpoint(
    state: str = Query("Delhi", description="State name for EV policy lookup"),
    vehicle_category: str = Query("Two-Wheeler", description="Vehicle category"),
) -> EVConcessionsResponse:
    """Retrieve road tax waivers, Section 66 permit exemptions, and green plate rights."""
    result = get_ev_privileges_and_concessions(state=state, vehicle_category=vehicle_category)
    return EVConcessionsResponse.model_validate(result)
