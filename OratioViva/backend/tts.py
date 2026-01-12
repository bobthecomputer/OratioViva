from __future__ import annotations

import io
import math
import struct
import uuid
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

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


VOICE_PRESETS = [
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
    VoicePreset(
        id="parler_en_neutral",
        model="parler-tts/parler-tts-mini-v1.1",
        language="en",
        label="Parler Neutral",
        description="Parler-TTS avec prompt de style",
    ),
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
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def list_voices(self):
        return [voice.__dict__ for voice in VOICE_PRESETS]

    def synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        speed: float = 1.0,
        style: Optional[str] = None,
        job_id: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> AudioResult:
        if voice_id not in VOICE_BY_ID:
            raise ValueError(f"Unknown voice_id: {voice_id}")

        job_id = job_id or str(uuid.uuid4())
        destination = self.audio_dir / f"{job_id}.wav"
        voice = VOICE_BY_ID[voice_id]
        created_at = datetime.now(timezone.utc)

        resolved_provider = provider or self._resolve_provider()
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

        try:
            if resolved_provider == "local":
                return self._synthesize_local(
                    text=text,
                    voice=voice,
                    job_id=job_id,
                    destination=destination,
                    speed=speed,
                    style=style,
                    created_at=created_at,
                )
            if resolved_provider == "inference":
                return self._synthesize_inference(
                    text=text,
                    voice=voice,
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

    def _resolve_provider(self) -> str:
        if self.provider in {"local", "inference", "stub"}:
            return self.provider
        # auto: prefer local models, then inference (token), else stub
        if self._has_local_models():
            return "local"
        if self.hf_token:
            return "inference"
        return "stub"

    def current_provider(self) -> str:
        """Expose the provider resolved at runtime."""
        return self._resolve_provider()

    def _has_local_models(self) -> bool:
        if self.model_manager is not None:
            return not self.model_manager.needs_download()
        if not self.models_dir:
            return False
        return any(self.models_dir.glob("*"))

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
        job_id: str,
        destination: Path,
        speed: float,
        style: Optional[str],
        created_at: datetime,
    ) -> AudioResult:
        client = self._get_client(voice.model)
        kwargs = {}
        if voice.voice:
            kwargs["voice"] = voice.voice
        if style:
            kwargs["style"] = style

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
        created_at: datetime,
    ) -> AudioResult:
        model_path = voice.model
        pipeline_key = voice.model
        if self.models_dir:
            candidate = self.models_dir / voice.model.replace("/", "_")
            if candidate.exists():
                model_path = str(candidate)
                pipeline_key = model_path

        try:
            from transformers import pipeline
            import numpy as np
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Local pipeline requires transformers and numpy installed") from exc

        if pipeline_key not in self._local_pipelines:
            self._local_pipelines[pipeline_key] = pipeline(
                task="text-to-speech",
                model=model_path,
                device="cpu",
            )
        tts = self._local_pipelines[pipeline_key]
        outputs = tts(text, forward_params={"speed": speed})
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
