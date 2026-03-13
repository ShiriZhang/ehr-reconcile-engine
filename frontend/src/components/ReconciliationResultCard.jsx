import { StatusBadge } from "./StatusBadge";

export function ReconciliationResultCard({ result, decision, onDecision }) {
  if (!result) {
    return (
      <section className="panel result-panel">
        <p className="empty-state">Submit medication conflicts to see a reconciled result.</p>
      </section>
    );
  }

  const tone = result.confidence_score >= 0.8 ? "green" : result.confidence_score >= 0.6 ? "yellow" : "red";
  const safetyTone =
    result.clinical_safety_check === "PASSED"
      ? "green"
      : result.clinical_safety_check === "WARNING"
        ? "yellow"
        : "red";

  return (
    <section className="panel result-panel">
      <div className="result-header">
        <div>
          <p className="eyebrow">Medication Reconciliation</p>
          <h2>{result.reconciled_medication}</h2>
        </div>
        <div className="result-badges">
          <StatusBadge label={`Confidence ${Math.round(result.confidence_score * 100)}%`} tone={tone} />
          <StatusBadge label={result.clinical_safety_check} tone={safetyTone} />
        </div>
      </div>

      <p className="reasoning-copy">{result.reasoning}</p>

      <div className="result-grid">
        <div>
          <h3>Recommended actions</h3>
          <ul>
            {result.recommended_actions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3>Clinician review</h3>
          <div className="decision-row">
            <button type="button" className="primary-button" onClick={() => onDecision("approved")}>
              Approve
            </button>
            <button type="button" className="secondary-button" onClick={() => onDecision("rejected")}>
              Reject
            </button>
          </div>
          <p className="decision-copy">
            Current review status: <strong>{decision || "pending"}</strong>
          </p>
        </div>
      </div>
    </section>
  );
}
