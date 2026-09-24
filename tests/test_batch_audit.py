"""Comprehensive test suite for commercial fleet batch challan auditing."""

import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pytest
from fastapi.testclient import TestClient

import app_core
from api import app

client = TestClient(app)


def test_audit_challan_batch_valid_overcharge_and_compliance():
    batch = [
        {
            "challan_id": "CH-001",
            "vehicle_number": "KA-01-AB-1234",
            "vehicle_type": "Two-Wheeler (> 50cc)",
            "state": "Karnataka",
            "violation_key": "no_helmet",
            "amount_paid": 1000.0,  # Central statutory ceiling charged; state rate is 500
        },
        {
            "challan_id": "CH-002",
            "vehicle_number": "DL-01-CD-5678",
            "vehicle_type": "Two-Wheeler (> 50cc)",
            "state": "Delhi",
            "violation_key": "no_helmet",
            "amount_paid": 1000.0,  # Delhi compounding is 1000 -> Compliant
        },
        {
            "challan_id": "CH-003",
            "vehicle_number": "MH-02-EF-9012",
            "vehicle_type": "Light Motor Vehicle (Car)",
            "state": "Maharashtra",
            "violation_key": "no_seatbelt",
            "amount_paid": 1000.0,  # Central ceiling charged; Maharashtra rate is 200
        },
        {
            "challan_id": "CH-004",
            "vehicle_number": "DL-03-GH-3456",
            "vehicle_type": "Light Motor Vehicle (Car)",
            "state": "Delhi",
            "violation_key": "drunk_driving",
            "amount_paid": 10000.0,  # Court mandatory
        },
    ]

    res = app_core.audit_challan_batch(batch)
    assert res["total_challans_audited"] == 4
    assert res["total_amount_paid"] == 13000.0
    assert res["total_legally_due"] == 11700.0  # 500 + 1000 + 200 + 10000
    assert res["total_potential_overcharges"] == 1300.0  # (1000-500) + (1000-200) = 1300
    assert res["overcharged_count"] == 2
    assert res["compliant_count"] == 1
    assert res["court_only_count"] == 1

    records = res["records"]
    assert records[0]["audit_status"] == "OVERCHARGED"
    assert records[0]["overcharge_amount"] == 500.0
    assert records[0]["notification_id"] == "TD 132 TMR 2019"

    assert records[1]["audit_status"] == "COMPLIANT"
    assert records[1]["overcharge_amount"] == 0.0

    assert records[2]["audit_status"] == "OVERCHARGED"
    assert records[2]["overcharge_amount"] == 800.0
    assert records[2]["notification_id"] == "MVR 0919/C.R. 152/TRA-2"

    assert records[3]["audit_status"] == "COURT_ONLY"


def test_audit_challan_batch_invalid_inputs():
    with pytest.raises(app_core.CalculatorInputError, match="At least one challan record is required"):
        app_core.audit_challan_batch([])

    with pytest.raises(app_core.CalculatorInputError, match="must be a dictionary"):
        app_core.audit_challan_batch(["not_a_dict"])

    with pytest.raises(app_core.CalculatorInputError, match="must be a finite non-negative number"):
        app_core.audit_challan_batch([{
            "challan_id": "CH-1",
            "vehicle_type": "Light Motor Vehicle (Car)",
            "state": "Delhi",
            "violation_key": "no_seatbelt",
            "amount_paid": -100.0,
        }])


def test_api_fleet_batch_audit_endpoint():
    payload = {
        "records": [
            {
                "challan_id": "FL-101",
                "vehicle_number": "KA-05-JK-1111",
                "vehicle_type": "Two-Wheeler (> 50cc)",
                "state": "Karnataka",
                "violation_key": "no_helmet",
                "amount_paid": 1000.0,
            }
        ]
    }
    response = client.post("/api/v1/fleet/audit-batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_challans_audited"] == 1
    assert data["total_potential_overcharges"] == 500.0
    assert data["overcharged_count"] == 1
    assert data["records"][0]["audit_status"] == "OVERCHARGED"


def test_api_fleet_sample_csv_endpoint():
    response = client.get("/api/v1/fleet/sample-csv")
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "sample_fleet_challans.csv"
    assert "challan_id,vehicle_number,vehicle_type" in data["csv_content"]

def test_fleet_audit_analytics_computation():
    """Verify computation of executive KPIs and categorical breakdowns in fleet analytics."""
    empty_analytics = app_core.get_fleet_audit_analytics({})
    assert empty_analytics["compliance_rate_pct"] == 100.0
    assert empty_analytics["overcharge_rate_pct"] == 0.0

    batch = [
        {
            "challan_id": "CH-1",
            "vehicle_type": "Two-Wheeler (> 50cc)",
            "state": "Karnataka",
            "violation_key": "no_helmet",
            "amount_paid": 1000.0,
        },
        {
            "challan_id": "CH-2",
            "vehicle_type": "Two-Wheeler (> 50cc)",
            "state": "Delhi",
            "violation_key": "no_helmet",
            "amount_paid": 1000.0,
        },
    ]
    audit_res = app_core.audit_challan_batch(batch)
    analytics = app_core.get_fleet_audit_analytics(audit_res)

    assert analytics["compliance_rate_pct"] == 50.0
    assert analytics["overcharge_rate_pct"] == 50.0
    assert analytics["court_mandatory_rate_pct"] == 0.0
    assert analytics["by_status"]["Compliant"] == 1
    assert analytics["by_status"]["Overcharged"] == 1
    assert "Karnataka" in analytics["by_state"]
    assert analytics["by_state"]["Karnataka"]["overcharges"] == 500.0


def test_state_compounding_relief_stats():
    """Verify extraction and percentage calculation of Section 200 state relief rates."""
    stats = app_core.get_state_compounding_relief_stats()
    assert isinstance(stats, list)
    assert len(stats) == 8

    states = {s["state"] for s in stats}
    assert "Gujarat" in states
    assert "Karnataka" in states
    assert "Maharashtra" in states

    for s in stats:
        assert s["compoundable_offences"] > 0
        assert s["central_sum"] > 0.0
        assert s["state_compounded_sum"] > 0.0
        assert 0.0 <= s["average_relief_pct"] <= 100.0

