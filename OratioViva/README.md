# OratioViva — Application texte vers voix

Application prévue pour transformer des articles (ex. threads Twitter) en audio agréable à écouter, avec un parcours simple, esthétique et pilotable via deux modèles TTS légers.

## Objectifs
- Coller ou importer du texte puis générer de l’audio en quelques clics.
- Choisir un modèle (priorité Kokoro-82M v1.0; option Parler-TTS Mini v1.1), une voix et des réglages (débit, pitch/émotion si disponible).
- Prévisualiser, télécharger et organiser les sorties (historique, favoris, tags).
- Garder un log de progression clair pour suivre l’avancement.

## Pile technique proposée
- **Backend**: Python 3.11+, FastAPI, `pydantic`, `uvicorn`. Gestion de files et cache disque pour réutiliser les échantillons audio.
- **TTS**: modèle par défaut Kokoro-82M v1.0 (Apache-2.0); option Parler-TTS Mini v1.1 si l’on veut plus de contrôles de style. Téléchargement/chargement via `huggingface_hub` (mode offline possible après warmup).
- **Frontend**: Vite + React + Tailwind (ou CSS maison) pour un studio clair: zone de texte, contrôle du débit/pitch, choix voix, timeline d’exports, lecteur intégré.
- **Stockage**: fichiers audio en `outputs/audio/` (hash du texte + voix); métadonnées locales en `outputs/history.json` ou petite base SQLite si besoin.

## Structure de repo (proposée)
- `backend/`: API FastAPI (`/synthesize`, `/voices`, `/history`, `/health`). Inclure un cache de modèles et une file de tâches légère.
- `frontend/`: app React (Vite) avec pages: éditeur, historique, préférences modèles.
- `assets/`: éventuels prompts/voix d’exemple.
- `scripts/`: tâches utilitaires (pré-chargement modèle, nettoyage cache).
- `outputs/`: audio généré et métadonnées (ignorés par git).

## Roadmap minimale
1) **Bootstrap backend**: dépendances, endpoints `/voices` (liste voix + langues), `/synthesize` (mode async, retourne URL locale), gestion du cache modèle, stockage audio disque.
2) **Bootstrap frontend**: pages éditeur + historique, sélection modèle/voix, lecteur audio et bouton download.
3) **Qualité**: gestion erreurs/timeout, validation d’entrée, quotas de taille, tests API (pytest + httpx).
4) **UX finale**: thème soigné, onboarding rapide, presets de voix (news, narrateur, conversation), indicateurs de progression de rendu.

## Progress log
Mise à jour après chaque session dans `PROGRESS.md`:
- Ajouter un bloc daté (UTC locale) avec: ce qui a été fait, restes à faire, blocages.
- Garder les entrées les plus récentes en haut.
- Exemple:
  - Date: 2026-01-10 21:16
  - Fait: ...
  - À faire: ...
  - Blocages/risques: ...

## Démarrage (brouillon)
Backend:
```
python -m venv .venv
.venv\\Scripts\\activate
pip install fastapi uvicorn[standard] pydantic transformers huggingface_hub
uvicorn backend.main:app --reload
```
Frontend (quand le dossier existera):
```
cd frontend
npm install
npm run dev
```

### Installation rapide (PowerShell)
```
.\scripts\setup.ps1
# ou sans frontend :
.\scripts\setup.ps1 -SkipFrontend
```

## Notes modèles
- Kokoro-82M v1.0: rapide, léger, multi-voix (EN/JP/ES/FR/Hindi/IT/PT-BR). Recommandé pour narration générale.
- Parler-TTS Mini v1.1: permet des descriptions de style (débit, expressivité) + 34 locuteurs. Multilingue Mini v1.1 si priorité aux langues européennes.
