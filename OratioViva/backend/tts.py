from __future__ import annotations

import io
import math
import struct
import uuid
import wave
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from huggingface_hub import InferenceClient

try:
    # Optional import, only used for provider auto-detection
    from backend.models import ModelManager
except Exception:  # noqa: BLE001
    ModelManager = None  # type: ignore[assignment]

@dataclass(frozen=True)
class VoicePreset:
    id: str
    model: str
    label: str
    language: str
    voice: Optional[str] = None
    description: Optional[str] = None


OPTIONAL_MODELS = {
    m.strip().lower() for m in os.getenv("ORATIO_OPTIONAL_MODELS", "kokoro").split(",") if m.strip()
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
        id="xtts_v2_multi",
        model="coqui/XTTS-v2",
        language="multi",
        label="XTTS v2 Clone",
        description="Voice cloning (voice_ref requis).",
    ),
    VoicePreset(
        id="f5_tts_multi",
        model="SWivid/F5-TTS",
        language="multi",
        label="F5-TTS Clone",
        description="Voice cloning moderne (voice_ref requis).",
    ),
    VoicePreset(
        id="cosyvoice3_multi",
        model="FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
        language="multi",
        label="CosyVoice3 Multi",
        description="Voix expressive (voice_ref requis).",
    ),
    VoicePreset(
        id="kokoro_en_us_0",
        model="hexgrad/Kokoro-82M",
        language="en",
        label="Kokoro US Neutral",
        description="Rapide, clair, anglais US",
    ),
    VoicePreset(
        id="kokoro_en_gb_0",
        model="hexgrad/Kokoro-82M",
        language="en",
        label="Kokoro UK Bright",
        description="Anglais UK, ton clair",
    ),
    VoicePreset(
        id="kokoro_fr_0",
        model="hexgrad/Kokoro-82M",
        language="fr",
        label="Kokoro Francais Clair",
        description="Francais, neutralite",
    ),
]

VOICE_PRESETS = [
    voice for voice in ALL_VOICE_PRESETS if not (SKIP_KOKORO and "kokoro" in voice.model.lower())
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
    source: str  # "inference" or "stub"


AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".webm"}

def _is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTENSIONS


class TTSService:
    def __init__(
        self,
        audio_dir: Path,
        base_audio_url: str = "/audio",
        hf_token: Optional[str] = None,
        use_stub: bool = False,
        fallback_stub: bool = False,
        provider: str = "auto",  # "auto" | "inference" | "local" | "stub"
        models_dir: Optional[Path] = None,
        model_manager: Optional["ModelManager"] = None,
    ) -> None:
        self.audio_dir = audio_dir
        self.base_audio_url = base_audio_url.rstrip("/")
        self.hf_token = hf_token
        self.use_stub = use_stub
        self.fallback_stub = fallback_stub
        self.provider = provider
        self.models_dir = models_dir
        self.model_manager = model_manager
        self._clients: Dict[str, InferenceClient] = {}
        self._local_pipelines: Dict[str, object] = {}
        self._parler_models: Dict[str, Tuple[Any, Any]] = {}
        self._speaker_encoder: Optional[object] = None
        self._speaker_embeddings: Dict[str, Any] = {}
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def list_voices(self):
        return [voice.__dict__ for voice in VOICE_PRESETS]

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

    def _resolve_local_voice_ref_path(self, voice_ref: Optional[str], *, required: bool = False) -> Optional[Path]:
        if not voice_ref or not voice_ref.strip():
            if required:
                raise RuntimeError("Ce modele local requiert un fichier voice_ref.")
            return None
        trimmed = voice_ref.strip()
        if trimmed.lower().startswith(("http://", "https://")):
            raise RuntimeError("voice_ref local doit etre un chemin vers un fichier audio.")
        path = Path(trimmed).expanduser()
        if not path.exists() or not path.is_file():
            raise RuntimeError(f"voice_ref introuvable: {voice_ref}")
        if not _is_audio_file(path):
            raise RuntimeError(f"voice_ref doit etre un fichier audio (.wav, .mp3, .ogg, etc.), pas un fichier {path.suffix}")
        return path

    def _get_local_pipeline(self, model_key: str, task: str = "text-to-speech") -> object:
        try:
            from transformers import pipeline
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Local pipeline requires transformers installed") from exc

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
                            return tts(text, forward_params={**forward_params, **merged})
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

    def synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        style: Optional[str] = None,
        voice_ref: Optional[str] = None,
        job_id: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> AudioResult:
        if voice_id not in VOICE_BY_ID:
            raise ValueError(f"Unknown voice_id: {voice_id}")

        job_id = job_id or str(uuid.uuid4())
        destination = self.audio_dir / f"{job_id}.wav"
        voice = VOICE_BY_ID[voice_id]
        created_at = datetime.now(timezone.utc)

        resolved_provider = provider or self._resolve_provider(voice.model)
        use_stub = self.use_stub or resolved_provider == "stub"

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

        if resolved_provider == "local":
            supported, reason = self._local_support(voice.model)
            if not supported:
                raise RuntimeError(reason or "Modele local indisponible.")
            if not self._has_local_models(voice.model):
                raise RuntimeError(
                    "Modele local manquant. Telechargez-le via l'onglet Modeles."
                )

        voice_ref_payload = None
        if self._supports_voice_ref(voice.model):
            if resolved_provider == "inference":
                voice_ref_payload = self._resolve_voice_ref(voice_ref)
                if voice_ref_payload is None:
                    raise ValueError("Ce modele requiert une reference de voix (voice_ref).")
            else:
                if not voice_ref or not voice_ref.strip():
                    raise ValueError("Ce modele requiert une reference de voix (voice_ref).")

        try:
            if resolved_provider == "local":
                return self._synthesize_local(
                    text=text,
                    voice=voice,
                    job_id=job_id,
                    destination=destination,
                    speed=speed,
                    style=style,
                    voice_ref=voice_ref,
                    created_at=created_at,
                )
            if resolved_provider == "inference":
                return self._synthesize_inference(
                    text=text,
                    voice=voice,
                    voice_ref=voice_ref_payload,
                    job_id=job_id,
                    destination=destination,
                    speed=speed,
                    style=style,
                    created_at=created_at,
                )
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
        except Exception:
            if not self.fallback_stub and resolved_provider != "stub":
                raise
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

    def _get_client(self, model: str) -> InferenceClient:
        if model not in self._clients:
            self._clients[model] = InferenceClient(model=model, token=self.hf_token)
        return self._clients[model]

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

    def _local_support(self, model_id: str) -> Tuple[bool, Optional[str]]:
        lower_id = model_id.lower()
        if "parler-tts" in lower_id:
            try:
                import parler_tts  # type: ignore  # noqa: F401
            except Exception:
                return False, "Parler local requiert le package parler-tts."
            return True, None
        if "bark" in lower_id:
            try:
                import transformers  # type: ignore  # noqa: F401
            except Exception:
                return False, "Bark local requiert transformers installe."
            return True, None
        if "speecht5" in lower_id:
            try:
                import torch  # type: ignore  # noqa: F401
                from transformers import (  # type: ignore  # noqa: F401
                    SpeechT5ForTextToSpeech,
                    SpeechT5HifiGan,
                    SpeechT5Processor,
                )
            except Exception:
                return False, "SpeechT5 local requiert torch + transformers installes."
            return True, None
        if "mms-tts" in lower_id or "mms_tts" in lower_id:
            try:
                import torch  # type: ignore  # noqa: F401
                from transformers import AutoProcessor, VitsModel  # type: ignore  # noqa: F401
            except Exception:
                return False, "MMS local requiert torch + transformers installes."
            return True, None
        if "kokoro" in lower_id:
            try:
                import kokoro  # type: ignore  # noqa: F401
            except Exception:
                return False, "Kokoro local indisponible (package kokoro non supporte en Python 3.13); utilisez HF_TOKEN pour l'inference ou restez en stub."
            return True, None
        if "xtts" in lower_id:
            try:
                from TTS.api import TTS  # type: ignore  # noqa: F401
            except Exception:
                try:
                    import transformers  # type: ignore  # noqa: F401
                except Exception:
                    return False, "XTTS local requiert TTS ou transformers installes."
            return True, None
        if "f5-tts" in lower_id or "f5_tts" in lower_id:
            try:
                import transformers  # type: ignore  # noqa: F401
            except Exception:
                return False, "F5-TTS local requiert transformers installe."
            return True, None
        if "cosyvoice" in lower_id:
            try:
                import transformers  # type: ignore  # noqa: F401
            except Exception:
                return False, "CosyVoice local requiert transformers installe."
            return True, None
        return True, None

    def _supports_local_model(self, model_id: str) -> bool:
        supported, _ = self._local_support(model_id)
        return supported

    def _resolve_provider(self, model_id: Optional[str] = None) -> str:
        if self.provider in {"local", "inference", "stub"}:
            return self.provider
        # auto: prefer local models, then inference (token), else stub
        if self._has_local_models(model_id):
            return "local"
        if self.hf_token:
            return "inference"
        return "stub"

    def current_provider(self) -> str:
        """Expose the provider resolved at runtime."""
        return self._resolve_provider()

    def _has_local_models(self, model_id: Optional[str] = None) -> bool:
        if model_id and not self._supports_local_model(model_id):
            return False

        statuses = self.model_manager.status() if self.model_manager is not None else None
        if statuses is not None:
            if model_id:
                for status in statuses:
                    if (
                        status.exists
                        and status.repo_id == model_id
                        and self._supports_local_model(status.repo_id)
                    ):
                        return True
                if (
                    self.model_manager.resolve_model_path(model_id) is not None
                    and self._supports_local_model(model_id)
                ):
                    return True
                return False
            return any(status.exists and self._supports_local_model(status.repo_id) for status in statuses)

        if not self.models_dir:
            return False
        if model_id:
            return (self.models_dir / model_id.replace("/", "_")).exists()
        return any(self.models_dir.glob("*"))

    def local_support(self, model_id: str) -> Tuple[bool, Optional[str]]:
        """Expose local support info for API responses."""
        return self._local_support(model_id)

    def provider_message(self, statuses: list[Any]) -> Optional[str]:
        """Give a human-readable reason when local provider is unavailable."""
        resolved = self.current_provider()
        if resolved in {"local", "stub"}:
            for status in statuses:
                supported, reason = self._local_support(getattr(status, "repo_id", ""))
                if not supported and reason:
                    return reason
            if self.model_manager is not None and self.model_manager.needs_download():
                return "Modeles locaux manquants. Telechargez-les pour activer le mode local."
        if resolved == "stub" and not self.hf_token:
            return "Aucun token HF fourni; utilisation du mode stub."
        return None

    def _write_wav_bytes(self, audio_bytes: bytes, destination: Path, speed: float) -> float:
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

    def _generate_stub_audio(self, text: str, destination: Path, speed: float = 1.0) -> float:
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
                value = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
                wav_file.writeframes(struct.pack("<h", value))

        return duration

    def _synthesize_inference(
        self,
        *,
        text: str,
        voice: VoicePreset,
        voice_ref: Optional[object],
        job_id: str,
        destination: Path,
        speed: float,
        style: Optional[str],
        created_at: datetime,
    ) -> AudioResult:
        client = self._get_client(voice.model)
        lower_model = voice.model.lower()
        kwargs = {}
        if voice_ref is not None:
            kwargs["voice"] = voice_ref
        elif voice.voice:
            kwargs["voice"] = voice.voice
        if style:
            kwargs["style"] = style
        if "bark" in lower_model:
            audio_bytes = client.text_to_audio(text, model=voice.model)
        else:
            audio_bytes = client.text_to_speech(text, model=voice.model, **kwargs)
        duration = self._write_wav_bytes(audio_bytes, destination, speed=speed)
        return AudioResult(
            job_id=job_id,
            audio_path=destination,
            audio_url=f"{self.base_audio_url}/{destination.name}",
            duration_seconds=duration,
            created_at=created_at,
            model=voice.model,
            voice_id=voice.id,
            source="inference",
        )

    def _synthesize_local(
        self,
        *,
        text: str,
        voice: VoicePreset,
        job_id: str,
        destination: Path,
        speed: float,
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
                style=style,
                voice_ref=voice_ref,
                created_at=created_at,
                model_path=model_path,
            )
        if "xtts" in lower_model:
            return self._synthesize_xtts_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                style=style,
                voice_ref=voice_ref,
                created_at=created_at,
                model_path=model_path,
            )
        if "f5-tts" in lower_model or "f5_tts" in lower_model:
            return self._synthesize_voice_clone_pipeline_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                style=style,
                voice_ref=voice_ref,
                created_at=created_at,
                model_path=model_path,
            )
        if "cosyvoice" in lower_model:
            return self._synthesize_voice_clone_pipeline_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                style=style,
                voice_ref=voice_ref,
                created_at=created_at,
                model_path=model_path,
            )
        if "mms-tts" in lower_model or "mms_tts" in lower_model:
            return self._synthesize_mms_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                style=style,
                created_at=created_at,
                model_path=model_path,
            )
        if "kokoro" in lower_model:
            raise RuntimeError(
                "Local Kokoro inference requires the kokoro package; "
                "install it or use ORATIO_TTS_PROVIDER=inference/stub."
            )

        tts = self._get_local_pipeline(model_key, task="text-to-speech")
        outputs = self._run_tts_pipeline(tts, text, speed=speed)
        audio = outputs["audio"] if isinstance(outputs, dict) else outputs
        sampling_rate = outputs.get("sampling_rate", 24000) if isinstance(outputs, dict) else 24000

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
        style: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        try:
            import torch
            from parler_tts import ParlerTTSForConditionalGeneration
            from transformers import AutoTokenizer
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Parler-TTS local mode requires the parler-tts package installed") from exc

        if model_path not in self._parler_models:
            model = ParlerTTSForConditionalGeneration.from_pretrained(model_path).to("cpu")
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
        duration = self._write_array_to_wav(waveform, model.config.sampling_rate, destination)
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
        style: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        try:
            from transformers import pipeline
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Bark local mode requires transformers installed") from exc

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
        sampling_rate = outputs.get("sampling_rate", 22050) if isinstance(outputs, dict) else 22050
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

    def _synthesize_xtts_local(
        self,
        *,
        text: str,
        voice: VoicePreset,
        job_id: str,
        destination: Path,
        speed: float,
        style: Optional[str],
        voice_ref: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        voice_ref_path = self._resolve_local_voice_ref_path(voice_ref, required=True)
        xtts_error: Optional[Exception] = None
        try:
            from TTS.api import TTS

            model_key = f"xtts::{model_path}"
            if model_key not in self._local_pipelines:
                model_dir = Path(model_path)
                tts_model = None
                if model_dir.exists() and model_dir.is_dir():
                    config_path = model_dir / "config.json"
                    checkpoint = model_dir / "model.pth"
                    if not checkpoint.exists():
                        candidates = [
                            p
                            for p in model_dir.glob("*.pth")
                            if "speaker" not in p.name.lower()
                        ]
                        if candidates:
                            checkpoint = candidates[0]
                    if config_path.exists() and checkpoint.exists():
                        tts_model = TTS(
                            model_path=str(checkpoint),
                            config_path=str(config_path),
                            progress_bar=False,
                            gpu=False,
                        )
                    else:
                        tts_model = TTS(model_path=str(model_dir), progress_bar=False, gpu=False)
                else:
                    tts_model = TTS(model_name=voice.model, progress_bar=False, gpu=False)
                self._local_pipelines[model_key] = tts_model

            tts_model = self._local_pipelines[model_key]
            language = voice.language if voice.language != "multi" else os.getenv("ORATIO_TTS_LANGUAGE", "en")
            audio = tts_model.tts(
                text=text,
                speaker_wav=str(voice_ref_path),
                language=language,
            )
            sample_rate = getattr(getattr(tts_model, "synthesizer", None), "output_sample_rate", 24000)
            duration = self._write_array_to_wav(audio, sample_rate, destination)
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
        except Exception as exc:  # noqa: BLE001
            xtts_error = exc

        try:
            return self._synthesize_voice_clone_pipeline_local(
                text=text,
                voice=voice,
                job_id=job_id,
                destination=destination,
                speed=speed,
                style=style,
                voice_ref=voice_ref,
                created_at=created_at,
                model_path=model_path,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"XTTS local a echoue (TTS puis pipeline): {xtts_error}"
            ) from exc

    def _synthesize_voice_clone_pipeline_local(
        self,
        *,
        text: str,
        voice: VoicePreset,
        job_id: str,
        destination: Path,
        speed: float,
        style: Optional[str],
        voice_ref: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        voice_ref_path = self._resolve_local_voice_ref_path(voice_ref, required=True)
        tts = self._get_local_pipeline(model_path, task="text-to-speech")
        outputs = self._run_tts_pipeline(
            tts,
            text,
            speed=speed,
            voice_ref_path=voice_ref_path,
            prompt_text=style,
        )
        audio = outputs["audio"] if isinstance(outputs, dict) else outputs
        sampling_rate = outputs.get("sampling_rate", 24000) if isinstance(outputs, dict) else 24000
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
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("SpeechT5 voice_ref requiert torchaudio installe.") from exc

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
            waveform = torchaudio.functional.resample(waveform, sample_rate, target_rate)

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
        style: Optional[str],
        voice_ref: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        try:
            import torch
            from transformers import SpeechT5ForTextToSpeech, SpeechT5HifiGan, SpeechT5Processor
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("SpeechT5 local mode requires transformers installed") from exc

        if model_path not in self._local_pipelines:
            vocoder_path = self._resolve_model_path("microsoft/speecht5_hifigan")
            processor = SpeechT5Processor.from_pretrained(model_path)
            model = SpeechT5ForTextToSpeech.from_pretrained(model_path)
            vocoder = SpeechT5HifiGan.from_pretrained(vocoder_path)
            self._local_pipelines[model_path] = (processor, model, vocoder)
        processor, model, vocoder = self._local_pipelines[model_path]

        inputs = processor(text=text, return_tensors="pt")
        if voice_ref:
            voice_ref_path = self._resolve_local_voice_ref_path(voice_ref, required=True)
            speaker_embeddings = self._resolve_speecht5_embedding(str(voice_ref_path))
        else:
            speaker_embeddings = torch.zeros((1, 512))  # neutral speaker embedding
        speaker_embeddings = speaker_embeddings.to(model.device)

        with torch.inference_mode():
            speech = model.generate_speech(
                inputs["input_ids"],
                speaker_embeddings,
                vocoder=vocoder,
            )
        if speed != 1.0:
            # Simple resample by adjusting frame rate via numpy; keep it lightweight
            speech = torch.nn.functional.interpolate(
                speech.unsqueeze(0).unsqueeze(0),
                scale_factor=1 / speed,
                mode="linear",
                align_corners=False,
            ).squeeze()
        waveform = speech.cpu().numpy()
        duration = self._write_array_to_wav(waveform, processor.feature_extractor.sampling_rate, destination)
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
        style: Optional[str],
        created_at: datetime,
        model_path: str,
    ) -> AudioResult:
        try:
            import torch
            import torch.nn.functional as F
            from transformers import AutoProcessor, VitsModel
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("MMS local mode requires transformers and torch installed") from exc

        if model_path not in self._local_pipelines:
            processor = AutoProcessor.from_pretrained(model_path)
            model = VitsModel.from_pretrained(model_path)
            model.eval()
            self._local_pipelines[model_path] = (processor, model)
        processor, model = self._local_pipelines[model_path]

        inputs = processor(text=text, return_tensors="pt")
        with torch.inference_mode():
            waveform = model(**inputs).waveform

        if waveform.ndim == 2:  # (batch, time)
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

    def _write_array_to_wav(self, audio_array, sample_rate: int, destination: Path) -> float:
        try:
            import numpy as np
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Local pipeline requires numpy installed") from exc

        destination.parent.mkdir(parents=True, exist_ok=True)
        # Ensure mono
        if audio_array.ndim > 1:
            audio_array = np.mean(audio_array, axis=1)
        # Normalize to int16
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
