from __future__ import annotations

import os

os.environ.setdefault("API_KEY", "test-api-key")

import pytest
from fastapi.testclient import TestClient

from app.ai.service import AIService
from app.api.dependencies import get_ai_service
from app.main import app


class StubAIService(AIService):
    async def enrich_reconciliation(self, payload: dict, base_result: dict) -> dict:
        return base_result

    async def enrich_data_quality(self, payload: dict, base_result: dict) -> dict:
        return base_result


@pytest.fixture()
def client() -> TestClient:
    app.dependency_overrides[get_ai_service] = lambda: StubAIService()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
