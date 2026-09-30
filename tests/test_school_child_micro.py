"""Tests for School Bus Safety, Child Restraints (Sec 194B(2)), and Micromobility Exemption (CMVR 2(u)) (Fixes #76)."""

import pytest
from fastapi.testclient import TestClient

import app_core
from api import app

client = TestClient(app)


class TestSafetyDataStructures:
    def test_school_bus_data(self):
        data = app_core.SCHOOL_BUS_STANDARDS
        assert "AIS-063" in data["statutory_framework"]["standard_code"]
        assert len(data["checklist_items"]) == 10
        assert sum(i["weight"] for i in data["checklist_items"]) == 100

    def test_child_restraint_data(self):
        data = app_core.CHILD_RESTRAINT_RULES
        assert "Section 194B(2)" in data["statutory_framework"]["mva_section"]
        assert data["statutory_framework"]["penalty_amount"] == 1000
        assert "two_wheeler_pillion_child" in data

    def test_micromobility_data(self):
        data = app_core.MICROMOBILITY_RULES
        assert "Rule 2(u)" in data["statutory_framework"]["cmvr_rule"]
        assert data["statutory_ceilings"]["max_continuous_rated_power_watts"] == 250.0
        assert data["statutory_ceilings"]["max_cut_off_speed_kmh"] == 25.0


class TestSchoolBusSafetyCore:
    def test_fully_compliant_bus(self):
        all_true = {item["id"]: True for item in app_core.SCHOOL_BUS_STANDARDS["checklist_items"]}
        res = app_core.audit_school_bus_safety("DL-1PB-4567", all_true)
        assert res["compliance_score"] == 100
        assert res["compliance_status"] == "FULLY_COMPLIANT"
        assert res["passed_items_count"] == 10
        assert res["failed_items_count"] == 0

    def test_defective_bus(self):
        checklist = {
            "golden_yellow_livery": True,
            "speed_governor_40kmh": True,
            "horizontal_window_grills": True,
            "fire_extinguisher_isi": True,
            "first_aid_box": True,
            "emergency_exit_door": True,
            "gps_and_cctv": True,
            "reliable_door_locks": False,
            "qualified_conductor_attendant": False,
            "driver_experience_5yr": False,
        }
        res = app_core.audit_school_bus_safety("MH-04-SB-1111", checklist)
        assert res["compliance_score"] == 70
        assert res["compliance_status"] == "DEFECTIVE_NEEDS_RECTIFICATION"
        assert res["failed_items_count"] == 3

    def test_fatal_hazard_bus(self):
        res = app_core.audit_school_bus_safety("UP-16-SB-9999", {"golden_yellow_livery": True})
        assert res["compliance_score"] == 10
        assert res["compliance_status"] == "FATAL_SAFETY_HAZARD"

    def test_blank_registration_raises(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.audit_school_bus_safety("", {})


class TestChildRestraintCore:
    def test_infant_car_restraint(self):
        res = app_core.get_child_restraint_safety_advice(child_age_years=1.5, vehicle_category="Car")
        assert "Rear-Facing" in res["recommended_system"]
        assert "194B(2)" in res["statutory_mandate"]
        assert "1000" in res["statutory_penalty"]
        assert res["is_two_wheeler"] is False

    def test_two_wheeler_child_safety(self):
        res = app_core.get_child_restraint_safety_advice(child_age_years=3.0, vehicle_category="Two-Wheeler")
        assert res["is_two_wheeler"] is True
        assert "Safety Harness" in res["recommended_system"]
        assert res["speed_limit_cap_kmh"] == 40
        assert "Rule 138(7)" in res["statutory_mandate"]

    def test_invalid_negative_age_raises(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.get_child_restraint_safety_advice(child_age_years=-1.0)


class TestMicromobilityCore:
    def test_compliant_e_bike_exemption(self):
        res = app_core.evaluate_micromobility_exemption(motor_power_watts=240.0, max_speed_kmh=24.0)
        assert res["is_exempt_from_mva"] is True
        assert res["legal_status"] == "EXEMPT_FROM_MVA"
        assert res["statutory_exemptions"]["driving_licence_required"] is False
        assert res["statutory_exemptions"]["registration_number_plate_required"] is False

    def test_excess_power_requires_mva(self):
        res = app_core.evaluate_micromobility_exemption(motor_power_watts=450.0, max_speed_kmh=24.0)
        assert res["is_exempt_from_mva"] is False
        assert res["legal_status"] == "FULL_MVA_REGULATION_APPLIES"
        assert res["statutory_exemptions"]["driving_licence_required"] is True

    def test_excess_speed_requires_mva(self):
        res = app_core.evaluate_micromobility_exemption(motor_power_watts=250.0, max_speed_kmh=35.0)
        assert res["is_exempt_from_mva"] is False
        assert res["is_speed_compliant"] is False

    def test_invalid_negative_power_raises(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.evaluate_micromobility_exemption(motor_power_watts=-50, max_speed_kmh=20)


class TestSafetyAPIEndpoints:
    def test_api_school_bus_audit(self):
        payload = {
            "bus_registration_no": "DL-1V-8888",
            "checklist": {"golden_yellow_livery": True, "speed_governor_40kmh": True},
        }
        res = client.post("/api/v1/safety/school-bus-audit", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["bus_registration_no"] == "DL-1V-8888"
        assert data["compliance_score"] == 20

    def test_api_child_restraint_advisory(self):
        payload = {"child_age_years": 3.5, "vehicle_category": "Car"}
        res = client.post("/api/v1/safety/child-restraint-advisory", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "Forward-Facing" in data["recommended_system"]

    def test_api_micromobility_exemption(self):
        payload = {"motor_power_watts": 250.0, "max_speed_kmh": 25.0}
        res = client.post("/api/v1/safety/micromobility-exemption", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["is_exempt_from_mva"] is True
        assert data["legal_status"] == "EXEMPT_FROM_MVA"

    def test_api_invalid_payload_error(self):
        res = client.post("/api/v1/safety/child-restraint-advisory", json={"child_age_years": -5})
        assert res.status_code == 422
