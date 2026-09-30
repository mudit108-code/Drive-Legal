"""Tests for Speed Camera Evidence Auditor & Calibration RTI Generator (CMVR 167A & Sec 136A MVA — Fixes #66)."""

import pytest
from fastapi.testclient import TestClient

import app_core
from api import app

client = TestClient(app)


class TestCameraEvidenceRulesData:
    def test_rules_structure_and_criteria(self):
        rules = app_core.CAMERA_EVIDENCE_RULES
        assert isinstance(rules, dict)
        assert "statutory_framework" in rules
        assert "Rule 167A" in rules["statutory_framework"]["cmvr_rule"]
        assert "Section 136A" in rules["statutory_framework"]["mva_section"]

        criteria = rules.get("mandatory_evidentiary_criteria", [])
        assert len(criteria) == 6
        weights_sum = sum(c["weight"] for c in criteria)
        assert weights_sum == 100

    def test_rti_template_present(self):
        tpl = app_core.CAMERA_EVIDENCE_RULES.get("rti_application_template", {})
        assert "questions" in tpl
        assert len(tpl["questions"]) >= 3
        assert "Section 6(1)" in tpl["subject"]


class TestAuditCameraEvidenceCore:
    def test_full_evidentiary_compliance(self):
        res = app_core.audit_camera_evidence_compliance(
            challan_no="DL-2026-CH-9988",
            has_clear_plate_photo=True,
            has_speed_measurement_proof=True,
            has_timestamp_and_gps=True,
            has_statutory_citation=True,
            has_evidence_act_compliance=True,
            has_annual_calibration_status=True,
        )
        assert res["compliance_score"] == 100
        assert res["compliance_status"] == "FULLY_COMPLIANT"
        assert res["challenge_recommended"] is False
        assert res["passed_criteria_count"] == 6
        assert res["failed_criteria_count"] == 0

    def test_substantially_defective_compliance(self):
        # Clear photo (25) + speed proof (20) + timestamp (15) = 60
        res = app_core.audit_camera_evidence_compliance(
            challan_no="MH-2026-CH-1234",
            has_clear_plate_photo=True,
            has_speed_measurement_proof=True,
            has_timestamp_and_gps=True,
            has_statutory_citation=False,
            has_evidence_act_compliance=False,
            has_annual_calibration_status=False,
        )
        assert res["compliance_score"] == 60
        assert res["compliance_status"] == "SUBSTANTIALLY_DEFECTIVE"
        assert res["challenge_recommended"] is True
        assert res["passed_criteria_count"] == 3
        assert res["failed_criteria_count"] == 3

    def test_fatally_defective_compliance(self):
        # Only timestamp (15)
        res = app_core.audit_camera_evidence_compliance(
            challan_no="KA-2026-CH-5555",
            has_clear_plate_photo=False,
            has_speed_measurement_proof=False,
            has_timestamp_and_gps=True,
            has_statutory_citation=False,
            has_evidence_act_compliance=False,
            has_annual_calibration_status=False,
        )
        assert res["compliance_score"] == 15
        assert res["compliance_status"] == "FATALLY_DEFECTIVE"
        assert res["challenge_recommended"] is True

    def test_blank_challan_no_raises(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.audit_camera_evidence_compliance(
                challan_no="   ",
                has_clear_plate_photo=True,
                has_speed_measurement_proof=True,
                has_timestamp_and_gps=True,
                has_statutory_citation=True,
                has_evidence_act_compliance=True,
                has_annual_calibration_status=True,
            )


class TestGenerateCalibrationRTICore:
    def test_rti_generation_success(self):
        res = app_core.generate_camera_calibration_rti(
            applicant_name="Rohit Sharma",
            applicant_address="B-402, Sea Green Apts, Mumbai",
            challan_no="MH-01-2026-7890",
            violation_date="2026-03-15",
            camera_location="Western Express Highway, Bandra Flyover",
        )
        assert res["applicant_name"] == "Rohit Sharma"
        assert res["challan_no"] == "MH-01-2026-7890"
        assert "Section 6(1)" in res["application_text"]
        assert "Western Express Highway, Bandra Flyover" in res["application_text"]
        assert "MH-01-2026-7890" in res["application_text"]
        assert len(res["questions_included"]) >= 3

    def test_empty_applicant_raises(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.generate_camera_calibration_rti(
                applicant_name="",
                applicant_address="Address",
                challan_no="123",
                violation_date="2026-01-01",
                camera_location="Delhi",
            )


class TestCameraEvidenceAPIEndpoints:
    def test_api_audit_evidence(self):
        payload = {
            "challan_no": "DL-1C-9999",
            "has_clear_plate_photo": True,
            "has_speed_measurement_proof": True,
            "has_timestamp_and_gps": False,
            "has_statutory_citation": True,
            "has_evidence_act_compliance": False,
            "has_annual_calibration_status": False,
        }
        res = client.post("/api/v1/evidence/audit-camera-challan", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["challan_no"] == "DL-1C-9999"
        assert data["compliance_score"] == 60
        assert data["compliance_status"] == "SUBSTANTIALLY_DEFECTIVE"
        assert data["challenge_recommended"] is True

    def test_api_generate_calibration_rti(self):
        payload = {
            "applicant_name": "Priya Nair",
            "applicant_address": "12, Indiranagar, Bengaluru, Karnataka",
            "challan_no": "KA-03-2026-1122",
            "violation_date": "2026-04-10",
            "camera_location": "Airport Elevated Expressway KM 14",
        }
        res = client.post("/api/v1/evidence/generate-calibration-rti", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["applicant_name"] == "Priya Nair"
        assert "Airport Elevated Expressway" in data["application_text"]
        assert "Rs 10/-" in data["statutory_fee"]

    def test_api_invalid_payload_validation(self):
        res = client.post("/api/v1/evidence/audit-camera-challan", json={})
        assert res.status_code == 422
