from __future__ import annotations

import asyncio

import httpx
import pytest

from app.ai.providers import ChatProvider, ProviderError


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    def __init__(self, response: FakeResponse | None = None, exception: Exception | None = None) -> None:
        self.response = response
        self.exception = exception

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
        if self.exception is not None:
            raise self.exception
        return self.response or FakeResponse(status_code=200)


def _build_provider() -> ChatProvider:
    return ChatProvider(
        name="openai",
        api_key="test-key",
        model="test-model",
        base_url="https://example.com/v1/chat/completions",
    )


def _patch_async_client(monkeypatch, response: FakeResponse | None = None, exception: Exception | None = None) -> None:
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: FakeAsyncClient(response=response, exception=exception),
    )


def test_chat_provider_maps_429_to_provider_error(monkeypatch) -> None:
    _patch_async_client(monkeypatch, response=FakeResponse(status_code=429))

    with pytest.raises(ProviderError, match="rate limited"):
        asyncio.run(_build_provider().complete_json("prompt"))


def test_chat_provider_maps_5xx_to_provider_error(monkeypatch) -> None:
    _patch_async_client(monkeypatch, response=FakeResponse(status_code=503))

    with pytest.raises(ProviderError, match="server error 503"):
        asyncio.run(_build_provider().complete_json("prompt"))


def test_chat_provider_parses_code_fenced_json(monkeypatch) -> None:
    _patch_async_client(
        monkeypatch,
        response=FakeResponse(
            status_code=200,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": '```json\n{"reasoning":"ok","recommended_actions":[],"clinical_safety_check":"PASSED"}\n```'
                        }
                    }
                ]
            },
        ),
    )

    result = asyncio.run(_build_provider().complete_json("prompt"))

    assert result["reasoning"] == "ok"
    assert result["clinical_safety_check"] == "PASSED"
