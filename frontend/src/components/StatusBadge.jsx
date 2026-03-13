export function StatusBadge({ label, tone = "neutral" }) {
  return <span className={`status-badge status-${tone}`}>{label}</span>;
}
