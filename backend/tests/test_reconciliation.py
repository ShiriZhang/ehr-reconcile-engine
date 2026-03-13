from __future__ import annotations


def test_reconciliation_prefers_recent_high_reliability_record(client) -> None:
    response = client.post(
        "/api/reconcile/medication",
        headers={"x-api-key": "test-api-key"},
        json={
            "patient_context": {
                "age": 67,
                "conditions": ["Type 2 Diabetes", "Hypertension"],
                "recent_labs": {"eGFR": 45},
            },
            "sources": [
                {
                    "system": "Hospital EHR",
                    "medication": "Metformin 1000mg twice daily",
                    "last_updated": "2024-10-15",
                    "source_reliability": "high",
                },
                {
                    "system": "Primary Care",
                    "medication": "Metformin 500mg twice daily",
                    "last_updated": "2025-01-20",
                    "source_reliability": "high",
                },
                {
                    "system": "Pharmacy",
                    "medication": "Metformin 1000mg daily",
                    "last_filled": "2025-01-25",
                    "source_reliability": "medium",
                },
            ],
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["reconciled_medication"] == "Metformin 500mg twice daily"
    assert payload["clinical_safety_check"] in {"PASSED", "WARNING"}
    assert payload["confidence_score"] >= 0.7


def test_reconciliation_validation_rejects_empty_sources(client) -> None:
    response = client.post(
        "/api/reconcile/medication",
        headers={"x-api-key": "test-api-key"},
        json={"patient_context": {}, "sources": []},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"
