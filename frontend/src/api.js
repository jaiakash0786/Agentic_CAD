/**
 * API client — all calls to the FastAPI backend (localhost:8000)
 */
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = {
  async interpret(description) {
    const res = await fetch(`${BASE}/api/interpret`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirement: description }),   // backend expects "requirement"
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async validate(spec) {
    const res = await fetch(`${BASE}/api/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(spec),   // DesignSpecification model directly
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async generateCAD(spec) {
    const res = await fetch(`${BASE}/api/generate-cad`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ specification: spec }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async runFEA(spec) {
    const res = await fetch(`${BASE}/api/run-fea`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ specification: spec }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async runOptimize(spec, options = {}) {
    const res = await fetch(`${BASE}/api/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        specification: spec,
        volume_fraction: options.volume_fraction ?? 0.4,
        penalty: options.penalty ?? 3.0,
        max_iter: options.max_iter ?? 40,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async generateReport(spec, feaResult, topoResult) {
    const res = await fetch(`${BASE}/api/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        specification: spec,
        fea_result: feaResult || null,
        topo_result: topoResult || null,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async sendChatMessage(messages, spec, feaResult, topoResult) {
    const res = await fetch(`${BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages,
        specification: spec || null,
        fea_result: feaResult || null,
        topo_result: topoResult || null,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async runPipeline(description) {
    const res = await fetch(`${BASE}/api/run-pipeline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirement: description }),   // backend expects "requirement"
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  fileUrl(path) {
    if (!path) return null;
    const filename = path.split(/[\\\/]/).pop();
    return `${BASE}/files/${filename}`;
  },

  stlUrl(relativePath) {
    if (!relativePath) return null;
    return `${BASE}${relativePath}`;
  },
};

export default api;
