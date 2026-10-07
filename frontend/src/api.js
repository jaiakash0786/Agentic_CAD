/**
 * API client — all calls to the FastAPI backend
 * Phase 10: Added timeout, retry logic, and backend health check
 *
 * BUG 8 FIX: BASE URL is now read dynamically from localStorage (via Settings modal)
 * so users can change the API endpoint at runtime without reloading.
 *
 * BUG 6 FIX: fileUrl() now preserves the full relative path instead of stripping subdirs.
 */

// ─── Dynamic base URL (reads from localStorage on every call) ────────────────

function getBase() {
  try {
    const saved = localStorage.getItem('agentic_cad_settings');
    if (saved) {
      const parsed = JSON.parse(saved);
      if (parsed.apiUrl) {
        let url = parsed.apiUrl.replace(/\/$/, '');
        if (typeof window !== 'undefined' && window.location?.hostname && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
          url = url.replace('localhost', window.location.hostname).replace('127.0.0.1', window.location.hostname);
        }
        return url;
      }
    }
  } catch {
    // ignore parse errors
  }
  if (typeof window !== 'undefined' && window.location?.hostname && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    return `http://${window.location.hostname}:8000`;
  }
  return import.meta.env.VITE_API_URL || 'http://localhost:8000';
}

// ─── Fetch with timeout + retry ─────────────────────────────────────────────

async function fetchWithTimeout(url, options = {}, timeoutMs = 120_000) {
  const controller = new AbortController();
  const tid = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error(`Request timed out after ${timeoutMs / 1000}s. The backend may be overloaded — please try again.`);
    }
    if (!navigator.onLine) {
      throw new Error('No internet connection. Please check your network and try again.');
    }
    throw new Error(`Network error: ${err.message}. Is the backend running on ${getBase()}?`);
  } finally {
    clearTimeout(tid);
  }
}

async function apiFetch(url, options = {}, { timeoutMs = 120_000, retries = 1 } = {}) {
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetchWithTimeout(url, options, timeoutMs);
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const body = await res.text();
          // Try parse JSON error detail from FastAPI
          const parsed = JSON.parse(body);
          detail = parsed?.detail || parsed?.error || body;
        } catch {
          // raw text already in detail
        }
        throw new Error(detail);
      }
      return res.json();
    } catch (err) {
      lastErr = err;
      if (attempt < retries) {
        // Exponential backoff: 500ms, 1000ms ...
        await new Promise(r => setTimeout(r, 500 * Math.pow(2, attempt)));
      }
    }
  }
  throw lastErr;
}

// ─── Health check ────────────────────────────────────────────────────────────

async function checkHealth() {
  try {
    const res = await fetchWithTimeout(`${getBase()}/health`, { method: 'GET' }, 5000);
    return res.ok;
  } catch {
    return false;
  }
}

// ─── API methods ─────────────────────────────────────────────────────────────

const api = {
  // BASE is a getter so it always reflects the current settings value
  get BASE() { return getBase(); },
  checkHealth,

  async interpret(description) {
    return apiFetch(`${getBase()}/api/interpret`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirement: description }),
    }, { timeoutMs: 30_000, retries: 1 });
  },

  async validate(spec) {
    return apiFetch(`${getBase()}/api/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(spec),
    }, { timeoutMs: 15_000, retries: 1 });
  },

  async generateCAD(spec) {
    return apiFetch(`${getBase()}/api/generate-cad`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ specification: spec }),
    }, { timeoutMs: 60_000, retries: 0 });
  },

  async runFEA(spec) {
    return apiFetch(`${getBase()}/api/run-fea`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ specification: spec }),
    }, { timeoutMs: 120_000, retries: 0 });
  },

  async runOptimize(spec, options = {}) {
    return apiFetch(`${getBase()}/api/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        specification: spec,
        volume_fraction: options.volume_fraction ?? 0.4,
        penalty: options.penalty ?? 3.0,
        max_iter: options.max_iter ?? 15,
      }),
    }, { timeoutMs: 300_000, retries: 0 });
  },

  async generateReport(spec, feaResult, topoResult) {
    return apiFetch(`${getBase()}/api/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        specification: spec,
        fea_result: feaResult || null,
        topo_result: topoResult || null,
      }),
    }, { timeoutMs: 30_000, retries: 1 });
  },

  async sendChatMessage(messages, spec, feaResult, topoResult) {
    return apiFetch(`${getBase()}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages,
        specification: spec || null,
        fea_result: feaResult || null,
        topo_result: topoResult || null,
      }),
    }, { timeoutMs: 30_000, retries: 1 });
  },

  async runPipeline(description) {
    return apiFetch(`${getBase()}/api/run-pipeline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirement: description }),
    }, { timeoutMs: 300_000, retries: 0 });
  },

  /**
   * BUG 6 FIX: fileUrl now accepts a relative URL path (e.g. "/files/cad/part.stl")
   * and prepends the dynamic base — no longer strips the subdirectory.
   */
  fileUrl(relativePath) {
    if (!relativePath) return null;
    return `${getBase()}${relativePath}`;
  },

  stlUrl(relativePath) {
    if (!relativePath) return null;
    return `${getBase()}${relativePath}`;
  },
};

export default api;
