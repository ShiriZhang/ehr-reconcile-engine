from __future__ import annotations

import json
from pathlib import Path

import pytest


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "samples" / "pyhealth"
RECONCILE_FIXTURES = sorted(FIXTURE_DIR.glob("reconcile_*.json")) if FIXTURE_DIR.exists() else []
QUALITY_FIXTURES = sorted(FIXTURE_DIR.glob("quality_*.json")) if FIXTURE_DIR.exists() else []


@pytest.mark.skipif(not RECONCILE_FIXTURES, reason="No PyHealth reconciliation fixtures found.")
@pytest.mark.parametrize("fixture_path", RECONCILE_FIXTURES, ids=lambda path: path.name)
def test_pyhealth_reconciliation_fixtures(client, fixture_path: Path) -> None:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    response = client.post(
        "/api/reconcile/medication",
        headers={"x-api-key": "test-api-key"},
        json=payload,
    )
    body = response.json()

    assert response.status_code == 200
    assert set(body) == {
        "reconciled_medication",
        "confidence_score",
        "reasoning",
        "recommended_actions",
        "clinical_safety_check",
    }
    assert isinstance(body["reconciled_medication"], str) and body["reconciled_medication"]
    assert isinstance(body["confidence_score"], (int, float))
    assert isinstance(body["reasoning"], str) and body["reasoning"]
    assert isinstance(body["recommended_actions"], list)
    assert body["clinical_safety_check"] in {"PASSED", "WARNING", "FAILED"}


@pytest.mark.skipif(not QUALITY_FIXTURES, reason="No PyHealth quality fixtures found.")
@pytest.mark.parametrize("fixture_path", QUALITY_FIXTURES, ids=lambda path: path.name)
def test_pyhealth_quality_fixtures(client, fixture_path: Path) -> None:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    response = client.post(
        "/api/validate/data-quality",
        headers={"x-api-key": "test-api-key"},
        json=payload,
    )
    body = response.json()

    assert response.status_code == 200
    assert set(body) == {"overall_score", "breakdown", "issues_detected"}
    assert isinstance(body["overall_score"], int)
    assert set(body["breakdown"]) == {"completeness", "accuracy", "timeliness", "clinical_plausibility"}
    assert isinstance(body["issues_detected"], list)
    assert any(
        issue["field"] == "allergies" and "allergies" in issue["issue"].lower()
        for issue in body["issues_detected"]
    )
