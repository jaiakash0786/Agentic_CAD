import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';

function MetricCard({ label, value, unit, sub, colorClass = 'purple', id }) {
  return (
    <div className="metric-card" id={id}>
      <div className="metric-label">{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
        <span className={`metric-value ${colorClass}`}>{value ?? '—'}</span>
        {unit && <span className="metric-unit">{unit}</span>}
      </div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}

function SafetyGauge({ sf }) {
  if (!sf) return null;
  const capped = Math.min(sf, 10);
  const pct    = (capped / 10) * 100;
  const color  = sf >= 3 ? 'var(--accent-green)' : sf >= 2 ? 'var(--accent-amber)' : 'var(--accent-red)';
  const label  = sf >= 3 ? 'Safe' : sf >= 2 ? 'Marginal' : 'Unsafe';
  return (
    <div className="metric-card" id="sf-gauge">
      <div className="metric-label">Safety Factor</div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="metric-value" style={{ color }}>{sf.toFixed(2)}</span>
        <span className="badge" style={{
          background: `${color}22`, color, border: `1px solid ${color}44`, fontSize: '11px', padding: '2px 8px',
        }}>{label}</span>
      </div>
      <div className="progress-bar-wrap" style={{ marginTop: '8px' }}>
        <div className="progress-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="metric-sub" style={{ marginTop: '4px' }}>Min required: 2.0</div>
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
      borderRadius: '6px', padding: '8px 12px', fontSize: '11px',
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>Iter {label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <b>{typeof p.value === 'number' ? p.value.toFixed(4) : p.value}</b>
        </div>
      ))}
    </div>
  );
}

export default function ResultsPanel({ feaResult, topoResult, onNavigateToHistory }) {
  const fea  = feaResult?.fea_result || feaResult || {};
  const topo = topoResult || {};

  // Prepare convergence chart data
  const chartData = (topo.history || []).map(h => ({
    iter:       h.iteration,
    compliance: parseFloat(h.compliance?.toFixed(4) || 0),
    vf:         parseFloat(((h.volume_fraction || 0) * 100).toFixed(1)),
  }));

  const hasData = Object.keys(fea).length > 0 || Object.keys(topo).length > 0;

  if (!hasData) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div className="glass-card" style={{ padding: '14px' }}>
          <div className="section-title">Results</div>
          <div style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: '10px', textAlign: 'center', padding: '20px 0' }}>
            Run the pipeline to see results
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

      {/* ── FEA Results ── */}
      {Object.keys(fea).length > 0 && (
        <div className="glass-card fade-in" style={{ padding: '14px' }}>
          <div className="section-title" style={{ marginBottom: '10px' }}>⚙️ FEA Results</div>

          <SafetyGauge sf={fea.safety_factor} />

          <div className="metrics-grid-2" style={{ marginTop: '8px' }}>
            <MetricCard
              id="max-stress-card"
              label="Max Von Mises"
              value={fea.max_stress_mpa?.toFixed(1)}
              unit="MPa"
              colorClass={fea.max_stress_mpa > 200 ? 'red' : 'cyan'}
            />
            <MetricCard
              id="max-disp-card"
              label="Max Displacement"
              value={fea.max_displacement_mm?.toFixed(3)}
              unit="mm"
              colorClass={fea.max_displacement_mm > 0.5 ? 'amber' : 'green'}
            />
          </div>

          <div className="metrics-grid-2" style={{ marginTop: '8px' }}>
            <MetricCard
              id="yield-str-card"
              label="Yield Strength"
              value={(fea.yield_strength_mpa || (fea.max_stress_mpa && fea.safety_factor ? fea.max_stress_mpa * fea.safety_factor : null))?.toFixed(0)}
              unit="MPa"
              colorClass="purple"
            />
            <MetricCard
              id="mass-card"
              label="Est. Mass"
              value={fea.mass_kg?.toFixed(3)}
              unit="kg"
              colorClass="cyan"
            />
          </div>

          {/* Validation badges */}
          {fea.constraint_results && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '10px' }}>
              {Object.entries(fea.constraint_results).map(([k, v]) => (
                <span key={k} className={`badge badge-${v ? 'green' : 'red'}`}>
                  {v ? '✓' : '✗'} {k.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Topology Results ── */}
      {Object.keys(topo).length > 0 && (
        <div className="glass-card fade-in" style={{ padding: '14px' }}>
          <div className="section-title" style={{ marginBottom: '10px' }}>⚡ Topology Optimization</div>

          <div className="metrics-grid-2">
            <MetricCard
              id="material-saved-card"
              label="Material Saved"
              value={topo.material_saved_pct?.toFixed(1)}
              unit="%"
              colorClass="green"
              sub="vs solid design"
            />
            <MetricCard
              id="solid-elements-card"
              label="Solid Elements"
              value={topo.solid_elements}
              sub={`of ${topo.total_elements} total`}
              colorClass="purple"
            />
          </div>

          <div className="metrics-grid-2" style={{ marginTop: '8px' }}>
            <MetricCard
              id="compliance-card"
              label="Final Compliance"
              value={topo.compliance?.toFixed(4)}
              colorClass="cyan"
            />
            <MetricCard
              id="iterations-card"
              label="Iterations"
              value={topo.iterations}
              sub={topo.converged ? '✓ converged' : 'max reached'}
              colorClass={topo.converged ? 'green' : 'amber'}
            />
          </div>

          {/* Convergence chart */}
          {chartData.length > 1 && (
            <div style={{ marginTop: '12px' }}>
              <div className="section-title" style={{ marginBottom: '6px' }}>Compliance Convergence</div>
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height={150}>
                  <LineChart data={chartData} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                    <XAxis dataKey="iter" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                    <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="compliance"
                      name="Compliance"
                      stroke="#8b5cf6"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4, fill: '#8b5cf6' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {onNavigateToHistory && (
            <button
              type="button"
              className="btn-secondary"
              style={{
                width: '100%',
                marginTop: '12px',
                fontSize: '11px',
                padding: '7px 10px',
                justifyContent: 'center',
                borderColor: 'rgba(139,92,246,0.35)',
              }}
              onClick={onNavigateToHistory}
            >
              📈 View Density Mesh & Full History →
            </button>
          )}
        </div>
      )}
    </div>
  );
}
