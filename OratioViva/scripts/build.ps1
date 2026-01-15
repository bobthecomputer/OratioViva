#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Script de construction complet pour OratioViva avec installateur NSIS
.DESCRIPTION
    Construit l'application et génère un installateur Windows (.exe)
    avec gestion automatique des dépendances et modèles.
.PARAMETER AppName
    Nom de l'application (défaut: OratioViva)
.PARAMETER PythonVersion
    Version de Python (défaut: 3.12)
.PARAMETER SkipFrontend
    Ne pas reconstruire le frontend
.PARAMETER SkipModels
    Ne pas inclure les modèles dans l'installateur
.PARAMETER BuildNSIS
    Générer l'installateur NSIS (requiert NSIS installé)
.PARAMETER OneDir
    Mode onedir au lieu de onefile (pour éviter les limites de taille)
#>
param(
    [string]$AppName = "OratioViva",
    [string]$PythonVersion = "3.12",
    [switch]$SkipFrontend,
    [switch]$SkipModels,
    [switch]$BuildNSIS,
    [switch]$OneDir
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path $scriptRoot -Parent
Push-Location $repoRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Construction OratioViva TTS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Test-Command {
    param([string]$Name)
    try { Get-Command $Name -ErrorAction Stop | Out-Null; return $true } catch { return $false }
}

function Install-Uv {
    if (-not (Test-Command "uv")) {
        Write-Host "Installation de uv (gestionnaire Python moderne)..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -UseBasicParsing | Invoke-Expression
        $env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
    }
    Write-Host "  uv installé: $(uv --version)" -ForegroundColor Green
}

function New-PythonVenv {
    param([string]$Path, [string]$Version)
    if (Test-Path $Path) {
        Write-Host "Environnement existant trouvé: $Path" -ForegroundColor Yellow
        return
    }
    Write-Host "Création de l'environnement Python $Version..." -ForegroundColor Green
    uv venv $Path --python "python$Version"
}

function Install-Deps {
    param([string]$VenvPath, [string]$Requirements)
    Write-Host "Installation des dépendances: $Requirements" -ForegroundColor Green
    uv pip install --python "$VenvPath\Scripts\python.exe" -r $Requirements
}

function Build-Frontend {
    if ($SkipFrontend) {
        Write-Host "Frontend ignoré (SkipFrontend)" -ForegroundColor Yellow
        return
    }
    Write-Host "Construction du frontend..." -ForegroundColor Green
    Push-Location "frontend"
    npm ci
    npm run build
    Pop-Location
}

function Download-Models {
    param([string]$Dest, [string]$VenvPath)
    if ($SkipModels) {
        Write-Host "Modèles ignorés (SkipModels)" -ForegroundColor Yellow
        return
    }
    Write-Host "Téléchargement des modèles TTS..." -ForegroundColor Green
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    & "$VenvPath\Scripts\python.exe" "$repoRoot\scripts\download_models.py" --dest $Dest
    $timer.Stop()
    Write-Host "Modèles prêts en $($timer.Elapsed.TotalSeconds.ToString('N1'))s" -ForegroundColor Green
}

function New-PyInstallerBuild {
    param(
        [string]$AppName,
        [string]$VenvPath,
        [string]$FrontendDist,
        [string]$ModelsPath,
        [string]$IconPath,
        [switch]$OneDir
    )
    Write-Host "Construction PyInstaller..." -ForegroundColor Green
    
    $pyinstallerArgs = @(
        "--noconfirm",
        "--clean",
        "--name", $AppName,
        "backend\desktop_app.py"
    )
    
    if (-not $OneDir) {
        $pyinstallerArgs += "--onefile"
    } else {
        $pyinstallerArgs += "--onedir"
    }
    
    if ($Windowed) {
        $pyinstallerArgs += "--noconsole"
    }
    
    if (Test-Path $FrontendDist) {
        $pyinstallerArgs += @("--add-data", "$FrontendDist;frontend/dist")
        Write-Host "  Frontend: $FrontendDist" -ForegroundColor Green
    }
    
    if ($ModelsPath -and (Test-Path $ModelsPath) -and (-not $SkipModels)) {
        $pyinstallerArgs += @("--add-data", "$ModelsPath;models")
        Write-Host "  Modèles: $ModelsPath" -ForegroundColor Green
    }
    
    if (Test-Path $IconPath) {
        $pyinstallerArgs += @("--icon", $IconPath)
        Write-Host "  Icône: $IconPath" -ForegroundColor Green
    }
    
    & "$VenvPath\Scripts\pyinstaller.exe" @pyinstallerArgs
}

function New-NSISInstaller {
    param(
        [string]$AppName,
        [string]$SourceDir,
        [string]$OutputPath
    )
    if (-not (Test-Command "makensis")) {
        Write-Host "NSIS non installé. Installation..." -ForegroundColor Yellow
        Write-Host "Télécharger depuis: https://nsis.sourceforge.io/Download" -ForegroundColor Yellow
        return $false
    }
    
    Write-Host "Génération de l'installateur NSIS..." -ForegroundColor Green
    makensis /DAPP_NAME="$AppName" /DSOURCE_DIR="$SourceDir" /DOUTPUT_PATH="$OutputPath" "$repoRoot\scripts\installer.nsi"
    return $true
}

# === EXÉCUTION ===
Write-Host "[1/6] Vérification de uv..." -ForegroundColor Green
Install-Uv

Write-Host "[2/6] Environnement Python..." -ForegroundColor Green
$venvPath = "$repoRoot\backend\.venv"
New-PythonVenv -Path $venvPath -Version $PythonVersion

Write-Host "[3/6] Installation des dépendances..." -ForegroundColor Green
Install-Deps -VenvPath $venvPath -Requirements "$repoRoot\backend\requirements.txt"
Install-Deps -VenvPath $venvPath -Requirements "$repoRoot\backend\requirements-tts.txt"

Write-Host "[4/6] Frontend..." -ForegroundColor Green
Build-Frontend

Write-Host "[5/6] Modèles..." -ForegroundColor Green
$modelsPath = "$repoRoot\models"
Download-Models -Dest $modelsPath -VenvPath $venvPath

Write-Host "[6/6] Construction..." -ForegroundColor Green
$frontendDist = "$repoRoot\frontend\dist"
$iconPath = "$repoRoot\assets\app.ico"
$outputExe = "$repoRoot\dist\$AppName.exe"
$installerExe = "$repoRoot\dist\OratioViva-Setup.exe"

New-PyInstallerBuild -AppName $AppName -VenvPath $venvPath -FrontendDist $frontendDist -ModelsPath $modelsPath -IconPath $iconPath -OneDir:$OneDir

if ($BuildNSIS) {
    New-NSISInstaller -AppName $AppName -SourceDir $repoRoot -OutputPath $installerExe
}

Pop-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Construction terminée !" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Exécutable: $outputExe" -ForegroundColor Green
if (Test-Path $installerExe) {
    Write-Host "Installateur: $installerExe" -ForegroundColor Green
}
Write-Host ""
Write-Host "Pour tester:" -ForegroundColor White
Write-Host "  $outputExe" -ForegroundColor Yellow
