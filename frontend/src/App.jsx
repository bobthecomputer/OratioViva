import { useEffect, useMemo, useState, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  createSynthesis,
  createLongSynthesis,
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
  fetchVoices,
  getApiBase,
  resolveApiBase,
} from "./api";
import { useTranslation } from "./i18n";

const POLL_INTERVAL_MS = 1000;
const MODEL_POLL_MS = 800;
const JOBS_POLL_MS = 1500;
const BACKEND_POLL_MS = 3000;

function formatBytes(bytes) {
  if (bytes <= 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let unitIndex = 0;
  let size = bytes;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

function LoadingScreen({ t, onRetry, downloadProgress, downloadError }) {
  const [status, setStatus] = useState("connecting");
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const downloadModel = downloadProgress?.model_id || downloadProgress?.repo_id || "model";
  const downloadDetail =
    downloadProgress && downloadProgress.total_bytes > 0
      ? t("loading.modelDownloadDetail", {
          downloaded: formatBytes(downloadProgress.downloaded_bytes),
          total: formatBytes(downloadProgress.total_bytes),
        })
      : "";

  useEffect(() => {
    let attempts = 0;
    const maxAttempts = 180;
    
    const checkStatus = async () => {
      try {
        const base = await resolveApiBase();
        const res = await fetch(`${base}/health`, { cache: "no-store" });
        if (res.ok) {
          setStatus("ready");
          setProgress(100);
          setStatusMessage(t("loading.backendReady"));
        } else {
          throw new Error("Backend not ready");
        }
      } catch {
        attempts++;
        if (attempts >= maxAttempts) {
          setStatus("failed");
          setStatusMessage(t("loading.timeout"));
        } else {
          setStatus("connecting");
          setStatusMessage(t("loading.backendWait"));
          setProgress(Math.min(90, (attempts / maxAttempts) * 100));
        }
      }
    };

    const interval = setInterval(checkStatus, 1000);
    checkStatus();

    return () => clearInterval(interval);
  }, [t]);

  return (
    <div className="loading-screen">
      <div className="loading-content">
        <div className="loading-logo">
          <img src="/favicon.ico" alt="OratioViva" />
        </div>
        <h1 className="loading-title">{t("loading.title")}</h1>
        <p className="loading-subtitle">{t("loading.subtitle")}</p>
        <div className="loading-bar-container">
          <div className="loading-bar">
            <div className="loading-bar-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
        <div className="loading-status-container">
          {status === "connecting" && (
            <>
              <div className="loading-spinner-small" />
              <p className="loading-status">{statusMessage || t("loading.backendWait")}</p>
            </>
          )}
          {status === "ready" && (
            <p className="loading-status success">{t("loading.backendReady")}</p>
          )}
          {status === "failed" && (
            <p className="loading-status error">{statusMessage || t("loading.timeout")}</p>
          )}
        </div>
        {(downloadProgress || downloadError) && (
          <div className="loading-download">
            {downloadProgress && (
              <>
                <p className="loading-status">
                  {downloadProgress.message || t("loading.modelDownload", { model: downloadModel })}
                </p>
                <ProgressBar progress={downloadProgress.progress} message={downloadDetail} />
              </>
            )}
            {downloadError && <p className="loading-status error">{downloadError}</p>}
          </div>
        )}
        {status === "failed" && (
          <button className="loading-retry" onClick={onRetry}>
            {t("loading.retryBtn")}
          </button>
        )}
      </div>
    </div>
  );
}

function ProgressBar({ progress, message, showDetails = true }) {
  const percent = Math.min(100, Math.max(0, (progress || 0) * 100));

  return (
    <div className="progress-container">
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${percent}%`, animation: "progress-fill 0.3s ease-out" }}
        />
      </div>
      {showDetails && message && (
        <div className="progress-info">
          <span className="progress-message">{message}</span>
          <span className="progress-percent">{percent.toFixed(1)}%</span>
        </div>
      )}
    </div>
  );
}

function ModelCard({ model, onDownload, downloadProgress, downloadingModels }) {
  const hasModel = model.exists;
  const modelDownloadProgress =
    downloadProgress?.[model.id] ||
    (downloadProgress?.model_id === model.id ? downloadProgress : null);
  const isCurrentDownload =
    modelDownloadProgress?.status === "downloading" || modelDownloadProgress?.status === "starting";
  const isDownloading = downloadingModels.has(model.id) || isCurrentDownload;

  const statusIcon = hasModel ? "✓" : isCurrentDownload ? "↻" : "↓";
  const statusText = hasModel ? "installed" : isCurrentDownload ? "downloading..." : "not installed";

  return (
    <div className={`model-card ${hasModel ? "model-installed" : ""} ${isCurrentDownload ? "model-downloading" : ""}`}>
      <div className="model-card-header">
        <div className="model-card-title">
          <span className="model-icon">
            {model.id === "dia2" ? "💬" : model.id === "parler" ? "🎭" : model.id === "bark" ? "🔊" : model.id === "mms" ? "🎤" : model.id === "speecht5" ? "📻" : "🤖"}
          </span>
          <div>
            <strong>{model.repo_id.split("/")[1] || model.repo_id}</strong>
            <span className="model-repo">{model.repo_id}</span>
          </div>
        </div>
        <span className={`model-status ${hasModel ? "status-ok" : isCurrentDownload ? "status-pending" : "status-warn"}`}>
          {statusIcon} {statusText}
        </span>
      </div>

      {model.local_reason && <p className="model-warning">{model.local_reason}</p>}

      {(isCurrentDownload || isDownloading) && modelDownloadProgress && (
        <div className="model-download-progress">
          <ProgressBar progress={modelDownloadProgress.progress} message={modelDownloadProgress.message} />
          {modelDownloadProgress.downloaded_bytes > 0 && (
            <div className="download-stats">
              <span>{formatBytes(modelDownloadProgress.downloaded_bytes)}</span>
              {modelDownloadProgress.total_bytes > 0 && (
                <> / <span>{formatBytes(modelDownloadProgress.total_bytes)}</span></>
              )}
            </div>
          )}
        </div>
      )}

      {!hasModel && (
        <button
          className="button model-download-btn"
          onClick={() => onDownload(model.id)}
          disabled={isDownloading && !isCurrentDownload}
        >
          {isDownloading && !isCurrentDownload ? (
            <>↻ Downloading...</>
          ) : isCurrentDownload ? (
            <>↻ In progress...</>
          ) : (
            <>↓ Install this model</>
          )}
        </button>
      )}
    </div>
  );
}

function ModelDownloadPanel({ models, onDownload, downloadProgress, isDownloading, onClose, onRefresh }) {
  const { t } = useTranslation();
  const [selectedModels, setSelectedModels] = useState(new Set());
  const [downloadingModels, setDownloadingModels] = useState(new Set());
  const [isBatchDownloading, setIsBatchDownloading] = useState(false);

  const modelInfo = {
    dia2: { name: "Dia2-2B", description: "Streaming dialogue TTS, conversational and natural.", size: "~2.5 GB", default: true },
    bark: { name: "Bark Small", description: "Expressive, multi-lingual speech synthesis.", size: "~5 GB", default: false },
    speecht5: { name: "SpeechT5 + HiFiGAN", description: "Neural TTS with high-quality vocoder.", size: "~2 GB", default: false },
    parler: { name: "Parler-TTS", description: "Style-controlled TTS with promptable expression.", size: "~2 GB", default: false },
    mms: { name: "MMS TTS", description: "Meta's Massively Multilingual Speech models.", size: "~500 MB", default: false },
  };

  const handleToggle = useCallback((modelId) => {
    setSelectedModels(prev => {
      const next = new Set(prev);
      if (next.has(modelId)) {
        next.delete(modelId);
      } else {
        next.add(modelId);
      }
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    const allIds = models.filter(m => !m.exists).map(m => m.id);
    setSelectedModels(new Set(allIds));
  }, [models]);

  const handleDeselectAll = useCallback(() => {
    setSelectedModels(new Set());
  }, []);

  const handleDownloadSelected = useCallback(async () => {
    if (selectedModels.size === 0) return;
    
    setIsBatchDownloading(true);
    setDownloadingModels(new Set(selectedModels));
    
    try {
      for (const modelId of selectedModels) {
        await downloadModels([modelId]);
        if (onRefresh) {
          await onRefresh();
        }
      }
    } finally {
      setTimeout(() => {
        setDownloadingModels(new Set());
        setIsBatchDownloading(false);
      }, 1000);
    }
  }, [selectedModels, downloadModels, onRefresh]);

  const installedCount = models.filter(m => m.exists).length;
  const notInstalledCount = models.filter(m => !m.exists).length;
  const selectedCount = selectedModels.size;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content models-panel-large" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t("models.title")}</h2>
          <button className="ghost modal-close" onClick={onClose}>✕</button>
        </div>

        <p className="modal-description">{t("models.description")}</p>

        <div className="models-summary">
          <span className="installed-count">✓ {installedCount} installed</span>
          <span className="available-count">{notInstalledCount} available</span>
        </div>

        <div className="model-selection-actions">
          <button className="ghost small" onClick={handleSelectAll}>{t("models.selectAll")}</button>
          <button className="ghost small" onClick={handleDeselectAll}>{t("models.deselectAll")}</button>
          <span className="selected-count">{selectedCount > 0 ? `${selectedCount} selected` : 'Click boxes below to select models'}</span>
        </div>

        <div className="model-list-container">
          {models.map(model => {
            const info = modelInfo[model.id] || { name: model.id, description: "", size: "", default: false };
            const isSelected = selectedModels.has(model.id);
            const downloadProgressInfo =
              downloadProgress?.[model.id] ||
              (downloadProgress?.model_id === model.id ? downloadProgress : null);
            const isDownloading =
              downloadingModels.has(model.id) || downloadProgressInfo?.status === "downloading";

            return (
              <div 
                key={model.id} 
                className={`model-select-card ${model.exists ? "model-installed" : ""} ${isSelected ? "model-selected" : ""}`}
                onClick={() => !model.exists && handleToggle(model.id)}
              >
                {!model.exists && (
                  <div className="model-checkbox">
                    <input 
                      type="checkbox" 
                      checked={isSelected} 
                      onChange={() => handleToggle(model.id)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </div>
                )}
                
                <div className="model-select-info">
                  <div className="model-select-header">
                    <span className="model-icon">
                      {model.id === "dia2" ? "💬" : model.id === "parler" ? "🎭" : model.id === "bark" ? "🔊" : model.id === "mms" ? "🎤" : model.id === "speecht5" ? "📻" : "🤖"}
                    </span>
                    <div>
                      <strong>{info.name}</strong>
                      {info.default && <span className="default-badge">Default</span>}
                    </div>
                    <span className="model-size">{info.size}</span>
                  </div>
                  <p className="model-description">{info.description}</p>
                  
                  {isDownloading && downloadProgressInfo && (
                    <div className="model-download-progress">
                      <ProgressBar progress={downloadProgressInfo.progress} message={downloadProgressInfo.message} />
                    </div>
                  )}
                  
                  {model.exists && (
                    <div className="model-installed-badge">
                      <span>✓ {t("models.installed")}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="modal-footer">
          <button className="button" onClick={onClose}>{t("models.close")}</button>
          {selectedCount > 0 && (
            <button 
              className="button button-primary button-large" 
              onClick={handleDownloadSelected}
              disabled={isBatchDownloading}
            >
              {isBatchDownloading 
                ? t("models.downloadingSelected", { count: selectedCount })
                : t("models.downloadSelected", { count: selectedCount })
              }
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function LongAudioModal({ text, voiceId, onConfirm, onCancel, t }) {
  const [chunkSize, setChunkSize] = useState(2000);
  const [parallel, setParallel] = useState(false);

  const chunkCount = Math.ceil(text.length / chunkSize);

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t("longAudio.title")}</h2>
          <button className="ghost modal-close" onClick={onCancel}>✕</button>
        </div>

        <p className="modal-description">{t("longAudio.description")}</p>

        <div className="long-audio-info">
          <p><strong>Text length:</strong> {text.length} characters</p>
          <p><strong>Estimated chunks:</strong> {chunkCount}</p>
        </div>

        <div className="long-audio-options">
          <h3>{t("longAudio.mode")}</h3>

          <label className={`long-audio-mode ${!parallel ? "selected" : ""}`}>
            <input type="radio" checked={!parallel} onChange={() => setParallel(false)} />
            <div className="mode-content">
              <strong>{t("longAudio.sequential")}</strong>
              <span>{t("longAudio.sequentialDesc")}</span>
            </div>
          </label>

          <label className={`long-audio-mode ${parallel ? "selected" : ""}`}>
            <input type="radio" checked={parallel} onChange={() => setParallel(true)} />
            <div className="mode-content">
              <strong>{t("longAudio.parallel")}</strong>
              <span>{t("longAudio.parallelDesc")}</span>
            </div>
          </label>
        </div>

        <div className="chunk-size-selector">
          <label>
            <strong>{t("longAudio.chunkSize")}:</strong> {chunkSize} {t("longAudio.characters")}
          </label>
          <input
            type="range"
            min="500"
            max="5000"
            step="500"
            value={chunkSize}
            onChange={e => setChunkSize(parseInt(e.target.value))}
          />
        </div>

        <div className="modal-footer">
          <button className="ghost" onClick={onCancel}>Cancel</button>
          <button className="button" onClick={() => onConfirm({ chunkSize, parallel })}>
            {t("longAudio.continueBtn", { mode: parallel ? "Parallel" : "Sequential" })}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const { t, lang, changeLanguage, loading: i18nLoading } = useTranslation();

  const [text, setText] = useState("");
  const [voices, setVoices] = useState([]);
  const [voiceId, setVoiceId] = useState("");
  const [speed, setSpeed] = useState(1);
  const [style, setStyle] = useState("");
  const [voiceRef, setVoiceRef] = useState("");
  const [history, setHistory] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedHistory, setSelectedHistory] = useState(new Set());
  const [selectedJobs, setSelectedJobs] = useState(new Set());
  const [modelState, setModelState] = useState({
    downloading: false,
    downloadError: null,
    downloadProgress: null,
    provider: "auto",
    providerMessage: "",
    models: [],
    searchPaths: [],
    bundledPath: null,
  });
  const [synthesisProgress, setSynthesisProgress] = useState(0);
  const [synthesisStatus, setSynthesisStatus] = useState("");
  const [retryJob, setRetryJob] = useState(null);
  const [backendReady, setBackendReady] = useState(false);
  const [apiBase, setApiBase] = useState(getApiBase());
  const [showModelsPanel, setShowModelsPanel] = useState(false);
  const [showLongAudioModal, setShowLongAudioModal] = useState(false);

  useEffect(() => {
    localStorage.clear();
    const savedVoice = localStorage.getItem("oratioviva_voice");
    const savedSpeed = localStorage.getItem("oratioviva_speed");
    const savedStyle = localStorage.getItem("oratioviva_style");
    const savedVoiceRef = localStorage.getItem("oratioviva_voiceRef");
    if (savedVoice) setVoiceId(savedVoice);
    if (savedSpeed) setSpeed(parseFloat(savedSpeed));
    if (savedStyle) setStyle(savedStyle);
    if (savedVoiceRef) {
      const ext = savedVoiceRef.split('.').pop().toLowerCase();
      const audioExts = ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac', 'webm'];
      if (savedVoiceRef.startsWith('http') || audioExts.includes(ext)) {
        setVoiceRef(savedVoiceRef);
      } else {
        localStorage.removeItem("oratioviva_voiceRef");
        setVoiceRef("");
      }
    }
  }, []);

  useEffect(() => {
    if (voiceId) localStorage.setItem("oratioviva_voice", voiceId);
    else localStorage.removeItem("oratioviva_voice");
  }, [voiceId]);

  useEffect(() => {
    localStorage.setItem("oratioviva_speed", speed.toString());
  }, [speed]);

  useEffect(() => {
    if (style) localStorage.setItem("oratioviva_style", style);
    else localStorage.removeItem("oratioviva_style");
  }, [style]);

  useEffect(() => {
    if (voiceRef) {
      const ext = voiceRef.split('.').pop().toLowerCase();
      const audioExts = ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac', 'webm'];
      if (voiceRef.startsWith('http') || audioExts.includes(ext)) {
        localStorage.setItem("oratioviva_voiceRef", voiceRef);
      }
    } else {
      localStorage.removeItem("oratioviva_voiceRef");
    }
  }, [voiceRef]);

  const checkBackend = useCallback(async () => {
    try {
      const base = await resolveApiBase();
      await fetch(`${base}/health`, { cache: "no-store" });
      setApiBase(base);
      return true;
    } catch {
      return false;
    }
  }, []);

  const refreshBackend = useCallback(async () => {
    setBackendReady(false);
    let attempts = 0;
    const maxAttempts = 30;
    while (attempts < maxAttempts) {
      if (await checkBackend()) {
        setBackendReady(true);
        fetchVoices()
          .then((res) => {
            setVoices(res.voices || []);
            if (!voiceId && res.voices?.length > 0) {
              const dia2Voice = res.voices.find(v => v.id === "dia2_2b_en");
              setVoiceId(dia2Voice?.id || res.voices[0].id);
            }
          })
          .catch((err) => setStatus(err.message));
        refreshHistory();
        refreshJobs();
        refreshModels();
        return;
      }
      await new Promise(r => setTimeout(r, 1000));
      attempts++;
    }
  }, [checkBackend, voiceId]);

  useEffect(() => {
    refreshBackend();
  }, [refreshBackend]);

  useEffect(() => {
    resolveApiBase().then(setApiBase).catch(() => {});
  }, []);

  useEffect(() => {
    const timer = setInterval(async () => {
      const ready = await checkBackend();
      if (ready !== backendReady) {
        setBackendReady(ready);
        if (ready) {
          refreshModels();
        }
      }
    }, BACKEND_POLL_MS);
    return () => clearInterval(timer);
  }, [backendReady, checkBackend]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        handleSubmit(e);
      }
      if (e.key === "Escape") {
        setText("");
        setStyle("");
        setVoiceRef("");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [text, voiceId, speed, style, voiceRef, loading]);

  async function refreshHistory() {
    try {
      const res = await fetchHistory();
      setHistory(res.items || []);
    } catch { /* noop */ }
  }

  async function refreshJobs() {
    try {
      const res = await fetchJobs();
      setJobs(res.items || []);
    } catch { /* noop */ }
  }

  async function refreshModels() {
    try {
      const res = await fetchModelStatus();
      setModelState({
        downloading: res.downloading,
        downloadError: res.download_error || null,
        downloadProgress: res.download_progress || null,
        models: res.models || [],
        provider: res.provider || "auto",
        providerMessage: res.provider_message || "",
        searchPaths: res.search_paths || [],
        bundledPath: res.bundled_path || null,
      });
    } catch { /* noop */ }
  }

  useEffect(() => {
    let timer;
    if (modelState.downloading) {
      timer = setInterval(refreshModels, MODEL_POLL_MS);
    }
    return () => { if (timer) clearInterval(timer); };
  }, [modelState.downloading]);

  useEffect(() => {
    let timer;
    timer = setInterval(refreshJobs, JOBS_POLL_MS);
    return () => { if (timer) clearInterval(timer); };
  }, []);

  const voiceOptions = useMemo(
    () => voices.map((v) => (
      <option key={v.id} value={v.id}>
        {v.label} - {v.language.toUpperCase()}
      </option>
    )),
    [voices],
  );

  function getJobStatusInfo(status) {
    const statusLower = (status || "").toLowerCase();
    const statusMap = {
      pending: { class: "status-pending", icon: "⏳", label: t("jobs.status.pending") },
      queued: { class: "status-pending", icon: "⏳", label: t("jobs.status.queued") },
      processing: { class: "status-processing", icon: "⚙️", label: t("jobs.status.running") },
      running: { class: "status-processing", icon: "⚙️", label: t("jobs.status.running") },
      succeeded: { class: "status-success", icon: "✓", label: t("jobs.status.succeeded") },
      completed: { class: "status-success", icon: "✓", label: t("jobs.status.succeeded") },
      failed: { class: "status-failed", icon: "✗", label: t("jobs.status.failed") },
    };
    return statusMap[statusLower] || { class: "status-default", icon: "•", label: status || "Unknown" };
  }

  function getVoiceModelId(voiceId) {
    const voice = voices.find(v => v.id === voiceId);
    if (!voice) return null;
    const modelMap = {
      dia2: "dia2", parler: "parler", bark: "bark", speecht5: "speecht5", mms: "mms",
      xtts: "xtts", f5_tts: "f5_tts", cosyvoice: "cosyvoice",
    };
    for (const [key, pattern] of Object.entries(modelMap)) {
      if (voice.id.includes(key) || voice.model?.toLowerCase().includes(key)) {
        return key;
      }
    }
    return null;
  }

  function isModelAvailable(voiceId) {
    const modelId = getVoiceModelId(voiceId);
    if (!modelId) return true;
    const model = modelState.models.find(m => m.id === modelId);
    return model?.exists === true;
  }

  async function pollJob(jobId) {
    let attempts = 0;
    const maxAttempts = 180;
    const statusMessages = [
      { progress: 10, message: "Initializing..." },
      { progress: 20, message: "Loading model..." },
      { progress: 40, message: "Processing text..." },
      { progress: 60, message: "Generating audio..." },
      { progress: 80, message: "Finalizing..." },
    ];

    while (attempts < maxAttempts) {
      const job = await fetchJob(jobId);
      const progressIndex = Math.min(attempts, statusMessages.length - 1);
      const progressStep = 80 / statusMessages.length;
      setSynthesisStatus(statusMessages[progressIndex]?.message || "In progress...");
      setSynthesisProgress(Math.round(progressIndex * progressStep + (attempts % 3) * 5));

      if (job.status === "succeeded") {
        setSynthesisProgress(100);
        setSynthesisStatus("Done!");
        return job;
      }
      if (job.status === "failed") {
        setSynthesisProgress(0);
        setSynthesisStatus("");
        throw new Error(job.error || "Synthesis failed");
      }

      await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
      attempts++;
    }
    setSynthesisProgress(0);
    setSynthesisStatus("");
    throw new Error("Timeout waiting for synthesis");
  }

  async function handleSubmit(e, longAudioOptions = null) {
    e?.preventDefault();
    if (!text.trim()) {
      setStatus(t("status.addText"));
      return;
    }

    const isLongAudio = text.length > 4000 || longAudioOptions;

    if (!isModelAvailable(voiceId)) {
      const modelId = getVoiceModelId(voiceId);
      setStatus(t("status.modelMissing", { voice: voiceId }));
      setShowModelsPanel(true);
      return;
    }

    if (voiceRef && voiceRef.trim()) {
      const ext = voiceRef.split('.').pop().toLowerCase();
      const audioExts = ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac', 'webm'];
      if (!voiceRef.startsWith('http') && !audioExts.includes(ext)) {
        setStatus("Please select an audio file for voice cloning (.wav, .mp3, .ogg, .flac, .m4a, .aac, .webm). Images are not supported.");
        return;
      }
    }

    setLoading(true);
    setSynthesisProgress(0);
    setSynthesisStatus("Initializing...");
    setRetryJob(null);

    try {
      let job;
      if (isLongAudio && longAudioOptions) {
        job = await createLongSynthesis({
          text,
          voice_id: voiceId,
          speed,
          style: style || undefined,
          voice_ref: voiceRef || undefined,
          chunk_size: longAudioOptions.chunkSize,
          parallel: longAudioOptions.parallel,
        });
      } else {
        job = await createSynthesis(
          { text, voice_id: voiceId, speed, style: style || undefined, voice_ref: voiceRef || undefined },
          { asyncMode: true },
        );
      }
      await pollJob(job.job_id);
      setStatus(t("status.synthDone"));
      await refreshHistory();
      await refreshJobs();
    } catch (err) {
      setStatus(t("status.synthError", { error: err.message }));
      setRetryJob({ text, voiceId, speed, style, voiceRef });
    } finally {
      setLoading(false);
      setSynthesisProgress(0);
      setSynthesisStatus("");
    }
  }

  async function handleRetry() {
    if (retryJob) {
      setText(retryJob.text);
      setVoiceId(retryJob.voiceId);
      setSpeed(retryJob.speed);
      setStyle(retryJob.style || "");
      const isValidVoiceRef = (ref) => {
        if (!ref || !ref.trim()) return true;
        const ext = ref.split('.').pop().toLowerCase();
        const audioExts = ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac', 'webm'];
        return ref.startsWith('http') || audioExts.includes(ext);
      };
      if (retryJob.voiceRef && !isValidVoiceRef(retryJob.voiceRef)) {
        setVoiceRef("");
        setStatus("Invalid voice reference was cleared. Please select an audio file.");
        setRetryJob(null);
        return;
      }
      setVoiceRef(retryJob.voiceRef || "");
      setRetryJob(null);
      handleSubmit();
    }
  }

  async function handleRetryJob(job) {
    if (job.text_preview) {
      setText(job.text_preview);
      if (job.voice_id) setVoiceId(job.voice_id);
      setStatus("Pre-filled for retry. Click Generate.");
    }
  }

  function copyText() {
    navigator.clipboard.writeText(text);
    setStatus(t("status.copied"));
    setTimeout(() => setStatus(""), 2000);
  }

  function clearText() {
    setText("");
    setStatus(t("status.cleared"));
    setTimeout(() => setStatus(""), 2000);
  }

  async function handleDeleteHistory(jobId) {
    try {
      await deleteHistory(jobId);
      await refreshHistory();
    } catch (err) {
      setStatus(err.message || "Cannot delete");
    }
  }

  async function handleDeleteJob(jobId) {
    try {
      await deleteJob(jobId);
      await refreshJobs();
    } catch (err) {
      setStatus(err.message || "Cannot delete");
    }
  }

  function toggleSelection(jobId) {
    const next = new Set(selectedHistory);
    if (next.has(jobId)) next.delete(jobId);
    else next.add(jobId);
    setSelectedHistory(next);
  }

  function toggleJobSelection(jobId) {
    const next = new Set(selectedJobs);
    if (next.has(jobId)) next.delete(jobId);
    else next.add(jobId);
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
      setStatus("Select at least one item to export.");
      return;
    }
    try {
      setStatus("Preparing export...");
      const url = await exportZip(Array.from(selectedHistory));
      const a = document.createElement("a");
      a.href = url;
      a.download = "oratioviva-audio.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setStatus("Export downloaded.");
      clearSelection();
    } catch (err) {
      setStatus(err.message || "Export failed");
    }
  }

  async function handleDeleteSelectedHistory() {
    if (selectedHistory.size === 0) {
      setStatus("Select items to delete.");
      return;
    }
    try {
      await deleteHistoryBatch(Array.from(selectedHistory), true);
      await refreshHistory();
      clearSelection();
      setStatus("History deleted.");
    } catch (err) {
      setStatus(err.message || "Cannot delete");
    }
  }

  async function handleDeleteSelectedJobs() {
    if (selectedJobs.size === 0) {
      setStatus("Select jobs to delete.");
      return;
    }
    try {
      await deleteJobsBatch(Array.from(selectedJobs));
      await refreshJobs();
      clearJobSelection();
      setStatus("Jobs deleted.");
    } catch (err) {
      setStatus(err.message || "Cannot delete");
    }
  }

  const currentVoice = voices.find(v => v.id === voiceId);
  const currentModelId = getVoiceModelId(voiceId);
  const currentModel = modelState.models.find(m => m.id === currentModelId);
  const currentModelReady = !currentModelId || currentModel?.exists;

  const needsLongAudio = text.length > 4000;

  if (i18nLoading) {
    return <div className="loading-screen"><div className="loading-content"><p>Loading...</p></div></div>;
  }

  const showStartupDownload = backendReady && (modelState.downloading || modelState.downloadProgress);

  if (!backendReady || showStartupDownload) {
    return (
      <LoadingScreen
        t={t}
        onRetry={refreshBackend}
        downloadProgress={modelState.downloadProgress}
        downloadError={modelState.downloadError}
      />
    );
  }

  return (
    <div className="page">
      {showModelsPanel && (
        <ModelDownloadPanel
          models={modelState.models}
          onDownload={async (modelId) => {
            await downloadModels([modelId]);
            await refreshModels();
          }}
          downloadProgress={modelState.downloadProgress}
          isDownloading={modelState.downloading}
          onRefresh={refreshModels}
          onClose={() => setShowModelsPanel(false)}
        />
      )}

      {showLongAudioModal && (
        <LongAudioModal
          text={text}
          voiceId={voiceId}
          onConfirm={(options) => {
            setShowLongAudioModal(false);
            handleSubmit(null, options);
          }}
          onCancel={() => setShowLongAudioModal(false)}
          t={t}
        />
      )}

      <div className="toolbar">
        <div className="toolbar-left">
          <img src="/favicon.ico" alt="OratioViva" className="toolbar-icon" />
          <div>
            <div className="toolbar-title">{t("app.title")}</div>
            <p className="toolbar-sub">{t("app.tagline")}</p>
          </div>
        </div>
        <div className="toolbar-actions">
          <button className="ghost" onClick={async () => { setStatus("Restarting backend..."); try { await invoke('restart_backend'); await refreshBackend(); setStatus("Backend restarted"); } catch(e) { setStatus("Restart failed: " + e.message); } }} title="Restart Backend">↻</button>
          <span className={backendReady ? "badge badge-ok" : "badge badge-warn"}>
            {backendReady ? t("toolbar.backendOk") : t("toolbar.backendOff")}
          </span>
          <span className={`badge ${currentModelReady ? "badge-ok" : "badge-warn"}`}>
            {currentModelReady ? t("toolbar.modelOk") : t("toolbar.modelMissing")}
          </span>
          <button className="ghost" onClick={() => { refreshModels(); setShowModelsPanel(true); }}>
            {t("toolbar.settings")}
          </button>
          <select
            className="lang-select"
            value={lang}
            onChange={(e) => changeLanguage(e.target.value)}
          >
            <option value="en">EN</option>
            <option value="fr">FR</option>
          </select>
        </div>
      </div>

      {modelState.downloading && (
        <div className="loading-overlay">
          <div className="loading-overlay-content">
            <div className="loading-spinner" />
            <p>{modelState.downloadProgress?.message || t("form.synthesizing")}</p>
            {modelState.downloadProgress && (
              <ProgressBar progress={modelState.downloadProgress.progress} message="" showDetails={false} />
            )}
          </div>
        </div>
      )}

      <header className="hero">
        <div>
          <p className="eyebrow">{t("hero.eyebrow")}</p>
          <h1>{t("hero.headline")}</h1>
          <p className="lede">{t("hero.lede")}</p>
        </div>
        <div className="logo-wrap">
          <img src="/logo.png" alt="OratioViva" className="logo" />
          <div className="pill">TTS Dia2 / Parler / Bark / SpeechT5 / MMS</div>
        </div>
      </header>

      <main className="grid">
        <section className="card">
          <form onSubmit={handleSubmit} className="form">
            <div className="label-row">
              <label className="label">{t("form.textLabel")}</label>
              <div className="text-actions">
                <button type="button" className="ghost small" onClick={copyText} title={t("form.copyText")}>
                  {t("form.copyText")}
                </button>
                <button type="button" className="ghost small" onClick={clearText} title={t("form.clearText")}>
                  {t("form.clearText")}
                </button>
                <span className="char-count">{text.length} {t("form.charCount")}</span>
              </div>
            </div>
            <textarea
              className="input textarea"
              rows={8}
              placeholder={t("form.placeholder")}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />

            {loading && (
              <div className="synthesis-progress">
                <ProgressBar progress={synthesisProgress / 100} message={synthesisStatus || t("form.synthesizing")} />
                <div className="synthesis-voice">
                  <span className="pulse-indicator"></span>
                  {currentVoice?.label || voiceId}
                </div>
              </div>
            )}

            {retryJob && (
              <div className="retry-container">
                <button type="button" className="button retry-btn" onClick={handleRetry}>
                  Retry Synthesis
                </button>
              </div>
            )}

            <div className="inline">
              <div className="field">
                <label className="label">{t("form.voiceLabel")}</label>
                <div className="voice-select-wrapper">
                  <select className="input" value={voiceId} onChange={(e) => setVoiceId(e.target.value)}>
                    {voiceOptions}
                  </select>
                  {!currentModelReady && (
                    <button
                      type="button"
                      className="voice-download-hint"
                      onClick={() => setShowModelsPanel(true)}
                      title={t("models.installForVoice", { voice: voiceId })}
                    >
                      ↓
                    </button>
                  )}
                </div>
              </div>
              <div className="field">
                <label className="label">{t("form.speedLabel", { speed: speed.toFixed(1) })}</label>
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
              <label className="label">{t("form.styleLabel")}</label>
              <input
                className="input"
                placeholder="e.g., slightly expressive, calm narrator."
                value={style}
                onChange={(e) => setStyle(e.target.value)}
              />
            </div>

            <div className="field">
              <label className="label">{t("form.voiceRefLabel")}</label>
              <div className="voice-ref-input-wrapper">
                <input
                  className="input"
                  placeholder="C:\samples\voice.wav or https://..."
                  value={voiceRef}
                  onChange={(e) => setVoiceRef(e.target.value)}
                />
                {voiceRef && (
                  <button
                    type="button"
                    className="ghost small clear-voice-ref"
                    onClick={() => { setVoiceRef(""); setStatus("Voice reference cleared"); setTimeout(() => setStatus(""), 2000); }}
                    title="Clear voice reference"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            <div className="form-actions">
              <button
                className="button"
                type="submit"
                disabled={loading || !text.trim()}
              >
                {loading ? t("form.synthesizing") : t("form.generateBtn")}
              </button>
              {needsLongAudio && !loading && (
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => setShowLongAudioModal(true)}
                >
                  Long Text ({Math.ceil(text.length / 2000)} chunks)
                </button>
              )}
            </div>
            {status && <p className="status">{status}</p>}
          </form>
        </section>

        <section className="card history">
          <div className="history-header">
            <div>
              <p className="eyebrow">{t("history.title")}</p>
              <h2>{t("history.recentGens")}</h2>
            </div>
            <div className="row">
              <button className="ghost" onClick={refreshHistory}>{t("history.refresh")}</button>
              <button className="ghost" onClick={handleExportSelected}>{t("history.exportZip")}</button>
              <button className="ghost" onClick={handleDeleteSelectedHistory}>{t("history.deleteSelected")}</button>
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
                    <span className="tag">{item.model?.split("/").pop()}</span>
                    <span className="tag">{item.voice_id}</span>
                  </div>
                  <button className="ghost small" onClick={() => handleDeleteHistory(item.job_id)}>
                    {t("history.delete")}
                  </button>
                </div>
                <p className="preview">{item.text_preview}</p>
                <div className="row space">
                  <small>{t("history.createdAt")}: {new Date(item.created_at).toLocaleString()}</small>
                  {item.audio_url ? (
                    <div className="row">
                      <audio controls src={`${apiBase}${item.audio_url}`} />
                      <a className="ghost small" href={`${apiBase}${item.audio_url}`} download>
                        {t("history.download")}
                      </a>
                    </div>
                  ) : (
                    <small>{t("history.noAudio")}</small>
                  )}
                </div>
              </article>
            ))}
            {history.length === 0 && <p className="muted">{t("history.noItems")}</p>}
          </div>
        </section>
      </main>

      <section className="card jobs">
        <div className="history-header">
          <div>
            <p className="eyebrow">{t("jobs.title")}</p>
            <h2>{t("jobs.queue")}</h2>
          </div>
          <div className="row">
            <span className="jobs-count">{jobs.length} job{jobs.length !== 1 ? "s" : ""}</span>
            <button className="ghost" onClick={refreshJobs}>{t("jobs.refresh")}</button>
            <button className="ghost" onClick={handleDeleteSelectedJobs}>{t("jobs.deleteSelected")}</button>
          </div>
        </div>
        <div className="history-list">
          {(jobs || []).map((job) => {
            const statusInfo = getJobStatusInfo(job.status);
            const isActive = job.status?.toLowerCase() === "pending" || job.status?.toLowerCase() === "processing" || job.status?.toLowerCase() === "running";
            return (
              <article key={job.job_id} className={`history-item job-item ${isActive ? "job-active" : ""}`}>
                <div className="row space">
                  <div className="row">
                    <input
                      type="checkbox"
                      checked={selectedJobs.has(job.job_id)}
                      onChange={() => toggleJobSelection(job.job_id)}
                    />
                    <span className={`tag job-status ${statusInfo.class}`}>
                      <span className="status-icon">{statusInfo.icon}</span>
                      {statusInfo.label}
                    </span>
                    {job.voice_id && <span className="tag">{job.voice_id}</span>}
                    {job.model && <span className="tag">{job.model?.split("/").pop()}</span>}
                  </div>
                  <div className="row">
                    {isActive && <div className="pulse-indicator"></div>}
                    {job.status?.toLowerCase() === "failed" && job.text_preview && (
                      <button className="ghost small retry-ghost" onClick={() => handleRetryJob(job)}>
                        {t("jobs.retry")}
                      </button>
                    )}
                    <button className="ghost small" onClick={() => handleDeleteJob(job.job_id)}>
                      {t("jobs.remove")}
                    </button>
                  </div>
                </div>
                <p className="muted job-id">{job.job_id.slice(0, 8)}...</p>
                <small>Created: {new Date(job.created_at).toLocaleString()}</small>
                {job.text_preview && <p className="preview">{job.text_preview}</p>}
              </article>
            );
          })}
          {jobs.length === 0 && <p className="muted">{t("jobs.noJobs")}</p>}
        </div>
      </section>
    </div>
  );
}
