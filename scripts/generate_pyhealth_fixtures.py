from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "samples" / "pyhealth"
MIMIC_ROOT = "https://storage.googleapis.com/pyhealth/Synthetic_MIMIC-III/"
MAX_FIXTURES = 5


def clean_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return None if not text or text.lower() in {"nan", "none", "null"} else text


def to_iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = clean_text(value)
    return text[:10] if text else None


def latest_timestamp(events: list[Any]) -> datetime | None:
    return max((event.timestamp for event in events if getattr(event, "timestamp", None) is not None), default=None)


def safe_lookup(inner_map: Any, code: Any) -> str | None:
    normalized = clean_text(code)
    if not normalized:
        return None
    try:
        return clean_text(inner_map.lookup(normalized.replace(".", "")))
    except Exception:
        return None


def resolve_medication(event: Any, ndc_map: Any) -> str | None:
    name = (
        safe_lookup(ndc_map, getattr(event, "ndc", None))
        or clean_text(getattr(event, "drug_name_generic", None))
        or clean_text(getattr(event, "drug_name_poe", None))
        or clean_text(getattr(event, "drug", None))
        or clean_text(getattr(event, "ndc", None))
    )
    if not name:
        return None
    strength = clean_text(getattr(event, "prod_strength", None))
    if not strength:
        dose = clean_text(getattr(event, "dose_val_rx", None))
        unit = clean_text(getattr(event, "dose_unit_rx", None))
        strength = " ".join(part for part in [dose, unit] if part) or None
    route = clean_text(getattr(event, "route", None))
    parts = [name]
    if strength and strength.lower() not in name.lower():
        parts.append(strength)
    if route:
        parts.append(f"via {route}")
    return " ".join(parts)


def resolve_condition(event: Any, icd9_map: Any) -> str | None:
    return safe_lookup(icd9_map, getattr(event, "icd9_code", None)) or clean_text(getattr(event, "icd9_code", None))


def calculate_age(patient_event: Any, reference_date: datetime | None) -> int | None:
    dob = to_iso_date(getattr(patient_event, "dob", None) if patient_event else None)
    if not dob:
        return None
    try:
        born = datetime.fromisoformat(dob)
        today = date.today()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    except ValueError:
        return None
    return max(0, min(age, 120))


def collect_unique(items: list[Any]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen


def build_reconcile_fixture(patient: Any, diagnoses: list[Any], prescriptions: list[Any], ndc_map: Any, icd9_map: Any) -> dict[str, Any] | None:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for event in prescriptions:
        hadm_id = clean_text(getattr(event, "hadm_id", None))
        if hadm_id:
            grouped[hadm_id].append(event)
    visits = []
    for hadm_id, events in grouped.items():
        medication = resolve_medication(max(events, key=lambda item: item.timestamp), ndc_map)
        if medication:
            visits.append((hadm_id, medication, latest_timestamp(events)))
    if len(visits) < 2 or len({visit[1] for visit in visits}) < 2:
        return None
    visits.sort(key=lambda item: item[2] or datetime.min, reverse=True)
    patient_event = next(iter(patient.get_events("patients")), None)
    conditions = collect_unique([resolve_condition(event, icd9_map) for event in diagnoses])[:5]
    return {
        "patient_context": {
            "age": calculate_age(patient_event, visits[0][2]),
            "conditions": conditions,
            "recent_labs": {},
        },
        "sources": [
            {
                "system": f"Synthetic MIMIC Visit {hadm_id}",
                "medication": medication,
                "last_updated": to_iso_date(timestamp),
                "source_reliability": "high" if index == 0 else "medium",
            }
            for index, (hadm_id, medication, timestamp) in enumerate(visits)
        ],
    }


def build_quality_fixture(patient: Any, diagnoses: list[Any], prescriptions: list[Any], ndc_map: Any, icd9_map: Any, implausible: bool) -> dict[str, Any] | None:
    patient_event = next(iter(patient.get_events("patients")), None)
    medications = collect_unique([resolve_medication(event, ndc_map) for event in prescriptions])[:5]
    conditions = collect_unique([resolve_condition(event, icd9_map) for event in diagnoses])[:5]
    last_updated = to_iso_date(latest_timestamp(prescriptions) or latest_timestamp(diagnoses))
    if not medications or not last_updated:
        return None
    return {
        "demographics": {
            "name": f"Synthetic MIMIC Patient {patient.patient_id}",
            "dob": to_iso_date(getattr(patient_event, "dob", None) if patient_event else None) or "1950-01-01",
            "gender": clean_text(getattr(patient_event, "gender", None) if patient_event else None) or "U",
        },
        "medications": medications,
        "allergies": [],
        "conditions": conditions,
        "vital_signs": {
            "blood_pressure": "340/180" if implausible else "128/78",
            "heart_rate": 88 if implausible else 72,
        },
        "last_updated": last_updated,
    }


def write_fixtures(prefix: str, payloads: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for index, payload in enumerate(payloads, start=1):
        path = OUTPUT_DIR / f"{prefix}_{index:02d}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def patch_pyhealth_url_handling() -> None:
    # PyHealth uses os.path.normpath for URLs, which produces backslashes on Windows.
    if os.name != "nt":
        return

    try:
        import pyhealth.datasets.base_dataset as base_dataset
    except Exception:
        return

    def patched_clean_path(path: str) -> str:
        parsed = urlparse(path)
        if parsed.scheme and parsed.netloc:
            parts = [part for part in parsed.path.split("/") if part]
            normalized = "/" + "/".join(parts)
            return urlunparse(parsed._replace(path=normalized))
        return str(Path(path).expanduser().resolve())

    base_dataset.clean_path = patched_clean_path


def main() -> int:
    patch_pyhealth_url_handling()
    try:
        from pyhealth.datasets import MIMIC3Dataset
        from pyhealth.medcode import InnerMap
    except Exception as exc:
        print(f"PyHealth import failed: {exc}. Existing exported fixtures remain unchanged.")
        return 0

    try:
        dataset = MIMIC3Dataset(root=MIMIC_ROOT, tables=["DIAGNOSES_ICD", "PRESCRIPTIONS"])
        ndc_map = InnerMap.load("NDC")
        icd9_map = InnerMap.load("ICD9CM")
    except Exception as exc:
        print(f"PyHealth initialization failed: {exc}. Existing exported fixtures remain unchanged.")
        return 0

    reconcile_payloads: list[dict[str, Any]] = []
    quality_payloads: list[dict[str, Any]] = []
    try:
        for patient in dataset.iter_patients():
            diagnoses = patient.get_events("diagnoses_icd")
            prescriptions = patient.get_events("prescriptions")
            if len(reconcile_payloads) < MAX_FIXTURES:
                payload = build_reconcile_fixture(patient, diagnoses, prescriptions, ndc_map, icd9_map)
                if payload:
                    reconcile_payloads.append(payload)
            if len(quality_payloads) < MAX_FIXTURES:
                payload = build_quality_fixture(
                    patient,
                    diagnoses,
                    prescriptions,
                    ndc_map,
                    icd9_map,
                    implausible=len(quality_payloads) == 0,
                )
                if payload:
                    quality_payloads.append(payload)
            if len(reconcile_payloads) >= 3 and len(quality_payloads) >= 3 and len(reconcile_payloads) >= MAX_FIXTURES:
                break
    except Exception as exc:
        print(f"PyHealth iteration failed: {exc}. Existing exported fixtures remain unchanged.")
        return 0

    write_fixtures("reconcile", reconcile_payloads[:MAX_FIXTURES])
    write_fixtures("quality", quality_payloads[:MAX_FIXTURES])
    print(f"Generated {len(reconcile_payloads[:MAX_FIXTURES])} reconciliation fixtures and {len(quality_payloads[:MAX_FIXTURES])} quality fixtures in {OUTPUT_DIR}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
