"""Tests for Inter-State Vehicle Relocation & Road Tax Refund Calculator (Sec 47 & 48 MVA — Fixes #72)."""

import pytest
from fastapi.testclient import TestClient

import app_core
from api import app

client = TestClient(app)


class TestInterstateRelocationData:
    def test_rules_structure(self):
        data = app_core.INTERSTATE_RELOCATION_RULES
        assert isinstance(data, dict)
        assert "statutory_framework" in data
        assert "Section 47" in data["statutory_framework"]["section_47"]
        assert "Section 48" in data["statutory_framework"]["section_48"]
        assert "procedural_rules" in data
        assert data["procedural_rules"]["interstate_grace_period_months"] == 12
        assert len(data["procedural_rules"]["required_documents"]) >= 5


class TestAuditInterstateRelocationCore:
    def test_within_12_month_grace_period(self):
        res = app_core.audit_interstate_relocation_status(
            stay_duration_months=7,
            has_noc=False,
            origin_state="Maharashtra",
            destination_state="Karnataka",
        )
        assert res["status_code"] == "WITHIN_STATUTORY_GRACE_PERIOD"
        assert res["is_within_grace_period"] is True
        assert res["re_registration_required"] is False
        assert "Section 47 MVA 1988" in res["legal_advisory"]
        assert "FASTag logs" in res["legal_advisory"]

    def test_exceeding_12_month_limit_without_noc(self):
        res = app_core.audit_interstate_relocation_status(
            stay_duration_months=15,
            has_noc=False,
            origin_state="Delhi",
            destination_state="Tamil Nadu",
        )
        assert res["status_code"] == "RE_REGISTRATION_MANDATORY"
        assert res["is_within_grace_period"] is False
        assert res["re_registration_required"] is True
        assert "Section 48(3)" in res["noc_status_advisory"]
        assert "30 days" in res["noc_status_advisory"]

    def test_exceeding_12_month_with_noc(self):
        res = app_core.audit_interstate_relocation_status(
            stay_duration_months=18,
            has_noc=True,
            origin_state="Haryana",
            destination_state="Rajasthan",
        )
        assert res["status_code"] == "RE_REGISTRATION_MANDATORY"
        assert res["re_registration_required"] is True
        assert "Form 28 NOC is available" in res["noc_status_advisory"]

    def test_same_state_intra_state_operation(self):
        res = app_core.audit_interstate_relocation_status(
            stay_duration_months=24,
            has_noc=False,
            origin_state="Maharashtra",
            destination_state="Maharashtra",
        )
        assert res["status_code"] == "INTRA_STATE_OPERATION"
        assert res["re_registration_required"] is False

    def test_invalid_arguments_raise(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.audit_interstate_relocation_status(
                stay_duration_months=-5,
                has_noc=False,
                origin_state="Delhi",
                destination_state="Punjab",
            )


class TestCalculateRoadTaxRefundCore:
    def test_pro_rata_refund_calculation_3_year_old_vehicle(self):
        # 36 months used out of 180 months -> 144 months left (80%)
        res = app_core.calculate_road_tax_refund(
            original_road_tax_paid=100000.0,
            vehicle_age_months=36,
            origin_state="Maharashtra",
            destination_state="Karnataka",
        )
        assert res["unused_lifespan_months"] == 144
        assert res["refund_percentage"] == 80.0
        assert res["eligible_refund_amount"] == 80000.0
        assert "Form DT" in res["claim_procedure"]

    def test_vehicle_beyond_15_years_no_refund(self):
        res = app_core.calculate_road_tax_refund(
            original_road_tax_paid=80000.0,
            vehicle_age_months=190,
            origin_state="Delhi",
            destination_state="Uttar Pradesh",
        )
        assert res["eligible_refund_amount"] == 0.0
        assert res["unused_lifespan_months"] == 0
        assert "exceeded the 15-year statutory lifespan" in res["advisory"]

    def test_invalid_refund_inputs_raise(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.calculate_road_tax_refund(
                original_road_tax_paid=-1000,
                vehicle_age_months=24,
                origin_state="Delhi",
                destination_state="Goa",
            )


class TestInterstateRelocationAPIEndpoints:
    def test_api_audit_relocation(self):
        payload = {
            "origin_state": "Delhi",
            "destination_state": "Karnataka",
            "stay_duration_months": 8,
            "has_noc": False,
        }
        res = client.post("/api/v1/relocation/audit-stay", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status_code"] == "WITHIN_STATUTORY_GRACE_PERIOD"
        assert data["re_registration_required"] is False
        assert len(data["required_documents"]) >= 5

    def test_api_calculate_tax_refund(self):
        payload = {
            "original_road_tax_paid": 120000.0,
            "vehicle_age_months": 60,  # 5 years -> 10 years left (120/180 = 66.7%)
            "origin_state": "Tamil Nadu",
            "destination_state": "Maharashtra",
        }
        res = client.post("/api/v1/relocation/calculate-tax-refund", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["unused_lifespan_months"] == 120
        assert data["eligible_refund_amount"] == 80000.0

    def test_api_invalid_payload_error(self):
        res = client.post("/api/v1/relocation/audit-stay", json={"stay_duration_months": -10})
        assert res.status_code == 422
