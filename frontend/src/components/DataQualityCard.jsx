import { StatusBadge } from "./StatusBadge";

function toneForScore(score) {
  if (score >= 80) return "green";
  if (score >= 60) return "yellow";
  return "red";
}

export function DataQualityCard({ result }) {
  if (!result) {
    return (
      <section className="panel result-panel">
        <p className="empty-state">Submit a patient record to inspect data quality.</p>
      </section>
    );
  }

  return (
    <section className="panel result-panel">
      <div className="result-header">
        <div>
          <p className="eyebrow">Data Quality Validation</p>
          <h2>Overall score: {result.overall_score}</h2>
        </div>
        <StatusBadge label={toneForScore(result.overall_score).toUpperCase()} tone={toneForScore(result.overall_score)} />
      </div>

      <div className="score-grid">
        {Object.entries(result.breakdown).map(([label, score]) => (
          <article key={label} className="score-card">
            <span>{label.replaceAll("_", " ")}</span>
            <strong>{score}</strong>
            <div className="score-bar">
              <div className={`score-fill status-${toneForScore(score)}`} style={{ width: `${score}%` }} />
            </div>
          </article>
        ))}
      </div>

      <div>
        <h3>Issues detected</h3>
        <ul className="issue-list">
          {result.issues_detected.map((issue, index) => (
            <li key={`${issue.field}-${index}`}>
              <div className="issue-row">
                <span>{issue.field}</span>
                <StatusBadge label={issue.severity} tone={issue.severity === "high" ? "red" : issue.severity === "medium" ? "yellow" : "green"} />
              </div>
              <p>{issue.issue}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
