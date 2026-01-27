# OratioViva - Standalone TTS Desktop Application

A powerful, standalone text-to-speech desktop application with support for multiple TTS models, voice cloning, and professional audio generation.

## Features

### Core Features
- **Multiple TTS Models**: Dia2, Parler TTS, Bark, SpeechT5, MMS, and more
- **Voice Cloning**: Support for SpeechT5, XTTS-v2, F5-TTS, and CosyVoice3
- **High-Quality Audio**: Generate natural, clear audio from any text
- **Offline Processing**: All synthesis happens locally on your machine
- **Privacy First**: Your data never leaves your computer

### User Experience
- **Interactive Tutorial**: Audio-guided walkthrough of all features
- **Guided Tour**: Step-by-step introduction to the interface
- **Keyboard Shortcuts**: Efficient workflow with keyboard shortcuts
- **Toast Notifications**: Real-time feedback on all operations
- **OS Notifications**: Desktop notifications when synthesis completes

### Advanced Features
- **Chain Generation**: Queue multiple texts for sequential processing
- **Batch Export**: Export as ZIP, CSV, or JSON manifest
- **MP3 Conversion**: Convert generated audio to MP3 format
- **History Management**: Track and replay all generations
- **Model Management**: Download and manage TTS models

## Installation

### Windows Installer
1. Download `OratioViva_1.2.0_x64-setup.exe`
2. Run the installer and follow the wizard
3. Launch OratioViva from the Start Menu or Desktop shortcut

### First Run Setup
On first launch, the application will:
1. Detect or install Python (if needed)
2. Create isolated virtual environments
3. Install required dependencies
4. Download default TTS models

This process may take several minutes depending on your internet connection.

## System Requirements

- **OS**: Windows 10/11 (64-bit)
- **RAM**: 8GB minimum (16GB recommended)
- **Storage**: 5GB free space (more for additional models)
- **Python**: Automatically managed by the installer

## Usage

### Basic Workflow
1. Paste or type your text in the editor
2. Select a voice from the voice browser
3. Adjust settings (speed, quality, tone)
4. Click "Generate Audio"
5. Download or play the generated audio

### Voice Selection
- Browse by **Model** or **Language** view
- Download additional models from Settings → Models
- Voice cloning requires a reference audio file

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| Ctrl + Enter | Generate audio |
| Escape | Clear text |
| Ctrl + C | Copy text |

## Models

### Pre-installed Models
- **Dia2 2B**: High-quality streaming dialogue (default)
- **Parler TTS**: Style-controlled speech synthesis
- **Bark**: Expressive and creative synthesis

### Downloadable Models
- **SpeechT5**: Voice cloning with reference audio
- **XTTS-v2**: Multi-language voice cloning
- **F5-TTS**: Fast voice cloning
- **CosyVoice3**: Natural voice cloning
- **MMS**: Massively Multilingual Speech

### HuggingFace Token
Some models require authentication. Add your HF token in:
**Settings → Hugging Face Token**

Your token: `[Your HF Token Here]`
Get it from: https://huggingface.co/settings/tokens

## Troubleshooting

### Backend Won't Start
1. Check if port 8000 is already in use
2. Restart the application
3. Check logs in `%LOCALAPPDATA%\Oratioviva\logs\`

### Model Download Fails
1. Verify internet connection
2. Check HuggingFace token in Settings
3. Retry the download

### Audio Quality Issues
1. Try "Quality" mode instead of "Fast"
2. Adjust the speed slider
3. Use a different voice model

## File Locations

- **App Data**: `%LOCALAPPDATA%\Oratioviva\`
- **Models**: `%LOCALAPPDATA%\Oratioviva\models\`
- **Generated Audio**: `%LOCALAPPDATA%\Oratioviva\outputs\`
- **Logs**: `%LOCALAPPDATA%\Oratioviva\logs\`

## Uninstallation

1. Go to **Settings → Cleanup**
2. Click "Clean All" to remove generated files
3. Use Windows "Add or Remove Programs" to uninstall

## Promo Video

A promotional video is available at: `promo-video/` directory

### Tutorial Audio
The tutorial audio file is included in the installation:
- Location: `outputs/audio/tutorial_complete.mp3`
- Duration: ~3 minutes
- Covers all major features

## Technical Details

### Architecture
- **Frontend**: React + Vite + Tauri
- **Backend**: FastAPI + Python
- **TTS Engines**: Dia2, Parler TTS, Bark, SpeechT5, MMS
- **UI Framework**: Custom CSS with dark theme

### Virtual Environments
- Main venv: `.venv` (fastapi, uvicorn, etc.)
- Dia2 venv: `.venv_dia2` (torch, transformers)

### Security
- All processing happens locally
- No data sent to external servers
- HuggingFace token stored locally only

## License

MIT License - See LICENSE file for details.

## Credits

- TTS Models: Nari Labs, Microsoft, Coqui, Suno
- UI Icons: Lucide React
- Framework: Tauri, React, FastAPI
