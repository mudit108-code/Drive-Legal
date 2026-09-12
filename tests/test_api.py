"""Comprehensive test suite for the DriveLegal India FastAPI microservice."""

import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pytest
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


def test_api_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "2.0.0"
    assert data["metrics"]["national_violations"] == 19
    assert data["metrics"]["jurisdictions_covered"] == 36
    assert data["metrics"]["verified_compounding_states"] == 8

    v1_resp = client.get("/api/v1/health")
    assert v1_resp.status_code == 200
    assert v1_resp.json() == data


def test_api_get_violations():
    response = client.get("/api/v1/violations")
    assert response.status_code == 200
    violations = response.json()
    assert len(violations) == 19

    # Filter by vehicle
    bike_resp = client.get("/api/v1/violations", params={"vehicle_type": "Two-Wheeler (> 50cc)"})
    assert bike_resp.status_code == 200
    assert all("Two-Wheeler (> 50cc)" in v["allowed_vehicle_types"] for v in bike_resp.json())

    # Filter by search
    search_resp = client.get("/api/v1/violations", params={"search": "helmet"})
    assert search_resp.status_code == 200
    assert any("helmet" in v["description"].lower() for v in search_resp.json())


def test_api_get_states():
    response = client.get("/api/v1/states")
    assert response.status_code == 200
    states = response.json()
    assert len(states) == 36

    compounding_resp = client.get("/api/v1/states", params={"compounding_only": True})
    assert compounding_resp.status_code == 200
    compounding_states = compounding_resp.json()
    assert len(compounding_states) == 8
    assert all(s["has_compounding_schedule"] for s in compounding_states)


def test_api_calculate_single_fine():
    payload = {
        "violation_key": "no_helmet",
        "vehicle_type": "Two-Wheeler (> 50cc)",
        "state": "Karnataka",
        "quantity": None,
        "is_repeat": False
    }
    response = client.post("/api/v1/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["violation_key"] == "no_helmet"
    assert data["base_fine"] == 1000.0
    assert data["calculated_fine"] == 1000.0
    assert data["state_compounding_applied"] is True
    assert data["compounded_fine"] == 500
    assert data["effective_fine"] == 500.0
    assert data["savings_from_compounding"] == 500.0
    assert data["notification_id"] == "TD 132 TMR 2019"


def test_api_calculate_single_fine_invalid_vehicle():
    payload = {
        "violation_key": "no_helmet",
        "vehicle_type": "Light Motor Vehicle (Car)",
        "state": "Delhi"
    }
    response = client.post("/api/v1/calculate", json=payload)
    assert response.status_code == 400
    assert "not applicable to" in response.json()["detail"]


def test_api_calculate_multi_fine():
    payload = {
        "state": "Maharashtra",
        "items": [
            {
                "violation_key": "no_helmet",
                "vehicle_type": "Two-Wheeler (> 50cc)",
                "quantity": None,
                "is_repeat": False
            },
            {
                "violation_key": "no_seatbelt",
                "vehicle_type": "Light Motor Vehicle (Car)",
                "quantity": None,
                "is_repeat": False
            }
        ]
    }
    response = client.post("/api/v1/calculate-multi", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "Maharashtra"
    assert data["item_count"] == 2
    assert data["grand_total"] == 2000.0
    assert data["total_compounding_fee"] == 700.0  # 500 helmet + 200 seatbelt
    assert data["has_compounding_items"] is True


def test_api_compounding_matrix():
    response = client.get("/api/v1/compounding-matrix")
    assert response.status_code == 200
    data = response.json()
    assert len(data["states"]) == 8
    assert len(data["rows"]) > 0

    # Filter matrix
    filtered = client.get("/api/v1/compounding-matrix", params={"violations": ["no_helmet", "signal_jump"]})
    assert filtered.status_code == 200
    assert len(filtered.json()["rows"]) == 2


def test_api_laws_catalogue():
    response = client.get("/api/v1/laws")
    assert response.status_code == 200
    assert len(response.json()) == 18

    search_resp = client.get("/api/v1/laws", params={"q": "185"})
    assert search_resp.status_code == 200
    laws = search_resp.json()
    assert len(laws) >= 1
    assert any("185" in l["section"] for l in laws)


def test_api_citizen_rights():
    response = client.get("/api/v1/citizen-rights")
    assert response.status_code == 200
    assert len(response.json()) == 5

    single_resp = client.get("/api/v1/citizen-rights", params={"id": "digilocker_validity"})
    assert single_resp.status_code == 200
    assert single_resp.json()[0]["id"] == "digilocker_validity"

    not_found = client.get("/api/v1/citizen-rights", params={"id": "non_existent"})
    assert not_found.status_code == 404


def test_api_dispute_types():
    response = client.get("/api/v1/dispute-types")
    assert response.status_code == 200
    types = response.json()
    assert "digilocker_rejection" in types
    assert "unapplied_compounding" in types
    assert "grace_period_demand" in types
    assert "wrong_vehicle_or_cloned_plate" in types


def test_api_create_dispute_representation():
    payload = {
        "citizen_name": "Rohan Verma",
        "vehicle_number": "MH-02-CD-5678",
        "challan_number": "MH56781234",
        "challan_date": "2026-09-03",
        "state": "Maharashtra",
        "issuing_authority": "Mumbai Traffic Police",
        "dispute_type": "unapplied_compounding",
        "violation_key": "no_helmet"
    }
    response = client.post("/api/v1/dispute-representation", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["challan_number"] == "MH56781234"
    assert data["vehicle_number"] == "MH-02-CD-5678"
    assert "Section 200" in data["letter_text"]
    assert "MVR 0919/C.R. 152/TRA-2" in data["letter_text"]
    assert data["html_content"] is not None
    assert "<!DOCTYPE html>" in data["html_content"]
    assert "MH56781234" in data["html_content"]
    assert "Rohan Verma" in data["html_content"]

def test_api_observability_headers():
    """Verify X-Request-ID and X-Process-Time-Ms middleware headers on all responses."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) > 0
    assert "x-process-time-ms" in resp.headers
    process_ms = float(resp.headers["x-process-time-ms"])
    assert process_ms >= 0.0

    custom_id = "test-custom-trace-uuid-1234"
    resp_custom = client.get("/health", headers={"x-request-id": custom_id})
    assert resp_custom.status_code == 200
    assert resp_custom.headers["x-request-id"] == custom_id

