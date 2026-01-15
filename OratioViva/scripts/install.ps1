#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Script d'installation pour OratioViva - Gestionnaire TTS local
.DESCRIPTION
    Installe l'application OratioViva avec gestion automatique des dépendances Python
    et téléchargement des modèles TTS (Parler, Bark, SpeechT5, MMS, Kokoro)
.PARAMETER InstallDir
    Répertoire d'installation (défaut: $env:ProgramFiles\OratioViva)
.PARAMETER SkipModels
    Ne pas télécharger les modèles locaux
.PARAMETER UseNSIS
    Générer un installateur NSIS au lieu de copier directement
.PARAMETER PythonVersion
    Version de Python à utiliser (défaut: 3.12)
#>
param(
    [string]$InstallDir = "$env:ProgramFiles\OratioViva",
    [switch]$SkipModels,
    [switch]$UseNSIS,
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path $scriptRoot -Parent

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Installation OratioViva TTS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Test-Command {
    param([string]$Name)
    try { Get-Command $Name -ErrorAction Stop | Out-Null; return $true } catch { return $false }
}

Write-Host "[1/6] Vérification des prérequis..." -ForegroundColor Green

if (-not (Test-Command "uv")) {
    Write-Host "Installation de uv (gestionnaire Python moderne)..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -UseBasicParsing | Invoke-Expression
    $env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
}

if (-not (Test-Command "python")) {
    Write-Host "Installation de Python $PythonVersion..." -ForegroundColor Yellow
    if ($PythonVersion -eq "3.12") {
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe" -UseBasicParsing -OutFile "$env:TEMP\python-installer.exe"
        Start-Process -FilePath "$env:TEMP\python-installer.exe" -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
    } else {
        Write-Host "Python $PythonVersion doit être installé manuellement depuis python.org" -ForegroundColor Red
        exit 1
    }
}

Write-Host "[2/6] Création de l'environnement Python..." -ForegroundColor Green

$venvDir = Join-Path $InstallDir ".venv"
if (Test-Path $venvDir) {
    Write-Host "Suppression de l'ancien environnement..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvDir
}

uv venv $venvDir --python "python$PythonVersion"
& "$venvDir\Scripts\python.exe" -m pip install --upgrade pip

Write-Host "Installation des dépendances principales..." -ForegroundColor Green
uv pip install --python "$venvDir\Scripts\python.exe" -r "$repoRoot\backend\requirements.txt"

if (-not $SkipModels) {
    Write-Host "Installation des dépendances TTS locales..." -ForegroundColor Green
    uv pip install --python "$venvDir\Scripts\python.exe" -r "$repoRoot\backend\requirements-tts.txt"
}

Write-Host "[3/6] Préparation de l'application..." -ForegroundColor Green

$appDir = Join-Path $InstallDir "app"
New-Item -ItemType Directory -Path $appDir -Force | Out-Null

Copy-Item -Path "$repoRoot\backend\*.py" -Destination $appDir -Recurse
Copy-Item -Path "$repoRoot\backend\requirements*.txt" -Destination $appDir
Copy-Item -Path "$repoRoot\frontend\dist\*" -Destination $appDir -Recurse
Copy-Item -Path "$repoRoot\assets\app.ico" -Destination $appDir

if (-not $SkipModels) {
    Write-Host "[4/6] Téléchargement des modèles TTS..." -ForegroundColor Green
    $modelsDir = Join-Path $InstallDir "models"
    New-Item -ItemType Directory -Path $modelsDir -Force | Out-Null
    
    $modelTimer = [System.Diagnostics.Stopwatch]::StartNew()
    & "$venvDir\Scripts\python.exe" "$repoRoot\scripts\download_models.py" --dest $modelsDir
    $modelTimer.Stop()
    Write-Host ("Modèles prêts en {0:N1}s" -f $modelTimer.Elapsed.TotalSeconds) -ForegroundColor Green
}

Write-Host "[5/6] Configuration..." -ForegroundColor Green

$env:ORATIO_DATA_DIR = Join-Path $InstallDir "data"
$env:ORATIO_MODELS_DIR = Join-Path $InstallDir "models"
New-Item -ItemType Directory -Path $env:ORATIO_DATA_DIR -Force | Out-Null

$launcherContent = @"
@echo off
set ORATIO_DATA_DIR=$env:ORATIO_DATA_DIR
set ORATIO_MODELS_DIR=$env:ORATIO_MODELS_DIR
set ORATIO_TTS_PROVIDER=local
"%~dp0.python\python.exe" "%~dp0app\backend\desktop_app.py" %*
"@
$launcherContent | Out-File -FilePath (Join-Path $InstallDir "launcher.bat") -Encoding ASCII

if ($UseNSIS) {
    Write-Host "[6/6] Génération de l'installateur NSIS..." -ForegroundColor Green
    $nsisScript = @"
!include "MUI2.nsh"
Name "OratioViva"
OutFile "$repoRoot\dist\OratioViva-Setup.exe"
InstallDir `$INSTDIR
RequestExecutionLevel admin

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "French"

Section "Install"
    SetOutPath `$INSTDIR
    File /r "$InstallDir\*"
    CreateDirectory `$INSTDIR\data
    CreateDirectory `$INSTDIR\outputs
    CreateShortcut `$SMPROGRAMS\OratioViva.lnk `$INSTDIR\launcher.bat
    CreateShortcut `$DESKTOP\OratioViva.lnk `$INSTDIR\launcher.bat
SectionEnd
"@
    $nsisScript | Out-File -FilePath "$repoRoot\scripts\installer.nsi" -Encoding ASCII
    
    if (Test-Command "makensis") {
        makensis "$repoRoot\scripts\installer.nsi"
        Write-Host "Installateur créé: $repoRoot\dist\OratioViva-Setup.exe" -ForegroundColor Green
    } else {
        Write-Host "NSIS non installé. Génération du script uniquement." -ForegroundColor Yellow
        Write-Host "Installez NSIS depuis https://nsis.sourceforge.io pour créer l'installateur." -ForegroundColor Yellow
    }
} else {
    Write-Host "[6/6] Finalisation..." -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Installation terminée !" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pour lancer l'application:" -ForegroundColor White
Write-Host "  $InstallDir\launcher.bat" -ForegroundColor Yellow
Write-Host ""
Write-Host "Les modèles seront téléchargés au premier lancement." -ForegroundColor White
