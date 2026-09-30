import { useState } from 'react';

const EXAMPLES = [
  "Design an aluminum 6061-T6 L-bracket for a robotic arm. Apply 5000N downward load at the end face. Fix through the mounting holes. Safety factor must be ≥ 2.",
  "Create a steel cantilever bracket 150mm long, 60mm wide, 8mm thick. 10kN vertical load at free end. Fixed at base. Min SF = 3.",
  "Aluminum rectangular plate 200×100×10mm. Distributed load 2000N on top face. Fixed bottom face. Keep displacement under 0.5mm.",
];

export default function RequirementInput({ onSubmit, loading }) {
  const [text, setText] = useState('');
  const [charCount, setCharCount] = useState(0);

  const handleChange = (e) => {
    setText(e.target.value);
    setCharCount(e.target.value.length);
  };

  const handleExample = (ex) => {
    setText(ex);
    setCharCount(ex.length);
  };

  const handleSubmit = () => {
    if (text.trim()) onSubmit(text.trim());
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSubmit();
  };

  return (
    <div className="glass-card" style={{ padding: '14px' }}>
      <div className="section-title" style={{ marginBottom: '10px' }}>
        🧠 Natural Language Requirement
      </div>

      <div className="req-input-wrap">
        <textarea
          id="requirement-input"
          className="req-textarea"
          placeholder="Describe your structural component in plain English…&#10;e.g. &quot;Design an aluminum L-bracket with 5000N load…&quot;"
          value={text}
          onChange={handleChange}
          onKeyDown={handleKey}
          rows={4}
          disabled={loading}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
            {charCount} chars · Ctrl+Enter to run
          </span>
        </div>
      </div>

      <button
        id="run-pipeline-btn"
        className="btn-primary"
        style={{ marginTop: '10px' }}
        onClick={handleSubmit}
        disabled={loading || !text.trim()}
      >
        {loading ? (
          <>
            <div className="spinner" />
            Running Pipeline…
          </>
        ) : (
          <>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            Run Agentic Pipeline
          </>
        )}
      </button>

      {/* Example prompts */}
      <div style={{ marginTop: '10px' }}>
        <div className="section-title" style={{ marginBottom: '6px' }}>Quick Examples</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {EXAMPLES.map((ex, i) => (
            <button
              key={i}
              className="btn-secondary"
              id={`example-btn-${i}`}
              onClick={() => handleExample(ex)}
              disabled={loading}
              style={{ textAlign: 'left', fontSize: '11px', lineHeight: '1.4' }}
            >
              <span style={{ color: 'var(--accent-purple)', flexShrink: 0 }}>#{i + 1}</span>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {ex.slice(0, 60)}…
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
