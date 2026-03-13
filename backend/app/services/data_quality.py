from __future__ import annotations

from datetime import date
from typing import Any

from app.api.models import DataQualityRequest
from app.core.scoring import weighted_average


def _safe_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _parse_bp(value: str | None) -> tuple[int | None, int | None]:
    if not value or "/" not in value:
        return None, None
    systolic, diastolic = value.split("/", maxsplit=1)
    return _safe_int(systolic), _safe_int(diastolic)


def assess_data_quality(payload: DataQualityRequest) -> dict[str, object]:
    issues: list[dict[str, str]] = []

    completeness = 100
    if not payload.demographics.name:
        completeness -= 15
        issues.append({"field": "demographics.name", "issue": "Missing patient name.", "severity": "high"})
    if not payload.demographics.dob:
        completeness -= 15
        issues.append({"field": "demographics.dob", "issue": "Missing date of birth.", "severity": "high"})
    if not payload.demographics.gender:
        completeness -= 10
        issues.append({"field": "demographics.gender", "issue": "Gender not documented.", "severity": "medium"})
    if not payload.medications:
        completeness -= 15
        issues.append({"field": "medications", "issue": "Medication list is empty.", "severity": "medium"})
    if payload.allergies == []:
        completeness -= 10
        issues.append(
            {
                "field": "allergies",
                "issue": "No allergies documented - likely incomplete",
                "severity": "medium",
            }
        )
    if not payload.conditions:
        completeness -= 10
        issues.append({"field": "conditions", "issue": "No conditions documented.", "severity": "medium"})

    accuracy = 100
    if payload.demographics.dob and payload.demographics.dob > date.today():
        accuracy -= 30
        issues.append({"field": "demographics.dob", "issue": "Date of birth is in the future.", "severity": "high"})
    if payload.demographics.gender and payload.demographics.gender not in {"M", "F", "O", "U"}:
        accuracy -= 15
        issues.append({"field": "demographics.gender", "issue": "Gender value is non-standard.", "severity": "low"})

    timeliness_age = (date.today() - payload.last_updated).days
    if timeliness_age <= 30:
        timeliness = 100
    elif timeliness_age <= 90:
        timeliness = 85
    elif timeliness_age <= 180:
        timeliness = 70
    elif timeliness_age <= 365:
        timeliness = 55
    else:
        timeliness = 40
        issues.append(
            {
                "field": "last_updated",
                "issue": "Data is 7+ months old",
                "severity": "medium",
            }
        )

    plausibility = 100
    systolic, diastolic = _parse_bp(payload.vital_signs.get("blood_pressure"))
    if systolic is None or diastolic is None:
        plausibility -= 10
        issues.append(
            {
                "field": "vital_signs.blood_pressure",
                "issue": "Blood pressure format is invalid or missing.",
                "severity": "medium",
            }
        )
    elif systolic > 300 or diastolic > 200 or systolic < 60 or diastolic < 30:
        plausibility -= 60
        accuracy -= 20
        issues.append(
            {
                "field": "vital_signs.blood_pressure",
                "issue": f"Blood pressure {payload.vital_signs.get('blood_pressure')} is physiologically implausible",
                "severity": "high",
            }
        )

    heart_rate = _safe_int(payload.vital_signs.get("heart_rate"))
    if heart_rate is not None and (heart_rate < 20 or heart_rate > 240):
        plausibility -= 40
        issues.append(
            {
                "field": "vital_signs.heart_rate",
                "issue": f"Heart rate {heart_rate} is outside a plausible clinical range.",
                "severity": "high",
            }
        )

    if any("metformin" in med.lower() for med in payload.medications) and "Type 2 Diabetes" not in payload.conditions:
        plausibility -= 15
        issues.append(
            {
                "field": "conditions",
                "issue": "Medication list suggests diabetes, but the condition is not documented.",
                "severity": "low",
            }
        )

    breakdown = {
        "completeness": max(completeness, 0),
        "accuracy": max(accuracy, 0),
        "timeliness": max(timeliness, 0),
        "clinical_plausibility": max(plausibility, 0),
    }
    return {
        "overall_score": weighted_average(breakdown),
        "breakdown": breakdown,
        "issues_detected": issues,
    }
