from __future__ import annotations

from functools import lru_cache

from app.ai.service import AIService


@lru_cache(maxsize=1)
def get_ai_service() -> AIService:
    return AIService()
