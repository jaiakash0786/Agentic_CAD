const STEPS = [
  { key: 'interpret',    label: 'AI Interpretation',     icon: '🧠' },
  { key: 'validate',     label: 'Spec Validation',        icon: '✅' },
  { key: 'cad',          label: 'CAD Generation',         icon: '📐' },
  { key: 'fea',          label: 'FEA Analysis',           icon: '🔬' },
  { key: 'optimize',     label: 'Topology Optimization',  icon: '⚡' },
  { key: 'reconstruct',  label: 'CAD Reconstruction',     icon: '🔧' },
  { key: 'report',       label: 'Report Generation',      icon: '📄' },
];

export default function PipelineStatus({ stepStates = {}, log = [] }) {
  const allDone = STEPS.every(s => stepStates[s.key] === 'done');

  return (
    <div className="glass-card" style={{ padding: '14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <div className="section-title" style={{ margin: 0 }}>Pipeline Status</div>
        {allDone && <span className="badge badge-green">✓ Complete</span>}
      </div>

      <div className="pipeline-steps">
        {STEPS.map((step) => {
          const state = stepStates[step.key] || 'pending';
          return (
            <div key={step.key} id={`step-${step.key}`} className={`pipeline-step ${state}`}>
              <div className={`step-icon ${state}`}>
                {state === 'active' ? <div className="spinner" /> :
                 state === 'done'  ? '✓' :
                 state === 'error' ? '✗' :
                 step.icon}
              </div>
              <span className={`step-label ${state}`}>{step.label}</span>
              {state === 'active' && (
                <span className="step-time">running…</span>
              )}
              {state === 'done' && (
                <span style={{ color: 'var(--accent-green)', fontSize: '10px' }}>done</span>
              )}
              {state === 'error' && (
                <span style={{ color: 'var(--accent-red)', fontSize: '10px' }}>failed</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Log output */}
      {log.length > 0 && (
        <div style={{ marginTop: '10px' }}>
          <div className="section-title" style={{ marginBottom: '4px' }}>Log</div>
          <div className="log-box">
            {log.map((line, i) => (
              <div key={i} className={`log-line ${line.level || 'info'}`}>
                {line.text}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
