# Frontend (Vite + React)

Interface pour OratioViva: éditeur de texte, choix de voix, génération TTS avec polling de jobs et historique avec lecteur audio.

## Pré-requis
- Node 18+
- Backend lancé sur `http://localhost:8000` (modifiable via `VITE_API_BASE`)

## Installation
```
cd frontend
npm install
```

## Développement
```
npm run dev
# ouvre http://localhost:5173
```

## Build
```
npm run build
npm run preview
```

## Config
- Créer un fichier `.env` (optionnel):
```
VITE_API_BASE=http://localhost:8000
```

## Notes UI
- Soumission utilise `async_mode=true` côté API puis poll `/jobs/{id}`.
- Historique et lecteur audio consomment `/history` et servent les WAV via `/audio/...`.
- Sélection multiple + Export ZIP (appelle `/export/zip`), suppression job/historique (batch delete).
