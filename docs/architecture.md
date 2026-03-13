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
