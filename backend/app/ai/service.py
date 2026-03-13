from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.ai.cache import MemoryCache
from app.ai.prompts import build_quality_prompt, build_reconciliation_prompt
from app.ai.providers import ProviderError, build_deepseek_provider, build_openai_provider
from app.api.models import DataQualityResult, ReconciliationResult
from app.core.scoring import weighted_average


logger = logging.getLogger(__name__)


class AIService:
    def __init__(self) -> None:
        self.cache = MemoryCache()
        self.providers = [build_openai_provider(), build_deepseek_provider()]

    async def enrich_reconciliation(
        self,
        payload: dict[str, Any],
        base_result: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = build_reconciliation_prompt(payload, base_result)
        cache_key = self.cache.build_key("reconciliation", {"prompt": prompt})
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        for provider in self.providers:
            try:
                enriched = await provider.complete_json(prompt)
                merged = {
                    **base_result,
                    "reasoning": enriched.get("reasoning", base_result["reasoning"]),
                    "recommended_actions": enriched.get(
                        "recommended_actions",
                        base_result["recommended_actions"],
                    ),
                    "clinical_safety_check": enriched.get(
                        "clinical_safety_check",
                        base_result["clinical_safety_check"],
                    ),
                }
                validated = ReconciliationResult(**merged).model_dump(mode="json")
                self.cache.set(cache_key, validated)
                return validated
            except ValidationError as exc:
                logger.warning("AI provider %s returned an invalid reconciliation payload: %s", provider.name, exc)
            except ProviderError as exc:
                logger.warning("AI provider %s failed: %s", provider.name, exc)
            except Exception:
                logger.exception("AI provider %s failed unexpectedly during reconciliation enrichment.", provider.name)

        self.cache.set(cache_key, base_result)
        return base_result

    async def enrich_data_quality(
        self,
        payload: dict[str, Any],
        base_result: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = build_quality_prompt(payload, base_result)
        cache_key = self.cache.build_key("data_quality", {"prompt": prompt})
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        for provider in self.providers:
            try:
                enriched = await provider.complete_json(prompt)
                breakdown = enriched.get("breakdown", base_result["breakdown"])
                merged = {
                    **base_result,
                    "overall_score": weighted_average(breakdown) if isinstance(breakdown, dict) else base_result["overall_score"],
                    "breakdown": breakdown,
                    "issues_detected": enriched.get("issues_detected", base_result["issues_detected"]),
                }
                validated = DataQualityResult(**merged).model_dump(mode="json")
                self.cache.set(cache_key, validated)
                return validated
            except ValidationError as exc:
                logger.warning("AI provider %s returned an invalid data quality payload: %s", provider.name, exc)
            except ProviderError as exc:
                logger.warning("AI provider %s failed: %s", provider.name, exc)
            except Exception:
                logger.exception("AI provider %s failed unexpectedly during data quality enrichment.", provider.name)

        self.cache.set(cache_key, base_result)
        return base_result
