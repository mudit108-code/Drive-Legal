"""FastAPI Headless REST API Microservice for DriveLegal India.

Provides high-performance, typed endpoints for traffic fine calculations,
multi-challan cart estimation, Section 200 state compounding matrix queries,
and statutory legal catalogue search.
"""

from __future__ import annotations

from typing import Any
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

import app_core
from models import (
    FleetAuditAnalyticsResponse,
    StateCompoundingReliefStatModel,
    VehicleRegistrationResolution,
    BatchAuditRequest,
    BatchAuditResponse,
    CitizenRightModel,
    CompoundingMatrixResponse,
    DisputeRepresentationRequest,
    DisputeRepresentationResponse,
    LegalSectionModel,
    MultiChallanRequest,
    MultiChallanResponse,
    SingleCalculationRequest,
    SingleCalculationResponse,
)

app = FastAPI(
    title="DriveLegal India — Traffic Law & Challan Engine API",
    description=(
        "Production-grade headless API for Indian Motor Vehicles Act (MVA 1988/2019) fine calculations, "
        "Section 200 state gazette compounding resolution, and citizen dispute awareness."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for web and mobile frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"], summary="Liveness & Readiness Health Check")
@app.get("/api/v1/health", tags=["health"], summary="API Health and Dataset Metadata")
def health_check() -> dict[str, Any]:
    """Verify service health and report bundled dataset dimensions."""
    compounding_states = [s for s, d in app_core.STATE_DATA.items() if d.get("compounding_schedule")]
    return {
        "status": "healthy",
        "service": "DriveLegal India Core API",
        "version": "2.0.0",
        "offline_first": True,
        "metrics": {
            "national_violations": len(app_core.NATIONAL_FINES),
            "vehicle_classes": len(app_core.VEHICLE_TYPES),
            "jurisdictions_covered": len(app_core.STATE_DATA),
            "verified_compounding_states": len(compounding_states),
            "statutory_sections": len(app_core.LEGAL_SECTIONS),
            "citizen_rights_guides": len(app_core.CITIZEN_RIGHTS),
            "rto_jurisdictions": len(app_core.RTO_DIRECTORY.get("state_codes", {})),
        },
    }


@app.get("/api/v1/violations", tags=["catalogue"], summary="List and Filter Traffic Violations")
def get_violations(
    vehicle_type: str | None = Query(default=None, description="Filter by allowed vehicle classification"),
    search: str | None = Query(default=None, description="Filter by title or section text"),
) -> list[dict[str, Any]]:
    """Retrieve all statutory violations, with optional vehicle and text search filters."""
    results = []
    search_lower = search.lower().strip() if search else None

    for key, rec in app_core.NATIONAL_FINES.items():
        if vehicle_type and vehicle_type not in rec.get("allowed_vehicle_types", []):
            continue
        if search_lower:
            text = f"{rec['description']} {rec['rule_section']} {rec['penalty_section']} {rec['legal_note']}".lower()
            if search_lower not in text:
                continue
        item = dict(rec)
        item["violation_key"] = key
        results.append(item)

    return sorted(results, key=lambda x: x["description"])


@app.get("/api/v1/states", tags=["jurisdictions"], summary="List States and Compounding Availability")
def get_states(
    compounding_only: bool = Query(default=False, description="Filter only to states with verified compounding schedules"),
) -> list[dict[str, Any]]:
    """Retrieve jurisdictions and their Section 200 compounding schedule metadata."""
    results = []
    for state_name in sorted(app_core.STATE_DATA):
        data = app_core.STATE_DATA[state_name]
        has_schedule = bool(data.get("compounding_schedule"))
        if compounding_only and not has_schedule:
            continue
        results.append({
            "state": state_name,
            "has_compounding_schedule": has_schedule,
            "notification_id": data.get("notification_id"),
            "effective_date": data.get("effective_date"),
            "jurisdiction": data.get("jurisdiction"),
            "surcharge": data.get("surcharge", 0.0),
        })
    return results


@app.post(
    "/api/v1/calculate",
    response_model=SingleCalculationResponse,
    tags=["calculator"],
    summary="Calculate Single Traffic Violation Fine",
)
def calculate_fine_endpoint(payload: SingleCalculationRequest) -> SingleCalculationResponse:
    """Calculate the statutory fine, vehicle adjustments, and state compounding rate."""
    try:
        res = app_core.calculate_fine(
            violation_key=payload.violation_key,
            vehicle_key=payload.vehicle_type,
            state=payload.state,
            repeat=payload.is_repeat,
            quantity=payload.quantity,
        )
        fine_rec = app_core.NATIONAL_FINES[payload.violation_key]
        compounded_fee = res.get("compounding_fee")
        state_compounding_applied = compounded_fee is not None
        effective_fine = float(compounded_fee if state_compounding_applied else res["total"])
        savings = float(max(0.0, res["total"] - effective_fine)) if state_compounding_applied else 0.0

        return SingleCalculationResponse(
            violation_key=payload.violation_key,
            description=fine_rec["description"],
            vehicle_type=payload.vehicle_type,
            state=payload.state,
            rule_section=res["rule_section"],
            penalty_section=res["penalty_section"],
            base_fine=float(res["base_fine"]),
            vehicle_multiplier=float(res["vehicle_multiplier"]),
            calculated_fine=float(res["total"]),
            state_surcharge_amount=float(res["state_surcharge"]),
            state_compounding_applied=state_compounding_applied,
            compounded_fine=compounded_fee,
            notification_id=res.get("compounding_notification_id"),
            effective_date=res.get("compounding_effective_date"),
            effective_fine=effective_fine,
            savings_from_compounding=savings,
            sources=[{"id": s["id"], "title": s["title"], "url": s["url"]} for s in res.get("sources", [])],
            legal_note=res.get("legal_note"),
        )
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Calculation error: {exc}") from exc


@app.post(
    "/api/v1/calculate-multi",
    response_model=MultiChallanResponse,
    tags=["calculator"],
    summary="Calculate Multi-Offence Challan Session",
)
def calculate_multi_fine_endpoint(payload: MultiChallanRequest) -> MultiChallanResponse:
    """Calculate multiple violations in an aggregate challan cart session."""
    try:
        items_payload = [
            {
                "violation_key": item.violation_key,
                "vehicle_key": item.vehicle_type,
                "repeat": item.is_repeat,
                "quantity": item.quantity,
            }
            for item in payload.items
        ]
        res = app_core.calculate_multi_fine(items=items_payload, state=payload.state)
        return MultiChallanResponse.model_validate(res)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Multi-calculation error: {exc}") from exc


@app.get(
    "/api/v1/compounding-matrix",
    response_model=CompoundingMatrixResponse,
    tags=["compounding"],
    summary="Inter-State Section 200 Compounding Comparison Matrix",
)
def get_compounding_matrix_endpoint(
    violations: list[str] | None = Query(default=None, description="Optional violation keys to filter rows"),
) -> CompoundingMatrixResponse:
    """Compare Section 200 compounding rates across all 8 verified states against statutory base fines."""
    try:
        matrix = app_core.get_compounding_comparison_matrix(violation_keys=violations)
        return CompoundingMatrixResponse.model_validate(matrix)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.get("/api/v1/laws", response_model=list[LegalSectionModel], tags=["catalogue"], summary="Search Traffic Law Sections")
def get_laws(
    q: str | None = Query(default=None, description="Search query by section number, title, or text"),
) -> list[dict[str, Any]]:
    """Search and retrieve the bundled statutory legal catalogue."""
    if q and q.strip():
        return app_core.search_legal_sections(q.strip())
    return app_core.LEGAL_SECTIONS


@app.get("/api/v1/citizen-rights", response_model=list[CitizenRightModel], tags=["citizen_rights"], summary="Citizen Rights & Grievance Guides")
def get_citizen_rights(
    id: str | None = Query(default=None, description="Optional ID to fetch single right guide"),
) -> list[dict[str, Any]]:
    """Retrieve citizen legal guides on DigiLocker validity, 15-day grace periods, and dispute portals."""
    if id and id.strip():
        guide = next((g for g in app_core.CITIZEN_RIGHTS if g["id"] == id.strip()), None)
        if not guide:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Citizen right guide '{id}' not found")
        return [guide]
    return app_core.CITIZEN_RIGHTS


@app.get("/api/v1/dispute-types", tags=["disputes"], summary="List Available Dispute Grounds & Authorities")
def get_dispute_types() -> dict[str, Any]:
    """Retrieve recognized statutory grounds for disputing an e-challan."""
    return app_core.DISPUTE_CATEGORIES


@app.post(
    "/api/v1/dispute-representation",
    response_model=DisputeRepresentationResponse,
    tags=["disputes"],
    summary="Draft Formal Statutory Representation Letter",
)
def create_dispute_representation(payload: DisputeRepresentationRequest) -> DisputeRepresentationResponse:
    """Generate a formal legal grievance / representation letter citing exact sections and rules."""
    try:
        letter = app_core.generate_dispute_representation(
            citizen_name=payload.citizen_name,
            vehicle_number=payload.vehicle_number,
            challan_number=payload.challan_number,
            challan_date=payload.challan_date,
            state=payload.state,
            issuing_authority=payload.issuing_authority,
            dispute_type=payload.dispute_type,
            violation_key=payload.violation_key,
            additional_facts=payload.additional_facts,
        )
        meta = app_core.DISPUTE_CATEGORIES[payload.dispute_type]
        return DisputeRepresentationResponse(
            letter_text=letter,
            dispute_type=payload.dispute_type,
            statutory_authority=meta["statutory_authority"],
            challan_number=payload.challan_number,
            vehicle_number=payload.vehicle_number,
        )
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Dispute generation error: {exc}") from exc


@app.post(
    "/api/v1/fleet/audit-batch",
    response_model=BatchAuditResponse,
    tags=["fleet"],
    summary="Audit Commercial Fleet Challan Batch",
)
def audit_fleet_batch_endpoint(payload: BatchAuditRequest) -> BatchAuditResponse:
    """Audit multiple fleet challans against Section 200 state compounding rates and flag overcharges."""
    try:
        records_payload = [rec.model_dump() for rec in payload.records]
        res = app_core.audit_challan_batch(records_payload)
        return BatchAuditResponse.model_validate(res)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fleet audit error: {exc}") from exc


@app.get("/api/v1/fleet/sample-csv", tags=["fleet"], summary="Download Fleet Audit Sample CSV Template")
def get_sample_csv() -> dict[str, str]:
    """Provide a reference CSV format for bulk fleet challan auditing."""
    sample_csv = (
        "challan_id,vehicle_number,vehicle_type,state,violation_key,amount_paid,quantity,repeat\n"
        "CH-001,KA-01-AB-1234,Two-Wheeler (> 50cc),Karnataka,no_helmet,1000,,\n"
        "CH-002,MH-02-CD-5678,Light Motor Vehicle (Car),Maharashtra,no_seatbelt,1000,,\n"
        "CH-003,DL-01-EF-9012,Heavy Motor Vehicle,Delhi,overloading_goods,22000,1,\n"
        "CH-004,TN-09-GH-3456,Transport / Commercial,Tamil Nadu,no_dl,5000,,\n"
    )
    return {"filename": "sample_fleet_challans.csv", "csv_content": sample_csv}

@app.get(
    "/api/v1/rto/resolve/{reg_number}",
    response_model=VehicleRegistrationResolution,
    tags=["rto"],
    summary="Resolve Vehicle Registration and Jurisdiction (Standard & BH-Series)",
)
def resolve_vehicle_registration(reg_number: str) -> VehicleRegistrationResolution:
    """Parse vehicle registration number, resolve state/UT, RTO division, and detect BH-series."""
    res = app_core.parse_vehicle_registration(reg_number)
    return VehicleRegistrationResolution.model_validate(res)

@app.get(
    "/api/v1/compounding-relief-stats",
    response_model=list[StateCompoundingReliefStatModel],
    tags=["compounding"],
    summary="Comparative State Compounding Concession Statistics",
)
def get_compounding_relief_stats() -> list[StateCompoundingReliefStatModel]:
    """Compute average financial relief percentage across all Section 200 notified states."""
    stats = app_core.get_state_compounding_relief_stats()
    return [StateCompoundingReliefStatModel.model_validate(s) for s in stats]


@app.post(
    "/api/v1/fleet/analytics",
    response_model=FleetAuditAnalyticsResponse,
    tags=["fleet"],
    summary="Generate Executive Fleet Audit Visual Telematics & Analytics",
)
def generate_fleet_analytics(payload: BatchAuditRequest) -> FleetAuditAnalyticsResponse:
    """Audit batch and generate executive KPIs, breakdown by status, state, and violations."""
    try:
        records_payload = [rec.model_dump() for rec in payload.records]
        audit_res = app_core.audit_challan_batch(records_payload)
        analytics = app_core.get_fleet_audit_analytics(audit_res)
        return FleetAuditAnalyticsResponse.model_validate(analytics)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Fleet analytics error: {exc}") from exc

