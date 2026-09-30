"""Tests for Commercial Driver Rest Hours & HAZCHEM Transport Safety Diagnostic (MTWA 1961 & CMVR 129-137 — Fixes #74)."""

import pytest
from fastapi.testclient import TestClient

import app_core
from api import app

client = TestClient(app)


class TestCommercialRegulationsData:
    def test_transport_worker_regulations_data(self):
        data = app_core.TRANSPORT_WORKER_REGULATIONS
        assert isinstance(data, dict)
        assert "statutory_framework" in data
        assert "Motor Transport Workers Act" in data["statutory_framework"]["act_name"]
        assert "statutory_limits" in data
        assert data["statutory_limits"]["max_continuous_driving_hours"] == 5.0
        assert data["statutory_limits"]["min_rest_interval_minutes"] == 30

    def test_hazchem_safety_rules_data(self):
        data = app_core.HAZCHEM_SAFETY_RULES
        assert isinstance(data, dict)
        assert "un_hazard_classes" in data
        assert len(data["un_hazard_classes"]) == 9
        assert "3" in data["un_hazard_classes"]
        assert data["un_hazard_classes"]["3"]["name"] == "Flammable Liquids"


class TestDriverFatigueAuditCore:
    def test_fully_compliant_driver_hours(self):
        res = app_core.audit_driver_fatigue_hours(
            continuous_driving_hours=4.0,
            daily_working_hours=7.5,
            weekly_working_hours=42.0,
            rest_interval_minutes=45,
            is_long_distance=False,
        )
        assert res["compliance_status"] == "COMPLIANT"
        assert res["violations_count"] == 0
        assert "satisfy statutory limits" in res["safety_advisory"]

    def test_continuous_driving_violation(self):
        res = app_core.audit_driver_fatigue_hours(
            continuous_driving_hours=6.5,
            daily_working_hours=7.0,
            weekly_working_hours=40.0,
            rest_interval_minutes=15,  # Less than 30m
            is_long_distance=False,
        )
        assert res["violations_count"] == 1
        assert res["violations"][0]["severity"] == "CRITICAL"
        assert "Section 15" in res["violations"][0]["section"]

    def test_multiple_violations_unlawful(self):
        res = app_core.audit_driver_fatigue_hours(
            continuous_driving_hours=7.0,
            daily_working_hours=12.0,
            weekly_working_hours=55.0,
            rest_interval_minutes=10,
            is_long_distance=False,
        )
        assert res["compliance_status"] == "UNLAWFUL_EXCESSIVE_HOURS"
        assert res["violations_count"] == 3

    def test_long_distance_10_hour_allowance(self):
        # 9.5 hours is compliant for long distance, but violation for standard (8h)
        res_ld = app_core.audit_driver_fatigue_hours(
            continuous_driving_hours=4.0,
            daily_working_hours=9.5,
            weekly_working_hours=45.0,
            rest_interval_minutes=45,
            is_long_distance=True,
        )
        assert res_ld["compliance_status"] == "COMPLIANT"

        res_std = app_core.audit_driver_fatigue_hours(
            continuous_driving_hours=4.0,
            daily_working_hours=9.5,
            weekly_working_hours=45.0,
            rest_interval_minutes=45,
            is_long_distance=False,
        )
        assert res_std["compliance_status"] == "MODERATE_FATIGUE_RISK"
        assert res_std["violations_count"] == 1

    def test_invalid_negative_hours_raise(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.audit_driver_fatigue_hours(
                continuous_driving_hours=-2.0,
                daily_working_hours=8.0,
                weekly_working_hours=40.0,
                rest_interval_minutes=30,
            )


class TestHazchemComplianceCore:
    def test_full_hazchem_compliance_class_3(self):
        res = app_core.audit_hazchem_carriage_compliance(
            un_class_id=3,
            has_eip_display=True,
            has_tremcard=True,
            has_hazardous_dl_endorsement=True,
            has_spark_arrester=True,
            has_fire_extinguisher=True,
        )
        assert res["un_class_id"] == 3
        assert res["hazard_class_name"] == "Flammable Liquids"
        assert res["compliance_score"] == 100
        assert res["compliance_status"] == "FULLY_COMPLIANT"
        assert len(res["missing_items"]) == 0

    def test_deficient_hazchem_compliance(self):
        res = app_core.audit_hazchem_carriage_compliance(
            un_class_id=2,  # Gases
            has_eip_display=False,
            has_tremcard=False,
            has_hazardous_dl_endorsement=False,
            has_spark_arrester=True,
            has_fire_extinguisher=True,
        )
        assert res["compliance_score"] == 30
        assert res["compliance_status"] == "CRITICAL_PROSECUTION_RISK"
        assert "Section 190(3)" in res["penalty_risk"]
        assert len(res["missing_items"]) == 3

    def test_invalid_un_class_raises(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.audit_hazchem_carriage_compliance(
                un_class_id=12,  # Invalid
                has_eip_display=True,
                has_tremcard=True,
                has_hazardous_dl_endorsement=True,
                has_spark_arrester=True,
                has_fire_extinguisher=True,
            )


class TestCommercialAPIEndpoints:
    def test_api_audit_driver_hours(self):
        payload = {
            "continuous_driving_hours": 6.0,
            "daily_working_hours": 9.0,
            "weekly_working_hours": 44.0,
            "rest_interval_minutes": 15,
            "is_long_distance": False,
        }
        res = client.post("/api/v1/commercial/audit-driver-hours", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["compliance_status"] == "UNLAWFUL_EXCESSIVE_HOURS"
        assert data["violations_count"] == 2

    def test_api_audit_hazchem(self):
        payload = {
            "un_class_id": 3,
            "has_eip_display": True,
            "has_tremcard": True,
            "has_hazardous_dl_endorsement": True,
            "has_spark_arrester": True,
            "has_fire_extinguisher": True,
        }
        res = client.post("/api/v1/commercial/audit-hazchem-carriage", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["compliance_score"] == 100
        assert data["compliance_status"] == "FULLY_COMPLIANT"

    def test_api_invalid_payload_error(self):
        res = client.post("/api/v1/commercial/audit-hazchem-carriage", json={"un_class_id": 99})
        assert res.status_code == 422
