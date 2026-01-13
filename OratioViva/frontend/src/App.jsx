import { useEffect, useMemo, useState } from "react";
import {
  createSynthesis,
  deleteHistory,
  deleteHistoryBatch,
  deleteJob,
  deleteJobsBatch,
  downloadModels,
  exportZip,
  fetchHistory,
  fetchJob,
  fetchJobs,
  fetchModelStatus,
  fetchAnalytics,
  fetchVoices,
  getApiBase,
} from "./api";

const POLL_INTERVAL_MS = 1200;
const MODEL_POLL_MS = 1500;
const ANALYTICS_POLL_MS = 3000;

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
  const [view, setView] = useState("studio"); // studio | analytics
  const [modelState, setModelState] = useState({
    needsDownload: false,
    downloading: false,
    provider: "auto",
    providerMessage: "",
    models: [],
  });
  const [startedAutoDownload, setStartedAutoDownload] = useState(false);
  const [analytics, setAnalytics] = useState(null);

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
    refreshModels();
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

  async function refreshModels() {
    try {
      const res = await fetchModelStatus();
      setModelState({
        needsDownload: res.needs_download,
        downloading: res.downloading,
        models: res.models,
        provider: res.provider || "auto",
        providerMessage: res.provider_message || "",
      });
    } catch {
      /* noop */
    }
  }

  useEffect(() => {
    if (modelState.needsDownload && !modelState.downloading && !startedAutoDownload) {
      setStartedAutoDownload(true);
      ensureModels();
    }
  }, [modelState.needsDownload, modelState.downloading, startedAutoDownload]);

  useEffect(() => {
    let timer;
    if (view === "analytics") {
      fetchAnalyticsData();
      timer = setInterval(fetchAnalyticsData, ANALYTICS_POLL_MS);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [view]);

  async function fetchAnalyticsData() {
    try {
      const res = await fetchAnalytics();
      setAnalytics(res);
    } catch (err) {
      setStatus(err.message || "Analytics indisponible");
    }
  }

  async function ensureModels() {
    setModelState((s) => ({ ...s, downloading: true }));
    try {
      await downloadModels();
      let attempts = 0;
      while (attempts < 30) {
        await new Promise((r) => setTimeout(r, MODEL_POLL_MS));
        const res = await fetchModelStatus();
        if (!res.needs_download) {
          setModelState({
            needsDownload: false,
            downloading: false,
            models: res.models,
            provider: res.provider || "auto",
            providerMessage: res.provider_message || "",
          });
          return;
        }
        attempts += 1;
      }
      setStatus("Telechargement des modeles: delai depasse.");
    } catch (err) {
      setStatus(err.message || "Erreur de telechargement des modeles");
    } finally {
      setModelState((s) => ({ ...s, downloading: false }));
    }
  }

  const voiceOptions = useMemo(
    () =>
      voices.map((v) => (
        <option key={v.id} value={v.id}>
          {v.label} - {v.language}
        </option>
      )),
    [voices],
  );

  const modelReady = !modelState.needsDownload && !modelState.downloading;
  const providerLabel = modelState.provider === "auto" ? "auto" : modelState.provider;
  const modelBadgeText = modelState.downloading
    ? "Telechargement des modeles..."
    : modelState.needsDownload
      ? "Modeles a installer"
      : `Mode ${providerLabel}`;
  const usingStub = providerLabel === "stub";

  async function pollJob(jobId) {
    let attempts = 0;
    while (attempts < 20) {
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
      setStatus("Ajoutez du texte avant de lancer la synthese.");
      return;
    }
    if (modelState.needsDownload) {
      setStatus("Installez les modeles pour obtenir une vraie voix.");
      return;
    }
    setLoading(true);
    setStatus("Synthese en cours...");
    try {
      const job = await createSynthesis(
        { text, voice_id: voiceId, speed, style: style || undefined },
        { asyncMode: true },
      );
      await pollJob(job.job_id);
      setStatus("Synthese terminee.");
      await refreshHistory();
      await refreshJobs();
    } catch (err) {
      setStatus(err.message || "Erreur de synthese");
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
      setStatus("Selectionnez au moins un rendu pour exporter.");
      return;
    }
    try {
      setStatus("Preparation de l'export...");
      const url = await exportZip(Array.from(selectedHistory));
      const a = document.createElement("a");
      a.href = url;
      a.download = "oratioviva-audio.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setStatus("Export telecharge.");
      clearSelection();
    } catch (err) {
      setStatus(err.message || "Export impossible");
    }
  }

  async function handleDeleteSelectedHistory() {
    if (selectedHistory.size === 0) {
      setStatus("Selectionnez au moins un rendu a supprimer.");
      return;
    }
    try {
      await deleteHistoryBatch(Array.from(selectedHistory), true);
      await refreshHistory();
      clearSelection();
      setStatus("Historique supprime.");
    } catch (err) {
      setStatus(err.message || "Suppression impossible");
    }
  }

  async function handleDeleteSelectedJobs() {
    if (selectedJobs.size === 0) {
      setStatus("Selectionnez au moins un job a supprimer.");
      return;
    }
    try {
      await deleteJobsBatch(Array.from(selectedJobs));
      await refreshJobs();
      clearJobSelection();
      setStatus("Jobs supprimes.");
    } catch (err) {
      setStatus(err.message || "Suppression impossible");
    }
  }

  return (
    <div className="page">
      {modelState.needsDownload && (
        <div className="overlay">
          <div className="overlay-card">
            <p className="eyebrow">Preparation</p>
            <h2>Installer les modeles TTS</h2>
            <p className="lede">
              Premier lancement: telechargez Kokoro/Parler pour entendre une vraie voix (sinon bip de test).
            </p>
            <p className="lede">
              Cela prend 1 a 3 minutes selon la connexion. Laissez la fenetre ouverte.
            </p>
            <button className="button" onClick={ensureModels} disabled={modelState.downloading}>
              {modelState.downloading ? "Telechargement..." : "Installer les modeles"}
            </button>
            {modelState.models && (
              <ul className="model-list">
                {modelState.models.map((m) => (
                  <li key={m.id}>
                    <span>{m.repo_id}</span> - {m.exists ? "present" : "manquant"}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      <div className="toolbar">
        <div className="toolbar-left">
          <img src="/favicon.ico" alt="OratioViva" className="toolbar-icon" />
          <div>
            <div className="toolbar-title">OratioViva Desktop</div>
            <p className="toolbar-sub">
              App locale connectee a <code>{getApiBase()}</code>
            </p>
          </div>
        </div>
        <div className="toolbar-actions">
          <span className={modelReady ? "badge badge-ok" : "badge badge-warn"}>{modelBadgeText}</span>
          <button className={`ghost ${view === "studio" ? "active" : ""}`} onClick={() => setView("studio")}>
            Studio
          </button>
          <button className={`ghost ${view === "analytics" ? "active" : ""}`} onClick={() => setView("analytics")}>
            Analytics
          </button>
          <button className="ghost" onClick={refreshModels}>Modeles</button>
          <button className="ghost" onClick={refreshHistory}>Historique</button>
          <button className="ghost" onClick={refreshJobs}>Jobs</button>
        </div>
      </div>

      {view === "studio" && (
        <>
      <header className="hero">
        <div>
          <p className="eyebrow">OratioViva Studio</p>
          <h1>Convertissez vos threads en audio clair.</h1>
          <p className="lede">
            Collez un texte, choisissez une voix, genere en un clic. Kokoro pour la vitesse, Parler pour le style.
          </p>
          {usingStub && (
            <p className="lede warning">
              Mode stub (bip de test). Installez les modeles pour entendre une vraie voix.
            </p>
          )}
          {modelState.providerMessage && (
            <p className="lede warning">{modelState.providerMessage}</p>
          )}
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
              placeholder="Collez votre thread ou article."
              value={text}
              onChange={(e) => setText(e.target.value)}
            />

            <div className="inline">
              <div className="field">
                <label className="label">Voix</label>
                <select className="input" value={voiceId} onChange={(e) => setVoiceId(e.target.value)}>
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
                placeholder="ex: slightly expressive, calm narrator."
                value={style}
                onChange={(e) => setStyle(e.target.value)}
              />
            </div>

            <button className="button" type="submit" disabled={loading}>
              {loading ? "Synthese..." : "Generer l'audio"}
            </button>
            {status && <p className="status">{status}</p>}
          </form>
        </section>

        <section className="card history">
          <div className="history-header">
            <div>
              <p className="eyebrow">Historique</p>
              <h2>Dernieres generations</h2>
            </div>
            <div className="row">
              <button className="ghost" onClick={refreshHistory}>Rafraichir</button>
              <button className="ghost" onClick={handleExportSelected}>Export ZIP</button>
              <button className="ghost" onClick={handleDeleteSelectedHistory}>Supprimer selection</button>
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
                      <a className="ghost small" href={`${getApiBase()}${item.audio_url}`} download>
                        Telecharger
                      </a>
                    </div>
                  ) : (
                    <small>Pas d'audio</small>
                  )}
                </div>
              </article>
            ))}
            {history.length === 0 && <p className="muted">Aucun rendu pour l'instant.</p>}
          </div>
        </section>
      </main>

      <section className="card jobs">
        <div className="history-header">
          <div>
            <p className="eyebrow">Jobs recents</p>
            <h2>File d'attente</h2>
          </div>
          <div className="row">
            <button className="ghost" onClick={refreshJobs}>Rafraichir</button>
            <button className="ghost" onClick={handleDeleteSelectedJobs}>Supprimer selection</button>
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
                Cree: {new Date(job.created_at).toLocaleString()} - Maj:{" "}
                {new Date(job.updated_at).toLocaleString()}
              </small>
            </article>
          ))}
          {jobs.length === 0 && <p className="muted">Aucun job en cours.</p>}
        </div>
      </section>
        </>
      )}

      {view === "analytics" && (
        <main className="grid analytics">
          <section className="card">
            <p className="eyebrow">Runtime</p>
            <h2>Provider status</h2>
            <p className="lede">
              Provider: <strong>{analytics?.provider || modelState.provider}</strong>
            </p>
            {analytics?.provider_message && <p className="lede warning">{analytics.provider_message}</p>}
            <h3>Models</h3>
            <ul className="model-list">
              {(analytics?.models || modelState.models || []).map((m) => (
                <li key={m.repo_id || m.id}>
                  <span>{m.repo_id || m.id}</span> — {m.exists ? "present" : "missing"} —{" "}
                  {m.local_supported ? "local ok" : "local unavailable"}
                  {m.local_reason ? ` (${m.local_reason})` : ""}
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <p className="eyebrow">Activity</p>
            <h2>Metrics</h2>
            <p>History items: {analytics?.counts?.history ?? history.length}</p>
            <p>Jobs stored: {analytics?.counts?.jobs ?? jobs.length}</p>
            <p>
              Audio duration (history):{" "}
              {analytics?.counts?.audio_duration_seconds
                ? `${(analytics.counts.audio_duration_seconds / 60).toFixed(1)} min`
                : "…"}
            </p>
            <h3>Recent jobs</h3>
            <ul className="model-list">
              {(analytics?.jobs_recent || []).map((job) => (
                <li key={job.job_id}>
                  {job.job_id} — {job.status} — {job.voice_id} ({job.model || "?"})
                </li>
              ))}
            </ul>
            <h3>Recent history</h3>
            <ul className="model-list">
              {(analytics?.history_recent || []).map((item) => (
                <li key={item.job_id}>
                  {item.text_preview} — {item.model} — {item.voice_id} —{" "}
                  {item.duration_seconds ? `${item.duration_seconds.toFixed(2)}s` : "n/a"}
                </li>
              ))}
            </ul>
          </section>
        </main>
      )}
    </div>
  );
}
