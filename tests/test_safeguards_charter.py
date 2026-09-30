"""Tests for Women Motorist Safeguards & Good Samaritan Immunity Charter (Sec 46(4) CrPC & Sec 134A MVA — Fixes #68)."""

import pytest
from fastapi.testclient import TestClient

import app_core
from api import app

client = TestClient(app)


class TestSafeguardsDataStructures:
    def test_women_driver_protections_data(self):
        data = app_core.WOMEN_DRIVER_PROTECTIONS
        assert isinstance(data, dict)
        assert "statutory_references" in data
        assert "night_arrest_ban" in data["statutory_references"]
        assert "Section 46(4)" in data["statutory_references"]["night_arrest_ban"]
        assert "protective_rules" in data
        assert len(data["protective_rules"]) >= 4

    def test_good_samaritan_charter_data(self):
        data = app_core.GOOD_SAMARITAN_CHARTER
        assert isinstance(data, dict)
        assert "statutory_framework" in data
        assert "Section 134A" in data["statutory_framework"]["mva_section"]
        assert "SaveLIFE Foundation" in data["statutory_framework"]["supreme_court_judgment"]
        assert "charter_guarantees" in data
        assert len(data["charter_guarantees"]) >= 4


class TestWomenMotoristSafeguardsCore:
    def test_night_time_no_female_officer_critical_alert(self):
        res = app_core.get_women_motorist_safeguards(
            is_night_time=True,
            female_officer_present=False,
            alone_in_vehicle=True,
        )
        assert res["advisory_level"] == "CRITICAL_SAFEGUARD_ALERT"
        assert "Section 46(4)" in res["action_summary"]
        assert any("112" in act for act in res["immediate_actions"])
        assert any("Lock all vehicle doors" in act for act in res["immediate_actions"])
        assert len(res["applicable_safeguards"]) >= 4

    def test_daytime_no_female_officer_elevated_caution(self):
        res = app_core.get_women_motorist_safeguards(
            is_night_time=False,
            female_officer_present=False,
            alone_in_vehicle=False,
        )
        assert res["advisory_level"] == "ELEVATED_CAUTION"
        assert "Sec 51(2)" in res["action_summary"]

    def test_female_officer_present_standard(self):
        res = app_core.get_women_motorist_safeguards(
            is_night_time=False,
            female_officer_present=True,
            alone_in_vehicle=False,
        )
        assert res["advisory_level"] == "STANDARD_PROCEDURE"
        assert "Comply with lawful document inspection" in res["action_summary"]

    def test_invalid_input_types_raise(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.get_women_motorist_safeguards(
                is_night_time="true",  # type: ignore
                female_officer_present=False,
            )


class TestGoodSamaritanCertificateCore:
    def test_generate_certificate_success(self):
        res = app_core.generate_good_samaritan_certificate(
            rescuer_name="Ananya Verma",
            accident_location="Ring Road near AIIMS, New Delhi",
            incident_date="2026-05-12",
            hospital_name="Safdarjung Hospital Emergency",
        )
        assert res["rescuer_name"] == "Ananya Verma"
        assert res["accident_location"] == "Ring Road near AIIMS, New Delhi"
        assert "Section 134A" in res["notice_text"]
        assert "SaveLIFE Foundation" in res["notice_text"]
        assert "Safdarjung Hospital Emergency" in res["notice_text"]
        assert len(res["statutory_clauses"]) >= 4

    def test_missing_fields_raise(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.generate_good_samaritan_certificate(
                rescuer_name="",
                accident_location="Location",
                incident_date="2026-05-12",
                hospital_name="Hospital",
            )


class TestSafeguardsAPIEndpoints:
    def test_api_women_safeguards_night(self):
        payload = {
            "is_night_time": True,
            "female_officer_present": False,
            "alone_in_vehicle": True,
        }
        res = client.post("/api/v1/safeguards/women-driver", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["advisory_level"] == "CRITICAL_SAFEGUARD_ALERT"
        assert len(data["immediate_actions"]) >= 3
        assert "1091" in data["statutory_references"]["emergency_helpline"]

    def test_api_good_samaritan_certificate(self):
        payload = {
            "rescuer_name": "Karthik Raja",
            "accident_location": "GST Road, Chennai",
            "incident_date": "2026-06-20",
            "hospital_name": "Government Royapettah Hospital",
            "victim_transported": True,
        }
        res = client.post("/api/v1/safeguards/good-samaritan-charter", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["rescuer_name"] == "Karthik Raja"
        assert "SaveLIFE Foundation" in data["supreme_court_citation"]
        assert "Section 134A" in data["statutory_basis"]
        assert len(data["notice_text"]) > 100

    def test_api_invalid_payload_handling(self):
        res = client.post("/api/v1/safeguards/good-samaritan-charter", json={})
        assert res.status_code == 422
