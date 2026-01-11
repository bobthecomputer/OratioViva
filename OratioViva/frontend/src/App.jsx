import { useEffect, useMemo, useState } from "react";
import {
  createSynthesis,
  fetchHistory,
  fetchJob,
  fetchJobs,
  fetchVoices,
  deleteHistory,
  deleteJob,
  deleteHistoryBatch,
  deleteJobsBatch,
  exportZip,
  getApiBase,
} from "./api";

const POLL_INTERVAL_MS = 1200;

export default function App() {
  const [text, setText] = useState("");
  const [voices, setVoices] = useState([]);
  const [voiceId, setVoiceId] = useState("");
  const [speed, setSpeed] = useState(1);
  const [style, setStyle] = useState("");
  const [history, setHistory] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedHistory, setSelectedHistory] = useState(new Set());
  const [selectedJobs, setSelectedJobs] = useState(new Set());

  useEffect(() => {
    fetchVoices()
      .then((res) => {
        setVoices(res.voices || []);
        if (!voiceId && res.voices?.[0]) {
        setVoiceId(res.voices[0].id);
      }
    })
      .catch((err) => setStatus(err.message));
    refreshHistory();
    refreshJobs();
  }, []);

  async function refreshHistory() {
    try {
      const res = await fetchHistory();
      setHistory(res.items || []);
    } catch {
      /* noop */
    }
  }

  async function refreshJobs() {
    try {
      const res = await fetchJobs();
      setJobs(res.items || []);
    } catch {
      /* noop */
    }
  }

  const voiceOptions = useMemo(
    () =>
      voices.map((v) => (
        <option key={v.id} value={v.id}>
          {v.label} · {v.language}
        </option>
      )),
    [voices],
  );

  async function pollJob(jobId) {
    let attempts = 0;
    while (attempts < 20) {
      // 20 * 1.2s ≈ 24s timeout
      attempts += 1;
      const job = await fetchJob(jobId);
      if (job.status === "succeeded") {
        return job;
      }
      if (job.status === "failed") {
        throw new Error(job.error || "Synthesis failed");
      }
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    }
    throw new Error("Timeout waiting for synthesis");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!text.trim()) {
      setStatus("Ajoutez du texte avant de lancer la synthèse.");
      return;
    }
    setLoading(true);
    setStatus("Synthèse en cours…");
    try {
      const job = await createSynthesis(
        { text, voice_id: voiceId, speed, style: style || undefined },
        { asyncMode: true },
      );
      const finalJob = await pollJob(job.job_id);
      setStatus("Synthèse terminée.");
      await refreshHistory();
      await refreshJobs();
    } catch (err) {
      setStatus(err.message || "Erreur de synthèse");
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteHistory(jobId) {
    try {
      await deleteHistory(jobId);
      await refreshHistory();
    } catch (err) {
      setStatus(err.message || "Suppression impossible");
    }
  }

  async function handleDeleteJob(jobId) {
    try {
      await deleteJob(jobId);
      await refreshJobs();
    } catch (err) {
      setStatus(err.message || "Suppression impossible");
    }
  }

  function toggleSelection(jobId) {
    const next = new Set(selectedHistory);
    if (next.has(jobId)) {
      next.delete(jobId);
    } else {
      next.add(jobId);
    }
    setSelectedHistory(next);
  }

  function toggleJobSelection(jobId) {
    const next = new Set(selectedJobs);
    if (next.has(jobId)) {
      next.delete(jobId);
    } else {
      next.add(jobId);
    }
    setSelectedJobs(next);
  }

  function clearSelection() {
    setSelectedHistory(new Set());
  }

  function clearJobSelection() {
    setSelectedJobs(new Set());
  }

  async function handleExportSelected() {
    if (selectedHistory.size === 0) {
      setStatus("Sélectionnez au moins un rendu pour exporter.");
      return;
    }
    try {
      setStatus("Préparation de l'export…");
      const url = await exportZip(Array.from(selectedHistory));
      const a = document.createElement("a");
      a.href = url;
      a.download = "oratioviva-audio.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setStatus("Export téléchargé.");
      clearSelection();
    } catch (err) {
      setStatus(err.message || "Export impossible");
    }
  }

  async function handleDeleteSelectedHistory() {
    if (selectedHistory.size === 0) {
      setStatus("Sélectionnez au moins un rendu à supprimer.");
      return;
    }
    try {
      await deleteHistoryBatch(Array.from(selectedHistory), true);
      await refreshHistory();
      clearSelection();
      setStatus("Historique supprimé.");
    } catch (err) {
      setStatus(err.message || "Suppression impossible");
    }
  }

  async function handleDeleteSelectedJobs() {
    if (selectedJobs.size === 0) {
      setStatus("Sélectionnez au moins un job à supprimer.");
      return;
    }
    try {
      await deleteJobsBatch(Array.from(selectedJobs));
      await refreshJobs();
      clearJobSelection();
      setStatus("Jobs supprimés.");
    } catch (err) {
      setStatus(err.message || "Suppression impossible");
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">OratioViva Studio</p>
          <h1>Convertissez vos threads en audio clair.</h1>
          <p className="lede">
            Collez un texte, choisissez une voix, générez en un clic. Kokoro pour la vitesse,
            Parler pour le style. API: <code>{getApiBase()}</code>
          </p>
        </div>
        <div className="logo-wrap">
          <img src="/logo.png" alt="OratioViva logo" className="logo" />
          <div className="pill">TTS Kokoro / Parler</div>
        </div>
      </header>

      <main className="grid">
        <section className="card">
          <form onSubmit={handleSubmit} className="form">
            <label className="label">Texte</label>
            <textarea
              className="input textarea"
              rows={8}
              placeholder="Collez votre thread ou article…"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />

            <div className="inline">
              <div className="field">
                <label className="label">Voix</label>
                <select
                  className="input"
                  value={voiceId}
                  onChange={(e) => setVoiceId(e.target.value)}
                >
                  {voiceOptions}
                </select>
              </div>
              <div className="field">
                <label className="label">Vitesse: {speed.toFixed(1)}x</label>
                <input
                  type="range"
                  min="0.6"
                  max="1.5"
                  step="0.1"
                  value={speed}
                  onChange={(e) => setSpeed(parseFloat(e.target.value))}
                />
              </div>
            </div>

            <div className="field">
              <label className="label">Style (Parler)</label>
              <input
                className="input"
                placeholder="ex: slightly expressive, calm narrator…"
                value={style}
                onChange={(e) => setStyle(e.target.value)}
              />
            </div>

            <button className="button" type="submit" disabled={loading}>
              {loading ? "Synthèse…" : "Générer l'audio"}
            </button>
            {status && <p className="status">{status}</p>}
          </form>
        </section>

        <section className="card history">
          <div className="history-header">
            <div>
              <p className="eyebrow">Historique</p>
              <h2>Dernières générations</h2>
            </div>
            <div className="row">
              <button className="ghost" onClick={refreshHistory}>
                Rafraîchir
              </button>
              <button className="ghost" onClick={handleExportSelected}>
                Export ZIP
              </button>
              <button className="ghost" onClick={handleDeleteSelectedHistory}>
                Supprimer sélection
              </button>
            </div>
          </div>
          <div className="history-list">
            {(history || []).map((item) => (
              <article key={item.job_id} className="history-item">
                <div className="row space">
                  <div className="row">
                    <input
                      type="checkbox"
                      checked={selectedHistory.has(item.job_id)}
                      onChange={() => toggleSelection(item.job_id)}
                    />
                    <span className="tag">{item.model}</span>
                    <span className="tag">{item.voice_id}</span>
                    <span className="tag subtle">{item.source}</span>
                  </div>
                  <button className="ghost small" onClick={() => handleDeleteHistory(item.job_id)}>
                    Supprimer
                  </button>
                </div>
                <div className="row">
                  <p className="preview">{item.text_preview}</p>
                </div>
                <div className="row space">
                  <small>{new Date(item.created_at).toLocaleString()}</small>
                  {item.audio_url ? (
                    <div className="row">
                      <audio controls src={`${getApiBase()}${item.audio_url}`} />
                      <a
                        className="ghost small"
                        href={`${getApiBase()}${item.audio_url}`}
                        download
                      >
                        Télécharger
                      </a>
                    </div>
                  ) : (
                    <small>Pas d'audio</small>
                  )}
                </div>
              </article>
            ))}
            {history.length === 0 && <p className="muted">Aucun rendu pour l’instant.</p>}
          </div>
        </section>
      </main>

      <section className="card jobs">
        <div className="history-header">
          <div>
            <p className="eyebrow">Jobs récents</p>
            <h2>File d’attente</h2>
          </div>
          <div className="row">
            <button className="ghost" onClick={refreshJobs}>
              Rafraîchir
            </button>
            <button className="ghost" onClick={handleDeleteSelectedJobs}>
              Supprimer sélection
            </button>
          </div>
        </div>
        <div className="history-list">
          {(jobs || []).map((job) => (
            <article key={job.job_id} className="history-item">
              <div className="row space">
                <div className="row">
                  <input
                    type="checkbox"
                    checked={selectedJobs.has(job.job_id)}
                    onChange={() => toggleJobSelection(job.job_id)}
                  />
                  <span className="tag">{job.status}</span>
                  {job.voice_id && <span className="tag">{job.voice_id}</span>}
                  {job.model && <span className="tag">{job.model}</span>}
                </div>
                <button className="ghost small" onClick={() => handleDeleteJob(job.job_id)}>
                  Retirer
                </button>
              </div>
              <p className="muted">{job.job_id}</p>
              <small>
                Créé: {new Date(job.created_at).toLocaleString()} · Maj:{" "}
                {new Date(job.updated_at).toLocaleString()}
              </small>
            </article>
          ))}
          {jobs.length === 0 && <p className="muted">Aucun job en cours.</p>}
        </div>
      </section>
    </div>
  );
}
