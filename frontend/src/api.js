import { invoke, isTauri } from "@tauri-apps/api/core";

const DEFAULT_API_BASE =
  import.meta.env.VITE_API_BASE ||
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000");
const API_BASE_KEY = "oratioviva_api_base";
let apiBaseCache = null;

export function getApiBase() {
  if (apiBaseCache) return apiBaseCache;
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem(API_BASE_KEY);
    if (stored) {
      apiBaseCache = stored;
      return stored;
    }
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
    if (typeof window !== "undefined") {
      window.localStorage.setItem(API_BASE_KEY, base);
    }
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

export async function getApiBaseAsync() {
  return resolveApiBase();
}
