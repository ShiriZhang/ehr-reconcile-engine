from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def load_env_file(env_path: Path | None = None) -> None:
    candidate = env_path or Path(__file__).resolve().parents[3] / ".env"
    if not candidate.exists():
        return

    for raw_line in candidate.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value[:1] == value[-1:] and value[:1] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


load_env_file()


@dataclass(slots=True)
class Settings:
    app_name: str = "EHR Reconcile Engine"
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    api_key: str = field(default_factory=lambda: os.getenv("API_KEY", "dev-api-key"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    deepseek_model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
    ai_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("AI_TIMEOUT_SECONDS", "20")))
    frontend_api_base_url: str = field(
        default_factory=lambda: os.getenv("FRONTEND_API_BASE_URL", "http://localhost:8000")
    )


settings = Settings()
