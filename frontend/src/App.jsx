import { useState } from "react";
import { JsonEditor } from "./components/JsonEditor";
import { ReconciliationResultCard } from "./components/ReconciliationResultCard";
import { DataQualityCard } from "./components/DataQualityCard";
import { postJson } from "./lib/api";
import { medicationSample, qualitySample } from "./lib/samples";

const medicationSeed = JSON.stringify(medicationSample, null, 2);
const qualitySeed = JSON.stringify(qualitySample, null, 2);

export default function App() {
  const [medicationInput, setMedicationInput] = useState(medicationSeed);
  const [qualityInput, setQualityInput] = useState(qualitySeed);
  const [medicationResult, setMedicationResult] = useState(null);
  const [qualityResult, setQualityResult] = useState(null);
  const [medicationDecision, setMedicationDecision] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState("");

  async function submitMedication() {
    setError("");
    setLoading("medication");
    try {
      const payload = JSON.parse(medicationInput);
      const result = await postJson("/api/reconcile/medication", payload);
      setMedicationResult(result);
      setMedicationDecision("");
    } catch (err) {
      setError(err.message || "Medication reconciliation failed.");
    } finally {
      setLoading("");
    }
  }

  async function submitQuality() {
    setError("");
    setLoading("quality");
    try {
      const payload = JSON.parse(qualityInput);
      const result = await postJson("/api/validate/data-quality", payload);
      setQualityResult(result);
    } catch (err) {
      setError(err.message || "Data quality validation failed.");
    } finally {
      setLoading("");
    }
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Clinical Data Reconciliation Engine</p>
          <h1>Resolve medication conflicts and audit EHR quality from one workstation.</h1>
          <p className="hero-copy">
            Compare medication records across systems, surface conflicts with
            AI-assisted reasoning, and validate patient data quality — all in one
            place.
          </p>
        </div>
        <div className="hero-card">
          <span>How it works</span>
          <strong>Submit records, review results, approve or reject</strong>
          <p>
            Conflicting medications are reconciled with confidence scoring.
            Patient records are audited for completeness, accuracy, and
            clinical plausibility.
          </p>
        </div>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="workspace-grid">
        <div className="editor-stack">
          <JsonEditor
            title="Medication Reconciliation"
            value={medicationInput}
            onChange={setMedicationInput}
            onLoadSample={() => setMedicationInput(medicationSeed)}
            helperText="Paste conflicting medication records from multiple systems."
          />
          <button type="button" className="primary-button action-button" onClick={submitMedication}>
            {loading === "medication" ? "Reconciling..." : "Run reconciliation"}
          </button>
        </div>
        <ReconciliationResultCard
          result={medicationResult}
          decision={medicationDecision}
          onDecision={setMedicationDecision}
        />
      </section>

      <section className="workspace-grid">
        <div className="editor-stack">
          <JsonEditor
            title="Data Quality Validation"
            value={qualityInput}
            onChange={setQualityInput}
            onLoadSample={() => setQualityInput(qualitySeed)}
            helperText="Inspect completeness, accuracy, timeliness, and plausibility."
          />
          <button type="button" className="primary-button action-button" onClick={submitQuality}>
            {loading === "quality" ? "Validating..." : "Validate quality"}
          </button>
        </div>
        <DataQualityCard result={qualityResult} />
      </section>
    </main>
  );
}
