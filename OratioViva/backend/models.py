from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from huggingface_hub import snapshot_download


DEFAULT_MODELS: Dict[str, str] = {
    "kokoro": "hexgrad/Kokoro-82M",
    "parler": "parler-tts/parler-tts-mini-v1.1",
    "bark": "suno/bark-small",
    "speecht5": "microsoft/speecht5_tts",
    "speecht5_vocoder": "microsoft/speecht5_hifigan",
    "mms": "facebook/mms-tts-eng",
}


@dataclass
class ModelStatus:
    id: str
    repo_id: str
    path: Path
    exists: bool


class ModelManager:
    def __init__(self, base_dir: Path, models_dir: Optional[Path], token: Optional[str]) -> None:
        self.base_dir = base_dir
        self.models_dir = models_dir or (base_dir / "models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.token = token
        self._lock = threading.Lock()
        self._downloading = False

    @property
    def downloading(self) -> bool:
        return self._downloading

    def status(self) -> List[ModelStatus]:
        statuses: List[ModelStatus] = []
        for key, repo_id in DEFAULT_MODELS.items():
            dest = self.models_dir / repo_id.replace("/", "_")
            statuses.append(ModelStatus(id=key, repo_id=repo_id, path=dest, exists=dest.exists()))
        return statuses

    def needs_download(self) -> bool:
        return any(not s.exists for s in self.status())

    def download(self, models: Optional[Iterable[str]] = None) -> List[ModelStatus]:
        with self._lock:
            if self._downloading:
                return self.status()
            self._downloading = True
        try:
            repo_ids = DEFAULT_MODELS
            if models:
                repo_ids = {m: DEFAULT_MODELS.get(m, m) for m in models}
            for repo_id in repo_ids.values():
                target = self.models_dir / repo_id.replace("/", "_")
                snapshot_download(
                    repo_id=repo_id,
                    local_dir=target,
                    local_dir_use_symlinks=False,
                    token=self.token,
                )
            return self.status()
        finally:
            with self._lock:
                self._downloading = False
