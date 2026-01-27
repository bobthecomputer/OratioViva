#!/usr/bin/env python3
"""
Generate tutorial audio files using local transformers
"""

import sys
import time
import json
import os
from pathlib import Path
import numpy as np

# Set output directory
OUTPUT_DIR = Path(os.path.expanduser("~")) / "OratioViva" / "outputs" / "audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TUTORIAL_SEGMENTS = [
    (
        "intro",
        "Welcome to OratioViva, your powerful text-to-speech companion. This tutorial will guide you through everything you need to know to transform your text into natural, clear audio.",
    ),
    (
        "setup",
        "Before you begin generating audio, let us make sure you are set up correctly. First, you will need to download the TTS models that power OratioViva.",
    ),
    (
        "voices",
        "Now let us explore the voice browser. By default, voices are organized by model, but you can switch to language view if you prefer.",
    ),
    (
        "text",
        "Paste any text you want to convert into audio. The editor supports articles, books, scripts, or any other content.",
    ),
    (
        "customize",
        "OratioViva gives you powerful controls to customize how your audio sounds. Use the speed slider to adjust playback from point six times to one and a half times normal speed.",
    ),
    (
        "generate",
        "When you are ready, click the Generate button to create your audio. You will see a progress bar showing the synthesis status.",
    ),
    (
        "history",
        "The History panel shows all your generated audio files. Click any item to play, download, or delete it.",
    ),
    (
        "export",
        "OratioViva offers multiple export options. Export your files as ZIP for easy sharing, or download a CSV or JSON manifest.",
    ),
    (
        "help",
        "Need help at any time? Click Help in the toolbar to start the guided tour again or view keyboard shortcuts.",
    ),
    (
        "conclusion",
        "That is everything you need to know to get the most out of OratioViva. Paste your text, choose a voice, and click Generate.",
    ),
]


def generate_with_speecht5(text, output_path):
    """Generate audio using Microsoft SpeechT5."""
    from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan
    from scipy.io.wavfile import write
    import torch

    print("  Loading SpeechT5 model...")

    # Load models
    processor = SpeechT5Processor.from_pretrained("microsoft/speecht5_tts")
    model = SpeechT5ForTextToSpeech.from_pretrained("microsoft/speecht5_tts")
    vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan")

    # Process text
    inputs = processor(text=text, return_tensors="pt")

    # Generate
    print("  Generating audio...")
    with torch.no_grad():
        spectrogram = model.generate_speech(inputs["input_ids"], vocoder=vocoder)

    # Convert to WAV
    spectrogram = spectrogram.numpy()
    audio = spectrogram.flatten()
    audio = audio / max(abs(audio.max()), abs(audio.min())) * 0.98

    # Save
    sample_rate = 22050
    audio_int16 = (audio * 32767).astype(np.int16)
    write(str(output_path), sample_rate, audio_int16)

    duration = len(audio) / sample_rate
    print(f"  Saved: {output_path} ({duration:.1f}s)")
    return duration


print("=" * 60)
print("OratioViva Tutorial Audio Generator (SpeechT5)")
print("=" * 60)
print(f"\nOutput directory: {OUTPUT_DIR}")
print(f"Generating {len(TUTORIAL_SEGMENTS)} segments...\n")

generated_files = []

for i, (segment_id, text) in enumerate(TUTORIAL_SEGMENTS):
    print(f"[{i + 1}/{len(TUTORIAL_SEGMENTS)}] Generating: {segment_id}...")

    output_file = OUTPUT_DIR / f"tutorial_{segment_id}.wav"

    try:
        duration = generate_with_speecht5(text, output_file)
        generated_files.append((segment_id, output_file, duration))
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print(f"Generated {len(generated_files)}/{len(TUTORIAL_SEGMENTS)} segments")
print("=" * 60)

if generated_files:
    # Save manifest
    manifest = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "microsoft/speecht5_tts",
        "segments": [
            {"id": seg_id, "file": str(path), "duration": dur}
            for seg_id, path, dur in generated_files
        ],
    }
    manifest_file = OUTPUT_DIR / "tutorial_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved: {manifest_file}")

    # Create concat file for ffmpeg
    concat_file = OUTPUT_DIR / "tutorial_concat.txt"
    with open(concat_file, "w") as f:
        for seg_id, path, dur in generated_files:
            f.write(f"file '{path.name}'\n")
    print(f"Concat file: {concat_file}")

    print("\nTo create single MP3:")
    print(
        f"  ffmpeg -f concat -safe 0 -i {concat_file} -b:a 192k tutorial_complete.mp3"
    )
