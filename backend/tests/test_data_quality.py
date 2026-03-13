from __future__ import annotations


def test_data_quality_detects_implausible_blood_pressure(client) -> None:
    response = client.post(
        "/api/validate/data-quality",
        headers={"x-api-key": "test-api-key"},
        json={
            "demographics": {"name": "John Doe", "dob": "1955-03-15", "gender": "M"},
            "medications": ["Metformin 500mg", "Lisinopril 10mg"],
            "allergies": [],
            "conditions": ["Type 2 Diabetes"],
            "vital_signs": {"blood_pressure": "340/180", "heart_rate": 72},
            "last_updated": "2024-06-15",
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["breakdown"]["clinical_plausibility"] <= 40
    assert any(issue["field"] == "vital_signs.blood_pressure" for issue in payload["issues_detected"])


def test_data_quality_detects_missing_required_fields(client) -> None:
    response = client.post(
        "/api/validate/data-quality",
        headers={"x-api-key": "test-api-key"},
        json={
            "demographics": {"name": "", "gender": "M"},
            "medications": [],
            "allergies": [],
            "conditions": [],
            "vital_signs": {},
            "last_updated": "2026-03-01",
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["breakdown"]["completeness"] < 80
    assert len(payload["issues_detected"]) >= 3
