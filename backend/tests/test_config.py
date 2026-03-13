from __future__ import annotations

import os
from pathlib import Path

from app.core.config import load_env_file


def test_load_env_file_sets_unset_values_without_overriding_existing_env(monkeypatch) -> None:
    env_file = Path(__file__).parent / "fixtures" / "config_sample.env"

    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "existing-value")

    load_env_file(env_file)

    assert os.environ["API_KEY"] == "file-api-key"
    assert os.environ["OPENAI_API_KEY"] == "openai-from-file"
    assert os.environ["DEEPSEEK_API_KEY"] == "existing-value"
