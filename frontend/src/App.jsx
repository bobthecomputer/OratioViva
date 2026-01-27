import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { TutorialPlayer } from "./TutorialPlayer";

let notificationApi = null;
if (typeof window !== "undefined" && window.__TAURI__) {
  notificationApi = window.__TAURI__.notification;
} else {
  try {
    notificationApi = require("@tauri-apps/api/notification");
  } catch {
    notificationApi = null;
  }
}
import {
  createSynthesis,
  createLongSynthesis,
  deleteHistory,
  deleteHistoryBatch,
  deleteJob,
  deleteJobsBatch,
  downloadModels,
  cancelDownload,
  deleteDownloadedModel,
  exportZip,
  exportMp3,
  fetchAnalytics,
  fetchHistory,
  fetchJob,
  fetchJobs,
  fetchModelStatus,
  fetchSettings,
  fetchVoices,
  getApiBase,
  resolveApiBase,
  saveHfToken,
  fetchPresets,
  saveTonePreset,
  deleteTonePreset,
  savePromptPreset,
  deletePromptPreset,
  fetchModelCapabilities,
  fetchDiagnostics,
  runCleanup,
  getTelemetrySettings,
  setTelemetrySettings,
} from "./api";
import { useTranslation } from "./i18n";

const POLL_INTERVAL_MS = 1000;
const MODEL_POLL_MS = 800;
const JOBS_POLL_MS = 1500;
const BACKEND_POLL_MS = 3000;
const LONG_TEXT_THRESHOLD = 4000;
const DEFAULT_CHUNK_SIZE = 3000;
const MAX_CHUNK_SIZE = 12000;
const DEFAULT_WPM = 165;

const LANGUAGE_LABELS = {
  en: "English",
  fr: "French",
  es: "Spanish",
  de: "German",
  it: "Italian",
  pt: "Portuguese",
  ru: "Russian",
  ja: "Japanese",
  ko: "Korean",
  zh: "Chinese",
};

const MODEL_DEPENDENCIES = {
  qwen3_tts: ["qwen3_tts", "qwen3_tokenizer_12hz"],
  speecht5: ["speecht5", "speecht5_vocoder"],
};

const PERF_PROFILES = {
  rtx3090: { label: "RTX 3090", multiplier: 1.0 },
  rtx4070: { label: "RTX 4070", multiplier: 1.15 },
  cpu: { label: "CPU", multiplier: 4.0 },
};

const MODEL_RTF_BASE = {
  dia2: 0.25,
  qwen3_tts: 0.35,
  parler: 0.6,
  bark: 0.9,
  speecht5: 0.5,
  mms: 0.7,
  xtts: 0.8,
  f5_tts: 0.7,
  cosyvoice: 0.7,
  chroma_4b: 1.0,
  kokoro: 0.4,
};

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
  remove(key) {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.removeItem(key);
    } catch {}
  },
  clear() {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.clear();
    } catch {}
  },
};

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

function countWords(text) {
  if (!text) return 0;
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function formatDuration(seconds) {
  if (!seconds || Number.isNaN(seconds)) return "—";
  const total = Math.max(0, Math.round(seconds));
  const hrs = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hrs > 0) return `${hrs}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

function estimateAudioSeconds(words, wpm) {
  if (!words) return 0;
  const effectiveWpm = wpm || DEFAULT_WPM;
  return (words / effectiveWpm) * 60;
}

function estimateGenerationSeconds(audioSeconds, modelId, profileKey) {
  if (!audioSeconds) return 0;
  const base = MODEL_RTF_BASE[modelId] ?? 0.8;
  const profile = PERF_PROFILES[profileKey] || PERF_PROFILES.rtx3090;
  return audioSeconds * base * profile.multiplier;
}

function VoiceWheel({ voices, selectedId, onSelect, centerLabel }) {
  if (!voices || voices.length === 0) {
    return (
      <div className="voice-wheel voice-wheel-empty">
        <span>No presets available</span>
      </div>
    );
  }

  const count = voices.length;
  const radius = count <= 5 ? 90 : count <= 8 ? 115 : count <= 12 ? 135 : 160;
  const size = radius * 2 + 80;

  return (
    <div className="voice-wheel" style={{ width: size, height: size }}>
      {centerLabel && <div className="voice-wheel-center">{centerLabel}</div>}
      {voices.map((voice, idx) => {
        const angle = (360 / count) * idx;
        const transform = `rotate(${angle}deg) translate(${radius}px) rotate(${-angle}deg)`;
        const isSelected = voice.id === selectedId;
        return (
          <button
            key={voice.id}
            type="button"
            className={`voice-wheel-item ${isSelected ? "selected" : ""}`}
            style={{ transform }}
            onClick={() => onSelect(voice.id)}
            title={voice.label}
          >
            <span>{voice.label}</span>
          </button>
        );
      })}
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
  const [isCancelling, setIsCancelling] = useState(false);

  const modelInfo = {
    dia2: { name: "Dia2-2B", description: "Streaming dialogue TTS, conversational and natural.", size: "~2.5 GB", default: true },
    bark: { name: "Bark Small", description: "Expressive, multi-lingual speech synthesis.", size: "~5 GB", default: false },
    speecht5: { name: "SpeechT5 + HiFiGAN", description: "Neural TTS with high-quality vocoder.", size: "~2 GB", default: false },
    speecht5_vocoder: { name: "SpeechT5 HiFiGAN", description: "Vocoder for SpeechT5 voices.", size: "~90 MB", default: false },
    parler: { name: "Parler-TTS", description: "Style-controlled TTS with promptable expression.", size: "~2 GB", default: false },
    mms: { name: "MMS TTS", description: "Meta's Massively Multilingual Speech models.", size: "~500 MB", default: false },
    kokoro: { name: "Kokoro-82M", description: "Lightweight TTS model (optional).", size: "~300 MB", default: false },
    chroma_4b: { name: "Chroma-4B", description: "FlashLabs Chroma-4B (gated).", size: "~8 GB", default: false },
    qwen3_tts: { name: "Qwen3-TTS CustomVoice", description: "Multi-lingual custom voice TTS.", size: "~3.6 GB", default: false },
    qwen3_tokenizer_12hz: { name: "Qwen3-TTS Tokenizer", description: "Tokenizer required for Qwen3-TTS.", size: "~50 MB", default: false },
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
        await onDownload(modelId);
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
  }, [selectedModels, onDownload, onRefresh]);

  const handleCancelDownload = useCallback(async () => {
    setIsCancelling(true);
    try {
      await cancelDownload();
    } catch (e) {
      console.error("Cancel failed:", e);
    } finally {
      setTimeout(() => {
        setIsCancelling(false);
        if (onRefresh) onRefresh();
      }, 500);
    }
  }, [cancelDownload, onRefresh]);

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
          <button className="ghost" onClick={onClose}>{t("models.close")}</button>
          {isBatchDownloading && (
            <button 
              className="button button-danger" 
              onClick={handleCancelDownload}
              disabled={isCancelling}
            >
              {isCancelling ? "Cancelling..." : "Cancel Download"}
            </button>
          )}
          {selectedCount > 0 && !isBatchDownloading && (
            <button 
              className="button button-primary button-large" 
              onClick={handleDownloadSelected}
            >
              {t("models.downloadSelected", { count: selectedCount })}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function SettingsPanel({
  t,
  voiceBrowseMode,
  onChangeVoiceBrowseMode,
  onOpenModels,
  onClose,
  perfProfile,
  onChangePerfProfile,
  readingSpeed,
  onChangeReadingSpeed,
  hfTokenStatus,
  hfTokenInput,
  onChangeHfTokenInput,
  onSaveHfToken,
  onClearHfToken,
  hfTokenMessage,
  hfTokenSaving,
  crashReports,
  onChangeCrashReports,
  osNotificationsEnabled,
  onChangeOsNotifications,
  showTutorialOnStartup,
  onChangeShowTutorialOnStartup,
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t("settings.title")}</h2>
          <button className="ghost modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="settings-section">
          <h3>{t("settings.voiceBrowseTitle")}</h3>
          <p className="modal-description">{t("settings.voiceBrowseDescription")}</p>
          <div className="segmented">
            <button
              type="button"
              className={`segmented-btn ${voiceBrowseMode === "model" ? "active" : ""}`}
              onClick={() => onChangeVoiceBrowseMode("model")}
            >
              {t("settings.voiceBrowseModel")}
            </button>
            <button
              type="button"
              className={`segmented-btn ${voiceBrowseMode === "language" ? "active" : ""}`}
              onClick={() => onChangeVoiceBrowseMode("language")}
            >
              {t("settings.voiceBrowseLanguage")}
            </button>
          </div>
        </div>

        <div className="settings-section">
          <h3>{t("settings.performanceTitle")}</h3>
          <p className="modal-description">{t("settings.performanceDescription")}</p>
          <div className="field">
            <label className="label">{t("settings.performanceProfile")}</label>
            <select
              className="input"
              value={perfProfile}
              onChange={(e) => onChangePerfProfile(e.target.value)}
            >
              {Object.entries(PERF_PROFILES).map(([key, profile]) => (
                <option key={key} value={key}>
                  {profile.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="label">{t("settings.readingSpeed", { wpm: readingSpeed })}</label>
            <input
              type="range"
              min="120"
              max="220"
              step="5"
              value={readingSpeed}
              onChange={(e) => onChangeReadingSpeed(parseInt(e.target.value))}
            />
          </div>
        </div>

        <div className="settings-section">
          <h3>{t("settings.modelsTitle")}</h3>
          <p className="modal-description">{t("settings.modelsDescription")}</p>
          <button className="button" onClick={onOpenModels}>
            {t("settings.openModels")}
          </button>
        </div>

        <div className="settings-section">
          <h3>{t("settings.telemetryTitle")}</h3>
          <p className="modal-description">{t("settings.telemetryDescription")}</p>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={crashReports}
              onChange={(e) => onChangeCrashReports(e.target.checked)}
            />
            <span>{t("settings.crashReportsLabel")}</span>
          </label>
        </div>

        <div className="settings-section">
          <h3>{t("settings.notificationsTitle")}</h3>
          <p className="modal-description">{t("settings.notificationsDescription")}</p>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={osNotificationsEnabled}
              onChange={(e) => onChangeOsNotifications(e.target.checked)}
            />
            <span>{t("settings.osNotificationsLabel")}</span>
          </label>
        </div>

        <div className="settings-section">
          <h3>{t("settings.generalTitle", "General")}</h3>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={showTutorialOnStartup}
              onChange={(e) => {
                setShowTutorialOnStartup(e.target.checked);
                storage.set("oratioviva_show_tutorial", String(e.target.checked));
              }}
            />
            <span>{t("settings.showTutorialLabel")}</span>
          </label>
        </div>

        <div className="settings-section">
          <h3>{t("settings.hfTokenTitle")}</h3>
          <p className="modal-description">{t("settings.hfTokenDescription")}</p>
          <div className="field">
            <label className="label">{t("settings.hfTokenLabel")}</label>
            <div className="voice-ref-input-wrapper">
              <input
                className="input"
                type="password"
                placeholder={t("settings.hfTokenPlaceholder")}
                value={hfTokenInput}
                onChange={(e) => onChangeHfTokenInput(e.target.value)}
              />
              {hfTokenInput && (
                <button
                  type="button"
                  className="ghost small clear-voice-ref"
                  onClick={() => onChangeHfTokenInput("")}
                  title={t("settings.hfTokenClear")}
                >
                  ✕
                </button>
              )}
            </div>
            <div className="row">
              <button
                type="button"
                className="button button-secondary"
                onClick={onSaveHfToken}
                disabled={hfTokenSaving}
              >
                {hfTokenSaving ? t("settings.hfTokenSaving") : t("settings.hfTokenSave")}
              </button>
              <button
                type="button"
                className="ghost"
                onClick={onClearHfToken}
                disabled={hfTokenSaving}
              >
                {t("settings.hfTokenClear")}
              </button>
            </div>
            {hfTokenStatus?.hf_token_set && (
              <p className="muted">
                {t("settings.hfTokenSet", { source: hfTokenStatus.hf_token_source })}
              </p>
            )}
            {!hfTokenStatus?.hf_token_set && (
              <p className="muted">{t("settings.hfTokenNotSet")}</p>
            )}
            {hfTokenMessage && <p className="status">{hfTokenMessage}</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

function ToastContainer({ toasts, onDismiss }) {
  return (
    <div className="toast-container">
      {toasts.map(toast => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          <span>{toast.message}</span>
          <button className="toast-close" onClick={() => onDismiss(toast.id)}>✕</button>
        </div>
      ))}
    </div>
  );
}

function GuidedTour({ t, tourSteps, currentStep, onNext, onPrev, onSkip }) {
  const [targetRect, setTargetRect] = useState(null);
  const step = tourSteps[currentStep];

  useEffect(() => {
    if (!step?.target) {
      setTargetRect(null);
      return;
    }
    const el = document.querySelector(step.target);
    if (el) {
      const rect = el.getBoundingClientRect();
      setTargetRect({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      });
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [currentStep, step]);

  if (!step) return null;

  return (
    <div className="tour-overlay">
      {targetRect && (
        <div
          className="tour-spotlight"
          style={{
            top: targetRect.top - 8,
            left: targetRect.left - 8,
            width: targetRect.width + 16,
            height: targetRect.height + 16,
          }}
        />
      )}
      <div className="tour-tooltip" style={{
        top: targetRect ? targetRect.bottom + 20 : "50%",
        left: targetRect ? targetRect.left : "50%",
        transform: targetRect ? "none" : "translate(-50%, -50%)",
      }}>
        <div className="tour-progress">
          {tourSteps.map((_, i) => (
            <div key={i} className={`tour-dot ${i === currentStep ? "active" : ""}`} />
          ))}
        </div>
        <p>{step.content}</p>
        <div className="tour-actions">
          <button className="ghost" onClick={onSkip}>{t("firstRun.skip")}</button>
          <button className="ghost" onClick={onPrev} disabled={currentStep === 0}>{t("firstRun.back")}</button>
          <button className="button" onClick={onNext}>
            {currentStep === tourSteps.length - 1 ? t("firstRun.getStarted") : t("firstRun.next")}
          </button>
        </div>
      </div>
    </div>
  );
}

function ShortcutsModal({ t, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t("help.shortcutsTitle")}</h2>
          <button className="ghost modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="shortcuts-list">
          <div className="shortcut-item">
            <span className="shortcut-keys">Ctrl + Enter</span>
            <span className="shortcut-desc">{t("help.shortcutsContent.generate")}</span>
          </div>
          <div className="shortcut-item">
            <span className="shortcut-keys">Esc</span>
            <span className="shortcut-desc">{t("help.shortcutsContent.clear")}</span>
          </div>
          <div className="shortcut-item">
            <span className="shortcut-keys">Ctrl + C</span>
            <span className="shortcut-desc">{t("help.shortcutsContent.copy")}</span>
          </div>
        </div>
        <div className="modal-footer">
          <button className="button" onClick={onClose}>{t("diagnostics.close")}</button>
        </div>
      </div>
    </div>
  );
}

function ChainModal({ t, onClose, onStart, presets, voices, currentVoice }) {
  const [items, setItems] = useState([{ text: "", voiceId: "", toneId: "", promptId: "" }]);

  const addItem = () => {
    setItems([...items, { text: "", voiceId: "", toneId: "", promptId: "" }]);
  };

  const removeItem = (index) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const updateItem = (index, field, value) => {
    const newItems = [...items];
    newItems[index][field] = value;
    setItems(newItems);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content chain-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t("chain.title")}</h2>
          <button className="ghost modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="chain-items">
          {items.map((item, index) => (
            <div key={index} className="chain-item">
              <div className="chain-item-header">
                <span>{t("chain.itemLabel", { index: index + 1 })}</span>
                {items.length > 1 && (
                  <button className="ghost small" onClick={() => removeItem(index)}>
                    {t("chain.removeItem")}
                  </button>
                )}
              </div>
              <textarea
                className="input"
                placeholder={t("form.placeholder")}
                value={item.text}
                onChange={(e) => updateItem(index, "text", e.target.value)}
              />
              <div className="chain-item-settings">
                <select
                  className="input"
                  value={item.voiceId}
                  onChange={(e) => updateItem(index, "voiceId", e.target.value)}
                >
                  <option value="">{t("form.voiceLabel")}...</option>
                  {voices.map(v => (
                    <option key={v.id} value={v.id}>{v.label || v.id}</option>
                  ))}
                </select>
              </div>
            </div>
          ))}
        </div>
        <button className="ghost" onClick={addItem}>+ {t("chain.addItem")}</button>
        <div className="modal-footer">
          <button className="ghost" onClick={onClose}>{t("cleanup.cancel")}</button>
          <button
            className="button"
            onClick={() => onStart(items)}
            disabled={items.every(i => !i.text.trim())}
          >
            {t("chain.startChain")}
          </button>
        </div>
      </div>
    </div>
  );
}

function DiagnosticsPanel({ t, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetchDiagnostics();
        setData(res);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const formatBytes = (bytes) => {
    if (!bytes) return "N/A";
    const gb = bytes / (1024**3);
    return `${gb.toFixed(2)} GB`;
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content diagnostics-panel" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t("diagnostics.title")}</h2>
          <button className="ghost modal-close" onClick={onClose}>✕</button>
        </div>

        {loading ? (
          <p>{t("diagnostics.loading")}</p>
        ) : error ? (
          <p className="error">{t("diagnostics.error", { error })}</p>
        ) : (
          <div className="diagnostics-content">
            <div className="diag-section">
              <h3>{t("diagnostics.backend")}</h3>
              <div className="diag-grid">
                <div className="diag-item">
                  <span className="diag-label">{t("diagnostics.platform")}:</span>
                  <span className="diag-value">{data?.backend?.platform}</span>
                </div>
                <div className="diag-item">
                  <span className="diag-label">{t("diagnostics.pythonVersion")}:</span>
                  <span className="diag-value">{data?.backend?.python?.version}</span>
                </div>
                <div className="diag-item">
                  <span className="diag-label">{t("diagnostics.status")}:</span>
                  <span className={`diag-value ${data?.backend?.status === "healthy" ? "ok" : "warn"}`}>
                    {data?.backend?.status}
                  </span>
                </div>
              </div>
            </div>

            <div className="diag-section">
              <h3>{t("diagnostics.storage")}</h3>
              <div className="diag-grid">
                <div className="diag-item">
                  <span className="diag-label">{t("diagnostics.outputsFree")}:</span>
                  <span className="diag-value">{formatBytes(data?.storage?.outputs_disk?.free_bytes)}</span>
                </div>
                <div className="diag-item">
                  <span className="diag-label">{t("diagnostics.modelsFree")}:</span>
                  <span className="diag-value">{formatBytes(data?.storage?.models_disk?.free_bytes)}</span>
                </div>
                <div className="diag-item">
                  <span className="diag-label">{t("diagnostics.outputsDir")}:</span>
                  <span className="diag-value small">{data?.storage?.outputs_dir}</span>
                </div>
              </div>
            </div>

            <div className="diag-section">
              <h3>{t("diagnostics.settings")}</h3>
              <div className="diag-grid">
                <div className="diag-item">
                  <span className="diag-label">{t("diagnostics.hfToken")}:</span>
                  <span className={`diag-value ${data?.settings?.hf_token_set ? "ok" : "warn"}`}>
                    {data?.settings?.hf_token_set ? t("diagnostics.set") : t("diagnostics.notSet")}
                  </span>
                </div>
                <div className="diag-item">
                  <span className="diag-label">{t("diagnostics.provider")}:</span>
                  <span className="diag-value">{data?.settings?.provider}</span>
                </div>
              </div>
            </div>

            <div className="diag-section">
              <h3>{t("diagnostics.models")}</h3>
              <div className="diag-item">
                <span className="diag-label">{t("diagnostics.availableModels")}:</span>
                <span className="diag-value">{data?.models?.available?.join(", ") || t("diagnostics.none")}</span>
              </div>
              <div className="diag-item">
                <span className="diag-label">{t("diagnostics.downloading")}:</span>
                <span className="diag-value">{data?.models?.downloading ? t("diagnostics.yes") : t("diagnostics.no")}</span>
              </div>
            </div>

            {data?.last_errors?.length > 0 && (
              <div className="diag-section">
                <h3>{t("diagnostics.lastErrors")}</h3>
                <div className="error-log">
                  {data.last_errors.map((err, i) => (
                    <div key={i} className="error-line">{err}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="modal-footer">
          <button className="button" onClick={onClose}>{t("diagnostics.close")}</button>
        </div>
      </div>
    </div>
  );
}

function CleanupPanel({ t, onClose, diagnostics }) {
  const [deletingAudio, setDeletingAudio] = useState(true);
  const [deletingHistory, setDeletingHistory] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [result, setResult] = useState(null);

  const handleCleanup = async () => {
    setCleaning(true);
    setResult(null);
    try {
      const res = await runCleanup({
        delete_audio: deletingAudio,
        delete_history: deletingHistory,
      });
      setResult(res);
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setCleaning(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content cleanup-panel" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t("cleanup.title")}</h2>
          <button className="ghost modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="cleanup-content">
          <div className="cleanup-info">
            <p className="muted">{t("cleanup.description")}</p>
            <div className="cleanup-stats">
              <div className="stat">
                <span className="stat-label">{t("cleanup.outputsFree")}:</span>
                <span className="stat-value">
                  {diagnostics?.storage?.outputs_disk?.free_gb} GB
                </span>
              </div>
            </div>
          </div>

          <div className="cleanup-options">
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={deletingAudio}
                onChange={(e) => setDeletingAudio(e.target.checked)}
              />
              <span>{t("cleanup.deleteAudioFiles")}</span>
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={deletingHistory}
                onChange={(e) => setDeletingHistory(e.target.checked)}
              />
              <span>{t("cleanup.deleteHistory")}</span>
            </label>
          </div>

          {result && (
            <div className={`cleanup-result ${result.error ? "error" : "success"}`}>
              {result.error ? (
                <p>{t("cleanup.error", { error: result.error })}</p>
              ) : (
                <div>
                  <p>{t("cleanup.success")}</p>
                  <ul>
                    {result.deleted?.audio_files > 0 && (
                      <li>{t("cleanup.deletedAudio", { count: result.deleted.audio_files })}</li>
                    )}
                    {result.deleted?.history_items > 0 && (
                      <li>{t("cleanup.deletedHistory")}</li>
                    )}
                    {result.deleted?.models?.length > 0 && (
                      <li>{t("cleanup.deletedModels", { models: result.deleted.models.join(", ") })}</li>
                    )}
                    {result.deleted?.audio_files === 0 && result.deleted?.history_items === 0 && !result.deleted?.models?.length && (
                      <li>{t("cleanup.nothingDeleted")}</li>
                    )}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="ghost" onClick={onClose}>{t("cleanup.cancel")}</button>
          <button
            className="button button-danger"
            onClick={handleCleanup}
            disabled={cleaning || (!deletingAudio && !deletingHistory)}
          >
            {cleaning ? t("cleanup.cleaning") : t("cleanup.cleanup")}
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
  const currentVoice = voices.find((voice) => voice.id === voiceId);
  const [speed, setSpeed] = useState(1);
  const [style, setStyle] = useState("");
  const [voicePrompt, setVoicePrompt] = useState("");
  const [autoPunctuate, setAutoPunctuate] = useState(true);
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
    needsDownload: false,
    provider: "auto",
    providerMessage: "",
    models: [],
    searchPaths: [],
    bundledPath: null,
  });
  const autoDownloadAttempted = useRef(false);
  const [synthesisProgress, setSynthesisProgress] = useState(0);
  const [synthesisStatus, setSynthesisStatus] = useState("");
  const [retryJob, setRetryJob] = useState(null);
  const [backendReady, setBackendReady] = useState(false);
  const [apiBase, setApiBase] = useState(getApiBase());
  const [showModelsPanel, setShowModelsPanel] = useState(false);
  const [showLongAudioModal, setShowLongAudioModal] = useState(false);
  const autoDownloadModels = useRef(new Set());
  const [showSettingsPanel, setShowSettingsPanel] = useState(false);
  const [voiceBrowseMode, setVoiceBrowseMode] = useState(() => {
    if (typeof window === "undefined") return "model";
    return storage.get("oratioviva_voice_browse_mode") || "model";
  });
  const [perfProfile, setPerfProfile] = useState(() => {
    if (typeof window === "undefined") return "rtx3090";
    return storage.get("oratioviva_perf_profile") || "rtx3090";
  });
  const [readingSpeed, setReadingSpeed] = useState(() => {
    if (typeof window === "undefined") return DEFAULT_WPM;
    const stored = storage.get("oratioviva_reading_wpm");
    return stored ? parseInt(stored, 10) : DEFAULT_WPM;
  });
  const [qualityMode, setQualityMode] = useState(() => {
    if (typeof window === "undefined") return "balanced";
    return storage.get("oratioviva_quality_mode") || "balanced";
  });
  const [analytics, setAnalytics] = useState(null);
  const [hfTokenStatus, setHfTokenStatus] = useState({
    hf_token_set: false,
    hf_token_source: "none",
  });
  const [hfTokenInput, setHfTokenInput] = useState("");
  const [hfTokenMessage, setHfTokenMessage] = useState("");
  const [hfTokenSaving, setHfTokenSaving] = useState(false);
  const [presets, setPresets] = useState({ tones: [], prompts: [], defaults: {} });
  const [toneId, setToneId] = useState("");
  const [promptId, setPromptId] = useState("");
  const [showPresetsPanel, setShowPresetsPanel] = useState(false);
  const [editingTone, setEditingTone] = useState(null);
  const [editingPrompt, setEditingPrompt] = useState(null);
  const [modelCapabilities, setModelCapabilities] = useState({ style: true, voice_prompt: true, voice_ref: false });
  const [diagnostics, setDiagnostics] = useState(null);
  const [showDiagnosticsPanel, setShowDiagnosticsPanel] = useState(false);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [showFirstRunGuide, setShowFirstRunGuide] = useState(false);
  const [showCleanupPanel, setShowCleanupPanel] = useState(false);
  const [crashReports, setCrashReports] = useState(false);
  const [showTutorialOnStartup, setShowTutorialOnStartup] = useState(true);
  const [showHelpMenu, setShowHelpMenu] = useState(false);
  const [showGuidedTour, setShowGuidedTour] = useState(false);
  const [showShortcutsModal, setShowShortcutsModal] = useState(false);
  const [tourStep, setTourStep] = useState(0);
  const [toasts, setToasts] = useState([]);
  const [osNotificationsEnabled, setOsNotificationsEnabled] = useState(false);
  const [showChainModal, setShowChainModal] = useState(false);
  const [chainItems, setChainItems] = useState([{ text: "", voiceId: "", toneId: "", promptId: "" }]);
  const [chainProgress, setChainProgress] = useState({ current: 0, total: 0, status: "idle" });
  const [showTutorial, setShowTutorial] = useState(false);

  useEffect(() => {
    const savedVoice = storage.get("oratioviva_voice");
    const savedSpeed = storage.get("oratioviva_speed");
    const savedStyle = storage.get("oratioviva_style");
    const savedVoicePrompt = storage.get("oratioviva_voice_prompt");
    const savedAutoPunctuate = storage.get("oratioviva_auto_punctuate");
    const savedVoiceRef = storage.get("oratioviva_voiceRef");
    if (savedVoice) setVoiceId(savedVoice);
    if (savedSpeed) setSpeed(parseFloat(savedSpeed));
    if (savedStyle) setStyle(savedStyle);
    if (savedVoicePrompt) setVoicePrompt(savedVoicePrompt);
    if (savedAutoPunctuate !== null) {
      setAutoPunctuate(savedAutoPunctuate === "true");
    }
    if (savedVoiceRef) {
      const ext = savedVoiceRef.split('.').pop().toLowerCase();
      const audioExts = ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac', 'webm'];
      if (savedVoiceRef.startsWith('http') || audioExts.includes(ext)) {
        setVoiceRef(savedVoiceRef);
      } else {
        storage.remove("oratioviva_voiceRef");
        setVoiceRef("");
      }
    }
  }, []);

  useEffect(() => {
    if (voiceId) storage.set("oratioviva_voice", voiceId);
    else storage.remove("oratioviva_voice");
  }, [voiceId]);

  useEffect(() => {
    storage.set("oratioviva_speed", speed.toString());
  }, [speed]);

  useEffect(() => {
    if (style) storage.set("oratioviva_style", style);
    else storage.remove("oratioviva_style");
  }, [style]);

  useEffect(() => {
    if (voicePrompt) storage.set("oratioviva_voice_prompt", voicePrompt);
    else storage.remove("oratioviva_voice_prompt");
  }, [voicePrompt]);

  useEffect(() => {
    storage.set("oratioviva_auto_punctuate", autoPunctuate ? "true" : "false");
  }, [autoPunctuate]);

  useEffect(() => {
    if (voiceRef) {
      const ext = voiceRef.split('.').pop().toLowerCase();
      const audioExts = ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'aac', 'webm'];
      if (voiceRef.startsWith('http') || audioExts.includes(ext)) {
        storage.set("oratioviva_voiceRef", voiceRef);
      }
    } else {
      storage.remove("oratioviva_voiceRef");
    }
  }, [voiceRef]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    storage.set("oratioviva_voice_browse_mode", voiceBrowseMode);
  }, [voiceBrowseMode]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    storage.set("oratioviva_perf_profile", perfProfile);
  }, [perfProfile]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    storage.set("oratioviva_reading_wpm", readingSpeed.toString());
  }, [readingSpeed]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    storage.set("oratioviva_quality_mode", qualityMode);
  }, [qualityMode]);

  useEffect(() => {
    if (toneId) storage.set("oratioviva_tone_id", toneId);
    else storage.remove("oratioviva_tone_id");
  }, [toneId]);

  useEffect(() => {
    if (promptId) storage.set("oratioviva_prompt_id", promptId);
    else storage.remove("oratioviva_prompt_id");
  }, [promptId]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedTone = storage.get("oratioviva_tone_id");
      const savedPrompt = storage.get("oratioviva_prompt_id");
      if (savedTone) setToneId(savedTone);
      if (savedPrompt) setPromptId(savedPrompt);
    }
  }, []);

  useEffect(() => {
    if (currentVoice?.model) {
      fetchModelCapabilities(currentVoice.model)
        .then(res => setModelCapabilities(res.capabilities || { style: true, voice_prompt: true, voice_ref: false }))
        .catch(() => setModelCapabilities({ style: true, voice_prompt: true, voice_ref: false }));
    }
  }, [currentVoice?.model]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const hasSeenGuide = storage.get("oratioviva_has_seen_guide");
      if (!hasSeenGuide && backendReady) {
        setTimeout(() => setShowFirstRunGuide(true), 500);
      }
      // Also show tutorial on startup if enabled
      const showTutorial = storage.get("oratioviva_show_tutorial");
      if (showTutorial !== "false" && backendReady && !showTutorialOnStartup) {
        // showTutorialOnStartup defaults to true, so we show if not explicitly disabled
      }
    }
  }, [backendReady]);

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
        refreshAnalytics();
        return;
      }
      await new Promise(r => setTimeout(r, 1000));
      attempts++;
    }
  }, [checkBackend, voiceId]);

  const refreshSettings = useCallback(async () => {
    try {
      const res = await fetchSettings();
      if (res) {
        setHfTokenStatus(res);
      }
      const telemetry = await getTelemetrySettings();
      setCrashReports(telemetry.crash_reports || false);
    } catch (e) {
      console.error("Failed to fetch settings:", e);
    }
  }, []);

  const handleChangeCrashReports = useCallback(async (enabled) => {
    setCrashReports(enabled);
    try {
      await setTelemetrySettings({ crash_reports: enabled });
    } catch (e) {
      console.error("Failed to save telemetry settings:", e);
    }
  }, []);

  const handleSaveHfToken = useCallback(async () => {
    setHfTokenSaving(true);
    setHfTokenMessage("");
    try {
      await saveHfToken(hfTokenInput);
      setHfTokenMessage(
        hfTokenInput ? t("settings.hfTokenSaved") : t("settings.hfTokenCleared")
      );
      setHfTokenInput("");
      await refreshSettings();
    } catch (e) {
      setHfTokenMessage(
        t("settings.hfTokenError", { error: e.message || "Save failed" })
      );
    } finally {
      setHfTokenSaving(false);
      setTimeout(() => setHfTokenMessage(""), 3000);
    }
  }, [hfTokenInput, refreshSettings, t]);

  const handleClearHfToken = useCallback(async () => {
    setHfTokenSaving(true);
    setHfTokenMessage("");
    try {
      await saveHfToken("");
      setHfTokenMessage(t("settings.hfTokenCleared"));
      setHfTokenInput("");
      await refreshSettings();
    } catch (e) {
      setHfTokenMessage(
        t("settings.hfTokenError", { error: e.message || "Clear failed" })
      );
    } finally {
      setHfTokenSaving(false);
      setTimeout(() => setHfTokenMessage(""), 3000);
    }
  }, [refreshSettings, t]);

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
        needsDownload: res.needs_download || false,
        models: res.models || [],
        provider: res.provider || "auto",
        providerMessage: res.provider_message || "",
        searchPaths: res.search_paths || [],
        bundledPath: res.bundled_path || null,
      });
    } catch { /* noop */ }
  }

  async function refreshAnalytics() {
    try {
      const res = await fetchAnalytics();
      setAnalytics(res);
    } catch { /* noop */ }
  }

  async function refreshPresets() {
    try {
      const res = await fetchPresets();
      setPresets(res);
      if (!toneId && res.defaults?.tone) {
        setToneId(res.defaults.tone);
      }
      if (!promptId && res.defaults?.prompt) {
        setPromptId(res.defaults.prompt);
      }
    } catch { /* noop */ }
  }

  useEffect(() => {
    if (backendReady) {
      refreshPresets();
    }
  }, [backendReady]);

  useEffect(() => {
    let timer;
    if (modelState.downloading) {
      timer = setInterval(refreshModels, MODEL_POLL_MS);
    }
    return () => { if (timer) clearInterval(timer); };
  }, [modelState.downloading]);

  useEffect(() => {
    if (!backendReady || autoDownloadAttempted.current) return;
    if (!modelState.models.length) return;
    if (modelState.downloading || modelState.downloadProgress) return;

    const baseModel = modelState.models.find((model) => model.id === "dia2");
    if (!baseModel || baseModel.exists) return;

    autoDownloadAttempted.current = true;
    downloadModels(["dia2"])
      .then(() => refreshModels())
      .catch((err) => {
        console.error("Auto-download of Dia2 failed:", err);
      });
  }, [
    backendReady,
    modelState.models,
    modelState.downloading,
    modelState.downloadProgress,
  ]);

  useEffect(() => {
    let timer;
    timer = setInterval(refreshJobs, JOBS_POLL_MS);
    return () => { if (timer) clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (!backendReady) return undefined;
    const timer = setInterval(refreshAnalytics, 10000);
    return () => clearInterval(timer);
  }, [backendReady]);


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

  function resolveModelIdForVoice(voice) {
    if (!voice) return null;
    const modelMap = {
      dia2: "dia2",
      parler: "parler",
      bark: "bark",
      speecht5: "speecht5",
      mms: "mms",
      xtts: "xtts",
      "f5-tts": "f5_tts",
      f5_tts: "f5_tts",
      cosyvoice: "cosyvoice",
      chroma: "chroma_4b",
      qwen: "qwen3_tts",
    };
    const lowerModel = (voice.model || "").toLowerCase();
    const lowerId = (voice.id || "").toLowerCase();
    for (const [needle, modelId] of Object.entries(modelMap)) {
      if (
        lowerId.includes(needle) ||
        lowerModel.includes(needle) ||
        lowerId.includes(modelId) ||
        lowerModel.includes(modelId)
      ) {
        return modelId;
      }
    }
    return null;
  }

  function getVoiceModelId(voiceId) {
    const voice = voices.find(v => v.id === voiceId);
    return resolveModelIdForVoice(voice);
  }

  function getRequiredModelsForModel(modelId) {
    return MODEL_DEPENDENCIES[modelId] || (modelId ? [modelId] : []);
  }

  function getRequiredModelsForVoice(voiceId) {
    const modelId = getVoiceModelId(voiceId);
    if (!modelId) return [];
    return getRequiredModelsForModel(modelId);
  }

  function areRequiredModelsAvailable(voiceId) {
    const required = getRequiredModelsForVoice(voiceId);
    if (!required.length) return true;
    return required.every((id) => {
      const model = modelState.models.find(m => m.id === id);
      return model?.exists === true;
    });
  }

  async function maybeAutoDownloadModels(voiceId) {
    if (modelState.downloading) return false;
    const required = getRequiredModelsForVoice(voiceId);
    if (!required.length) return false;
    const missing = required.filter((id) => {
      const model = modelState.models.find(m => m.id === id);
      return !model?.exists;
    });
    if (!missing.length) return false;

    const key = missing.sort().join(",");
    if (autoDownloadModels.current.has(key)) return true;
    autoDownloadModels.current.add(key);
    setStatus(`Downloading required model(s): ${missing.join(", ")}...`);
    try {
      await downloadModels(missing);
      await refreshModels();
    } catch (err) {
      setStatus(`Model download failed: ${err.message}`);
    }
    return true;
  }

  function showToast(message, type = "info", duration = 4000) {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, duration);
  }

  function dismissToast(id) {
    setToasts(prev => prev.filter(t => t.id !== id));
  }

  function sendOsNotification(title, body) {
    if (!osNotificationsEnabled || !notificationApi) return;
    try {
      if (notificationApi.sendNotification) {
        notificationApi.sendNotification({ title, body });
      } else if (notificationApi.isPermissionGranted?.()) {
        notificationApi.sendNotification({ title, body });
      } else {
        notificationApi.requestPermission().then(permission => {
          if (permission === "granted") {
            notificationApi.sendNotification({ title, body });
          }
        });
      }
    } catch (e) {
      console.warn("OS notification failed:", e);
    }
  }

  const tourSteps = [
    { target: ".toolbar", content: t("tour.stepToolbar") },
    { target: ".hero", content: t("tour.stepHero") },
    { target: ".form .input.textarea", content: t("tour.stepTextInput") },
    { target: ".estimator-panel", content: t("tour.stepEstimator") },
    { target: ".voice-browser-section", content: t("tour.stepVoiceBrowser") },
    { target: ".field input[type='range']", content: t("tour.stepSpeed") },
    { target: ".segmented", content: t("tour.stepQuality") },
    { target: "select[name='tone']", content: t("tour.stepTone") },
    { target: "select[name='prompt']", content: t("tour.stepVoiceDirection") },
    { target: "input[placeholder*='style']", content: t("tour.stepStyle") },
    { target: "textarea[placeholder*='warm']", content: t("tour.stepVoicePrompt") },
    { target: "input[placeholder*='voice.wav']", content: t("tour.stepVoiceRef") },
    { target: ".form-actions .button", content: t("tour.stepGenerate") },
    { target: ".history", content: t("tour.stepHistory") },
    { target: ".jobs", content: t("tour.stepQueue") },
    { target: ".analytics", content: t("tour.stepAnalytics") },
    { target: ".toolbar .ghost:nth-child(5)", content: t("tour.stepSettings") },
  ];

  function nextTourStep() {
    if (tourStep < tourSteps.length - 1) {
      setTourStep(tourStep + 1);
    } else {
      setShowGuidedTour(false);
      storage.set("oratioviva_has_seen_tour", "true");
    }
  }

  function prevTourStep() {
    if (tourStep > 0) {
      setTourStep(tourStep - 1);
    }
  }

  function skipTour() {
    setShowGuidedTour(false);
    storage.set("oratioviva_has_seen_tour", "true");
  }

  async function handleDownloadModel(modelId) {
    const required = getRequiredModelsForModel(modelId);
    if (!required.length) return;
    try {
      setStatus(`Downloading ${required.join(", ")}...`);
      await downloadModels(required);
      await refreshModels();
    } catch (err) {
      setStatus(`Model download failed: ${err.message}`);
    }
  }

  async function pollJob(jobId) {
    let attempts = 0;
    const maxAttempts = 180;
    const startedAt = Date.now();
    const words = countWords(text);
    const audioSeconds = estimateAudioSeconds(words, readingSpeed);
    const estimatedSeconds = estimateGenerationSeconds(
      audioSeconds,
      currentVoice?.model,
      perfProfile,
    );
    const statusMessages = [
      { progress: 10, message: "Initializing..." },
      { progress: 20, message: "Loading model..." },
      { progress: 40, message: "Processing text..." },
      { progress: 60, message: "Generating audio..." },
      { progress: 80, message: "Finalizing..." },
    ];

    while (attempts < maxAttempts) {
      let job;
      try {
        job = await fetchJob(jobId);
      } catch (err) {
        if (err.message && err.message.includes("Job not found")) {
          setSynthesisProgress(0);
          setSynthesisStatus("");
          throw new Error("Backend restarted during synthesis. Please retry.");
        }
        throw err;
      }
      const progressIndex = Math.min(attempts, statusMessages.length - 1);
      setSynthesisStatus(statusMessages[progressIndex]?.message || "In progress...");
      const base = statusMessages[progressIndex]?.progress ?? 10;
      const elapsedSeconds = (Date.now() - startedAt) / 1000;
      const estimatedProgress =
        estimatedSeconds > 0 ? (elapsedSeconds / estimatedSeconds) * 100 : null;
      // Smooth progress while polling: monotonic and capped until job completes.
      setSynthesisProgress((prev) => {
        const target = estimatedProgress ?? (base + attempts * 1.2);
        const next = Math.max(prev || 0, target);
        return Math.min(99, next);
      });

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

    const isLongAudio = text.length > LONG_TEXT_THRESHOLD || longAudioOptions;

    if (isLongAudio && !longAudioOptions) {
      setShowLongAudioModal(true);
      return;
    }

    if (!areRequiredModelsAvailable(voiceId)) {
      await maybeAutoDownloadModels(voiceId);
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
          quality: qualityMode,
          tone_id: toneId || undefined,
          prompt_id: promptId || undefined,
          voice_prompt: voicePrompt || undefined,
          auto_punctuate: autoPunctuate,
          style: style || undefined,
          voice_ref: voiceRef || undefined,
          chunk_size: longAudioOptions.chunkSize,
          parallel: longAudioOptions.parallel,
        });
      } else {
        job = await createSynthesis(
          {
            text,
            voice_id: voiceId,
            speed,
            quality: qualityMode,
            tone_id: toneId || undefined,
            prompt_id: promptId || undefined,
            voice_prompt: voicePrompt || undefined,
            auto_punctuate: autoPunctuate,
            style: style || undefined,
            voice_ref: voiceRef || undefined,
          },
          { asyncMode: true },
        );
      }
      await pollJob(job.job_id);
      setStatus(t("status.synthDone"));
      sendOsNotification("OratioViva", t("status.synthDone"));
      await refreshHistory();
      await refreshJobs();
    } catch (err) {
      setStatus(t("status.synthError", { error: err.message }));
      setRetryJob({
        text,
        voiceId,
        speed,
        qualityMode,
        style,
        voicePrompt,
        autoPunctuate,
        voiceRef,
      });
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
      setQualityMode(retryJob.qualityMode || "balanced");
      setStyle(retryJob.style || "");
      setVoicePrompt(retryJob.voicePrompt || "");
      setAutoPunctuate(Boolean(retryJob.autoPunctuate));
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

  async function handleExportMp3() {
    if (selectedHistory.size === 0) {
      setStatus("Select at least one item to export.");
      return;
    }
    try {
      setStatus("Converting to MP3...");
      const url = await exportMp3(Array.from(selectedHistory));
      const a = document.createElement("a");
      a.href = url;
      a.download = selectedHistory.size === 1 ? "oratioviva-audio.mp3" : "oratioviva-audio-mp3.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setStatus("MP3 export downloaded.");
      clearSelection();
    } catch (err) {
      setStatus(err.message || "MP3 export failed. Ensure ffmpeg is installed.");
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

  const currentModelId = getVoiceModelId(voiceId);
  const currentModelReady = areRequiredModelsAvailable(voiceId);

  const wordCount = countWords(text);
  const estimatedAudioSeconds = estimateAudioSeconds(wordCount, readingSpeed);
  const estimatedGenSeconds = estimateGenerationSeconds(
    estimatedAudioSeconds,
    currentModelId,
    perfProfile,
  );
  const estimatedGenLow = estimatedGenSeconds * 0.7;
  const estimatedGenHigh = estimatedGenSeconds * 1.3;
  const analyticsAvgRtf = analytics?.rtf?.average || null;
  const analyticsModelRtf =
    (currentVoice?.model && analytics?.rtf?.by_model?.[currentVoice.model]) || null;

  const voicesByModel = useMemo(() => {
    const groups = {};
    for (const voice of voices) {
      const modelId = resolveModelIdForVoice(voice) || voice.model;
      if (!groups[modelId]) groups[modelId] = [];
      groups[modelId].push(voice);
    }
    return groups;
  }, [voices]);

  const voicesByLanguage = useMemo(() => {
    const groups = {};
    for (const voice of voices) {
      const lang = (voice.language || "unknown").toLowerCase();
      if (!groups[lang]) groups[lang] = [];
      groups[lang].push(voice);
    }
    return groups;
  }, [voices]);

  const sortedLanguages = useMemo(() => {
    return Object.keys(voicesByLanguage).sort((a, b) => a.localeCompare(b));
  }, [voicesByLanguage]);

  const missingModels = useMemo(
    () => modelState.models.filter((model) => !model.exists),
    [modelState.models],
  );

  const needsLongAudio = text.length > LONG_TEXT_THRESHOLD;

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
          onDownload={handleDownloadModel}
          downloadProgress={modelState.downloadProgress}
          isDownloading={modelState.downloading}
          onRefresh={refreshModels}
          onClose={() => setShowModelsPanel(false)}
        />
      )}

      {showSettingsPanel && (
        <SettingsPanel
          t={t}
          voiceBrowseMode={voiceBrowseMode}
          onChangeVoiceBrowseMode={setVoiceBrowseMode}
          onOpenModels={() => {
            setShowSettingsPanel(false);
            setShowModelsPanel(true);
          }}
          onClose={() => setShowSettingsPanel(false)}
          perfProfile={perfProfile}
          onChangePerfProfile={setPerfProfile}
          readingSpeed={readingSpeed}
          onChangeReadingSpeed={setReadingSpeed}
          hfTokenStatus={hfTokenStatus}
          hfTokenInput={hfTokenInput}
          onChangeHfTokenInput={setHfTokenInput}
          onSaveHfToken={handleSaveHfToken}
          onClearHfToken={handleClearHfToken}
          hfTokenMessage={hfTokenMessage}
          hfTokenSaving={hfTokenSaving}
          crashReports={crashReports}
          onChangeCrashReports={handleChangeCrashReports}
          osNotificationsEnabled={osNotificationsEnabled}
          onChangeOsNotifications={setOsNotificationsEnabled}
          showTutorialOnStartup={showTutorialOnStartup}
          onChangeShowTutorialOnStartup={setShowTutorialOnStartup}
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

      {showPresetsPanel && (
        <PresetsPanel
          t={t}
          presets={presets}
          onClose={() => setShowPresetsPanel(false)}
          onRefresh={refreshPresets}
        />
      )}

      {showFirstRunGuide && (
        <FirstRunGuide
          t={t}
          onClose={() => setShowFirstRunGuide(false)}
        />
      )}

      {showDiagnosticsPanel && (
        <DiagnosticsPanel
          t={t}
          onClose={() => setShowDiagnosticsPanel(false)}
        />
      )}

      {showCleanupPanel && (
        <CleanupPanel
          t={t}
          onClose={() => setShowCleanupPanel(false)}
          diagnostics={diagnostics}
        />
      )}

      {showGuidedTour && (
        <GuidedTour
          t={t}
          tourSteps={tourSteps}
          currentStep={tourStep}
          onNext={nextTourStep}
          onPrev={prevTourStep}
          onSkip={skipTour}
        />
      )}

      {showShortcutsModal && (
        <ShortcutsModal
          t={t}
          onClose={() => setShowShortcutsModal(false)}
        />
      )}

      {showChainModal && (
        <ChainModal
          t={t}
          onClose={() => setShowChainModal(false)}
          onStart={(items) => {
            setShowChainModal(false);
            showToast(t("chain.startChain"), "info");
          }}
          presets={presets}
          voices={voices}
          currentVoice={currentVoice}
        />
      )}

      {showTutorial && (
        <TutorialPlayer
          t={t}
          onClose={() => setShowTutorial(false)}
        />
      )}

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

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
          <button className="ghost" onClick={() => { setShowDiagnosticsPanel(true); }}>
            {t("toolbar.diagnostics")}
          </button>
          <button className="ghost" onClick={() => { setShowCleanupPanel(true); }}>
            {t("toolbar.cleanup")}
          </button>
          <button className="ghost" onClick={() => { refreshModels(); refreshSettings(); setShowSettingsPanel(true); }}>
            {t("toolbar.settings")}
          </button>
          <div className="help-menu-container">
            <button
              className="ghost"
              onClick={() => setShowHelpMenu(!showHelpMenu)}
            >
              {t("help.title")}
            </button>
            {showHelpMenu && (
              <div className="help-dropdown">
                <button onClick={() => { setShowHelpMenu(false); setShowGuidedTour(true); setTourStep(0); }}>
                  {t("help.startTour")}
                </button>
                <button onClick={() => { setShowHelpMenu(false); setShowTutorial(true); }}>
                  {t("help.tutorial")}
                </button>
                <button onClick={() => { setShowHelpMenu(false); setShowShortcutsModal(true); }}>
                  {t("help.shortcuts")}
                </button>
                <button onClick={() => setShowHelpMenu(false)}>
                  {t("help.whatsNew")}
                </button>
              </div>
            )}
          </div>
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

            <div className="estimator-panel" aria-live="polite">
              <div>
                <span className="estimator-label">{t("analytics.estimatedAudio")}</span>
                <strong>{formatDuration(estimatedAudioSeconds)}</strong>
                <span className="estimator-muted">
                  {wordCount} {t("analytics.words")}
                </span>
              </div>
              <div>
                <span className="estimator-label">{t("analytics.estimatedGeneration")}</span>
                <strong>
                  {formatDuration(estimatedGenLow)} – {formatDuration(estimatedGenHigh)}
                </strong>
                <span className="estimator-muted">
                  {PERF_PROFILES[perfProfile]?.label || perfProfile}
                </span>
              </div>
              {(analyticsModelRtf || analyticsAvgRtf) && (
                <div>
                  <span className="estimator-label">{t("analytics.avgRealtime")}</span>
                  <strong>
                    {(analyticsModelRtf || analyticsAvgRtf).toFixed(2)}x
                  </strong>
                  <span className="estimator-muted">
                    {analyticsModelRtf ? t("analytics.modelBased") : t("analytics.globalBased")}
                  </span>
                </div>
              )}
            </div>

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

            <div className="field voice-browser-section">
              <div className="label-row">
                <label className="label">{t("form.voiceLabel")}</label>
                <span className="voice-view-chip">
                  {voiceBrowseMode === "model"
                    ? t("settings.voiceBrowseModel")
                    : t("settings.voiceBrowseLanguage")}
                </span>
              </div>
              <div className="voice-browser">
                {voiceBrowseMode === "model" ? (
                  <div className="voice-model-grid">
                    {modelState.models.map((model) => {
                      const modelVoices = voicesByModel[model.id] || [];
                      const installed = model.exists;
                      const isDownloading = modelState.downloadProgress?.model_id === model.id;
                      const modelName = model.repo_id.split("/")[1] || model.repo_id;
                      return (
                        <div
                          key={model.id}
                          className={`voice-model-card ${installed ? "installed" : "missing"}`}
                        >
                          <div className="voice-model-header">
                            <div>
                              <h4>{modelName}</h4>
                              <span className="model-repo">{model.repo_id}</span>
                            </div>
                            {installed ? (
                              <span className="badge badge-ok">{t("models.installed")}</span>
                            ) : (
                              <button
                                type="button"
                                className="button button-primary button-small"
                                onClick={() => handleDownloadModel(model.id)}
                                disabled={modelState.downloading}
                              >
                                {isDownloading ? t("models.downloading") : t("models.download")}
                              </button>
                            )}
                          </div>

                          {installed ? (
                            <VoiceWheel
                              voices={modelVoices}
                              selectedId={voiceId}
                              onSelect={setVoiceId}
                              centerLabel={modelName}
                            />
                          ) : (
                            <div className="voice-locked">
                              <p>
                                {t("models.downloadToUnlock", { count: modelVoices.length })}
                              </p>
                              {isDownloading && (
                                <ProgressBar
                                  progress={modelState.downloadProgress?.progress}
                                  message={modelState.downloadProgress?.message}
                                />
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="voice-language-grid">
                    {sortedLanguages.map((lang) => {
                      const voicesForLang = voicesByLanguage[lang] || [];
                      const availableVoices = voicesForLang.filter((voice) =>
                        areRequiredModelsAvailable(voice.id),
                      );
                      if (!availableVoices.length) return null;
                      return (
                        <div key={lang} className="voice-language-card">
                          <div className="voice-language-header">
                            <h4>{LANGUAGE_LABELS[lang] || lang.toUpperCase()}</h4>
                            <span className="badge">{availableVoices.length} presets</span>
                          </div>
                          <VoiceWheel
                            voices={availableVoices}
                            selectedId={voiceId}
                            onSelect={setVoiceId}
                            centerLabel={LANGUAGE_LABELS[lang] || lang.toUpperCase()}
                          />
                        </div>
                      );
                    })}
                    {missingModels.length > 0 && (
                      <div className="voice-missing-models">
                        <h4>{t("models.missingModels")}</h4>
                        <div className="missing-model-list">
                          {missingModels.map((model) => {
                            const modelName = model.repo_id.split("/")[1] || model.repo_id;
                            return (
                              <button
                                key={model.id}
                                type="button"
                                className="ghost small"
                                onClick={() => handleDownloadModel(model.id)}
                              >
                                ↓ {modelName}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="inline">
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
              <label className="label">{t("form.qualityLabel")}</label>
              <div className="segmented">
                <button
                  type="button"
                  className={`segmented-btn ${qualityMode === "fast" ? "active" : ""}`}
                  onClick={() => setQualityMode("fast")}
                >
                  {t("form.qualityFast")}
                </button>
                <button
                  type="button"
                  className={`segmented-btn ${qualityMode === "balanced" ? "active" : ""}`}
                  onClick={() => setQualityMode("balanced")}
                >
                  {t("form.qualityBalanced")}
                </button>
                <button
                  type="button"
                  className={`segmented-btn ${qualityMode === "quality" ? "active" : ""}`}
                  onClick={() => setQualityMode("quality")}
                >
                  {t("form.qualityQuality")}
                </button>
              </div>
              <p className="muted">{t("form.qualityHint")}</p>
            </div>

            <div className="field">
              <div className="row space" style={{ marginBottom: "0.5rem" }}>
                <label className="label" style={{ marginBottom: 0 }}>{t("form.toneLabel")}</label>
                <button
                  type="button"
                  className="ghost small"
                  onClick={() => setShowPresetsPanel(true)}
                >
                  {t("form.managePresets")}
                </button>
              </div>
              <select
                className="input"
                value={toneId}
                onChange={(e) => setToneId(e.target.value)}
              >
                <option value="">{t("form.noTone")}</option>
                {(presets.tones || []).filter(p => !p.category || p.category === "tts").map((tone) => (
                  <option key={tone.id} value={tone.id}>
                    {tone.name}{tone.is_custom ? " *" : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label className="label">{t("form.promptLabel")}</label>
              <select
                className="input"
                value={promptId}
                onChange={(e) => setPromptId(e.target.value)}
              >
                <option value="">{t("form.noPrompt")}</option>
                {(presets.prompts || []).filter(p => !p.category || p.category === "tts").map((prompt) => (
                  <option key={prompt.id} value={prompt.id}>
                    {prompt.name}{prompt.is_custom ? " *" : ""}
                  </option>
                ))}
              </select>
            </div>

            {!modelCapabilities.style && (
              <p className="muted">{t("form.toneNotSupported")}</p>
            )}

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
              <label className="label">{t("form.voicePromptLabel")}</label>
              <textarea
                className="input textarea"
                rows={3}
                placeholder={t("form.voicePromptPlaceholder")}
                value={voicePrompt}
                onChange={(e) => setVoicePrompt(e.target.value)}
              />
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={autoPunctuate}
                  onChange={(e) => setAutoPunctuate(e.target.checked)}
                />
                <span>{t("form.autoPunctuateLabel")}</span>
              </label>
              <p className="muted">{t("form.autoPunctuateHint")}</p>
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
              {!modelCapabilities.voice_ref && voiceRef && (
                <p className="warning">{t("safeguards.voiceRefNotSupported")}</p>
              )}
            </div>

            {!modelCapabilities.style && (style || toneId) && (
              <p className="warning">{t("safeguards.styleNotSupported")}</p>
            )}

            {!modelCapabilities.voice_prompt && (voicePrompt || promptId) && (
              <p className="warning">{t("safeguards.voicePromptNotSupported")}</p>
            )}

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
                  Long Text ({Math.ceil(text.length / DEFAULT_CHUNK_SIZE)} chunks)
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
              <button className="ghost" onClick={handleExportMp3}>{t("export.exportMp3")}</button>
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

      <section className="card analytics">
        <div className="history-header">
          <div>
            <p className="eyebrow">{t("analytics.title")}</p>
            <h2>{t("analytics.metrics")}</h2>
          </div>
          <div className="row">
            <button className="ghost" onClick={refreshAnalytics}>{t("analytics.refresh")}</button>
          </div>
        </div>
        {!analytics ? (
          <p className="muted">{t("analytics.loading")}</p>
        ) : (
          <div className="analytics-grid">
            <div className="analytics-card">
              <h4>{t("analytics.runtime")}</h4>
              <p>{analytics.provider}</p>
              {analytics.provider_message && (
                <small className="muted">{analytics.provider_message}</small>
              )}
            </div>
            <div className="analytics-card">
              <h4>{t("analytics.activity")}</h4>
              <p>
                {t("analytics.historyItems")}: {analytics.counts?.history || 0}
              </p>
              <p>
                {t("analytics.jobsStored")}: {analytics.counts?.jobs || 0}
              </p>
              <p>
                {t("analytics.audioDuration")}: {formatDuration(analytics.counts?.audio_duration_seconds || 0)}
              </p>
            </div>
            <div className="analytics-card">
              <h4>{t("analytics.estimator")}</h4>
              <p>
                {t("analytics.estimatedAudio")}: {formatDuration(estimatedAudioSeconds)}
              </p>
              <p>
                {t("analytics.estimatedGeneration")}: {formatDuration(estimatedGenLow)} – {formatDuration(estimatedGenHigh)}
              </p>
              <p>
                {t("analytics.estimationProfile")}: {PERF_PROFILES[perfProfile]?.label || perfProfile}
              </p>
              <p>
                {t("analytics.readingSpeed", { wpm: readingSpeed })}
              </p>
              {(analyticsModelRtf || analyticsAvgRtf) && (
                <p>
                  {t("analytics.avgRealtime")}: {(analyticsModelRtf || analyticsAvgRtf).toFixed(2)}x
                </p>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
