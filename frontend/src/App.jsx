import { useState, useCallback, useEffect, useRef } from 'react';
import './index.css';
import api from './api';
import RequirementInput from './components/RequirementInput';
import SpecForm from './components/SpecForm';
import PipelineStatus from './components/PipelineStatus';
import ModelViewer from './components/ModelViewer';
import ResultsPanel from './components/ResultsPanel';
import OptimizationHistory from './components/OptimizationHistory';
import HumanReview from './components/HumanReview';
import ChatPanel from './components/ChatPanel';
import SettingsModal, { loadSettings } from './components/SettingsModal';

// ─── Sidebar icon button ───────────────────────────────────────────
const NavIcon = ({ children, active, onClick, tooltip, id, badge }) => (
  <button className={`sidebar-btn ${active ? 'active' : ''}`} onClick={onClick} id={id}
    style={{ position: 'relative' }}>
    {children}
    {badge && (
      <span style={{
        position: 'absolute', top: '4px', right: '4px',
        width: '7px', height: '7px', borderRadius: '50%',
        background: 'var(--accent-red)', boxShadow: '0 0 6px var(--accent-red)',
      }} />
    )}
    <span className="tooltip">{tooltip}</span>
  </button>
);

// ─── Toast notification system ────────────────────────────────────
function Toast({ toasts, onDismiss }) {
  return (
    <div style={{
      position: 'fixed', top: '70px', right: '18px', zIndex: 2000,
      display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '340px',
    }}>
      {toasts.map(t => (
        <div key={t.id} style={{
          padding: '10px 14px',
          background: t.type === 'error' ? 'rgba(239,68,68,0.15)' :
            t.type === 'warn' ? 'rgba(245,158,11,0.15)' :
              'rgba(16,185,129,0.15)',
          border: `1px solid ${t.type === 'error' ? 'rgba(239,68,68,0.4)' :
            t.type === 'warn' ? 'rgba(245,158,11,0.4)' :
              'rgba(16,185,129,0.4)'}`,
          borderRadius: '10px', backdropFilter: 'blur(12px)',
          display: 'flex', alignItems: 'flex-start', gap: '8px',
          fontSize: '12px', color: 'var(--text-primary)',
          animation: 'slide-in-right 0.25s ease',
          boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
          cursor: 'pointer',
        }} onClick={() => onDismiss(t.id)}>
          <span style={{ fontSize: '14px', flexShrink: 0 }}>
            {t.type === 'error' ? '✗' : t.type === 'warn' ? '⚠' : '✓'}
          </span>
          <span style={{ lineHeight: '1.5', flex: 1 }}>{t.message}</span>
          <span style={{ color: 'var(--text-muted)', flexShrink: 0, marginLeft: '4px' }}>✕</span>
        </div>
      ))}
    </div>
  );
}


// --- Backend status pill --------------------------------------------------
// busy=true while pipeline runs: shows amber 'Backend Busy' not red 'Offline'
function BackendStatus({ status, busy }) {
  const display = (busy && status !== 'error') ? 'busy' : status;
  const colors  = { ok: '#10b981', busy: '#f59e0b', checking: '#f59e0b', error: '#ef4444' };
  const labels  = { ok: 'Backend Online', busy: 'Backend Busy...', checking: 'Connecting...', error: 'Backend Offline' };
  const pulse   = display === 'busy' || display === 'checking';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <div style={{
        width: '7px', height: '7px', borderRadius: '50%',
        background: colors[display],
        boxShadow: display === 'ok' ? '0 0 8px #10b981' : display === 'busy' ? '0 0 6px #f59e0b' : 'none',
        transition: 'all 0.4s',
        animation: pulse ? 'pulse-dot 1.4s ease-in-out infinite' : 'none',
      }} />
      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{labels[display]}</span>
    </div>
  );
}

// ─── Empty state helper ───────────────────────────────────────────
function EmptyState({ icon, title, subtitle, suggestion }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      height: '100%', minHeight: '220px', gap: '10px',
      color: 'var(--text-muted)', textAlign: 'center', padding: '20px',
    }}>
      <div style={{ fontSize: '40px', opacity: 0.4 }}>{icon}</div>
      <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-secondary)' }}>{title}</div>
      {subtitle && <div style={{ fontSize: '12px', lineHeight: '1.6', maxWidth: '280px' }}>{subtitle}</div>}
      {suggestion && (
        <div style={{
          fontSize: '11px', padding: '6px 12px', borderRadius: '20px',
          background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.2)',
          color: 'var(--accent-purple)', marginTop: '4px',
        }}>{suggestion}</div>
      )}
    </div>
  );
}

export default function App() {
  // ── State ────────────────────────────────────────────────────────
  const [view, setView] = useState('design');
  const [chatOpen, setChatOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [spec, setSpec] = useState(null);
  const [stepStates, setStepStates] = useState({});
  const [log, setLog] = useState([]);
  const [feaResult, setFeaResult] = useState(null);
  const [topoResult, setTopoResult] = useState(null);
  const [stlUrl, setStlUrl] = useState(null);
  const [stlLabel, setStlLabel] = useState('');
  const [error, setError] = useState(null);
  const [lastDescription, setLastDescription] = useState('');

  // Phase 10 additions
  const [backendStatus, setBackendStatus] = useState('checking');
  const [toasts, setToasts] = useState([]);
  const toastIdRef = useRef(0);

  // ── Backend health check ─────────────────────────────────────────
  // Suppress "offline" during active pipeline runs — topo opt blocks
  // the Python process for ~60-120s so health pings time out (5s).
  // We only flip to offline when we're NOT mid-pipeline.
  useEffect(() => {
    const check = async () => {
      const ok = await api.checkHealth();
      // If the pipeline is running, ONLY update status to 'ok' (never to 'error')
      // This prevents the false-offline flicker during topology optimization.
      setBackendStatus(prev => {
        if (!ok && loading) return prev;   // stay as-is while pipeline active
        return ok ? 'ok' : 'error';
      });
    };
    check();
    const interval = setInterval(check, 30_000);
    return () => clearInterval(interval);
  }, [loading]);

  // ── Toast helpers ────────────────────────────────────────────────
  const showToast = useCallback((message, type = 'ok', durationMs = 4000) => {
    const id = ++toastIdRef.current;
    setToasts(t => [...t.slice(-4), { id, message, type }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), durationMs);
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts(t => t.filter(x => x.id !== id));
  }, []);

  // ── Helpers ──────────────────────────────────────────────────────
  const setStep = (key, state) =>
    setStepStates(s => ({ ...s, [key]: state }));

  const addLog = (text, level = 'info') =>
    setLog(l => [...l.slice(-50), { text, level }]);

  const reset = () => {
    setStepStates({});
    setLog([]);
    setFeaResult(null);
    setTopoResult(null);
    setStlUrl(null);
    setError(null);
  };

  // ── Full Pipeline ─────────────────────────────────────────────────
  const runPipeline = useCallback(async (description) => {
    reset();
    setLoading(true);
    setError(null);
    setLastDescription(description);

    try {
      // Step 1: Interpret
      setStep('interpret', 'active');
      addLog('🧠 Interpreting requirement…');
      const interpResult = await api.interpret(description);
      if (!interpResult?.specification) throw new Error('AI interpretation returned no specification');
      const parsedSpec = interpResult.specification;
      setSpec(parsedSpec);
      setStep('interpret', 'done');
      addLog(`✓ Interpreted: ${parsedSpec.component} / ${parsedSpec.material_name}`, 'ok');
      showToast(`Component: ${parsedSpec.component} | Material: ${parsedSpec.material_name}`, 'ok');

      // Step 2: Validate
      setStep('validate', 'active');
      addLog('✅ Validating specification…');
      const valResult = await api.validate(parsedSpec);
      setStep('validate', valResult?.valid ? 'done' : 'error');
      if (!valResult?.valid) {
        const issues = valResult?.issues?.join(', ') || 'Unknown validation issue';
        addLog(`⚠ Validation: ${issues}`, 'warn');
        showToast(`Validation warning: ${issues}`, 'warn', 6000);
      } else {
        addLog('✓ Spec valid', 'ok');
      }

      // Step 3: CAD
      setStep('cad', 'active');
      addLog('📐 Generating CAD model…');
      const cadResult = await api.generateCAD(parsedSpec);
      if (cadResult?.success === false) throw new Error(`CAD generation failed: ${cadResult.error}`);
      setStep('cad', 'done');
      addLog('✓ STEP + STL generated', 'ok');
      if (cadResult?.stl_file_url) {
        setStlUrl(`${api.BASE}${cadResult.stl_file_url}`);
        setStlLabel('Original CAD');
      }

      // Step 4: FEA
      setStep('fea', 'active');
      addLog('🔬 Running FEA (C3D4 tetrahedral solver)…');
      const feaRes = await api.runFEA(parsedSpec);
      if (feaRes?.success === false) throw new Error(`FEA failed: ${feaRes.error}`);
      const feaData = feaRes.fea_result ?? feaRes;
      setFeaResult(feaData);
      setStep('fea', 'done');
      const sfVal = feaData.safety_factor?.toFixed(2);
      const sigVal = feaData.max_stress_mpa?.toFixed(1);
      addLog(`✓ FEA: SF=${sfVal}, σ=${sigVal} MPa`, 'ok');
      const sfNum = parseFloat(sfVal);
      showToast(
        `FEA complete — SF ${sfVal} ${sfNum >= 2 ? '✓ PASS' : '✗ FAIL'}`,
        sfNum >= 2 ? 'ok' : 'warn', 5000
      );

      // Step 5: Topology Optimization
      setStep('optimize', 'active');
      const userSettings = loadSettings();
      addLog(`⚡ Running SIMP topology optimization (${userSettings.maxTopoIter ?? 15} iters)…`);
      const topoRes = await api.runOptimize(parsedSpec, {
        volume_fraction: userSettings.volumeFraction ?? 0.4,
        max_iter: userSettings.maxTopoIter ?? 15,
      });
      if (topoRes?.success === false) throw new Error(`Topology opt failed: ${topoRes.error}`);
      setTopoResult(topoRes);
      setStep('optimize', 'done');
      addLog(`✓ Topology: ${topoRes.material_saved_pct?.toFixed(1)}% material saved, ${topoRes.iterations} iters`, 'ok');
      showToast(`Topology: ${topoRes.material_saved_pct?.toFixed(1)}% material removed`, 'ok');

      setStep('reconstruct', 'done');
      setStep('report', 'done');
      addLog('🎉 Pipeline complete! Review results in the right panel.', 'ok');
      showToast('Pipeline complete! Check Results & Review tabs.', 'ok', 6000);

    } catch (err) {
      const msg = err.message || 'Unknown error';
      setError(msg);
      addLog(`✗ Error: ${msg}`, 'error');
      showToast(msg, 'error', 8000);
      setStepStates(s => {
        const next = { ...s };
        for (const k of Object.keys(next)) {
          if (next[k] === 'active') next[k] = 'error';
        }
        return next;
      });
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  // ── Retry pipeline ────────────────────────────────────────────────
  const retryPipeline = useCallback(() => {
    if (lastDescription) runPipeline(lastDescription);
  }, [lastDescription, runPipeline]);

  // ── Redesign ────────────────────────────────────────────────────
  const runRedesign = useCallback(async ({ note } = {}) => {
    if (!spec) return;
    setView('design');
    reset();
    setLoading(true);
    setError(null);
    addLog(`🔄 Redesign triggered${note ? ': ' + note : ''}`, 'warn');

    try {
      setStep('interpret', 'done');
      setStep('validate', 'done');
      setStep('cad', 'active');
      addLog('📐 Regenerating CAD with current spec…');
      const cadResult = await api.generateCAD(spec);
      if (cadResult?.success === false) throw new Error(cadResult.error);
      setStep('cad', 'done');
      addLog('✓ CAD regenerated', 'ok');
      if (cadResult?.stl_file_url) {
        setStlUrl(`${api.BASE}${cadResult.stl_file_url}`);
        setStlLabel('Redesigned CAD');
      }

      setStep('fea', 'active');
      addLog('🔬 Running FEA on redesigned model…');
      const feaRes = await api.runFEA(spec);
      if (feaRes?.success === false) throw new Error(feaRes.error);
      const feaData = feaRes.fea_result ?? feaRes;
      setFeaResult(feaData);
      setStep('fea', 'done');
      const sf = feaData.safety_factor?.toFixed(2);
      addLog(`✓ FEA: SF=${sf}, σ=${feaData.max_stress_mpa?.toFixed(1)} MPa`, sf >= 2 ? 'ok' : 'warn');

      setStep('optimize', 'active');
      addLog('⚡ Running closed-loop redesign…');
      const BASE2 = api.BASE;
      const redesignRes = await fetch(`${BASE2}/api/run-pipeline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ specification: spec }),
      }).then(r => r.json());

      setStep('optimize', 'done');
      setStep('reconstruct', 'done');
      setStep('report', 'done');

      const pState = redesignRes?.state;
      const latestFea = pState?.design_history?.iterations?.at(-1)?.fea_result;
      if (latestFea) {
        setFeaResult(latestFea);
        addLog(
          `✓ Redesign: SF=${latestFea.safety_factor?.toFixed(2)}, σ=${latestFea.max_stress_mpa?.toFixed(1)} MPa`,
          latestFea.safety_factor >= 2 ? 'ok' : 'warn',
        );
      } else {
        addLog('✓ Redesign pipeline complete', 'ok');
      }
      showToast('Redesign complete!', 'ok');

    } catch (err) {
      setError(err.message);
      addLog(`✗ Redesign error: ${err.message}`, 'error');
      showToast(err.message, 'error', 8000);
      setStepStates(s => {
        const next = { ...s };
        for (const k of Object.keys(next)) if (next[k] === 'active') next[k] = 'error';
        return next;
      });
    } finally {
      setLoading(false);
    }
  }, [spec, showToast]);

  // ── Standalone FEA ───────────────────────────────────────────────
  const runFEAOnly = useCallback(async () => {
    if (!spec) return;
    setLoading(true);
    setError(null);
    try {
      addLog('🔬 Running FEA…');
      const res = await api.runFEA(spec);
      const resData = res.fea_result ?? res;
      setFeaResult(resData);
      addLog(`✓ FEA: SF=${resData.safety_factor?.toFixed(2)}`, 'ok');
      showToast(`FEA: SF=${resData.safety_factor?.toFixed(2)}`, 'ok');
    } catch (err) {
      setError(err.message);
      showToast(err.message, 'error', 8000);
    } finally {
      setLoading(false);
    }
  }, [spec, showToast]);

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className="app-shell">

      {/* ─── Toast Notifications ──────────────────────────────────── */}
      <Toast toasts={toasts} onDismiss={dismissToast} />

      {/* ─── Top Bar ──────────────────────────────────────────────── */}
      <header className="topbar">
        <div className="topbar-logo">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="url(#grad)" strokeWidth="2">
            <defs>
              <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#8b5cf6" />
                <stop offset="100%" stopColor="#06b6d4" />
              </linearGradient>
            </defs>
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          Agentic CAD
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '4px' }}>
          AI-Powered Structural Optimizer
        </span>
        <div className="topbar-spacer" />
        <BackendStatus status={backendStatus} busy={loading} />
        <div className="divider" style={{ width: '1px', height: '20px', margin: '0 12px', background: 'var(--border-subtle)' }} />
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          Phases 1–10 ✓
        </span>
      </header>

      {/* ─── Sidebar ──────────────────────────────────────────────── */}
      <nav className="sidebar">
        <NavIcon active={view === 'design'} onClick={() => setView('design')} tooltip="Design" id="nav-design">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
            <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
          </svg>
        </NavIcon>
        <NavIcon active={view === 'history'} onClick={() => setView('history')} tooltip="History" id="nav-history"
          badge={!!topoResult}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
        </NavIcon>
        <NavIcon active={view === 'review'} onClick={() => setView('review')} tooltip="Review" id="nav-review"
          badge={!!feaResult}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 11l3 3L22 4" />
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
        </NavIcon>
        <div className="sidebar-spacer" />
        <NavIcon active={settingsOpen} onClick={() => setSettingsOpen(true)} tooltip="Settings" id="nav-settings">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0 1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l-.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </NavIcon>
      </nav>

      {/* ─── Main Content ─────────────────────────────────────────── */}
      <main className="main-content">

        {view === 'design' && (
          <>
            {/* Left Panel */}
            <div className="left-panel">
              <RequirementInput onSubmit={runPipeline} loading={loading} />
              <SpecForm spec={spec} onChange={setSpec} onRunFEA={runFEAOnly} loading={loading} />
              <PipelineStatus stepStates={stepStates} log={log} />
            </div>

            {/* Center — 3D Viewer */}
            <div className="center-panel">
              {!stlUrl && !loading ? (
                <EmptyState
                  icon="🏗️"
                  title="No Model Loaded"
                  subtitle="Enter a natural language requirement above to generate and analyse a CAD model."
                  suggestion="Try: 'Aluminum L-bracket 150mm, 10kN load, SF ≥ 3'"
                />
              ) : (
                <ModelViewer stlUrl={stlUrl} label={stlLabel} />
              )}
            </div>

            {/* Right Panel */}
            <div className="right-panel">
              {/* Error card with retry */}
              {error && (
                <div className="glass-card fade-in" style={{
                  padding: '14px', borderColor: 'rgba(239,68,68,0.3)',
                  background: 'rgba(239,68,68,0.05)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <div className="badge badge-red">Pipeline Error</div>
                    {lastDescription && (
                      <button onClick={retryPipeline}
                        style={{
                          fontSize: '10px', padding: '4px 10px', borderRadius: '6px',
                          background: 'rgba(139,92,246,0.15)', border: '1px solid rgba(139,92,246,0.35)',
                          color: 'var(--accent-purple)', cursor: 'pointer',
                        }}>↺ Retry</button>
                    )}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--accent-red)', lineHeight: '1.6' }}>{error}</div>
                  {backendStatus === 'error' && (
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '6px', lineHeight: '1.5' }}>
                      ⚠ Backend appears offline. Run:<br />
                      <code style={{ color: 'var(--accent-cyan)', fontSize: '9px' }}>
                        .\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
                      </code>
                    </div>
                  )}
                </div>
              )}

              {!feaResult && !loading && !error && (
                <EmptyState
                  icon="📊"
                  title="No Results Yet"
                  subtitle="Results will appear here after the pipeline completes."
                />
              )}

              <ResultsPanel
                feaResult={feaResult}
                topoResult={topoResult}
                onNavigateToHistory={() => setView('history')}
              />
            </div>
          </>
        )}

        {view === 'history' && (
          <div style={{ gridColumn: '1 / -1', overflow: 'hidden' }}>
            {!feaResult && !topoResult ? (
              <div style={{ padding: '60px 40px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <EmptyState
                  icon="📈"
                  title="No History Yet"
                  subtitle="Run the pipeline first to see FEA results and topology optimization history here."
                  suggestion="Go to the Design tab and enter a requirement"
                />
              </div>
            ) : (
              <OptimizationHistory
                feaResult={feaResult}
                topoResult={topoResult}
                spec={spec}
                log={log}
              />
            )}
          </div>
        )}

        {view === 'review' && (
          <div style={{ gridColumn: '1 / -1', overflow: 'hidden' }}>
            {!spec ? (
              <div style={{ padding: '60px 40px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <EmptyState
                  icon="🔍"
                  title="No Design to Review"
                  subtitle="Complete the pipeline first to generate a design ready for human review."
                  suggestion="Go to the Design tab and enter a requirement"
                />
              </div>
            ) : (
              <HumanReview
                spec={spec}
                feaResult={feaResult}
                topoResult={topoResult}
                loading={loading}
                onApprove={({ note }) => {
                  addLog(`✓ Design approved${note ? ': ' + note : ''}`, 'ok');
                  showToast('Design approved ✓', 'ok', 5000);
                }}
                onReject={runRedesign}
              />
            )}
          </div>
        )}

      </main>

      {/* ─── Global AI Chatbot ──────────────────────────────────────── */}
      <ChatPanel
        spec={spec}
        feaResult={feaResult}
        topoResult={topoResult}
        isOpen={chatOpen}
        onToggle={() => setChatOpen(o => !o)}
      />

      {/* ─── Settings Modal ────────────────────────────────────────── */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />

    </div>
  );
}
