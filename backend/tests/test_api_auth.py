from __future__ import annotations


def test_reconcile_requires_api_key(client) -> None:
    response = client.post("/api/reconcile/medication", json={"patient_context": {}, "sources": []})
    assert response.status_code == 401


def test_invalid_api_key_returns_401(client) -> None:
    response = client.post(
        "/api/validate/data-quality",
        headers={"x-api-key": "wrong"},
        json={
            "demographics": {"name": "John Doe", "dob": "1955-03-15", "gender": "M"},
            "medications": ["Metformin 500mg"],
            "allergies": [],
            "conditions": ["Type 2 Diabetes"],
            "vital_signs": {"blood_pressure": "120/80", "heart_rate": 72},
            "last_updated": "2026-03-01",
        },
    )
    assert response.status_code == 401
