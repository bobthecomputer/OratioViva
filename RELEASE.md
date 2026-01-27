# OratioViva Release Guide

This guide covers the minimum steps to cut a Windows desktop release.

## 1. Versioning

Update version numbers in these locations:
- `frontend/src-tauri/tauri.conf.json` (app installer version)
- `frontend/package.json` (frontend package version)
- `backend/main.py` (FastAPI app version, if you version the API)

If you update `frontend/package.json`, keep `frontend/package-lock.json` in sync
by running `npm install` (or `npm ci` + `npm install` if needed).

## 2. QA checklist

Run through the pre-release checklist:
- `QA_CHECKLIST.md`

## 3. Build the installer

```bash
cd frontend
npm run build
npm run pretauri:build
npm run tauri:build
```

The NSIS installer is produced under:
`frontend/src-tauri/target/release/bundle/nsis/`

## 4. Smoke test

On a clean Windows VM:
- Install the new build
- Launch the app and verify backend starts
- Generate one Dia2 sample
- Confirm audio playback and exports

## 5. Release notes (template)

```
# OratioViva vX.Y.Z

## Highlights
- ...

## Improvements
- ...

## Fixes
- ...

## Known issues
- ...
```

