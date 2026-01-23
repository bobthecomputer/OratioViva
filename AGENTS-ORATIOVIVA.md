# OratioViva Agent Playbook

This file documents the workflow for making robust changes to OratioViva.

## Ground Rules

- Debug from logs first: `C:\Users\<user>\AppData\Roaming\com.oratioviva.app\logs\`.
- Avoid "silent" fallbacks. If we must fall back (e.g., stub audio), surface it in UI/health.
- Separate concerns:
  - Backend venv (`.venv`) is lightweight (FastAPI, huggingface_hub, etc.)
  - Dia2 venv (`.venv_dia2`) contains heavy deps (torch, transformers, sphn, etc.)

## Packaging Reality (Tauri)

- The bundled backend lives under `...\AppData\Local\OratioViva\_up_\_up_\backend`.
- The writable data directory is `...\AppData\Roaming\com.oratioviva.app`.
- Always pass paths through env vars from the bootstrapper (Rust) to the backend (Python):
  - `ORATIO_DATA_DIR`, `ORATIO_MODELS_DIR`, `ORATIO_OUTPUTS_DIR`, `ORATIO_LOG_DIR`
  - `ORATIO_DIA2_PYTHON` (path to `.venv_dia2` interpreter)

## Model Downloads

- Prefer `snapshot_download(local_dir=...)` to keep a single folder per repo.
- Show progress based on local file sizes (large files update slowly).
- Support cancel and safe resume.

## Synthesis Debug Checklist

1. Confirm provider mode via `/health` (and show in UI).
2. If output is a 440Hz beep, you are in stub mode.
3. For Dia2:
   - Ensure `model.safetensors` exists in the model folder.
   - Ensure `.venv_dia2` has torch/transformers/safetensors/sphn.
   - Ensure `ORATIO_DIA2_PYTHON` points to the correct interpreter.

## Release Steps

1. Build frontend: `cd frontend && npm run build`
2. Build installer: `cd frontend && npm run pretauri:build && npm run tauri:build`
3. Verify logs and one full Dia2 generation.
