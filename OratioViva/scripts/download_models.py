#!/usr/bin/env python
"""
Download TTS models locally to use OratioViva en mode offline.
Place the folder path in ORATIO_MODELS_DIR (or rely on PyInstaller bundled models).

Examples:
  python scripts/download_models.py --dest models
  python scripts/download_models.py --models kokoro parler --dest assets/models
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable, List

from huggingface_hub import snapshot_download

DEFAULT_MODELS = {
    "kokoro": "hexgrad/Kokoro-82M",
    "parler": "parler-tts/parler-tts-mini-v1.1",
    "bark": "suno/bark-small",
    "speecht5": "microsoft/speecht5_tts",
    "speecht5_vocoder": "microsoft/speecht5_hifigan",
    "mms": "facebook/mms-tts-eng",
}


def resolve_repo_ids(models: Iterable[str]) -> List[str]:
    repo_ids: List[str] = []
    for name in models:
        repo_ids.append(DEFAULT_MODELS.get(name, name))
    return repo_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Telecharge les modeles TTS necessaires en local.")
    parser.add_argument(
        "--dest",
        default="models",
        help="Dossier cible pour stocker les modeles (cree si absent).",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_MODELS.keys()),
        help="Liste de modeles (alias kokoro/parler/bark/speecht5/mms ou repo_id HF).",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Token Hugging Face (sinon HF_TOKEN/HUGGINGFACEHUB_API_TOKEN).",
    )
    args = parser.parse_args()

    dest = Path(args.dest).expanduser().resolve()
    token = args.token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    repo_ids = resolve_repo_ids(args.models)

    dest.mkdir(parents=True, exist_ok=True)
    for repo_id in repo_ids:
        target = dest / repo_id.replace("/", "_")
        print(f"--> Downloading {repo_id} to {target}")
        snapshot_download(
            repo_id=repo_id,
            local_dir=target,
            local_dir_use_symlinks=False,
            token=token,
        )
    print("Done.")


if __name__ == "__main__":
    main()
