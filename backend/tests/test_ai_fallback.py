from __future__ import annotations

import asyncio

import httpx

from app.ai.providers import ProviderError
from app.ai.service import AIService


class FailingProvider:
    def __init__(self, name: str) -> None:
        self.name = name

    async def complete_json(self, prompt: str) -> dict:
        raise ProviderError(f"{self.name} failed")


class SuccessfulProvider:
    name = "deepseek"

    def __init__(self) -> None:
        self.calls = 0

    async def complete_json(self, prompt: str) -> dict:
        self.calls += 1
        return {
            "reasoning": "Fallback provider succeeded.",
            "recommended_actions": ["Verify with clinician."],
            "clinical_safety_check": "PASSED",
        }


class NetworkFailureProvider:
    name = "openai"

    async def complete_json(self, prompt: str) -> dict:
        raise httpx.ConnectError("network down")


class QualityProvider:
    name = "openai"

    async def complete_json(self, prompt: str) -> dict:
        return {
            "breakdown": {
                "completeness": 90,
                "accuracy": 80,
                "timeliness": 70,
                "clinical_plausibility": 60,
            },
            "issues_detected": [
                {
                    "field": "allergies",
                    "issue": "No allergies documented - likely incomplete",
                    "severity": "medium",
                }
            ],
        }


def test_ai_service_uses_fallback_provider() -> None:
    service = AIService()
    backup = SuccessfulProvider()
    service.providers = [FailingProvider("openai"), backup]

    result = asyncio.run(
        service.enrich_reconciliation(
            {"patient_context": {}, "sources": []},
            {
                "reconciled_medication": "Metformin 500mg twice daily",
                "confidence_score": 0.81,
                "reasoning": "Base reasoning",
                "recommended_actions": ["Base action"],
                "clinical_safety_check": "WARNING",
            },
        )
    )

    assert result["reasoning"] == "Fallback provider succeeded."
    assert backup.calls == 1


def test_ai_service_caches_repeated_requests() -> None:
    service = AIService()
    backup = SuccessfulProvider()
    service.providers = [backup]
    payload = {"patient_context": {}, "sources": []}
    base_result = {
        "reconciled_medication": "Metformin 500mg twice daily",
        "confidence_score": 0.81,
        "reasoning": "Base reasoning",
        "recommended_actions": ["Base action"],
        "clinical_safety_check": "WARNING",
    }

    first = asyncio.run(service.enrich_reconciliation(payload, base_result))
    second = asyncio.run(service.enrich_reconciliation(payload, base_result))

    assert first == second
    assert backup.calls == 1


def test_ai_service_falls_back_when_provider_hits_network_error() -> None:
    service = AIService()
    backup = SuccessfulProvider()
    service.providers = [NetworkFailureProvider(), backup]

    result = asyncio.run(
        service.enrich_reconciliation(
            {"patient_context": {}, "sources": []},
            {
                "reconciled_medication": "Metformin 500mg twice daily",
                "confidence_score": 0.81,
                "reasoning": "Base reasoning",
                "recommended_actions": ["Base action"],
                "clinical_safety_check": "WARNING",
            },
        )
    )

    assert result["reasoning"] == "Fallback provider succeeded."
    assert backup.calls == 1


def test_data_quality_enrichment_recomputes_overall_score() -> None:
    service = AIService()
    service.providers = [QualityProvider()]

    result = asyncio.run(
        service.enrich_data_quality(
            {
                "demographics": {"name": "John Doe", "dob": "1955-03-15", "gender": "M"},
                "medications": ["Metformin 500mg"],
                "allergies": [],
                "conditions": ["Type 2 Diabetes"],
                "vital_signs": {"blood_pressure": "120/80", "heart_rate": 72},
                "last_updated": "2026-03-01",
            },
            {
                "overall_score": 100,
                "breakdown": {
                    "completeness": 100,
                    "accuracy": 100,
                    "timeliness": 100,
                    "clinical_plausibility": 100,
                },
                "issues_detected": [],
            },
        )
    )

    assert result["overall_score"] == 75
    assert result["breakdown"]["clinical_plausibility"] == 60
