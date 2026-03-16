from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from app.core import data_quality_rules


def build_payload() -> dict[str, Any]:
    return {
        "demographics": {"name": "John Doe", "dob": "1955-03-15", "gender": "M"},
        "medications": ["Aspirin 81mg"],
        "allergies": ["NKDA"],
        "conditions": ["Hypertension"],
        "vital_signs": {"blood_pressure": "120/80", "heart_rate": 72},
        "last_updated": date.today().isoformat(),
    }


def post_payload(client, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        "/api/validate/data-quality",
        headers={"x-api-key": "test-api-key"},
        json=payload,
    )
    assert response.status_code == 200
    return response.json()


def get_issues(payload: dict[str, Any], field: str) -> list[dict[str, Any]]:
    return [issue for issue in payload["issues_detected"] if issue["field"] == field]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (72, 72),
        (72.0, 72),
        ("72.0", 72),
        ("98%", 98),
        ("18 bpm", 18),
        (True, None),
        ("abc", None),
    ],
)
def test_safe_numeric_parses_common_ehr_inputs(value: Any, expected: int | None) -> None:
    assert data_quality_rules._safe_numeric(value) == expected


@pytest.mark.parametrize("value", [120, []])
def test_parse_bp_handles_non_string_inputs(value: Any) -> None:
    assert data_quality_rules._parse_bp(value) == (None, None)


def test_empty_vital_signs_penalizes_completeness_only(client) -> None:
    payload = build_payload()
    payload["vital_signs"] = {}

    body = post_payload(client, payload)

    assert body["breakdown"]["completeness"] == 85
    assert body["breakdown"]["clinical_plausibility"] == 100
    assert get_issues(body, "vital_signs") == [
        {"field": "vital_signs", "issue": "No vital signs documented.", "severity": "medium"}
    ]
    assert not get_issues(body, "vital_signs.blood_pressure")


def test_missing_bp_with_other_vitals_does_not_change_score(client) -> None:
    payload = build_payload()
    payload["vital_signs"] = {"heart_rate": 72}

    body = post_payload(client, payload)

    assert body["breakdown"]["completeness"] == 100
    assert body["breakdown"]["clinical_plausibility"] == 100
    assert not get_issues(body, "vital_signs.blood_pressure")


@pytest.mark.parametrize("bp_value", ["", "   "])
def test_blank_bp_is_ignored_without_penalty(client, bp_value: str) -> None:
    payload = build_payload()
    payload["vital_signs"]["blood_pressure"] = bp_value

    body = post_payload(client, payload)

    assert body["breakdown"]["completeness"] == 100
    assert body["breakdown"]["clinical_plausibility"] == 100
    assert not get_issues(body, "vital_signs.blood_pressure")


def test_invalid_bp_format_penalizes_plausibility_only(client) -> None:
    payload = build_payload()
    payload["vital_signs"]["blood_pressure"] = "abc"

    body = post_payload(client, payload)

    assert body["breakdown"]["accuracy"] == 100
    assert body["breakdown"]["clinical_plausibility"] == 90
    assert get_issues(body, "vital_signs.blood_pressure") == [
        {"field": "vital_signs.blood_pressure", "issue": "Blood pressure format is invalid.", "severity": "medium"}
    ]


@pytest.mark.parametrize("bp_value", [120, []])
def test_non_string_bp_values_are_invalid_not_crashes(client, bp_value: Any) -> None:
    payload = build_payload()
    payload["vital_signs"]["blood_pressure"] = bp_value

    body = post_payload(client, payload)

    assert body["breakdown"]["accuracy"] == 100
    assert body["breakdown"]["clinical_plausibility"] == 90
    assert get_issues(body, "vital_signs.blood_pressure") == [
        {"field": "vital_signs.blood_pressure", "issue": "Blood pressure format is invalid.", "severity": "medium"}
    ]


@pytest.mark.parametrize(
    ("field", "value", "issue"),
    [
        ("heart_rate", "abc", "Heart rate format is invalid."),
        ("respiratory_rate", "abc", "Respiratory rate format is invalid."),
        ("oxygen_saturation", "abc", "Oxygen saturation format is invalid."),
    ],
)
def test_invalid_numeric_vital_formats_penalize_plausibility(client, field: str, value: Any, issue: str) -> None:
    payload = build_payload()
    payload["vital_signs"][field] = value

    body = post_payload(client, payload)

    assert body["breakdown"]["accuracy"] == 100
    assert body["breakdown"]["clinical_plausibility"] == 90
    assert get_issues(body, f"vital_signs.{field}") == [
        {"field": f"vital_signs.{field}", "issue": issue, "severity": "medium"}
    ]


@pytest.mark.parametrize(
    ("field", "value", "expected_plausibility", "issue"),
    [
        ("blood_pressure", "340/180", 40, "Blood pressure 340/180 is physiologically implausible"),
        ("heart_rate", 300, 60, "Heart rate 300 is outside a plausible clinical range."),
        ("respiratory_rate", "72 breaths/min", 70, "Respiratory rate 72 is outside a plausible clinical range."),
        ("oxygen_saturation", "150%", 70, "Oxygen saturation 150% is outside a plausible clinical range."),
    ],
)
def test_implausible_vital_values_only_penalize_plausibility(
    client,
    field: str,
    value: Any,
    expected_plausibility: int,
    issue: str,
) -> None:
    payload = build_payload()
    payload["vital_signs"][field] = value

    body = post_payload(client, payload)

    assert body["breakdown"]["accuracy"] == 100
    assert body["breakdown"]["clinical_plausibility"] == expected_plausibility
    assert get_issues(body, f"vital_signs.{field}") == [
        {"field": f"vital_signs.{field}", "issue": issue, "severity": "high"}
    ]


def test_unknown_vital_keys_are_ignored(client) -> None:
    payload = build_payload()
    payload["vital_signs"]["mystery_metric"] = "999"

    body = post_payload(client, payload)

    assert body["breakdown"]["clinical_plausibility"] == 100
    assert not get_issues(body, "vital_signs.mystery_metric")


def test_insulin_without_diabetes_adds_low_severity_condition_issue(client) -> None:
    payload = build_payload()
    payload["medications"] = ["Insulin glargine 10 units"]
    payload["conditions"] = ["Hypertension"]

    body = post_payload(client, payload)

    assert body["breakdown"]["clinical_plausibility"] == 90
    assert get_issues(body, "conditions") == [
        {
            "field": "conditions",
            "issue": "Insulin in medication list may suggest diabetes, but no diabetes-related condition is documented.",
            "severity": "low",
        }
    ]


def test_metformin_matches_non_exact_diabetes_condition(client) -> None:
    payload = build_payload()
    payload["medications"] = ["Metformin 500mg"]
    payload["conditions"] = ["Diabetes with other specified manifestations, type II or unspecified type, uncontrolled"]

    body = post_payload(client, payload)

    assert body["breakdown"]["clinical_plausibility"] == 100
    assert not get_issues(body, "conditions")


@pytest.mark.parametrize(
    ("days_offset", "expected_timeliness", "expected_accuracy", "expected_issue", "expected_severity"),
    [
        (-10, 50, 75, "Record timestamp is in the future - likely a data entry error.", "high"),
        (10, 100, 100, None, None),
        (60, 85, 100, None, None),
        (120, 70, 100, None, None),
        (300, 55, 100, "Data is 6-12 months old.", "medium"),
        (500, 40, 100, "Data is over 12 months old.", "high"),
    ],
)
def test_timeliness_scoring_uses_relative_dates(
    client,
    days_offset: int,
    expected_timeliness: int,
    expected_accuracy: int,
    expected_issue: str | None,
    expected_severity: str | None,
) -> None:
    payload = build_payload()
    payload["last_updated"] = (date.today() - timedelta(days=days_offset)).isoformat()

    body = post_payload(client, payload)

    assert body["breakdown"]["timeliness"] == expected_timeliness
    assert body["breakdown"]["accuracy"] == expected_accuracy
    issues = get_issues(body, "last_updated")
    if expected_issue is None:
        assert not issues
    else:
        assert issues == [{"field": "last_updated", "issue": expected_issue, "severity": expected_severity}]


def test_new_numeric_vital_rule_can_be_added_without_changing_orchestration(client, monkeypatch) -> None:
    new_rule = data_quality_rules.VitalRule(
        field="capillary_refill_seconds",
        parser_kind="numeric",
        display_name="Capillary refill",
        invalid_penalty=10,
        invalid_severity="medium",
        range_penalty=20,
        range_severity="high",
        min_value=0,
        max_value=5,
    )
    monkeypatch.setattr(data_quality_rules, "VITAL_RULES", data_quality_rules.VITAL_RULES + (new_rule,))

    payload = build_payload()
    payload["vital_signs"]["capillary_refill_seconds"] = 9

    body = post_payload(client, payload)

    assert body["breakdown"]["clinical_plausibility"] == 80
    assert get_issues(body, "vital_signs.capillary_refill_seconds") == [
        {
            "field": "vital_signs.capillary_refill_seconds",
            "issue": "Capillary refill 9 is outside a plausible clinical range.",
            "severity": "high",
        }
    ]


def test_new_medication_condition_rule_can_be_added_without_changing_orchestration(client, monkeypatch) -> None:
    new_rule = data_quality_rules.MedicationConditionRule(
        medication_keywords=("levothyroxine",),
        condition_keywords=("hypothyroid",),
        penalty=12,
        severity="low",
        issue="Medication list suggests hypothyroidism, but the condition is not documented.",
    )
    monkeypatch.setattr(
        data_quality_rules,
        "MEDICATION_CONDITION_RULES",
        data_quality_rules.MEDICATION_CONDITION_RULES + (new_rule,),
    )

    payload = build_payload()
    payload["medications"] = ["Levothyroxine 50mcg"]
    payload["conditions"] = ["Hypertension"]

    body = post_payload(client, payload)

    assert body["breakdown"]["clinical_plausibility"] == 88
    assert get_issues(body, "conditions") == [
        {
            "field": "conditions",
            "issue": "Medication list suggests hypothyroidism, but the condition is not documented.",
            "severity": "low",
        }
    ]


def test_data_quality_detects_missing_required_fields(client) -> None:
    payload = build_payload()
    payload["demographics"] = {"name": "", "gender": "M"}
    payload["medications"] = []
    payload["allergies"] = []
    payload["conditions"] = []
    payload["vital_signs"] = {}

    body = post_payload(client, payload)

    assert body["breakdown"]["completeness"] == 20
    assert len(body["issues_detected"]) >= 6
