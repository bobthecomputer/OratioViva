Param(
    [string]$AppName = "OratioViva",
    [switch]$SkipFrontend = $false,
    [switch]$SkipModels = $false,
    [string]$ModelsDest = "models",
    [string]$DataDir = "data",
    [string]$IconPath = "assets/app.ico",
    [string]$Entrypoint = "backend\desktop_app.py",
    [switch]$Windowed = $true,
    [switch]$OneDir = $false
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path $scriptRoot -Parent
Push-Location $repoRoot

Write-Host "== OratioViva build (one-shot) ==" -ForegroundColor Cyan
Write-Host "Fenetre uniquement. Le binaire lance backend + frontend automatiquement." -ForegroundColor Yellow

# Backend: venv + deps + pyinstaller
Push-Location "backend"
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtualenv..." -ForegroundColor Green
    python -m venv .venv
}
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
if (-not $SkipModels) {
    Write-Host "Installing local TTS deps (torch/torchaudio/transformers/parler-tts)..." -ForegroundColor Green
    & $python -m pip install -r requirements-tts.txt
} else {
    Write-Host "Skipping local TTS deps (SkipModels set)" -ForegroundColor Yellow
}
& $python -m pip install pyinstaller
Pop-Location

# Frontend build
if (-not $SkipFrontend) {
    Push-Location "frontend"
    Write-Host "Installing frontend deps (npm ci)..." -ForegroundColor Green
    npm ci
    Write-Host "Building frontend..." -ForegroundColor Green
    npm run build
    Pop-Location
} else {
    Write-Host "Skipping frontend build (SkipFrontend set)" -ForegroundColor Yellow
}

# Optional model download
$modelsPath = $null
if (-not $SkipModels) {
    Write-Host "Downloading models to $ModelsDest (peut prendre 1-3 minutes)..." -ForegroundColor Green
    $modelTimer = [System.Diagnostics.Stopwatch]::StartNew()
    & ".\backend\.venv\Scripts\python.exe" ".\scripts\download_models.py" --dest $ModelsDest
    $modelTimer.Stop()
    Write-Host ("Models ready in {0:N1}s" -f $modelTimer.Elapsed.TotalSeconds) -ForegroundColor Green
    $modelsPath = (Resolve-Path $ModelsDest).Path
} elseif (Test-Path $ModelsDest) {
    $modelsPath = (Resolve-Path $ModelsDest).Path
    Write-Host "Using existing models at $modelsPath" -ForegroundColor Green
} else {
    Write-Host "No models bundled (SkipModels set and none found)" -ForegroundColor Yellow
}

# Resolve data dir (where outputs will be written when running the EXE)
$dataPath = $null
try {
    $dataPath = (Resolve-Path $DataDir).Path
} catch {
    $dataPath = (New-Item -ItemType Directory -Path $DataDir -Force).FullName
}
$env:ORATIO_DATA_DIR = $dataPath

# Build executable (bundles frontend/dist + models if present)
$buildModeArg = "--onefile"
if ($OneDir) {
    $buildModeArg = "--onedir"
    Write-Host "Using onedir mode to avoid oversized onefile archives." -ForegroundColor Yellow
} else {
    Write-Host "Using onefile mode (may fail if archive exceeds 4GB; use -OneDir to switch)." -ForegroundColor Yellow
}
$pyinstallerArgs = @(
    "--noconfirm",
    "--clean",
    $buildModeArg,
    "--name", $AppName,
    $Entrypoint
)
if ($Windowed) {
    $pyinstallerArgs += "--noconsole"
    Write-Host "Building in windowed mode (no console)" -ForegroundColor Green
} else {
    Write-Host "Building with console (close window to quit)" -ForegroundColor Green
}
$frontendDist = Join-Path $repoRoot "frontend\dist"
if (Test-Path $frontendDist) {
    $distResolved = (Resolve-Path $frontendDist).Path
    $pyinstallerArgs += @("--add-data", "$distResolved;frontend/dist")
    Write-Host "Bundling frontend dist from $distResolved" -ForegroundColor Green
} else {
    Write-Host "Frontend dist not found; skipping bundle (path: $frontendDist)" -ForegroundColor Yellow
}
if ($modelsPath) {
    $pyinstallerArgs += @("--add-data", "$modelsPath;models")
    Write-Host "Bundling models from $modelsPath" -ForegroundColor Green
}
$iconResolved = $null
if (Test-Path $IconPath) {
    $iconResolved = (Resolve-Path $IconPath).Path
    $pyinstallerArgs += @("--icon", $iconResolved)
    Write-Host "Using icon $iconResolved" -ForegroundColor Green
} else {
    Write-Host "Icon not found at $IconPath (skipping)" -ForegroundColor Yellow
}

Write-Host "Running PyInstaller..." -ForegroundColor Green
& ".\backend\.venv\Scripts\pyinstaller.exe" @pyinstallerArgs

Pop-Location
Write-Host "== Done. Executable in dist\$AppName.exe ==" -ForegroundColor Cyan
Write-Host "Outputs will be stored under $dataPath (ORATIO_DATA_DIR)." -ForegroundColor Cyan
