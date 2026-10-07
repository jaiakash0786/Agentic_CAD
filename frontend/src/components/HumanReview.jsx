import { useState } from 'react';
import api from '../api';

// ─── Section header ────────────────────────────────────────────────────
function SectionHead({ title, subtitle }) {
  return (
    <div style={{ marginBottom: '12px' }}>
      <div className="section-title">{title}</div>
      {subtitle && <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>{subtitle}</div>}
    </div>
  );
}

// ─── Info row ─────────────────────────────────────────────────────────
function InfoRow({ label, value, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ fontSize: '12px', fontWeight: 600, color: color || 'var(--text-primary)' }}>{value ?? '—'}</span>
    </div>
  );
}

// ─── Constraint check row ─────────────────────────────────────────────
function CheckRow({ label, required, actual, unit, passed }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '10px',
      padding: '8px 12px', borderRadius: '8px',
      background: passed ? 'rgba(16,185,129,0.07)' : 'rgba(239,68,68,0.07)',
      border: `1px solid ${passed ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)'}`,
      marginBottom: '6px',
    }}>
      <span style={{ fontSize: '16px' }}>{passed ? '✅' : '❌'}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: '12px', fontWeight: 600 }}>{label}</div>
        <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
          Required: <b>{required}{unit}</b> · Actual: <b style={{ color: passed ? 'var(--accent-green)' : 'var(--accent-red)' }}>{actual}{unit}</b>
        </div>
      </div>
      <span className={`badge badge-${passed ? 'green' : 'red'}`} style={{ fontSize: '10px' }}>
        {passed ? 'PASS' : 'FAIL'}
      </span>
    </div>
  );
}

export default function HumanReview({ spec, feaResult, topoResult, onApprove, onReject, loading }) {
  const [decision, setDecision]       = useState(null);  // 'approved' | 'rejected'
  const [note, setNote]               = useState('');
  const [downloading, setDownloading] = useState(false);
  const [reportUrl, setReportUrl]     = useState(null);

  const downloadReport = async () => {
    if (!spec) return;
    setDownloading(true);
    try {
      const res = await api.generateReport(spec, feaResult, topoResult);
      if (res?.success && res.report_url) {
        // Use api.BASE getter so it respects the user's Settings URL
        const url = `${api.BASE}${res.report_url}`;
        setReportUrl(url);
        window.open(url, '_blank');
      }
    } catch (err) {
      console.error('Report generation failed:', err);
    } finally {
      setDownloading(false);
    }
  };

  const fea  = feaResult  || {};
  const topo = topoResult || {};
  const sf   = fea.safety_factor ?? 0;

  // BUG 5 FIX: Read thresholds from spec.constraints, not hardcoded values
  const reqSF   = spec?.constraints?.min_safety_factor   ?? 2.0;
  const reqDisp = spec?.constraints?.max_displacement_mm ?? 1.0;
  // Max stress: use spec value if given, otherwise derive from yield / SF
  const reqStress = spec?.constraints?.max_stress_mpa
    ?? (fea.yield_strength_mpa ? fea.yield_strength_mpa / reqSF : 270 / reqSF);

  const overallPass = sf >= reqSF && (fea.max_displacement_mm ?? 999) <= reqDisp;

  // Build constraint checks from live FEA data using spec-defined thresholds
  const checks = [
    {
      label: 'Safety Factor',
      required: `≥ ${reqSF.toFixed(1)}`,
      actual: sf.toFixed(2),
      unit: '',
      passed: sf >= reqSF,
    },
    {
      label: 'Max Displacement',
      required: `≤ ${reqDisp.toFixed(1)}`,
      actual: (fea.max_displacement_mm ?? 999).toFixed(3),
      unit: ' mm',
      passed: (fea.max_displacement_mm ?? 999) <= reqDisp,
    },
    {
      label: 'Von Mises Stress',
      required: `< ${reqStress.toFixed(0)}`,
      actual: (fea.max_stress_mpa ?? 0).toFixed(1),
      unit: ' MPa',
      passed: (fea.max_stress_mpa ?? 0) < reqStress,
    },
  ];

  const handleApprove = () => {
    setDecision('approved');
    onApprove?.({ note });
  };

  const handleReject = () => {
    setDecision('rejected');
    onReject?.({ note });
  };

  const hasData = Object.keys(fea).length > 0;

  return (
    <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto', height: '100%' }}>

      {/* ── Header ──────────────────────────────────────────────────── */}
      <div>
        <h2 style={{
          fontSize: '18px', fontWeight: 700,
          background: 'linear-gradient(135deg, var(--accent-purple), var(--accent-cyan))',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: '4px',
        }}>
          Human Review
        </h2>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Review the design before finalizing the report
        </p>
      </div>

      {/* ── Overall verdict banner ───────────────────────────────── */}
      {hasData && !decision && (
        <div style={{
          padding: '14px 18px', borderRadius: '12px',
          background: overallPass ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
          border: `1px solid ${overallPass ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
          display: 'flex', alignItems: 'center', gap: '12px',
        }}>
          <span style={{ fontSize: '28px' }}>{overallPass ? '✅' : '⚠️'}</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: '14px', color: overallPass ? 'var(--accent-green)' : 'var(--accent-red)' }}>
              {overallPass ? 'Design Meets All Constraints' : 'Design Has Constraint Violations'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              {overallPass
                ? 'All structural constraints satisfied. Ready to approve.'
                : 'Review the failures below before approving.'}
            </div>
          </div>
        </div>
      )}

      {/* ── After decision banner ───────────────────────────────────── */}
      {decision && (
        <div style={{
          padding: '14px 18px', borderRadius: '12px', textAlign: 'center',
          background: decision === 'approved' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
          border: `1px solid ${decision === 'approved' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
        }}>
          <div style={{ fontSize: '28px', marginBottom: '6px' }}>
            {decision === 'approved' ? '🎉' : '🔄'}
          </div>
          <div style={{ fontWeight: 700, fontSize: '14px', color: decision === 'approved' ? 'var(--accent-green)' : 'var(--accent-red)' }}>
            Design {decision === 'approved' ? 'Approved' : 'Sent Back for Revision'}
          </div>
          {note && (
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px' }}>
              Note: "{note}"
            </div>
          )}
          <button
            onClick={() => { setDecision(null); setNote(''); }}
            style={{ marginTop: '10px', fontSize: '11px', padding: '4px 12px', cursor: 'pointer',
              background: 'transparent', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: 'var(--text-muted)' }}>
            Reset
          </button>
        </div>
      )}

      {/* ── Constraint Checks ────────────────────────────────────── */}
      {hasData && (
        <div className="glass-card" style={{ padding: '16px' }}>
          <SectionHead title="Constraint Checks" subtitle="Auto-evaluated from FEA results" />
          {checks.map(c => (
            <CheckRow key={c.label} {...c} />
          ))}
        </div>
      )}

      {/* ── Spec Summary ────────────────────────────────────────── */}
      {spec && (
        <div className="glass-card" style={{ padding: '16px' }}>
          <SectionHead title="Design Specification" />
          <InfoRow label="Component"      value={spec.component} />
          <InfoRow label="Material"       value={spec.material_name} />
          <InfoRow label="Safety Factor"  value={spec.safety_factor} />
          {spec.dimensions && Object.entries(spec.dimensions).map(([k, v]) => (
            <InfoRow key={k} label={k.replace(/_/g, ' ')} value={`${v} mm`} />
          ))}
        </div>
      )}

      {/* ── FEA Summary ────────────────────────────────────────────── */}
      {hasData && (
        <div className="glass-card" style={{ padding: '16px' }}>
          <SectionHead title="FEA Summary" />
          <InfoRow label="Max Von Mises Stress"   value={`${fea.max_stress_mpa?.toFixed(2)} MPa`}  color="var(--accent-cyan)" />
          <InfoRow label="Max Displacement"        value={`${fea.max_displacement_mm?.toFixed(4)} mm`} />
          <InfoRow label="Safety Factor"           value={fea.safety_factor?.toFixed(3)} color={sf >= 2 ? 'var(--accent-green)' : 'var(--accent-red)'} />
          <InfoRow label="Yield Strength"          value={`${fea.yield_strength_mpa?.toFixed(0)} MPa`} color="var(--accent-purple)" />
          <InfoRow label="Est. Mass"               value={`${fea.mass_kg?.toFixed(4)} kg`} />
          <InfoRow label="Volume"                  value={fea.volume_mm3 ? `${fea.volume_mm3.toFixed(1)} mm³` : null} />
          {fea.num_elements > 0 && (
            <InfoRow label="Mesh"  value={`${fea.num_nodes} nodes · ${fea.num_elements} elements`} color="var(--text-muted)" />
          )}
        </div>
      )}

      {/* ── Topology Summary ────────────────────────────────────────── */}
      {Object.keys(topo).length > 0 && (
        <div className="glass-card" style={{ padding: '16px' }}>
          <SectionHead title="Topology Optimization" />
          <InfoRow label="Material Saved"    value={`${topo.material_saved_pct?.toFixed(1)}%`} color="var(--accent-green)" />
          <InfoRow label="Compliance"        value={topo.compliance?.toFixed(4)} />
          <InfoRow label="Iterations"        value={topo.iterations} />
          <InfoRow label="Converged"         value={topo.converged ? 'Yes ✓' : 'No (max iters)'} color={topo.converged ? 'var(--accent-green)' : 'var(--accent-amber)'} />
          <InfoRow label="Solid Elements"    value={`${topo.solid_elements} / ${topo.total_elements}`} />
        </div>
      )}

      {/* ── Reviewer Notes ───────────────────────────────────────── */}
      {!decision && hasData && (
        <div className="glass-card" style={{ padding: '16px' }}>
          <SectionHead title="Reviewer Note" subtitle="Optional comment" />
          <textarea
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="Add a note (optional)..."
            rows={3}
            style={{
              width: '100%', resize: 'vertical', padding: '10px 12px',
              background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)',
              borderRadius: '8px', color: 'var(--text-primary)', fontSize: '12px',
              fontFamily: 'inherit', outline: 'none', transition: 'border-color 0.2s',
            }}
            onFocus={e => e.target.style.borderColor = 'var(--accent-purple)'}
            onBlur={e => e.target.style.borderColor = 'var(--border-subtle)'}
          />

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
            <button
              id="btn-approve"
              onClick={handleApprove}
              disabled={loading}
              style={{
                flex: 1, padding: '10px', borderRadius: '8px', cursor: 'pointer', fontWeight: 600,
                fontSize: '13px', border: 'none',
                background: 'linear-gradient(135deg, var(--accent-green), #059669)',
                color: '#fff', transition: 'opacity 0.2s',
                opacity: loading ? 0.5 : 1,
              }}>
              ✓ Approve Design
            </button>
            <button
              id="btn-reject"
              onClick={handleReject}
              disabled={loading}
              style={{
                flex: 1, padding: '10px', borderRadius: '8px', cursor: 'pointer', fontWeight: 600,
                fontSize: '13px', border: '1px solid var(--accent-amber)',
                background: 'rgba(245,158,11,0.1)', color: 'var(--accent-amber)', transition: 'opacity 0.2s',
                opacity: loading ? 0.5 : 1,
              }}>
              🔄 Trigger Auto-Redesign
            </button>
          </div>

          {/* Download Report */}
          <button
            id="btn-download-report"
            onClick={downloadReport}
            disabled={downloading || !spec}
            style={{
              width: '100%', marginTop: '10px', padding: '10px', borderRadius: '8px',
              cursor: spec ? 'pointer' : 'not-allowed', fontWeight: 600, fontSize: '13px',
              border: '1px solid var(--border-glow)',
              background: 'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(6,182,212,0.15))',
              color: downloading ? 'var(--text-muted)' : 'var(--accent-purple)',
              transition: 'all 0.2s',
            }}>
            {downloading ? '⏳ Generating PDF…' : reportUrl ? '✓ PDF Ready — Download Again' : '📄 Download PDF Report'}
          </button>
          {reportUrl && (
            <div style={{ fontSize: '11px', color: 'var(--accent-green)', textAlign: 'center', marginTop: '4px' }}>
              <a href={reportUrl} target="_blank" rel="noreferrer" style={{ color: 'inherit' }}>
                Open PDF ↗
              </a>
            </div>
          )}
        </div>
      )}

      {/* ── Empty state ───────────────────────────────────────────── */}
      {!hasData && (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '40px', marginBottom: '12px' }}>🔍</div>
          <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>Nothing to review yet</div>
          <div style={{ fontSize: '12px' }}>Complete the pipeline in the Design tab first.</div>
        </div>
      )}
    </div>
  );
}
