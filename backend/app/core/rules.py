from __future__ import annotations

from dataclasses import dataclass
import re
from datetime import date


RELIABILITY_WEIGHTS = {
    "high": 1.0,
    "medium": 0.75,
    "low": 0.55,
}

LAB_KEY_ALIASES: dict[str, str] = {
    "egfr": "egfr",
    "e_gfr": "egfr",
    "e_g_f_r": "egfr",
    "gfr": "egfr",
    "inr": "inr",
    "potassium": "potassium",
    "k": "potassium",
    "k+": "potassium",
    "creatinine": "creatinine",
    "scr": "creatinine",
    "alt": "alt",
    "sgpt": "alt",
}


@dataclass(frozen=True, slots=True)
class SafetyRule:
    drug_keyword: str
    trigger_type: str
    trigger_key: str
    compare: str
    threshold: float | None
    penalty: float
    max_daily_dose: float | None
    reason: str


@dataclass(slots=True)
class SafetyResult:
    penalty: float
    reasons: list[str]
    triggered_rules: list[str]


SAFETY_RULES: list[SafetyRule] = [
    SafetyRule(
        drug_keyword="metformin",
        trigger_type="lab",
        trigger_key="egfr",
        compare="le",
        threshold=30,
        penalty=0.28,
        max_daily_dose=None,
        reason="Metformin is contraindicated when eGFR is below 30 due to lactic acidosis risk.",
    ),
    SafetyRule(
        drug_keyword="metformin",
        trigger_type="lab",
        trigger_key="egfr",
        compare="le",
        threshold=45,
        penalty=0.18,
        max_daily_dose=1000,
        reason="Metformin dosing should not exceed 1000 mg/day when eGFR is 45 or below.",
    ),
    SafetyRule(
        drug_keyword="warfarin",
        trigger_type="lab",
        trigger_key="inr",
        compare="gt",
        threshold=4.0,
        penalty=0.22,
        max_daily_dose=None,
        reason="Warfarin carries increased bleeding risk when INR is above 4.0.",
    ),
    SafetyRule(
        drug_keyword="digoxin",
        trigger_type="lab",
        trigger_key="potassium",
        compare="lt",
        threshold=3.5,
        penalty=0.20,
        max_daily_dose=None,
        reason="Digoxin toxicity risk increases when potassium is below 3.5.",
    ),
    SafetyRule(
        drug_keyword="lisinopril",
        trigger_type="lab",
        trigger_key="potassium",
        compare="gt",
        threshold=5.5,
        penalty=0.18,
        max_daily_dose=None,
        reason="Lisinopril can worsen hyperkalemia when potassium is above 5.5.",
    ),
    SafetyRule(
        drug_keyword="enalapril",
        trigger_type="lab",
        trigger_key="potassium",
        compare="gt",
        threshold=5.5,
        penalty=0.18,
        max_daily_dose=None,
        reason="Enalapril can worsen hyperkalemia when potassium is above 5.5.",
    ),
    SafetyRule(
        drug_keyword="ramipril",
        trigger_type="lab",
        trigger_key="potassium",
        compare="gt",
        threshold=5.5,
        penalty=0.18,
        max_daily_dose=None,
        reason="Ramipril can worsen hyperkalemia when potassium is above 5.5.",
    ),
    SafetyRule(
        drug_keyword="gentamicin",
        trigger_type="lab",
        trigger_key="creatinine",
        compare="gt",
        threshold=2.0,
        penalty=0.22,
        max_daily_dose=None,
        reason="Gentamicin increases nephrotoxicity risk when creatinine is above 2.0.",
    ),
    SafetyRule(
        drug_keyword="tobramycin",
        trigger_type="lab",
        trigger_key="creatinine",
        compare="gt",
        threshold=2.0,
        penalty=0.22,
        max_daily_dose=None,
        reason="Tobramycin increases nephrotoxicity risk when creatinine is above 2.0.",
    ),
    SafetyRule(
        drug_keyword="atorvastatin",
        trigger_type="lab",
        trigger_key="alt",
        compare="gt",
        threshold=120,
        penalty=0.16,
        max_daily_dose=None,
        reason="Atorvastatin may increase liver injury risk when ALT is above 120.",
    ),
    SafetyRule(
        drug_keyword="simvastatin",
        trigger_type="lab",
        trigger_key="alt",
        compare="gt",
        threshold=120,
        penalty=0.16,
        max_daily_dose=None,
        reason="Simvastatin may increase liver injury risk when ALT is above 120.",
    ),
    SafetyRule(
        drug_keyword="rosuvastatin",
        trigger_type="lab",
        trigger_key="alt",
        compare="gt",
        threshold=120,
        penalty=0.16,
        max_daily_dose=None,
        reason="Rosuvastatin may increase liver injury risk when ALT is above 120.",
    ),
    SafetyRule(
        drug_keyword="ibuprofen",
        trigger_type="lab",
        trigger_key="egfr",
        compare="le",
        threshold=30,
        penalty=0.24,
        max_daily_dose=None,
        reason="Ibuprofen increases nephrotoxicity risk when eGFR is 30 or below.",
    ),
    SafetyRule(
        drug_keyword="naproxen",
        trigger_type="lab",
        trigger_key="egfr",
        compare="le",
        threshold=30,
        penalty=0.24,
        max_daily_dose=None,
        reason="Naproxen increases nephrotoxicity risk when eGFR is 30 or below.",
    ),
    SafetyRule(
        drug_keyword="diclofenac",
        trigger_type="lab",
        trigger_key="egfr",
        compare="le",
        threshold=30,
        penalty=0.24,
        max_daily_dose=None,
        reason="Diclofenac increases nephrotoxicity risk when eGFR is 30 or below.",
    ),
    SafetyRule(
        drug_keyword="metformin",
        trigger_type="condition",
        trigger_key="heart failure",
        compare="contains",
        threshold=None,
        penalty=0.15,
        max_daily_dose=None,
        reason="Metformin may increase lactic acidosis risk in patients with heart failure.",
    ),
    SafetyRule(
        drug_keyword="metoprolol",
        trigger_type="condition",
        trigger_key="asthma",
        compare="contains",
        threshold=None,
        penalty=0.20,
        max_daily_dose=None,
        reason="Metoprolol may worsen bronchospasm in patients with asthma.",
    ),
    SafetyRule(
        drug_keyword="propranolol",
        trigger_type="condition",
        trigger_key="asthma",
        compare="contains",
        threshold=None,
        penalty=0.20,
        max_daily_dose=None,
        reason="Propranolol may worsen bronchospasm in patients with asthma.",
    ),
    SafetyRule(
        drug_keyword="ibuprofen",
        trigger_type="condition",
        trigger_key="gastrointestinal bleed",
        compare="contains",
        threshold=None,
        penalty=0.22,
        max_daily_dose=None,
        reason="Ibuprofen may worsen gastrointestinal bleeding risk in patients with a gastrointestinal bleed history.",
    ),
    SafetyRule(
        drug_keyword="naproxen",
        trigger_type="condition",
        trigger_key="gastrointestinal bleed",
        compare="contains",
        threshold=None,
        penalty=0.22,
        max_daily_dose=None,
        reason="Naproxen may worsen gastrointestinal bleeding risk in patients with a gastrointestinal bleed history.",
    ),
]


def normalize_medication_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_lab_keys(raw_labs: dict[str, float]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for key, value in raw_labs.items():
        normalized_key = key.lower().strip()
        canonical = LAB_KEY_ALIASES.get(normalized_key, normalized_key)
        normalized[canonical] = value
    return normalized


def parse_medication_details(value: str) -> dict[str, float | str | None]:
    normalized = normalize_medication_name(value)
    dose_match = re.search(r"(\d+(?:\.\d+)?)\s*mg", normalized)
    dose_mg = float(dose_match.group(1)) if dose_match else None

    frequency_map = {
        "three times daily": 3.0,
        "twice daily": 2.0,
        "once daily": 1.0,
        "tid": 3.0,
        "bid": 2.0,
        "daily": 1.0,
    }
    frequency = 1.0
    frequency_label = "daily"
    for label, multiplier in frequency_map.items():
        if label in normalized:
            frequency = multiplier
            frequency_label = label
            break

    medication_name = normalized.split(str(int(dose_mg)) + "mg")[0].strip() if dose_mg else normalized
    total_daily_dose = dose_mg * frequency if dose_mg else None
    return {
        "name": medication_name,
        "dose_mg": dose_mg,
        "frequency_per_day": frequency,
        "frequency_label": frequency_label,
        "total_daily_dose": total_daily_dose,
    }


def recency_score(record_date: date | None, today: date | None = None) -> float:
    if record_date is None:
        return 0.2
    comparison_date = today or date.today()
    age_days = max((comparison_date - record_date).days, 0)
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.9
    if age_days <= 90:
        return 0.75
    if age_days <= 180:
        return 0.55
    if age_days <= 365:
        return 0.35
    return 0.2


def completeness_score(*values: object) -> float:
    populated = sum(1 for value in values if value not in (None, "", [], {}))
    return populated / max(len(values), 1)


def _compare_lab_value(value: float, compare: str, threshold: float) -> bool:
    if compare == "lt":
        return value < threshold
    if compare == "le":
        return value <= threshold
    if compare == "gt":
        return value > threshold
    if compare == "ge":
        return value >= threshold
    return False


def safety_penalty(
    medication: str,
    recent_labs: dict[str, float],
    conditions: list[str],
) -> SafetyResult:
    details = parse_medication_details(medication)
    normalized_name = str(details["name"])
    total_daily_dose = details["total_daily_dose"] or 0.0
    normalized_labs = normalize_lab_keys(recent_labs)
    normalized_conditions = " ".join(condition.strip().lower() for condition in conditions if condition).strip()

    triggered_penalties: list[float] = []
    reasons: list[str] = []
    triggered_rules: list[str] = []

    for rule in SAFETY_RULES:
        if rule.drug_keyword not in normalized_name:
            continue

        triggered = False
        if rule.trigger_type == "lab":
            if rule.trigger_key not in normalized_labs or rule.threshold is None:
                continue
            lab_value = normalized_labs[rule.trigger_key]
            if not _compare_lab_value(lab_value, rule.compare, rule.threshold):
                continue
            if rule.max_daily_dose is not None and total_daily_dose <= rule.max_daily_dose:
                continue
            triggered = True
        elif rule.trigger_type == "condition":
            if rule.compare != "contains" or rule.trigger_key not in normalized_conditions:
                continue
            triggered = True

        if not triggered:
            continue

        triggered_penalties.append(rule.penalty)
        reasons.append(rule.reason)
        triggered_rules.append(f"{rule.drug_keyword}:{rule.trigger_key}")

    return SafetyResult(
        penalty=max(triggered_penalties, default=0.0),
        reasons=reasons,
        triggered_rules=triggered_rules,
    )


def classify_score(score: int) -> str:
    if score >= 80:
        return "green"
    if score >= 60:
        return "yellow"
    return "red"
