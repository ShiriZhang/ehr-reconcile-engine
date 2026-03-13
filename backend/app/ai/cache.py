from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MemoryCache:
    _store: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def build_key(namespace: str, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        return f"{namespace}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
