#!/usr/bin/env python3
"""
OratioViva Tutorial Audio Generator - Truly Standalone Version
Generates the complete tutorial audio in English using OratioViva's TTS engine.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Set up paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
AUDIO_DIR = OUTPUT_DIR / "audio"
MODELS_DIR = BASE_DIR / "models"

# Tutorial script segments with timing targets
TUTORIAL_SEGMENTS = [
    (
        "intro",
        "Welcome to OratioViva, your powerful text-to-speech companion. This tutorial will guide you through everything you need to know to transform your text into natural, clear audio. Whether you're creating audiobooks, voiceovers, or simply listening to articles, OratioViva has you covered. Let's get started!",
        30,
    ),
    (
        "setup",
        "Before you begin generating audio, let's make sure you're set up correctly. First, you'll need to download the TTS models that power OratioViva. Click on Settings in the toolbar, then select Models. Here you can download voices like Dia Two for streaming dialogue, Parler TTS for style-controlled speech, Bark Small for expressive synthesis, and many more. If you have a Hugging Face token, you can enter it in Settings to access gated models that require authentication. The app runs entirely on your machine, so your data stays private.",
        45,
    ),
    (
        "voices",
        "Now let's explore the voice browser. By default, voices are organized by model, but you can switch to language view if you prefer. Each model card shows which voices are available. If a model isn't downloaded yet, click the download button to unlock its voices. Once downloaded, you can select a voice from the wheel interface. Try selecting different voices to hear how they sound. For voice cloning, models like Speech T Five, X T T S v Two, F Five T T S, and Cosy Voice Three allow you to use a reference audio file to mimic a specific voice. Simply upload a WAV or MP3 file with clear speech, and the model will learn to speak in that voice style.",
        60,
    ),
    (
        "text",
        "Paste any text you want to convert into audio. The editor supports articles, books, scripts, or any other content. You can copy text to your clipboard or clear the editor with the buttons on the right. The character counter shows how long your text is. The estimator panel will show you the estimated audio duration and generation time based on your current settings.",
        30,
    ),
    (
        "customize",
        "OratioViva gives you powerful controls to customize how your audio sounds. Use the speed slider to adjust playback from point six times to one and a half times normal speed. Choose your quality mode: Fast for quick previews, Balanced for good quality and speed, or Quality for the best results. Now let's talk about tone presets. Select a tone like Neutral, Expressive, Calm, Authoritative, or Storyteller to change the delivery style. You can also add a voice direction prompt to give the voice specific instructions, such as warm and confident or soft and gentle. The auto punctuate feature will automatically add basic punctuation to your text if it's missing. For models that support it, you can add a style prompt for fine-grained control over the synthesis. And for voice cloning models, you can provide a reference audio file.",
        75,
    ),
    (
        "generate",
        "When you're ready, click the Generate button to create your audio. You'll see a progress bar showing the synthesis status. For long texts over four thousand characters, click the Long Text button to process your content in chunks, either sequentially or in parallel for faster generation. Once complete, your audio appears in the History panel where you can play it directly, download the file, or share it.",
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
        "That's everything you need to know to get the most out of OratioViva. Paste your text, choose a voice, and click Generate. Happy listening!",
        15,
    ),
]


# Voice settings for tutorial narration
TUTORIAL_VOICE = "dia2_2b_en"
TUTORIAL_SPEED = 1.0
TUTORIAL_TONE = "neutral"
TUTORIAL_QUALITY = "balanced"


# Simple voice preset class
class VoicePreset:
    def __init__(self, id, model, label=None, language="en"):
        self.id = id
        self.model = model
        self.label = label or id
        self.language = language


# Voice presets - dia2 voices
VOICE_PRESETS = [
    VoicePreset("dia2_2b_en", "dia2", "Dia2 English", "en"),
    VoicePreset("dia2_2b_es", "dia2", "Dia2 Spanish", "es"),
    VoicePreset("dia2_2b_fr", "dia2", "Dia2 French", "fr"),
    VoicePreset("dia2_2b_de", "dia2", "Dia2 German", "de"),
    VoicePreset("dia2_2b_pt", "dia2", "Dia2 Portuguese", "pt"),
    VoicePreset("dia2_2b_ja", "dia2", "Dia2 Japanese", "ja"),
    VoicePreset("dia2_2b_zh", "dia2", "Dia2 Chinese", "zh"),
]


def ensure_directories():
    """Create necessary directories."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def enhance_text(text, auto_punctuate=True, tone=None):
    """Enhance text with proper punctuation."""
    if not text:
        return ""

    # Basic text cleanup
    text = text.strip()

    # Add periods if missing at end of sentences
    if auto_punctuate:
        import re

        # Ensure proper sentence endings
        text = re.sub(r"([^\.!?])$", r"\1.", text)
        # Fix multiple spaces
        text = re.sub(r"\s+", " ", text)
        # Ensure proper spacing after punctuation
        text = re.sub(r"([\.!?])\s*([A-Z])", r"\1 \2", text)

    return text


def save_to_history(audio_path, text, model, voice_id, duration, generation_seconds):
    """Save generation to history."""
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


async def generate_segment(segment_id, text, job_id):
    """Generate audio for a single tutorial segment using the TTS service."""
    print(f"Generating segment: {segment_id}")

    # Enhance text
    enhanced_text = enhance_text(text, True, TUTORIAL_TONE)

    # Generate unique output filename
    output_filename = f"tutorial_{segment_id}_{uuid4().hex[:8]}.wav"
    output_path = AUDIO_DIR / output_filename
    audio_url = f"/audio/{output_filename}"

    start_time = time.time()

    try:
        # Import and use the actual TTS service
        sys.path.insert(0, str(BASE_DIR / "backend"))
        from tts import TTSService
        from models import ModelManager

        model_manager = ModelManager(
            base_dir=BASE_DIR,
            models_dir=MODELS_DIR,
            token=os.getenv("HF_TOKEN") or None,
        )

        tts_service = TTSService(
            audio_dir=AUDIO_DIR,
            base_audio_url="/audio",
            use_stub=False,
            fallback_stub=False,
            provider="local",
            models_dir=MODELS_DIR,
            model_manager=model_manager,
        )

        result = tts_service.synthesize(
            text=enhanced_text,
            voice_id=TUTORIAL_VOICE,
            speed=TUTORIAL_SPEED,
            quality=TUTORIAL_QUALITY,
            tone_id=TUTORIAL_TONE,
            job_id=job_id,
        )

        elapsed = time.time() - start_time

        # Record in history
        save_to_history(
            audio_path=str(result.audio_path),
            text=enhanced_text,
            model="nari-labs/Dia2-2B",
            voice_id=TUTORIAL_VOICE,
            duration=result.duration_seconds,
            generation_seconds=elapsed,
        )

        return result

    except Exception as e:
        print(f"Error generating {segment_id}: {e}")
        import traceback

        traceback.print_exc()
        raise


async def generate_tutorial_audio():
    """Generate the complete tutorial audio."""
    print("=" * 60)
    print("OratioViva Tutorial Audio Generator")
    print("=" * 60)

    # Setup
    ensure_directories()

    # Check if voice is available
    voice = next((v for v in VOICE_PRESETS if v.id == TUTORIAL_VOICE), None)
    if voice is None:
        print(f"ERROR: Voice {TUTORIAL_VOICE} not found.")
        return False

    print(f"\nUsing voice: {voice.label}")

    # Generate each segment
    segment_info = []

    print(f"\nGenerating {len(TUTORIAL_SEGMENTS)} tutorial segments...")
    print("-" * 60)

    total_start = time.time()

    for i, (segment_id, text, target_duration) in enumerate(TUTORIAL_SEGMENTS):
        job_id = f"tutorial_{segment_id}_{uuid4().hex[:8]}"

        try:
            result = await generate_segment(segment_id, text, job_id)

            audio_path = Path(result.audio_path)
            segment_info.append(
                {
                    "segment": segment_id,
                    "file": str(audio_path),
                    "duration": result.duration_seconds,
                    "text_length": len(text),
                    "target_seconds": target_duration,
                }
            )

            print(
                f"  [{i + 1}/{len(TUTORIAL_SEGMENTS)}] {segment_id}: {result.duration_seconds:.1f}s (target: {target_duration}s)"
            )

        except Exception as e:
            print(f"  [{i + 1}/{len(TUTORIAL_SEGMENTS)}] {segment_id}: ERROR - {e}")
            return False

    total_elapsed = time.time() - total_start

    print("-" * 60)
    print(f"Total generation time: {total_elapsed:.1f}s")

    # Save segment info
    info_path = OUTPUT_DIR / "tutorial_segments.json"
    with open(info_path, "w") as f:
        json.dump(
            {
                "generated_at": datetime.now().isoformat(),
                "voice": TUTORIAL_VOICE,
                "speed": TUTORIAL_SPEED,
                "tone": TUTORIAL_TONE,
                "segments": segment_info,
                "total_duration": sum(s["duration"] for s in segment_info),
            },
            f,
            indent=2,
        )

    print(f"\nSegment info saved to: {info_path}")
    print(
        f"Total tutorial duration: {sum(s['duration'] for s in segment_info):.1f} seconds"
    )

    # Generate concatenation manifest for ffmpeg
    concat_manifest = OUTPUT_DIR / "tutorial_concat.txt"
    with open(concat_manifest, "w") as f:
        for segment in segment_info:
            f.write(f"file '{Path(segment['file']).name}'\n")

    print(f"\nTo concatenate all segments into one file:")
    print(
        f"  ffmpeg -f concat -safe 0 -i {concat_manifest} -c copy tutorial_complete.wav"
    )
    print(f"\nOr to create an MP3:")
    print(
        f"  ffmpeg -f concat -safe 0 -i {concat_manifest} -b:a 192k tutorial_complete.mp3"
    )

    return True


if __name__ == "__main__":
    success = asyncio.run(generate_tutorial_audio())

    if success:
        print("\n" + "=" * 60)
        print("Tutorial audio generation complete!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("ERROR: Tutorial audio generation failed!")
        print("=" * 60)
        sys.exit(1)
