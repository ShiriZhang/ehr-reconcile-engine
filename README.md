# EHR Reconcile Engine

A clinical data reconciliation engine that resolves conflicting medication records across healthcare systems and validates EHR data quality. Built as a Full Stack Developer - EHR Integration Intern take-home assessment.

## What It Does

| Endpoint | Purpose |
|----------|---------|
| `POST /api/reconcile/medication` | Accepts conflicting medication records from multiple sources (hospital, primary care, pharmacy) along with patient context (age, conditions, labs). Returns a single reconciled medication recommendation with confidence score, clinical reasoning, recommended actions, and safety status. |
| `POST /api/validate/data-quality` | Accepts a patient record (demographics, medications, allergies, conditions, vitals). Returns quality scores across four dimensions—completeness, accuracy, timeliness, and clinical plausibility—with detected issues and severity levels. |
| `GET /health` | Unauthenticated readiness probe. |

A React dashboard lets reviewers submit payloads via editable JSON editors, inspect AI-enriched results, and approve or reject medication suggestions (local state only).

## Tech Stack

- **Backend:** Python 3.13, FastAPI, Uvicorn, Pydantic, httpx
- **Frontend:** React 18, Vite 5, JavaScript (ES modules)
- **AI:** OpenAI GPT-4.1-mini (primary), DeepSeek (fallback), deterministic rules (baseline)
- **Testing:** pytest (backend), Vitest + React Testing Library (frontend)
- **Deployment:** Docker Compose (multi-container)
- **Storage:** In-memory only (no database)

## Project Structure

```text
ehr-reconcile-engine/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point, CORS, error handlers
│   │   ├── ai/                  # LLM integration (providers, prompts, cache, service)
│   │   ├── api/                 # Routes, Pydantic request/response models, DI
│   │   ├── services/            # Deterministic reconciliation & data quality logic
│   │   └── core/                # Auth, config, safety rules, scoring, logging
│   ├── tests/                   # pytest suite (auth, rules, AI fallback, fixtures)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Dual-panel dashboard UI
│   │   ├── components/          # ResultCard, DataQualityCard, JsonEditor, StatusBadge
│   │   └── lib/                 # API client, sample payloads
│   ├── package.json
│   └── Dockerfile
├── samples/                     # Example request payloads & PyHealth fixtures
├── scripts/                     # MIMIC-III fixture generator
├── docs/
│   └── architecture.md          # Architecture decisions document
├── docker-compose.yml
├── .env.example
└── README.md
```

## How to Run Locally

### Prerequisites

- Python 3.13+
- Node.js 22+ and npm
- (Optional) Docker and Docker Compose

### 1. Environment Variables

Copy `.env.example` to `.env` in the repository root and fill in your keys:

```env
APP_ENV=development
API_KEY=dev-api-key

# At least one LLM key required for AI enrichment; app works without either (deterministic only)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat

AI_TIMEOUT_SECONDS=20
FRONTEND_API_BASE_URL=http://localhost:8000
```

The backend auto-loads `.env` from the repository root. Already-exported process environment variables take precedence.

### 2. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs at http://localhost:8000 with hot-reload enabled.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173 with HMR.

### 4. Docker Compose (alternative)

```bash
docker compose up --build
```

Builds both images and exposes the same ports (backend: 8000, frontend: 5173).

### 5. Running Tests

**Backend:**
```bash
cd backend
python -m pytest tests
```

**Frontend:**
```bash
cd frontend
npm test
```

## API Examples

```bash
# Medication reconciliation
curl -X POST http://localhost:8000/api/reconcile/medication \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev-api-key" \
  --data "@samples/medication_reconcile_sample.json"

# Data quality validation
curl -X POST http://localhost:8000/api/validate/data-quality \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev-api-key" \
  --data "@samples/data_quality_sample.json"
```

## Which LLM API and Why

**Primary: OpenAI GPT-4.1-mini** — Selected because it was the main model family requested for the project. GPT-4.1-mini provides strong structured JSON reasoning at low latency and cost, which suits the clinical enrichment use case (generating reasoning text and recommended actions, not making the final decision).

**Fallback: DeepSeek** — Provides a second compatible chat-completions API path. If OpenAI is unavailable (rate limits, outages, network errors), the system automatically retries with DeepSeek before degrading further.

**Baseline: Deterministic rules** — All business logic is computed without any LLM. The AI layer only enriches the result (reasoning, actions, safety commentary). This means:
- The app works with zero LLM keys configured
- Timeouts, malformed JSON, schema validation failures, `429`, and `5xx` responses all degrade silently to the rule-based result
- The LLM never decides which medication wins or what the confidence score is

The provider adapter uses `temperature=0.1` for medical conservatism and a system prompt framing the model as a clinical decision support tool with JSON-only output expectations.

## Key Design Decisions and Trade-offs

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Rule-based baseline first, AI enrichment second** | Resilience and testability. The system always produces a valid result even without LLM access. Safety-critical scoring is deterministic and auditable. | More code to maintain for scoring logic; AI is limited to enriching reasoning/actions rather than driving decisions. |
| **Graceful degradation for all AI failures** | Clinical decision support cannot silently fail. Eight failure modes are handled (timeout, network, 429, 5xx, 4xx, invalid JSON, unexpected shape, validation mismatch). | AI enrichment is best-effort; users may not realize they are seeing deterministic-only output. |
| **In-memory SHA-256 keyed cache** | Avoids redundant LLM calls for identical prompts, reducing cost and latency with zero infrastructure. | Cache is not shared across processes and is lost on restart. |
| **No database** | Simplifies deployment for the assessment scope. Backend is stateless (aside from ephemeral AI cache). | Approve/reject decisions exist only in browser state; no audit trail. |
| **Editable JSON editors instead of forms** | Aligns with assessment examples, reduces UI overhead, and makes it easy to test arbitrary payloads. | Less user-friendly for non-technical reviewers. |
| **Table-driven safety rules** | 20+ medication-lab and drug-condition rules are defined as data tables, making it easy to add rules without code changes. | Rules must be manually curated; no automatic drug interaction database integration. |
| **Simple API key auth** | Sufficient for the assessment scope; implemented as a FastAPI dependency (`x-api-key` header). | Not suitable for production multi-tenant use. |
| **Pydantic validation on both request and AI response** | Catches malformed input early and ensures AI responses conform to the expected schema before returning to the client. | Strict validation may reject creative but useful AI responses. |

## PyHealth Test Data Integration

The repository includes a script to generate test fixtures from Synthetic MIMIC-III data via PyHealth:

```bash
pip install -r scripts/requirements-scripts.txt
python scripts/generate_pyhealth_fixtures.py
```

Pre-generated fixtures are committed under `samples/pyhealth/` so the test suite runs without PyHealth installed or public dataset access. Backend validation for these fixtures lives in `backend/tests/test_pyhealth_fixtures.py`.

## What I Would Improve With More Time

- **Persistent audit trail** — Store approve/reject decisions and reconciliation history in a database for compliance and review.
- **Expanded duplicate detection** — Group duplicate medication records explicitly for clinician review rather than applying a flat boost.
- **Broader clinical rules** — Integrate a drug interaction database (e.g., RxNorm, openFDA) instead of hand-curated rule tables.
- **User authentication** — Replace the single shared API key with role-based access (clinician, pharmacist, admin).
- **Streaming AI responses** — Use SSE or WebSocket streaming for the LLM enrichment step so the user sees reasoning as it generates.
- **Observability** — Add structured logging, request tracing, and a metrics endpoint for production monitoring.
- **Deployment** — Deploy to a cloud environment.

## Estimated Time Spent

| Phase | Hours |
|-------|-------|
| Architecture and scaffolding | 3.0 |
| Backend logic and tests | 8.0 |
| Frontend dashboard | 3.5 |
| Docs and packaging | 3.5 |
| Runtime hardening and live verification | 5.5 |
| **Total** | **23.5** |
