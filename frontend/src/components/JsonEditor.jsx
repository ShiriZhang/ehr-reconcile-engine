export function JsonEditor({ title, value, onChange, onLoadSample, helperText }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">{title}</p>
          <h2>{title} Input</h2>
        </div>
        <button type="button" className="secondary-button" onClick={onLoadSample}>
          Reset to sample
        </button>
      </div>
      <p className="helper-text">{helperText}</p>
      <textarea
        className="json-textarea"
        spellCheck="false"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </section>
  );
}
