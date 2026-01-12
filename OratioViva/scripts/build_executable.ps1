Param(
    [string]$ExeName = "oratioviva-api",
    [switch]$SkipFrontendBuild = $false,
    [switch]$DownloadModels = $false,
    [string]$ModelsDest = "models",
    [string]$DataDir = ".",
    [string]$IconPath = "assets/app.ico",
    [string]$Entrypoint = "backend\desktop_app.py",
    [switch]$Windowed = $false
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path $scriptRoot -Parent

Write-Host "== Packaging OratioViva ==" -ForegroundColor Cyan
Push-Location $repoRoot

# Backend env
Push-Location "backend"
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtualenv..." -ForegroundColor Green
    python -m venv .venv
}
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
& $python -m pip install pyinstaller
Pop-Location

# Frontend build (optional)
if (-not $SkipFrontendBuild) {
    Push-Location "frontend"
    Write-Host "Building frontend (npm install + npm run build)..." -ForegroundColor Green
    npm install
    npm run build
    Pop-Location
} else {
    Write-Host "Skipping frontend build (SkipFrontendBuild set)" -ForegroundColor Yellow
}

# Optional model download for offline/local provider
if ($DownloadModels) {
    Write-Host "Downloading models to $ModelsDest" -ForegroundColor Green
    & ".\backend\.venv\Scripts\python.exe" ".\scripts\download_models.py" --dest $ModelsDest
}

# Build executable
$dataPath = $null
try {
    $dataPath = (Resolve-Path $DataDir).Path
} catch {
    $dataPath = (New-Item -ItemType Directory -Path $DataDir -Force).FullName
}
$env:ORATIO_DATA_DIR = $dataPath
$pyinstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--name", $ExeName,
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
    Write-Host "No frontend dist found to bundle (path: $frontendDist)" -ForegroundColor Yellow
}
$modelsPath = $null
try {
    $modelsPath = (Resolve-Path $ModelsDest -ErrorAction Stop).Path
} catch {
    $modelsPath = $null
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
Write-Host "== Done. Executable in dist\$ExeName.exe ==" -ForegroundColor Cyan
Write-Host "Run: .\dist\$ExeName.exe  (set ORATIO_DATA_DIR to choose output folder)" -ForegroundColor Cyan
