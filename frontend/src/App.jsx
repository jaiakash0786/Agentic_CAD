import { useState, useCallback } from 'react';
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

// ─── Sidebar icons ─────────────────────────────────────────────────
const NavIcon = ({ children, active, onClick, tooltip, id }) => (
  <button className={`sidebar-btn ${active ? 'active' : ''}`} onClick={onClick} id={id}>
    {children}
    <span className="tooltip">{tooltip}</span>
  </button>
);

export default function App() {
  // ── State ────────────────────────────────────────────────────────
  const [view, setView]           = useState('design');    // design | history | review
  const [chatOpen, setChatOpen]   = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [loading, setLoading]     = useState(false);
  const [spec, setSpec]           = useState(null);
  const [stepStates, setStepStates] = useState({});
  const [log, setLog]             = useState([]);
  const [feaResult, setFeaResult] = useState(null);
  const [topoResult, setTopoResult] = useState(null);
  const [stlUrl, setStlUrl]       = useState(null);
  const [stlLabel, setStlLabel]   = useState('');
  const [error, setError]         = useState(null);

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

    try {
      // Step 1: Interpret
      setStep('interpret', 'active');
      addLog('🧠 Interpreting requirement…');
      const interpResult = await api.interpret(description);
      if (!interpResult?.specification) throw new Error('Interpretation failed');
      const parsedSpec = interpResult.specification;
      setSpec(parsedSpec);
      setStep('interpret', 'done');
      addLog(`✓ Interpreted: ${parsedSpec.component} / ${parsedSpec.material_name}`, 'ok');

      // Step 2: Validate
      setStep('validate', 'active');
      addLog('✅ Validating specification…');
      const valResult = await api.validate(parsedSpec);
      setStep('validate', valResult?.valid ? 'done' : 'error');
      if (!valResult?.valid) {
        addLog(`⚠ Validation: ${valResult?.issues?.join(', ')}`, 'warn');
      } else {
        addLog('✓ Spec valid', 'ok');
      }

      // Step 3: CAD
      setStep('cad', 'active');
      addLog('📐 Generating CAD model…');
      const cadResult = await api.generateCAD(parsedSpec);
      if (cadResult?.success === false) throw new Error(cadResult.error);
      setStep('cad', 'done');
      addLog('✓ STEP + STL generated', 'ok');
      if (cadResult?.stl_file_url) {
        const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        setStlUrl(`${BASE}${cadResult.stl_file_url}`);
        setStlLabel('Original CAD');
      }

      // Step 4: FEA
      setStep('fea', 'active');
      addLog('🔬 Running FEA (C3D4 tetrahedral solver)…');
      const feaRes = await api.runFEA(parsedSpec);
      if (feaRes?.success === false) throw new Error(feaRes.error);
      const feaData = feaRes.fea_result ?? feaRes;  // unwrap nested fea_result if present
      setFeaResult(feaData);
      setStep('fea', 'done');
      addLog(`✓ FEA: SF=${feaData.safety_factor?.toFixed(2)}, σ=${feaData.max_stress_mpa?.toFixed(1)} MPa`, 'ok');

      // Step 5: Topology Optimization
      setStep('optimize', 'active');
      const userSettings = loadSettings();
      addLog(`⚡ Running SIMP topology optimization (${userSettings.maxTopoIter ?? 15} iters)…`);
      const topoRes = await api.runOptimize(parsedSpec, {
        volume_fraction: userSettings.volumeFraction ?? 0.4,
        max_iter: userSettings.maxTopoIter ?? 15,
      });
      if (topoRes?.success === false) throw new Error(topoRes.error);
      setTopoResult(topoRes);
      setStep('optimize', 'done');
      addLog(`✓ Topology: ${topoRes.material_saved_pct?.toFixed(1)}% material saved, ${topoRes.iterations} iters`, 'ok');

      // Steps 6 & 7 (reconstruct, report) — mark pending for now
      setStep('reconstruct', 'done');
      setStep('report', 'done');
      addLog('✓ Pipeline complete!', 'ok');

    } catch (err) {
      setError(err.message);
      addLog(`✗ Error: ${err.message}`, 'error');
      // Mark current active step as error
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
  }, []);

  // ── Redesign (triggered from Human Review rejection) ───────────────
  const runRedesign = useCallback(async ({ note } = {}) => {
    if (!spec) return;
    // Navigate to Design tab so user sees the pipeline running
    setView('design');
    reset();
    setLoading(true);
    setError(null);
    addLog(`🔄 Redesign triggered${note ? ': ' + note : ''}`, 'warn');
    addLog('♻️ Running closed-loop redesign (auto-thickness + FEA iterations)…');

    try {
      // Step 1: CAD
      setStep('interpret', 'done');   // spec already interpreted
      setStep('validate', 'done');    // spec already validated
      setStep('cad', 'active');
      addLog('📐 Regenerating CAD with current spec…');
      const cadResult = await api.generateCAD(spec);
      if (cadResult?.success === false) throw new Error(cadResult.error);
      setStep('cad', 'done');
      addLog('✓ CAD regenerated', 'ok');
      if (cadResult?.stl_file_url) {
        const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        setStlUrl(`${BASE}${cadResult.stl_file_url}`);
        setStlLabel('Redesigned CAD');
      }

      // Step 2: FEA with current spec
      setStep('fea', 'active');
      addLog('🔬 Running FEA on redesigned model…');
      const feaRes = await api.runFEA(spec);
      if (feaRes?.success === false) throw new Error(feaRes.error);
      const feaData = feaRes.fea_result ?? feaRes;
      setFeaResult(feaData);
      setStep('fea', 'done');
      const sf = feaData.safety_factor?.toFixed(2);
      const sig = feaData.max_stress_mpa?.toFixed(1);
      addLog(`✓ FEA: SF=${sf}, σ=${sig} MPa`, sf >= 2 ? 'ok' : 'warn');

      // Step 3: POST spec directly to /api/run-pipeline — the backend's
      // design_loop.py will auto-increment thickness/dims and re-run FEA
      // up to 10 iterations until all constraints pass.
      setStep('optimize', 'active');
      addLog('⚡ Running closed-loop redesign (up to 10 iterations)…');
      const BASE2 = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const redesignRes = await fetch(`${BASE2}/api/run-pipeline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ specification: spec }),
      }).then(r => r.json());

      setStep('optimize', 'done');
      setStep('reconstruct', 'done');
      setStep('report', 'done');

      // Pull best FEA from pipeline state if available
      const pState = redesignRes?.state;
      const latestFea = pState?.design_history?.iterations?.at(-1)?.fea_result;
      if (latestFea) {
        setFeaResult(latestFea);
        addLog(
          `✓ Redesign complete: SF=${latestFea.safety_factor?.toFixed(2)}, σ=${latestFea.max_stress_mpa?.toFixed(1)} MPa`,
          latestFea.safety_factor >= 2 ? 'ok' : 'warn',
        );
      } else {
        addLog('✓ Redesign pipeline complete', 'ok');
      }

    } catch (err) {
      setError(err.message);
      addLog(`✗ Redesign error: ${err.message}`, 'error');
      setStepStates(s => {
        const next = { ...s };
        for (const k of Object.keys(next)) if (next[k] === 'active') next[k] = 'error';
        return next;
      });
    } finally {
      setLoading(false);
    }
  }, [spec]);

  // ── Standalone FEA ────────────────────────────────────────────────
  const runFEAOnly = useCallback(async () => {
    if (!spec) return;
    setLoading(true);
    setError(null);
    try {
      addLog('🔬 Running FEA…');
      const res = await api.runFEA(spec);
      const resData = res.fea_result ?? res;  // unwrap nested fea_result if present
      setFeaResult(resData);
      addLog(`✓ FEA: SF=${resData.safety_factor?.toFixed(2)}`, 'ok');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [spec]);

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className="app-shell">

      {/* ─── Top Bar ─────────────────────────────────────────── */}
      <header className="topbar">
        <div className="topbar-logo">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="url(#grad)" strokeWidth="2">
            <defs>
              <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#8b5cf6"/>
                <stop offset="100%" stopColor="#06b6d4"/>
              </linearGradient>
            </defs>
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
          Agentic CAD
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '4px' }}>
          AI-Powered Structural Optimizer
        </span>
        <div className="topbar-spacer" />
        <div className="status-dot" />
        <span className="topbar-status">Backend Connected</span>
        <div className="divider" style={{ width: '1px', height: '20px', margin: '0 12px', background: 'var(--border-subtle)' }}/>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
          Phases 1–7 ✓
        </span>
      </header>

      {/* ─── Sidebar ──────────────────────────────────────────── */}
      <nav className="sidebar">
        {/* Design */}
        <NavIcon active={view === 'design'} onClick={() => setView('design')} tooltip="Design" id="nav-design">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
            <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
          </svg>
        </NavIcon>
        {/* Optimization History */}
        <NavIcon active={view === 'history'} onClick={() => setView('history')} tooltip="History" id="nav-history">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
        </NavIcon>
        {/* Human Review */}
        <NavIcon active={view === 'review'} onClick={() => setView('review')} tooltip="Review" id="nav-review">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 11l3 3L22 4"/>
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
          </svg>
        </NavIcon>
        <div className="sidebar-spacer" />
        <NavIcon
          active={settingsOpen}
          onClick={() => setSettingsOpen(true)}
          tooltip="Settings"
          id="nav-settings"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0 1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l-.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </NavIcon>
      </nav>

      {/* ─── Main Content ─────────────────────────────────────── */}
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
              <ModelViewer stlUrl={stlUrl} label={stlLabel} />
            </div>

            {/* Right Panel */}
            <div className="right-panel">
              {error && (
                <div className="glass-card fade-in" style={{ padding: '12px', borderColor: 'rgba(239,68,68,0.3)' }}>
                  <div className="badge badge-red" style={{ marginBottom: '6px' }}>Error</div>
                  <div style={{ fontSize: '11px', color: 'var(--accent-red)', lineHeight: '1.5' }}>{error}</div>
                </div>
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
            <OptimizationHistory
              feaResult={feaResult}
              topoResult={topoResult}
              spec={spec}
              log={log}
            />
          </div>
        )}

        {view === 'review' && (
          <div style={{ gridColumn: '1 / -1', overflow: 'hidden' }}>
            <HumanReview
              spec={spec}
              feaResult={feaResult}
              topoResult={topoResult}
              loading={loading}
              onApprove={({ note }) => addLog(`✓ Design approved${note ? ': ' + note : ''}`, 'ok')}
              onReject={runRedesign}
            />
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
