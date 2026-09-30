"""Unit tests for National Lok Adalat Challan Settlement & Concession Engine."""
import pytest
from fastapi.testclient import TestClient

import app_core
from api import app

client = TestClient(app)


class TestLokAdalatSchedules:
    def test_schedules_loaded(self):
        data = app_core.get_lok_adalat_schedules()
        assert "quarterly_calendar" in data
        assert len(data["quarterly_calendar"]) == 4
        assert "state_policies" in data
        assert "Legal Services Authorities Act" in data["statutory_basis"]
        assert "award_finality" in data

    def test_state_policies_coverage(self):
        policies = app_core.LOK_ADALAT_RULES["state_concession_policies"]
        assert "Karnataka" in policies
        assert policies["Karnataka"]["average_concession_pct"] == 50.0
        assert "Delhi" in policies
        assert policies["Delhi"]["average_concession_pct"] == 65.0
        assert "Maharashtra" in policies
        assert policies["Maharashtra"]["average_concession_pct"] == 60.0

    def test_non_compoundable_list(self):
        non_comp = app_core.LOK_ADALAT_RULES["non_compoundable_offences"]
        assert "drunk_driving" in non_comp
        assert "minor_driving" in non_comp


class TestLokAdalatCalculationLogic:
    def test_all_compoundable_in_delhi(self):
        # no_helmet (1000) + no_seatbelt (1000) = 2000 nominal
        # Delhi concession is 65% -> payable is 35% of 2000 = 700, savings = 1300
        res = app_core.calculate_lok_adalat_concession(
            violation_keys=["no_helmet", "no_seatbelt"],
            state="Delhi",
        )
        assert res["total_nominal_fine"] == 2000.0
        assert res["compoundable_fine_sum"] == 2000.0
        assert res["non_compoundable_fine_sum"] == 0.0
        assert res["estimated_lok_adalat_payable"] == 700.0
        assert res["estimated_savings"] == 1300.0
        assert res["effective_concession_pct"] == 65.0
        assert len(res["compoundable_items"]) == 2
        assert len(res["non_compoundable_items"]) == 0

    def test_karnataka_flat_50_pct(self):
        # no_helmet (1000) in Karnataka -> 50% concession = 500
        res = app_core.calculate_lok_adalat_concession(
            violation_keys=["no_helmet"],
            state="Karnataka",
        )
        assert res["total_nominal_fine"] == 1000.0
        assert res["estimated_lok_adalat_payable"] == 500.0
        assert res["estimated_savings"] == 500.0
        assert res["effective_concession_pct"] == 50.0

    def test_mixed_compoundable_and_non_compoundable(self):
        # no_helmet (1000, compoundable) + drunk_driving (10000, non-compoundable)
        # Delhi concession 65% on helmet = 350 payable
        # Drunk driving = 10000 payable (no discount)
        # Total payable = 10350, savings = 650
        res = app_core.calculate_lok_adalat_concession(
            violation_keys=["no_helmet", "drunk_driving"],
            state="Delhi",
        )
        assert res["total_nominal_fine"] == 11000.0
        assert res["compoundable_fine_sum"] == 1000.0
        assert res["non_compoundable_fine_sum"] == 10000.0
        assert res["estimated_lok_adalat_payable"] == 10350.0
        assert res["estimated_savings"] == 650.0
        assert len(res["non_compoundable_items"]) == 1
        assert res["non_compoundable_items"][0]["violation_key"] == "drunk_driving"

    def test_procedural_steps_present(self):
        res = app_core.calculate_lok_adalat_concession(
            violation_keys=["no_parking"],
            state="Maharashtra",
        )
        assert len(res["procedural_steps"]) == 4
        assert any("Token" in s for s in res["procedural_steps"])
        assert any("Section 21" in s for s in res["procedural_steps"])

    def test_empty_violation_keys_raises(self):
        with pytest.raises(app_core.CalculatorInputError, match="must be a non-empty list"):
            app_core.calculate_lok_adalat_concession(violation_keys=[])

    def test_unknown_violation_key_raises(self):
        with pytest.raises(app_core.CalculatorInputError, match="Unknown violation keys"):
            app_core.calculate_lok_adalat_concession(violation_keys=["fake_violation"])


class TestLokAdalatAPIEndpoints:
    def test_get_schedules_api(self):
        response = client.get("/api/v1/lok-adalat/schedules")
        assert response.status_code == 200
        data = response.json()
        assert "quarterly_calendar" in data
        assert len(data["quarterly_calendar"]) == 4
        assert "state_policies" in data

    def test_post_concession_estimate_api(self):
        payload = {
            "violation_keys": ["no_helmet", "no_seatbelt"],
            "state": "Delhi",
        }
        response = client.post("/api/v1/lok-adalat/concession-estimate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["total_nominal_fine"] == 2000.0
        assert data["estimated_lok_adalat_payable"] == 700.0
        assert data["estimated_savings"] == 1300.0

    def test_post_concession_estimate_invalid_violation(self):
        payload = {
            "violation_keys": ["invalid_key"],
            "state": "Karnataka",
        }
        response = client.post("/api/v1/lok-adalat/concession-estimate", json=payload)
        assert response.status_code == 400
        assert "Unknown violation keys" in response.json()["detail"]

    def test_post_concession_estimate_empty_list_fails_validation(self):
        payload = {
            "violation_keys": [],
            "state": "Delhi",
        }
        response = client.post("/api/v1/lok-adalat/concession-estimate", json=payload)
        assert response.status_code == 422
