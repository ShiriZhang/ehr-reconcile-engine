from __future__ import annotations

import re
from datetime import date


RELIABILITY_WEIGHTS = {
    "high": 1.0,
    "medium": 0.75,
    "low": 0.55,
}


def normalize_medication_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def parse_medication_details(value: str) -> dict[str, float | str | None]:
    normalized = normalize_medication_name(value)
    dose_match = re.search(r"(\d+(?:\.\d+)?)\s*mg", normalized)
    dose_mg = float(dose_match.group(1)) if dose_match else None

    frequency_map = {
        "three times daily": 3.0,
        "twice daily": 2.0,
        "once daily": 1.0,
        "tid": 3.0,
        "bid": 2.0,
        "daily": 1.0,
    }
    frequency = 1.0
    frequency_label = "daily"
    for label, multiplier in frequency_map.items():
        if label in normalized:
            frequency = multiplier
            frequency_label = label
            break

    medication_name = normalized.split(str(int(dose_mg)) + "mg")[0].strip() if dose_mg else normalized
    total_daily_dose = dose_mg * frequency if dose_mg else None
    return {
        "name": medication_name,
        "dose_mg": dose_mg,
        "frequency_per_day": frequency,
        "frequency_label": frequency_label,
        "total_daily_dose": total_daily_dose,
    }


def recency_score(record_date: date | None, today: date | None = None) -> float:
    if record_date is None:
        return 0.2
    comparison_date = today or date.today()
    age_days = max((comparison_date - record_date).days, 0)
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.9
    if age_days <= 90:
        return 0.75
    if age_days <= 180:
        return 0.55
    if age_days <= 365:
        return 0.35
    return 0.2


def completeness_score(*values: object) -> float:
    populated = sum(1 for value in values if value not in (None, "", [], {}))
    return populated / max(len(values), 1)


def safety_penalty(medication: str, egfr: float | None) -> float:
    details = parse_medication_details(medication)
    normalized_name = str(details["name"])
    total_daily_dose = details["total_daily_dose"] or 0.0
    if "metformin" in normalized_name and egfr is not None:
        if egfr <= 45 and total_daily_dose > 1000:
            return 0.18
        if egfr <= 30:
            return 0.28
    return 0.0


def classify_score(score: int) -> str:
    if score >= 80:
        return "green"
    if score >= 60:
        return "yellow"
    return "red"
