"""Tests for National Vehicle Scrappage Policy & EV Green Plate Concession Matrix (MoRTH GSR 653(E) & SO 3064(E) — Fixes #70)."""

import pytest
from fastapi.testclient import TestClient

import app_core
from api import app

client = TestClient(app)


class TestScrappageEVDataStructures:
    def test_scrappage_rates_data(self):
        data = app_core.SCRAPPAGE_RATES
        assert isinstance(data, dict)
        assert "statutory_framework" in data
        assert "G.S.R. 653(E)" in data["statutory_framework"]["notification_id"]
        assert "scrappage_parameters" in data
        assert data["scrappage_parameters"]["scrap_value_rate_pct"] == 5.0
        assert data["scrappage_parameters"]["oem_discount_rate_pct"] == 5.0
        assert data["scrappage_parameters"]["road_tax_rebate_non_transport_pct"] == 25.0

    def test_ev_state_incentives_data(self):
        data = app_core.EV_STATE_INCENTIVES
        assert isinstance(data, dict)
        assert "statutory_framework" in data
        assert "S.O. 3064(E)" in data["statutory_framework"]["permit_exemption_notification"]
        assert "state_incentives" in data
        assert "Delhi" in data["state_incentives"]
        assert "Maharashtra" in data["state_incentives"]


class TestScrappageCalculationCore:
    def test_eligible_car_scrappage(self):
        # 16-year-old car, ₹10,00,000 ex-showroom in Delhi
        res = app_core.calculate_scrappage_incentives(
            vehicle_type="Light Motor Vehicle (Car)",
            new_vehicle_ex_showroom=1000000.0,
            state="Delhi",
            vehicle_age_years=16,
            is_transport=False,
        )
        assert res["is_eligible"] is True
        assert res["minimum_scrappage_age"] == 15
        assert res["scrap_value_estimate"] == 50000.0
        assert res["oem_discount_estimate"] == 50000.0
        # Delhi road tax: 10% of 10,00,000 = 1,00,000; 25% rebate = 25,000
        assert res["estimated_road_tax"] == 100000.0
        assert res["road_tax_rebate"] == 25000.0
        assert res["registration_fee_waiver"] == 1000.0
        assert res["total_financial_benefits"] == 126000.0
        assert "Certificate of Deposit" in res["statutory_advisory"]

    def test_ineligible_young_vehicle(self):
        res = app_core.calculate_scrappage_incentives(
            vehicle_type="Light Motor Vehicle (Car)",
            new_vehicle_ex_showroom=800000.0,
            state="Maharashtra",
            vehicle_age_years=6,
            is_transport=False,
        )
        assert res["is_eligible"] is False
        assert "does not meet the minimum statutory threshold" in res["statutory_advisory"]

    def test_transport_vehicle_10_year_threshold(self):
        res = app_core.calculate_scrappage_incentives(
            vehicle_type="Transport / Commercial",
            new_vehicle_ex_showroom=2000000.0,
            state="Karnataka",
            vehicle_age_years=11,
            is_transport=True,
        )
        assert res["is_eligible"] is True
        assert res["minimum_scrappage_age"] == 10
        assert res["road_tax_rebate_pct"] == 15.0

    def test_invalid_price_or_age_raises(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.calculate_scrappage_incentives(
                vehicle_type="Light Motor Vehicle (Car)",
                new_vehicle_ex_showroom=-500,
                state="Delhi",
                vehicle_age_years=16,
            )

        with pytest.raises(app_core.CalculatorInputError):
            app_core.calculate_scrappage_incentives(
                vehicle_type="Light Motor Vehicle (Car)",
                new_vehicle_ex_showroom=500000,
                state="Delhi",
                vehicle_age_years=-2,
            )


class TestEVPrivilegesCore:
    def test_delhi_ev_privileges(self):
        res = app_core.get_ev_privileges_and_concessions(state="Delhi", vehicle_category="Two-Wheeler")
        assert res["state"] == "Delhi"
        assert res["road_tax_concession_pct"] == 100.0
        assert res["registration_fee_concession_pct"] == 100.0
        assert res["permit_exemption_active"] is True
        assert "Rule 50" in res["green_plate_specification"]

    def test_kerala_ev_privileges(self):
        res = app_core.get_ev_privileges_and_concessions(state="Kerala")
        assert res["road_tax_concession_pct"] == 50.0

    def test_fallback_state_ev_privileges(self):
        res = app_core.get_ev_privileges_and_concessions(state="Nagaland")
        assert res["road_tax_concession_pct"] == 100.0
        assert res["permit_exemption_active"] is True


class TestScrappageEVAPIEndpoints:
    def test_api_scrappage_incentives(self):
        payload = {
            "vehicle_type": "Light Motor Vehicle (Car)",
            "new_vehicle_ex_showroom": 1200000.0,
            "state": "Maharashtra",
            "vehicle_age_years": 16,
            "is_transport": False,
        }
        res = client.post("/api/v1/green/scrappage-incentives", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["is_eligible"] is True
        assert data["total_financial_benefits"] > 100000.0
        assert "Certificate of Deposit" in data["statutory_authority"]["cod_tradability"]

    def test_api_ev_privileges(self):
        res = client.get("/api/v1/green/ev-privileges?state=Delhi&vehicle_category=Car")
        assert res.status_code == 200
        data = res.json()
        assert data["state"] == "Delhi"
        assert data["road_tax_concession_pct"] == 100.0
        assert data["permit_exemption_active"] is True

    def test_api_invalid_payload(self):
        res = client.post("/api/v1/green/scrappage-incentives", json={"vehicle_age_years": -5})
        assert res.status_code == 422
