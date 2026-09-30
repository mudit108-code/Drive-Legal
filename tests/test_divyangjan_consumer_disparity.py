"""Unit and integration tests for Divyangjan adapted vehicle rights, Lemon Law defect notice generator, and state compounding leniency index (PR 8 - Fixes #78)."""

import pytest
from fastapi.testclient import TestClient

import app_core
from api import app


@pytest.fixture
def client():
    return TestClient(app)


class TestDivyangjanRightsEngine:
    """Test Divyangjan adapted vehicle benefits, GST concessions, and toll waivers."""

    def test_eligible_petrol_hatchback(self):
        res = app_core.calculate_divyangjan_concessions(
            vehicle_ex_showroom=800000.0,
            engine_cc=1197,
            fuel_type="petrol",
            length_mm=3995,
            state="Delhi",
            disability_pct=50.0,
        )
        assert res["benchmark_disability_satisfied"] is True
        assert res["gst_concession_eligible"] is True
        assert res["estimated_gst_savings"] > 0
        assert res["road_tax_exemption_pct"] == 100.0
        assert res["estimated_road_tax_savings"] == 80000.0
        assert res["total_estimated_concession"] > 100000.0
        assert res["toll_exemption_eligible"] is True
        assert "52(1)" in res["alteration_immunity_statute"]
        assert len(res["disqualification_reasons"]) == 0
        assert len(res["required_checklist"]) > 0

    def test_eligible_diesel_compact_suv(self):
        res = app_core.calculate_divyangjan_concessions(
            vehicle_ex_showroom=1100000.0,
            engine_cc=1498,
            fuel_type="diesel",
            length_mm=3990,
            state="Maharashtra",
            disability_pct=60.0,
        )
        assert res["benchmark_disability_satisfied"] is True
        assert res["gst_concession_eligible"] is True
        assert res["road_tax_exemption_pct"] == 100.0
        assert res["toll_exemption_eligible"] is True

    def test_eligible_electric_vehicle(self):
        res = app_core.calculate_divyangjan_concessions(
            vehicle_ex_showroom=950000.0,
            engine_cc=0,
            fuel_type="electric",
            length_mm=3800,
            state="Karnataka",
            disability_pct=40.0,
        )
        assert res["benchmark_disability_satisfied"] is True
        assert res["gst_concession_eligible"] is True
        assert res["estimated_gst_savings"] > 0

    def test_ineligible_due_to_low_disability_percentage(self):
        res = app_core.calculate_divyangjan_concessions(
            vehicle_ex_showroom=700000.0,
            engine_cc=1000,
            fuel_type="petrol",
            length_mm=3700,
            state="Delhi",
            disability_pct=35.0,  # Below 40% benchmark
        )
        assert res["benchmark_disability_satisfied"] is False
        assert res["gst_concession_eligible"] is False
        assert res["estimated_gst_savings"] == 0.0
        assert res["road_tax_exemption_pct"] == 0.0
        assert res["toll_exemption_eligible"] is False
        assert any("below the statutory benchmark" in r for r in res["disqualification_reasons"])

    def test_ineligible_due_to_vehicle_length_exceeded(self):
        res = app_core.calculate_divyangjan_concessions(
            vehicle_ex_showroom=1500000.0,
            engine_cc=1198,
            fuel_type="petrol",
            length_mm=4350,  # Exceeds 4000 mm ceiling
            state="Gujarat",
            disability_pct=50.0,
        )
        assert res["benchmark_disability_satisfied"] is True
        assert res["gst_concession_eligible"] is False
        assert any("exceeds the maximum ceiling" in r for r in res["disqualification_reasons"])

    def test_ineligible_due_to_engine_displacement_petrol(self):
        res = app_core.calculate_divyangjan_concessions(
            vehicle_ex_showroom=1200000.0,
            engine_cc=1498,  # > 1200cc for petrol
            fuel_type="petrol",
            length_mm=3990,
            state="Tamil Nadu",
            disability_pct=50.0,
        )
        assert res["gst_concession_eligible"] is False
        assert any("exceeds the 1200 cc limit" in r for r in res["disqualification_reasons"])

    def test_invalid_fuel_type_raises(self):
        with pytest.raises(app_core.CalculatorInputError, match="Invalid fuel_type"):
            app_core.calculate_divyangjan_concessions(
                vehicle_ex_showroom=500000.0,
                engine_cc=1000,
                fuel_type="hydrogen",
                length_mm=3800,
                state="Delhi",
                disability_pct=50.0,
            )

    def test_invalid_state_raises(self):
        with pytest.raises(app_core.CalculatorInputError, match="Unknown state"):
            app_core.calculate_divyangjan_concessions(
                vehicle_ex_showroom=500000.0,
                engine_cc=1000,
                fuel_type="petrol",
                length_mm=3800,
                state="Atlantis",
                disability_pct=50.0,
            )


class TestLemonLawNoticeGenerator:
    """Test automotive Lemon Law notice generator and CPA 2019 jurisdiction."""

    def test_generate_notice_district_commission(self):
        res = app_core.generate_lemon_law_notice(
            owner_name="Manoj Sharma",
            owner_address="B-42, Vasant Kunj, New Delhi 110070",
            manufacturer_name="Apex Motors India Pvt Ltd",
            dealer_name="Prime Star Dealership",
            dealer_address="Plot 14, Mathura Road, Faridabad, Haryana",
            vehicle_make_model="Apex Horizon EV",
            vin_or_chassis="MA3EWD110K123456",
            purchase_date="2025-11-15",
            purchase_price=1450000.0,
            defect_category="electrical_fire_hazard",
            repair_attempts_count=4,
            days_out_of_service=42,
            defect_description="Thermal battery warning and loss of power steering at highway speeds.",
            remedy_sought="Full refund of purchase amount Rs. 14,50,000/- with statutory interest.",
        )
        assert "LEGAL NOTICE" in res["notice_text"]
        assert "Manoj Sharma" in res["notice_text"]
        assert "Apex Motors India Pvt Ltd" in res["notice_text"]
        assert "MA3EWD110K123456" in res["notice_text"]
        assert "District Consumer Disputes Redressal Commission" in res["pecuniary_forum"]
        assert res["claim_amount"] == 1450000.0
        assert res["is_lemon_threshold_met"] is True
        assert res["cure_period_days"] == 15
        assert len(res["statutory_citations"]) >= 4

    def test_generate_notice_state_commission(self):
        res = app_core.generate_lemon_law_notice(
            owner_name="Sunita Agarwal",
            owner_address="12, Race Course Road, Bengaluru, Karnataka",
            manufacturer_name="LuxAuto India Ltd",
            dealer_name="Elite Wheels Bengaluru",
            dealer_address="Hosur Main Road, Bengaluru",
            vehicle_make_model="LuxAuto Velar 300",
            vin_or_chassis="LUX1234567890ABCD",
            purchase_date="2025-06-10",
            purchase_price=8500000.0,  # 85 Lakhs -> State Commission
            defect_category="transmission_failure",
            repair_attempts_count=3,
            days_out_of_service=35,
            defect_description="Complete transmission slippage and gear lock while in motion.",
            remedy_sought="Replacement with defect-free brand-new vehicle.",
        )
        assert "State Consumer Disputes Redressal Commission" in res["pecuniary_forum"]
        assert res["is_lemon_threshold_met"] is True

    def test_generate_notice_national_commission(self):
        res = app_core.generate_lemon_law_notice(
            owner_name="Vikramaditya Oberoi",
            owner_address="Worli Sea Face, Mumbai 400018",
            manufacturer_name="Exotic Supercars AG",
            dealer_name="Imperial Motors South Mumbai",
            dealer_address="Worli, Mumbai",
            vehicle_make_model="Exotic Stallion V12",
            vin_or_chassis="EXO999888777666",
            purchase_date="2025-01-20",
            purchase_price=25000000.0,  # 2.5 Crores -> National Commission
            defect_category="structural_chassis_defect",
            repair_attempts_count=2,
            days_out_of_service=45,
            defect_description="Subframe cracking and airbag sensor failure.",
            remedy_sought="Full refund of invoice price with 18% p.a. interest.",
        )
        assert "National Consumer Disputes Redressal Commission" in res["pecuniary_forum"]

    def test_invalid_defect_category_raises(self):
        with pytest.raises(app_core.CalculatorInputError, match="Invalid defect_category"):
            app_core.generate_lemon_law_notice(
                owner_name="Test Owner",
                owner_address="Test Address",
                manufacturer_name="Test OEM",
                dealer_name="Test Dealer",
                dealer_address="Test Dealer Addr",
                vehicle_make_model="Test Car",
                vin_or_chassis="VIN123",
                purchase_date="2025-01-01",
                purchase_price=500000.0,
                defect_category="dirty_floor_mats",
                repair_attempts_count=1,
                days_out_of_service=1,
                defect_description="Mats are dirty",
                remedy_sought="New mats",
            )


class TestStateCompoundingLeniencyIndex:
    """Test Pan-India State Compounding Leniency Index and Ranking."""

    def test_leniency_index_structure_and_ranking(self):
        index_res = app_core.get_state_compounding_leniency_index()
        assert index_res["total_notified_states"] > 0
        assert index_res["average_leniency_score"] >= 0.0
        assert isinstance(index_res["most_lenient_state"], str)
        assert isinstance(index_res["strictest_state"], str)
        
        rankings = index_res["rankings"]
        assert len(rankings) == index_res["total_notified_states"]
        
        # Verify descending order of leniency score
        for i in range(len(rankings) - 1):
            assert rankings[i]["leniency_score"] >= rankings[i + 1]["leniency_score"]
            assert rankings[i]["rank"] == i + 1

        # Check required fields in ranking item
        for item in rankings:
            assert "state" in item
            assert "compoundable_violations_count" in item
            assert "central_total" in item
            assert "state_compounded_total" in item
            assert "relief_pct" in item
            assert "leniency_score" in item
            assert item["compoundable_violations_count"] > 0


class TestConsumerProtectionEndpoints:
    """Integration test suite for FastAPI consumer endpoints."""

    def test_divyangjan_benefits_api_success(self, client):
        payload = {
            "vehicle_ex_showroom": 850000.0,
            "engine_cc": 1198,
            "fuel_type": "petrol",
            "length_mm": 3995,
            "state": "Maharashtra",
            "disability_pct": 50.0,
        }
        resp = client.post("/api/v1/consumer/divyangjan-benefits", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["benchmark_disability_satisfied"] is True
        assert data["gst_concession_eligible"] is True
        assert data["estimated_gst_savings"] > 0

    def test_divyangjan_benefits_api_invalid_input(self, client):
        payload = {
            "vehicle_ex_showroom": -100.0,
            "engine_cc": 1198,
            "fuel_type": "petrol",
            "length_mm": 3995,
            "state": "Maharashtra",
            "disability_pct": 50.0,
        }
        resp = client.post("/api/v1/consumer/divyangjan-benefits", json=payload)
        assert resp.status_code == 422  # Pydantic validation failure

    def test_generate_lemon_notice_api_success(self, client):
        payload = {
            "owner_name": "Rohan Verma",
            "owner_address": "Flat 302, Palm Heights, Gurugram, Haryana",
            "manufacturer_name": "Zenith Auto India",
            "dealer_name": "Grand Zenith Motors",
            "dealer_address": "Sohna Road, Gurugram",
            "vehicle_make_model": "Zenith Cruiser Turbo",
            "vin_or_chassis": "ZEN98765432100",
            "purchase_date": "2025-08-12",
            "purchase_price": 1850000.0,
            "defect_category": "transmission_failure",
            "repair_attempts_count": 3,
            "days_out_of_service": 31,
            "defect_description": "Automatic dual-clutch transmission overheating and dropping into neutral.",
            "remedy_sought": "Full vehicle replacement or refund.",
        }
        resp = client.post("/api/v1/consumer/generate-lemon-notice", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "LEGAL NOTICE" in data["notice_text"]
        assert data["cure_period_days"] == 15
        assert data["is_lemon_threshold_met"] is True

    def test_state_leniency_index_api_success(self, client):
        resp = client.get("/api/v1/consumer/state-leniency-index")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_notified_states"] > 0
        assert len(data["rankings"]) > 0
