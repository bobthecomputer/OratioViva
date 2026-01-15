# Installation d'OratioViva

## Prérequis
- Windows 10/11
- Python 3.11 ou 3.12 (https://python.org/downloads)
- Node.js 18+ (pour construire le frontend, optionnel)

## Installation rapide

### Option 1: Utiliser l'existant (déjà construit)

L'application est déjà prête dans `dist\OratioViva.exe`.

```powershell
.\dist\OratioViva.exe
```

### Option 2: Reconstruire avec le script

```powershell
.\scripts\build.ps1 -BuildNSIS
```

Cela génère:
- `dist\OratioViva.exe` - Exécutable standalone
- `dist\OratioViva-Setup.exe` - Installateur Windows (si NSIS installé)

### Option 3: Installation manuelle

```powershell
# Créer l'environnement Python
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-tts.txt

# Construire le frontend (optionnel)
cd ..\frontend
npm ci
npm run build

# Lancer l'application
cd ..
.venv\Scripts\python backend\desktop_app.py
```

## Utilisation

1. Lancez `OratioViva.exe`
2. L'application télécharge automatiquement les modèles au premier lancement
3. Sélectionnez une voix (Parler, Bark, SpeechT5, MMS)
4. Entrez votre texte et cliquez sur "Synthétiser"

## Dépannage

### "Python non trouvé"
Installez Python depuis https://python.org/downloads (cochez "Add Python to PATH")

### Modèle manquant
Les modèles sont téléchargés automatiquement. Si un modèle échoue:
```powershell
python scripts\download_models.py --dest models
```

### Erreur de mémoire
Les modèles sont configurés pour utiliser le CPU. Pour les GPU, modifiez `backend/tts.py`.

### Les modèles Parler/Bark ne fonctionnent pas
Vérifiez que les dépendances sont installées:
```powershell
.venv\Scripts\pip install torch torchaudio transformers parler-tts
```

## Fichiers générés

- `data/` - Données utilisateur (historique, audio)
- `models/` - Modèles TTS téléchargés
- `outputs/` - Fichiers audio générés
