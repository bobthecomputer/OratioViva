# Journal de progression



Mise à jour après chaque session. Garder les entrées les plus récentes en haut.



Template rapide:

- Date: YYYY-MM-DD HH:MM (local)

- Fait:

- A faire:

- Blocages/risques:



## Entrées

### 2026-01-12 08:01

- Fait: ajout d'un lanceur desktop Python (backend/desktop_app.py) qui demarre FastAPI et ouvre automatiquement l'UI; generation d'une icone depuis le logo (assets/app.ico + favicon), scripts make_app/build_executable ajustes (entree desktop, icone, option Windowed), spec PyInstaller mise a jour.

- A faire: lancer make_app.ps1 pour valider le binaire et l'icone, tester la fermeture en mode Windowed, valider la synthese reelle avec les modeles telecharges.

- Blocages/risques: mode Windowed sans console => arret via gestionnaire de taches si la fenetre console est masquee; build PyInstaller non relance dans cette passe.

### 2026-01-11 22:12

- Fait: backend expose /models/status et /models/download (téléchargement en tâche de fond façon premier lancement), ModelManager avec détection models dir; frontend affiche un overlay de premier run et bouton d'installation des modèles; script unique `make_app.ps1` reste l'entrée principale; tests backend (pytest) et frontend (npm test/build) repassés OK.

- A faire: lancer réellement `scripts/make_app.ps1` pour valider le binaire + bundle des modèles, tester le provider local avec modèles téléchargés (`download_models.py` ou /models/download + ORATIO_TTS_PROVIDER=local et ORATIO_MODELS_DIR), traiter les vulnérabilités npm modérées si besoin.

- Blocages/risques: PyInstaller non lancé dans cette passe; synthèse réelle toujours non testée (torch/transformers non installés); vulnérabilités npm modérées signalées (npm audit).



### 2026-01-11 17:21

- Fait: ajouté logo (assets/logo.png) et affichage frontend; UI: section jobs (GET /jobs), bouton suppression job/historique, bouton download audio; nouvelles API DELETE /history/{id} et /jobs/{id}; .gitignore ignore *.npm et dossier; job store persistant déjà en place; .gitignore racine pour n’inclure que OratioViva/ dans le dépôt.

- A faire: exécuter tests, améliorer export (zip ou multi-téléchargement), design mobile/erreurs, ignorer bruits git globaux si besoin à la racine.

- Blocages/risques: dépôt git racine contient des fichiers hors projet (ex: *.npm); cleanup best-effort seulement.

### 2026-01-11 17:54

- Fait: installé dépendances backend dans `.venv`, exécuté `pytest` (2 tests OK en mode stub); corrigé tests pour chargement module backend via sys.path.

- A faire: export zip/multi-download, UI mobile/erreurs, suppression multiple jobs/historique, vérifier build frontend.

- Blocages/risques: job store persiste en JSON mais toujours en mémoire; dépendance HF pour audio réel.

### 2026-01-11 18:03

- Fait: ajouté export ZIP backend (`POST /export/zip`), collecte audio par job_ids; frontend: sélection multiple dans l’historique, bouton Export ZIP, suppression job/historique, section jobs mobile-friendly; CSS responsive ajustée; tests backend relancés (OK, stub).

- A faire: vérifier build frontend, ajouter multi-suppression/batch côté API si besoin, brancher modèles réels (lever `ORATIO_TTS_STUB`), peaufiner états d’erreur.

- Blocages/risques: pas d’erreurs connues; dépendance HF si non stub.

### 2026-01-11 18:03 (suite)

- Fait: batch delete API (`/jobs/batch_delete`, `/history/batch_delete`), front sélection multiple + suppression sélection pour jobs et historique; `npm install` frontend et `npm run build` OK.

- A faire: éventuellement tests UI (Vitest/RTL), intégration modèle local (sans Inference API), gestion multi-suppression côté UI plus avancée.

- Blocages/risques: synthèse réelle non testée (stub utilisé); pas de quotas si modèle local mais pipeline locale non branchée encore.

### 2026-01-11 18:25

- Fait: ajout mode TTS local optionnel (`ORATIO_TTS_PROVIDER=local`) avec pipeline transformers; docs mises à jour; tests UI (Vitest/RTL) ajoutés et passés; vitest config; batch delete front utilisable; npm install/build/test validés.

- A faire: brancher réellement Kokoro/Parler localement (installer torch/transformers/numpy), améliorer gestion d’erreurs UI.

- Blocages/risques: pipeline local dépend de deps lourdes (torch/transformers); audio réel non vérifié en local.

### 2026-01-11 17:14

- Fait: persistance des jobs dans `outputs/jobs.json` (limite 300), nouveau endpoint `GET /jobs`, compteur dans `/health`; doc backend mise à jour; script d’install PowerShell ajouté.

- A faire: UI pour lister/supprimer jobs/entrées d’historique, améliorer export (zip/download direct), tests à exécuter après install deps.

- Blocages/risques: dépôt git ancré dans le home montre des fichiers `.npm` hors projet (bruit); jobs toujours en mémoire mais reload depuis jobs.json, WAV purgés via cleanup.

### 2026-01-11 15:29

- Fait: créé frontend Vite/React (package.json, vite.config, index, App.jsx, styles, API helper) avec éditeur, picker de voix, slider vitesse, style prompt, bouton Générer (async_mode avec polling /jobs), affichage historique + player audio; doc frontend ajoutée; script d'installation rapide PowerShell ajouté (`scripts/setup.ps1`).

- A faire: tests API/UI, nettoyage périodique des WAV et persistance des jobs, ajuster design mobile si besoin.

- Blocages/risques: aucun côté frontend; dépendance backend/huggingface pour audio réel.

### 2026-01-11 17:08

- Fait: ajouté nettoyage startup et endpoint `/maintenance/cleanup` (paramétrable via env) pour purger WAV et tronquer l’historique; enrichi `/health` (compte d’items); ajouté tests API (httpx/pytest) en mode stub; ajouté dépendances dev; doc backend mise à jour.

- A faire: exécuter la suite de tests après installation deps; persister les jobs si redémarrage; peaufiner frontend mobile et états d’erreur.

- Blocages/risques: nettoyage simple (best effort); jobs toujours en mémoire uniquement.

### 2026-01-11 15:29

- Fait: créé frontend Vite/React (package.json, vite.config, index, App.jsx, styles, API helper) avec éditeur, picker de voix, slider vitesse, style prompt, bouton Générer (async_mode avec polling /jobs), affichage historique + player audio; doc frontend ajoutée.

- A faire: tests API/UI, nettoyage périodique des WAV et persistance des jobs, ajuster design mobile si besoin.

- Blocages/risques: aucun côté frontend; dépendance backend/huggingface pour audio réel.

### 2026-01-10 23:16

- Fait: ajouté gestion de jobs (queue en mémoire, statut `/jobs/{id}`, mode async optionnel via `async_mode`), réponse enrichie avec statut et job_id, branchement TTS sur le même job_id, doc backend mise à jour.

- A faire: nettoyage périodique des WAV/historique, gestion d’une file plus robuste si charge, amorcer frontend (Vite/React) avec éditeur/lecteur.

- Blocages/risques: jobs non persistés entre redémarrages; dépendance à l’Inference API tant que les modèles ne sont pas packagés localement.

### 2026-01-10 23:04

- Fait: ajouté service TTS (Hugging Face Inference Kokoro/Parler) avec fallback stub, montée en version API 0.2.0, nouvelles réponses enrichies, configuration env (`HF_TOKEN`, `ORATIO_TTS_STUB`), et doc backend nettoyée en ASCII.

- A faire: ajouter une file de tâches légère et statut de jobs, affiner la persistance (supprimer anciens WAV, limites), amorcer le frontend (Vite/React) avec éditeur et lecteur audio.

- Blocages/risques: dépendance à l’Inference API tant que les modèles ne sont pas packagés localement; vitesse/quotas à surveiller.

### 2026-01-10 22:54

- Fait: ajouté squelette backend FastAPI (`backend/main.py`) avec endpoints `/health`, `/voices`, `/synthesize`, `/history`, génération audio stub WAV + historique disque; ajouté `backend/requirements.txt` et README; mis à jour `.gitignore` pour `outputs/`.

- A faire: brancher vrais modèles Kokoro/Parler via `huggingface_hub`, gérer file d’attente et streaming, créer frontend (Vite/React) avec éditeur et lecteur, ajouter tests API.

- Blocages/risques: la synthèse est pour l’instant simulée (tone), prévoir téléchargement/chargement des modèles.

### 2026-01-10 21:16

- Fait: créé le squelette documentaire (`README.md`, `.gitignore`, `PROGRESS.md`) et posé la stack cible (FastAPI + React) avec priorisation Kokoro-82M v1.0 + option Parler-TTS Mini.

- A faire: initialiser `backend/` avec FastAPI, endpoints `/voices` et `/synthesize`, cache audio/disque; initialiser `frontend/` (Vite/React) avec pages éditeur + historique.

- Blocages/risques: aucun pour l’instant (repo vide).

