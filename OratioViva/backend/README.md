# Backend FastAPI (OratioViva)

API TTS avec FastAPI. Par defaut, la synthese passe par Hugging Face Inference (Kokoro-82M, option Parler-TTS Mini v1.1). Un mode stub (tone WAV) est disponible pour tester sans modele.

## Installation
```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Variables d'environnement
- `HF_TOKEN` ou `HUGGINGFACEHUB_API_TOKEN`: token Hugging Face recommande pour l'Inference API.
- `ORATIO_TTS_STUB=1`: force le mode stub (aucun appel modele).
- `ORATIO_CLEAN_MAX_HOURS` (defaut 48): age max des WAV avant purge au startup/cleanup.
- `ORATIO_CLEAN_MAX_HISTORY` (defaut 200): nombre max d'entrees conservees dans `history.json`.
- `ORATIO_JOBS_MAX` (defaut 300, via code): jobs conserves dans `outputs/jobs.json`.
- `ORATIO_TTS_PROVIDER` (`inference` | `local` | `stub`): choisir la source TTS. `local` attend transformers+numpy (+ torch) installes.
- `ORATIO_DATA_DIR`: force le dossier racine des outputs (`outputs/`). Quand l'app est packagée (PyInstaller), le cwd est utilisé par défaut.
- `ORATIO_FRONTEND_DIR`: chemin vers un dossier static (ex: `frontend/dist`) qui sera servi sur `/app` (sinon auto-détection du bundle PyInstaller).
- `ORATIO_MODELS_DIR`: chemin vers des modèles téléchargés localement (structure `hexgrad_Kokoro-82M`, `parler-tts_parler-tts-mini-v1.1`). Quand packagée, `_MEIPASS/models` est auto-détecté si présent.

## Demarrer l'API
```
uvicorn backend.main:app --reload
```

## Endpoints
- `GET /health`
- `GET /voices`
- `POST /synthesize?async_mode=false` body:
  - `text` (str, obligatoire)
  - `voice_id` (str, repertorie via `/voices`)
  - `speed` (0.5-2.0)
  - `style` (optionnel, prevu pour Parler)
- `GET /jobs/{job_id}`: statut d'un job (queued, running, succeeded, failed)
- `GET /jobs?limit=50`: liste des jobs recents (persistes dans `outputs/jobs.json`)
- `DELETE /jobs/{job_id}`: retire un job du store (ne touche pas l'audio/historique)
- `POST /jobs/batch_delete` body `{ "job_ids": [] }`
- `GET /history?limit=20`
- `DELETE /history/{job_id}`: supprime l'entree et le fichier audio associe si present
- `POST /history/batch_delete` body `{ "job_ids": [], "delete_audio": true }`
- `POST /maintenance/cleanup`: purge les vieux WAV et tronque l'historique (selon env ci-dessus)
- `POST /export/zip`: body `{ "job_ids": ["..."] }` -> renvoie un zip des WAV correspondants

Les fichiers sont ecrits dans `outputs/audio/` et listes dans `outputs/history.json` (ignores par git).

## Job store (memoire)
- Jobs gardes en memoire et persistés dans `outputs/jobs.json` (limite 300 par defaut).
- Si l'API redemarre, les statuts sont recharges depuis `jobs.json` (les WAV anciens peuvent etre purges selon la config cleanup).
- Pour un stockage plus robuste, on pourra remplacer par SQLite/Redis plus tard.

## Mode TTS local (hors Inference API)
- Passer `ORATIO_TTS_PROVIDER=local` pour activer le pipeline local.
- Installer les deps (exemple) :
  ```
  pip install torch transformers numpy
  ```
- Modeles par defaut: `hexgrad/Kokoro-82M` et `parler-tts/parler-tts-mini-v1.1` via transformers `pipeline("text-to-speech")`.
- Si les deps manquent, le service retombe sur le stub si `fallback_stub=True`.

## Packaging / offline
- Commande unique (deps, frontend build, modèles, exe onefile) : `.\scripts\make_app.ps1`
- T‚l‚charger les modŠles (offline) : `python scripts\download_models.py --dest models` (utilise `HF_TOKEN`).
- Servir le frontend build‚ si `frontend/dist` existe ou via `ORATIO_FRONTEND_DIR`; accessible sur `/app` (d‚tection aussi depuis un bundle PyInstaller).

## Premier lancement / téléchargements de modèles
- Endpoint `GET /models/status`: indique si les modèles par défaut sont présents.
- Endpoint `POST /models/download`: déclenche le téléchargement en tâche de fond (identique au script `scripts/download_models.py`), pour un onboarding "premier run" côté frontend.
