from __future__ import annotations

import io
import json
import math
import struct
import uuid
import wave
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from backend.models import ModelManager
except Exception:
    ModelManager = None


@dataclass(frozen=True)
class VoicePreset:
    id: str
    model: str
    label: str
    language: str
    voice: Optional[str] = None
    description: Optional[str] = None


OPTIONAL_MODELS = {
    m.strip().lower()
    for m in os.getenv("ORATIO_OPTIONAL_MODELS", "kokoro").split(",")
    if m.strip()
}
SKIP_KOKORO = "kokoro" in OPTIONAL_MODELS
VOICE_REF_MODELS = ("xtts", "f5-tts", "cosyvoice")

ALL_VOICE_PRESETS = [
    VoicePreset(
        id="parler_en_neutral",
        model="parler-tts/parler-tts-mini-v1.1",
        language="en",
        label="Parler Neutral",
        description="Parler-TTS avec prompt de style",
    ),
    VoicePreset(
        id="bark_en_0",
        model="suno/bark-small",
        language="en",
        label="Bark Small EN",
        description="Modele Bark leger (<8GB VRAM), neutre",
    ),
    VoicePreset(
        id="speecht5_en_0",
        model="microsoft/speecht5_tts",
        language="en",
        label="SpeechT5 EN",
        description="SpeechT5 + HiFiGAN vocoder, speaker embed par defaut",
    ),
    VoicePreset(
        id="mms_en_0",
        model="facebook/mms-tts-eng",
        language="en",
        label="MMS EN Warm",
        description="Meta MMS TTS (CPU/<=8GB VRAM), voix naturelle style lecture.",
    ),
    VoicePreset(
        id="dia2_2b_en",
        model="nari-labs/Dia2-2B",
        language="en",
        label="Dia2 2B EN",
        description="Streaming dialogue TTS, 2min context, conversational",
    ),
    VoicePreset(
        id="qwen3_custom_ryan_en",
        model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        language="en",
        label="Qwen3 CustomVoice (Ryan)",
        voice="Ryan",
        description="Qwen3-TTS CustomVoice (English male). Style via 'Style' field.",
    ),
    VoicePreset(
        id="qwen3_custom_ryan_es",
        model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        language="es",
        label="Qwen3 CustomVoice (Ryan ES)",
        voice="Ryan",
        description="Qwen3-TTS CustomVoice (Spanish). Style via 'Style' field.",
    ),
    VoicePreset(
        id="qwen3_custom_ryan_fr",
        model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        language="fr",
        label="Qwen3 CustomVoice (Ryan FR)",
        voice="Ryan",
        description="Qwen3-TTS CustomVoice (French). Style via 'Style' field.",
    ),
    VoicePreset(
        id="qwen3_custom_ryan_de",
        model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        language="de",
        label="Qwen3 CustomVoice (Ryan DE)",
        voice="Ryan",
        description="Qwen3-TTS CustomVoice (German). Style via 'Style' field.",
    ),
    VoicePreset(
        id="qwen3_custom_ryan_it",
        model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        language="it",
        label="Qwen3 CustomVoice (Ryan IT)",
        voice="Ryan",
        description="Qwen3-TTS CustomVoice (Italian). Style via 'Style' field.",
    ),
    VoicePreset(
        id="qwen3_custom_ryan_pt",
        model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        language="pt",
        label="Qwen3 CustomVoice (Ryan PT)",
        voice="Ryan",
        description="Qwen3-TTS CustomVoice (Portuguese). Style via 'Style' field.",
    ),
    VoicePreset(
        id="qwen3_custom_ryan_ru",
        model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        language="ru",
        label="Qwen3 CustomVoice (Ryan RU)",
        voice="Ryan",
        description="Qwen3-TTS CustomVoice (Russian). Style via 'Style' field.",
    ),
    VoicePreset(
        id="qwen3_custom_ryan_ja",
        model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        language="ja",
        label="Qwen3 CustomVoice (Ryan JA)",
        voice="Ryan",
        description="Qwen3-TTS CustomVoice (Japanese). Style via 'Style' field.",
    ),
    VoicePreset(
        id="qwen3_custom_ryan_ko",
        model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        language="ko",
        label="Qwen3 CustomVoice (Ryan KO)",
        voice="Ryan",
        description="Qwen3-TTS CustomVoice (Korean). Style via 'Style' field.",
    ),
    VoicePreset(
        id="qwen3_custom_aiden_en",
        model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        language="en",
        label="Qwen3 CustomVoice (Aiden)",
        voice="Aiden",
        description="Qwen3-TTS CustomVoice (English male). Style via 'Style' field.",
    ),
    VoicePreset(
        id="qwen3_custom_vivian_zh",
        model="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        language="zh",
        label="Qwen3 CustomVoice (Vivian)",
        voice="Vivian",
        description="Qwen3-TTS CustomVoice (Chinese female). Style via 'Style' field.",
    ),
    VoicePreset(
        id="chroma_4b_en",
        model="FlashLabs/Chroma-4B",
        language="en",
        label="Chroma-4B",
        description="FlashLabs Chroma-4B (gated). Optional voice_ref + style prompt.",
    ),
]

VOICE_PRESETS = [
    voice
    for voice in ALL_VOICE_PRESETS
    if not (SKIP_KOKORO and "kokoro" in voice.model.lower())
]
VOICE_BY_ID: Dict[str, VoicePreset] = {voice.id: voice for voice in VOICE_PRESETS}


@dataclass
class AudioResult:
    job_id: str
    audio_path: Path
    audio_url: str
    duration_seconds: float
    created_at: datetime
    model: str
    voice_id: str
    source: str


AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".webm"}


def _is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTENSIONS


class TTSService:
    def __init__(
        self,
        audio_dir: Path,
        base_audio_url: str = "/audio",
        use_stub: bool = False,
        fallback_stub: bool = False,
        provider: str = "local",
        models_dir: Optional[Path] = None,
        model_manager: Optional["ModelManager"] = None,
    ) -> None:
        self.audio_dir = audio_dir
        self.base_audio_url = base_audio_url.rstrip("/")
        self.use_stub = use_stub
        self.fallback_stub = fallback_stub
        self.provider = provider
        self.models_dir = models_dir
        self.model_manager = model_manager
        self._local_pipelines: Dict[str, object] = {}
        self._parler_models: Dict[str, Tuple[Any, Any]] = {}
        self._speaker_encoder: Optional[object] = None
        self._speaker_embeddings: Dict[str, Any] = {}
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def list_voices(self):
        return [voice.__dict__ for voice in VOICE_PRESETS]

    def current_provider(self) -> str:
        if self.use_stub:
            return "stub"
        return self.provider

    def provider_message(self, statuses=None) -> str:
        if self.use_stub:
            return "Running in stub mode (ORATIO_TTS_STUB=1)"
        return ""

    def local_support(self, repo_id: str) -> Tuple[bool, Optional[str]]:
        return self._local_support(repo_id)

    def _supports_voice_ref(self, model_id: str) -> bool:
        lower_id = model_id.lower()
        return any(token in lower_id for token in VOICE_REF_MODELS)

    def _resolve_voice_ref(self, voice_ref: Optional[str]) -> Optional[object]:
        if not voice_ref:
            return None
        trimmed = voice_ref.strip()
        if not trimmed:
            return None
        if trimmed.lower().startswith(("http://", "https://")):
            return trimmed
        candidate = Path(trimmed).expanduser()
        if candidate.exists() and candidate.is_file():
            return candidate.read_bytes()
        return trimmed

    def _resolve_local_voice_ref_path(
        self, voice_ref: Optional[str], *, required: bool = False
    ) -> Optional[Path]:
        if not voice_ref or not voice_ref.strip():
            if required:
                raise RuntimeError("Ce modele local requiert un fichier voice_ref.")
            return None
        trimmed = voice_ref.strip()
        if trimmed.lower().startswith(("http://", "https://")):
            raise RuntimeError(
                "voice_ref local doit etre un chemin vers un fichier audio."
            )
        path = Path(trimmed).expanduser()
        if not path.exists() or not path.is_file():
            raise RuntimeError(f"voice_ref introuvable: {voice_ref}")
        if not _is_audio_file(path):
            raise RuntimeError(
                f"voice_ref doit etre un fichier audio (.wav, .mp3, .ogg, etc.), pas un fichier {path.suffix}"
            )
        return path

    def _get_local_pipeline(
        self, model_key: str, task: str = "text-to-speech"
    ) -> object:
        try:
            from transformers import pipeline
        except Exception as exc:
            raise RuntimeError(
                "Local pipeline requires transformers installed"
            ) from exc

        if model_key not in self._local_pipelines:
            self._local_pipelines[model_key] = pipeline(
                task=task,
                model=model_key,
                device="cpu",
                trust_remote_code=True,
            )
        return self._local_pipelines[model_key]

    def _run_tts_pipeline(
        self,
        tts: object,
        text: str,
        *,
        speed: float,
        voice_ref_path: Optional[Path] = None,
        prompt_text: Optional[str] = None,
    ):
        forward_params = {"speed": speed} if speed != 1.0 else {}
        voice_candidates = []
        if voice_ref_path is not None:
            voice_path = str(voice_ref_path)
            voice_candidates = [
                {"speaker_wav": voice_path},
                {"prompt_wav": voice_path},
                {"ref_audio": voice_path},
                {"reference_audio": voice_path},
                {"voice": voice_path},
                {"audio_prompt": voice_path},
            ]
        prompt_candidates = []
        if prompt_text:
            prompt_candidates = [
                {"prompt_text": prompt_text},
                {"ref_text": prompt_text},
                {"reference_text": prompt_text},
                {"style": prompt_text},
            ]
        if not voice_candidates and not prompt_candidates:
            voice_candidates = [{}]
            prompt_candidates = [{}]
        elif not voice_candidates:
            voice_candidates = [{}]
        elif not prompt_candidates:
            prompt_candidates = [{}]

        last_error = None
        for voice_kwargs in voice_candidates:
            for prompt_kwargs in prompt_candidates:
                kwargs = {**voice_kwargs, **prompt_kwargs}
                try:
                    if forward_params:
                        return tts(text, forward_params=forward_params, **kwargs)
                    return tts(text, **kwargs)
                except TypeError as exc:
                    last_error = exc
                    continue

        if voice_ref_path is not None or prompt_text:
            if forward_params:
                for voice_kwargs in voice_candidates:
                    for prompt_kwargs in prompt_candidates:
                        merged = {**voice_kwargs, **prompt_kwargs}
                        try:
                            return tts(
                                text, forward_params={**forward_params, **merged}
                            )
                        except TypeError as exc:
                            last_error = exc
                            continue

        if forward_params:
            try:
                return tts(text, forward_params=forward_params)
            except TypeError as exc:
                last_error = exc

        if voice_ref_path is not None or prompt_text:
            raise RuntimeError(
                "Le modele local n'accepte pas voice_ref/prompt; verifiez les dependances."
            ) from last_error
        if last_error is not None:
            raise last_error
        return tts(text)

    def _compose_presets(
        self,
        tone_id: Optional[str],
        prompt_id: Optional[str],
        style: Optional[str],
        voice_prompt: Optional[str],
        model_name: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        final_style = style
        final_voice_prompt = voice_prompt

        try:
            from backend.main import (
                load_presets,
                DEFAULT_TONE_PRESETS,
                DEFAULT_PROMPT_PRESETS,
            )

            presets = load_presets()
            tones = presets.get("tones", {})
            prompts = presets.get("prompts", {})

            tone_preset = None
            if tone_id:
                default_tone_ids = {p.id for p in DEFAULT_TONE_PRESETS}
                if tone_id in default_tone_ids:
                    for p in DEFAULT_TONE_PRESETS:
                        if p.id == tone_id:
                            tone_preset = p.model_dump()
                            break
                elif tone_id in tones:
                    tone_preset = tones[tone_id]

            prompt_preset = None
            if prompt_id:
                default_prompt_ids = {p.id for p in DEFAULT_PROMPT_PRESETS}
                if prompt_id in default_prompt_ids:
                    for p in DEFAULT_PROMPT_PRESETS:
                        if p.id == prompt_id:
                            prompt_preset = p.model_dump()
                            break
                elif prompt_id in prompts:
                    prompt_preset = prompts[prompt_id]

            if tone_preset and model_name:
                overrides = tone_preset.get("overrides", {})
                if model_name in overrides:
                    override = overrides[model_name]
                    if override:
                        if override.get("style"):
                            final_style = override["style"]
                        if override.get("voice_prompt"):
                            final_voice_prompt = override["voice_prompt"]
                else:
                    if tone_preset.get("style") and not final_style:
                        final_style = tone_preset["style"]
                    if tone_preset.get("voice_prompt") and not final_voice_prompt:
                        final_voice_prompt = tone_preset["voice_prompt"]
            else:
                if tone_preset:
                    if tone_preset.get("style") and not final_style:
                        final_style = tone_preset["style"]
                    if tone_preset.get("voice_prompt") and not final_voice_prompt:
                        final_voice_prompt = tone_preset["voice_prompt"]

            if prompt_preset and model_name:
                overrides = prompt_preset.get("overrides", {})
                if model_name in overrides:
                    override = overrides[model_name]
                    if override:
                        if override.get("style"):
                            final_style = override["style"]
                        if override.get("voice_prompt"):
                            final_voice_prompt = override["voice_prompt"]
                else:
                    if prompt_preset.get("style") and not final_style:
                        final_style = prompt_preset["style"]
                    if prompt_preset.get("voice_prompt") and not final_voice_prompt:
                        final_voice_prompt = prompt_preset["voice_prompt"]
            else:
                if prompt_preset:
                    if prompt_preset.get("style") and not final_style:
                        final_style = prompt_preset["style"]
                    if prompt_preset.get("voice_prompt") and not final_voice_prompt:
                        final_voice_prompt = prompt_preset["voice_prompt"]

        except Exception:
            pass

        return final_style, final_voice_prompt

    def synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        quality: Optional[str] = None,
        tone_id: Optional[str] = None,
        prompt_id: Optional[str] = None,
        style: Optional[str] = None,
        voice_prompt: Optional[str] = None,
        voice_ref: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> AudioResult:
        if voice_id not in VOICE_BY_ID:
            raise ValueError(f"Unknown voice_id: {voice_id}")

        if voice_ref:
            voice_ref = validate_voice_ref(voice_ref)

        voice = VOICE_BY_ID[voice_id]
        style, voice_prompt = self._compose_presets(
            tone_id, prompt_id, style, voice_prompt, voice.model
        )

        job_id = job_id or str(uuid.uuid4())
        destination = self.audio_dir / f"{job_id}.wav"
        voice = VOICE_BY_ID[voice_id]
        created_at = datetime.now(timezone.utc)

        use_stub = self.use_stub

        if use_stub:
            duration = self._generate_stub_audio(text, destination, speed=speed)
            return AudioResult(
                job_id=job_id,
                audio_path=destination,
                audio_url=f"{self.base_audio_url}/{destination.name}",
                duration_seconds=duration,
                created_at=created_at,
                model=voice.model,
                voice_id=voice_id,
                source="stub",
            )

        supported, reason = self._local_support(voice.model)
        if not supported:
            if self.fallback_stub:
                duration = self._generate_stub_audio(text, destination, speed=speed)
                return AudioResult(
                    job_id=job_id,
                    audio_path=destination,
                    audio_url=f"{self.base_audio_url}/{destination.name}",
                    duration_seconds=duration,
                    created_at=created_at,
                    model=voice.model,
                    voice_id=voice_id,
                    source="stub",
                )
            raise RuntimeError(reason or "Modele local indisponible.")

        if not self._has_local_models(voice.model):
            if self.fallback_stub:
                duration = self._generate_stub_audio(text, destination, speed=speed)
                return AudioResult(
                    job_id=job_id,
                    audio_path=destination,
                    audio_url=f"{self.base_audio_url}/{destination.name}",
                    duration_seconds=duration,
                    created_at=created_at,
                    model=voice.model,
                    voice_id=voice_id,
                    source="stub",
                )
            raise RuntimeError(
                "Modele local manquant. Telechargez-le via l'onglet Modeles."
            )

        voice_ref_payload = None
        if self._supports_voice_ref(voice.model):
            if not voice_ref or not voice_ref.strip():
                raise ValueError(
                    "Ce modele requiert une reference de voix (voice_ref)."
                )

        try:
            return self._synthesize_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                quality=quality,
                style=style,
                voice_ref=voice_ref,
                created_at=created_at,
            )
        except Exception:
            if self.fallback_stub:
                duration = self._generate_stub_audio(text, destination, speed=speed)
                return AudioResult(
                    job_id=job_id,
                    audio_path=destination,
                    audio_url=f"{self.base_audio_url}/{destination.name}",
                    duration_seconds=duration,
                    created_at=created_at,
                    model=voice.model,
                    voice_id=voice_id,
                    source="stub",
                )
            raise

    def _resolve_model_path(self, model_name: str) -> str:
        model_path = model_name
        if self.model_manager is not None:
            resolved = self.model_manager.resolve_model_path(model_name)
            if resolved is not None:
                return str(resolved)
        if self.models_dir:
            candidate = self.models_dir / model_name.replace("/", "_")
            if candidate.exists():
                model_path = str(candidate)
        return model_path

    def _heavy_python(self) -> Path:
        """Return python executable for heavy models (torch/transformers).

        We reuse the Dia2 venv because it already carries torch+transformers.
        """
        import os

        override = os.getenv("ORATIO_DIA2_PYTHON")
        if override:
            return Path(override)
        backend_dir = Path(__file__).resolve().parent
        return backend_dir.parent / ".venv_dia2" / "Scripts" / "python.exe"

    def _resolve_dia2_python(self) -> Path:
        """Resolve Dia2 python executable and ensure core deps are available."""
        import os
        import subprocess
        import time

        override = os.getenv("ORATIO_DIA2_PYTHON")
        if override:
            dia2_venv_python = Path(override)
        else:
            backend_dir = Path(__file__).resolve().parent
            dia2_venv_python = (
                backend_dir.parent / ".venv_dia2" / "Scripts" / "python.exe"
            )

        if not dia2_venv_python.exists():
            raise RuntimeError(
                "Dia2 python not found. Ensure Dia2 venv is installed (desktop should create it automatically)."
            )

        ready = False
        last_details = ""
        for _ in range(36):  # ~3 minutes
            check = subprocess.run(
                [
                    str(dia2_venv_python),
                    "-c",
                    "import torch, transformers, safetensors, sphn; print('ok')",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if check.returncode == 0:
                ready = True
                break

            last_details = (check.stderr or check.stdout or "").strip()
            lower = last_details.lower()
            missing_pkg = "no module named" in lower and any(
                name in lower
                for name in ["torch", "transformers", "safetensors", "sphn"]
            )
            if missing_pkg:
                time.sleep(5)
                continue
            break

        if not ready:
            raise RuntimeError(
                "Dia2 environment is not ready (torch/transformers missing) or setup failed. "
                "Wait for first-run setup to finish and restart the app. "
                f"Details: {last_details}"
            )

        return dia2_venv_python

    @staticmethod
    def _dia2_sampling_params(quality: Optional[str]) -> tuple[float, float, int]:
        base_cfg = float(os.getenv("ORATIO_DIA2_CFG_SCALE", "2.0"))
        base_temp = float(os.getenv("ORATIO_DIA2_TEMPERATURE", "0.8"))
        base_top_k = int(os.getenv("ORATIO_DIA2_TOP_K", "50"))
        quality_key = (quality or "").lower()
        if quality_key == "fast":
            cfg_scale = float(os.getenv("ORATIO_DIA2_FAST_CFG_SCALE", str(base_cfg)))
            temperature = float(
                os.getenv("ORATIO_DIA2_FAST_TEMPERATURE", str(base_temp))
            )
            top_k = int(os.getenv("ORATIO_DIA2_FAST_TOP_K", str(base_top_k)))
            return cfg_scale, temperature, top_k
        if quality_key == "quality":
            cfg_scale = float(os.getenv("ORATIO_DIA2_QUALITY_CFG_SCALE", str(base_cfg)))
            temperature = float(
                os.getenv("ORATIO_DIA2_QUALITY_TEMPERATURE", str(base_temp))
            )
            top_k = int(os.getenv("ORATIO_DIA2_QUALITY_TOP_K", str(base_top_k)))
            return cfg_scale, temperature, top_k
        return base_cfg, base_temp, base_top_k

    @staticmethod
    def _dia2_timeout_seconds() -> int:
        return max(60, int(os.getenv("ORATIO_DIA2_TIMEOUT", "300")))

    @staticmethod
    def _dia2_batch_timeout_seconds() -> int:
        return max(120, int(os.getenv("ORATIO_DIA2_BATCH_TIMEOUT", "1200")))

    def _ensure_qwen_tts_deps(self, python_exe: Path) -> None:
        """Install qwen-tts deps into the heavy venv if missing."""
        import subprocess

        check = subprocess.run(
            [str(python_exe), "-c", "import qwen_tts"],
            capture_output=True,
            text=True,
        )
        if check.returncode == 0:
            return

        requirements = Path(__file__).resolve().parent / "requirements_qwen_tts.txt"
        if not requirements.exists():
            raise RuntimeError(
                "Qwen3-TTS dependencies missing and requirements_qwen_tts.txt not found."
            )

        install = subprocess.run(
            [
                str(python_exe),
                "-m",
                "pip",
                "install",
                "-r",
                str(requirements),
            ],
            capture_output=True,
            text=True,
        )
        if install.returncode != 0:
            details = (install.stderr or install.stdout or "").strip()
            raise RuntimeError(f"Failed to install Qwen3-TTS dependencies: {details}")

    @staticmethod
    def _qwen_timeout_seconds(quality: Optional[str]) -> int:
        base = int(os.getenv("ORATIO_QWEN_TIMEOUT", "600"))
        quality_key = (quality or "").lower()
        if quality_key == "fast":
            return max(60, int(os.getenv("ORATIO_QWEN_FAST_TIMEOUT", str(base))))
        if quality_key == "quality":
            return max(60, int(os.getenv("ORATIO_QWEN_QUALITY_TIMEOUT", str(base))))
        return max(60, base)

    @staticmethod
    def _qwen_batch_timeout_seconds(quality: Optional[str]) -> int:
        base = int(os.getenv("ORATIO_QWEN_BATCH_TIMEOUT", "1800"))
        quality_key = (quality or "").lower()
        if quality_key == "fast":
            return max(120, int(os.getenv("ORATIO_QWEN_FAST_BATCH_TIMEOUT", str(base))))
        if quality_key == "quality":
            return max(
                120, int(os.getenv("ORATIO_QWEN_QUALITY_BATCH_TIMEOUT", str(base)))
            )
        return max(120, base)

    def _synthesize_qwen3_customvoice_local(
        self,
        *,
        text: str,
        voice: VoicePreset,
        job_id: str,
        destination: Path,
        speed: float,
        quality: Optional[str],
        style: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        import json
        import subprocess

        python_exe = self._heavy_python()
        if not python_exe.exists():
            raise RuntimeError(
                "Heavy python env not found. Restart the app to let it set up the heavy environment."
            )

        self._ensure_qwen_tts_deps(python_exe)

        backend_dir = Path(__file__).resolve().parent
        worker_script = backend_dir / "qwen_tts_worker.py"
        if not worker_script.exists():
            raise RuntimeError("qwen_tts_worker.py not found")

        # Prefer explicit speaker from preset.
        speaker = voice.voice or "Ryan"

        # Map our language code to Qwen naming.
        lang_map = {
            "en": "English",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "de": "German",
            "fr": "French",
            "ru": "Russian",
            "pt": "Portuguese",
            "es": "Spanish",
            "it": "Italian",
        }
        language = lang_map.get((voice.language or "").lower(), "Auto")
        instruct = style or ""

        cmd = [
            str(python_exe),
            str(worker_script),
            text,
            model_path,
            str(destination),
            language,
            speaker,
            instruct,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self._qwen_timeout_seconds(quality),
        )
        if result.returncode != 0:
            err = result.stderr or result.stdout or "Unknown error"
            raise RuntimeError(f"Qwen3-TTS worker failed: {err}")

        output = self._parse_worker_json(result.stdout, "Qwen3")
        if not output.get("success"):
            raise RuntimeError(output.get("error") or "Qwen3-TTS generation failed")

        duration = float(output.get("duration", 0.0))
        if speed != 1.0 and destination.exists():
            self._apply_speed_to_wav(destination, speed)
            if duration:
                duration = duration / speed

        return AudioResult(
            job_id=job_id,
            audio_path=destination,
            audio_url=f"{self.base_audio_url}/{destination.name}",
            duration_seconds=duration,
            created_at=created_at,
            model=voice.model,
            voice_id=voice.id,
            source="local",
        )

    @staticmethod
    def _parse_worker_json(raw: str, context: str) -> dict:
        raw = (raw or "").strip()
        if not raw:
            raise RuntimeError(f"{context} worker returned empty output.")

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        for line in reversed(lines):
            if not (line.startswith("{") and line.endswith("}")):
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = raw[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                pass

        raise RuntimeError(f"Invalid JSON from {context} worker: {raw[:500]}".strip())

    def _synthesize_qwen3_customvoice_batch(
        self,
        *,
        chunks: List[str],
        voice: VoicePreset,
        job_ids: List[str],
        speed: float,
        style: Optional[str],
        quality: Optional[str],
        created_at: datetime,
    ) -> List[AudioResult]:
        import json
        import os
        import subprocess
        import tempfile

        if len(chunks) != len(job_ids):
            raise ValueError("Chunks/job_ids length mismatch.")

        python_exe = self._heavy_python()
        if not python_exe.exists():
            raise RuntimeError(
                "Heavy python env not found. Restart the app to let it set up the heavy environment."
            )

        self._ensure_qwen_tts_deps(python_exe)

        backend_dir = Path(__file__).resolve().parent
        worker_script = backend_dir / "qwen_tts_worker.py"
        if not worker_script.exists():
            raise RuntimeError("qwen_tts_worker.py not found")

        model_path = self._resolve_model_path(voice.model)
        output_paths = [self.audio_dir / f"{job_id}.wav" for job_id in job_ids]

        speaker = voice.voice or "Ryan"
        lang_map = {
            "en": "English",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "de": "German",
            "fr": "French",
            "ru": "Russian",
            "pt": "Portuguese",
            "es": "Spanish",
            "it": "Italian",
        }
        language = lang_map.get((voice.language or "").lower(), "Auto")
        instruct = style or ""

        payload = {
            "model_path": model_path,
            "chunks": chunks,
            "output_paths": [str(p) for p in output_paths],
            "language": language,
            "speaker": speaker,
            "instruct": instruct,
        }

        fd, payload_path = tempfile.mkstemp(prefix="qwen_batch_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            timeout = self._qwen_batch_timeout_seconds(quality)
            cmd = [
                str(python_exe),
                str(worker_script),
                "--batch",
                str(payload_path),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                err = result.stderr or result.stdout or "Unknown error"
                raise RuntimeError(f"Qwen3-TTS batch failed: {err}")

            output = self._parse_worker_json(result.stdout, "Qwen3 batch")
            if not output.get("success"):
                raise RuntimeError(output.get("error") or "Qwen3-TTS batch failed")

            results = output.get("results") or []
            if len(results) != len(output_paths):
                raise RuntimeError("Qwen3-TTS batch returned unexpected results")

            audio_results: List[AudioResult] = []
            for idx, info in enumerate(results):
                out_path = Path(info.get("output_path") or output_paths[idx])
                duration = float(info.get("duration") or 0.0)
                if speed != 1.0 and out_path.exists():
                    self._apply_speed_to_wav(out_path, speed)
                    if duration:
                        duration = duration / speed
                audio_results.append(
                    AudioResult(
                        job_id=job_ids[idx],
                        audio_path=out_path,
                        audio_url=f"{self.base_audio_url}/{out_path.name}",
                        duration_seconds=duration,
                        created_at=created_at,
                        model=voice.model,
                        voice_id=voice.id,
                        source="local",
                    )
                )
            return audio_results
        finally:
            try:
                os.unlink(payload_path)
            except OSError:
                pass

    def synthesize_qwen3_customvoice_batch(
        self,
        *,
        chunks: List[str],
        voice_id: str,
        job_ids: List[str],
        speed: float = 1.0,
        style: Optional[str] = None,
        quality: Optional[str] = None,
    ) -> List[AudioResult]:
        if voice_id not in VOICE_BY_ID:
            raise ValueError(f"Unknown voice_id: {voice_id}")
        voice = VOICE_BY_ID[voice_id]
        if "qwen3-tts" not in (voice.model or "").lower():
            raise ValueError("Batch Qwen synthesis requested for non-Qwen voice.")
        created_at = datetime.now(timezone.utc)
        return self._synthesize_qwen3_customvoice_batch(
            chunks=chunks,
            voice=voice,
            job_ids=job_ids,
            speed=speed,
            style=style,
            quality=quality,
            created_at=created_at,
        )

    def _synthesize_chroma_local(
        self,
        *,
        text: str,
        voice: VoicePreset,
        job_id: str,
        destination: Path,
        speed: float,
        quality: Optional[str],
        style: Optional[str],
        voice_ref: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        import json
        import subprocess

        python_exe = self._heavy_python()
        if not python_exe.exists():
            raise RuntimeError(
                "Heavy python env not found. Restart the app to let it set up the heavy environment."
            )

        backend_dir = Path(__file__).resolve().parent
        worker_script = backend_dir / "chroma_worker.py"
        if not worker_script.exists():
            raise RuntimeError("chroma_worker.py not found")

        prompt_text = style or ""
        prompt_audio = ""
        if voice_ref:
            prompt_audio = validate_voice_ref(voice_ref)

        cmd = [
            str(python_exe),
            str(worker_script),
            text,
            model_path,
            str(destination),
            prompt_text,
            prompt_audio,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900,
        )
        if result.returncode != 0:
            err = result.stderr or result.stdout or "Unknown error"
            raise RuntimeError(f"Chroma worker failed: {err}")

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"Invalid JSON from Chroma worker: {result.stdout}")
        if not output.get("success"):
            raise RuntimeError(output.get("error") or "Chroma generation failed")

        duration = float(output.get("duration", 0.0))
        if speed != 1.0 and destination.exists():
            self._apply_speed_to_wav(destination, speed)
            if duration:
                duration = duration / speed

        return AudioResult(
            job_id=job_id,
            audio_path=destination,
            audio_url=f"{self.base_audio_url}/{destination.name}",
            duration_seconds=duration,
            created_at=created_at,
            model=voice.model,
            voice_id=voice.id,
            source="local",
        )

    def _synthesize_dia2_batch(
        self,
        *,
        chunks: List[str],
        voice: VoicePreset,
        job_ids: List[str],
        speed: float,
        quality: Optional[str],
        created_at: datetime,
    ) -> List[AudioResult]:
        import json
        import os
        import subprocess
        import tempfile

        if len(chunks) != len(job_ids):
            raise ValueError("Chunks/job_ids length mismatch.")

        model_path = self._resolve_model_path(voice.model)
        output_paths = [self.audio_dir / f"{job_id}.wav" for job_id in job_ids]

        backend_dir = Path(__file__).resolve().parent
        worker_script = backend_dir / "dia2_worker.py"
        if not worker_script.exists():
            raise RuntimeError("dia2_worker.py not found in backend directory")

        dia2_venv_python = self._resolve_dia2_python()
        cfg_scale, temperature, top_k = self._dia2_sampling_params(quality)

        payload = {
            "model_path": model_path,
            "chunks": chunks,
            "output_paths": [str(p) for p in output_paths],
            "cfg_scale": cfg_scale,
            "temperature": temperature,
            "top_k": top_k,
        }

        fd, payload_path = tempfile.mkstemp(prefix="dia2_batch_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            timeout = self._dia2_batch_timeout_seconds()
            cmd = [
                str(dia2_venv_python),
                str(worker_script),
                "--batch",
                str(payload_path),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                err = result.stderr or result.stdout or "Unknown error"
                raise RuntimeError(f"Dia2 batch failed: {err}")

            output = self._parse_worker_json(result.stdout, "Dia2 batch")
            if not output.get("success"):
                raise RuntimeError(output.get("error") or "Dia2 batch failed")

            results = output.get("results") or []
            if len(results) != len(output_paths):
                raise RuntimeError("Dia2 batch returned unexpected results")

            audio_results: List[AudioResult] = []
            for idx, info in enumerate(results):
                out_path = Path(info.get("output_path") or output_paths[idx])
                duration = float(info.get("duration") or 0.0)
                if speed != 1.0 and out_path.exists():
                    self._apply_speed_to_wav(out_path, speed)
                    if duration:
                        duration = duration / speed
                audio_results.append(
                    AudioResult(
                        job_id=job_ids[idx],
                        audio_path=out_path,
                        audio_url=f"{self.base_audio_url}/{out_path.name}",
                        duration_seconds=duration,
                        created_at=created_at,
                        model=voice.model,
                        voice_id=voice.id,
                        source="local",
                    )
                )
            return audio_results
        finally:
            try:
                os.unlink(payload_path)
            except OSError:
                pass

    def synthesize_dia2_batch(
        self,
        *,
        chunks: List[str],
        voice_id: str,
        job_ids: List[str],
        speed: float = 1.0,
        quality: Optional[str] = None,
    ) -> List[AudioResult]:
        if voice_id not in VOICE_BY_ID:
            raise ValueError(f"Unknown voice_id: {voice_id}")
        voice = VOICE_BY_ID[voice_id]
        if "dia2" not in (voice.model or "").lower():
            raise ValueError("Batch Dia2 synthesis requested for non-Dia2 voice.")
        created_at = datetime.now(timezone.utc)
        return self._synthesize_dia2_batch(
            chunks=chunks,
            voice=voice,
            job_ids=job_ids,
            speed=speed,
            quality=quality,
            created_at=created_at,
        )

    def _local_support(self, model_id: str) -> Tuple[bool, Optional[str]]:
        lower_id = model_id.lower()
        if "parler-tts" in lower_id:
            try:
                import parler_tts
            except Exception:
                return False, "Parler local requiert le package parler-tts."
            return True, None
        if "bark" in lower_id:
            try:
                import transformers
            except Exception:
                return False, "Bark local requiert transformers installe."
            return True, None
        if "speecht5" in lower_id:
            try:
                import torch
                from transformers import (
                    SpeechT5ForTextToSpeech,
                    SpeechT5HifiGan,
                    SpeechT5Processor,
                )
            except Exception:
                return False, "SpeechT5 local requiert torch + transformers installes."
            return True, None
        if "mms-tts" in lower_id or "mms_tts" in lower_id:
            try:
                import torch
                from transformers import AutoProcessor, VitsModel
            except Exception:
                return False, "MMS local requiert torch + transformers installes."
            return True, None
        if "kokoro" in lower_id:
            try:
                import kokoro
            except Exception:
                return (
                    False,
                    "Kokoro local indisponible (package kokoro non supporte en Python 3.13).",
                )
            return True, None
        if "xtts" in lower_id:
            try:
                from TTS.api import TTS
            except Exception:
                try:
                    import transformers
                except Exception:
                    return False, "XTTS local requiert TTS ou transformers installes."
            return True, None
        if "f5-tts" in lower_id or "f5_tts" in lower_id:
            try:
                import transformers
            except Exception:
                return False, "F5-TTS local requiert transformers installe."
            return True, None
        if "cosyvoice" in lower_id:
            try:
                import transformers
            except Exception:
                return False, "CosyVoice local requiert transformers installe."
            return True, None
        if "dia2" in lower_id:
            return True, None
        if "chroma" in lower_id:
            return True, None
        if "qwen" in lower_id and "tts" in lower_id:
            return True, None
        return True, None

    def _supports_local_model(self, model_id: str) -> bool:
        supported, _ = self._local_support(model_id)
        return supported

    def _has_local_models(self, model_id: Optional[str] = None) -> bool:
        if model_id and not self._supports_local_model(model_id):
            return False

        # Qwen3-TTS requires its tokenizer repo to be present as well.
        if model_id and "qwen3-tts" in model_id.lower():
            if self.model_manager is None:
                return False
            tokenizer_repo = "Qwen/Qwen3-TTS-Tokenizer-12Hz"
            if self.model_manager.resolve_model_path(tokenizer_repo) is None:
                return False

        statuses = (
            self.model_manager.status() if self.model_manager is not None else None
        )
        if statuses is not None:
            if model_id:
                for status in statuses:
                    if (
                        status.exists
                        and status.repo_id == model_id
                        and self._supports_local_model(status.repo_id)
                    ):
                        return True
                if self.model_manager.resolve_model_path(
                    model_id
                ) is not None and self._supports_local_model(model_id):
                    return True
                return False
            return any(
                status.exists and self._supports_local_model(status.repo_id)
                for status in statuses
            )

        if not self.models_dir:
            return False
        if model_id:
            return (self.models_dir / model_id.replace("/", "_")).exists()
        return any(self.models_dir.glob("*"))

    def _write_wav_bytes(
        self, audio_bytes: bytes, destination: Path, speed: float
    ) -> float:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_in:
            params = wav_in.getparams()
            frames = wav_in.readframes(params.nframes)

        sample_rate = int(params.framerate * speed)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(destination), "wb") as wav_out:
            wav_out.setnchannels(params.nchannels)
            wav_out.setsampwidth(params.sampwidth)
            wav_out.setframerate(sample_rate)
            wav_out.writeframes(frames)

        duration = len(frames) / (params.sampwidth * params.nchannels * sample_rate)
        return duration

    def _generate_stub_audio(
        self, text: str, destination: Path, speed: float = 1.0
    ) -> float:
        sample_rate = 24_000
        base_duration = max(1.0, min(5.0, len(text) / 20.0))
        duration = base_duration / speed
        frequency = 440.0
        amplitude = 0.2

        destination.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(destination), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            frame_count = int(sample_rate * duration)
            for i in range(frame_count):
                value = int(
                    amplitude
                    * 32767
                    * math.sin(2 * math.pi * frequency * i / sample_rate)
                )
                wav_file.writeframes(struct.pack("<h", value))

        return duration

    def _synthesize_local(
        self,
        *,
        text: str,
        voice: VoicePreset,
        job_id: str,
        destination: Path,
        speed: float,
        quality: Optional[str],
        style: Optional[str],
        voice_ref: Optional[str],
        created_at: datetime,
    ) -> AudioResult:
        model_path = self._resolve_model_path(voice.model)
        model_key = model_path

        lower_model = voice.model.lower()
        if "parler-tts" in lower_model:
            return self._synthesize_parler_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                quality=quality,
                style=style,
                created_at=created_at,
                model_path=model_path,
            )
        if "bark" in lower_model:
            return self._synthesize_bark_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                quality=quality,
                style=style,
                created_at=created_at,
                model_path=model_path,
            )
        if "speecht5" in lower_model:
            return self._synthesize_speecht5_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                quality=quality,
                style=style,
                voice_ref=voice_ref,
                created_at=created_at,
                model_path=model_path,
            )
        if "dia2" in lower_model:
            return self._synthesize_dia2_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                quality=quality,
                style=style,
                voice_ref=voice_ref,
                created_at=created_at,
                model_path=model_path,
            )

        if "qwen3-tts" in lower_model and "customvoice" in lower_model:
            return self._synthesize_qwen3_customvoice_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                quality=quality,
                style=style,
                created_at=created_at,
                model_path=model_path,
            )

        if "chroma" in lower_model:
            return self._synthesize_chroma_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                quality=quality,
                style=style,
                voice_ref=voice_ref,
                created_at=created_at,
                model_path=model_path,
            )

        tts = self._get_local_pipeline(model_key, task="text-to-speech")
        outputs = self._run_tts_pipeline(tts, text, speed=speed)
        audio = outputs["audio"] if isinstance(outputs, dict) else outputs
        sampling_rate = (
            outputs.get("sampling_rate", 24000) if isinstance(outputs, dict) else 24000
        )

        duration = self._write_array_to_wav(audio, sampling_rate, destination)
        return AudioResult(
            job_id=job_id,
            audio_path=destination,
            audio_url=f"{self.base_audio_url}/{destination.name}",
            duration_seconds=duration,
            created_at=created_at,
            model=voice.model,
            voice_id=voice.id,
            source="local",
        )

    def _synthesize_parler_local(
        self,
        *,
        text: str,
        voice: VoicePreset,
        job_id: str,
        destination: Path,
        speed: float,
        quality: Optional[str],
        style: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        try:
            import torch
            from parler_tts import ParlerTTSForConditionalGeneration
            from transformers import AutoTokenizer
        except Exception as exc:
            raise RuntimeError(
                "Parler-TTS local mode requires the parler-tts package installed"
            ) from exc

        if model_path not in self._parler_models:
            model = ParlerTTSForConditionalGeneration.from_pretrained(model_path).to(
                "cpu"
            )
            model.eval()
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            self._parler_models[model_path] = (model, tokenizer)
        model, tokenizer = self._parler_models[model_path]

        device = next(model.parameters()).device
        description = style or "Neutral speaker, clear voice, studio quality."
        desc_ids = tokenizer(description, return_tensors="pt").input_ids.to(device)
        prompt_ids = tokenizer(text, return_tensors="pt").input_ids.to(device)

        with torch.inference_mode():
            audio = model.generate(input_ids=desc_ids, prompt_input_ids=prompt_ids)
        waveform = audio.cpu().numpy().squeeze()
        duration = self._write_array_to_wav(
            waveform, model.config.sampling_rate, destination
        )
        return AudioResult(
            job_id=job_id,
            audio_path=destination,
            audio_url=f"{self.base_audio_url}/{destination.name}",
            duration_seconds=duration,
            created_at=created_at,
            model=voice.model,
            voice_id=voice.id,
            source="local",
        )

    def _synthesize_bark_local(
        self,
        *,
        text: str,
        voice: VoicePreset,
        job_id: str,
        destination: Path,
        speed: float,
        quality: Optional[str],
        style: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        try:
            from transformers import pipeline
        except Exception as exc:
            raise RuntimeError(
                "Bark local mode requires transformers installed"
            ) from exc

        model_key = model_path
        if model_key not in self._local_pipelines:
            self._local_pipelines[model_key] = pipeline(
                task="text-to-audio",
                model=model_key,
                device="cpu",
                trust_remote_code=True,
            )
        bark = self._local_pipelines[model_key]
        outputs = bark(text)
        audio = outputs["audio"] if isinstance(outputs, dict) else outputs
        sampling_rate = (
            outputs.get("sampling_rate", 22050) if isinstance(outputs, dict) else 22050
        )
        duration = self._write_array_to_wav(audio, sampling_rate, destination)
        return AudioResult(
            job_id=job_id,
            audio_path=destination,
            audio_url=f"{self.base_audio_url}/{destination.name}",
            duration_seconds=duration,
            created_at=created_at,
            model=voice.model,
            voice_id=voice.id,
            source="local",
        )

    def _resolve_speecht5_embedding(self, voice_ref: str):
        try:
            import torch
            import torchaudio
            from torchaudio.pipelines import SUPERB_XVECTOR
        except Exception as exc:
            raise RuntimeError(
                "SpeechT5 voice_ref requiert torchaudio installe."
            ) from exc

        path = Path(voice_ref).expanduser()
        if not path.exists():
            raise RuntimeError(f"voice_ref introuvable: {voice_ref}")
        cache_key = str(path.resolve())
        cached = self._speaker_embeddings.get(cache_key)
        if cached is not None:
            return cached

        waveform, sample_rate = torchaudio.load(str(path))
        if waveform.ndim > 1 and waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        target_rate = SUPERB_XVECTOR.sample_rate
        if sample_rate != target_rate:
            waveform = torchaudio.functional.resample(
                waveform, sample_rate, target_rate
            )

        if self._speaker_encoder is None:
            self._speaker_encoder = SUPERB_XVECTOR.get_model()
            self._speaker_encoder.eval()

        with torch.inference_mode():
            embedding = self._speaker_encoder(waveform)
        if isinstance(embedding, tuple):
            embedding = embedding[0]
        if embedding.ndim == 1:
            embedding = embedding.unsqueeze(0)
        elif embedding.ndim > 2:
            embedding = embedding.squeeze()
            if embedding.ndim == 1:
                embedding = embedding.unsqueeze(0)
        self._speaker_embeddings[cache_key] = embedding
        return embedding

    def _synthesize_speecht5_local(
        self,
        *,
        text: str,
        voice: VoicePreset,
        job_id: str,
        destination: Path,
        speed: float,
        quality: Optional[str],
        style: Optional[str],
        voice_ref: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        try:
            import torch
            from transformers import (
                SpeechT5ForTextToSpeech,
                SpeechT5HifiGan,
                SpeechT5Processor,
            )
        except Exception as exc:
            raise RuntimeError(
                "SpeechT5 local mode requires transformers installed"
            ) from exc

        if model_path not in self._local_pipelines:
            vocoder_path = self._resolve_model_path("microsoft/speecht5_hifigan")
            processor = SpeechT5Processor.from_pretrained(model_path)
            model = SpeechT5ForTextToSpeech.from_pretrained(model_path)
            vocoder = SpeechT5HifiGan.from_pretrained(vocoder_path)
            self._local_pipelines[model_path] = (processor, model, vocoder)
        processor, model, vocoder = self._local_pipelines[model_path]

        inputs = processor(text=text, return_tensors="pt")
        if voice_ref:
            voice_ref_path = self._resolve_local_voice_ref_path(
                voice_ref, required=True
            )
            speaker_embeddings = self._resolve_speecht5_embedding(str(voice_ref_path))
        else:
            speaker_embeddings = torch.zeros((1, 512))
        speaker_embeddings = speaker_embeddings.to(model.device)

        with torch.inference_mode():
            speech = model.generate_speech(
                inputs["input_ids"],
                speaker_embeddings,
                vocoder=vocoder,
            )
        if speed != 1.0:
            speech = torch.nn.functional.interpolate(
                speech.unsqueeze(0).unsqueeze(0),
                scale_factor=1 / speed,
                mode="linear",
                align_corners=False,
            ).squeeze()
        waveform = speech.cpu().numpy()
        duration = self._write_array_to_wav(
            waveform, processor.feature_extractor.sampling_rate, destination
        )
        return AudioResult(
            job_id=job_id,
            audio_path=destination,
            audio_url=f"{self.base_audio_url}/{destination.name}",
            duration_seconds=duration,
            created_at=created_at,
            model=voice.model,
            voice_id=voice.id,
            source="local",
        )

    def _synthesize_mms_local(
        self,
        *,
        text: str,
        voice: VoicePreset,
        job_id: str,
        destination: Path,
        speed: float,
        quality: Optional[str],
        style: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        try:
            import torch
            import torch.nn.functional as F
            from transformers import AutoProcessor, VitsModel
        except Exception as exc:
            raise RuntimeError(
                "MMS local mode requires transformers and torch installed"
            ) from exc

        if model_path not in self._local_pipelines:
            processor = AutoProcessor.from_pretrained(model_path)
            model = VitsModel.from_pretrained(model_path)
            model.eval()
            self._local_pipelines[model_path] = (processor, model)
        processor, model = self._local_pipelines[model_path]

        inputs = processor(text=text, return_tensors="pt")
        with torch.inference_mode():
            waveform = model(**inputs).waveform

        if waveform.ndim == 2:
            waveform = waveform.unsqueeze(1)
        if speed != 1.0:
            waveform = F.interpolate(
                waveform,
                scale_factor=1 / speed,
                mode="linear",
                align_corners=False,
            )
        waveform = waveform.squeeze().cpu().numpy()

        sampling_rate = getattr(model.config, "sampling_rate", 16000)
        duration = self._write_array_to_wav(waveform, sampling_rate, destination)
        return AudioResult(
            job_id=job_id,
            audio_path=destination,
            audio_url=f"{self.base_audio_url}/{destination.name}",
            duration_seconds=duration,
            created_at=created_at,
            model=voice.model,
            voice_id=voice.id,
            source="local",
        )

    def _synthesize_dia2_local(
        self,
        *,
        text: str,
        voice: VoicePreset,
        job_id: str,
        destination: Path,
        speed: float,
        quality: Optional[str],
        style: Optional[str],
        voice_ref: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        self._ensure_dia2_weights(model_path)
        import json
        import subprocess

        backend_dir = Path(__file__).resolve().parent
        dia2_venv_python = self._resolve_dia2_python()
        cfg_scale, temperature, top_k = self._dia2_sampling_params(quality)

        worker_script = backend_dir / "dia2_worker.py"
        if not worker_script.exists():
            raise RuntimeError("dia2_worker.py not found in backend directory")

        cmd = [
            str(dia2_venv_python),
            str(worker_script),
            text,
            model_path,
            str(destination),
            str(cfg_scale),
            str(temperature),
            str(top_k),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self._dia2_timeout_seconds(),
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise RuntimeError(f"Dia2 worker failed: {error_msg}")

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"Invalid JSON from Dia2 worker: {result.stdout}")

        if not output.get("success"):
            raise RuntimeError(
                f"Dia2 generation failed: {output.get('error', 'Unknown error')}"
            )

        duration = output.get("duration", 0.0)

        if speed != 1.0 and destination.exists():
            self._apply_speed_to_wav(destination, speed)
            if duration:
                duration = duration / speed

        return AudioResult(
            job_id=job_id,
            audio_path=destination,
            audio_url=f"{self.base_audio_url}/{destination.name}",
            duration_seconds=duration,
            created_at=created_at,
            model=voice.model,
            voice_id=voice.id,
            source="local",
        )

    def _ensure_dia2_weights(self, model_path: str) -> None:
        import json
        import os
        import shutil

        model_dir = Path(model_path)
        weights_path = model_dir / "model.safetensors"
        if weights_path.exists():
            return

        parts_manifest = model_dir / "model.safetensors.parts.json"
        if parts_manifest.exists():
            manifest = json.loads(parts_manifest.read_text(encoding="utf-8"))
            parts = [model_dir / name for name in manifest.get("parts", [])]
        else:
            parts = sorted(model_dir.glob("model.safetensors.part*"))

        if not parts:
            raise RuntimeError(
                "Dia2 weights missing. Expected model.safetensors or chunked parts."
            )

        tmp_path = model_dir / "model.safetensors.tmp"
        with tmp_path.open("wb") as out_file:
            for part in parts:
                with part.open("rb") as in_file:
                    shutil.copyfileobj(in_file, out_file, length=4 * 1024 * 1024)

        tmp_path.replace(weights_path)

        keep_parts = os.getenv("ORATIO_KEEP_DIA2_PARTS", "0") == "1"
        if not keep_parts:
            for part in parts:
                try:
                    part.unlink()
                except OSError:
                    pass

    def _write_array_to_wav(
        self, audio_array, sample_rate: int, destination: Path
    ) -> float:
        try:
            import numpy as np
        except Exception as exc:
            raise RuntimeError("Local pipeline requires numpy installed") from exc

        destination.parent.mkdir(parents=True, exist_ok=True)
        if audio_array.ndim > 1:
            audio_array = np.mean(audio_array, axis=1)
        max_val = np.max(np.abs(audio_array))
        if max_val > 0:
            audio_array = audio_array / max_val
        int_data = (audio_array * 32767).astype(np.int16)

        with wave.open(str(destination), "wb") as wav_out:
            wav_out.setnchannels(1)
            wav_out.setsampwidth(2)
            wav_out.setframerate(sample_rate)
            wav_out.writeframes(int_data.tobytes())

        duration = len(int_data) / sample_rate
        return duration

    def _apply_speed_to_wav(self, path: Path, speed: float) -> None:
        with wave.open(str(path), "rb") as wav_in:
            params = wav_in.getparams()
            frames = wav_in.readframes(params.nframes)

        new_sample_rate = int(params.framerate * speed)
        with wave.open(str(path), "wb") as wav_out:
            wav_out.setnchannels(params.nchannels)
            wav_out.setsampwidth(params.sampwidth)
            wav_out.setframerate(new_sample_rate)
            wav_out.writeframes(frames)


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}


def validate_voice_ref(voice_ref: Optional[str]) -> Optional[str]:
    if not voice_ref:
        return None
    if voice_ref.startswith("http"):
        return voice_ref
    path = Path(voice_ref)
    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        raise ValueError(
            "Voice reference must be an audio file (WAV/MP3/OGG), not an image. "
            f"Received: {voice_ref}"
        )
    if ext not in AUDIO_EXTENSIONS:
        raise ValueError(
            f"Invalid voice reference format: {ext}. "
            f"Supported audio formats: {', '.join(AUDIO_EXTENSIONS)}"
        )
    return voice_ref


def chunk_audio_files(input_paths: List[Path], output_path: Path) -> Path:
    import numpy as np

    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_audio = []
    sample_rate = 24000

    for path in input_paths:
        if not path.exists():
            continue
        try:
            with wave.open(str(path), "rb") as wav:
                params = wav.getparams()
                frames = wav.readframes(params.nframes)
                audio = np.frombuffer(frames, dtype=np.int16)
                if params.nchannels == 2:
                    audio = audio.reshape(-1, 2).mean(axis=1).astype(np.int16)
                all_audio.append(audio)
        except Exception as e:
            print(f"Error reading {path}: {e}")
            continue

    if not all_audio:
        raise ValueError("No valid audio files to combine")

    combined = np.concatenate(all_audio).astype(np.int16)

    with wave.open(str(output_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(combined.tobytes())

    return output_path
