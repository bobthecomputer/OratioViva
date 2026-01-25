from __future__ import annotations

import io
import json
import os
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.cleanup import run_from_env
from backend.jobs import JobStatus, JobStore
from backend.models import ModelManager
from backend.tts import TTSService, VOICE_PRESETS, AudioResult, chunk_audio_files


def resolve_base_dir() -> Path:
    """Locate base directory for outputs; supports env override."""
    data_dir_env = os.getenv("ORATIO_DATA_DIR")
    if data_dir_env:
        return Path(data_dir_env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def resolve_models_dir() -> Path:
    """Resolve models directory from environment or default."""
    models_dir_env = os.getenv("ORATIO_MODELS_DIR")
    if models_dir_env:
        return Path(models_dir_env).expanduser().resolve()
    return resolve_base_dir() / "models"


def resolve_outputs_dir() -> Path:
    """Resolve outputs directory from environment or default."""
    outputs_dir_env = os.getenv("ORATIO_OUTPUTS_DIR")
    if outputs_dir_env:
        return Path(outputs_dir_env).expanduser().resolve()
    return resolve_base_dir() / "outputs"


def resolve_logs_dir() -> Path:
    """Resolve logs directory from environment or default."""
    logs_dir_env = os.getenv("ORATIO_LOG_DIR")
    if logs_dir_env:
        return Path(logs_dir_env).expanduser().resolve()
    return resolve_base_dir() / "logs"


BASE_DIR = resolve_base_dir()
MODELS_DIR = resolve_models_dir()
OUTPUT_DIR = resolve_outputs_dir()
LOGS_DIR = resolve_logs_dir()

# If desktop bootstrapper provides a CA bundle, apply it for all outbound HTTPS
# (huggingface_hub/requests, worker subprocesses inherit env).
_ca_bundle = os.getenv("ORATIO_CA_BUNDLE")
if _ca_bundle and Path(_ca_bundle).exists():
    os.environ.setdefault("SSL_CERT_FILE", _ca_bundle)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca_bundle)
    os.environ.setdefault("CURL_CA_BUNDLE", _ca_bundle)
AUDIO_DIR = OUTPUT_DIR / "audio"
HISTORY_PATH = OUTPUT_DIR / "history.json"
JOBS_PATH = OUTPUT_DIR / "jobs.json"

HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
# Stub mode should be an explicit user choice.
USE_STUB = os.getenv("ORATIO_TTS_STUB", "0") == "1"
MAX_JOBS = int(os.getenv("ORATIO_JOBS_MAX", "300"))
MAX_TEXT_LENGTH = int(os.getenv("ORATIO_TEXT_MAX", "20000"))
MAX_LONG_TEXT_LENGTH = int(os.getenv("ORATIO_LONG_TEXT_MAX", "200000"))
TTS_PROVIDER = os.getenv(
    "ORATIO_TTS_PROVIDER", "auto"
)  # auto | inference | local | stub
MODELS_DIR_ENV = os.getenv("ORATIO_MODELS_DIR")
OPTIONAL_MODELS = {
    m.strip().lower()
    for m in os.getenv(
        "ORATIO_OPTIONAL_MODELS",
        "kokoro,chroma_4b,qwen3_tts,qwen3_tokenizer_12hz",
    ).split(",")
    if m.strip()
}


def find_bundled_models() -> Optional[Path]:
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path.cwd()))
        candidate = bundle_root / "models"
        if candidate.exists():
            return candidate
    elif hasattr(sys, "_MEIPASS2"):
        bundle_root = Path(getattr(sys, "_MEIPASS2", Path.cwd()))
        candidate = bundle_root / "models"
        if candidate.exists():
            return candidate
    tauri_resource_dir = os.getenv("TAURI_RESOURCE_DIR")
    if tauri_resource_dir:
        candidate = Path(tauri_resource_dir) / "models"
        if candidate.exists():
            return candidate
    return None


BUNDLED_MODELS_DIR = find_bundled_models()
if MODELS_DIR_ENV:
    MODELS_DIR = Path(MODELS_DIR_ENV).expanduser().resolve()
else:
    MODELS_DIR = BASE_DIR / "models"


class SynthesisRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    voice_id: str = Field("parler_en_neutral")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    style: Optional[str] = Field(
        None,
        description="Optional style/prompt (used for Parler or other style-aware models).",
    )
    voice_ref: Optional[str] = Field(
        None,
        description="Optional voice reference (path or URL) for voice cloning models.",
    )


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    generation_seconds: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    model: Optional[str] = None
    voice_id: Optional[str] = None
    source: Optional[str] = None
    error: Optional[str] = None


class ExportRequest(BaseModel):
    job_ids: List[str] = Field(
        ..., min_length=1, description="List of job_ids to include."
    )


class BatchDeleteRequest(BaseModel):
    job_ids: List[str] = Field(
        ..., min_length=1, description="List of job_ids to delete."
    )
    delete_audio: bool = Field(
        True, description="When deleting history, also delete audio files."
    )


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
    HISTORY_PATH.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
    )


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


app = FastAPI(title="OratioViva API", version="0.6.6")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_directories()
model_manager = ModelManager(
    base_dir=BASE_DIR,
    models_dir=MODELS_DIR,
    token=HF_TOKEN,
    optional_models=OPTIONAL_MODELS,
    extra_dirs=[BUNDLED_MODELS_DIR] if BUNDLED_MODELS_DIR else None,
)
tts_service = TTSService(
    audio_dir=AUDIO_DIR,
    base_audio_url="/audio",
    use_stub=USE_STUB or TTS_PROVIDER == "stub",
    fallback_stub=False,
    provider=TTS_PROVIDER,
    models_dir=MODELS_DIR,
    model_manager=model_manager,
)
job_store = JobStore(path=JOBS_PATH, max_items=MAX_JOBS)
run_from_env(AUDIO_DIR, HISTORY_PATH)

job_store.clear()
write_history([])

app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")


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
    progress = model_manager.get_download_progress()
    return {
        "models": [
            {
                "id": s.id,
                "repo_id": s.repo_id,
                "exists": s.exists,
                "path": str(s.path),
                "local_supported": tts_service.local_support(s.repo_id)[0],
                "local_reason": tts_service.local_support(s.repo_id)[1],
            }
            for s in statuses
        ],
        "search_paths": model_manager.get_search_paths(),
        "bundled_path": str(BUNDLED_MODELS_DIR) if BUNDLED_MODELS_DIR else None,
        "downloading": model_manager.downloading,
        "download_error": model_manager.download_error,
        "download_progress": {
            "model_id": progress.model_id if progress else None,
            "repo_id": progress.repo_id if progress else None,
            "progress": progress.progress if progress else 0.0,
            "downloaded_bytes": progress.downloaded_bytes if progress else 0,
            "total_bytes": progress.total_bytes if progress else 0,
            "status": progress.status if progress else "idle",
            "message": progress.message if progress else "",
        }
        if model_manager.downloading or progress
        else None,
        "needs_download": model_manager.needs_download(),
        "provider": tts_service.current_provider(),
        "provider_message": tts_service.provider_message(statuses),
    }


@app.post("/models/download")
def models_download(body: ModelDownloadRequest, background_tasks: BackgroundTasks):
    if model_manager.downloading:
        return {"status": "running"}

    def _download():
        model_manager.download(body.models)

    background_tasks.add_task(_download)
    return {"status": "started"}


@app.post("/models/download/cancel")
def models_download_cancel():
    model_manager.cancel_current_download()
    return {"status": "cancelled"}


@app.delete("/models/download")
def models_download_delete(body: ModelDownloadRequest):
    """Delete a partially or fully downloaded model to allow re-download."""
    from backend.models import MODEL_ALIASES

    deleted = []
    if body.models:
        for model_key in body.models:
            repo_id = MODEL_ALIASES.get(model_key, model_key)
            model_dir = MODELS_DIR / repo_id.replace("/", "_")
            if model_dir.exists():
                import shutil

                try:
                    shutil.rmtree(model_dir)
                    deleted.append(model_key)
                except Exception as e:
                    return {"status": "error", "message": str(e)}
            else:
                deleted.append(f"{model_key} (not found)")
    return {"status": "deleted", "models": deleted}


@app.get("/analytics")
def analytics():
    statuses = model_manager.status()
    history = load_history()
    jobs = job_store.list(limit=100)
    audio_duration = sum((item.get("duration_seconds") or 0) for item in history)
    rtf_values = []
    rtf_by_model: Dict[str, List[float]] = {}
    for item in history:
        gen = item.get("generation_seconds")
        dur = item.get("duration_seconds")
        model = item.get("model") or "unknown"
        if not gen or not dur:
            continue
        if dur <= 0:
            continue
        rtf = gen / dur
        rtf_values.append(rtf)
        rtf_by_model.setdefault(model, []).append(rtf)

    avg_rtf = sum(rtf_values) / len(rtf_values) if rtf_values else None
    avg_rtf_by_model = {
        key: (sum(values) / len(values)) for key, values in rtf_by_model.items()
    }
    return {
        "provider": tts_service.current_provider(),
        "provider_message": tts_service.provider_message(statuses),
        "models": [
            {
                "id": s.id,
                "repo_id": s.repo_id,
                "exists": s.exists,
                "local_supported": tts_service.local_support(s.repo_id)[0],
                "local_reason": tts_service.local_support(s.repo_id)[1],
            }
            for s in statuses
        ],
        "search_paths": model_manager.get_search_paths(),
        "bundled_path": str(BUNDLED_MODELS_DIR) if BUNDLED_MODELS_DIR else None,
        "counts": {
            "history": len(history),
            "jobs": len(jobs),
            "audio_duration_seconds": audio_duration,
        },
        "rtf": {
            "average": avg_rtf,
            "by_model": avg_rtf_by_model,
        },
        "jobs_recent": [j for j in jobs[:5]],
        "history_recent": history[:5],
    }


def _record_history(
    result, text: str, generation_seconds: Optional[float] = None
) -> None:
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
    if generation_seconds is not None:
        entry["generation_seconds"] = generation_seconds
        if result.duration_seconds:
            entry["realtime_factor"] = generation_seconds / result.duration_seconds
    append_history(entry)


def _run_job(
    job_id: str,
    text: str,
    voice_id: str,
    speed: float,
    style: Optional[str],
    voice_ref: Optional[str],
) -> JobStatus:
    from backend.tts import validate_voice_ref

    if voice_ref and voice_ref.strip():
        try:
            voice_ref = validate_voice_ref(voice_ref)
        except ValueError:
            return job_store.update(
                job_id,
                status="failed",
                error="Invalid voice reference file. Please select an audio file (.wav, .mp3, .ogg, .flac, .m4a, .aac, .webm).",
            )

    job_store.update(job_id, status="running")
    try:
        start_time = time.perf_counter()
        result = tts_service.synthesize(
            text=text,
            voice_id=voice_id,
            speed=speed,
            style=style,
            voice_ref=voice_ref,
            job_id=job_id,
        )
        generation_seconds = time.perf_counter() - start_time
        _record_history(result, text, generation_seconds=generation_seconds)
        status = job_store.update(
            job_id,
            status="succeeded",
            audio_url=result.audio_url,
            duration_seconds=result.duration_seconds,
            generation_seconds=generation_seconds,
            model=result.model,
            voice_id=result.voice_id,
            source=result.source,
        )
        return status
    except Exception as exc:  # noqa: BLE001
        return job_store.update(job_id, status="failed", error=str(exc))


@app.post("/synthesize", response_model=JobStatusResponse)
def synthesize(
    request: SynthesisRequest,
    background_tasks: BackgroundTasks,
    async_mode: bool = False,
):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text payload cannot be empty.")
    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail="Long text exceeds maximum allowed length.",
        )

    if request.voice_ref and request.voice_ref.strip():
        ext = Path(request.voice_ref).suffix.lower()
        audio_exts = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".webm"}
        if not request.voice_ref.startswith("http") and ext not in audio_exts:
            raise HTTPException(
                status_code=400,
                detail="Invalid voice reference. Select an audio file (.wav, .mp3, .ogg, .flac, .m4a, .aac, .webm). Images are not supported.",
            )

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
            request.voice_ref,
        )
        job = job_store.get(job_id)
        assert job is not None
        return JobStatusResponse(**job.__dict__)

    job = _run_job(
        job_id, text, request.voice_id, request.speed, request.style, request.voice_ref
    )
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
        raise HTTPException(
            status_code=404, detail="No audio files found for given jobs"
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for path in files:
            zip_file.write(path, arcname=Path(path).name)
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="oratioviva-audio.zip"'}
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)


class LongAudioRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice_id: str = Field("parler_en_neutral")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    style: Optional[str] = Field(None)
    voice_ref: Optional[str] = Field(None)
    chunk_size: int = Field(2000, ge=500, le=12000)
    parallel: bool = Field(False)


@app.post("/synthesize/long", response_model=JobStatusResponse)
def synthesize_long(
    request: LongAudioRequest,
    background_tasks: BackgroundTasks,
):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text payload cannot be empty.")

    job_id = str(uuid.uuid4())
    job_store.create(job_id, status="queued")

    background_tasks.add_task(
        _run_long_job,
        job_id,
        text,
        request.voice_id,
        request.speed,
        request.style,
        request.voice_ref,
        request.chunk_size,
        request.parallel,
    )

    job = job_store.get(job_id)
    assert job is not None
    return JobStatusResponse(**job.__dict__)


def _split_text_into_chunks(text: str, chunk_size: int) -> List[str]:
    paragraphs = text.replace("\n\n", "|||").replace("\n", " ").split("|||")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        while len(para) > chunk_size:
            split_point = para.rfind(" ", 0, chunk_size)
            if split_point == -1:
                split_point = chunk_size
            chunks.append(para[:split_point].strip())
            para = para[split_point:].strip()

        if current_chunk and (len(current_chunk) + len(para) > chunk_size):
            chunks.append(current_chunk)
            current_chunk = para
        else:
            current_chunk = (
                (current_chunk + " " + para).strip() if current_chunk else para
            )

    if current_chunk:
        chunks.append(current_chunk)

    return chunks if chunks else [text]


def _run_long_job(
    job_id: str,
    text: str,
    voice_id: str,
    speed: float,
    style: Optional[str],
    voice_ref: Optional[str],
    chunk_size: int,
    parallel: bool,
) -> JobStatus:
    from backend.tts import validate_voice_ref

    if voice_ref and voice_ref.strip():
        try:
            voice_ref = validate_voice_ref(voice_ref)
        except ValueError:
            return job_store.update(
                job_id,
                status="failed",
                error="Invalid voice reference file. Please select an audio file (.wav, .mp3, .ogg, .flac, .m4a, .aac, .webm).",
            )

    from backend.tts import chunk_audio_files

    job_store.update(job_id, status="running")
    try:
        start_time = time.perf_counter()
        chunks = _split_text_into_chunks(text, chunk_size)
        total_chunks = len(chunks)

        if total_chunks == 1:
            return _run_job(job_id, text, voice_id, speed, style, voice_ref)

        from backend.tts import VOICE_BY_ID

        voice = VOICE_BY_ID.get(voice_id)
        model_id = (voice.model or "").lower() if voice else ""
        is_qwen = "qwen3-tts" in model_id

        chunk_job_ids = []
        for i, chunk in enumerate(chunks):
            chunk_job_id = f"{job_id}_chunk_{i}"
            chunk_job_ids.append(chunk_job_id)
            job_store.create(chunk_job_id, status="queued")
            job_store.update(
                chunk_job_id,
                status="pending",
                source=f"chunk {i + 1}/{total_chunks}",
            )

        job_store.update(
            job_id,
            status="running",
            source=f"Processing {total_chunks} chunks ({'parallel' if parallel else 'sequential'})",
        )

        if is_qwen:
            try:
                results = tts_service.synthesize_qwen3_customvoice_batch(
                    chunks=chunks,
                    voice_id=voice_id,
                    job_ids=chunk_job_ids,
                    speed=speed,
                    style=style,
                )
                for idx, result in enumerate(results):
                    job_store.update(
                        chunk_job_ids[idx],
                        status="succeeded",
                        audio_url=result.audio_url,
                        duration_seconds=result.duration_seconds,
                        model=result.model,
                        voice_id=result.voice_id,
                        source=f"chunk {idx + 1}/{total_chunks}",
                    )
                valid_results = results
            except Exception as exc:
                for cid in chunk_job_ids:
                    job_store.update(cid, status="failed", error=str(exc))
                return job_store.update(job_id, status="failed", error=str(exc))
        elif parallel:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            def process_chunk(chunk_idx):
                chunk_text = chunks[chunk_idx]
                cid = chunk_job_ids[chunk_idx]
                try:
                    result = tts_service.synthesize(
                        text=chunk_text,
                        voice_id=voice_id,
                        speed=speed,
                        style=style,
                        voice_ref=voice_ref,
                        job_id=cid,
                    )
                    job_store.update(
                        cid,
                        status="succeeded",
                        audio_url=result.audio_url,
                        duration_seconds=result.duration_seconds,
                        model=result.model,
                        voice_id=result.voice_id,
                        source=f"chunk {chunk_idx + 1}/{total_chunks}",
                    )
                    return result
                except Exception as exc:
                    job_store.update(cid, status="failed", error=str(exc))
                    return None

            max_workers = max(1, int(os.getenv("ORATIO_LONG_PARALLEL_WORKERS", "4")))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(process_chunk, range(total_chunks)))

            valid_results = [r for r in results if r is not None]
        else:
            valid_results = []
            for i, chunk in enumerate(chunks):
                cid = chunk_job_ids[i]
                job_store.update(cid, status="running")
                try:
                    result = tts_service.synthesize(
                        text=chunk,
                        voice_id=voice_id,
                        speed=speed,
                        style=style,
                        voice_ref=voice_ref,
                        job_id=cid,
                    )
                    job_store.update(
                        cid,
                        status="succeeded",
                        audio_url=result.audio_url,
                        duration_seconds=result.duration_seconds,
                        model=result.model,
                        voice_id=result.voice_id,
                        source=f"chunk {i + 1}/{total_chunks}",
                    )
                    valid_results.append(result)
                except Exception as exc:
                    job_store.update(cid, status="failed", error=str(exc))

        if not valid_results:
            generation_seconds = time.perf_counter() - start_time
            return job_store.update(
                job_id,
                status="failed",
                error="All chunks failed",
                generation_seconds=generation_seconds,
            )

        audio_paths = [r.audio_path for r in valid_results if r.audio_path]
        if len(audio_paths) == 1:
            combined_path = Path(audio_paths[0])
            combined_result = valid_results[0]
        else:
            combined_path = AUDIO_DIR / f"{job_id}_combined.wav"
            combined_path = chunk_audio_files(
                [Path(p) for p in audio_paths], combined_path
            )

        if combined_path.exists():
            combined_result = AudioResult(
                job_id=job_id,
                audio_path=combined_path,
                audio_url=f"/audio/{combined_path.name}",
                duration_seconds=sum(r.duration_seconds or 0 for r in valid_results),
                created_at=datetime.now(timezone.utc),
                model=valid_results[0].model if valid_results else voice_id,
                voice_id=voice_id,
                source=f"combined {len(valid_results)} chunks",
            )
            generation_seconds = time.perf_counter() - start_time
            _record_history(
                combined_result,
                f"[{len(chunks)} chunks] {text[:160]}...",
                generation_seconds=generation_seconds,
            )
            return job_store.update(
                job_id,
                status="succeeded",
                audio_url=combined_result.audio_url,
                duration_seconds=combined_result.duration_seconds,
                generation_seconds=generation_seconds,
                model=combined_result.model,
                voice_id=voice_id,
                source=f"combined {len(valid_results)}/{total_chunks} chunks",
            )
        else:
            generation_seconds = time.perf_counter() - start_time
            return job_store.update(
                job_id,
                status="failed",
                error="Failed to combine chunks",
                generation_seconds=generation_seconds,
            )

    except Exception as exc:
        generation_seconds = time.perf_counter() - start_time
        return job_store.update(
            job_id,
            status="failed",
            error=str(exc),
            generation_seconds=generation_seconds,
        )


if __name__ == "__main__":
    import uvicorn

    reload_flag = os.getenv("ORATIO_RELOAD", "0") == "1"
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=reload_flag)
