# OratioViva (app desktop)

Studio texte-vers-voix local (Kokoro / Parler). Un seul binaire Windows qui lance le backend et le frontend dans la m\u00eame fen\u00eatre.

## Pr\u00e9requis
- Windows, Python 3.11+, Node 18+. (Pas d'autres scripts \u00e0 ex\u00e9cuter.)
- Pour un rendu vocal r\u00e9el : connexion internet le temps de t\u00e9l\u00e9charger les mod\u00e8les.

## Construire l'exe (unique)
```
cd OratioViva
.\scripts\make_app.ps1 -AppName OratioViva -Windowed
```
Ce script :
- cr\u00e9e `.venv`, installe les d\u00e9ps backend
- build le frontend
- t\u00e9l\u00e9charge les mod\u00e8les (Kokoro + Parler) et les embarque
- g\u00e9n\u00e8re `dist\OratioViva.exe` avec l'ic\u00f4ne

## Lancer
```
.\dist\OratioViva.exe
```
- La fen\u00eatre s'ouvre, backend d\u00e9j\u00e0 lanc\u00e9. Les donn\u00e9es sont dans `data\` (modifier via `ORATIO_DATA_DIR` avant de lancer l'exe).
- Au premier lancement, l'appli t\u00e9l\u00e9charge les mod\u00e8les si besoin. L'\u00e9tiquette "Modeles a installer" passe en "Mode local" quand tout est pr\u00eat. En mode "stub" vous n'entendrez qu'un bip.

## Contr\u00f4les dans l'UI
- Voix Kokoro/Parler, vitesse, style (prompt Parler).
- Historique, lecture, t\u00e9l\u00e9chargement, export ZIP, suppression et gestion des jobs.
- Badge d'\u00e9tat mod\u00e8les/provider + avertissement si mode stub.

## D\u00e9veloppement (optionnel)
- Backend local : `.\backend\.venv\Scripts\uvicorn backend.main:app --reload`
- Frontend dev : `cd frontend && npm run dev` (utilise `VITE_API_BASE`)
- Tests backend : `.\backend\.venv\Scripts\pytest -q`
- Tests frontend : `cd frontend && npm test && npm run build`

## Points techniques
- Provider auto : s'il trouve des mod\u00e8les locaux -> local; sinon token HF -> inference; sinon stub (bip).
- Mod\u00e8les bundl\u00e9s via `scripts\make_app.ps1` (utilise `scripts\download_models.py`).
- Outputs : `data\outputs\audio` + `history.json` (ignor\u00e9s par git).

