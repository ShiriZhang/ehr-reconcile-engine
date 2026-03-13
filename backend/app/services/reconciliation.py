from __future__ import annotations

from collections import Counter

from app.api.models import MedicationReconcileRequest
from app.core.rules import (
    RELIABILITY_WEIGHTS,
    completeness_score,
    normalize_medication_name,
    parse_medication_details,
    recency_score,
    safety_penalty,
)
from app.core.scoring import calibrate_confidence


def reconcile_medication_request(payload: MedicationReconcileRequest) -> dict[str, object]:
    egfr = payload.patient_context.recent_labs.get("eGFR")

    scored_sources: list[dict[str, object]] = []
    normalized_counter = Counter(normalize_medication_name(source.medication) for source in payload.sources)
    for source in payload.sources:
        base_score = (
            RELIABILITY_WEIGHTS[source.source_reliability] * 0.5
            + recency_score(source.reference_date) * 0.35
            + completeness_score(source.system, source.medication, source.reference_date) * 0.15
        )
        penalty = safety_penalty(source.medication, egfr)
        duplicate_boost = 0.08 if normalized_counter[normalize_medication_name(source.medication)] > 1 else 0.0
        final_score = max(0.0, min(base_score - penalty + duplicate_boost, 1.0))
        scored_sources.append(
            {
                "source": source,
                "score": final_score,
                "penalty": penalty,
            }
        )

    scored_sources.sort(key=lambda item: item["score"], reverse=True)
    winner = scored_sources[0]
    runner_up_score = scored_sources[1]["score"] if len(scored_sources) > 1 else 0.0
    agreement_ratio = normalized_counter[normalize_medication_name(winner["source"].medication)] / len(payload.sources)
    confidence = calibrate_confidence(
        base_score=float(winner["score"]),
        margin=max(float(winner["score"]) - float(runner_up_score), 0.0),
        agreement_ratio=agreement_ratio,
    )

    medication_details = parse_medication_details(winner["source"].medication)
    actions = [
        f"Update other systems to reflect {winner['source'].medication}.",
        f"Confirm current regimen with {winner['source'].system}.",
    ]

    reasoning_parts = [
        f"{winner['source'].system} was selected because it had the strongest combination of recency and source reliability.",
    ]
    if winner["penalty"]:
        reasoning_parts.append("Higher-dose alternatives were penalized due to renal safety concerns.")
    if egfr is not None and "metformin" in str(medication_details["name"]):
        reasoning_parts.append(f"Kidney function context was considered using eGFR {egfr}.")
    if agreement_ratio > 0.5:
        reasoning_parts.append("Multiple sources reported the same regimen, increasing confidence.")
    reasoning = " ".join(reasoning_parts)

    safety_status = "PASSED"
    if float(winner["penalty"]) > 0:
        safety_status = "WARNING"
        actions.append("Review renal dosing and verify the latest prescription with the pharmacy.")

    return {
        "reconciled_medication": winner["source"].medication,
        "confidence_score": confidence,
        "reasoning": reasoning,
        "recommended_actions": actions,
        "clinical_safety_check": safety_status,
    }
