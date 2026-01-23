#!/usr/bin/env python
"""Chroma worker (FlashLabs/Chroma-4B).

Runs in the heavy venv (currently ORATIO_DIA2_PYTHON) because it requires torch+transformers.

Args:
  <text> <model_path> <output_wav> <prompt_text> <prompt_audio>
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
    if len(sys.argv) < 4:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "Usage: <text> <model_path> <output_wav> <prompt_text> <prompt_audio>",
                }
            )
        )
        sys.exit(1)

    text = sys.argv[1]
    model_path = sys.argv[2]
    output_wav = sys.argv[3]
    prompt_text = sys.argv[4] if len(sys.argv) > 4 else ""
    prompt_audio = sys.argv[5] if len(sys.argv) > 5 else ""

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        # Construct conversation for pure text-to-speech.
        system_prompt = (
            "You are Chroma, an advanced virtual human created by FlashLabs. "
            "Return a spoken response (audio output)."
        )
        conversation = [
            [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": text}],
                },
            ]
        ]

        device_map = "auto" if torch.cuda.is_available() else "cpu"
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            device_map=device_map,
        )
        processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)

        prompt_audio_list = [prompt_audio] if prompt_audio else []
        prompt_text_list = [prompt_text] if prompt_text else []

        inputs = processor(
            conversation,
            add_generation_prompt=True,
            tokenize=False,
            prompt_audio=prompt_audio_list,
            prompt_text=prompt_text_list,
        )
        device = getattr(model, "device", None)
        if device is None:
            device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        output = model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            use_cache=True,
        )

        # The Chroma model emits audio tokens that are decoded via the codec.
        audio_values = model.codec_model.decode(output.permute(0, 2, 1)).audio_values
        audio = audio_values[0].detach().cpu().numpy().astype(np.float32)
        sr = 24_000

        duration = _write_wav(output_wav, audio, sr)
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
