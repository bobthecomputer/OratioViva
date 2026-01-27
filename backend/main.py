from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
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
SETTINGS_PATH = OUTPUT_DIR / "settings.json"
SETTINGS_VERSION = 1
ERROR_LOG_PATH = OUTPUT_DIR / "error.log"


def log_error(message: str, exc: Optional[Exception] = None) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    error_line = f"[{timestamp}] {message}"
    if exc:
        error_line += f": {type(exc).__name__}: {str(exc)}"
    try:
        ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(error_line + "\n")
    except Exception:
        pass


def migrate_settings(data: Dict[str, Any], from_version: int) -> Dict[str, Any]:
    if from_version < 1:
        pass
    return data


def load_settings() -> Dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {"_version": SETTINGS_VERSION}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            current_version = data.get("_version", 0)
            if current_version < SETTINGS_VERSION:
                data = migrate_settings(data, current_version)
                data["_version"] = SETTINGS_VERSION
                save_settings(data)
            return data
    except json.JSONDecodeError:
        pass
    return {"_version": SETTINGS_VERSION}


def save_settings(settings: Dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings["_version"] = SETTINGS_VERSION
    clean_settings = {k: v for k, v in settings.items() if v is not None}
    SETTINGS_PATH.write_text(
        json.dumps(clean_settings, indent=2, ensure_ascii=False), encoding="utf-8"
    )


_settings = load_settings()
_env_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
_hf_token_from_settings = (
    _settings.get("hf_token") if isinstance(_settings, dict) else None
)
HF_TOKEN = _env_token or (
    _hf_token_from_settings if isinstance(_hf_token_from_settings, str) else None
)
if HF_TOKEN and not _env_token:
    os.environ.setdefault("HF_TOKEN", HF_TOKEN)
    os.environ.setdefault("HUGGINGFACEHUB_API_TOKEN", HF_TOKEN)
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

PRESETS_PATH = OUTPUT_DIR / "presets.json"


class TonePreset(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    style: Optional[str] = None
    voice_prompt: Optional[str] = None
    category: str = "tts"
    is_default: bool = False


class PromptPreset(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    style: Optional[str] = None
    voice_prompt: Optional[str] = None
    category: str = "tts"
    is_default: bool = False


DEFAULT_TONE_PRESETS = [
    TonePreset(
        id="neutral",
        name="Neutral",
        description="Standard, balanced delivery with natural prosody",
        style="Neutral speaker, clear voice, studio quality. Natural pacing with proper breathing.",
        voice_prompt="Neutral delivery, consistent volume, clear articulation, natural pauses.",
        category="tts",
        is_default=True,
    ),
    TonePreset(
        id="expressive",
        name="Expressive",
        description="Animated, emotional delivery with dynamic variations",
        style="Expressive speaker, emotional depth, dynamic tone variations, theatrical flair.",
        voice_prompt="Warm, confident, steady pace, clear pauses after each sentence. Use emotional depth.",
        category="tts",
    ),
    TonePreset(
        id="calm",
        name="Calm & Soothing",
        description="Gentle, peaceful delivery with relaxed pacing",
        style="Calm speaker, slow pace, gentle, soothing tone with soft dynamics.",
        voice_prompt="Soft, soothing, relaxed breathing between phrases. Lower volume, gentle inflections.",
        category="tts",
    ),
    TonePreset(
        id="authoritative",
        name="Authoritative",
        description="Strong, confident delivery with commanding presence",
        style="Authoritative speaker, strong presence, clear articulation, commanding tone.",
        voice_prompt="Confident, authoritative, steady rhythm, emphasize key words, project power.",
        category="tts",
    ),
    TonePreset(
        id="news_anchor",
        name="News Anchor",
        description="Professional broadcast style for informative content",
        style="Professional news anchor, neutral but engaging, broadcast-quality delivery.",
        voice_prompt="Clear, professional, measured pace, proper enunciation, broadcast standards.",
        category="tts",
    ),
    TonePreset(
        id="storyteller",
        name="Storyteller",
        description="Engaging narrative voice for books and stories",
        style="Warm narrator, engaging, brings stories to life with character.",
        voice_prompt="Storytelling voice, varied pacing, slight dramatization, natural flow, character voices.",
        category="tts",
    ),
    TonePreset(
        id="suspenseful",
        name="Suspenseful",
        description="Tense, mysterious delivery for thrillers and horror",
        style="Tense, suspenseful narrator, lowered voice, controlled tension.",
        voice_prompt="Suspenseful, whispers, tense pauses, building dread, controlled breathing.",
        category="tts",
    ),
    TonePreset(
        id="whisper",
        name="Whisper",
        description="Intimate, quiet delivery for secrets or romance",
        style="Intimate whisper, very soft, breathy, personal tone.",
        voice_prompt="Whispered, soft, breathy, intimate, lowered volume throughout.",
        category="tts",
    ),
    TonePreset(
        id="cheerful",
        name="Cheerful",
        description="Happy, upbeat delivery with positive energy",
        style="Cheerful speaker, bright tone, positive energy, warm smile in voice.",
        voice_prompt="Happy, upbeat, bright tone, warm smile, energetic inflections.",
        category="tts",
    ),
    TonePreset(
        id="sad_melancholy",
        name="Sad / Melancholy",
        description="Somber, emotional delivery for grief or loss",
        style="Somber speaker, lowered energy, emotional weight, gentle sorrow.",
        voice_prompt="Sad, gentle sorrow, lowered energy, soft pauses, emotional weight.",
        category="tts",
    ),
    TonePreset(
        id="excited",
        name="Excited",
        description="Energetic, enthusiastic delivery for celebrations",
        style="Excited speaker, high energy, enthusiastic, animated expressions.",
        voice_prompt="Excited, enthusiastic, high energy, animated, exclamation marks for emphasis.",
        category="tts",
    ),
    TonePreset(
        id="sarcastic",
        name="Sarcastic",
        description="Dry humor with ironic delivery",
        style="Sarcastic speaker, dry tone, ironic inflection, playful edge.",
        voice_prompt="Sarcastic, dry humor, ironic tone, playful edge, timing is key.",
        category="tts",
    ),
    TonePreset(
        id="mysterious",
        name="Mysterious",
        description="Enigmatic delivery for mysteries and intrigue",
        style="Mysterious narrator, low register, slow pacing, hidden depth.",
        voice_prompt="Mysterious, low voice, slow pacing, enigmatic, draw out key words.",
        category="tts",
    ),
]

DEFAULT_PROMPT_PRESETS = [
    PromptPreset(
        id="default",
        name="Default",
        description="Standard voice direction without special effects",
        voice_prompt=None,
        category="tts",
        is_default=True,
    ),
    PromptPreset(
        id="warm_confident",
        name="Warm & Confident",
        description="Friendly, assured delivery with personal connection",
        voice_prompt="Warm, confident, steady pace, clear pauses after each sentence. Friendly tone.",
        category="tts",
    ),
    PromptPreset(
        id="soft_gentle",
        name="Soft & Gentle",
        description="Quiet, careful delivery for sensitive content",
        voice_prompt="Soft, gentle, careful, relaxed breathing between phrases. Lower volume.",
        category="tts",
    ),
    PromptPreset(
        id="energetic_upbeat",
        name="Energetic & Upbeat",
        description="Dynamic, lively delivery with high energy",
        voice_prompt="Energetic, upbeat, lively, animated tone variations. Higher energy throughout.",
        category="tts",
    ),
    PromptPreset(
        id="formal_professional",
        name="Formal & Professional",
        description="Business-appropriate delivery for corporate content",
        voice_prompt="Formal, professional, clear articulation, measured pace, business-appropriate tone.",
        category="tts",
    ),
    PromptPreset(
        id="casual_friendly",
        name="Casual & Friendly",
        description="Relaxed, conversational delivery for casual content",
        voice_prompt="Casual, friendly, conversational, natural rhythm, like talking to a friend.",
        category="tts",
    ),
    PromptPreset(
        id="with_laughs",
        name="With Laughter",
        description="Warm delivery with natural laughter breaks",
        voice_prompt="Warm delivery with occasional [laughs], natural giggling, joyful tone.",
        category="tts",
    ),
    PromptPreset(
        id="suspense_pause",
        name="Suspenseful with Pauses",
        description="Tense delivery with dramatic pauses for suspense",
        voice_prompt="Suspenseful, use [pause] after key phrases, build tension, lower volume for effect.",
        category="tts",
    ),
    PromptPreset(
        id="breathy_intimate",
        name="Breathy & Intimate",
        description="Close, personal delivery for romantic or secret content",
        voice_prompt="Breathy, intimate, very soft, close to the listener, personal tone.",
        category="tts",
    ),
    PromptPreset(
        id="character_voices",
        name="Character Voices",
        description="Multi-character dialogue with distinct voices",
        voice_prompt="Character voices, distinct accents, [interrupting] for dialogue, different tones per speaker.",
        category="tts",
    ),
    PromptPreset(
        id="with_sfx",
        name="With Sound Effects",
        description="Narration enhanced with environmental sounds",
        voice_prompt="Include sound effects naturally: [door creaks], [footsteps], [thunder], [applause] as described.",
        category="tts",
    ),
    PromptPreset(
        id="singing_melodic",
        name="Singing / Melodic",
        description="Partial singing or melodic delivery",
        voice_prompt="Singing quickly, melodic inflections, musical quality, blend speech and song.",
        category="tts",
    ),
]

DEFAULT_MUSIC_PRESETS = [
    PromptPreset(
        id="ambient_electronic",
        name="Ambient Electronic",
        description="Atmospheric electronic soundscapes for background",
        style="Ambient electronic, ethereal pads, soft synthesizer textures, slow evolution.",
        voice_prompt="Ambient electronic music, ethereal synthesizer pads, soft textures, slow evolving, no drums, peaceful atmosphere.",
        category="music",
    ),
    PromptPreset(
        id="upbeat_pop",
        name="Upbeat Pop",
        description="Catchy pop music with modern production",
        style="Upbeat pop, bright melodies, 4/4 beat, modern production.",
        voice_prompt="Upbeat pop song, bright synth melodies, steady 4/4 beat, modern production, catchy chorus, 120 BPM.",
        category="music",
    ),
    PromptPreset(
        id="cinematic_orchestral",
        name="Cinematic Orchestral",
        description="Full orchestral score for film and video",
        style="Cinematic orchestral, full strings, brass, percussion.",
        voice_prompt="Cinematic orchestral music, full strings section, brass fanfare, timpani drums, dramatic crescendo, film score quality.",
        category="music",
    ),
    PromptPreset(
        id="lofi_chill",
        name="Lo-Fi Chill",
        description="Relaxed lo-fi beats for study or focus",
        style="Lo-fi chill, warm vinyl texture, slow beat.",
        voice_prompt="Lo-fi chillhop, warm vinyl texture, soft drums, jazz samples, relaxed vibe, 80 BPM, perfect for studying.",
        category="music",
    ),
    PromptPreset(
        id="rock_energetic",
        name="Energetic Rock",
        description="High-energy rock with guitars and drums",
        style="Energetic rock, distorted guitars, driving drums.",
        voice_prompt="Energetic rock song, distorted electric guitars, powerful drums, anthemic chorus, driving rhythm, 140 BPM.",
        category="music",
    ),
    PromptPreset(
        id="jazz_smooth",
        name="Smooth Jazz",
        description="Relaxed jazz with saxophone melodies",
        style="Smooth jazz, saxophone, soft rhythm section.",
        voice_prompt="Smooth jazz, saxophone melody, soft piano chords, light brushed drums, relaxed evening vibe, 90 BPM.",
        category="music",
    ),
    PromptPreset(
        id="classical_piano",
        name="Classical Piano",
        description="Solo piano pieces in classical style",
        style="Classical piano, melodic, expressive.",
        voice_prompt="Classical piano solo, melodic and expressive, romantic era style, gentle dynamics, solo instrument.",
        category="music",
    ),
    PromptPreset(
        id="hiphop_beat",
        name="Hip-Hop Beat",
        description="Modern hip-hop production with bass",
        style="Hip-hop, heavy bass, crisp drums.",
        voice_prompt="Hip-hop instrumental, heavy bass, crisp snare drums, atmospheric samples, modern production, 90 BPM.",
        category="music",
    ),
    PromptPreset(
        id="nature_soundscape",
        name="Nature Soundscape",
        description="Organic sounds with nature recordings",
        style="Nature sounds, organic textures, environmental recordings.",
        voice_prompt="Nature soundscape, gentle rain, birds chirping, rustling leaves, peaceful forest ambience, no music.",
        category="music",
    ),
    PromptPreset(
        id="dubstep_electronic",
        name="Dubstep / Electronic",
        description="Heavy bass drops and electronic rhythms",
        style="Dubstep, wobble bass, electronic rhythms.",
        voice_prompt="Dubstep electronic track, wobble bass, heavy drop, electronic drums, aggressive energy, 140 BPM.",
        category="music",
    ),
]

DEFAULT_SFX_PRESETS = [
    PromptPreset(
        id="nature_ambience",
        name="Nature Ambience",
        description="Natural environmental sounds for background",
        style="Natural, organic, environmental.",
        voice_prompt="Nature ambience: gentle forest with birds, rustling leaves, distant wind, peaceful atmosphere.",
        category="sfx",
    ),
    PromptPreset(
        id="urban_ambience",
        name="Urban Ambience",
        description="City and urban environmental sounds",
        style="Urban, city, environmental.",
        voice_prompt="City ambience: distant traffic, people talking, occasional car horns, urban atmosphere.",
        category="sfx",
    ),
    PromptPreset(
        id="ui_sounds",
        name="UI / Interface Sounds",
        description="Click, whoosh, and interface sounds",
        style="Clean, modern, interface-appropriate.",
        voice_prompt="UI sound effects: clean click, soft whoosh, subtle chime for success notification.",
        category="sfx",
    ),
    PromptPreset(
        id="horror_sfx",
        name="Horror Sounds",
        description="Spooky and frightening sound effects",
        style="Dark, tense, unsettling.",
        voice_prompt="Horror ambience: creaking door, distant footsteps, wind howl, tense atmosphere, unsettling.",
        category="sfx",
    ),
    PromptPreset(
        id="sci_fi_sfx",
        name="Sci-Fi Sounds",
        description="Futuristic and sci-fi sound effects",
        style="Futuristic, technological, clean.",
        voice_prompt="Sci-fi ambience: subtle computer hum, data processing sounds, futuristic interface beeps.",
        category="sfx",
    ),
]


def load_presets() -> Dict[str, Dict[str, dict]]:
    if not PRESETS_PATH.exists():
        return {"tones": {}, "prompts": {}}
    try:
        data = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "tones" in data and "prompts" in data:
            return data
    except json.JSONDecodeError:
        pass
    return {"tones": {}, "prompts": {}}


def save_presets(presets: Dict[str, Dict[str, dict]]) -> None:
    PRESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRESETS_PATH.write_text(
        json.dumps(presets, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_preset_for_model(
    preset_id: str,
    preset_type: str,
    model_name: Optional[str] = None,
) -> Optional[dict]:
    presets = load_presets()
    collection = presets.get(preset_type, {})
    if preset_id in collection:
        preset = collection[preset_id]
        if model_name and "overrides" in preset and model_name in preset["overrides"]:
            return preset["overrides"][model_name]
        return preset
    return None


def merge_preset_with_overrides(
    preset: Optional[dict],
    model_name: Optional[str] = None,
) -> Optional[dict]:
    if not preset:
        return None
    result = preset.copy()
    if model_name and "overrides" in result and model_name in result["overrides"]:
        override = result["overrides"][model_name]
        if override:
            result.update(override)
    return result


MODEL_CAPABILITIES = {
    "parler-tts/parler-tts-mini-v1.1": {
        "style": True,
        "voice_prompt": True,
        "voice_ref": False,
        "category": "tts",
    },
    "suno/bark-small": {
        "style": True,
        "voice_prompt": True,
        "voice_ref": False,
        "category": "tts",
    },
    "microsoft/speecht5_tts": {
        "style": False,
        "voice_prompt": False,
        "voice_ref": True,
        "category": "tts",
    },
    "facebook/mms-tts-eng": {
        "style": False,
        "voice_prompt": False,
        "voice_ref": False,
        "category": "tts",
    },
    "nari-labs/Dia2-2B": {
        "style": False,
        "voice_prompt": False,
        "voice_ref": False,
        "category": "tts",
    },
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice": {
        "style": True,
        "voice_prompt": False,
        "voice_ref": False,
        "category": "tts",
    },
    "FunAudioLLM/Fun-CosyVoice3-0.5B-2512": {
        "style": False,
        "voice_prompt": False,
        "voice_ref": True,
        "category": "tts",
    },
    "coqui/XTTS-v2": {
        "style": False,
        "voice_prompt": False,
        "voice_ref": True,
        "category": "tts",
    },
    "SWivid/F5-TTS": {
        "style": False,
        "voice_prompt": False,
        "voice_ref": True,
        "category": "tts",
    },
    "shininglies/Dia2-2B": {
        "style": False,
        "voice_prompt": False,
        "voice_ref": False,
        "category": "tts",
    },
    "stable-audio/stable-audio": {
        "style": False,
        "voice_prompt": True,
        "voice_ref": False,
        "category": "music",
    },
    "stabilityai/stable-audio-2.5": {
        "style": False,
        "voice_prompt": True,
        "voice_ref": False,
        "category": "music",
    },
    "facebook/musicgen": {
        "style": False,
        "voice_prompt": True,
        "voice_ref": False,
        "category": "music",
    },
    "google/musiclm": {
        "style": False,
        "voice_prompt": True,
        "voice_ref": False,
        "category": "music",
    },
    "meta/musicgen": {
        "style": False,
        "voice_prompt": True,
        "voice_ref": False,
        "category": "music",
    },
    "elevenlabs/eleven-tts": {
        "style": True,
        "voice_prompt": True,
        "voice_ref": False,
        "category": "tts",
    },
    "elevenlabs/eleven-multilingual-v2": {
        "style": True,
        "voice_prompt": True,
        "voice_ref": False,
        "category": "tts",
    },
    "openai/audio-generation": {
        "style": True,
        "voice_prompt": True,
        "voice_ref": False,
        "category": "tts",
    },
    "kokoro": {
        "style": True,
        "voice_prompt": True,
        "voice_ref": False,
        "category": "tts",
    },
}


def get_model_capabilities(model_name: Optional[str] = None) -> Dict[str, Any]:
    if not model_name:
        return {
            "style": True,
            "voice_prompt": True,
            "voice_ref": False,
            "category": "tts",
        }
    for pattern, caps in MODEL_CAPABILITIES.items():
        if pattern.lower() in model_name.lower():
            return caps
    return {"style": True, "voice_prompt": True, "voice_ref": False, "category": "tts"}


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
    quality: Optional[str] = Field(
        None, description="Optional quality mode: fast | balanced | quality."
    )
    tone_id: Optional[str] = Field(
        None,
        description="Optional tone preset ID to apply.",
    )
    prompt_id: Optional[str] = Field(
        None,
        description="Optional voice direction preset ID to apply.",
    )
    voice_prompt: Optional[str] = Field(
        None,
        description="Optional voice direction / delivery prompt.",
    )
    auto_punctuate: bool = Field(
        False,
        description="Apply automatic punctuation/spacing cleanup for readability.",
    )
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


class SettingsTokenRequest(BaseModel):
    hf_token: Optional[str] = Field(
        None, description="Hugging Face access token (stored locally)."
    )


class PresetRequest(BaseModel):
    id: str = Field(..., description="Unique preset ID")
    name: str = Field(..., description="Preset display name")
    description: Optional[str] = Field(None, description="Preset description")
    style: Optional[str] = Field(None, description="Style prompt text")
    voice_prompt: Optional[str] = Field(None, description="Voice direction text")
    overrides: Optional[Dict[str, Dict[str, Optional[str]]]] = Field(
        None,
        description="Per-model overrides {model_name: {style/voice_prompt: value}}",
    )


class PresetDeleteRequest(BaseModel):
    id: str = Field(..., description="Preset ID to delete")


class PresetsResponse(BaseModel):
    tones: List[dict]
    prompts: List[dict]
    defaults: Dict[str, str]


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


def get_hf_token_status() -> Dict[str, str | bool]:
    env_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    saved_token = load_settings().get("hf_token")
    token = env_token or saved_token
    if env_token:
        source = "env"
    elif saved_token:
        source = "saved"
    else:
        source = "none"
    return {"hf_token_set": bool(token), "hf_token_source": source}


def merge_style_prompt(
    style: Optional[str], voice_prompt: Optional[str]
) -> Optional[str]:
    style_val = (style or "").strip()
    prompt_val = (voice_prompt or "").strip()
    if style_val and prompt_val:
        return f"{style_val}\n{prompt_val}"
    if style_val:
        return style_val
    if prompt_val:
        return prompt_val
    return None


QUESTION_START_RE = re.compile(
    r"^(?:[\"'“”‘’\(\[]+\s*)?("
    r"who|what|why|how|when|where|which|whom|"
    r"can|could|should|would|do|does|did|is|are|am|was|were|"
    r"will|won't|may|might|shall|"
    r"qui|quoi|que|quand|où|ou|comment|pourquoi|est\s*-?\s*ce|"
    r"peux|peut|pouvez|dois|devrais|voudrais|voulez|"
    r"sera|serait|sont|etes|êtes"
    r")\b",
    re.IGNORECASE,
)
EXCLAMATION_HINTS_RE = re.compile(
    r"\b(wow|amazing|incredible|fantastic|awesome|excellent|brilliant|great|let's\s+go|"
    r"bravo|yay|genial|génial|super|incroyable|excellent|formidable)\b",
    re.IGNORECASE,
)
ACRONYM_RE = re.compile(r"\b(?:AI|API|GPU|CPU|RAM|VRAM|TTS|SFX|UX|UI|LG)\b")


def _normalize_whitespace(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'")
    cleaned = re.sub(r"[\t ]+", " ", cleaned)
    cleaned = re.sub(r"\s+\n", "\n", cleaned)
    cleaned = re.sub(r"\n\s+", "\n", cleaned)
    return cleaned.strip()


def _spell_out_acronyms(text: str) -> str:
    def repl(match: re.Match) -> str:
        token = match.group(0)
        return " ".join(token)

    return ACRONYM_RE.sub(repl, text)


def _chunk_text(text: str, max_len: int = 140) -> List[str]:
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_len)
        if end < len(text):
            space = text.rfind(" ", start, end)
            if space != -1 and space > start + 40:
                end = space
        chunk = text[start:end].strip(" ,;:")
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


def _is_question(sentence: str) -> bool:
    if "?" in sentence:
        return True
    stripped = sentence.strip()
    return bool(QUESTION_START_RE.search(stripped))


def _infer_terminal_punct(sentence: str, tone_id: Optional[str]) -> str:
    if _is_question(sentence):
        return "?"
    if tone_id in {"excited", "cheerful"} and EXCLAMATION_HINTS_RE.search(sentence):
        return "!"
    return "."


def auto_punctuate_text(text: str, tone_id: Optional[str] = None) -> str:
    cleaned = _normalize_whitespace(text)
    if not cleaned:
        return cleaned

    cleaned = _spell_out_acronyms(cleaned)

    cleaned = re.sub(r"\.{4,}", "...", cleaned)
    cleaned = re.sub(r"([!?]){2,}", r"\1", cleaned)

    paragraphs = [p.strip() for p in re.split(r"\n+", cleaned) if p.strip()]
    sentences: List[str] = []
    for para in paragraphs:
        if re.search(r"[.!?]", para):
            parts = re.split(r"(?<=[.!?])\s+", para)
        else:
            parts = _chunk_text(para)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if not re.search(r"[.!?]$", part):
                part = part.rstrip(" ,;:")
                part = f"{part}{_infer_terminal_punct(part, tone_id)}"
            sentences.append(part)

    cleaned = " ".join(sentences)
    cleaned = re.sub(r"\s*([.!?])\s*", r"\1 ", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(
        r"(?<![,;:])\s+(and|but|so|because|however|therefore|yet)\s+",
        r", \1 ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def enhance_text(text: str, auto_punctuate: bool, tone_id: Optional[str] = None) -> str:
    if auto_punctuate:
        return auto_punctuate_text(text, tone_id)
    return text


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


@app.get("/settings")
def settings_status():
    return get_hf_token_status()


@app.post("/settings/token")
def settings_token(body: SettingsTokenRequest):
    token = (body.hf_token or "").strip()
    settings = load_settings()

    if token:
        settings["hf_token"] = token
        save_settings(settings)
        os.environ["HF_TOKEN"] = token
        os.environ["HUGGINGFACEHUB_API_TOKEN"] = token
        return {"status": "ok", "hf_token_set": True}

    if "hf_token" in settings:
        settings.pop("hf_token", None)
        save_settings(settings)
    os.environ.pop("HF_TOKEN", None)
    os.environ.pop("HUGGINGFACEHUB_API_TOKEN", None)
    return {"status": "ok", "hf_token_set": False}


class TelemetrySettingsRequest(BaseModel):
    crash_reports: Optional[bool] = None


@app.get("/settings/telemetry")
def get_telemetry_settings():
    settings = load_settings()
    return {
        "crash_reports": settings.get("crash_reports", False),
    }


@app.post("/settings/telemetry")
def set_telemetry_settings(body: TelemetrySettingsRequest):
    settings = load_settings()
    if body.crash_reports is not None:
        settings["crash_reports"] = body.crash_reports
    save_settings(settings)
    return {"status": "ok", "crash_reports": settings.get("crash_reports", False)}


@app.get("/presets")
def list_presets():
    presets = load_presets()
    tones = presets.get("tones", {})
    prompts = presets.get("prompts", {})

    def preset_to_dict(p):
        if hasattr(p, "model_dump"):
            p = p.model_dump()
        elif isinstance(p, dict):
            p = dict(p)
        else:
            p = {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "style": p.style,
                "voice_prompt": p.voice_prompt,
                "category": getattr(p, "category", "tts"),
                "is_default": p.is_default,
            }
        if "is_default" not in p:
            p["is_default"] = False
        if "category" not in p:
            p["category"] = "tts"
        return p

    default_tone_ids = [p.id for p in DEFAULT_TONE_PRESETS if p.is_default]
    default_prompt_ids = [p.id for p in DEFAULT_PROMPT_PRESETS if p.is_default]
    default_music_ids = [p.id for p in DEFAULT_MUSIC_PRESETS if p.is_default]
    default_sfx_ids = [p.id for p in DEFAULT_SFX_PRESETS if p.is_default]

    all_tones = [preset_to_dict(p) for p in DEFAULT_TONE_PRESETS] + [
        preset_to_dict(p) for p in tones.values()
    ]
    all_prompts = [preset_to_dict(p) for p in DEFAULT_PROMPT_PRESETS] + [
        preset_to_dict(p) for p in prompts.values()
    ]
    all_music = [preset_to_dict(p) for p in DEFAULT_MUSIC_PRESETS]
    all_sfx = [preset_to_dict(p) for p in DEFAULT_SFX_PRESETS]

    return {
        "tones": [
            {
                **p,
                "is_custom": p["id"] not in default_tone_ids,
            }
            for p in all_tones
            if p["id"] not in default_tone_ids or p.get("is_default")
        ],
        "prompts": [
            {
                **p,
                "is_custom": p["id"] not in default_prompt_ids,
            }
            for p in all_prompts
            if p["id"] not in default_prompt_ids or p.get("is_default")
        ],
        "music": [
            {
                **p,
                "is_custom": False,
            }
            for p in all_music
        ],
        "sfx": [
            {
                **p,
                "is_custom": False,
            }
            for p in all_sfx
        ],
        "defaults": {
            "tone": default_tone_ids[0] if default_tone_ids else "neutral",
            "prompt": default_prompt_ids[0] if default_prompt_ids else "default",
        },
        "categories": {
            "tts": "Voice / Speech",
            "music": "Music Generation",
            "sfx": "Sound Effects",
        },
    }


@app.post("/presets/tones")
def save_tone_preset(body: PresetRequest):
    presets = load_presets()
    if "tones" not in presets:
        presets["tones"] = {}
    presets["tones"][body.id] = {
        "id": body.id,
        "name": body.name,
        "description": body.description,
        "style": body.style,
        "voice_prompt": body.voice_prompt,
        "overrides": body.overrides or {},
    }
    save_presets(presets)
    return {"status": "ok", "id": body.id}


@app.delete("/presets/tones/{preset_id}")
def delete_tone_preset(preset_id: str):
    presets = load_presets()
    if "tones" not in presets:
        return {"status": "error", "message": "No custom presets found"}

    default_ids = [p.id for p in DEFAULT_TONE_PRESETS]
    if preset_id in default_ids:
        return {"status": "error", "message": "Cannot delete default presets"}

    if preset_id in presets["tones"]:
        del presets["tones"][preset_id]
        save_presets(presets)
        return {"status": "ok", "id": preset_id}
    return {"status": "error", "message": "Preset not found"}


@app.post("/presets/prompts")
def save_prompt_preset(body: PresetRequest):
    presets = load_presets()
    if "prompts" not in presets:
        presets["prompts"] = {}
    presets["prompts"][body.id] = {
        "id": body.id,
        "name": body.name,
        "description": body.description,
        "style": body.style,
        "voice_prompt": body.voice_prompt,
        "overrides": body.overrides or {},
    }
    save_presets(presets)
    return {"status": "ok", "id": body.id}


@app.delete("/presets/prompts/{preset_id}")
def delete_prompt_preset(preset_id: str):
    presets = load_presets()
    if "prompts" not in presets:
        return {"status": "error", "message": "No custom presets found"}

    default_ids = [p.id for p in DEFAULT_PROMPT_PRESETS]
    if preset_id in default_ids:
        return {"status": "error", "message": "Cannot delete default presets"}

    if preset_id in presets["prompts"]:
        del presets["prompts"][preset_id]
        save_presets(presets)
        return {"status": "ok", "id": preset_id}
    return {"status": "error", "message": "Preset not found"}


@app.get("/presets/model-capabilities")
def get_model_capabilities_endpoint(model_name: Optional[str] = None):
    return {"capabilities": get_model_capabilities(model_name)}


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


@app.get("/diagnostics")
def diagnostics():
    import shutil
    import platform

    def get_disk_info(path):
        try:
            total, used, free = shutil.disk_usage(str(path))
            return {
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "total_gb": round(total / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_python_info():
        return {
            "version": platform.python_version(),
            "executable": sys.executable,
        }

    def get_last_error():
        error_log = OUTPUT_DIR / "error.log"
        if error_log.exists():
            try:
                lines = error_log.read_text(encoding="utf-8").strip().split("\n")
                return lines[-20:] if len(lines) > 20 else lines
            except Exception:
                pass
        return []

    outputs_disk = get_disk_info(OUTPUT_DIR)
    models_disk = get_disk_info(MODELS_DIR)

    settings = load_settings()

    return {
        "backend": {
            "status": "healthy",
            "python": get_python_info(),
            "platform": platform.system(),
        },
        "storage": {
            "outputs_dir": str(OUTPUT_DIR),
            "models_dir": str(MODELS_DIR),
            "outputs_disk": outputs_disk,
            "models_disk": models_disk,
        },
        "settings": {
            "hf_token_set": bool(settings.get("hf_token")),
            "hf_token_source": settings.get("hf_token_source", "none"),
            "provider": tts_service.current_provider(),
        },
        "models": {
            "available": [s.id for s in model_manager.status() if s.exists],
            "downloading": model_manager.downloading,
        },
        "last_errors": get_last_error(),
    }


@app.get("/diagnostics")
def diagnostics():
    import shutil
    import platform

    def get_disk_info(path):
        try:
            total, used, free = shutil.disk_usage(str(path))
            return {
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "total_gb": round(total / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_python_info():
        return {
            "version": platform.python_version(),
            "executable": sys.executable,
        }

    def get_last_error():
        error_log = OUTPUT_DIR / "error.log"
        if error_log.exists():
            try:
                lines = error_log.read_text(encoding="utf-8").strip().split("\n")
                return lines[-20:] if len(lines) > 20 else lines
            except Exception:
                pass
        return []

    outputs_disk = get_disk_info(OUTPUT_DIR)
    models_disk = get_disk_info(MODELS_DIR)

    settings = load_settings()

    return {
        "backend": {
            "status": "healthy",
            "python": get_python_info(),
            "platform": platform.system(),
        },
        "storage": {
            "outputs_dir": str(OUTPUT_DIR),
            "models_dir": str(MODELS_DIR),
            "outputs_disk": outputs_disk,
            "models_disk": models_disk,
        },
        "settings": {
            "hf_token_set": bool(settings.get("hf_token")),
            "hf_token_source": settings.get("hf_token_source", "none"),
            "provider": tts_service.current_provider(),
        },
        "models": {
            "available": [s.id for s in model_manager.status() if s.exists],
            "downloading": model_manager.downloading,
        },
        "last_errors": get_last_error(),
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
    quality: Optional[str],
    tone_id: Optional[str],
    prompt_id: Optional[str],
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
            quality=quality,
            tone_id=tone_id,
            prompt_id=prompt_id,
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

    text = enhance_text(text, request.auto_punctuate, request.tone_id)
    style = merge_style_prompt(request.style, request.voice_prompt)

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
            request.quality,
            request.tone_id,
            request.prompt_id,
            style,
            request.voice_ref,
        )
        job = job_store.get(job_id)
        assert job is not None
        return JobStatusResponse(**job.__dict__)

    job = _run_job(
        job_id,
        text,
        request.voice_id,
        request.speed,
        request.quality,
        request.tone_id,
        request.prompt_id,
        style,
        request.voice_ref,
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


class CleanupRequest(BaseModel):
    delete_audio: bool = True
    delete_history: bool = False
    delete_models: Optional[List[str]] = None


@app.post("/maintenance/cleanup")
def cleanup_endpoint(body: CleanupRequest):
    import shutil

    deleted = {"audio_files": 0, "history_items": 0, "models": []}

    if body.delete_audio and AUDIO_DIR.exists():
        try:
            for f in AUDIO_DIR.glob("*.wav"):
                f.unlink()
                deleted["audio_files"] += 1
        except Exception as e:
            pass

    if body.delete_history and HISTORY_PATH.exists():
        try:
            HISTORY_PATH.unlink()
            deleted["history_items"] = 1
        except Exception as e:
            pass

    if body.delete_models:
        for model_key in body.delete_models:
            from backend.models import MODEL_ALIASES

            repo_id = MODEL_ALIASES.get(model_key, model_key)
            model_dir = MODELS_DIR / repo_id.replace("/", "_")
            if model_dir.exists():
                try:
                    shutil.rmtree(model_dir)
                    deleted["models"].append(model_key)
                except Exception:
                    pass

    return {"status": "ok", "deleted": deleted}


class ReportRequest(BaseModel):
    type: str = Field(..., description="bug, feedback, feature, voice_issue")
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    email: Optional[str] = Field(None, max_length=255)
    device_info: Optional[str] = Field(None, max_length=500)
    logs: Optional[str] = Field(None, max_length=10000)
    attachment_ids: Optional[List[str]] = Field(default_factory=list)


REPORTS_PATH = OUTPUT_DIR / "reports.json"


def load_reports() -> List[Dict]:
    if REPORTS_PATH.exists():
        try:
            with open(REPORTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_reports(reports: List[Dict]) -> None:
    REPORTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_PATH, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2, ensure_ascii=False)


@app.post("/reports/submit")
def submit_report(body: ReportRequest):
    report = {
        "id": str(uuid.uuid4()),
        "type": body.type,
        "title": body.title,
        "description": body.description,
        "email": body.email,
        "device_info": body.device_info,
        "logs": body.logs,
        "attachment_ids": body.attachment_ids,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "new",
    }

    reports = load_reports()
    reports.insert(0, report)
    reports = reports[:1000]
    save_reports(reports)

    return {"status": "ok", "report_id": report["id"]}


@app.get("/reports")
def list_reports(status: Optional[str] = None, limit: int = 50):
    reports = load_reports()
    if status:
        reports = [r for r in reports if r.get("status") == status]
    return {"items": reports[:limit]}


@app.post("/reports/{report_id}/status")
def update_report_status(report_id: str, status: str = "reviewed"):
    reports = load_reports()
    for report in reports:
        if report["id"] == report_id:
            report["status"] = status
            report["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_reports(reports)
            return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Report not found")


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


class ExportManifestRequest(BaseModel):
    job_ids: List[str]
    format: str = "csv"


@app.post("/export/manifest")
def export_manifest(body: ExportManifestRequest):
    items = load_history()
    filtered = [item for item in items if item.get("job_id") in body.job_ids]
    if not filtered:
        raise HTTPException(status_code=404, detail="No entries found for given jobs")

    if body.format == "csv":
        import csv

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "job_id",
                "text_preview",
                "model",
                "voice_id",
                "created_at",
                "duration_seconds",
                "audio_path",
            ],
        )
        writer.writeheader()
        for item in filtered:
            writer.writerow(
                {
                    "job_id": item.get("job_id", ""),
                    "text_preview": item.get("text_preview", "")[:160],
                    "model": item.get("model", ""),
                    "voice_id": item.get("voice_id", ""),
                    "created_at": item.get("created_at", ""),
                    "duration_seconds": item.get("duration_seconds", ""),
                    "audio_path": item.get("audio_path", ""),
                }
            )
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="oratioviva-manifest.csv"'
            },
        )
    else:
        return Response(
            content=json.dumps(filtered, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="oratioviva-manifest.json"'
            },
        )


class ExportMp3Request(BaseModel):
    job_ids: List[str]


def convert_wav_to_mp3(wav_path: Path, mp3_path: Path) -> bool:
    """Convert a WAV file to MP3 using ffmpeg."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(wav_path),
                "-b:a",
                "192k",
                "-f",
                "mp3",
                str(mp3_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return mp3_path.exists()
    except Exception:
        return False


@app.post("/export/mp3")
def export_mp3(body: ExportMp3Request):
    """Export audio files as MP3."""
    files = collect_audio_files(body.job_ids)
    if not files:
        raise HTTPException(
            status_code=404, detail="No audio files found for given jobs"
        )

    if len(files) == 1:
        wav_path = Path(files[0])
        mp3_path = wav_path.with_suffix(".mp3")
        if convert_wav_to_mp3(wav_path, mp3_path):
            buffer = io.BytesIO(mp3_path.read_bytes())
            mp3_path.unlink()
            return StreamingResponse(
                buffer,
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": f'attachment; filename="{mp3_path.name}"'
                },
            )
        raise HTTPException(status_code=500, detail="MP3 conversion failed")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for wav_path in files:
            wav_file = Path(wav_path)
            mp3_file = wav_file.with_suffix(".mp3")
            if convert_wav_to_mp3(wav_file, mp3_file):
                zip_file.write(mp3_file, arcname=mp3_file.name)
                mp3_file.unlink()
            else:
                zip_file.write(wav_file, arcname=wav_file.name)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="oratioviva-audio-mp3.zip"'
        },
    )


class ChainRequest(BaseModel):
    items: List[SynthesisRequest]
    parallel: bool = False


@app.post("/synthesize/chain", response_model=Dict)
def synthesize_chain(
    request: ChainRequest,
    background_tasks: BackgroundTasks,
):
    chain_id = str(uuid.uuid4())
    job_ids = []

    for i, item in enumerate(request.items):
        text = item.text.strip()
        if not text:
            continue
        text = enhance_text(text, item.auto_punctuate, item.tone_id)
        style = merge_style_prompt(item.style, item.voice_prompt)

        job_id = str(uuid.uuid4())
        job_ids.append(job_id)
        job_store.create(job_id, status="queued", chain_id=chain_id, chain_index=i)

    background_tasks.add_task(
        _run_chain,
        chain_id,
        job_ids,
        [item.model_dump() for item in request.items],
        request.parallel,
    )

    return {"chain_id": chain_id, "job_ids": job_ids, "status": "queued"}


def _run_chain(chain_id: str, job_ids: List[str], items: List[Dict], parallel: bool):
    from backend.tts import validate_voice_ref

    results = []
    for i, job_id in enumerate(job_ids):
        item = items[i]
        text = item.get("text", "").strip()
        voice_id = item.get("voice_id")
        speed = item.get("speed", 1.0)
        quality = item.get("quality")
        tone_id = item.get("tone_id")
        prompt_id = item.get("prompt_id")
        style = item.get("style") or ""
        voice_prompt = item.get("voice_prompt") or ""
        style = merge_style_prompt(style, voice_prompt)
        voice_ref = item.get("voice_ref")

        job_store.update(job_id, status="running")

        try:
            if voice_ref and voice_ref.strip():
                try:
                    voice_ref = validate_voice_ref(voice_ref)
                except ValueError:
                    job_store.update(
                        job_id, status="failed", error="Invalid voice reference"
                    )
                    continue

            start_time = time.perf_counter()
            result = tts_service.synthesize(
                text=text,
                voice_id=voice_id,
                speed=speed,
                quality=quality,
                tone_id=tone_id,
                prompt_id=prompt_id,
                style=style,
                voice_ref=voice_ref,
                job_id=job_id,
            )
            generation_seconds = time.perf_counter() - start_time
            _record_history(result, text, generation_seconds=generation_seconds)
            job_store.update(
                job_id,
                status="succeeded",
                audio_url=result.audio_url,
                duration_seconds=result.duration_seconds,
                generation_seconds=generation_seconds,
                model=result.model,
                voice_id=result.voice_id,
                source=result.source,
            )
            results.append({"job_id": job_id, "status": "succeeded"})
        except Exception as exc:
            job_store.update(job_id, status="failed", error=str(exc))
            results.append({"job_id": job_id, "status": "failed", "error": str(exc)})

    return {"chain_id": chain_id, "results": results}


@app.get("/chains/{chain_id}/status")
def chain_status(chain_id: str):
    jobs = job_store.list(limit=1000)
    chain_jobs = [j for j in jobs if getattr(j, "chain_id", None) == chain_id]
    if not chain_jobs:
        raise HTTPException(status_code=404, detail="Chain not found")

    total = len(chain_jobs)
    succeeded = sum(1 for j in chain_jobs if j.status == "succeeded")
    failed = sum(1 for j in chain_jobs if j.status == "failed")
    running = sum(
        1 for j in chain_jobs if j.status in ("running", "processing", "queued")
    )

    return {
        "chain_id": chain_id,
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "running": running,
        "completed": succeeded + failed == total,
        "jobs": [{"job_id": j.job_id, "status": j.status} for j in chain_jobs],
    }


class LongAudioRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_LONG_TEXT_LENGTH)
    voice_id: str = Field("parler_en_neutral")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    quality: Optional[str] = Field(None)
    tone_id: Optional[str] = Field(None)
    prompt_id: Optional[str] = Field(None)
    voice_prompt: Optional[str] = Field(None)
    auto_punctuate: bool = Field(False)
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

    text = enhance_text(text, request.auto_punctuate, request.tone_id)
    style = merge_style_prompt(request.style, request.voice_prompt)

    job_id = str(uuid.uuid4())
    job_store.create(job_id, status="queued")

    background_tasks.add_task(
        _run_long_job,
        job_id,
        text,
        request.voice_id,
        request.speed,
        request.quality,
        request.tone_id,
        request.prompt_id,
        style,
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
    quality: Optional[str],
    tone_id: Optional[str],
    prompt_id: Optional[str],
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
    start_time = None
    try:
        start_time = time.perf_counter()
        chunks = _split_text_into_chunks(text, chunk_size)
        total_chunks = len(chunks)

        if total_chunks == 1:
            return _run_job(job_id, text, voice_id, speed, quality, style, voice_ref)

        from backend.tts import VOICE_BY_ID

        voice = VOICE_BY_ID.get(voice_id)
        model_id = (voice.model or "").lower() if voice else ""
        is_qwen = "qwen3-tts" in model_id
        is_dia2 = "dia2" in model_id

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

        valid_results = None

        if is_qwen:
            try:
                results = tts_service.synthesize_qwen3_customvoice_batch(
                    chunks=chunks,
                    voice_id=voice_id,
                    job_ids=chunk_job_ids,
                    speed=speed,
                    style=style,
                    quality=quality,
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
                job_store.update(
                    job_id,
                    status="running",
                    source=(
                        "Qwen batch failed, falling back to sequential: "
                        f"{str(exc)[:160]}"
                    ),
                )
                valid_results = None
        elif is_dia2:
            try:
                job_store.update(
                    job_id,
                    status="running",
                    source=f"Processing {total_chunks} chunks (dia2 batch)",
                )
                results = tts_service.synthesize_dia2_batch(
                    chunks=chunks,
                    voice_id=voice_id,
                    job_ids=chunk_job_ids,
                    speed=speed,
                    quality=quality,
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
                # Fall back to sequential chunks if batch fails.
                job_store.update(
                    job_id,
                    status="running",
                    source=(
                        "Dia2 batch failed, falling back to sequential: "
                        f"{str(exc)[:160]}"
                    ),
                )
                valid_results = None

        if valid_results is None and parallel:
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
                        quality=quality,
                        tone_id=tone_id,
                        prompt_id=prompt_id,
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
        elif valid_results is None:
            valid_results = []
            for i, chunk in enumerate(chunks):
                cid = chunk_job_ids[i]
                job_store.update(cid, status="running")
                try:
                    result = tts_service.synthesize(
                        text=chunk,
                        voice_id=voice_id,
                        speed=speed,
                        quality=quality,
                        tone_id=tone_id,
                        prompt_id=prompt_id,
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
        generation_seconds = (time.perf_counter() - start_time) if start_time else None
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
