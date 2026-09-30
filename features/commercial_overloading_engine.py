"""Commercial dynamic axle-weight overloading and excess penalty engine (Sec 113, 114, 194(1) MVA).

Self-contained feature module: models, data loading, logic and API router live
here so this feature never edits app_core.py, api.py or models.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

import app_core
from app_core import CalculatorInputError, _read_json


# --- Commercial Axle-Weight Overloading Models (Sec 113, 114, 194(1) MVA) ---

class AxleConfigurationModel(BaseModel):
    """MoRTH S.O. 2822(E) statutory axle configuration and gross weight limit."""
    model_config = ConfigDict(frozen=True)

    code: str
    name: str
    tyres: int
    max_permissible_gvw_tonnes: float
    steer_axle_limit_tonnes: float
    drive_axle_limit_tonnes: float
    description: str


class OverloadingCalculationRequest(BaseModel):
    """Request payload to calculate statutory commercial vehicle overloading penalty."""
    model_config = ConfigDict(extra="forbid")

    registered_gvw_tonnes: float = Field(..., gt=0, description="Gross Vehicle Weight in tonnes as per RC")
    actual_weight_tonnes: float = Field(..., ge=0, description="Measured laden weight in tonnes at weighbridge")
    axle_configuration: str | None = Field(None, description="Optional MoRTH axle configuration code")
    refused_weighment: bool = Field(False, description="Whether weighment was refused (Sec 194(2) penalty)")


class OverloadingCalculationResponse(BaseModel):
    """Statutory overloading financial and offloading liability assessment."""
    model_config = ConfigDict(frozen=True)

    registered_gvw_tonnes: float
    actual_weight_tonnes: float
    excess_weight_tonnes: float
    chargeable_excess_tonnes: int
    is_overloaded: bool
    refused_weighment: bool
    compliance_status: str
    base_overloading_penalty: int
    excess_tonnage_penalty: int
    refusal_penalty: int
    total_penalty: int
    offloading_mandated: bool
    axle_configuration: str | None = None
    axle_configuration_name: str | None = None
    config_statutory_warning: str | None = None
    legal_summary: str
    statutory_basis: str


# ---------------------------------------------------------------------------
# Commercial Axle-Weight Overloading & Excess Penalty Engine (Sec 113, 114, 194(1) MVA)
# ---------------------------------------------------------------------------

AXLE_WEIGHT_LIMITS: dict[str, Any] = _read_json("axle_weight_limits.json")


def get_safe_axle_configurations() -> list[dict[str, Any]]:
    """Return statutory safe axle weight limits and configurations under MoRTH S.O. 2822(E)."""
    return AXLE_WEIGHT_LIMITS.get("configurations", [])


def calculate_overloading_penalty(
    registered_gvw_tonnes: float,
    actual_weight_tonnes: float,
    axle_configuration: str | None = None,
    refused_weighment: bool = False,
) -> dict[str, Any]:
    """Calculate statutory overloading penalty under Sections 113, 114, 194(1), and 194(2) MVA 1988/2019.

    Args:
        registered_gvw_tonnes: Gross Vehicle Weight in tonnes as stated in Registration Certificate.
        actual_weight_tonnes: Measured weight in tonnes at highway weighbridge / static scale.
        axle_configuration: Optional axle configuration code (e.g. '2_axle_rigid', '3_axle_rigid').
        refused_weighment: Whether driver/owner refused to submit to weighment (Sec 114 / 194(2)).

    Returns:
        dict with detailed breakdown of base penalty, excess tonnes, per-tonne surcharge,
        refusal penalty, offloading requirement, and legal citations.
    """
    if registered_gvw_tonnes <= 0:
        raise CalculatorInputError(f"registered_gvw_tonnes must be positive: {registered_gvw_tonnes}")
    if actual_weight_tonnes < 0:
        raise CalculatorInputError(f"actual_weight_tonnes cannot be negative: {actual_weight_tonnes}")

    params = AXLE_WEIGHT_LIMITS.get("penalty_parameters", {})
    base_fine = params.get("base_overloading_fine_inr", 20000)
    per_tonne_rate = params.get("per_excess_tonne_fine_inr", 2000)
    refusal_fine = params.get("refusal_to_weigh_fine_inr", 40000)

    # Check against safe axle configuration if provided
    config_details = None
    config_warning = None
    if axle_configuration:
        configs = {c["code"]: c for c in AXLE_WEIGHT_LIMITS.get("configurations", [])}
        if axle_configuration in configs:
            config_details = configs[axle_configuration]
            max_statutory_gvw = config_details["max_permissible_gvw_tonnes"]
            if registered_gvw_tonnes > max_statutory_gvw:
                config_warning = (
                    f"Registered GVW ({registered_gvw_tonnes}T) exceeds MoRTH S.O. 2822(E) "
                    f"maximum statutory limit ({max_statutory_gvw}T) for configuration {config_details['name']}."
                )

    excess_weight = round(max(0.0, actual_weight_tonnes - registered_gvw_tonnes), 3)
    is_overloaded = excess_weight > 0.0

    import math
    chargeable_excess_tonnes = math.ceil(excess_weight) if is_overloaded else 0
    excess_tonne_penalty = chargeable_excess_tonnes * per_tonne_rate

    statutory_base_penalty = base_fine if is_overloaded else 0
    statutory_refusal_penalty = refusal_fine if refused_weighment else 0
    total_penalty = statutory_base_penalty + excess_tonne_penalty + statutory_refusal_penalty

    if is_overloaded:
        status_msg = f"OVERLOADED by {excess_weight:.2f} tonnes ({chargeable_excess_tonnes} chargeable tonnes)"
        offloading_required = True
        legal_summary = (
            f"Under Sec 194(1) MVA 1988, overloading incurs a base penalty of Rs {base_fine:,} "
            f"plus Rs {per_tonne_rate:,}/tonne for {chargeable_excess_tonnes} tonnes = Rs {excess_tonne_penalty:,}. "
            "Under Sec 194(1)(b), the vehicle must not be permitted to move until the excess weight "
            "is offloaded at the risk and expense of the transporter."
        )
    elif refused_weighment:
        status_msg = "REFUSAL TO WEIGH (Sec 194(2) MVA)"
        offloading_required = False
        legal_summary = (
            f"Under Sec 194(2) MVA 1988, refusal to stop or submit to weighment under Sec 114 "
            f"attracts a statutory fine of Rs {refusal_fine:,}."
        )
    else:
        status_msg = "COMPLIANT — Within Registered GVW"
        offloading_required = False
        legal_summary = (
            f"Actual measured weight ({actual_weight_tonnes}T) is within registered "
            f"Gross Vehicle Weight ({registered_gvw_tonnes}T). No overloading penalty applicable."
        )

    return {
        "registered_gvw_tonnes": registered_gvw_tonnes,
        "actual_weight_tonnes": actual_weight_tonnes,
        "excess_weight_tonnes": excess_weight,
        "chargeable_excess_tonnes": chargeable_excess_tonnes,
        "is_overloaded": is_overloaded,
        "refused_weighment": refused_weighment,
        "compliance_status": status_msg,
        "base_overloading_penalty": statutory_base_penalty,
        "excess_tonnage_penalty": excess_tonne_penalty,
        "refusal_penalty": statutory_refusal_penalty,
        "total_penalty": total_penalty,
        "offloading_mandated": offloading_required,
        "axle_configuration": config_details["code"] if config_details else None,
        "axle_configuration_name": config_details["name"] if config_details else None,
        "config_statutory_warning": config_warning,
        "legal_summary": legal_summary,
        "statutory_basis": AXLE_WEIGHT_LIMITS["statutory_basis"],
    }


router = APIRouter()


@router.get(
    "/api/v1/commercial/axle-limits",
    response_model=list[AxleConfigurationModel],
    tags=["commercial"],
    summary="MoRTH Statutory Safe Axle Weight Configurations (S.O. 2822(E))",
)
def get_axle_limits_endpoint() -> list[AxleConfigurationModel]:
    """Retrieve MoRTH statutory safe axle weight limits and configurations for commercial transport."""
    configs = get_safe_axle_configurations()
    return [AxleConfigurationModel.model_validate(c) for c in configs]


@router.post(
    "/api/v1/commercial/overloading-calculator",
    response_model=OverloadingCalculationResponse,
    tags=["commercial"],
    summary="Commercial Vehicle Overloading Penalty Calculator (Sec 194(1) MVA)",
)
def calculate_overloading_endpoint(
    payload: OverloadingCalculationRequest,
) -> OverloadingCalculationResponse:
    """Compute statutory overloading penalties under Section 194(1) and 194(2) MVA 1988/2019,
    including base penalty (Rs 20k), per-tonne excess rate (Rs 2k/tonne), and offloading liabilities."""
    try:
        res = calculate_overloading_penalty(
            registered_gvw_tonnes=payload.registered_gvw_tonnes,
            actual_weight_tonnes=payload.actual_weight_tonnes,
            axle_configuration=payload.axle_configuration,
            refused_weighment=payload.refused_weighment,
        )
        return OverloadingCalculationResponse.model_validate(res)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Overloading calculation error: {exc}",
        ) from exc
