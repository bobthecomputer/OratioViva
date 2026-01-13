# OratioViva (desktop app)

Studio texte-vers-voix local (Parler, Bark, SpeechT5, MMS) avec Kokoro via HF Inference si besoin. Un seul binaire Windows ouvre backend + frontend dans la meme fenetre.

## Prerequis
- Windows, Python 3.11+, Node 18+.
- Connexion internet pour telecharger les modeles la premiere fois (ensuite offline).

## Construire l'exe
```
cd OratioViva
.\scripts\make_app.ps1 -AppName OratioViva -Windowed
```
Options utiles : `-SkipModels` pour ne pas embarquer les modeles, `-OneDir` si PyInstaller onefile depasse 4GB.

Ce script :
- cree `.venv`, installe les deps backend
- build le frontend
- telecharge les modeles locaux (Kokoro, Parler, Bark Small, SpeechT5 + vocoder, MMS TTS) et les embarque
- genere `dist\OratioViva.exe` (ou un dossier si `-OneDir`) avec l'icone

## Lancer
```
.\dist\OratioViva.exe
```
- Fenetre unique, backend deja lance. Les donnees sont dans `data\` (changer via `ORATIO_DATA_DIR` avant de lancer l'exe).
- Au premier lancement, l'appli telecharge les modeles si besoin. L'etiquette "Modeles a installer" passe en "Mode local" quand tout est pret. En mode "stub" vous n'entendrez qu'un bip.

## Controles dans l'UI
- Voix Parler/Bark/SpeechT5/MMS/Kokoro, vitesse, style (prompt Parler).
- Historique, lecture, telechargement, export ZIP, suppression et gestion des jobs.
- Onglet Analytics (provider local/inference/stub, modeles presents, metriques audio, derniers jobs).
- Badge d'etat modeles/provider + avertissement si mode stub.

## Developpement (optionnel)
- Backend local : `.\backend\.venv\Scripts\uvicorn backend.main:app --reload`
- Deps TTS locales : `pip install -r backend\requirements-tts.txt` (Parler, Bark Small, SpeechT5 + vocoder, MMS). Kokoro reste via HF Inference en Python 3.13.
- Frontend dev : `cd frontend && npm run dev` (utilise `VITE_API_BASE`)
- Tests backend : `.\backend\.venv\Scripts\pytest -q`
- Tests frontend : `cd frontend && npm test && npm run build`

## Points techniques
- Provider auto : si modeles locaux presents -> local; sinon token HF -> inference; sinon stub (bip).
- Modeles bundles via `scripts\make_app.ps1` (utilise `scripts\download_models.py`).
- Outputs : `data\outputs\audio` + `history.json` (ignores par git).
