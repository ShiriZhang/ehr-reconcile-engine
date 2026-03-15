from __future__ import annotations

from app.api.models import MedicationReconcileRequest
from app.core.rules import normalize_lab_keys, safety_penalty
from app.services.reconciliation import reconcile_medication_request


def test_empty_labs_and_conditions_returns_zero_penalty() -> None:
    result = safety_penalty("Metformin 500mg twice daily", {}, [])
    assert result.penalty == 0.0
    assert result.reasons == []
    assert result.triggered_rules == []


def test_irrelevant_labs_return_zero_penalty() -> None:
    result = safety_penalty("Metformin 500mg twice daily", {"ALT": 200, "INR": 5.0}, [])
    assert result.penalty == 0.0


def test_unknown_medication_returns_zero_penalty() -> None:
    result = safety_penalty("Amoxicillin 500mg three times daily", {"eGFR": 20}, ["Heart Failure"])
    assert result.penalty == 0.0


def test_metformin_egfr_below_30_triggers_contraindication() -> None:
    result = safety_penalty("Metformin 500mg twice daily", {"eGFR": 25}, [])
    assert result.penalty == 0.28
    assert any("below 30" in reason for reason in result.reasons)
    assert "metformin:egfr" in result.triggered_rules


def test_metformin_egfr_exactly_30_triggers_contraindication() -> None:
    result = safety_penalty("Metformin 500mg twice daily", {"eGFR": 30}, [])
    assert result.penalty == 0.28


def test_metformin_egfr_31_does_not_trigger_contraindication() -> None:
    result = safety_penalty("Metformin 500mg twice daily", {"eGFR": 31}, [])
    assert result.penalty == 0.0


def test_metformin_high_dose_egfr_below_45_triggers_warning() -> None:
    result = safety_penalty("Metformin 1000mg twice daily", {"eGFR": 40}, [])
    assert result.penalty == 0.18
    assert any("1000" in reason for reason in result.reasons)


def test_metformin_high_dose_egfr_exactly_45_triggers_warning() -> None:
    result = safety_penalty("Metformin 1000mg twice daily", {"eGFR": 45}, [])
    assert result.penalty == 0.18


def test_metformin_high_dose_egfr_46_no_penalty() -> None:
    result = safety_penalty("Metformin 1000mg twice daily", {"eGFR": 46}, [])
    assert result.penalty == 0.0


def test_metformin_low_dose_egfr_below_45_no_penalty() -> None:
    result = safety_penalty("Metformin 500mg twice daily", {"eGFR": 40}, [])
    assert result.penalty == 0.0


def test_egfr_case_insensitive() -> None:
    for key in ["eGFR", "egfr", "EGFR", "e_gfr"]:
        result = safety_penalty("Metformin 500mg daily", {key: 25}, [])
        assert result.penalty == 0.28, f"Failed for lab key: {key}"


def test_potassium_alias_k() -> None:
    for key in ["potassium", "K", "k+"]:
        result = safety_penalty("Digoxin 0.25mg daily", {key: 3.0}, [])
        assert result.penalty == 0.20, f"Failed for lab key: {key}"


def test_warfarin_high_inr_triggers_penalty() -> None:
    result = safety_penalty("Warfarin 5mg daily", {"INR": 4.5}, [])
    assert result.penalty == 0.22


def test_gentamicin_high_creatinine_triggers_penalty() -> None:
    result = safety_penalty("Gentamicin 80mg daily", {"creatinine": 2.5}, [])
    assert result.penalty == 0.22


def test_atorvastatin_high_alt_triggers_penalty() -> None:
    result = safety_penalty("Atorvastatin 40mg daily", {"ALT": 150}, [])
    assert result.penalty == 0.16


def test_ibuprofen_low_egfr_triggers_penalty() -> None:
    result = safety_penalty("Ibuprofen 400mg three times daily", {"eGFR": 25}, [])
    assert result.penalty == 0.24


def test_metformin_heart_failure_triggers_penalty() -> None:
    result = safety_penalty("Metformin 500mg daily", {}, ["Heart Failure", "Hypertension"])
    assert result.penalty == 0.15
    assert any("heart failure" in reason.lower() for reason in result.reasons)


def test_metoprolol_asthma_triggers_penalty() -> None:
    result = safety_penalty("Metoprolol 50mg twice daily", {}, ["Asthma"])
    assert result.penalty == 0.20


def test_ibuprofen_gi_bleed_triggers_penalty() -> None:
    result = safety_penalty("Ibuprofen 400mg daily", {}, ["History of gastrointestinal bleeding"])
    assert result.penalty == 0.22


def test_multiple_rules_returns_max_penalty() -> None:
    result = safety_penalty("Metformin 1000mg daily", {"eGFR": 25}, ["Heart Failure"])
    assert result.penalty == 0.28
    assert len(result.reasons) >= 2


def test_ibuprofen_egfr_and_gi_bleed() -> None:
    result = safety_penalty("Ibuprofen 400mg daily", {"eGFR": 25}, ["Gastrointestinal bleed"])
    assert result.penalty == 0.24
    assert len(result.reasons) == 2


def test_normalize_lab_keys_maps_aliases() -> None:
    raw = {"eGFR": 45, "K": 4.0, "SCR": 1.2, "UnknownLab": 99}
    result = normalize_lab_keys(raw)
    assert result == {"egfr": 45, "potassium": 4.0, "creatinine": 1.2, "unknownlab": 99}


def test_reasoning_mentions_penalized_alternatives() -> None:
    payload = MedicationReconcileRequest.model_validate(
        {
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
            ],
        }
    )

    result = reconcile_medication_request(payload)
    assert "Alternative regimens were deprioritized" in result["reasoning"]
    assert "Metformin 1000mg twice daily" in result["reasoning"]


def test_reasoning_mentions_winner_own_concerns_when_all_penalized() -> None:
    payload = MedicationReconcileRequest.model_validate(
        {
            "patient_context": {
                "conditions": [],
                "recent_labs": {"eGFR": 25},
            },
            "sources": [
                {
                    "system": "System A",
                    "medication": "Metformin 500mg daily",
                    "last_updated": "2025-01-20",
                    "source_reliability": "high",
                },
                {
                    "system": "System B",
                    "medication": "Metformin 1000mg daily",
                    "last_updated": "2025-01-15",
                    "source_reliability": "high",
                },
            ],
        }
    )

    result = reconcile_medication_request(payload)
    reasoning = str(result["reasoning"]).lower()
    assert "safety considerations" in reasoning or "safety concerns" in reasoning


def test_reasoning_no_safety_mention_when_no_rules_triggered() -> None:
    payload = MedicationReconcileRequest.model_validate(
        {
            "patient_context": {
                "conditions": ["Hypertension"],
                "recent_labs": {},
            },
            "sources": [
                {
                    "system": "System A",
                    "medication": "Lisinopril 10mg daily",
                    "last_updated": "2025-01-20",
                    "source_reliability": "high",
                },
                {
                    "system": "System B",
                    "medication": "Lisinopril 20mg daily",
                    "last_updated": "2025-01-10",
                    "source_reliability": "medium",
                },
            ],
        }
    )

    result = reconcile_medication_request(payload)
    assert "safety" not in str(result["reasoning"]).lower()
