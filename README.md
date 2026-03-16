# EHR Reconcile Engine

Clinical Data Reconciliation Engine built for the Full Stack Developer - EHR Integration Intern take-home assessment.

## Stack
- Backend: FastAPI
- Frontend: React + Vite
- AI: OpenAI primary, DeepSeek fallback
- Storage: in-memory

## What It Does
- `POST /api/reconcile/medication`: reconcile conflicting medication records and return the most likely truth with confidence, reasoning, actions, and safety status.
- `POST /api/validate/data-quality`: score patient record quality across completeness, accuracy, timeliness, and clinical plausibility.
- Dashboard: lets a reviewer submit both payload types, inspect results, and approve or reject the medication suggestion.

## Project Structure
```text
ehr-reconcile-engine/
├─ backend/
├─ frontend/
├─ docs/
├─ samples/
├─ PROJECT_TRACKER.md
└─ docker-compose.yml
```

## Local Setup
### 1. Environment
Copy `.env.example` to `.env` and fill in keys as needed. The backend auto-loads the repository-root `.env` during local startup, while already-exported process environment variables still take precedence.

```env
API_KEY=dev-api-key
OPENAI_API_KEY=
DEEPSEEK_API_KEY=
```

### 2. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs at [http://localhost:8000](http://localhost:8000).

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend runs at [http://localhost:5173](http://localhost:5173).

## Docker
```bash
docker compose up --build
```

## API Examples
### Medication Reconciliation
```bash
curl -X POST http://localhost:8000/api/reconcile/medication \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev-api-key" \
  --data "@samples/medication_reconcile_sample.json"
```

### Data Quality Validation
```bash
curl -X POST http://localhost:8000/api/validate/data-quality \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev-api-key" \
  --data "@samples/data_quality_sample.json"
```

## Testing
Backend:
```bash
cd backend
python -m pytest tests
```

Frontend:
```bash
cd frontend
npm test
```

## LLM Choice And Why
- OpenAI is the primary provider because it is the main model family requested for the project and is used for concise structured reasoning.
- DeepSeek is the backup provider because it offers a second compatible chat-completions path if the primary provider fails.
- Deterministic rule-based logic remains the baseline so the app still works without any provider response.

## Design Decisions And Trade-Offs
- The backend always computes a rule-based result first. This makes the system resilient and testable.
- The frontend uses editable JSON instead of a large custom form to stay aligned with the assessment examples and reduce UI overhead.
- Approval/rejection is local state only in v1 so the backend does not exceed the assessment's endpoint constraint.
- In-memory caching keeps the implementation simple and cost-aware, but it is not shared across instances.
- AI responses are schema-validated before being returned. Network errors, timeouts, malformed JSON, `429`, and `5xx` responses degrade cleanly to deterministic output.

## Verification Notes
- 2026-03-12: the sample medication and data-quality payloads were verified end to end against the configured OpenAI and DeepSeek providers.
- Both providers returned valid JSON for their respective prompts and preserved the expected response schema.
- Observed local response times in that run were about 5.5-5.8 seconds for OpenAI and 7.1-7.8 seconds for DeepSeek.
- A forced-timeout check confirmed that provider timeouts still return HTTP 200 with rule-based fallback content.

## PyHealth Test Data Integration
- `scripts/generate_pyhealth_fixtures.py` attempts to load Synthetic MIMIC-III through PyHealth and export request fixtures into `samples/pyhealth/`.
- The export logic maps `NDC` and `ICD9CM` codes with `pyhealth.medcode.InnerMap`, then converts patient events into the existing API request shapes used by the backend.
- Committed fixtures live in `samples/pyhealth/` so the test suite works without PyHealth installed or public dataset access.
- The script includes a Windows-specific URL normalization workaround for PyHealth so the public Synthetic MIMIC-III root can be used from PowerShell environments that would otherwise produce backslash-corrupted URLs.
- Backend validation for these fixtures lives in `backend/tests/test_pyhealth_fixtures.py`.

Regenerate the fixtures:

```bash
pip install -r scripts/requirements-scripts.txt
python scripts/generate_pyhealth_fixtures.py
```

## What I Would Improve With More Time
- Expand duplicate record detection into explicit grouped output for clinician review.
- Add persistent audit history for approve/reject decisions.
- Add richer clinical plausibility rules for drug-disease mismatches and lab-aware medication safety.
- Deploy the app and record a short video walkthrough.

## Estimated Time Spent
- Architecture and scaffolding: 3.0 hours
- Backend logic and tests: 8.0 hours
- Frontend dashboard: 3.5 hours
- Docs and packaging: 3.5 hours
- Runtime hardening and live verification: 5.5 hours
- Total: 23.5 hours
