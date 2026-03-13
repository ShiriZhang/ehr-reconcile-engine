from __future__ import annotations

import json
from typing import Any


def build_reconciliation_prompt(payload: dict[str, Any], base_result: dict[str, Any]) -> str:
    return (
        "You are a clinical data reconciliation assistant. "
        "Return strict JSON with keys: reasoning, recommended_actions, clinical_safety_check. "
        "Keep reasoning concise and explain why the chosen medication is most likely correct.\n\n"
        f"Patient payload:\n{json.dumps(payload, indent=2, default=str)}\n\n"
        f"Rule-based draft:\n{json.dumps(base_result, indent=2, default=str)}"
    )


def build_quality_prompt(payload: dict[str, Any], base_result: dict[str, Any]) -> str:
    return (
        "You are a clinical data quality assistant. "
        "Return strict JSON with keys: breakdown, issues_detected. "
        "Validate plausibility, timeliness, completeness, and likely documentation gaps.\n\n"
        f"Patient record:\n{json.dumps(payload, indent=2, default=str)}\n\n"
        f"Rule-based draft:\n{json.dumps(base_result, indent=2, default=str)}"
    )
