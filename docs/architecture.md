# Architecture Decisions

## Current Overview
- Backend: FastAPI app with two authenticated business endpoints and one unauthenticated health check.
- Frontend: React + Vite single-page dashboard with JSON editors for both workflows.
- AI layer: deterministic rule-based baseline first, then optional LLM enrichment through OpenAI with DeepSeek fallback.
- Storage: no database. Backend state is limited to an in-memory AI response cache, and frontend review state stays in the browser.

## Runtime Shape
- `backend/app/main.py` wires logging, CORS, error handlers, and the route modules.
- `backend/app/api` owns request and response models, route handlers, and dependency injection.
- `backend/app/services` contains the deterministic scoring and rule orchestration.
- `backend/app/core` contains auth, env/config loading, scoring helpers, medication safety rules, data-quality rules, logging, and error formatting.
- `backend/app/ai` contains prompt builders, provider adapters, and the in-memory cache.
- `frontend/src/App.jsx` renders two independent work areas: medication reconciliation and data-quality validation.

## Request Flow
1. The frontend posts JSON to the backend with `x-api-key`.
2. FastAPI validates the API key and request payload.
3. A deterministic service computes the baseline result.
4. `AIService` builds a prompt, checks the in-memory cache, then tries OpenAI first and DeepSeek second.
5. If AI enrichment succeeds and validates against the Pydantic response model, the enriched result is returned. Otherwise the deterministic result is returned unchanged.

This means AI is never the source of truth for endpoint availability. Missing provider keys, network failures, timeouts, malformed JSON, schema mismatches, `429`, and `5xx` responses all degrade to the rule-based result.

## API Surface
- `GET /health`: returns `{"status": "ok", "app": settings.app_name}` and does not require an API key.
- `POST /api/reconcile/medication`: accepts `patient_context` plus one or more medication source records.
- `POST /api/validate/data-quality`: accepts demographics, medications, allergies, conditions, vital signs, and `last_updated`.

Both business endpoints require the `x-api-key` header. Validation failures return a structured `422` body with `error`, `message`, and `details`. Explicit `ValueError` failures are converted into `400` responses.

## Medication Reconciliation
The medication reconciliation request model is intentionally small:
- `patient_context.age`
- `patient_context.conditions`
- `patient_context.recent_labs`
- `sources[]`, where each source must include `system`, `medication`, `source_reliability`, and at least one of `last_updated` or `last_filled`

Deterministic source ranking is computed per record from:
- source reliability weight at 50%
- recency score at 35%
- completeness score at 15%
- minus the maximum triggered safety penalty
- plus a `0.08` duplicate boost when multiple sources report the same normalized medication string

Safety penalties are currently rule-driven, not model-driven. The implemented rules cover:
- metformin vs `eGFR` thresholds and heart failure
- warfarin vs high `INR`
- digoxin vs low potassium
- lisinopril, enalapril, and ramipril vs high potassium
- gentamicin and tobramycin vs high creatinine
- atorvastatin, simvastatin, and rosuvastatin vs high `ALT`
- ibuprofen, naproxen, and diclofenac vs low `eGFR`
- ibuprofen and naproxen vs gastrointestinal bleed history
- metoprolol and propranolol vs asthma

Confidence is calibrated from the winning source score, the margin over the runner-up, and cross-source agreement. The deterministic response returns:
- `reconciled_medication`
- `confidence_score`
- `reasoning`
- `recommended_actions`
- `clinical_safety_check`

Important current behavior:
- the deterministic path chooses the medication and confidence score
- AI enrichment may only replace `reasoning`, `recommended_actions`, and `clinical_safety_check`
- the schema allows `PASSED`, `WARNING`, or `FAILED`, but the deterministic service currently emits `PASSED` or `WARNING` only

## Data Quality Validation
The data-quality endpoint produces four deterministic dimension scores:
- `completeness`
- `accuracy`
- `timeliness`
- `clinical_plausibility`

`overall_score` is the rounded arithmetic mean of those four dimensions.

The current rule sets are:
- completeness checks for missing name, DOB, gender, medications, allergies, conditions, and vital signs
- accuracy checks for future DOB, non-standard gender values, and future `last_updated`
- timeliness buckets based on how old `last_updated` is
- clinical plausibility rules for vital sign parsing and range checking, plus medication-condition mismatches

The vital-sign rule engine is table-driven through `VITAL_RULES`, and the medication-condition cross-checks are table-driven through `MEDICATION_CONDITION_RULES`. Unknown vital fields are ignored. Blank values are ignored. Invalid formats and implausible ranges produce structured issues with severity.

Current medication-condition rules are intentionally narrow:
- metformin without a documented diabetes-related condition
- insulin without a documented diabetes-related condition

Important current behavior:
- the deterministic path computes the initial `breakdown`, `issues_detected`, and `overall_score`
- AI enrichment may replace `breakdown` and `issues_detected`
- `overall_score` is always recomputed on the server from the final `breakdown`

## AI Prompting And Providers
Prompt construction is explicit and endpoint-specific:
- reconciliation prompts cast the model as a clinical pharmacist and ask it to reason about reliability, recency, clinical safety, and cross-source agreement
- data-quality prompts cast the model as a clinical data quality analyst and ask it to score completeness, accuracy, timeliness, and plausibility

Each prompt includes:
- role framing
- a reasoning checklist aligned with the deterministic rules
- a strict JSON output contract
- the full request payload plus the rule-based draft result

The provider adapter uses chat-completions style APIs with:
- `temperature = 0.1`
- a medical conservatism system message
- JSON-only expectations with code-fence normalization if a provider still wraps the response

The backend currently builds providers in this order:
1. OpenAI via `https://api.openai.com/v1/chat/completions`
2. DeepSeek via `https://api.deepseek.com/chat/completions`

## Cache, Config, And Operational Guardrails
- `AIService` is exposed through an `lru_cache(maxsize=1)` dependency, so one service instance is reused per process.
- `MemoryCache` stores prompt results in memory and keys them by SHA-256 of the serialized prompt payload.
- `.env` is auto-loaded from the repository root, but existing process environment variables take precedence.
- Current configurable values include `API_KEY`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `AI_TIMEOUT_SECONDS`, and `FRONTEND_API_BASE_URL`.
- CORS allows `http://localhost:5173` plus the configured `FRONTEND_API_BASE_URL` value.
- Logging is basic process-wide structured text logging through `logging.basicConfig`.

## Frontend Behavior
The frontend is intentionally thin:
- both workflows use editable JSON textareas instead of large forms
- initial payloads come from `frontend/src/lib/samples.js`
- requests are sent through `frontend/src/lib/api.js`, which reads `VITE_API_BASE_URL` and `VITE_API_KEY`
- the medication result card displays medication, confidence, safety status, reasoning, and recommended actions
- approve and reject are local UI state only and are not persisted to the backend
- the data-quality card displays the overall score, per-dimension bars, and the detected issue list

## Testing And Fixtures
The current automated coverage matches the implemented architecture:
- backend tests cover auth, config loading, reconciliation scoring, safety rules, data-quality rules, provider error handling, AI fallback, and PyHealth fixtures
- frontend tests cover medication submission and the local approve action

PyHealth fixture generation is still part of the repository:
- `scripts/generate_pyhealth_fixtures.py` attempts to load Synthetic MIMIC-III through PyHealth
- reconciliation fixtures are built by grouping prescription events by `hadm_id`
- quality fixtures intentionally keep `allergies` empty so completeness rules continue to fire
- one quality fixture is exported with implausible blood pressure to exercise plausibility logic
- committed fixtures under `samples/pyhealth/` are used as the offline regression corpus
