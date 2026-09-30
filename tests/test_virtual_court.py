"""Unit tests for Virtual Courts (vcourts.gov.in) Advisory Engine (Sec 208 MVA)."""
import pytest
from fastapi.testclient import TestClient

import app_core
from api import app

client = TestClient(app)


class TestVirtualCourtData:
    def test_rules_data_structure(self):
        rules = app_core.VIRTUAL_COURT_RULES
        assert "jurisdictions" in rules
        assert "grounds_to_contest" in rules
        assert "portal_url" in rules
        assert rules["portal_url"] == "https://vcourts.gov.in"
        assert "Section 208 MVA" in rules["statutory_basis"]

    def test_key_states_present(self):
        jurisdictions = app_core.VIRTUAL_COURT_RULES["jurisdictions"]
        expected_states = [
            "Delhi", "Maharashtra", "Uttar Pradesh", "Karnataka",
            "Tamil Nadu", "Kerala", "Gujarat", "Haryana", "West Bengal",
            "Odisha", "Punjab", "Andhra Pradesh"
        ]
        for state in expected_states:
            assert state in jurisdictions, f"Expected {state} in Virtual Court jurisdictions"
            info = jurisdictions[state]
            assert info["is_active"] is True
            assert info["summons_window_days"] in (60, 90)
            assert "vcourts.gov.in" in info["portal_domain"]

    def test_grounds_to_contest_entries(self):
        grounds = app_core.VIRTUAL_COURT_RULES["grounds_to_contest"]
        assert len(grounds) >= 5
        codes = [g["code"] for g in grounds]
        assert "missing_or_blurred_plate" in codes
        assert "camera_calibration_expired" in codes
        assert "emergency_passage_given" in codes


class TestVirtualCourtCoreLogic:
    def test_get_virtual_court_jurisdictions(self):
        jurisdictions = app_core.get_virtual_court_jurisdictions()
        assert isinstance(jurisdictions, list)
        assert len(jurisdictions) >= 12
        for j in jurisdictions:
            assert "state" in j
            assert "virtual_court_name" in j
            assert "summons_window_days" in j

    def test_advisory_plead_guilty_standard(self):
        adv = app_core.get_virtual_court_advisory(
            state="Delhi",
            violation_key="no_helmet",
            days_since_notice=10,
            has_photo_evidence=True,
        )
        assert adv["virtual_court_available"] is True
        assert adv["is_window_active"] is True
        assert adv["contest_advisable"] is False
        assert "Plead Guilty" in adv["recommended_action"]
        assert "vcourts.gov.in" in adv["portal_url"]

    def test_advisory_defective_evidence_contests(self):
        adv = app_core.get_virtual_court_advisory(
            state="Maharashtra",
            violation_key="signal_jump",
            days_since_notice=15,
            has_photo_evidence=False,
        )
        assert adv["contest_advisable"] is True
        assert "Contest" in adv["recommended_action"]
        assert "CMVR Rule 167A" in adv["detailed_recommendation"]

    def test_advisory_specific_contest_ground(self):
        adv = app_core.get_virtual_court_advisory(
            state="Karnataka",
            violation_key="overspeeding_lmv",
            days_since_notice=20,
            has_photo_evidence=True,
            contest_ground="camera_calibration_expired",
        )
        assert adv["contest_advisable"] is True
        assert "Expired Radar" in adv["recommended_action"]
        assert "Legal Metrology" in adv["detailed_recommendation"]

    def test_advisory_automatic_dl_risk_mandates_physical_court(self):
        adv = app_core.get_virtual_court_advisory(
            state="Delhi",
            violation_key="drunk_driving",
            days_since_notice=5,
            has_photo_evidence=True,
        )
        assert adv["contest_advisable"] is True
        assert "Mandatory Physical Court Appearance" in adv["recommended_action"]
        assert "DL disqualification" in adv["detailed_recommendation"]

    def test_advisory_exceeded_summons_window(self):
        # UP has 60 day window
        adv = app_core.get_virtual_court_advisory(
            state="Uttar Pradesh",
            violation_key="no_seatbelt",
            days_since_notice=75,
            has_photo_evidence=True,
        )
        assert adv["is_window_active"] is False
        assert "Physical Summons Escalation" in adv["recommended_action"]
        assert "75 days ago" in adv["detailed_recommendation"]

    def test_advisory_state_without_virtual_court(self):
        adv = app_core.get_virtual_court_advisory(
            state="Goa",
            violation_key="no_helmet",
            days_since_notice=10,
        )
        assert adv["virtual_court_available"] is False
        assert "No Virtual Court" in adv["virtual_court_name"]

    def test_invalid_violation_key_raises(self):
        with pytest.raises(app_core.CalculatorInputError, match="Unknown violation key"):
            app_core.get_virtual_court_advisory(
                state="Delhi",
                violation_key="imaginary_offence",
                days_since_notice=10,
            )

    def test_negative_days_raises(self):
        with pytest.raises(app_core.CalculatorInputError, match="cannot be negative"):
            app_core.get_virtual_court_advisory(
                state="Delhi",
                violation_key="no_helmet",
                days_since_notice=-5,
            )


class TestVirtualCourtAPIEndpoints:
    def test_get_jurisdictions_api(self):
        response = client.get("/api/v1/virtual-court/jurisdictions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 12
        states = [d["state"] for d in data]
        assert "Delhi" in states
        assert "Maharashtra" in states

    def test_post_advisory_api_plead_guilty(self):
        payload = {
            "state": "Delhi",
            "violation_key": "no_helmet",
            "days_since_notice": 14,
            "has_photo_evidence": True,
        }
        response = client.post("/api/v1/virtual-court/advisory", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["virtual_court_available"] is True
        assert data["contest_advisable"] is False
        assert "Plead Guilty" in data["recommended_action"]

    def test_post_advisory_api_contest_defective_evidence(self):
        payload = {
            "state": "Maharashtra",
            "violation_key": "signal_jump",
            "days_since_notice": 10,
            "has_photo_evidence": False,
        }
        response = client.post("/api/v1/virtual-court/advisory", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["contest_advisable"] is True
        assert "Contest" in data["recommended_action"]

    def test_post_advisory_api_invalid_violation(self):
        payload = {
            "state": "Delhi",
            "violation_key": "nonexistent_violation",
            "days_since_notice": 10,
        }
        response = client.post("/api/v1/virtual-court/advisory", json=payload)
        assert response.status_code == 400
        assert "Unknown violation key" in response.json()["detail"]

    def test_post_advisory_api_negative_days_fails_validation(self):
        payload = {
            "state": "Delhi",
            "violation_key": "no_helmet",
            "days_since_notice": -10,
        }
        response = client.post("/api/v1/virtual-court/advisory", json=payload)
        assert response.status_code == 422
