from __future__ import annotations

import json
from typing import Any


def build_reconciliation_prompt(payload: dict[str, Any], base_result: dict[str, Any]) -> str:
    return (
        "You are a senior clinical pharmacist performing medication reconciliation. "
        "Your task is to review conflicting medication records from multiple healthcare systems "
        "and validate or improve the draft reconciliation below.\n\n"

        "## How to reason\n"
        "1. Compare source reliability and recency — more recent records from high-reliability "
        "systems generally take precedence.\n"
        "2. Evaluate clinical safety — consider the patient's age, conditions, and lab values. "
        "For example, reduced eGFR may require dose adjustments for renally cleared drugs like metformin.\n"
        "3. Look for cross-source agreement — if multiple systems report the same regimen, confidence increases.\n"
        "4. Flag any drug-disease contraindications or dose-safety concerns.\n\n"

        "## Output format\n"
        "Return strict JSON only (no markdown fences) with exactly these keys:\n"
        '- "reasoning": string — 2-4 sentences explaining why the reconciled medication is most likely correct, '
        "referencing specific source dates, reliability, and clinical factors.\n"
        '- "recommended_actions": list of strings — concrete next steps for the care team.\n'
        '- "clinical_safety_check": one of "PASSED", "WARNING", or "FAILED".\n\n'

        f"## Patient payload\n{json.dumps(payload, indent=2, default=str)}\n\n"
        f"## Rule-based draft (improve this)\n{json.dumps(base_result, indent=2, default=str)}"
    )


def build_quality_prompt(payload: dict[str, Any], base_result: dict[str, Any]) -> str:
    return (
        "You are a clinical data quality analyst reviewing an EHR patient record. "
        "Your task is to validate or improve the draft quality assessment below.\n\n"

        "## Scoring dimensions (each 0-100)\n"
        "- completeness: are required fields populated? Empty allergies lists are suspicious.\n"
        "- accuracy: are values valid? Check for future dates, non-standard codes, impossible vitals.\n"
        "- timeliness: how recent is the data? Stale records reduce reliability.\n"
        "- clinical_plausibility: do medications match conditions? Are vital signs physiologically possible?\n\n"

        "## Output format\n"
        "Return strict JSON only (no markdown fences) with exactly these keys:\n"
        '- "breakdown": object with keys completeness, accuracy, timeliness, clinical_plausibility, each an integer 0-100.\n'
        '- "issues_detected": list of objects, each with "field" (string), "issue" (string), '
        'and "severity" (one of "low", "medium", "high").\n\n'

        f"## Patient record\n{json.dumps(payload, indent=2, default=str)}\n\n"
        f"## Rule-based draft (improve this)\n{json.dumps(base_result, indent=2, default=str)}"
    )
