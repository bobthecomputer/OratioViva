#!/usr/bin/env python3
"""
Generate tutorial audio files using edge-tts (Microsoft Edge TTS)
"""

import asyncio
import sys
import time
import json
import os
from pathlib import Path
import edge_tts

# Set output directory
OUTPUT_DIR = Path(os.path.expanduser("~")) / "OratioViva" / "outputs" / "audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEXT = """Welcome to OratioViva, your powerful text-to-speech companion. This tutorial will guide you through everything you need to know to transform your text into natural, clear audio.

Before you begin generating audio, let us make sure you are set up correctly. First, you will need to download the TTS models that power OratioViva. Click on Settings in the toolbar, then select Models. Here you can download voices like Dia Two for streaming dialogue, Parler TTS for style-controlled speech, Bark Small for expressive synthesis, and many more.

Now let us explore the voice browser. By default, voices are organized by model, but you can switch to language view if you prefer. Each model card shows which voices are available. If a model is not downloaded yet, click the download button to unlock its voices.

Paste any text you want to convert into audio. The editor supports articles, books, scripts, or any other content. You can copy text to your clipboard or clear the editor with the buttons on the right.

OratioViva gives you powerful controls to customize how your audio sounds. Use the speed slider to adjust playback from point six times to one and a half times normal speed. Choose your quality mode.

When you are ready, click the Generate button to create your audio. You will see a progress bar showing the synthesis status. For long texts, use the Long Text button to process your content in chunks.

The History panel shows all your generated audio files. Click any item to play, download, or delete it. You can select multiple items and export them as a ZIP file.

OratioViva offers multiple export options. Export your files as ZIP for easy sharing, or download a CSV or JSON manifest with metadata about your generations.

Need help at any time? Click Help in the toolbar to start the guided tour again or view keyboard shortcuts. Control Enter generates audio, Escape clears the text, and Control C copies to clipboard.

That is everything you need to know to get the most out of OratioViva. Paste your text, choose a voice, and click Generate. Happy listening!
"""


async def generate():
    print("=" * 60)
    print("OratioViva Tutorial Audio Generator (Edge TTS)")
    print("=" * 60)
    print(f"\nOutput directory: {OUTPUT_DIR}")

    # List available voices
    voices = await edge_tts.list_voices()
    print(f"Available voices: {len(voices)}")

    # Find a good English voice
    en_voices = [v for v in voices if v["Locale"].startswith("en-")]
    for v in en_voices:
        if "Neural" in v["Name"]:
            selected_voice = v["Name"]
            break
    else:
        selected_voice = en_voices[0]["Name"] if en_voices else "en-US-AriaNeural"

    print(f"Using voice: {selected_voice}")

    output_file = OUTPUT_DIR / "tutorial_complete.mp3"

    print(f"\nGenerating tutorial audio...")

    communicate = edge_tts.Communicate(TEXT, selected_voice, rate="+0%")
    await communicate.save(str(output_file))

    print(f"\nSaved: {output_file}")

    # Check file size
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"Size: {size_mb:.2f} MB")

    print("\n" + "=" * 60)
    print("Tutorial audio generated successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(generate())
