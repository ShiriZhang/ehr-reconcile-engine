from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal

from app.core.rules import normalize_medication_name


Severity = Literal["low", "medium", "high"]
VitalParserKind = Literal["numeric", "blood_pressure"]

_UNIT_SUFFIX = re.compile(r"[^0-9.\-]+$")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class VitalRule:
    field: str
    parser_kind: VitalParserKind
    display_name: str
    invalid_penalty: int
    invalid_severity: Severity
    range_penalty: int
    range_severity: Severity
    min_value: int
    max_value: int
    secondary_min_value: int | None = None
    secondary_max_value: int | None = None
    value_suffix: str = ""


@dataclass(frozen=True, slots=True)
class MedicationConditionRule:
    medication_keywords: tuple[str, ...]
    condition_keywords: tuple[str, ...]
    penalty: int
    severity: Severity
    issue: str


VITAL_RULES: tuple[VitalRule, ...] = (
    VitalRule(
        field="blood_pressure",
        parser_kind="blood_pressure",
        display_name="Blood pressure",
        invalid_penalty=10,
        invalid_severity="medium",
        range_penalty=60,
        range_severity="high",
        min_value=60,
        max_value=300,
        secondary_min_value=30,
        secondary_max_value=200,
    ),
    VitalRule(
        field="heart_rate",
        parser_kind="numeric",
        display_name="Heart rate",
        invalid_penalty=10,
        invalid_severity="medium",
        range_penalty=40,
        range_severity="high",
        min_value=20,
        max_value=240,
    ),
    VitalRule(
        field="respiratory_rate",
        parser_kind="numeric",
        display_name="Respiratory rate",
        invalid_penalty=10,
        invalid_severity="medium",
        range_penalty=30,
        range_severity="high",
        min_value=4,
        max_value=60,
    ),
    VitalRule(
        field="oxygen_saturation",
        parser_kind="numeric",
        display_name="Oxygen saturation",
        invalid_penalty=10,
        invalid_severity="medium",
        range_penalty=30,
        range_severity="high",
        min_value=40,
        max_value=100,
        value_suffix="%",
    ),
)

MEDICATION_CONDITION_RULES: tuple[MedicationConditionRule, ...] = (
    MedicationConditionRule(
        medication_keywords=("metformin",),
        condition_keywords=("diabetes",),
        penalty=15,
        severity="low",
        issue="Medication list suggests diabetes, but the condition is not documented.",
    ),
    MedicationConditionRule(
        medication_keywords=("insulin",),
        condition_keywords=("diabetes",),
        penalty=10,
        severity="low",
        issue="Insulin in medication list may suggest diabetes, but no diabetes-related condition is documented.",
    ),
)


def has_documented_value(value: Any) -> bool:
    return value is not None and bool(str(value).strip())


def _safe_numeric(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    raw = _UNIT_SUFFIX.sub("", str(value).strip())
    if not raw:
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _parse_bp(value: Any) -> tuple[int | None, int | None]:
    text = str(value).strip() if value is not None else ""
    if not text or "/" not in text:
        return None, None
    systolic, diastolic = text.split("/", maxsplit=1)
    return _safe_numeric(systolic), _safe_numeric(diastolic)


def normalize_condition_text(value: str) -> str:
    return _WHITESPACE.sub(" ", value.strip().lower())


def normalize_conditions(conditions: list[str]) -> str:
    normalized: list[str] = []
    for condition in conditions:
        if not condition:
            continue
        collapsed = normalize_condition_text(condition)
        if collapsed:
            normalized.append(collapsed)
    return " ".join(normalized)


def normalize_medications(medications: list[str]) -> list[str]:
    normalized: list[str] = []
    for medication in medications:
        if not medication or not medication.strip():
            continue
        normalized.append(normalize_medication_name(medication))
    return normalized


def evaluate_vital_rule(rule: VitalRule, vital_signs: dict[str, Any]) -> tuple[int, list[dict[str, str]]]:
    raw_value = vital_signs.get(rule.field)
    if not has_documented_value(raw_value):
        return 0, []

    field = f"vital_signs.{rule.field}"
    if rule.parser_kind == "blood_pressure":
        primary_value, secondary_value = _parse_bp(raw_value)
        if primary_value is None or secondary_value is None:
            return rule.invalid_penalty, [
                {
                    "field": field,
                    "issue": f"{rule.display_name} format is invalid.",
                    "severity": rule.invalid_severity,
                }
            ]
        if (
            primary_value < rule.min_value
            or primary_value > rule.max_value
            or secondary_value is None
            or rule.secondary_min_value is None
            or rule.secondary_max_value is None
            or secondary_value < rule.secondary_min_value
            or secondary_value > rule.secondary_max_value
        ):
            return rule.range_penalty, [
                {
                    "field": field,
                    "issue": f"{rule.display_name} {raw_value} is physiologically implausible",
                    "severity": rule.range_severity,
                }
            ]
        return 0, []

    parsed_value = _safe_numeric(raw_value)
    if parsed_value is None:
        return rule.invalid_penalty, [
            {
                "field": field,
                "issue": f"{rule.display_name} format is invalid.",
                "severity": rule.invalid_severity,
            }
        ]
    if parsed_value < rule.min_value or parsed_value > rule.max_value:
        value_text = f"{parsed_value}{rule.value_suffix}"
        return rule.range_penalty, [
            {
                "field": field,
                "issue": f"{rule.display_name} {value_text} is outside a plausible clinical range.",
                "severity": rule.range_severity,
            }
        ]
    return 0, []


def evaluate_medication_condition_rule(
    rule: MedicationConditionRule,
    normalized_medications: list[str],
    normalized_conditions: str,
) -> tuple[int, list[dict[str, str]]]:
    medication_matches = any(
        keyword in medication
        for medication in normalized_medications
        for keyword in rule.medication_keywords
    )
    if not medication_matches:
        return 0, []
    if any(keyword in normalized_conditions for keyword in rule.condition_keywords):
        return 0, []
    return rule.penalty, [{"field": "conditions", "issue": rule.issue, "severity": rule.severity}]
