#!/usr/bin/env python
"""Qwen3-TTS worker.

Runs in the heavy venv (currently ORATIO_DIA2_PYTHON) because it requires
torch+transformers.

Args:
  <text> <model_path> <output_wav> <language> <speaker> <instruct>
  --batch <payload.json>
"""

from __future__ import annotations

import contextlib
import json
import sys
import wave
from pathlib import Path

import numpy as np


def _write_wav(path: str, audio: np.ndarray, sample_rate: int) -> float:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.reshape(-1)
    audio = audio / (np.max(np.abs(audio)) + 1e-8)
    int_data = (audio * 32767).astype(np.int16)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(int(sample_rate))
        f.writeframes(int_data.tobytes())
    return float(len(audio) / float(sample_rate))


def _load_model(model_path: str):
    import torch
    from qwen_tts import Qwen3TTSModel

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    with contextlib.redirect_stdout(sys.stderr), contextlib.redirect_stderr(
        sys.stderr
    ):
        model = Qwen3TTSModel.from_pretrained(
            model_path,
            device_map=device,
            dtype=dtype,
        )
    return model


def _run_single(
    *,
    text: str,
    model_path: str,
    output_wav: str,
    language: str,
    speaker: str,
    instruct: str,
) -> None:
    model = _load_model(model_path)
    with contextlib.redirect_stdout(sys.stderr), contextlib.redirect_stderr(
        sys.stderr
    ):
        wavs, sr = model.generate_custom_voice(
            text=text,
            language=language,
            speaker=speaker,
            instruct=instruct,
        )
    duration = _write_wav(output_wav, wavs[0], sr)
    print(
        json.dumps(
            {
                "success": True,
                "output_path": output_wav,
                "sample_rate": int(sr),
                "duration": duration,
            }
        )
    )


def _run_batch(payload_path: str) -> None:
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    model_path = payload.get("model_path")
    chunks = payload.get("chunks") or []
    output_paths = payload.get("output_paths") or []
    language = payload.get("language") or "Auto"
    speaker = payload.get("speaker") or "Ryan"
    instruct = payload.get("instruct") or ""

    if not model_path or not isinstance(chunks, list) or not chunks:
        raise ValueError("Batch payload missing model_path/chunks.")
    if len(output_paths) != len(chunks):
        raise ValueError("Batch payload output_paths length mismatch.")

    model = _load_model(model_path)
    results = []
    sample_rate = None
    for text, output_wav in zip(chunks, output_paths):
        with contextlib.redirect_stdout(sys.stderr), contextlib.redirect_stderr(
            sys.stderr
        ):
            wavs, sr = model.generate_custom_voice(
                text=text,
                language=language,
                speaker=speaker,
                instruct=instruct,
            )
        sample_rate = sr
        duration = _write_wav(output_wav, wavs[0], sr)
        results.append(
            {
                "output_path": output_wav,
                "duration": duration,
            }
        )

    print(
        json.dumps(
            {
                "success": True,
                "sample_rate": int(sample_rate or 0),
                "results": results,
            }
        )
    )


def main() -> None:
    try:
        if len(sys.argv) >= 3 and sys.argv[1] == "--batch":
            _run_batch(sys.argv[2])
            return
        if len(sys.argv) < 7:
            print(
                json.dumps(
                    {
                        "success": False,
                        "error": "Usage: <text> <model_path> <output_wav> <language> <speaker> <instruct> | --batch <payload.json>",
                    }
                )
            )
            sys.exit(1)

        _run_single(
            text=sys.argv[1],
            model_path=sys.argv[2],
            output_wav=sys.argv[3],
            language=sys.argv[4] or "Auto",
            speaker=sys.argv[5] or "Ryan",
            instruct=sys.argv[6] or "",
        )
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
