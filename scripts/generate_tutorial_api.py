#!/usr/bin/env python3
"""
Generate tutorial audio files using OratioViva backend API
"""

import requests
import time
import json
import os
from pathlib import Path

API_URL = "http://localhost:8000"
OUTPUT_DIR = Path(os.path.expanduser("~")) / "OratioViva" / "outputs" / "audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TUTORIAL_SEGMENTS = [
    (
        "intro",
        "Welcome to OratioViva, your powerful text-to-speech companion. This tutorial will guide you through everything you need to know to transform your text into natural, clear audio. Whether you are creating audiobooks, voiceovers, or simply listening to articles, OratioViva has you covered. Let us get started!",
    ),
    (
        "setup",
        "Before you begin generating audio, let us make sure you are set up correctly. First, you will need to download the TTS models that power OratioViva. Click on Settings in the toolbar, then select Models. Here you can download voices like Dia Two for streaming dialogue, Parler TTS for style-controlled speech, Bark Small for expressive synthesis, and many more. If you have a Hugging Face token, you can enter it in Settings to access gated models that require authentication. The app runs entirely on your machine, so your data stays private.",
    ),
    (
        "voices",
        "Now let us explore the voice browser. By default, voices are organized by model, but you can switch to language view if you prefer. Each model card shows which voices are available. If a model is not downloaded yet, click the download button to unlock its voices. Once downloaded, you can select a voice from the wheel interface. Try selecting different voices to hear how they sound. For voice cloning, models like Speech T Five, X T T S v Two, F Five T T S, and Cosy Voice Three allow you to use a reference audio file to mimic a specific voice.",
    ),
    (
        "text",
        "Paste any text you want to convert into audio. The editor supports articles, books, scripts, or any other content. You can copy text to your clipboard or clear the editor with the buttons on the right. The character counter shows how long your text is. The estimator panel will show you the estimated audio duration and generation time based on your current settings.",
    ),
    (
        "customize",
        "OratioViva gives you powerful controls to customize how your audio sounds. Use the speed slider to adjust playback from point six times to one and a half times normal speed. Choose your quality mode: Fast for quick previews, Balanced for good quality and speed, or Quality for the best results. Now let us talk about tone presets. Select a tone like Neutral, Expressive, Calm, Authoritative, or Storyteller to change the delivery style.",
    ),
    (
        "generate",
        "When you are ready, click the Generate button to create your audio. You will see a progress bar showing the synthesis status. For long texts over four thousand characters, click the Long Text button to process your content in chunks, either sequentially or in parallel for faster generation.",
    ),
    (
        "history",
        "The History panel shows all your generated audio files. Click any item to play, download, or delete it. You can select multiple items and export them as a ZIP file. The Queue panel shows pending and in-progress jobs.",
    ),
    (
        "export",
        "OratioViva offers multiple export options. Export your files as ZIP for easy sharing, or download a CSV or JSON manifest with metadata about your generations. In Settings, you can adjust the performance profile based on your hardware, configure voice browsing preferences, and manage telemetry options.",
    ),
    (
        "help",
        "Need help at any time? Click Help in the toolbar to start the guided tour again or view keyboard shortcuts. Control Enter generates audio, Escape clears the text, and Control C copies to clipboard.",
    ),
    (
        "conclusion",
        "That is everything you need to know to get the most out of OratioViva. Paste your text, choose a voice, and click Generate. Happy listening!",
    ),
]


def wait_for_job(job_id, timeout=180):
    """Wait for a job to complete and return the result."""
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(f"{API_URL}/jobs/{job_id}")
        if resp.status_code == 200:
            job = resp.json()
            if job["status"] == "succeeded":
                return job
            elif job["status"] == "failed":
                raise Exception(f"Job failed: {job.get('error')}")
        time.sleep(2)
    raise Exception("Job timed out")


print("=" * 60)
print("OratioViva Tutorial Audio Generator")
print("=" * 60)
print(f"\nOutput directory: {OUTPUT_DIR}")
print(f"Generating {len(TUTORIAL_SEGMENTS)} segments...\n")

generated_files = []

for i, (segment_id, text) in enumerate(TUTORIAL_SEGMENTS):
    print(f"[{i + 1}/{len(TUTORIAL_SEGMENTS)}] Generating: {segment_id}...")

    # Submit synthesis job
    payload = {
        "text": text,
        "voice_id": "parler_en_neutral",
        "speed": 1.0,
        "quality": "balanced",
    }

    resp = requests.post(f"{API_URL}/synthesize", json=payload)
    if resp.status_code != 200:
        print(f"  ERROR: {resp.text}")
        continue

    job = resp.json()
    job_id = job["job_id"]

    # Wait for completion
    try:
        result = wait_for_job(job_id)
        audio_url = result.get("audio_url")

        if audio_url:
            # Download audio
            if audio_url.startswith("/"):
                audio_url = API_URL + audio_url

            audio_resp = requests.get(audio_url)
            if audio_resp.status_code == 200:
                output_file = OUTPUT_DIR / f"tutorial_{segment_id}.wav"
                with open(output_file, "wb") as f:
                    f.write(audio_resp.content)
                print(f"  Saved: {output_file}")
                generated_files.append((segment_id, output_file))
            else:
                print(f"  ERROR downloading audio: {audio_resp.status_code}")
        else:
            print(f"  ERROR: No audio_url in result")

    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print(f"Generated {len(generated_files)}/{len(TUTORIAL_SEGMENTS)} segments")
print("=" * 60)

if generated_files:
    # Save manifest
    manifest = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "voice": "dia2_2b_en",
        "segments": [
            {"id": seg_id, "file": str(path)} for seg_id, path in generated_files
        ],
    }
    manifest_file = OUTPUT_DIR / "tutorial_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved: {manifest_file}")

    # Create concat file for ffmpeg
    concat_file = OUTPUT_DIR / "tutorial_concat.txt"
    with open(concat_file, "w") as f:
        for seg_id, path in generated_files:
            f.write(f"file '{path.name}'\n")
    print(f"Concat file: {concat_file}")

    print("\nTo create single MP3:")
    print(
        f"  ffmpeg -f concat -safe 0 -i {concat_file} -b:a 192k tutorial_complete.mp3"
    )
