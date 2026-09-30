import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend,
  BarChart, Bar,
} from 'recharts';
import TopoMeshView from './TopoMeshView';

// ─── Custom Tooltip ──────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
      borderRadius: '8px', padding: '10px 14px', fontSize: '11px',
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 600 }}>Iteration {label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.color, display: 'flex', justifyContent: 'space-between', gap: '16px' }}>
          <span>{p.name}</span>
          <b>{typeof p.value === 'number' ? p.value.toFixed(3) : p.value}</b>
        </div>
      ))}
    </div>
  );
}

// ─── Metric badge ─────────────────────────────────────────────────────
function Stat({ label, value, unit, color = 'var(--accent-purple)' }) {
  return (
    <div style={{
      background: 'var(--bg-elevated)', borderRadius: '10px',
      padding: '12px 16px', border: '1px solid var(--border-subtle)',
    }}>
      <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
        {label}
      </div>
      <div style={{ fontSize: '22px', fontWeight: 700, color, lineHeight: 1 }}>
        {value ?? '—'}
        {unit && <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-muted)', marginLeft: '4px' }}>{unit}</span>}
      </div>
    </div>
  );
}

// ─── Row for iteration table ──────────────────────────────────────────
function IterRow({ iter, fea, constraints }) {
  const passed = constraints?.every(c => c.passed);
  return (
    <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <td style={{ padding: '8px 10px', color: 'var(--text-muted)', fontSize: '11px' }}>{iter}</td>
      <td style={{ padding: '8px 10px', fontSize: '11px' }}>{fea?.max_stress_mpa?.toFixed(1) ?? '—'}</td>
      <td style={{ padding: '8px 10px', fontSize: '11px' }}>{fea?.max_displacement_mm?.toFixed(3) ?? '—'}</td>
      <td style={{ padding: '8px 10px', fontSize: '11px' }}>
        <span style={{
          color: fea?.safety_factor >= 2 ? 'var(--accent-green)' : 'var(--accent-red)',
          fontWeight: 600,
        }}>
          {fea?.safety_factor?.toFixed(2) ?? '—'}
        </span>
      </td>
      <td style={{ padding: '8px 10px', fontSize: '11px' }}>{fea?.mass_kg?.toFixed(3) ?? '—'}</td>
      <td style={{ padding: '8px 10px' }}>
        <span className={`badge badge-${passed ? 'green' : 'red'}`} style={{ fontSize: '10px' }}>
          {passed ? '✓ Pass' : '✗ Fail'}
        </span>
      </td>
    </tr>
  );
}

export default function OptimizationHistory({ feaResult, topoResult, spec, log }) {
  const topo = topoResult || {};
  const topoHistory = topo.history || [];

  // Chart data from topo history
  const complianceData = topoHistory.map(h => ({
    iter: h.iteration,
    compliance: parseFloat((h.compliance || 0).toFixed(4)),
    vf: parseFloat(((h.volume_fraction || 0) * 100).toFixed(1)),
  }));

  const hasTopo = topoHistory.length > 0;
  const hasFea  = feaResult && Object.keys(feaResult).length > 0;

  return (
    <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '20px', overflowY: 'auto', height: '100%' }}>

      {/* ── Header ───────────────────────────────────────────────── */}
      <div>
        <h2 style={{
          fontSize: '18px', fontWeight: 700,
          background: 'linear-gradient(135deg, var(--accent-purple), var(--accent-cyan))',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          marginBottom: '4px',
        }}>
          Optimization History
        </h2>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Full record of the design-loop runs — FEA results and topology convergence
        </p>
      </div>

      {/* ── Summary stats ────────────────────────────────────────── */}
      {(hasFea || hasTopo) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
          <Stat label="Safety Factor" value={feaResult?.safety_factor?.toFixed(2)} color={feaResult?.safety_factor >= 2 ? 'var(--accent-green)' : 'var(--accent-red)'} />
          <Stat label="Max Stress"    value={feaResult?.max_stress_mpa?.toFixed(1)} unit="MPa" color="var(--accent-cyan)" />
          <Stat label="Material Saved" value={topo.material_saved_pct?.toFixed(1)} unit="%" color="var(--accent-green)" />
          <Stat label="Compliance ↓"  value={topo.compliance?.toFixed(2)} color="var(--accent-amber)" />
        </div>
      )}

      {/* ── Topology Mesh View (density field + per-round table) ──── */}
      {hasTopo && (
        <div className="glass-card" style={{ padding: '16px' }}>
          <TopoMeshView topoResult={topoResult} />
        </div>
      )}

      {/* ── FEA Results Table ────────────────────────────────────── */}
      {hasFea && (
        <div className="glass-card" style={{ padding: '16px' }}>
          <div className="section-title" style={{ marginBottom: '12px' }}>FEA Analysis Results</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  {['Run', 'σ_max (MPa)', 'Disp (mm)', 'Safety Factor', 'Mass (kg)', 'Status'].map(h => (
                    <th key={h} style={{ padding: '8px 10px', textAlign: 'left', fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <IterRow iter={1} fea={feaResult} constraints={[{ passed: (feaResult?.safety_factor ?? 0) >= 2 }]} />
              </tbody>
            </table>
          </div>

          {/* Constraint breakdown */}
          <div style={{ marginTop: '12px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {[
              { label: 'Safety Factor ≥ 2', passed: (feaResult?.safety_factor ?? 0) >= 2 },
              { label: 'Yield not exceeded', passed: (feaResult?.max_stress_mpa ?? 999) < (feaResult?.yield_strength_mpa ?? 270) },
              { label: 'Displacement < 1mm', passed: (feaResult?.max_displacement_mm ?? 999) < 1 },
            ].map(c => (
              <span key={c.label} className={`badge badge-${c.passed ? 'green' : 'red'}`} style={{ fontSize: '11px' }}>
                {c.passed ? '✓' : '✗'} {c.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Log ──────────────────────────────────────────────────── */}
      {log?.length > 0 && (
        <div className="glass-card" style={{ padding: '16px' }}>
          <div className="section-title" style={{ marginBottom: '8px' }}>Run Log</div>
          <div className="log-box" style={{ maxHeight: '200px' }}>
            {log.map((line, i) => (
              <div key={i} className={`log-line ${line.level || 'info'}`}>{line.text}</div>
            ))}
          </div>
        </div>
      )}

      {/* ── Empty state ───────────────────────────────────────────── */}
      {!hasFea && !hasTopo && (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '40px', marginBottom: '12px' }}>📊</div>
          <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>No history yet</div>
          <div style={{ fontSize: '12px' }}>Run the pipeline from the Design tab to see results here.</div>
        </div>
      )}
    </div>
  );
}
