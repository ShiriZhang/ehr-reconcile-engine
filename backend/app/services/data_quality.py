from __future__ import annotations

from datetime import date

from app.api.models import DataQualityRequest
from app.core import data_quality_rules
from app.core.scoring import weighted_average


def _score_completeness(payload: DataQualityRequest) -> tuple[int, list[dict[str, str]]]:
    score = 100
    issues: list[dict[str, str]] = []

    if not payload.demographics.name:
        score -= 15
        issues.append({"field": "demographics.name", "issue": "Missing patient name.", "severity": "high"})
    if not payload.demographics.dob:
        score -= 15
        issues.append({"field": "demographics.dob", "issue": "Missing date of birth.", "severity": "high"})
    if not payload.demographics.gender:
        score -= 10
        issues.append({"field": "demographics.gender", "issue": "Gender not documented.", "severity": "medium"})
    if not payload.medications:
        score -= 15
        issues.append({"field": "medications", "issue": "Medication list is empty.", "severity": "medium"})
    if payload.allergies == []:
        score -= 10
        issues.append(
            {
                "field": "allergies",
                "issue": "No allergies documented - likely incomplete",
                "severity": "medium",
            }
        )
    if not payload.conditions:
        score -= 10
        issues.append({"field": "conditions", "issue": "No conditions documented.", "severity": "medium"})
    if not payload.vital_signs:
        score -= 15
        issues.append({"field": "vital_signs", "issue": "No vital signs documented.", "severity": "medium"})

    return score, issues


def _score_accuracy(payload: DataQualityRequest) -> tuple[int, list[dict[str, str]]]:
    score = 100
    issues: list[dict[str, str]] = []

    if payload.demographics.dob and payload.demographics.dob > date.today():
        score -= 30
        issues.append({"field": "demographics.dob", "issue": "Date of birth is in the future.", "severity": "high"})
    if payload.demographics.gender and payload.demographics.gender not in {"M", "F", "O", "U"}:
        score -= 15
        issues.append({"field": "demographics.gender", "issue": "Gender value is non-standard.", "severity": "low"})
    if payload.last_updated > date.today():
        score -= 25
        issues.append(
            {
                "field": "last_updated",
                "issue": "Record timestamp is in the future - likely a data entry error.",
                "severity": "high",
            }
        )

    return score, issues


def _score_timeliness(payload: DataQualityRequest) -> tuple[int, list[dict[str, str]]]:
    timeliness_age = (date.today() - payload.last_updated).days
    if timeliness_age < 0:
        return 50, []
    if timeliness_age <= 30:
        return 100, []
    if timeliness_age <= 90:
        return 85, []
    if timeliness_age <= 180:
        return 70, []
    if timeliness_age <= 365:
        return 55, [
            {
                "field": "last_updated",
                "issue": "Data is 6-12 months old.",
                "severity": "medium",
            }
        ]
    return 40, [
        {
            "field": "last_updated",
            "issue": "Data is over 12 months old.",
            "severity": "high",
        }
    ]


def _score_clinical_plausibility(payload: DataQualityRequest) -> tuple[int, list[dict[str, str]]]:
    score = 100
    issues: list[dict[str, str]] = []

    for vital_rule in data_quality_rules.VITAL_RULES:
        penalty, rule_issues = data_quality_rules.evaluate_vital_rule(vital_rule, payload.vital_signs)
        score -= penalty
        issues.extend(rule_issues)

    normalized_medications = data_quality_rules.normalize_medications(payload.medications)
    normalized_conditions = data_quality_rules.normalize_conditions(payload.conditions)
    for medication_rule in data_quality_rules.MEDICATION_CONDITION_RULES:
        penalty, rule_issues = data_quality_rules.evaluate_medication_condition_rule(
            medication_rule,
            normalized_medications,
            normalized_conditions,
        )
        score -= penalty
        issues.extend(rule_issues)

    return score, issues


def assess_data_quality(payload: DataQualityRequest) -> dict[str, object]:
    completeness, completeness_issues = _score_completeness(payload)
    accuracy, accuracy_issues = _score_accuracy(payload)
    timeliness, timeliness_issues = _score_timeliness(payload)
    plausibility, plausibility_issues = _score_clinical_plausibility(payload)

    breakdown = {
        "completeness": max(completeness, 0),
        "accuracy": max(accuracy, 0),
        "timeliness": max(timeliness, 0),
        "clinical_plausibility": max(plausibility, 0),
    }
    issues = completeness_issues + accuracy_issues + timeliness_issues + plausibility_issues

    return {
        "overall_score": weighted_average(breakdown),
        "breakdown": breakdown,
        "issues_detected": issues,
    }
