#!/usr/bin/env python
"""Qwen3-TTS worker.

Runs in the heavy venv (currently ORATIO_DIA2_PYTHON) because it requires torch+transformers.

Args:
  <text> <model_path> <output_wav> <language> <speaker> <instruct>
"""

from __future__ import annotations

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


def main() -> None:
    if len(sys.argv) < 7:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "Usage: <text> <model_path> <output_wav> <language> <speaker> <instruct>",
                }
            )
        )
        sys.exit(1)

    text = sys.argv[1]
    model_path = sys.argv[2]
    output_wav = sys.argv[3]
    language = sys.argv[4] or "Auto"
    speaker = sys.argv[5] or "Ryan"
    instruct = sys.argv[6] or ""

    try:
        import torch
        from qwen_tts import Qwen3TTSModel

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

        model = Qwen3TTSModel.from_pretrained(
            model_path,
            device_map=device,
            dtype=dtype,
        )

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
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
