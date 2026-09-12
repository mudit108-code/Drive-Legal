"""Typed Pydantic v2 domain schemas for DriveLegal India.Provides validation, serialization, and type guarantees for fine records,
jurisdictions, vehicle classifications, legal sections, citizen rights,
and calculation requests/responses.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, NonNegativeInt


class SourceModel(BaseModel):
    """Metadata for an official source or gazette notification."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(..., description="Unique citation identifier")
    title: str = Field(..., description="Title of legal document or authority")
    url: str = Field(..., description="HTTPS canonical URL")


class MetadataModel(BaseModel):
    """Metadata package root."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int
    last_reviewed: str
    sources: list[SourceModel]
    disclaimer: str | None = None


class FineRecordModel(BaseModel):
    """Statutory fine specification under the Motor Vehicles Act."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str = Field(..., description="Human-readable violation title")
    fine: NonNegativeInt = Field(..., description="Base fine in INR")
    imprisonment: str | None = Field(default=None, description="Statutory imprisonment clause")
    rule_section: str = Field(..., description="Primary conduct rule section (e.g. 119)")
    penalty_section: str = Field(..., description="Charging penalty section (e.g. 184)")
    allowed_vehicle_types: list[str] = Field(..., min_length=1)
    repeat_policy: Literal["not_applicable", "reference_only", "explicit"] = Field(...)
    fine_basis: Literal["fixed", "base_plus_excess_tonne", "per_excess_passenger"] = Field(...)
    apply_vehicle_multiplier: bool
    source_status: str
    source_ids: list[str] = Field(..., min_length=1)
    repeat_fine: NonNegativeInt | None = None
    extra_unit_fine: NonNegativeInt | None = None
    quantity_field: str | None = None
    quantity_label: str | None = None
    legal_note: str = Field(..., min_length=1)


class StateDataModel(BaseModel):
    """State or Union Territory jurisdictional profile and compounding schedule."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    surcharge: NonNegativeFloat = 0.0
    notes: list[str] = Field(default_factory=list)
    helmet_law: str
    speed_city: NonNegativeInt
    speed_highway: NonNegativeInt
    source_status: str
    source_ids: list[str]
    legal_note: str
    notification_id: str | None = None
    effective_date: str | None = None
    jurisdiction: str | None = None
    compounding_schedule: dict[str, NonNegativeInt] | None = None


class LegalSectionModel(BaseModel):
    """Statutory section in the Motor Vehicles Act catalogue."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    section: str = Field(..., description="Section identifier, e.g. 'Section 185'")
    chapter: str | None = Field(default=None, description="Act Chapter")
    title: str = Field(..., description="Statutory title")
    description: str = Field(..., description="Authoritative statutory text")
    url: str | None = None


class CitizenRightModel(BaseModel):
    """Citizen legal empowerment and redressal guide entry."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(..., description="Identifier for the right/workflow")
    title: str = Field(..., description="Citizen-friendly title")
    statutory_basis: str = Field(..., description="CMVR rule or Supreme Court guidelines")
    summary: str = Field(..., description="Core legal takeaway")
    key_provisions: list[str] = Field(..., min_length=1)
    source_id: str = Field(..., description="Citation ID in metadata.json")


# --- Calculation Request / Response Models ---

class SingleCalculationRequest(BaseModel):
    """Parameters to calculate a single traffic fine."""
    model_config = ConfigDict(extra="forbid")

    violation_key: str = Field(..., description="Identifier from national_fines.json")
    vehicle_type: str = Field(..., description="Vehicle classification category")
    state: str = Field(..., description="State or Union Territory name")
    quantity: float | None = Field(default=None, description="Excess tonnes or excess passengers")
    is_repeat: bool = Field(default=False, description="Whether violation is a second/subsequent offence")


class ResolvedSource(BaseModel):
    """Resolved source citation for client display."""
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    url: str


class SingleCalculationResponse(BaseModel):
    """Itemized breakdown of a calculated traffic fine."""
    violation_key: str
    description: str
    vehicle_type: str
    state: str
    rule_section: str
    penalty_section: str
    base_fine: float
    vehicle_multiplier: float
    calculated_fine: float
    state_surcharge_amount: float
    state_compounding_applied: bool
    compounded_fine: int | None = None
    notification_id: str | None = None
    effective_date: str | None = None
    effective_fine: float
    savings_from_compounding: float
    sources: list[ResolvedSource]
    legal_note: str | None = None


class MultiChallanItemRequest(BaseModel):
    """Single line item in a multi-challan cart request."""
    model_config = ConfigDict(extra="forbid")

    violation_key: str
    vehicle_type: str
    quantity: float | None = None
    is_repeat: bool = False


class MultiChallanRequest(BaseModel):
    """Request to calculate multiple violations in a single session."""
    model_config = ConfigDict(extra="forbid")

    items: list[MultiChallanItemRequest] = Field(..., min_length=1)
    state: str


class MultiChallanItemResponse(BaseModel):
    """Calculated breakdown for a single item in a multi-challan summary."""
    base_fine: float
    vehicle_multiplier: float
    state_surcharge: float
    total: float
    rule_section: str
    penalty_section: str
    compounding_fee: int | None = None
    compounding_notification_id: str | None = None
    compounding_effective_date: str | None = None
    legal_note: str | None = None


class MultiChallanResponse(BaseModel):
    """Aggregated multi-challan summary and grand totals."""
    state: str
    items: list[dict[str, Any]]
    item_count: int
    total_base_fine: float
    total_vehicle_adjustment: float
    total_state_surcharge: float
    total_repeat_penalty: float
    grand_total: float
    has_compounding_items: bool
    total_compounding_fee: float | None = None


class CompoundingMatrixRow(BaseModel):
    """Row in the inter-state compounding comparison matrix."""
    violation_key: str
    description: str
    penalty_section: str
    central_fine: int
    state_fees: dict[str, int | None]


class CompoundingMatrixResponse(BaseModel):
    """Complete inter-state compounding comparison matrix."""
    states: list[str]
    rows: list[CompoundingMatrixRow]


DisputeCategoryType = Literal[
    "digilocker_rejection",
    "unapplied_compounding",
    "grace_period_demand",
    "wrong_vehicle_or_cloned_plate",
]


class DisputeRepresentationRequest(BaseModel):
    """Parameters to generate a formal legal grievance / representation letter."""
    model_config = ConfigDict(extra="forbid")

    citizen_name: str = Field(..., min_length=1)
    vehicle_number: str = Field(..., min_length=1)
    challan_number: str = Field(..., min_length=1)
    challan_date: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    issuing_authority: str = Field(..., min_length=1)
    dispute_type: DisputeCategoryType
    violation_key: str | None = None
    additional_facts: str | None = None


class DisputeRepresentationResponse(BaseModel):
    """Formatted legal representation notice and statutory metadata."""
    letter_text: str
    dispute_type: str
    statutory_authority: str
    challan_number: str
    vehicle_number: str


class FleetChallanInputRow(BaseModel):
    """Input row representing an individual challan in a commercial fleet batch."""
    model_config = ConfigDict(extra="ignore")

    challan_id: str | None = None
    vehicle_number: str | None = None
    vehicle_type: str
    state: str
    violation_key: str
    amount_paid: float
    quantity: float | None = None
    repeat: bool = False


class BatchAuditRequest(BaseModel):
    """Request to audit multiple commercial fleet challans."""
    model_config = ConfigDict(extra="forbid")

    records: list[FleetChallanInputRow] = Field(..., min_length=1)


class BatchAuditResponse(BaseModel):
    """Aggregated financial audit report for a commercial fleet batch."""
    total_challans_audited: int
    total_amount_paid: float
    total_legally_due: float
    total_potential_overcharges: float
    overcharged_count: int
    compliant_count: int
    court_only_count: int
    undercharged_count: int
    records: list[dict[str, Any]]


	# --- Domain Package Validator Helper ---

def validate_package_with_models(
    national_fines: dict[str, Any],
    vehicle_types: dict[str, float],
    state_data: dict[str, Any],
    metadata: dict[str, Any],
    legal_sections: list[dict[str, Any]],
    citizen_rights: list[dict[str, Any]],
) -> tuple[int, int, int, int, int, int]:
    """Validate all bundled data sets using Pydantic v2 schemas.
    Returns counts of validated records upon success.
    """
    # 1. Metadata
    MetadataModel.model_validate(metadata)

    # 2. National fines
    for key, rec in national_fines.items():
        FineRecordModel.model_validate(rec)

    # 3. Vehicle types
    for v, mult in vehicle_types.items():
        if not isinstance(mult, (float, int)) or mult <= 0 or float('inf') == mult or mult != mult:
            raise ValueError(f"Invalid multiplier for {v}: {mult}")

    # 4. States
    for s, rec in state_data.items():
        StateDataModel.model_validate(rec)

    # 5. Legal sections
    for sec in legal_sections:
        LegalSectionModel.model_validate(sec)

    # 6. Citizen rights
    for cr in citizen_rights:
        CitizenRightModel.model_validate(cr)

    return (
        len(national_fines),
        len(vehicle_types),
        len(state_data),
        len(metadata.sources) if hasattr(metadata, 'sources') else len(metadata.get('sources', [])),
        len(legal_sections),
        len(citizen_rights),
    )

class VehicleRegistrationResolution(BaseModel):
    """Resolved jurisdictional and RTO details for an Indian vehicle registration number."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_registration: str
    normalized_registration: str
    is_valid: bool
    is_bh_series: bool
    registration_year: str | None = None
    state_code: str | None = None
    state_name: str | None = None
    rto_code: str | None = None
    rto_name: str | None = None
    series_code: str | None = None
    vehicle_unique_number: str | None = None
    jurisdiction_type: str
    statutory_note: str

class TrafficStopSafeguardModel(BaseModel):
    """Statutory citizen safeguard during on-the-road police traffic stops."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    statutory_authority: str
    summary: str
    citizen_action: str
    legal_citations: list[str]

