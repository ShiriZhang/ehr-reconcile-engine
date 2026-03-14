# Architecture Decisions

## Overview
- Backend: FastAPI service with two assessment-constrained business endpoints.
- Frontend: React + Vite dashboard focused on clinician clarity over workflow complexity.
- AI layer: OpenAI primary provider, DeepSeek fallback, in-memory cache, and rule-based safe fallback.
- Storage: in-memory only for v1. No database required for the take-home scope.

## Backend Design
- `app/api`: HTTP routes, request/response models, dependency wiring.
- `app/services`: deterministic core logic for medication reconciliation and data quality scoring.
- `app/ai`: prompt construction, provider adapters, caching, and graceful fallback behavior.
- `app/core`: auth, config, logging, error formatting, scoring helpers, and clinical heuristics.

## Reconciliation Logic
- Base selection combines source reliability, recency, and record completeness.
- Safety-aware scoring penalizes higher-risk regimens when patient context suggests caution, such as reduced eGFR with metformin.
- Confidence score is calibrated from three factors:
  - winning candidate strength
  - margin over the runner-up
  - cross-source agreement ratio
- Duplicate bias is handled implicitly by slightly boosting exact repeated regimens across sources.

## Data Quality Logic
- Scores are broken into `completeness`, `accuracy`, `timeliness`, and `clinical_plausibility`.
- Implausible vitals, outdated records, and missing core documentation generate structured issues with severity.
- The rule engine is deterministic so the API remains usable even when the LLM layer is unavailable.

## Prompt Engineering Approach
- Prompts include the raw request payload plus the rule-based draft output.
- The model is instructed to return strict JSON only, reducing parsing ambiguity.
- AI is responsible for:
  - concise clinical reasoning
  - recommended actions
  - human-readable explanation of data quality concerns
- AI is not trusted for baseline correctness. Deterministic logic produces the first answer, and the model only enriches it.

## Reliability Guardrails
- Missing API keys, rate limits, malformed LLM output, or provider failures do not break endpoint responses.
- OpenAI is attempted first; DeepSeek is attempted second; rule-based output is returned last.
- Repeated identical prompts are cached in memory to reduce cost and improve responsiveness.

## Frontend Design
- JSON-first input keeps the UI simple while matching assessment payload examples.
- Result cards prioritize confidence, safety status, issues, and actions.
- Approve/reject is kept client-side in v1 to avoid inventing extra backend endpoints outside the assessment scope.

## PyHealth Test Data Integration
- `scripts/generate_pyhealth_fixtures.py` is the standalone export path for Synthetic MIMIC-III based request fixtures.
- The script attempts to load Synthetic MIMIC-III with PyHealth, reads patient events through the Patient event API, and groups prescription events by `hadm_id` so each admission becomes one reconciliation source.
- `pyhealth.medcode.InnerMap` is used to resolve `NDC` medication codes and `ICD9CM` diagnosis codes into human-readable labels, with raw-code fallback when a lookup misses.
- Exported reconciliation fixtures are written to `samples/pyhealth/reconcile_*.json`; exported quality fixtures are written to `samples/pyhealth/quality_*.json`.
- The quality fixtures intentionally keep `allergies` empty so the backend completeness rules continue to exercise the missing-allergies path, and one fixture includes implausible vital signs.
- The script patches PyHealth URL normalization on Windows so `https://storage.googleapis.com/pyhealth/Synthetic_MIMIC-III/` remains a valid URL instead of being rewritten with backslashes.
- Committed fixtures in `samples/pyhealth/` still serve as the offline test corpus and are validated by `backend/tests/test_pyhealth_fixtures.py`.
