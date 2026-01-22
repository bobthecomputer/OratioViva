#!/usr/bin/env python
"""Dia2 worker - runs in .venv_dia2 subprocess."""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np
import torch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


def main():
    if len(sys.argv) < 5:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "Usage: <text> <model_path> <output_wav> <cfg_scale> <temp> <top_k>",
                }
            )
        )
        sys.exit(1)

    text = sys.argv[1]
    model_path = sys.argv[2]
    output_wav = sys.argv[3]
    cfg_scale = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0
    temperature = float(sys.argv[5]) if len(sys.argv) > 5 else 0.8
    top_k = int(sys.argv[6]) if len(sys.argv) > 6 else 50

    try:
        from backend.third_party.dia2 import Dia2, GenerationConfig, SamplingConfig

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = "bfloat16" if device == "cuda" else "float32"

        dia = Dia2.from_local(
            config_path=f"{model_path}/config.json",
            weights_path=f"{model_path}/model.safetensors",
            tokenizer_id="nari-labs/Dia2-2B",
            device=device,
            dtype=dtype,
        )

        config = GenerationConfig(
            cfg_scale=cfg_scale,
            audio=SamplingConfig(temperature=temperature, top_k=top_k),
            use_cuda_graph=False,
        )

        result = dia.generate(text, config=config)

        audio = result.waveform.squeeze().cpu().numpy()
        audio = audio / (np.max(np.abs(audio)) + 1e-8)
        int_data = (audio * 32767).astype(np.int16)

        with wave.open(output_wav, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(result.sample_rate)
            f.writeframes(int_data.tobytes())

        duration = len(audio) / result.sample_rate

        print(
            json.dumps(
                {
                    "success": True,
                    "output_path": output_wav,
                    "sample_rate": result.sample_rate,
                    "duration": duration,
                }
            )
        )
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
