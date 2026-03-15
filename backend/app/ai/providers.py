from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


class ProviderError(RuntimeError):
    pass


@dataclass(slots=True)
class ChatProvider:
    name: str
    api_key: str
    model: str
    base_url: str

    async def complete_json(self, prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderError(f"{self.name} API key is not configured.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a clinical decision support system. "
                        "You return valid JSON only, with no markdown fences or commentary. "
                        "Your responses must be medically conservative — when uncertain, "
                        "flag safety concerns rather than dismiss them."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
                response = await client.post(self.base_url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError(f"{self.name} request timed out.") from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"{self.name} request failed due to a network error.") from exc

        if response.status_code == 429:
            raise ProviderError(f"{self.name} request was rate limited.")
        if response.status_code >= 500:
            raise ProviderError(f"{self.name} request failed with server error {response.status_code}.")
        if response.status_code >= 400:
            raise ProviderError(f"{self.name} request failed with status {response.status_code}.")

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(f"{self.name} returned invalid JSON in the HTTP response body.") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{self.name} returned an unexpected response shape.") from exc

        if not content:
            raise ProviderError(f"{self.name} returned empty content.")

        try:
            return json.loads(_normalize_json_content(content))
        except json.JSONDecodeError as exc:
            raise ProviderError(f"{self.name} returned invalid JSON.") from exc


def _normalize_json_content(content: str) -> str:
    text = content.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines:
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    normalized = "\n".join(lines).strip()
    if normalized.lower().startswith("json"):
        normalized = normalized[4:].lstrip()
    return normalized


def build_openai_provider() -> ChatProvider:
    return ChatProvider(
        name="openai",
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url="https://api.openai.com/v1/chat/completions",
    )


def build_deepseek_provider() -> ChatProvider:
    return ChatProvider(
        name="deepseek",
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model,
        base_url="https://api.deepseek.com/chat/completions",
    )
