"""Tests for Offline Anti-Phishing & Fake Challan SMS/URL Scanner (Sec 66D IT Act — Fixes #64)."""

import pytest
from fastapi.testclient import TestClient

import app_core
from api import app

client = TestClient(app)


class TestCyberThreatRulesData:
    def test_rules_loaded(self):
        rules = app_core.CYBER_THREAT_RULES
        assert isinstance(rules, dict)
        assert "trusted_domains" in rules
        assert "echallan.parivahan.gov.in" in rules["trusted_domains"]
        assert "suspicious_tlds" in rules
        assert ".xyz" in rules["suspicious_tlds"]
        assert "suspicious_domain_patterns" in rules
        assert "echallan-" in rules["suspicious_domain_patterns"]
        assert "statutory_provisions" in rules
        assert rules["statutory_provisions"]["helpline_number"] == "1930"


class TestScanChallanMessageCore:
    def test_official_parivahan_link_is_safe(self):
        msg = "Dear Citizen, Challan DL12345 has been issued for your vehicle. Pay online at https://echallan.parivahan.gov.in/."
        result = app_core.scan_challan_message(msg)
        assert result["risk_level"] == "SAFE"
        assert result["threat_score"] == 0
        assert result["is_official_domain"] is True
        assert "echallan.parivahan.gov.in" in result["extracted_domains"]

    def test_official_vcourts_link_is_safe(self):
        msg = "Your traffic challan has been referred to Virtual Court. Settle online at https://vcourts.gov.in"
        result = app_core.scan_challan_message(msg)
        assert result["risk_level"] == "SAFE"
        assert result["threat_score"] == 0
        assert result["is_official_domain"] is True

    def test_phishing_typosquatting_domain(self):
        msg = "URGENT: Challan pending of Rs 1000. Pay now at http://echallan-parivahan-gov.xyz before arrest."
        result = app_core.scan_challan_message(msg)
        assert result["risk_level"] == "HIGH_RISK_FRAUD"
        assert result["threat_score"] >= 60
        assert result["is_official_domain"] is False
        indicators = [f["indicator"] for f in result["detected_flags"]]
        assert any("Typosquatting" in ind for ind in indicators)
        assert any("Suspicious TLD" in ind for ind in indicators)

    def test_apk_download_malicious_lure(self):
        msg = "Traffic police notification: Download APK to check camera violation photo: http://rto-service.net/challan.apk"
        result = app_core.scan_challan_message(msg)
        assert result["risk_level"] == "HIGH_RISK_FRAUD"
        assert any("Malicious App / APK" in f["indicator"] for f in result["detected_flags"])

    def test_coercive_urgency_without_links(self):
        msg = "Notice: Pay pending traffic fine within 24 hours or court warrant and FIR registered."
        result = app_core.scan_challan_message(msg)
        assert result["risk_level"] in ("SUSPICIOUS", "HIGH_RISK_FRAUD")
        assert any("Urgency" in f["indicator"] for f in result["detected_flags"])

    def test_raw_ip_address_host(self):
        msg = "Challan notice: Pay fine at http://192.168.1.50/pay-fine"
        result = app_core.scan_challan_message(msg)
        assert result["risk_level"] == "HIGH_RISK_FRAUD"
        assert any("IP Address" in f["indicator"] for f in result["detected_flags"])

    def test_empty_input_raises_error(self):
        with pytest.raises(app_core.CalculatorInputError):
            app_core.scan_challan_message("")

        with pytest.raises(app_core.CalculatorInputError):
            app_core.scan_challan_message("   ")

    def test_statutory_recourse_details(self):
        msg = "Pay fine: http://echallan-fake.top"
        result = app_core.scan_challan_message(msg)
        recourse = result["statutory_recourse"]
        assert "Section 66D" in recourse["it_act"]
        assert recourse["helpline"] == "1930"
        assert "cybercrime.gov.in" in recourse["portal"]

    def test_get_trusted_challan_portals(self):
        portals = app_core.get_trusted_challan_portals()
        assert isinstance(portals, list)
        assert len(portals) >= 5
        assert "echallan.parivahan.gov.in" in portals
        assert "vcourts.gov.in" in portals


class TestCyberDefenseAPIEndpoints:
    def test_api_scan_phishing_message(self):
        payload = {
            "message_text": "Challan pending. Pay within 24h at http://echallan-parivahan-pay.xyz to avoid warrant."
        }
        res = client.post("/api/v1/cyber/scan-challan-message", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["threat_score"] >= 60
        assert data["risk_level"] == "HIGH_RISK_FRAUD"
        assert data["is_official_domain"] is False
        assert len(data["detected_flags"]) >= 2
        assert data["statutory_recourse"]["helpline"] == "1930"

    def test_api_scan_official_message(self):
        payload = {
            "message_text": "Notice: Pending challan recorded. Settle via https://echallan.parivahan.gov.in/"
        }
        res = client.post("/api/v1/cyber/scan-challan-message", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["threat_score"] == 0
        assert data["risk_level"] == "SAFE"
        assert data["is_official_domain"] is True

    def test_api_scan_empty_message_validation_error(self):
        payload = {"message_text": "a"}  # Less than min_length=3
        res = client.post("/api/v1/cyber/scan-challan-message", json=payload)
        assert res.status_code == 422

    def test_api_get_trusted_domains(self):
        res = client.get("/api/v1/cyber/trusted-domains")
        assert res.status_code == 200
        data = res.json()
        assert "trusted_domains" in data
        assert data["total_count"] == len(data["trusted_domains"])
        assert "echallan.parivahan.gov.in" in data["trusted_domains"]
