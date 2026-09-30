"""Offline heuristic anti-phishing and fake challan SMS/URL scanner (Sec 66D IT Act).

Self-contained feature module: models, data loading, logic and API router live
here so this feature never edits app_core.py, api.py or models.py.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

import app_core
from app_core import CalculatorInputError, _read_json, _require


class ChallanThreatFlag(BaseModel):
    """Specific threat indicator flag detected by the cyber scanner."""
    model_config = ConfigDict(frozen=True)

    indicator: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    detail: str


class StatutoryCyberRecourse(BaseModel):
    """Statutory remedies and reporting authorities under IT Act."""
    model_config = ConfigDict(frozen=True)

    it_act: str
    helpline: str
    portal: str
    action: str


class ChallanThreatScanRequest(BaseModel):
    """Input payload for scanning an SMS, notification, or URL."""
    model_config = ConfigDict(extra="forbid")

    message_text: str = Field(..., min_length=3, max_length=2000, description="Raw text of the SMS, alert, or link received")


class ChallanThreatScanResponse(BaseModel):
    """Response payload detailing threat analysis and scam risk."""
    model_config = ConfigDict(frozen=True)

    text_sample: str
    threat_score: int = Field(..., ge=0, le=100)
    risk_level: Literal["SAFE", "SUSPICIOUS", "HIGH_RISK_FRAUD"]
    extracted_domains: list[str]
    is_official_domain: bool
    detected_flags: list[ChallanThreatFlag]
    recommendation: str
    statutory_recourse: StatutoryCyberRecourse


class TrustedPortalsResponse(BaseModel):
    """List of verified official state and central traffic challan portals."""
    model_config = ConfigDict(frozen=True)

    trusted_domains: list[str]
    total_count: int


def _validate_cyber_threat_rules(rules: Any) -> None:
    _require(isinstance(rules, dict), "cyber_threat_rules must be an object")
    for key in ("trusted_domains", "suspicious_tlds", "suspicious_domain_patterns", "urgency_keywords", "statutory_provisions"):
        _require(key in rules and isinstance(rules[key], (list, dict)), f"missing {key} in cyber_threat_rules")


CYBER_THREAT_RULES = _read_json("cyber_threat_rules.json")
_validate_cyber_threat_rules(CYBER_THREAT_RULES)


def scan_challan_message(text: str) -> dict[str, Any]:
    """Scan raw SMS or URL text for fraudulent e-challan smishing indicators.

    Returns threat score (0-100), risk level (SAFE, SUSPICIOUS, HIGH_RISK_FRAUD),
    detected flags, extracted domains, and statutory cyber-crime reporting advice.
    """
    if not isinstance(text, str) or not text.strip():
        raise CalculatorInputError("Input text must be a non-empty string.")

    cleaned_text = text.strip()
    lowered = cleaned_text.lower()

    rules = CYBER_THREAT_RULES
    trusted_domains = [d.lower() for d in rules.get("trusted_domains", [])]
    suspicious_tlds = [t.lower() for t in rules.get("suspicious_tlds", [])]
    suspicious_patterns = [p.lower() for p in rules.get("suspicious_domain_patterns", [])]
    urgency_keywords = [u.lower() for u in rules.get("urgency_keywords", [])]

    url_pattern = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s<>"]*)?')
    found_urls = url_pattern.findall(cleaned_text)

    detected_flags: list[dict[str, str]] = []
    threat_score = 0
    extracted_domains: list[str] = []
    is_whitelisted = False

    for raw_url in found_urls:
        parsed_url = raw_url if raw_url.startswith(("http://", "https://")) else "http://" + raw_url
        try:
            parsed = urlparse(parsed_url)
            netloc = parsed.netloc.lower() or parsed.path.split('/')[0].lower()
            netloc = netloc.split(':')[0]
            if netloc and netloc not in extracted_domains:
                extracted_domains.append(netloc)
        except Exception:
            continue

    for domain in extracted_domains:
        if any(domain == td or domain.endswith("." + td) for td in trusted_domains):
            is_whitelisted = True
            continue

        for tld in suspicious_tlds:
            if domain.endswith(tld):
                threat_score += 35
                detected_flags.append({
                    "indicator": f"Suspicious TLD ({tld})",
                    "severity": "HIGH",
                    "detail": f"Domain '{domain}' uses generic/unregulated TLD '{tld}' instead of official government domains (.gov.in / .nic.in).",
                })
                break

        for pattern in suspicious_patterns:
            if pattern in domain:
                threat_score += 40
                detected_flags.append({
                    "indicator": f"Typosquatting / Deceptive Domain Pattern ('{pattern}')",
                    "severity": "CRITICAL",
                    "detail": f"Domain '{domain}' mimics official Parivahan/Challan portals using pattern '{pattern}'.",
                })
                break

        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', domain):
            threat_score += 65
            detected_flags.append({
                "indicator": "Raw IP Address Host",
                "severity": "CRITICAL",
                "detail": f"Direct IP address '{domain}' used instead of verified official .gov.in domain.",
            })

    matched_urgencies = [kw for kw in urgency_keywords if kw in lowered]
    if matched_urgencies:
        threat_score += min(len(matched_urgencies) * 20, 40)
        detected_flags.append({
            "indicator": "Coercive / Smishing Urgency Language",
            "severity": "HIGH" if len(matched_urgencies) > 1 else "MEDIUM",
            "detail": f"Message contains high-pressure coercive phrases: {', '.join(repr(k) for k in matched_urgencies[:3])}.",
        })

    if ".apk" in lowered or "install app" in lowered or "download app" in lowered:
        threat_score += 45
        detected_flags.append({
            "indicator": "Malicious App / APK Download Lure",
            "severity": "CRITICAL",
            "detail": "Traffic police never asks citizens to install third-party .apk files to view or pay challans.",
        })

    if ("pay" in lowered or "fine" in lowered or "challan" in lowered) and found_urls and not is_whitelisted and threat_score == 0:
        threat_score += 25
        detected_flags.append({
            "indicator": "Unverified Third-Party Link",
            "severity": "MEDIUM",
            "detail": "Message references fine payment but redirects to an unverified non-government domain.",
        })

    if is_whitelisted and not detected_flags:
        threat_score = 0

    threat_score = min(max(threat_score, 0), 100)

    if threat_score >= 60:
        risk_level = "HIGH_RISK_FRAUD"
        recommendation = "DO NOT CLICK OR PAY. This message exhibits severe indicators of an impersonation/smishing scam. File an incident report immediately."
    elif threat_score >= 25:
        risk_level = "SUSPICIOUS"
        recommendation = "Exercise caution. Do not click links directly. Verify pending challans independently at https://echallan.parivahan.gov.in."
    else:
        risk_level = "SAFE"
        recommendation = "No overt fraudulent indicators detected. Ensure payments are made strictly via https://echallan.parivahan.gov.in or https://vcourts.gov.in."

    return {
        "text_sample": cleaned_text[:100] + ("..." if len(cleaned_text) > 100 else ""),
        "threat_score": threat_score,
        "risk_level": risk_level,
        "extracted_domains": extracted_domains,
        "is_official_domain": is_whitelisted,
        "detected_flags": detected_flags,
        "recommendation": recommendation,
        "statutory_recourse": {
            "it_act": rules["statutory_provisions"]["it_act_section"],
            "helpline": rules["statutory_provisions"]["helpline_number"],
            "portal": rules["statutory_provisions"]["cyber_crime_portal"],
            "action": "If defrauded or targeted, file an incident report at cybercrime.gov.in or dial 1930 within the golden hour to freeze fraudulent banking transactions.",
        },
    }


def get_trusted_challan_portals() -> list[str]:
    """Return the registry of verified official government challan portals."""
    return sorted(CYBER_THREAT_RULES.get("trusted_domains", []))


router = APIRouter()


@router.post(
    "/api/v1/cyber/scan-challan-message",
    response_model=ChallanThreatScanResponse,
    tags=["cyber_defense"],
    summary="Scan Challan SMS or Link for Phishing/Fraud (Sec 66D IT Act)",
)
def scan_challan_endpoint(request: ChallanThreatScanRequest) -> ChallanThreatScanResponse:
    """Offline heuristic scanning of traffic challan SMS alerts and URLs for phishing indicators."""
    try:
        result = scan_challan_message(request.message_text)
        return ChallanThreatScanResponse.model_validate(result)
    except app_core.CalculatorInputError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/api/v1/cyber/trusted-domains",
    response_model=TrustedPortalsResponse,
    tags=["cyber_defense"],
    summary="Get List of Verified Official Traffic Challan Domains",
)
def get_trusted_domains_endpoint() -> TrustedPortalsResponse:
    """Return verified official central and state government e-challan portals."""
    domains = get_trusted_challan_portals()
    return TrustedPortalsResponse(trusted_domains=domains, total_count=len(domains))
