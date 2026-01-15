@echo off
REM OratioViva TTS Launcher
REM Ce script configure l'environnement et lance l'application

set SCRIPT_DIR=%~dp0
set PYTHON_DIR=%SCRIPT_DIR%.python

REM Configuration de l'environnement
set ORATIO_DATA_DIR=%SCRIPT_DIR%data
set ORATIO_MODELS_DIR=%SCRIPT_DIR%models
set ORATIO_TTS_PROVIDER=local
set ORATIO_FRONTEND_DIR=%SCRIPT_DIR%app\frontend\dist

REM Création des dossiers si nécessaires
if not exist "%ORATIO_DATA_DIR%" mkdir "%ORATIO_DATA_DIR%"
if not exist "%ORATIO_DATA_DIR%\outputs" mkdir "%ORATIO_DATA_DIR%\outputs"
if not exist "%ORATIO_DATA_DIR%\outputs\audio" mkdir "%ORATIO_DATA_DIR%\audio"

REM Détection de Python
if exist "%PYTHON_DIR%\python.exe" (
    "%PYTHON_DIR%\python.exe" "%SCRIPT_DIR%app\backend\desktop_app.py" %*
) else if exist "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" (
    "%SCRIPT_DIR%backend\.venv\Scripts\python.exe" "%SCRIPT_DIR%app\backend\desktop_app.py" %*
) else if exist "python.exe" (
    python.exe "%SCRIPT_DIR%app\backend\desktop_app.py" %*
) else (
    echo Erreur: Python non trouvé
    echo.
    echo Veuillez installer Python 3.11+ depuis https://python.org
    pause
    exit /b 1
)
