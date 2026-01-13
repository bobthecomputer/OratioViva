from __future__ import annotations

import io
import math
import struct
import uuid
import wave
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
    VoicePreset(
        id="bark_en_0",
        model="suno/bark-small",
        language="en",
        label="Bark Small EN",
        description="Modèle Bark léger (<8GB VRAM), neutre",
    ),
    VoicePreset(
        id="speecht5_en_0",
        model="microsoft/speecht5_tts",
        language="en",
        label="SpeechT5 EN",
        description="SpeechT5 + HiFiGAN vocoder, speaker embed par défaut",
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
        self._parler_models: Dict[str, Tuple[Any, Any]] = {}
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

    def _resolve_model_path(self, model_name: str) -> str:
        model_path = model_name
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
        if "kokoro" in lower_id:
            try:
                import kokoro  # type: ignore  # noqa: F401
            except Exception:
                return False, "Kokoro local indisponible (package kokoro non supporte en Python 3.13); utilisez HF_TOKEN pour l'inference ou restez en stub."
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
        if self.model_manager is not None:
            if self.model_manager.needs_download():
                return False
            for status in self.model_manager.status():
                if status.exists and self._supports_local_model(status.repo_id):
                    return True
            return False
        if not self.models_dir:
            return False
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
                created_at=created_at,
                model_path=model_path,
            )
        if "kokoro" in lower_model:
            raise RuntimeError(
                "Local Kokoro inference requires the kokoro package; "
                "install it or use ORATIO_TTS_PROVIDER=inference/stub."
            )

        try:
            from transformers import pipeline
            import numpy as np
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Local pipeline requires transformers and numpy installed") from exc

        if model_key not in self._local_pipelines:
            self._local_pipelines[model_key] = pipeline(
                task="text-to-speech",
                model=model_key,
                device="cpu",
                trust_remote_code=True,
            )
        tts = self._local_pipelines[model_key]
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

    def _synthesize_speecht5_local(
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
        speaker_embeddings = torch.zeros((1, 512))  # neutral speaker embedding

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
