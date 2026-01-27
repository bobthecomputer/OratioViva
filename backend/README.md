# OratioViva Backend (FastAPI)

FastAPI backend for OratioViva TTS desktop application. Handles text-to-speech synthesis, model management, and audio processing.

## Quick Start

### Development
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Production (via Tauri Desktop App)
The backend is bundled with the desktop application and managed automatically.

## Architecture

### Virtual Environments
- **Main venv (`.venv`)**: FastAPI, uvicorn, huggingface_hub, pydantic
- **Dia2 venv (`.venv_dia2`)**: torch, transformers, safetensors (heavy ML deps)

Both venvs are created automatically on first run.

### Directory Structure
```
backend/
├── main.py           # FastAPI app entry point
├── server.py         # Uvicorn server runner
├── tts.py            # TTS service orchestration
├── models.py         # Model management
├── jobs.py           # Job queue and status
├── dia2_worker.py    # Dia2 subprocess worker
├── requirements.txt  # Core dependencies
├── requirements_dia2.txt  # Dia2 ML dependencies
├── certs/           # SSL certificates
└── third_party/     # Third-party code (Dia2, etc.)
```

## Endpoints

### Health & Status
- `GET /health` - API health check
- `GET /voices` - List available voices
- `GET /model-status` - Downloaded models status

### Synthesis
- `POST /synthesize` - Generate audio from text
- `POST /synthesize/long` - Generate long audio in chunks
- `POST /synthesize/chain` - Chain multiple syntheses

### Jobs
- `GET /jobs/{job_id}` - Get job status
- `GET /jobs` - List active jobs
- `DELETE /jobs/{job_id}` - Cancel job

### History
- `GET /history` - List generation history
- `DELETE /history/{job_id}` - Delete history entry

### Export
- `POST /export/zip` - Export audio as ZIP
- `POST /export/manifest` - Export metadata as CSV/JSON
- `POST /export/mp3` - Convert to MP3

### Models
- `GET /models/status` - Model download status
- `POST /models/download` - Download a model

### Reports
- `POST /reports/submit` - Submit bug report/feedback
- `GET /reports` - List submitted reports

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORATIO_DATA_DIR` | Auto | Output directory |
| `ORATIO_MODELS_DIR` | Auto | Models directory |
| `ORATIO_DIA2_PYTHON` | Auto | Dia2 venv Python path |
| `HF_TOKEN` | - | HuggingFace API token |
| `ORATIO_CLEAN_MAX_HOURS` | 48 | Max age of audio files |
| `ORATIO_CLEAN_MAX_HISTORY` | 200 | Max history entries |
| `ORATIO_PORT` | 8000 | Server port |

## Voice Cloning

Supported models for voice cloning:
- **SpeechT5**: `voice_ref` = path to WAV/MP3
- **XTTS-v2**: `voice_ref` required
- **F5-TTS**: `voice_ref` required
- **CosyVoice3**: `voice_ref` required

Reference audio requirements:
- WAV or MP3 format
- 5-30 seconds recommended
- Clear voice, minimal background noise

## Troubleshooting

### Dia2 Worker Fails
1. Check `.venv_dia2` exists in app data
2. Verify torch/transformers installed:
   ```bash
   .venv_dia2\Scripts\python -c "import torch; print(torch.__version__)"
   ```
3. Check logs in `%LOCALAPPDATA%\Oratioviva\logs\`

### Model Download Issues
1. Verify internet connection
2. Check HuggingFace token in Settings
3. Ensure sufficient disk space

### Port Already in Use
The app automatically finds an available port if 8000 is in use.

## License

See project root LICENSE file.
