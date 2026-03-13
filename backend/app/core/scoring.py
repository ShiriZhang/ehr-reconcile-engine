from __future__ import annotations


def calibrate_confidence(base_score: float, margin: float, agreement_ratio: float) -> float:
    calibrated = 0.45 + (base_score * 0.3) + (margin * 0.15) + (agreement_ratio * 0.1)
    return round(max(0.05, min(calibrated, 0.99)), 2)


def weighted_average(parts: dict[str, int]) -> int:
    if not parts:
        return 0
    total = sum(parts.values()) / len(parts)
    return int(round(total))
