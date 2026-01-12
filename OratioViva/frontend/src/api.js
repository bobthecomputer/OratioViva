const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function jsonFetch(path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || `Request failed (${resp.status})`);
  }
  return resp.json();
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

export async function deleteHistory(jobId) {
  const resp = await fetch(`${API_BASE}/history/${jobId}`, { method: "DELETE" });
  if (!resp.ok) {
    throw new Error("Suppression impossible");
  }
  return true;
}

export async function deleteJob(jobId) {
  const resp = await fetch(`${API_BASE}/jobs/${jobId}`, { method: "DELETE" });
  if (!resp.ok) {
    throw new Error("Suppression impossible");
  }
  return true;
}

export async function deleteJobsBatch(ids) {
  const resp = await fetch(`${API_BASE}/jobs/batch_delete`, {
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
  const resp = await fetch(`${API_BASE}/history/batch_delete`, {
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
  const resp = await fetch(`${API_BASE}/export/zip`, {
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

export function getApiBase() {
  return API_BASE;
}
