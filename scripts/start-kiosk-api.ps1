# Kiosk / main API on :8000 - waits for remote TTS if configured, then starts uvicorn.
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File .\scripts\start-kiosk-api.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Load .env into process (uvicorn also loads via api.main)
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"')
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

$remote = $env:BANK_TTS_REMOTE_URL
if ($remote) {
    Write-Host "==> Remote TTS configured: $remote" -ForegroundColor Cyan
    # One quick check only — the API starts either way. While the voice server is down
    # the kiosk speaks with Sarvam (if a key is set); switch Speaking back to
    # Open-source in Settings once the server is up.
    try {
        $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri "$($remote.TrimEnd('/'))/api/health"
        Write-Host "    Voice server is up." -ForegroundColor Green
    }
    catch {
        Write-Host "    Voice server is offline - starting anyway (Sarvam voice is used until it is back)." -ForegroundColor Yellow
    }
}
else {
    Write-Host "==> No BANK_TTS_REMOTE_URL - local TTS/MMS on this machine" -ForegroundColor Cyan
}

$Port = if ($env:BANK_API_PORT) { $env:BANK_API_PORT } else { "8000" }

Write-Host ""
Write-Host "==> Main API on 0.0.0.0:$Port" -ForegroundColor Green
Write-Host "    Health: http://127.0.0.1:$Port/api/health"
Write-Host "    Do NOT use .venv-parler for this process."
Write-Host ""

# Prefer project .venv (has requirements.txt); fall back to py -3.12
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    Write-Host "    Using: $venvPy"
    & $venvPy -m uvicorn api.main:app --host 0.0.0.0 --port $Port
} else {
    Write-Host "    Using: py -3.12 (no .venv found)"
    py -3.12 -m uvicorn api.main:app --host 0.0.0.0 --port $Port
}
