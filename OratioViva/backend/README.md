# Backend FastAPI (OratioViva)

API TTS avec FastAPI. Provider auto: local si des modeles sont presents, sinon Hugging Face Inference si `HF_TOKEN` est defini, sinon stub (bip). Local par defaut: Parler-TTS mini, Bark Small, SpeechT5 + HiFiGAN, MMS TTS; Kokoro reste via Inference en Python 3.13.

## Installation
```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
Deps TTS locales (torch/transformers/parler-tts/bark/speecht5/mms):
```
pip install -r requirements-tts.txt
```

## Variables d'environnement
- `HF_TOKEN` ou `HUGGINGFACEHUB_API_TOKEN`: token Hugging Face recommande pour l'Inference API.
- `ORATIO_TTS_STUB=1`: force le mode stub (aucun appel modele).
- `ORATIO_CLEAN_MAX_HOURS` (defaut 48): age max des WAV avant purge au startup/cleanup.
- `ORATIO_CLEAN_MAX_HISTORY` (defaut 200): nombre max d'entrees conservees dans `history.json`.
- `ORATIO_JOBS_MAX` (defaut 300, via code): jobs conserves dans `outputs/jobs.json`.
- `ORATIO_TTS_PROVIDER` (`auto` | `local` | `inference` | `stub`): choisir la source TTS. `auto` priorise local si un modele supporte le mode local, sinon inference (token HF), sinon stub. `local` attend transformers+numpy+torch installes.
- `ORATIO_DATA_DIR`: force le dossier racine des outputs (`outputs/`). Quand l'app est packegee (PyInstaller), le cwd est utilise par defaut.
- `ORATIO_FRONTEND_DIR`: chemin vers un dossier static (ex: `frontend/dist`) servi sur `/app` (sinon auto-detection du bundle PyInstaller).
- `ORATIO_MODELS_DIR`: chemin vers des modeles telecharges localement (structure `hexgrad_Kokoro-82M`, `parler-tts_parler-tts-mini-v1.1`, `facebook_mms-tts-eng`, etc.). `_MEIPASS/models` est auto-detecte si present.
- `ORATIO_OPTIONAL_MODELS`: liste d'alias separes par des virgules a ne pas rendre obligatoires ni a telecharger par defaut (`kokoro` par defaut, pratique si vous ne voulez pas Kokoro). Retirez-les pour forcer le telechargement.

## Demarrer l'API
```
uvicorn backend.main:app --reload
```

## Endpoints
- `GET /health`
- `GET /voices`
- `POST /synthesize?async_mode=false` body: `text`, `voice_id`, `speed`, `style`
- `GET /jobs/{job_id}`
- `GET /jobs?limit=50`
- `DELETE /jobs/{job_id}`
- `POST /jobs/batch_delete`
- `GET /history?limit=20`
- `DELETE /history/{job_id}`
- `POST /history/batch_delete`
- `POST /maintenance/cleanup`
- `POST /export/zip`
- `GET /models/status` / `POST /models/download`
- `GET /analytics` (provider, modeles disponibles, metriques jobs/audio)

Les fichiers sont ecrits dans `outputs/audio/` et listes dans `outputs/history.json` (ignores par git).

## Job store (memoire)
- Jobs gardes en memoire et persistes dans `outputs/jobs.json` (limite 300 par defaut).
- Si l'API redemarre, les statuts sont recharges depuis `jobs.json` (les WAV anciens peuvent etre purges selon la config cleanup).
- Pour un stockage plus robuste, on pourra remplacer par SQLite/Redis plus tard.

## Mode TTS local (hors Inference API)
- Passer `ORATIO_TTS_PROVIDER=local` pour activer le pipeline local.
- Installer les deps : `pip install -r requirements-tts.txt`.
- Modeles par defaut: `parler-tts/parler-tts-mini-v1.1`, `suno/bark-small`, `microsoft/speecht5_tts` + `microsoft/speecht5_hifigan`, `facebook/mms-tts-eng`. Kokoro local indisponible sous Python 3.13 faute de package compatible.
- Si les deps manquent, le service retombe sur le stub si `fallback_stub=True`.

## Packaging / offline
- Commande unique (deps, frontend build, modeles, exe) : `..\scripts\make_app.ps1`.
- Switch `-OneDir` recommande si le mode onefile PyInstaller depasse 4GB; `-SkipModels` evite de les embarquer.
- Telecharger les modeles: `python scripts\download_models.py --dest models` (utilise `HF_TOKEN`).
- Le frontend build (`frontend/dist`) est servi sur `/app` (detecte aussi depuis un bundle PyInstaller).

## Premier lancement / telechargements de modeles
- Endpoint `GET /models/status`: indique si les modeles par defaut sont presents.
- Endpoint `POST /models/download`: declenche le telechargement en tache de fond (identique au script `scripts/download_models.py`).
