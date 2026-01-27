import { invoke, isTauri } from "@tauri-apps/api/core";

const DEFAULT_API_BASE =
  import.meta.env.VITE_API_BASE ||
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000");
const API_BASE_KEY = "oratioviva_api_base";
let apiBaseCache = null;

const storage = {
  get(key) {
    if (typeof window === "undefined") return null;
    try {
      return window.localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key, value) {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(key, value);
    } catch {}
  },
};

export function getApiBase() {
  if (apiBaseCache) return apiBaseCache;
  const stored = storage.get(API_BASE_KEY);
  if (stored) {
    apiBaseCache = stored;
    return stored;
  }
  return DEFAULT_API_BASE;
}

export async function resolveApiBase() {
  let base = apiBaseCache || DEFAULT_API_BASE;

  // Prefer Tauri IPC when running inside the desktop app.
  // In Tauri v2 `window.__TAURI__` is only available when `app.withGlobalTauri` is enabled.
  if (typeof window !== "undefined") {
    try {
      if (window.__TAURI__?.invoke) {
        const tauriBase = await window.__TAURI__.invoke("get_api_base");
        if (tauriBase) base = tauriBase;
      } else if (isTauri()) {
        const tauriBase = await invoke("get_api_base");
        if (tauriBase) base = tauriBase;
      }
    } catch {
      // fallback to cached/default base
    }
  }
  if (base !== apiBaseCache) {
    apiBaseCache = base;
    storage.set(API_BASE_KEY, base);
  }
  return base;
}

async function jsonFetch(path, options = {}) {
  try {
    const base = await resolveApiBase();
    const resp = await fetch(`${base}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (!resp.ok) {
      const detail = await resp.text();
      throw new Error(detail || `Request failed (${resp.status})`);
    }
    return resp.json();
  } catch (err) {
    if (err.message.includes("Failed to fetch") || err.message.includes("network")) {
      throw new Error("Backend non connecte. Veuillez demarrer le serveur backend.");
    }
    throw err;
  }
}

export async function fetchVoices() {
  return jsonFetch("/voices");
}

export async function fetchHistory(limit = 12) {
  return jsonFetch(`/history?limit=${limit}`);
}

export async function fetchJobs(limit = 12) {
  return jsonFetch(`/jobs?limit=${limit}`);
}

export async function createSynthesis(payload, { asyncMode = true } = {}) {
  const params = asyncMode ? "?async_mode=true" : "?async_mode=false";
  return jsonFetch(`/synthesize${params}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createLongSynthesis(payload, { asyncMode = true } = {}) {
  return jsonFetch("/synthesize/long", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchJob(jobId) {
  return jsonFetch(`/jobs/${jobId}`);
}

export async function fetchModelStatus() {
  return jsonFetch("/models/status");
}

export async function downloadModels(models) {
  return jsonFetch("/models/download", {
    method: "POST",
    body: JSON.stringify(models ? { models } : {}),
  });
}

export async function cancelDownload() {
  const base = await resolveApiBase();
  const resp = await fetch(`${base}/models/download/cancel`, { method: "POST" });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || "Cancel failed");
  }
  return resp.json();
}

export async function deleteDownloadedModel(models) {
  return jsonFetch("/models/download", {
    method: "DELETE",
    body: JSON.stringify({ models: Array.isArray(models) ? models : [models] }),
  });
}

export async function fetchAnalytics() {
  return jsonFetch("/analytics");
}

export async function fetchSettings() {
  return jsonFetch("/settings");
}

export async function saveHfToken(token) {
  return jsonFetch("/settings/token", {
    method: "POST",
    body: JSON.stringify({ hf_token: token }),
  });
}

export async function deleteHistory(jobId) {
  const base = await resolveApiBase();
  const resp = await fetch(`${base}/history/${jobId}`, { method: "DELETE" });
  if (!resp.ok) {
    throw new Error("Suppression impossible");
  }
  return true;
}

export async function deleteJob(jobId) {
  const base = await resolveApiBase();
  const resp = await fetch(`${base}/jobs/${jobId}`, { method: "DELETE" });
  if (!resp.ok) {
    throw new Error("Suppression impossible");
  }
  return true;
}

export async function deleteJobsBatch(ids) {
  const base = await resolveApiBase();
  const resp = await fetch(`${base}/jobs/batch_delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: ids }),
  });
  if (!resp.ok) {
    throw new Error("Suppression jobs impossible");
  }
  return resp.json();
}

export async function deleteHistoryBatch(ids, deleteAudio = true) {
  const base = await resolveApiBase();
  const resp = await fetch(`${base}/history/batch_delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: ids, delete_audio: deleteAudio }),
  });
  if (!resp.ok) {
    throw new Error("Suppression historique impossible");
  }
  return resp.json();
}

export async function exportZip(jobIds) {
  const base = await resolveApiBase();
  const resp = await fetch(`${base}/export/zip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
  if (!resp.ok) {
    throw new Error("Export impossible");
  }
  const blob = await resp.blob();
  const url = window.URL.createObjectURL(blob);
  return url;
}

export async function exportMp3(jobIds) {
  const base = await resolveApiBase();
  const resp = await fetch(`${base}/export/mp3`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
  if (!resp.ok) {
    throw new Error("MP3 export failed");
  }
  const blob = await resp.blob();
  const url = window.URL.createObjectURL(blob);
  return url;
}

export async function getApiBaseAsync() {
  return resolveApiBase();
}

export async function fetchPresets() {
  return jsonFetch("/presets");
}

export async function saveTonePreset(preset) {
  return jsonFetch("/presets/tones", {
    method: "POST",
    body: JSON.stringify(preset),
  });
}

export async function deleteTonePreset(presetId) {
  const base = await resolveApiBase();
  const resp = await fetch(`${base}/presets/tones/${presetId}`, { method: "DELETE" });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || "Delete failed");
  }
  return resp.json();
}

export async function savePromptPreset(preset) {
  return jsonFetch("/presets/prompts", {
    method: "POST",
    body: JSON.stringify(preset),
  });
}

export async function deletePromptPreset(presetId) {
  const base = await resolveApiBase();
  const resp = await fetch(`${base}/presets/prompts/${presetId}`, { method: "DELETE" });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || "Delete failed");
  }
  return resp.json();
}

export async function fetchModelCapabilities(modelName) {
  return jsonFetch(`/presets/model-capabilities?model_name=${encodeURIComponent(modelName || "")}`);
}

export async function fetchDiagnostics() {
  return jsonFetch("/diagnostics");
}

export async function runCleanup(options) {
  return jsonFetch("/maintenance/cleanup", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export async function getTelemetrySettings() {
  return jsonFetch("/settings/telemetry");
}

export async function setTelemetrySettings(settings) {
  return jsonFetch("/settings/telemetry", {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

export async function createChain(items, parallel = false) {
  return jsonFetch("/synthesize/chain", {
    method: "POST",
    body: JSON.stringify({ items, parallel }),
  });
}

export async function fetchChainStatus(chainId) {
  return jsonFetch(`/chains/${chainId}/status`);
}

export async function exportManifest(jobIds, format = "csv") {
  const base = await resolveApiBase();
  const resp = await fetch(`${base}/export/manifest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds, format }),
  });
  if (!resp.ok) {
    throw new Error("Export manifest failed");
  }
  const blob = await resp.blob();
  const ext = format === "csv" ? "csv" : "json";
  const filename = `oratioviva-manifest.${ext}`;
  const url = window.URL.createObjectURL(blob);
  return { url, filename };
}

export async function submitReport(report) {
  return jsonFetch("/reports/submit", {
    method: "POST",
    body: JSON.stringify(report),
  });
}

export async function fetchReports(status = null, limit = 50) {
  const base = await resolveApiBase();
  let url = `${base}/reports?limit=${limit}`;
  if (status) {
    url += `&status=${encodeURIComponent(status)}`;
  }
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error("Failed to fetch reports");
  }
  return resp.json();
}

export async function updateReportStatus(reportId, status) {
  const base = await resolveApiBase();
  const resp = await fetch(`${base}/reports/${reportId}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!resp.ok) {
    throw new Error("Failed to update report status");
  }
  return resp.json();
}
