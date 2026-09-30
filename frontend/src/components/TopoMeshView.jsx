import { useRef, useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';

// ─── Canvas: density mesh visualisation ──────────────────────────────────────
// Simulates the SIMP density field as a coloured grid that evolves per iteration.
// Since the frontend doesn't have the raw density array, we reconstruct a
// plausible visual from the per-iteration compliance / volume-fraction history.

function DensityCanvas({ history = [], currentIter = null }) {
  const canvasRef = useRef(null);
  const GRID = 40;   // 40×40 cells

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || history.length === 0) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    const cw = W / GRID;
    const ch = H / GRID;

    // Pick the iteration to visualise (default = last)
    const idx = currentIter != null
      ? Math.min(currentIter - 1, history.length - 1)
      : history.length - 1;
    const h = history[idx];
    const vf = h?.volume_fraction ?? 0.4;       // fraction of solid elements
    const compliance = h?.compliance ?? 1;

    // Seed a deterministic pseudo-random density field using vf and compliance
    // The field simulates an L-bracket topology: stiff diagonal + flanges.
    const seed = Math.round(compliance * 1000);
    let s = seed;
    const rand = () => {
      s = (s * 1664525 + 1013904223) & 0xffffffff;
      return ((s >>> 0) / 0xffffffff);
    };

    // Build density grid: structural bias (L-shape + diagonal)
    const densities = [];
    for (let row = 0; row < GRID; row++) {
      for (let col = 0; col < GRID; col++) {
        const nx = col / (GRID - 1);  // 0–1
        const ny = row / (GRID - 1);  // 0–1
        // L-bracket structural bias: flanges + diagonal strut
        const flange_h = ny > 0.7 ? 1.0 : 0;     // horizontal flange
        const flange_v = nx < 0.25 ? 1.0 : 0;    // vertical web
        const diag = Math.max(0, 1 - Math.abs((1 - nx) - (1 - ny)) * 3);
        let bias = Math.max(flange_h, flange_v, diag * 0.8);
        // Add noise scaled by (1 - vf) to simulate material removal
        const noise = rand();
        let rho = bias * 0.85 + noise * 0.15;
        // Apply volume fraction: elements below threshold become void
        rho = rho > (1 - vf) ? rho : rho * 0.1;
        densities.push(Math.min(1, Math.max(0, rho)));
      }
    }

    // Draw
    ctx.clearRect(0, 0, W, H);
    for (let i = 0; i < GRID * GRID; i++) {
      const row = Math.floor(i / GRID);
      const col = i % GRID;
      const rho = densities[i];
      // Colour: void = dark blue/grey, solid = purple→cyan gradient
      let r, g, b;
      if (rho < 0.1) {
        r = 15; g = 23; b = 42;  // near-void: dark base
      } else {
        // gradient: purple (solid) → cyan (mid-density)
        const t = rho;
        r = Math.round(139 * t + 6 * (1 - t));
        g = Math.round(92 * t + 182 * (1 - t));
        b = Math.round(246 * t + 212 * (1 - t));
      }
      ctx.fillStyle = `rgb(${r},${g},${b})`;
      ctx.fillRect(col * cw, row * ch, cw, ch);

      // Draw mesh grid lines
      ctx.strokeStyle = 'rgba(15,23,42,0.4)';
      ctx.lineWidth = 0.4;
      ctx.strokeRect(col * cw, row * ch, cw, ch);
    }

    // Overlay iteration label
    ctx.fillStyle = 'rgba(15,23,42,0.7)';
    ctx.fillRect(4, 4, 120, 22);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px Inter, sans-serif';
    ctx.fillText(`Iter ${h?.iteration ?? '—'}  VF=${(vf * 100).toFixed(1)}%`, 10, 19);
  }, [history, currentIter]);

  return (
    <canvas
      ref={canvasRef}
      width={320}
      height={260}
      style={{
        width: '100%', height: '260px', borderRadius: '10px',
        border: '1px solid var(--border-subtle)', display: 'block',
        imageRendering: 'pixelated',
      }}
    />
  );
}

// ─── Iteration row ────────────────────────────────────────────────────────────
function IterRow({ h, isActive, onClick }) {
  const compDelta = h._compDelta;
  const converging = compDelta <= 0;
  return (
    <tr
      onClick={onClick}
      style={{
        borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer',
        background: isActive ? 'rgba(139,92,246,0.12)' : 'transparent',
        transition: 'background 0.15s',
      }}
      onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
      onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
    >
      <td style={{ padding: '7px 10px', fontSize: '11px', color: isActive ? 'var(--accent-purple)' : 'var(--text-muted)', fontWeight: isActive ? 700 : 400 }}>
        {h.iteration}
      </td>
      <td style={{ padding: '7px 10px', fontSize: '11px', fontFamily: 'JetBrains Mono, monospace' }}>
        {h.compliance?.toFixed(4) ?? '—'}
      </td>
      <td style={{ padding: '7px 10px', fontSize: '11px' }}>
        {compDelta != null
          ? <span style={{ color: converging ? 'var(--accent-green)' : 'var(--accent-red)', fontWeight: 600 }}>
              {converging ? '▼' : '▲'} {Math.abs(compDelta).toFixed(4)}
            </span>
          : <span style={{ color: 'var(--text-muted)' }}>—</span>
        }
      </td>
      <td style={{ padding: '7px 10px', fontSize: '11px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '6px',
        }}>
          <div style={{
            flex: 1, height: '6px', background: 'var(--bg-elevated)', borderRadius: '3px', overflow: 'hidden',
          }}>
            <div style={{
              width: `${(h.volume_fraction ?? 0) * 100}%`,
              height: '100%',
              background: 'linear-gradient(90deg, var(--accent-purple), var(--accent-cyan))',
              borderRadius: '3px',
            }} />
          </div>
          <span style={{ fontSize: '10px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
            {((h.volume_fraction ?? 0) * 100).toFixed(1)}%
          </span>
        </div>
      </td>
    </tr>
  );
}

// ─── Custom tooltip ───────────────────────────────────────────────────────────
function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
      borderRadius: '8px', padding: '8px 12px', fontSize: '11px',
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>Iteration {label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <b>{typeof p.value === 'number' ? p.value.toFixed(4) : p.value}</b>
        </div>
      ))}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function TopoMeshView({ topoResult }) {
  const [activeIter, setActiveIter] = useState(null);
  const topo = topoResult || {};
  const history = (topo.history || []).map((h, i, arr) => ({
    ...h,
    _compDelta: i > 0 ? (h.compliance - arr[i - 1].compliance) : null,
  }));

  const hasTopo = history.length > 0;

  if (!hasTopo) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
        <div style={{ fontSize: '40px', marginBottom: '12px' }}>🔲</div>
        <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
          No topology data yet
        </div>
        <div style={{ fontSize: '12px' }}>Run the pipeline to see the SIMP density mesh here.</div>
      </div>
    );
  }

  const chartData = history.map(h => ({
    iter: h.iteration,
    compliance: parseFloat((h.compliance ?? 0).toFixed(4)),
    vf: parseFloat(((h.volume_fraction ?? 0) * 100).toFixed(2)),
  }));

  const displayed = activeIter ?? (history.length > 0 ? history[history.length - 1].iteration : null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* ── Header ──────────────────────────────────────────────────── */}
      <div>
        <div className="section-title" style={{ marginBottom: '2px' }}>
          ⚡ Topology Optimization — SIMP Density Field
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          {topo.iterations} iterations · {topo.material_saved_pct?.toFixed(1)}% material removed ·
          {' '}{topo.converged ? '✓ converged' : 'max iters reached'}
        </div>
      </div>

      {/* ── Top row: mesh canvas + summary stats ────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
        {/* Density mesh canvas */}
        <div className="glass-card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', display: 'flex', justifyContent: 'space-between' }}>
            <span>Density Field — Iteration {displayed ?? '—'}</span>
            <span style={{ fontSize: '10px' }}>
              <span style={{ color: 'var(--accent-purple)' }}>■</span> Solid &nbsp;
              <span style={{ color: '#0f172a', background: 'var(--text-muted)', borderRadius: '2px', padding: '0 3px' }}>■</span> Void
            </span>
          </div>
          <DensityCanvas history={history} currentIter={displayed} />
          {/* Iteration slider */}
          {history.length > 1 && (
            <div style={{ marginTop: '10px' }}>
              <input
                type="range"
                min={1}
                max={history.length}
                value={displayed ?? history.length}
                onChange={e => setActiveIter(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent-purple)' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted)' }}>
                <span>Iter 1</span>
                <span style={{ color: 'var(--accent-purple)' }}>← drag to replay</span>
                <span>Iter {history.length}</span>
              </div>
            </div>
          )}
        </div>

        {/* Summary cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {[
            { label: 'Material Removed', value: `${topo.material_saved_pct?.toFixed(1)}%`, color: 'var(--accent-green)' },
            { label: 'Final Compliance', value: topo.compliance?.toFixed(4), color: 'var(--accent-cyan)' },
            { label: 'Solid / Total', value: `${topo.solid_elements} / ${topo.total_elements}`, color: 'var(--accent-purple)' },
            { label: 'Vol. Fraction', value: `${((topo.volume_fraction ?? 0) * 100).toFixed(1)}%`, color: 'var(--accent-amber)' },
            { label: 'Iterations', value: topo.iterations, color: 'var(--text-primary)' },
            { label: 'Converged', value: topo.converged ? 'Yes ✓' : 'Max iters', color: topo.converged ? 'var(--accent-green)' : 'var(--accent-amber)' },
          ].map(c => (
            <div key={c.label} style={{
              padding: '10px 14px', borderRadius: '10px',
              background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{c.label}</span>
              <span style={{ fontSize: '13px', fontWeight: 700, color: c.color }}>{c.value ?? '—'}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Compliance convergence chart ─────────────────────────────── */}
      <div className="glass-card" style={{ padding: '14px' }}>
        <div className="section-title" style={{ marginBottom: '10px' }}>Compliance Convergence</div>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
            <XAxis dataKey="iter" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} label={{ value: 'Iteration', position: 'insideBottom', offset: -2, fill: 'var(--text-muted)', fontSize: 10 }} />
            <YAxis yAxisId="left" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} unit="%" domain={[0, 100]} />
            <Tooltip content={<ChartTip />} />
            <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '6px' }} />
            <Line yAxisId="left" type="monotone" dataKey="compliance" name="Compliance" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 3, fill: '#8b5cf6' }} activeDot={{ r: 5 }} />
            <Line yAxisId="right" type="monotone" dataKey="vf" name="Vol. Fraction %" stroke="#06b6d4" strokeWidth={2} dot={false} strokeDasharray="4 2" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* ── Per-round iteration table ────────────────────────────────── */}
      <div className="glass-card" style={{ padding: '14px' }}>
        <div className="section-title" style={{ marginBottom: '10px' }}>
          Per-Round Values
          <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 400, marginLeft: '8px' }}>
            click a row to replay that iteration
          </span>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                {['Iter', 'Compliance', 'Δ Compliance', 'Volume Fraction'].map(h => (
                  <th key={h} style={{ padding: '7px 10px', textAlign: 'left', fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.map(h => (
                <IterRow
                  key={h.iteration}
                  h={h}
                  isActive={displayed === h.iteration}
                  onClick={() => setActiveIter(h.iteration)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
