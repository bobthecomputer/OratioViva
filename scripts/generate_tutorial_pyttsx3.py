#!/usr/bin/env python3
"""
Generate tutorial audio files using pyttsx3 (offline TTS)
"""

import sys
import time
import json
import os
from pathlib import Path
import pyttsx3

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

print("=" * 60)
print("OratioViva Tutorial Audio Generator (pyttsx3)")
print("=" * 60)
print(f"\nOutput directory: {OUTPUT_DIR}")
print(f"Generating {len(TUTORIAL_SEGMENTS)} segments...\n")

# Initialize TTS engine
print("Initializing TTS engine...")
engine = pyttsx3.init()

# Get available voices
voices = engine.getProperty("voices")
print(f"Available voices: {len(voices)}")

# Try to find a good English voice
for v in voices:
    if "english" in v.name.lower() or "en" in v.languages:
        engine.setProperty("voice", v.id)
        print(f"Using voice: {v.name}")
        break

engine.setProperty("rate", 175)  # Words per minute

generated_files = []

for i, (segment_id, text) in enumerate(TUTORIAL_SEGMENTS):
    print(f"[{i + 1}/{len(TUTORIAL_SEGMENTS)}] Generating: {segment_id}...")

    output_file = OUTPUT_DIR / f"tutorial_{segment_id}.wav"

    try:
        # Save to file
        engine.save_to_file(text, str(output_file))
        engine.runAndWait()

        # Check if file was created
        if output_file.exists():
            duration = output_file.stat().st_size / 44100 / 2  # Approximate
            print(f"  Saved: {output_file}")
            generated_files.append((segment_id, output_file, duration))
        else:
            print(f"  ERROR: File not created")

    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print(f"Generated {len(generated_files)}/{len(TUTORIAL_SEGMENTS)} segments")
print("=" * 60)

if generated_files:
    # Save manifest
    manifest = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "pyttsx3",
        "segments": [
            {"id": seg_id, "file": str(path)} for seg_id, path, _ in generated_files
        ],
    }
    manifest_file = OUTPUT_DIR / "tutorial_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved: {manifest_file}")

    # Create concat file for ffmpeg
    concat_file = OUTPUT_DIR / "tutorial_concat.txt"
    with open(concat_file, "w") as f:
        for seg_id, path, _ in generated_files:
            f.write(f"file '{path.name}'\n")
    print(f"Concat file: {concat_file}")

    print("\nTo create single MP3:")
    print(
        f"  ffmpeg -f concat -safe 0 -i {concat_file} -b:a 192k tutorial_complete.mp3"
    )
