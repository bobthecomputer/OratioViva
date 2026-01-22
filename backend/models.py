from __future__ import annotations

import os
import ssl
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from huggingface_hub import hf_hub_download, snapshot_download
from tqdm.auto import tqdm


@dataclass
class DownloadProgress:
    model_id: str
    repo_id: str
    progress: float
    downloaded_bytes: int
    total_bytes: int
    status: str
    message: str = ""


DEFAULT_MODELS: Dict[str, str] = {
    "kokoro": "hexgrad/Kokoro-82M",
    "parler": "parler-tts/parler-tts-mini-v1.1",
    "bark": "suno/bark-small",
    "speecht5": "microsoft/speecht5_tts",
    "speecht5_vocoder": "microsoft/speecht5_hifigan",
    "mms": "facebook/mms-tts-eng",
    "dia2": "nari-labs/Dia2-2B",
}
EXTRA_MODELS: Dict[str, str] = {
    "xtts": "coqui/XTTS-v2",
    "f5_tts": "SWivid/F5-TTS",
    "cosyvoice3": "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
}
MODEL_ALIASES: Dict[str, str] = {**DEFAULT_MODELS, **EXTRA_MODELS}


@dataclass
class ModelStatus:
    id: str
    repo_id: str
    path: Path
    exists: bool


def get_bundled_cert_path() -> Optional[Path]:
    bundled = Path(__file__).parent / "certs" / "cacert.pem"
    if bundled.is_file():
        return bundled
    return None


class ModelManager:
    def __init__(
        self,
        base_dir: Path,
        models_dir: Optional[Path],
        token: Optional[str],
        optional_models: Optional[Iterable[str]] = None,
        extra_dirs: Optional[Iterable[Path]] = None,
    ) -> None:
        self.base_dir = base_dir
        self.models_dir = models_dir or (base_dir / "models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.token = token
        self.optional_models: Set[str] = {m.lower() for m in (optional_models or [])}
        self.extra_dirs = [Path(p) for p in (extra_dirs or []) if p]
        self._lock = threading.Lock()
        self._downloading = False
        self._download_error: Optional[str] = None
        self._download_progress: Dict[str, DownloadProgress] = field(
            default_factory=dict
        )
        self._current_download_model: Optional[str] = None

    @property
    def downloading(self) -> bool:
        return self._downloading

    @property
    def download_error(self) -> Optional[str]:
        return self._download_error

    @property
    def current_download_model(self) -> Optional[str]:
        return self._current_download_model

    def get_download_progress(self) -> Optional[DownloadProgress]:
        if (
            self._current_download_model
            and self._current_download_model in self._download_progress
        ):
            return self._download_progress[self._current_download_model]
        return None

    def _candidate_roots(self) -> List[Path]:
        roots = []
        for root in [self.models_dir, *self.extra_dirs]:
            if root and root.exists():
                roots.append(root)
        return roots

    def get_search_paths(self) -> List[str]:
        paths = []
        for root in self._candidate_roots():
            paths.append(str(root))
        return paths

    def resolve_model_path(self, repo_id: str) -> Optional[Path]:
        name = repo_id.replace("/", "_")
        for root in self._candidate_roots():
            candidate = root / name
            if candidate.exists():
                if "dia2" in repo_id.lower() and not self._has_dia2_weights(candidate):
                    continue
                return candidate
        return None

    @staticmethod
    def _has_dia2_weights(model_dir: Path) -> bool:
        weights_path = model_dir / "model.safetensors"
        if weights_path.exists():
            return True
        parts_manifest = model_dir / "model.safetensors.parts.json"
        if parts_manifest.exists():
            return True
        if any(model_dir.glob("model.safetensors.part*")):
            return True
        return False

    def status(self) -> List[ModelStatus]:
        statuses: List[ModelStatus] = []
        for key, repo_id in DEFAULT_MODELS.items():
            resolved = self.resolve_model_path(repo_id)
            dest = resolved or (self.models_dir / repo_id.replace("/", "_"))
            statuses.append(
                ModelStatus(
                    id=key, repo_id=repo_id, path=dest, exists=resolved is not None
                )
            )
        return statuses

    def needs_download(self) -> bool:
        return any(
            not s.exists
            for s in self.status()
            if s.id.lower() not in self.optional_models
        )

    def _update_progress(
        self,
        model_id: str,
        repo_id: str,
        progress: float,
        downloaded: int,
        total: int,
        message: str = "",
    ) -> None:
        with self._lock:
            if model_id in self._download_progress:
                self._download_progress[model_id].progress = progress
                self._download_progress[model_id].downloaded_bytes = downloaded
                self._download_progress[model_id].total_bytes = total
                self._download_progress[model_id].message = message

    def _try_download_with_fallback(
        self,
        repo_id: str,
        target: Path,
        progress_hook,
    ) -> None:
        bundled_cert = get_bundled_cert_path()

        if bundled_cert:
            print(f"Using bundled certificate: {bundled_cert}")
            os.environ["SSL_CERT_FILE"] = str(bundled_cert)
            os.environ["REQUESTS_CA_BUNDLE"] = str(bundled_cert)
            os.environ["CURL_CA_BUNDLE"] = str(bundled_cert)

        try:
            snapshot_download(
                repo_id=repo_id,
                local_dir=target,
                local_dir_use_symlinks=False,
                token=self.token,
                progress_hook=progress_hook,
            )
        except Exception as tls_err:
            err_str = str(tls_err).lower()
            if any(
                x in err_str for x in ["tls", "ssl", "certificate", "ca certificate"]
            ):
                print(f"TLS/SSL error, retrying without verification: {tls_err}")
                self._update_progress(
                    repo_id.split("/")[-1]
                    .lower()
                    .replace("2b", "")
                    .replace("dia", "dia2"),
                    repo_id,
                    0.1,
                    0,
                    0,
                    "Retrying without SSL verification...",
                )
                os.environ.pop("SSL_CERT_FILE", None)
                os.environ.pop("REQUESTS_CA_BUNDLE", None)
                os.environ.pop("CURL_CA_BUNDLE", None)
                try:
                    snapshot_download(
                        repo_id=repo_id,
                        local_dir=target,
                        local_dir_use_symlinks=False,
                        token=self.token,
                        progress_hook=progress_hook,
                        ignore_patterns=["*.safetensors*"],
                    )
                    print("Download completed with fallback (ignore_patterns)")
                    return
                except Exception as e2:
                    print(f"Fallback also failed: {e2}")
                    ssl_context = ssl.create_default_context()
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    hf_hub_download(
                        repo_id=repo_id,
                        filename="pytorch_model.bin",
                        local_dir=target,
                        token=self.token,
                        local_dir_use_symlinks=False,
                        ssl_context=ssl_context,
                    )
                    print("Download completed with SSL_CERT_NONE fallback")
            else:
                raise

    def download(self, models: Optional[Iterable[str]] = None) -> List[ModelStatus]:
        with self._lock:
            if self._downloading:
                return self.status()
            self._downloading = True
            self._download_error = None
            self._download_progress = {}
        try:
            if models:
                repo_ids = {m: MODEL_ALIASES.get(m, m) for m in models}
            else:
                repo_ids = {
                    key: repo_id
                    for key, repo_id in DEFAULT_MODELS.items()
                    if key not in self.optional_models
                }

            for model_id, repo_id in repo_ids.items():
                if self.resolve_model_path(repo_id) is not None:
                    continue

                self._current_download_model = model_id
                target = self.models_dir / repo_id.replace("/", "_")

                self._download_progress[model_id] = DownloadProgress(
                    model_id=model_id,
                    repo_id=repo_id,
                    progress=0.0,
                    downloaded_bytes=0,
                    total_bytes=0,
                    status="downloading",
                    message=f"Downloading {model_id}...",
                )

                def progress_hook(progress):
                    self._update_progress(
                        model_id,
                        repo_id,
                        progress.fraction,
                        progress.downloaded,
                        progress.total,
                        f"Downloading... {progress.fraction * 100:.1f}%",
                    )

                self._update_progress(
                    model_id, repo_id, 0.1, 0, 0, f"Starting download of {model_id}..."
                )

                self._try_download_with_fallback(repo_id, target, progress_hook)

                self._download_progress[model_id] = DownloadProgress(
                    model_id=model_id,
                    repo_id=repo_id,
                    progress=1.0,
                    downloaded_bytes=0,
                    total_bytes=0,
                    status="done",
                    message="Complete!",
                )

            self._current_download_model = None
            return self.status()
        except Exception as exc:
            self._download_error = str(exc)
            if (
                self._current_download_model
                and self._current_download_model in self._download_progress
            ):
                self._download_progress[self._current_download_model].status = "error"
                self._download_progress[self._current_download_model].message = str(exc)
            raise
        finally:
            with self._lock:
                self._downloading = False
