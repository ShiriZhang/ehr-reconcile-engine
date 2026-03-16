# Architecture Decisions

This document explains the architectural choices behind the EHR Reconcile Engine—why certain approaches were chosen, what alternatives were considered, and what trade-offs were accepted.

## High-Level Architecture

The system follows a **layered hybrid architecture** with five distinct layers:

```
┌─────────────────────────────────────────────┐
│  Frontend (React + Vite SPA)                │
│  JSON editors, result cards, local state    │
├─────────────────────────────────────────────┤
│  API Layer (FastAPI routes + Pydantic)       │
│  Auth, validation, dependency injection     │
├─────────────────────────────────────────────┤
│  Service Layer (deterministic logic)        │
│  Reconciliation scoring, quality scoring    │
├─────────────────────────────────────────────┤
│  AI Layer (optional LLM enrichment)         │
│  OpenAI → DeepSeek → deterministic fallback │
├─────────────────────────────────────────────┤
│  Core Layer (rules, config, scoring)        │
│  Safety rules, vital rules, calibration     │
└─────────────────────────────────────────────┘
```

**Why layered?** Each layer has a single responsibility and can be tested, replaced, or disabled independently. The AI layer is entirely optional—removing it does not break any endpoint.

## Request Flow

1. The frontend posts JSON to the backend with an `x-api-key` header.
2. FastAPI validates the API key via dependency injection and validates the request body against Pydantic models.
3. The deterministic service layer computes a complete baseline result using rule engines and scoring formulas.
4. `AIService` builds an endpoint-specific prompt (including the deterministic draft), checks the in-memory cache, then tries OpenAI first and DeepSeek second.
5. If AI enrichment succeeds and the response validates against the Pydantic response model, the enriched result is returned. Otherwise the deterministic result is returned unchanged.

This means AI is never the source of truth for endpoint availability. Missing provider keys, network failures, timeouts, malformed JSON, schema mismatches, `429`, and `5xx` responses all degrade silently to the rule-based result.

## Why Rule-Based Baseline First

**Decision:** Compute all business logic deterministically before invoking any LLM.

**Alternatives considered:**
- *LLM-only approach:* Let the model handle all reasoning and scoring. Rejected because it makes the system untestable, non-reproducible, and unavailable when the provider is down.
- *LLM-first with rule fallback:* Try the model first, fall back to rules on failure. Rejected because it adds latency to the happy path and makes the LLM the primary decision-maker for safety-critical scoring.

**Why this approach:** The deterministic baseline ensures the system is always available, fully testable with unit tests, and produces reproducible results. The LLM enriches human-readable fields (reasoning text, recommended actions, safety commentary) but never overrides the medication choice or confidence score. This separation means a model hallucination cannot change a clinical recommendation.

## Why OpenAI GPT-4.1-mini as the Primary LLM

**Decision:** Use OpenAI's GPT-4.1-mini via the chat-completions API.

**Why:**
- Requested model family for the assessment.
- Strong structured JSON output at low latency and cost.
- `temperature=0.1` keeps responses conservative and consistent—important for clinical text.
- The chat-completions API is a widely supported interface, making it easy to swap providers.

**Why DeepSeek as fallback:** It exposes a compatible chat-completions API, so the same `ChatProvider` adapter works with no code changes. If OpenAI hits rate limits or has an outage, the system retries with DeepSeek before degrading to deterministic-only output.

## Why Table-Driven Safety Rules

**Decision:** Implement medication safety checks as declarative data tables rather than procedural code.

**Implemented rule categories:**
- **Lab-based penalties** (8 rules): Metformin vs. eGFR, Warfarin vs. INR, Digoxin vs. Potassium, ACE inhibitors vs. Potassium, Aminoglycosides vs. Creatinine, Statins vs. ALT, NSAIDs vs. eGFR
- **Condition-based penalties** (3 rules): Metformin vs. Heart Failure, Beta-blockers vs. Asthma, NSAIDs vs. GI bleed history
- **Vital sign rules** (2 rules): Blood pressure parsing + systolic/diastolic range validation, heart rate range validation
- **Medication-condition cross-checks** (2 rules): Metformin/Insulin without documented diabetes

**Why tables over procedural code:** Adding a new safety rule means adding a row to a list, not writing new conditional logic. The rule engine iterates the table and applies matching penalties automatically. This reduces the chance of bugs and makes the rule set reviewable by non-engineers.

**Trade-off:** The rules are hand-curated. A production system would integrate a drug interaction database (RxNorm, openFDA) for broader coverage.

## Medication Reconciliation Scoring

The deterministic scoring formula balances three factors:

```
base_score = (reliability_weight * 0.5) + (recency_score * 0.35) + (completeness_score * 0.15)
final_score = clamp(base_score - max_safety_penalty + duplicate_boost, 0.0, 1.0)
```

- **Source reliability** (50%): high=1.0, medium=0.75, low=0.55. The most heavily weighted factor because source trustworthiness is the strongest signal.
- **Recency** (35%): More recent records are more likely to reflect current therapy.
- **Completeness** (15%): Records with more fields filled in are slightly preferred.
- **Safety penalty**: The maximum triggered penalty from the rule engine is subtracted. Using the max (not the sum) avoids over-penalizing medications that trigger multiple related rules.
- **Duplicate boost** (+0.08): When multiple sources report the same normalized medication, agreement increases confidence.

Confidence calibration anchors at 0.45 minimum to reflect inherent uncertainty in cross-system reconciliation:

```
calibrated = 0.45 + (base_score * 0.3) + (margin * 0.15) + (agreement_ratio * 0.1)
```

**Why these weights?** They were tuned against the sample payloads and PyHealth fixtures to produce confidence scores in a clinically intuitive range (0.5–0.85 for typical cases, lower for safety-flagged medications).

## Data Quality Scoring

Four dimensions, each scored 0–100, with `overall_score` as their arithmetic mean:

| Dimension | What it measures | Key rules |
|-----------|-----------------|-----------|
| Completeness | Missing required fields | -10 to -15 per missing field (name, DOB, gender, medications, allergies, conditions, vitals) |
| Accuracy | Data entry errors | Future DOB (-30), non-standard gender (-15), future last_updated (-25) |
| Timeliness | Record staleness | Scored by age: ≤30d=100, ≤90d=85, ≤180d=70, ≤365d=55, >365d=40 |
| Clinical plausibility | Medical consistency | Vital sign range checks, medication-condition mismatches |

**Why four dimensions?** They map to standard data quality frameworks used in healthcare informatics (completeness, accuracy, timeliness, consistency/plausibility), making the output interpretable by clinical data analysts.

## Why In-Memory Cache (No Database)

**Decision:** Cache AI responses in a Python dictionary keyed by SHA-256 of the serialized prompt.

**Why no database:**
- The assessment scope does not require persistence.
- The backend is stateless by design—every request can be served independently.
- The cache exists purely to avoid redundant LLM calls for identical inputs.

**Trade-offs accepted:**
- Cache is lost on process restart.
- Cache is not shared across multiple backend instances.
- Approve/reject decisions exist only in browser local state with no audit trail.

A production version would add a database for decision persistence and a shared cache (Redis) for multi-instance deployments.

## Why Editable JSON Instead of Forms

**Decision:** The frontend uses JSON textarea editors for both workflows rather than structured form inputs.

**Why:**
- Aligns with the assessment's example payloads—reviewers can paste samples directly.
- Reduces frontend code surface significantly (no form state management, field validation UI, or dynamic field rendering).
- Allows testing arbitrary payloads without UI changes.

**Trade-off:** Less user-friendly for non-technical users. A production version would add a form-based input mode alongside the JSON editor.

## Why Simple API Key Authentication

**Decision:** A single shared API key validated via `x-api-key` header, implemented as a FastAPI dependency.

**Why:** Sufficient for the assessment scope. The health endpoint is deliberately unauthenticated for readiness probes.

**What production would need:** JWT-based authentication, role-based access control (clinician, pharmacist, admin), and per-user audit logging.

## AI Prompt Design

Each endpoint has a dedicated prompt template that includes:
- **Role framing**: The model is cast as a domain expert (clinical pharmacist for reconciliation, clinical data quality analyst for validation).
- **Reasoning checklist**: Guides the model through the same factors the deterministic rules evaluate, ensuring consistency.
- **Strict JSON output contract**: Specifies exact keys and allowed values, reducing parsing failures.
- **Full context**: Both the original request payload and the deterministic draft result are included, so the model can refine rather than regenerate.

**Why include the deterministic draft?** It anchors the model's response and reduces hallucination. The model improves reasoning text and suggests actions, but it works from a correct baseline rather than reasoning from scratch.

## Graceful Degradation Strategy

The AI layer handles eight distinct failure modes:

| Failure | Handling |
|---------|----------|
| Missing API key | Provider not constructed; skip to next or deterministic |
| Network error | Catch `httpx` exception; log warning; try next provider |
| Timeout | Configurable via `AI_TIMEOUT_SECONDS` (default 20s); try next provider |
| HTTP 429 (rate limit) | Log warning; try next provider |
| HTTP 5xx (server error) | Log warning; try next provider |
| HTTP 4xx (client error) | Log warning; try next provider |
| Invalid JSON response | Catch parse error; try next provider |
| Schema validation failure | Pydantic rejects response; return deterministic result |

**Fallback chain:** OpenAI → DeepSeek → deterministic baseline. Each step is independent—a failure in one provider does not affect the next.

## Testing Strategy

Tests are organized to match the architecture layers:

- **Auth tests**: API key validation (valid, missing, wrong key)
- **Config tests**: Environment variable loading and defaults
- **Reconciliation tests**: Deterministic scoring with known inputs
- **Safety rule tests**: Each medication-lab and medication-condition rule in isolation
- **Data quality tests**: Each dimension scorer with edge cases
- **AI provider tests**: Error handling for each failure mode
- **AI fallback tests**: Full fallback chain behavior
- **PyHealth fixture tests**: Regression tests against MIMIC-III derived data
- **Frontend tests**: Component rendering and submission flow

**Why no LLM integration tests?** LLM responses are non-deterministic. The test suite validates the deterministic logic and the error-handling wrapper around the AI layer, not the model's output quality.

## Runtime Shape

| Component | File | Responsibility |
|-----------|------|---------------|
| Entry point | `backend/app/main.py` | Wires logging, CORS, error handlers, route modules |
| Routes & models | `backend/app/api/` | Request/response schemas, route handlers, dependency injection |
| Business logic | `backend/app/services/` | Deterministic scoring and rule orchestration |
| Infrastructure | `backend/app/core/` | Auth, config, safety rules, data quality rules, scoring helpers, logging, error formatting |
| AI integration | `backend/app/ai/` | Prompt builders, provider adapters, response cache, orchestration service |
| Dashboard | `frontend/src/App.jsx` | Dual-panel UI for reconciliation and data quality workflows |
| API client | `frontend/src/lib/api.js` | Fetch wrapper with `x-api-key` header, reads `VITE_API_BASE_URL` |
