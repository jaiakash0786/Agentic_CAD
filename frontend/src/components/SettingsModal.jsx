import { useState, useEffect } from 'react';

const DEFAULT_SETTINGS = {
  elementSize: 5.0,
  volumeFraction: 0.4,
  maxTopoIter: 15,
  minSafetyFactor: 2.0,
  apiUrl: 'http://localhost:8000',
};

export function loadSettings() {
  try {
    const saved = localStorage.getItem('agentic_cad_settings');
    if (saved) return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
  } catch (e) {
    console.error('Failed to load settings', e);
  }
  return DEFAULT_SETTINGS;
}

export function saveSettings(settings) {
  try {
    localStorage.setItem('agentic_cad_settings', JSON.stringify(settings));
  } catch (e) {
    console.error('Failed to save settings', e);
  }
}

export default function SettingsModal({ isOpen, onClose, onSettingsChange }) {
  const [settings, setSettings] = useState(loadSettings);
  const [testStatus, setTestStatus] = useState(null); // 'testing' | 'ok' | 'error'
  const [testMsg, setTestMsg] = useState('');

  useEffect(() => {
    if (isOpen) {
      setSettings(loadSettings());
      setTestStatus(null);
      setTestMsg('');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    saveSettings(settings);
    if (onSettingsChange) onSettingsChange(settings);
    onClose();
  };

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS);
    saveSettings(DEFAULT_SETTINGS);
    if (onSettingsChange) onSettingsChange(DEFAULT_SETTINGS);
  };

  const testBackend = async () => {
    setTestStatus('testing');
    setTestMsg('Connecting…');
    const t0 = performance.now();
    try {
      const res = await fetch(`${settings.apiUrl}/docs`, { method: 'HEAD' });
      const elapsed = Math.round(performance.now() - t0);
      if (res.ok || res.status === 200 || res.status === 307) {
        setTestStatus('ok');
        setTestMsg(`Connected (${elapsed}ms)`);
      } else {
        setTestStatus('error');
        setTestMsg(`HTTP ${res.status}`);
      }
    } catch (err) {
      setTestStatus('error');
      setTestMsg('Cannot reach backend');
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(5, 7, 15, 0.75)',
        backdropFilter: 'blur(8px)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
      onClick={e => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="glass-card fade-in"
        style={{
          width: '100%',
          maxWidth: '520px',
          background: 'var(--bg-elevated, #0f172a)',
          border: '1px solid var(--border-subtle, rgba(255,255,255,0.1))',
          borderRadius: '16px',
          boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-subtle, rgba(255,255,255,0.08))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '18px' }}>⚙️</span>
            <div>
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 600 }}>Preferences & Solver Settings</h3>
              <p style={{ margin: '2px 0 0', fontSize: '11px', color: 'var(--text-muted, #94a3b8)' }}>
                Configure mesh fidelity, SIMP parameters, and backend defaults
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="sidebar-btn"
            style={{ width: '30px', height: '30px', fontSize: '16px', lineHeight: 1 }}
          >
            ✕
          </button>
        </div>

        {/* Content Body */}
        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '18px', maxHeight: '70vh', overflowY: 'auto' }}>

          {/* Section 1: Mesh & FEA */}
          <div>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--accent-purple, #a855f7)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              🔬 Mesh & FEA Solver
            </div>

            <div className="form-field" style={{ marginBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <label className="form-label" style={{ margin: 0 }}>Default Mesh Element Size</label>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--accent-cyan, #06b6d4)' }}>
                  {settings.elementSize} mm
                </span>
              </div>
              <input
                type="range"
                min="2.0"
                max="12.0"
                step="0.5"
                value={settings.elementSize}
                onChange={e => handleChange('elementSize', parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent-purple, #a855f7)', cursor: 'pointer' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-muted, #94a3b8)', marginTop: '2px' }}>
                <span>Fine (2–3mm) · Slower</span>
                <span style={{ color: 'var(--accent-green, #10b981)' }}>Balanced (5mm) · 2-3s</span>
                <span>Fast (8–12mm)</span>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '6px' }}>
              {[
                { label: '⚡ Ultra Fast (8mm)', size: 8.0 },
                { label: '⚖️ Balanced (5mm)', size: 5.0 },
                { label: '🎯 Detailed (3mm)', size: 3.0 },
              ].map(preset => (
                <button
                  key={preset.size}
                  type="button"
                  className="btn-secondary"
                  style={{
                    flex: 1,
                    fontSize: '11px',
                    padding: '5px 8px',
                    borderColor: settings.elementSize === preset.size ? 'var(--accent-purple)' : 'transparent',
                    background: settings.elementSize === preset.size ? 'rgba(168,85,247,0.15)' : undefined,
                  }}
                  onClick={() => handleChange('elementSize', preset.size)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          <div className="divider" style={{ height: '1px', background: 'var(--border-subtle, rgba(255,255,255,0.08))' }} />

          {/* Section 2: Topology Optimization */}
          <div>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--accent-cyan, #06b6d4)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              ⚡ SIMP Topology Optimization
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div className="form-field">
                <label className="form-label">Target Volume Fraction</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    className="form-input"
                    type="number"
                    min="0.1"
                    max="0.9"
                    step="0.05"
                    value={settings.volumeFraction}
                    onChange={e => handleChange('volumeFraction', parseFloat(e.target.value))}
                  />
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    ({Math.round(settings.volumeFraction * 100)}%)
                  </span>
                </div>
              </div>

              <div className="form-field">
                <label className="form-label">Max Iterations</label>
                <input
                  className="form-input"
                  type="number"
                  min="5"
                  max="50"
                  value={settings.maxTopoIter}
                  onChange={e => handleChange('maxTopoIter', parseInt(e.target.value, 10))}
                />
              </div>
            </div>
          </div>

          <div className="divider" style={{ height: '1px', background: 'var(--border-subtle, rgba(255,255,255,0.08))' }} />

          {/* Section 3: Backend Endpoint */}
          <div>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #cbd5e1)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              🌐 Backend API Connection
            </div>

            <div className="form-field">
              <label className="form-label">API Base URL</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  className="form-input"
                  type="text"
                  value={settings.apiUrl}
                  onChange={e => handleChange('apiUrl', e.target.value)}
                  placeholder="http://localhost:8000"
                  style={{ flex: 1 }}
                />
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={testBackend}
                  style={{ whiteSpace: 'nowrap', fontSize: '11px', padding: '6px 12px' }}
                >
                  Test Ping
                </button>
              </div>
              {testStatus && (
                <div style={{
                  fontSize: '11px',
                  marginTop: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: testStatus === 'ok' ? 'var(--accent-green, #10b981)' : testStatus === 'testing' ? 'var(--accent-amber, #f59e0b)' : 'var(--accent-red, #ef4444)'
                }}>
                  <span>{testStatus === 'ok' ? '●' : testStatus === 'testing' ? '◌' : '●'}</span>
                  <span>{testMsg}</span>
                </div>
              )}
            </div>
          </div>

        </div>

        {/* Footer actions */}
        <div
          style={{
            padding: '14px 20px',
            borderTop: '1px solid var(--border-subtle, rgba(255,255,255,0.08))',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'rgba(0,0,0,0.15)',
          }}
        >
          <button
            type="button"
            className="btn-secondary"
            onClick={handleReset}
            style={{ fontSize: '11px', color: 'var(--text-muted)' }}
          >
            Reset Defaults
          </button>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              style={{ fontSize: '12px' }}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={handleSave}
              style={{ fontSize: '12px' }}
            >
              Save Settings
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
