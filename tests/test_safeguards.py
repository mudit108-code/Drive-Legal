"""Test suite for on-the-road police stop statutory safeguards and citizen rights."""

import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pytest
from fastapi.testclient import TestClient

import app_core
from api import app
from models import TrafficStopSafeguardModel

client = TestClient(app)


def test_traffic_stop_safeguards_loaded():
    """Verify safeguards dataset is loaded with 5 verified statutory rules."""
    safeguards = app_core.get_traffic_stop_safeguards()
    assert isinstance(safeguards, list)
    assert len(safeguards) == 5

    ids = {s["id"] for s in safeguards}
    assert "key_seizure_prohibition" in ids
    assert "officer_rank_requirement" in ids
    assert "digilocker_document_validity" in ids
    assert "towing_with_occupants_prohibition" in ids
    assert "recording_police_interaction" in ids


def test_safeguard_model_validation():
    """Ensure all safeguards strictly validate against TrafficStopSafeguardModel schema."""
    safeguards = app_core.get_traffic_stop_safeguards()
    for sg in safeguards:
        model = TrafficStopSafeguardModel.model_validate(sg)
        assert model.id
        assert model.title
        assert model.statutory_authority
        assert model.summary
        assert model.citizen_action
        assert len(model.legal_citations) >= 1


def test_key_confiscation_safeguard_content():
    """Verify statutory content of key snatching prohibition."""
    safeguards = app_core.get_traffic_stop_safeguards()
    key_sg = next(s for s in safeguards if s["id"] == "key_seizure_prohibition")
    assert "key" in key_sg["title"].lower()
    assert any("MVA" in c or "Section 130" in c or "Section 207" in c for c in key_sg["legal_citations"])


def test_video_recording_safeguard_content():
    """Verify citizen constitutional right to record police interactions in public."""
    safeguards = app_core.get_traffic_stop_safeguards()
    video_sg = next(s for s in safeguards if s["id"] == "recording_police_interaction")
    assert "record" in video_sg["title"].lower()
    assert "Article 19(1)(a)" in video_sg["statutory_authority"] or any("Article 19" in c for c in video_sg["legal_citations"])


def test_api_traffic_stop_safeguards_endpoint():
    """Verify GET /api/v1/traffic-stop-safeguards endpoint."""
    response = client.get("/api/v1/traffic-stop-safeguards")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 5
    assert all(TrafficStopSafeguardModel.model_validate(item) for item in data)
