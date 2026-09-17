# AegisForecast SOC Platform — one-command demo launcher
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\demo_all.ps1 [-Headless] [-Kind multi]
param(
  [switch]$Headless,          # run backend + headless demo, skip frontend/browser
  [ValidateSet("single","multi","evasion")]
  [string]$Kind = "multi",    # SOC default: 5-host lateral APT
  [int]$ReconMin = 8,
  [int]$DetMin = 12,
  [int]$Speed = 150,
  [int]$ReconMinGui = 8,
  [int]$DetMinGui = 12
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

function Kill-Port([int]$port) {
  $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($conns) {
    $conns | Select-Object -ExpandProperty OwningProcess -Unique |
      ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Start-Sleep 1
  }
}

Write-Host "== AegisForecast demo launcher ==" -ForegroundColor Cyan

# 1. model artifact check
if (-not (Test-Path "aegis\ml\artifacts\forecast_model.pt")) {
  Write-Host "training quick model first (~4 min)..." -ForegroundColor Yellow
  python -m aegis.ml.train --epochs 6 | Out-Null
}

# 2. backend on :8000
Kill-Port 8000
Write-Host "starting backend  -> http://127.0.0.1:8000" -ForegroundColor Green
Start-Process -WindowStyle Hidden python -ArgumentList "-m", "aegis.server" -WorkingDirectory $root
Start-Sleep 6
$health = Invoke-RestMethod http://127.0.0.1:8000/api/health -ErrorAction Stop
Write-Host ("  backend ok: {0} (threshold {1})" -f $health.status, $health.threshold)

if ($Headless) {
  # headless end-to-end demo, then exit
  Write-Host "running headless demo..." -ForegroundColor Green
  python demo\run_demo.py $ReconMin $DetMin $Speed
  exit $LASTEXITCODE
}

# 3. frontend on :5173
Kill-Port 5173
if (-not (Test-Path "frontend\node_modules")) {
  Write-Host "installing frontend deps..." -ForegroundColor Yellow
  Push-Location frontend; npm install --silent; Pop-Location
}
Write-Host "starting frontend -> http://localhost:5173" -ForegroundColor Green
Start-Process -FilePath "cmd" -ArgumentList "/c", "cd /d `"$root\frontend`" && npm run dev" -WindowStyle Hidden
Start-Sleep 10

# 4. kick off an attack session so the dashboard is live immediately
$kindLabel = @{single="Single Host"; multi="Lateral APT (5-host)"; evasion="Red-Team"}[$Kind]
Write-Host "launching $kindLabel simulation (recon $ReconMinGui m -> detonation $DetMinGui m, ${Speed}x)..." -ForegroundColor Green
$null = Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/sim/start?kind=$Kind&recon_min=$ReconMinGui&det_min=$DetMinGui&speed=$Speed"

# 5. open the dashboard
Start-Process "http://localhost:5173"
Write-Host @"

Demo is LIVE — AegisForecast SOC Platform ($kindLabel).
  - dashboard  : http://localhost:5173  (kind picker: Lateral APT / Single Host / Red-Team)
  - topology   : live risk-colored 5-host map + animated attack edges
  - SOAR       : respond buttons + auto-SOAR toggle in the right panel
  - playbook   : http://127.0.0.1:8000/api/playbook.md
  - campaigns  : http://127.0.0.1:8000/api/campaigns
  - report     : http://127.0.0.1:8000/api/report/{id}.html (after session ends)
  - replay A/B : http://127.0.0.1:8000/api/replays → /api/replay/{id}?host=WEB
  - evasion    : http://127.0.0.1:8000/api/evasion/analysis
  - stop sim   : POST /api/sim/stop (or the Abort button)

"@ -ForegroundColor Cyan
