#!/usr/bin/env python
"""Dia2 worker - runs in .venv_dia2 subprocess."""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path
from typing import List

import numpy as np
import torch

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


def _load_dia2(model_path: str):
    from backend.third_party.dia2 import Dia2

    device = "cuda" if torch.cuda.is_available() else "cpu"
    use_cuda_graph = torch.cuda.is_available()
    dtype = "bfloat16" if device == "cuda" else "float32"

    print(
        json.dumps(
            {"device": device, "use_cuda_graph": use_cuda_graph, "dtype": dtype}
        ),
        file=sys.stderr,
    )

    return Dia2.from_local(
        config_path=f"{model_path}/config.json",
        weights_path=f"{model_path}/model.safetensors",
        tokenizer_id=model_path,
        device=device,
        dtype=dtype,
    )


def _write_audio(output_wav: str, waveform: np.ndarray, sample_rate: int) -> float:
    audio = waveform.squeeze().cpu().numpy()
    audio = audio / (np.max(np.abs(audio)) + 1e-8)
    int_data = (audio * 32767).astype(np.int16)
    out_path = Path(output_wav)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(int_data.tobytes())
    return len(audio) / sample_rate


def _run_single(args: List[str]) -> None:
    text = args[0]
    model_path = args[1]
    output_wav = args[2]
    cfg_scale = float(args[3]) if len(args) > 3 else 2.0
    temperature = float(args[4]) if len(args) > 4 else 0.8
    top_k = int(args[5]) if len(args) > 5 else 50

    from backend.third_party.dia2 import GenerationConfig, SamplingConfig

    dia = _load_dia2(model_path)
    use_cuda_graph = torch.cuda.is_available()
    config = GenerationConfig(
        cfg_scale=cfg_scale,
        audio=SamplingConfig(temperature=temperature, top_k=top_k),
        use_cuda_graph=use_cuda_graph,
    )

    result = dia.generate(text, config=config)
    duration = _write_audio(output_wav, result.waveform, result.sample_rate)
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


def _run_batch(payload_path: str) -> None:
    with open(payload_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    model_path = payload.get("model_path") or ""
    chunks = payload.get("chunks") or []
    output_paths = payload.get("output_paths") or []
    cfg_scale = float(payload.get("cfg_scale", 2.0))
    temperature = float(payload.get("temperature", 0.8))
    top_k = int(payload.get("top_k", 50))

    if not model_path or not chunks or not output_paths:
        raise ValueError("Batch payload missing model_path/chunks/output_paths")
    if len(chunks) != len(output_paths):
        raise ValueError("Batch payload chunks/output_paths length mismatch")

    from backend.third_party.dia2 import GenerationConfig, SamplingConfig

    dia = _load_dia2(model_path)
    use_cuda_graph = torch.cuda.is_available()
    config = GenerationConfig(
        cfg_scale=cfg_scale,
        audio=SamplingConfig(temperature=temperature, top_k=top_k),
        use_cuda_graph=use_cuda_graph,
    )

    results = []
    for text, out_path in zip(chunks, output_paths):
        result = dia.generate(text, config=config)
        duration = _write_audio(out_path, result.waveform, result.sample_rate)
        results.append(
            {
                "output_path": out_path,
                "sample_rate": result.sample_rate,
                "duration": duration,
            }
        )

    print(json.dumps({"success": True, "results": results}))


def main():
    try:
        if len(sys.argv) >= 3 and sys.argv[1] == "--batch":
            _run_batch(sys.argv[2])
            return

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

        _run_single(sys.argv[1:])
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
