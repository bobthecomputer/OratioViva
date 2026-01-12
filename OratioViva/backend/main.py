from __future__ import annotations

import io
import json
import os
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.cleanup import run_from_env
from backend.jobs import JobStatus, JobStore
from backend.models import ModelManager
from backend.tts import TTSService, VOICE_PRESETS


def resolve_base_dir() -> Path:
    """Locate base directory for outputs; supports PyInstaller (frozen) + env override."""
    data_dir_env = os.getenv("ORATIO_DATA_DIR")
    if data_dir_env:
        return Path(data_dir_env).expanduser().resolve()
    if getattr(sys, "frozen", False):
        # When packaged, default to the working directory of the executable.
        return Path.cwd()
    return Path(__file__).resolve().parent.parent


def resolve_frontend_dist(base_dir: Path) -> Path:
    env_dir = os.getenv("ORATIO_FRONTEND_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    if getattr(sys, "frozen", False):
        # When frozen, PyInstaller exposes bundled files under _MEIPASS.
        bundle_root = Path(getattr(sys, "_MEIPASS", Path.cwd()))
        return bundle_root / "frontend" / "dist"
    return base_dir / "frontend" / "dist"


BASE_DIR = resolve_base_dir()
OUTPUT_DIR = BASE_DIR / "outputs"
AUDIO_DIR = OUTPUT_DIR / "audio"
HISTORY_PATH = OUTPUT_DIR / "history.json"
JOBS_PATH = OUTPUT_DIR / "jobs.json"

HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
USE_STUB = os.getenv("ORATIO_TTS_STUB", "0") == "1"
MAX_JOBS = int(os.getenv("ORATIO_JOBS_MAX", "300"))
TTS_PROVIDER = os.getenv("ORATIO_TTS_PROVIDER", "auto")  # auto | inference | local | stub
MODELS_DIR_ENV = os.getenv("ORATIO_MODELS_DIR")
if MODELS_DIR_ENV:
    MODELS_DIR = Path(MODELS_DIR_ENV).expanduser().resolve()
elif getattr(sys, "frozen", False):
    bundle_root = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    candidate = bundle_root / "models"
    MODELS_DIR = candidate if candidate.exists() else None
else:
    MODELS_DIR = BASE_DIR / "models"
FRONTEND_DIST = resolve_frontend_dist(BASE_DIR)


class SynthesisRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=6000)
    voice_id: str = Field("kokoro_en_us_0")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    style: Optional[str] = Field(
        None, description="Optional style/prompt (used for Parler or other style-aware models)."
    )


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    model: Optional[str] = None
    voice_id: Optional[str] = None
    source: Optional[str] = None
    error: Optional[str] = None


class ExportRequest(BaseModel):
    job_ids: List[str] = Field(..., min_length=1, description="List of job_ids to include.")


class BatchDeleteRequest(BaseModel):
    job_ids: List[str] = Field(..., min_length=1, description="List of job_ids to delete.")
    delete_audio: bool = Field(True, description="When deleting history, also delete audio files.")


class ModelDownloadRequest(BaseModel):
    models: Optional[List[str]] = Field(
        None, description="Optional list of model aliases/repo_ids to download."
    )


def ensure_directories() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_history() -> List[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def write_history(entries: List[dict]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def append_history(entry: dict) -> None:
    history = load_history()
    history.insert(0, entry)
    write_history(history)


def delete_history_entry(job_id: str, delete_audio: bool = True) -> bool:
    history = load_history()
    remaining = []
    removed = False
    for entry in history:
        if entry.get("job_id") == job_id:
            removed = True
            if delete_audio:
                audio_path = entry.get("audio_path")
                if audio_path and Path(audio_path).exists():
                    try:
                        Path(audio_path).unlink()
                    except OSError:
                        pass
            continue
        remaining.append(entry)
    if removed:
        write_history(remaining)
    return removed


def collect_audio_files(job_ids: List[str]) -> List[Path]:
    history = load_history()
    selected = []
    requested = set(job_ids)
    for entry in history:
        if entry.get("job_id") in requested:
            audio_path = entry.get("audio_path")
            if audio_path and Path(audio_path).exists():
                selected.append(Path(audio_path))
    return selected


app = FastAPI(title="OratioViva API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_directories()
model_manager = ModelManager(base_dir=BASE_DIR, models_dir=MODELS_DIR, token=HF_TOKEN)
tts_service = TTSService(
    audio_dir=AUDIO_DIR,
    base_audio_url="/audio",
    hf_token=HF_TOKEN,
    use_stub=USE_STUB or TTS_PROVIDER == "stub",
    fallback_stub=False,
    provider=TTS_PROVIDER,
    models_dir=MODELS_DIR,
    model_manager=model_manager,
)
job_store = JobStore(path=JOBS_PATH, max_items=MAX_JOBS)
# Cleanup on startup (best-effort)
run_from_env(AUDIO_DIR, HISTORY_PATH)

app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
if FRONTEND_DIST.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc),
        "use_stub": USE_STUB,
        "provider": tts_service.current_provider(),
        "voices": len(VOICE_PRESETS),
        "history_items": len(load_history()),
        "jobs": len(job_store.list(limit=9999)),
    }


@app.get("/voices")
def list_voices():
    return {"voices": tts_service.list_voices()}


@app.get("/models/status")
def models_status():
    statuses = model_manager.status()
    return {
        "models": [
            {"id": s.id, "repo_id": s.repo_id, "exists": s.exists, "path": str(s.path)}
            for s in statuses
        ],
        "downloading": model_manager.downloading,
        "needs_download": model_manager.needs_download(),
        "provider": tts_service.current_provider(),
    }


@app.post("/models/download")
def models_download(body: ModelDownloadRequest, background_tasks: BackgroundTasks):
    if model_manager.downloading:
        return {"status": "running"}

    def _download():
        model_manager.download(body.models)

    background_tasks.add_task(_download)
    return {"status": "started"}


def _record_history(result, text: str) -> None:
    entry = {
        "job_id": result.job_id,
        "text_preview": text[:160],
        "model": result.model,
        "voice_id": result.voice_id,
        "audio_path": str(result.audio_path),
        "audio_url": result.audio_url,
        "duration_seconds": result.duration_seconds,
        "created_at": result.created_at.isoformat(),
        "source": result.source,
    }
    append_history(entry)


def _run_job(job_id: str, text: str, voice_id: str, speed: float, style: Optional[str]) -> JobStatus:
    job_store.update(job_id, status="running")
    try:
        result = tts_service.synthesize(
            text=text,
            voice_id=voice_id,
            speed=speed,
            style=style,
            job_id=job_id,
        )
        _record_history(result, text)
        status = job_store.update(
            job_id,
            status="succeeded",
            audio_url=result.audio_url,
            duration_seconds=result.duration_seconds,
            model=result.model,
            voice_id=result.voice_id,
            source=result.source,
        )
        return status
    except Exception as exc:  # noqa: BLE001
        return job_store.update(job_id, status="failed", error=str(exc))


@app.post("/synthesize", response_model=JobStatusResponse)
def synthesize(request: SynthesisRequest, background_tasks: BackgroundTasks, async_mode: bool = False):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text payload cannot be empty.")
    job_id = str(uuid.uuid4())
    job_store.create(job_id, status="queued")

    if async_mode:
        background_tasks.add_task(
            _run_job,
            job_id,
            text,
            request.voice_id,
            request.speed,
            request.style,
        )
        job = job_store.get(job_id)
        assert job is not None
        return JobStatusResponse(**job.__dict__)

    job = _run_job(job_id, text, request.voice_id, request.speed, request.style)
    return JobStatusResponse(**job.__dict__)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**job.__dict__)


@app.get("/jobs")
def job_list(limit: int = 50):
    jobs = job_store.list(limit=limit)
    return {"items": [job.__dict__ for job in jobs]}


@app.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    removed = job_store.delete(job_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "ok"}


@app.post("/jobs/batch_delete")
def batch_delete_jobs(body: BatchDeleteRequest):
    deleted = 0
    for job_id in body.job_ids:
        if job_store.delete(job_id):
            deleted += 1
    if deleted == 0:
        raise HTTPException(status_code=404, detail="No jobs deleted")
    return {"status": "ok", "deleted": deleted}


@app.get("/history")
def history(limit: int = 20):
    history = load_history()[:limit]
    return {"items": history}


@app.delete("/history/{job_id}")
def delete_history(job_id: str):
    removed = delete_history_entry(job_id, delete_audio=True)
    if not removed:
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"status": "ok"}


@app.post("/history/batch_delete")
def batch_delete_history(body: BatchDeleteRequest):
    deleted = 0
    for job_id in body.job_ids:
        if delete_history_entry(job_id, delete_audio=body.delete_audio):
            deleted += 1
    if deleted == 0:
        raise HTTPException(status_code=404, detail="No history entries deleted")
    return {"status": "ok", "deleted": deleted}


@app.post("/maintenance/cleanup")
def cleanup_endpoint():
    summary = run_from_env(AUDIO_DIR, HISTORY_PATH)
    return {"status": "ok", "cleanup": summary}


@app.post("/export/zip")
def export_zip(body: ExportRequest):
    files = collect_audio_files(body.job_ids)
    if not files:
        raise HTTPException(status_code=404, detail="No audio files found for given jobs")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for path in files:
            zip_file.write(path, arcname=Path(path).name)
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="oratioviva-audio.zip"'}
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)


if __name__ == "__main__":
    import uvicorn

    reload_flag = os.getenv("ORATIO_RELOAD", "0") == "1"
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=reload_flag)
