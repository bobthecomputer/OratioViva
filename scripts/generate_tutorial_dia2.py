#!/usr/bin/env python3
"""
OratioViva Tutorial Audio Generator - Uses OratioViva's dia2 implementation
"""

import sys
import json
import time
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

print("Tutorial generator starting...")

# Add backend to path
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR.parent))

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
AUDIO_DIR = OUTPUT_DIR / "audio"
MODELS_DIR = Path(__file__).parent.parent / "models"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

TUTORIAL_SEGMENTS = [
    (
        "intro",
        "Welcome to OratioViva, your powerful text-to-speech companion. This tutorial will guide you through everything you need to know to transform your text into natural, clear audio. Whether you are creating audiobooks, voiceovers, or simply listening to articles, OratioViva has you covered. Let us get started!",
        30,
    ),
    (
        "setup",
        "Before you begin generating audio, let us make sure you are set up correctly. First, you will need to download the TTS models that power OratioViva. Click on Settings in the toolbar, then select Models. Here you can download voices like Dia Two for streaming dialogue, Parler TTS for style-controlled speech, Bark Small for expressive synthesis, and many more. If you have a Hugging Face token, you can enter it in Settings to access gated models that require authentication. The app runs entirely on your machine, so your data stays private.",
        45,
    ),
    (
        "voices",
        "Now let us explore the voice browser. By default, voices are organized by model, but you can switch to language view if you prefer. Each model card shows which voices are available. If a model is not downloaded yet, click the download button to unlock its voices. Once downloaded, you can select a voice from the wheel interface. Try selecting different voices to hear how they sound. For voice cloning, models like Speech T Five, X T T S v Two, F Five T T S, and Cosy Voice Three allow you to use a reference audio file to mimic a specific voice. Simply upload a WAV or MP3 file with clear speech, and the model will learn to speak in that voice style.",
        60,
    ),
    (
        "text",
        "Paste any text you want to convert into audio. The editor supports articles, books, scripts, or any other content. You can copy text to your clipboard or clear the editor with the buttons on the right. The character counter shows how long your text is. The estimator panel will show you the estimated audio duration and generation time based on your current settings.",
        30,
    ),
    (
        "customize",
        "OratioViva gives you powerful controls to customize how your audio sounds. Use the speed slider to adjust playback from point six times to one and a half times normal speed. Choose your quality mode: Fast for quick previews, Balanced for good quality and speed, or Quality for the best results. Now let us talk about tone presets. Select a tone like Neutral, Expressive, Calm, Authoritative, or Storyteller to change the delivery style. You can also add a voice direction prompt to give the voice specific instructions, such as warm and confident or soft and gentle. The auto punctuate feature will automatically add basic punctuation to your text if it is missing. For models that support it, you can add a style prompt for fine-grained control over the synthesis. And for voice cloning models, you can provide a reference audio file.",
        75,
    ),
    (
        "generate",
        "When you are ready, click the Generate button to create your audio. You will see a progress bar showing the synthesis status. For long texts over four thousand characters, click the Long Text button to process your content in chunks, either sequentially or in parallel for faster generation. Once complete, your audio appears in the History panel where you can play it directly, download the file, or share it.",
        45,
    ),
    (
        "history",
        "The History panel shows all your generated audio files. Click any item to play, download, or delete it. You can select multiple items and export them as a ZIP file. The Queue panel shows pending and in-progress jobs. If a job fails, you can retry it or remove it from the queue.",
        30,
    ),
    (
        "export",
        "OratioViva offers multiple export options. Export your files as ZIP for easy sharing, or download a CSV or JSON manifest with metadata about your generations. In Settings, you can adjust the performance profile based on your hardware, configure voice browsing preferences, and manage telemetry options. Use the Diagnostics panel to check system information, and Cleanup to free up disk space.",
        45,
    ),
    (
        "help",
        "Need help at any time? Click Help in the toolbar to start the guided tour again or view keyboard shortcuts. Control Enter generates audio, Escape clears the text, and Control C copies to clipboard.",
        15,
    ),
    (
        "conclusion",
        "That is everything you need to know to get the most out of OratioViva. Paste your text, choose a voice, and click Generate. Happy listening!",
        15,
    ),
]


def enhance_text(text, auto_punctuate=True, tone=None):
    if not text:
        return ""
    text = text.strip()
    if auto_punctuate:
        text = re.sub(r"([^\.!?])$", r"\1.", text)
        text = re.sub(r"\s+", " ", text)
    return text


def save_to_history(audio_path, text, model, voice_id, duration, generation_seconds):
    history_path = OUTPUT_DIR / "history.json"
    history = []
    if history_path.exists():
        try:
            with open(history_path, "r") as f:
                history = json.load(f)
        except:
            history = []
    entry = {
        "job_id": str(uuid4()),
        "text_preview": text[:160],
        "text": text,
        "model": model,
        "voice_id": voice_id,
        "created_at": datetime.now().isoformat(),
        "duration_seconds": duration,
        "audio_path": str(audio_path),
        "generation_seconds": generation_seconds,
    }
    history.insert(0, entry)
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)


print("=" * 60)
print("OratioViva Tutorial Audio Generator")
print("=" * 60)

# Load Dia2 using OratioViva's custom implementation
print("\nLoading Dia2 model...")
try:
    from backend.third_party.dia2 import Dia2
    from backend.third_party.dia2.core.model import DecodeState

    model_path = MODELS_DIR / "nari-labs_Dia2-2B"
    config_path = model_path / "config.json"
    weights_path = model_path / "model.safetensors"
    tokenizer_path = model_path
    dia = Dia2.from_local(
        str(config_path),
        str(weights_path),
        device="cpu",
        tokenizer_id=str(tokenizer_path),
    )
    print("Dia2 model loaded!")
except Exception as e:
    print(f"Error loading Dia2 model: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print(f"\nGenerating {len(TUTORIAL_SEGMENTS)} tutorial segments...")
print("-" * 60)

segment_info = []
total_start = time.time()

for i, (segment_id, text, target_duration) in enumerate(TUTORIAL_SEGMENTS):
    print(f"Generating segment: {segment_id}")

    enhanced = enhance_text(text, True, "neutral")

    start = time.time()

    # Generate using Dia2
    result = dia.generate(
        enhanced,
        do_sample=True,
        temperature=1.0,
        top_k=50,
        guidance_scale=3.0,
    )

    audio = result.audio
    elapsed = time.time() - start

    # Save WAV
    output_filename = f"tutorial_{segment_id}_{uuid4().hex[:8]}.wav"
    output_path = AUDIO_DIR / output_filename

    # Write WAV file
    import numpy as np
    from scipy.io.wavfile import write

    audio_float = np.array(audio, dtype=np.float32)
    if len(audio_float.shape) > 1:
        audio_float = audio_float.squeeze()

    # Normalize
    max_val = max(abs(audio_float.max()), abs(audio_float.min()))
    if max_val > 0:
        audio_float = audio_float / max_val * 0.98

    sample_rate = 44100  # Dia2 default
    audio_int16 = (audio_float * 32767).astype(np.int16)
    write(str(output_path), sample_rate, audio_int16)

    duration = len(audio_float) / sample_rate

    # Record history
    save_to_history(
        str(output_path), enhanced, "nari-labs/Dia2-2B", "dia2_2b_en", duration, elapsed
    )

    segment_info.append(
        {
            "segment": segment_id,
            "file": str(output_path),
            "duration": duration,
            "text_length": len(text),
            "target_seconds": target_duration,
        }
    )

    print(
        f"  [{i + 1}/{len(TUTORIAL_SEGMENTS)}] {segment_id}: {duration:.1f}s (target: {target_duration}s)"
    )

total_elapsed = time.time() - total_start
print("-" * 60)
print(f"Total generation time: {total_elapsed:.1f}s")

# Save segment info
info_path = OUTPUT_DIR / "tutorial_segments.json"
with open(info_path, "w") as f:
    json.dump(
        {
            "generated_at": datetime.now().isoformat(),
            "voice": "dia2_2b_en",
            "speed": 1.0,
            "tone": "neutral",
            "segments": segment_info,
            "total_duration": sum(s["duration"] for s in segment_info),
        },
        f,
        indent=2,
    )

print(
    f"\nTotal tutorial duration: {sum(s['duration'] for s in segment_info):.1f} seconds"
)
print(f"Segment info saved to: {info_path}")

# Generate concat manifest
concat_manifest = OUTPUT_DIR / "tutorial_concat.txt"
with open(concat_manifest, "w") as f:
    for seg in segment_info:
        f.write(f"file '{Path(seg['file']).name}'\n")

print(f"\nTo create MP3:")
print(
    f"  ffmpeg -f concat -safe 0 -i {concat_manifest} -b:a 192k tutorial_complete.mp3"
)

print("\n" + "=" * 60)
print("Tutorial audio generation complete!")
print("=" * 60)
