from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


Reliability = Literal["high", "medium", "low"]
SafetyStatus = Literal["PASSED", "WARNING", "FAILED"]
Severity = Literal["low", "medium", "high"]


class PatientContext(BaseModel):
    age: int | None = Field(default=None, ge=0, le=120)
    conditions: list[str] = Field(default_factory=list)
    recent_labs: dict[str, float] = Field(default_factory=dict)


class MedicationSourceRecord(BaseModel):
    system: str = Field(min_length=1)
    medication: str = Field(min_length=1)
    last_updated: date | None = None
    last_filled: date | None = None
    source_reliability: Reliability = "medium"

    @property
    def reference_date(self) -> date | None:
        return self.last_updated or self.last_filled

    @model_validator(mode="after")
    def ensure_reference_date(self) -> "MedicationSourceRecord":
        if self.last_updated is None and self.last_filled is None:
            raise ValueError("Each source must include last_updated or last_filled.")
        return self


class MedicationReconcileRequest(BaseModel):
    patient_context: PatientContext = Field(default_factory=PatientContext)
    sources: list[MedicationSourceRecord] = Field(min_length=1)


class ReconciliationResult(BaseModel):
    reconciled_medication: str
    confidence_score: float = Field(ge=0, le=1)
    reasoning: str
    recommended_actions: list[str]
    clinical_safety_check: SafetyStatus


class Demographics(BaseModel):
    name: str | None = None
    dob: date | None = None
    gender: str | None = None


class DataQualityRequest(BaseModel):
    demographics: Demographics
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    vital_signs: dict[str, Any] = Field(default_factory=dict)
    last_updated: date


class IssueDetected(BaseModel):
    field: str
    issue: str
    severity: Severity


class DataQualityResult(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    breakdown: dict[str, int]
    issues_detected: list[IssueDetected]
