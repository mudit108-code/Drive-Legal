"""Unit tests for Commercial Vehicle Axle-Weight Overloading & Excess Penalty Engine (Sec 113, 114, 194 MVA)."""
import pytest
from fastapi.testclient import TestClient

import app_core
from api import app

client = TestClient(app)


class TestAxleConfigurations:
    def test_configurations_loaded(self):
        configs = app_core.get_safe_axle_configurations()
        assert isinstance(configs, list)
        assert len(configs) >= 8
        codes = [c["code"] for c in configs]
        assert "2_axle_rigid" in codes
        assert "3_axle_rigid" in codes
        assert "tractor_trailer_6_axle" in codes

    def test_rigid_truck_statutory_limits(self):
        configs = {c["code"]: c for c in app_core.get_safe_axle_configurations()}
        assert configs["2_axle_rigid"]["max_permissible_gvw_tonnes"] == 18.5
        assert configs["3_axle_rigid"]["max_permissible_gvw_tonnes"] == 28.0
        assert configs["4_axle_rigid"]["max_permissible_gvw_tonnes"] == 35.0
        assert configs["5_axle_rigid"]["max_permissible_gvw_tonnes"] == 43.5

    def test_tractor_trailer_statutory_limits(self):
        configs = {c["code"]: c for c in app_core.get_safe_axle_configurations()}
        assert configs["tractor_trailer_3_axle"]["max_permissible_gvw_tonnes"] == 30.0
        assert configs["tractor_trailer_6_axle"]["max_permissible_gvw_tonnes"] == 55.0


class TestOverloadingCalculationLogic:
    def test_compliant_vehicle(self):
        res = app_core.calculate_overloading_penalty(
            registered_gvw_tonnes=18.5,
            actual_weight_tonnes=17.2,
            axle_configuration="2_axle_rigid",
        )
        assert res["is_overloaded"] is False
        assert res["excess_weight_tonnes"] == 0.0
        assert res["chargeable_excess_tonnes"] == 0
        assert res["total_penalty"] == 0
        assert res["offloading_mandated"] is False
        assert "COMPLIANT" in res["compliance_status"]

    def test_overloading_exact_one_tonne(self):
        # 1 tonne excess = 20,000 base + 2,000 excess = 22,000
        res = app_core.calculate_overloading_penalty(
            registered_gvw_tonnes=18.5,
            actual_weight_tonnes=19.5,
            axle_configuration="2_axle_rigid",
        )
        assert res["is_overloaded"] is True
        assert res["excess_weight_tonnes"] == 1.0
        assert res["chargeable_excess_tonnes"] == 1
        assert res["base_overloading_penalty"] == 20000
        assert res["excess_tonnage_penalty"] == 2000
        assert res["total_penalty"] == 22000
        assert res["offloading_mandated"] is True
        assert "OVERLOADED" in res["compliance_status"]

    def test_overloading_fractional_tonne_ceiling(self):
        # 1.2 tonnes excess rounds up to 2 chargeable tonnes under Sec 194(1)
        # 20,000 base + 2 * 2,000 = 24,000
        res = app_core.calculate_overloading_penalty(
            registered_gvw_tonnes=28.0,
            actual_weight_tonnes=29.2,
            axle_configuration="3_axle_rigid",
        )
        assert res["is_overloaded"] is True
        assert res["excess_weight_tonnes"] == 1.2
        assert res["chargeable_excess_tonnes"] == 2
        assert res["excess_tonnage_penalty"] == 4000
        assert res["total_penalty"] == 24000

    def test_refusal_to_weigh_penalty(self):
        # Sec 194(2) refusal penalty = 40,000
        res = app_core.calculate_overloading_penalty(
            registered_gvw_tonnes=18.5,
            actual_weight_tonnes=18.0,
            refused_weighment=True,
        )
        assert res["is_overloaded"] is False
        assert res["refused_weighment"] is True
        assert res["refusal_penalty"] == 40000
        assert res["total_penalty"] == 40000
        assert "REFUSAL TO WEIGH" in res["compliance_status"]

    def test_overloaded_and_refused_combined(self):
        # 2 tonnes excess (24k) + refusal (40k) = 64,000
        res = app_core.calculate_overloading_penalty(
            registered_gvw_tonnes=18.5,
            actual_weight_tonnes=20.5,
            refused_weighment=True,
        )
        assert res["is_overloaded"] is True
        assert res["base_overloading_penalty"] == 20000
        assert res["excess_tonnage_penalty"] == 4000
        assert res["refusal_penalty"] == 40000
        assert res["total_penalty"] == 64000

    def test_config_statutory_warning(self):
        # 2-axle rigid max statutory is 18.5T; if registered at 22T, should warn
        res = app_core.calculate_overloading_penalty(
            registered_gvw_tonnes=22.0,
            actual_weight_tonnes=22.0,
            axle_configuration="2_axle_rigid",
        )
        assert res["config_statutory_warning"] is not None
        assert "exceeds MoRTH S.O. 2822(E)" in res["config_statutory_warning"]

    def test_invalid_registered_gvw_raises(self):
        with pytest.raises(app_core.CalculatorInputError, match="must be positive"):
            app_core.calculate_overloading_penalty(
                registered_gvw_tonnes=0.0,
                actual_weight_tonnes=10.0,
            )

    def test_negative_actual_weight_raises(self):
        with pytest.raises(app_core.CalculatorInputError, match="cannot be negative"):
            app_core.calculate_overloading_penalty(
                registered_gvw_tonnes=18.5,
                actual_weight_tonnes=-2.0,
            )


class TestOverloadingAPIEndpoints:
    def test_get_axle_limits_api(self):
        response = client.get("/api/v1/commercial/axle-limits")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 8
        codes = [d["code"] for d in data]
        assert "2_axle_rigid" in codes

    def test_post_overloading_compliant_api(self):
        payload = {
            "registered_gvw_tonnes": 18.5,
            "actual_weight_tonnes": 17.5,
            "axle_configuration": "2_axle_rigid",
            "refused_weighment": False,
        }
        response = client.post("/api/v1/commercial/overloading-calculator", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["is_overloaded"] is False
        assert data["total_penalty"] == 0

    def test_post_overloading_excess_api(self):
        payload = {
            "registered_gvw_tonnes": 28.0,
            "actual_weight_tonnes": 31.0,
            "axle_configuration": "3_axle_rigid",
            "refused_weighment": False,
        }
        response = client.post("/api/v1/commercial/overloading-calculator", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["is_overloaded"] is True
        assert data["excess_weight_tonnes"] == 3.0
        assert data["total_penalty"] == 26000  # 20000 + 3*2000

    def test_post_overloading_invalid_payload(self):
        payload = {
            "registered_gvw_tonnes": -10.0,
            "actual_weight_tonnes": 15.0,
        }
        response = client.post("/api/v1/commercial/overloading-calculator", json=payload)
        assert response.status_code == 422
