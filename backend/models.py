from __future__ import annotations

import os
import ssl
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from huggingface_hub import hf_hub_download, snapshot_download
from tqdm.auto import tqdm


def format_size(size: int) -> str:
    """Format file size in human readable format."""
    size_f: float = float(size)
    for unit in ["B", "KB", "MB", "GB"]:
        if size_f < 1024:
            return f"{size_f:.1f} {unit}"
        size_f /= 1024
    return f"{size_f:.1f} TB"


@dataclass
class DownloadProgress:
    model_id: str
    repo_id: str
    progress: float
    downloaded_bytes: int
    total_bytes: int
    status: str
    attempt: int = 1
    max_attempts: int = 3
    message: str = ""
    error: Optional[str] = None


DEFAULT_MODELS: Dict[str, str] = {
    "kokoro": "hexgrad/Kokoro-82M",
    "parler": "parler-tts/parler-tts-mini-v1.1",
    "bark": "suno/bark-small",
    "speecht5": "microsoft/speecht5_tts",
    "speecht5_vocoder": "microsoft/speecht5_hifigan",
    "mms": "facebook/mms-tts-eng",
    "dia2": "nari-labs/Dia2-2B",
    # Download-only (not integrated for synthesis yet)
    "chroma_4b": "FlashLabs/Chroma-4B",
    "qwen3_tts": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "qwen3_tokenizer_12hz": "Qwen/Qwen3-TTS-Tokenizer-12Hz",
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


def is_retryable_error(err: Exception) -> tuple[bool, str]:
    """Classify error and determine if it's retryable with reason."""
    err_str = str(err).lower()
    err_type = type(err).__name__

    if any(
        x in err_str
        for x in [
            "tls",
            "ssl",
            "certificate",
            "ca certificate",
            "ssl_cert",
            "ssl_context",
        ]
    ):
        return True, "ssl_error"
    if any(
        x in err_str
        for x in ["connection", "network", "timeout", "econnreset", "eof", "socket"]
    ):
        return True, "network_error"
    if any(x in err_str for x in ["401", "unauthorized", "auth", "token"]):
        return False, "auth_error"
    if any(x in err_str for x in ["403", "forbidden", "access denied"]):
        return False, "auth_error"
    if any(x in err_str for x in ["404", "not found"]):
        return False, "not_found"
    if any(x in err_str for x in ["429", "rate limit", "too many requests"]):
        return True, "rate_limit"
    if any(x in err_str for x in ["disk", "space", "permission", "enospc", "eacces"]):
        return False, "disk_error"
    if any(x in err_str for x in ["keyboardinterrupt", "cancelled", "canceled"]):
        return False, "cancelled"
    return True, "unknown"


def get_fallback_filenames(repo_id: str) -> List[str]:
    """Get appropriate fallback filenames for a model based on repo_id."""
    if "dia2" in repo_id.lower():
        return ["model.safetensors", "model.safetensors.parts.json"]
    if "kokoro" in repo_id.lower():
        return ["pytorch_model.bin", "kokoro-v0_19.safetensors", "config.json"]
    if "bark" in repo_id.lower():
        return ["pytorch_model.bin", "safety_checker_pytorch_model.bin", "config.json"]
    if "speecht5" in repo_id.lower():
        return ["pytorch_model.bin", "speecht5_hifigan_vocoder.pt", "config.json"]
    if "mms" in repo_id.lower():
        return ["pytorch_model.bin", "adapter.bin", "config.json"]
    if "parler" in repo_id.lower():
        return ["pytorch_model.bin", "model.safetensors", "config.json"]
    if "xtts" in repo_id.lower():
        return ["model.pth", "config.json", "XTTS-v2.pt"]
    if "chroma" in repo_id.lower():
        return ["model.safetensors.index.json", "model.safetensors", "config.json"]
    if "qwen" in repo_id.lower() and "tts" in repo_id.lower():
        return ["model.safetensors.index.json", "model.safetensors", "config.json"]
    return ["pytorch_model.bin", "model.safetensors", "config.json"]


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
        self._cancel_download = False
        self._last_progress_time: float = 0
        self._download_start_time: Optional[float] = None

    @property
    def downloading(self) -> bool:
        return self._downloading

    @property
    def download_error(self) -> Optional[str]:
        return self._download_error

    @property
    def current_download_model(self) -> Optional[str]:
        return self._current_download_model

    @property
    def cancel_download(self) -> bool:
        return self._cancel_download

    def set_cancel_download(self, cancel: bool = True) -> None:
        with self._lock:
            self._cancel_download = cancel

    def reset_cancel_download(self) -> None:
        with self._lock:
            self._cancel_download = False

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
        attempt: int = 1,
        max_attempts: int = 3,
        error: Optional[str] = None,
    ) -> None:
        with self._lock:
            if model_id in self._download_progress:
                self._download_progress[model_id].progress = progress
                self._download_progress[model_id].downloaded_bytes = downloaded
                self._download_progress[model_id].total_bytes = total
                self._download_progress[model_id].message = message
                self._download_progress[model_id].attempt = attempt
                self._download_progress[model_id].max_attempts = max_attempts
                self._download_progress[model_id].error = error

    def _check_cancelled(self) -> bool:
        with self._lock:
            return self._cancel_download

    def _clear_partial_download(self, target: Path) -> None:
        """Clear incomplete download to start fresh."""
        if target.exists():
            import shutil

            for item in target.rglob("*"):
                if item.is_file():
                    try:
                        item.unlink()
                    except OSError:
                        pass
            try:
                target.rmdir()
            except OSError:
                pass

    def _try_download_with_fallback(
        self,
        repo_id: str,
        target: Path,
        model_id: str,
    ) -> None:
        max_attempts = 3
        bundled_cert = get_bundled_cert_path()

        if bundled_cert:
            print(f"Using bundled certificate: {bundled_cert}")
            os.environ["SSL_CERT_FILE"] = str(bundled_cert)
            os.environ["REQUESTS_CA_BUNDLE"] = str(bundled_cert)
            os.environ["CURL_CA_BUNDLE"] = str(bundled_cert)

        for attempt in range(1, max_attempts + 1):
            if self._check_cancelled():
                raise Exception("Download cancelled by user")

            self._update_progress(
                model_id,
                repo_id,
                0.05,
                0,
                0,
                f"Starting download... (attempt {attempt}/{max_attempts})",
                attempt,
                max_attempts,
            )

            # Start download in a thread so we can monitor progress
            import threading

            download_result = {"error": None, "done": False}

            def do_download():
                try:
                    snapshot_download(
                        repo_id=repo_id,
                        local_dir=target,
                        local_dir_use_symlinks=False,
                        token=self.token,
                        resume_download=True,
                    )
                    download_result["done"] = True
                except Exception as e:
                    download_result["error"] = e

            download_thread = threading.Thread(target=do_download, daemon=True)
            download_thread.start()

            # Rough estimate used only for progress UI.
            lower_repo = repo_id.lower()
            if "dia2" in lower_repo:
                estimated_total = 7_800_000_000
            elif "chroma" in lower_repo:
                estimated_total = 9_500_000_000
            elif "qwen" in lower_repo and "tts" in lower_repo:
                estimated_total = 4_500_000_000
            else:
                estimated_total = 2_000_000_000

            # Monitor progress by checking file sizes
            last_progress_time = time.time()
            last_size = 0
            stall_counter = 0

            while not download_result["done"] and not download_result["error"]:
                if self._check_cancelled():
                    raise Exception("Download cancelled by user")

                # Calculate current download size from incomplete files and target directory
                current_size = 0
                incomplete_size = 0
                for f in target.rglob("*"):
                    if f.is_file() and f.stat().st_size > 0:
                        size = f.stat().st_size
                        current_size += size
                        if f.name.endswith(".incomplete"):
                            incomplete_size = size

                # Estimate progress (Dia2 model.safetensors is ~4.5GB)
                progress = (
                    min(0.95, current_size / estimated_total)
                    if current_size > 0
                    else 0.05
                )

                # Update progress every 2 seconds or when size changes significantly
                size_changed = abs(current_size - last_size) > (
                    1024 * 1024
                )  # 1MB change
                time_passed = time.time() - last_progress_time > 2.0

                if size_changed or time_passed:
                    status_msg = f"Downloading... {format_size(current_size)}"
                    if incomplete_size > 0:
                        status_msg += f" (incomplete: {format_size(incomplete_size)})"

                    self._update_progress(
                        model_id,
                        repo_id,
                        progress,
                        current_size,
                        estimated_total,
                        status_msg,
                        attempt,
                        max_attempts,
                    )
                    last_size = current_size
                    last_progress_time = time.time()

                    # Detect stall - if no progress for 30 seconds
                    if not size_changed and time_passed:
                        stall_counter += 1
                        if stall_counter > 15:  # 30+ seconds of no progress
                            print(
                                f"Download appears stalled at {format_size(current_size)}"
                            )
                            stall_counter = 0

                download_thread.join(timeout=1.0)
                if download_thread.is_alive():
                    continue
                break

            if download_result["error"]:
                if self._check_cancelled():
                    raise Exception("Download cancelled by user")

                e = download_result["error"]
                retryable, error_type = is_retryable_error(e)
                error_msg = str(e)

                print(
                    f"Attempt {attempt}/{max_attempts} failed: {error_type} - {error_msg[:200]}"
                )

                if not retryable or attempt == max_attempts:
                    raise e

                if error_type == "ssl_error":
                    os.environ.pop("SSL_CERT_FILE", None)
                    os.environ.pop("REQUESTS_CA_BUNDLE", None)
                    os.environ.pop("CURL_CA_BUNDLE", None)
                    self._update_progress(
                        model_id,
                        repo_id,
                        0.05,
                        0,
                        0,
                        f"Retrying without SSL verification...",
                        attempt + 1,
                        max_attempts,
                        error_type,
                    )
                    time.sleep(2**attempt)
                    continue

                if error_type == "network_error":
                    self._update_progress(
                        model_id,
                        repo_id,
                        0.05,
                        0,
                        0,
                        f"Network error, retrying in {2**attempt}s...",
                        attempt + 1,
                        max_attempts,
                        error_type,
                    )
                    time.sleep(2**attempt)
                    continue

                if error_type == "rate_limit":
                    wait_time = 10 * (2 ** (attempt - 1))
                    self._update_progress(
                        model_id,
                        repo_id,
                        0.05,
                        0,
                        0,
                        f"Rate limited, waiting {wait_time}s...",
                        attempt + 1,
                        max_attempts,
                        error_type,
                    )
                    time.sleep(wait_time)
                    continue

                time.sleep(2**attempt)
                continue

            # Download succeeded
            print(f"Download completed successfully: {repo_id}")
            self._update_progress(
                model_id,
                repo_id,
                1.0,
                0,
                0,
                "Download complete!",
                attempt,
                max_attempts,
            )
            return

        raise Exception(f"Download failed after {max_attempts} attempts")

    def cancel_current_download(self) -> None:
        with self._lock:
            self._cancel_download = True

    def clear_download_state(self) -> None:
        with self._lock:
            self._cancel_download = False
            self._download_error = None

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
                self.reset_cancel_download()

                self._download_progress[model_id] = DownloadProgress(
                    model_id=model_id,
                    repo_id=repo_id,
                    progress=0.0,
                    downloaded_bytes=0,
                    total_bytes=0,
                    status="downloading",
                    message=f"Downloading {model_id}...",
                )

                self._update_progress(
                    model_id, repo_id, 0.05, 0, 0, f"Starting download of {model_id}..."
                )

                self._try_download_with_fallback(repo_id, target, model_id)

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
            self.reset_cancel_download()
            return self.status()
        except Exception as exc:
            self._download_error = str(exc)
            if (
                self._current_download_model
                and self._current_download_model in self._download_progress
            ):
                self._download_progress[self._current_download_model].status = "error"
                self._download_progress[self._current_download_model].message = str(exc)
            self.reset_cancel_download()
            raise
        finally:
            with self._lock:
                self._downloading = False
