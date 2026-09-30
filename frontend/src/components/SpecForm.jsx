import { useState } from 'react';

const MATERIALS = [
  { value: 'aluminum_6061_t6',  label: 'Aluminum 6061-T6' },
  { value: 'aluminum_7075_t6',  label: 'Aluminum 7075-T6' },
  { value: 'steel_mild',        label: 'Mild Steel (S235)' },
  { value: 'steel_stainless',   label: 'Stainless Steel 316' },
  { value: 'titanium_grade5',   label: 'Titanium Grade 5' },
];

const COMPONENTS = [
  { value: 'l_bracket',         label: 'L-Bracket' },
  { value: 'rectangular_plate', label: 'Rectangular Plate' },
  { value: 'cantilever_beam',   label: 'Cantilever Beam' },
  { value: 'circular_plate',    label: 'Circular Plate' },
];

const DIRECTIONS = [
  { value: 'negative_y', label: '−Y (Downward)' },
  { value: 'positive_y', label: '+Y (Upward)' },
  { value: 'negative_z', label: '−Z (Into page)' },
  { value: 'positive_z', label: '+Z (Out of page)' },
  { value: 'negative_x', label: '−X (Left)' },
  { value: 'positive_x', label: '+X (Right)' },
];

export default function SpecForm({ spec, onChange, onRunFEA, loading }) {
  const [open, setOpen] = useState(false);
  if (!spec) return null;

  const update = (path, val) => {
    const next = JSON.parse(JSON.stringify(spec));
    const keys = path.split('.');
    let obj = next;
    for (let i = 0; i < keys.length - 1; i++) obj = obj[keys[i]];
    obj[keys[keys.length - 1]] = val;
    onChange(next);
  };

  return (
    <div className="glass-card" style={{ padding: '14px' }}>
      <button
        className="btn-secondary"
        style={{ width: '100%', justifyContent: 'space-between', marginBottom: open ? '12px' : 0 }}
        onClick={() => setOpen(o => !o)}
        id="spec-form-toggle"
      >
        <span>⚙️ Edit Specification</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="fade-in">
          <div className="spec-grid">
            <div className="form-field">
              <label className="form-label">Component</label>
              <select className="form-select" value={spec.component || ''} id="component-select"
                onChange={e => update('component', e.target.value)}>
                {COMPONENTS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div className="form-field">
              <label className="form-label">Material</label>
              <select className="form-select" value={spec.material_name || ''} id="material-select"
                onChange={e => update('material_name', e.target.value)}>
                {MATERIALS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </div>

            <div className="form-field">
              <label className="form-label">Length (mm)</label>
              <input className="form-input" type="number" id="dim-length"
                value={spec.dimensions?.length || ''} min="10" max="1000"
                onChange={e => update('dimensions.length', +e.target.value)} />
            </div>
            <div className="form-field">
              <label className="form-label">Width (mm)</label>
              <input className="form-input" type="number" id="dim-width"
                value={spec.dimensions?.width || ''} min="10" max="500"
                onChange={e => update('dimensions.width', +e.target.value)} />
            </div>
            <div className="form-field">
              <label className="form-label">Height (mm)</label>
              <input className="form-input" type="number" id="dim-height"
                value={spec.dimensions?.height || ''} min="10" max="500"
                onChange={e => update('dimensions.height', +e.target.value)} />
            </div>
            <div className="form-field">
              <label className="form-label">Thickness (mm)</label>
              <input className="form-input" type="number" id="dim-thickness"
                value={spec.dimensions?.thickness || ''} min="1" max="100"
                onChange={e => update('dimensions.thickness', +e.target.value)} />
            </div>

            <div className="form-field">
              <label className="form-label">Load (N)</label>
              <input className="form-input" type="number" id="load-magnitude"
                value={spec.loads?.[0]?.magnitude || ''} min="1"
                onChange={e => update('loads.0.magnitude', +e.target.value)} />
            </div>
            <div className="form-field">
              <label className="form-label">Direction</label>
              <select className="form-select" id="load-direction"
                value={spec.loads?.[0]?.direction || 'negative_y'}
                onChange={e => update('loads.0.direction', e.target.value)}>
                {DIRECTIONS.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </div>

            <div className="form-field">
              <label className="form-label">Min Safety Factor</label>
              <input className="form-input" type="number" id="min-sf"
                value={spec.constraints?.min_safety_factor || 2.0} min="0.5" max="10" step="0.1"
                onChange={e => update('constraints.min_safety_factor', +e.target.value)} />
            </div>
            <div className="form-field">
              <label className="form-label">Max Disp (mm)</label>
              <input className="form-input" type="number" id="max-disp"
                value={spec.constraints?.max_displacement_mm || 0.5} min="0.01" max="50" step="0.01"
                onChange={e => update('constraints.max_displacement_mm', +e.target.value)} />
            </div>

            <div className="form-field full" style={{ marginTop: '6px' }}>
              <button className="btn-primary" id="run-fea-btn"
                onClick={onRunFEA} disabled={loading}>
                {loading ? <><div className="spinner" />Running FEA…</> : '🔬 Run FEA Only'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
