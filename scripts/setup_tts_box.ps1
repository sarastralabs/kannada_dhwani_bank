# One-time setup for the 8 GB TTS GPU machine (Parler only).
# Run from repo root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_tts_box.ps1
#
# After setup:
#   Terminal 1: .\scripts\run_tts_server.ps1
#   Terminal 2: cloudflared tunnel ... config-tts.yml

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Ok($msg) { Write-Host "  OK: $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Kannada TTS GPU box - setup" -ForegroundColor Yellow
Write-Host "Repo:  $Root"
Write-Host ""

# --- Python 3.12 ---------------------------------------------------------------
$py = $null
$PyArgs = @()
try {
    & py -3.12 --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $py = "py"
        $PyArgs = @("-3.12")
        Ok "Using py -3.12"
    }
} catch { }

if (-not $py) {
    Fail "Python 3.12 not found. Install from https://www.python.org/downloads/"
}

# --- Host venv (lightweight API only) -----------------------------------------
$venvDir = Join-Path $Root ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "==> Creating .venv (TTS API host only)..."
    if ($PyArgs.Count) { & $py @PyArgs -m venv $venvDir } else { & $py -m venv $venvDir }
    if (-not (Test-Path $venvPython)) { Fail "Failed to create .venv" }
    Ok "Created .venv"
} else {
    Ok ".venv exists"
}

Write-Host "==> Installing TTS API host packages..."
& $venvPython -m pip install --upgrade pip wheel
& $venvPython -m pip install -r requirements-tts-box.txt
if ($LASTEXITCODE -ne 0) { Fail "requirements-tts-box.txt install failed" }
Ok "TTS API dependencies installed"

# --- Parler isolated venv -----------------------------------------------------
Write-Host ""
Write-Host "==> Parler model venv (.venv-parler)..."
& "$PSScriptRoot\setup_parler_venv.ps1"
if ($LASTEXITCODE -ne 0) { Fail "setup_parler_venv.ps1 failed" }

# --- .env for TTS box ---------------------------------------------------------
$envFile = Join-Path $Root ".env"
$envTemplate = Join-Path $Root ".env.tts.example"

if (-not (Test-Path $envFile)) {
    if (Test-Path $envTemplate) {
        Copy-Item $envTemplate $envFile
        Ok "Created .env from .env.tts.example"
        Write-Host ""
        Write-Host "  ACTION: Set BANK_TTS_REMOTE_KEY in .env - same value as kiosk .env" -ForegroundColor Yellow
    } else {
        Fail ".env.tts.example missing"
    }
} else {
    Ok ".env already exists (not overwritten)"
}

Write-Host ""
Write-Host "SUCCESS - TTS box ready." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps on this machine:" -ForegroundColor Yellow
Write-Host "  1) Edit .env - set BANK_TTS_REMOTE_KEY (match kiosk PC)"
Write-Host "  2) .\scripts\run_tts_server.ps1"
Write-Host '  3) cloudflared tunnel --config %USERPROFILE%\.cloudflared\config-tts.yml run bank-tts'
Write-Host "  4) curl http://127.0.0.1:8001/api/health   (expect ready=true)"
Write-Host ""
Write-Host "Kiosk .env must have:"
Write-Host "  BANK_TTS_REMOTE_URL=https://tts.sarastralabs.com"
Write-Host "  BANK_TTS_REMOTE_KEY=same-secret-as-this-machine"
Write-Host ""
