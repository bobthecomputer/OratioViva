Param(
    [switch]$SkipFrontend = $false
)

Write-Host "== OratioViva setup starting ==" -ForegroundColor Cyan

$ErrorActionPreference = "Stop"

# Backend setup
Push-Location "backend"
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtualenv..." -ForegroundColor Green
    python -m venv .venv
}
Write-Host "Installing backend requirements..." -ForegroundColor Green
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
Pop-Location

if (-not $SkipFrontend) {
    Push-Location "frontend"
    Write-Host "Installing frontend dependencies..." -ForegroundColor Green
    npm install
    Pop-Location
} else {
    Write-Host "Skipping frontend install (SkipFrontend set)" -ForegroundColor Yellow
}

Write-Host "== Done. Run backend: uvicorn backend.main:app --reload ==" -ForegroundColor Cyan
Write-Host "== Frontend: cd frontend && npm run dev ==" -ForegroundColor Cyan
