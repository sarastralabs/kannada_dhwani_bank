# Dedicated Parler TTS server (8 GB GPU box).
# Run from repo root after: .\scripts\setup_tts_box.ps1
#
# Expose with cloudflared → https://tts.sarastralabs.com
# Kiosk .env: BANK_TTS_REMOTE_URL=https://tts.sarastralabs.com

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Load-DotEnv($path) {
    if (-not (Test-Path $path)) { return }
    Get-Content $path | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"')
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

Load-DotEnv (Join-Path $Root ".env")

$ParlerPy = Join-Path $Root ".venv-parler\Scripts\python.exe"
$HostPy = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $ParlerPy)) {
    Write-Host "ERROR: .venv-parler not found." -ForegroundColor Red
    Write-Host "Run first: powershell -ExecutionPolicy Bypass -File .\scripts\setup_tts_box.ps1"
    exit 1
}

if (-not (Test-Path $HostPy)) {
    Write-Host "ERROR: .venv not found (TTS API host)." -ForegroundColor Red
    Write-Host "Run first: powershell -ExecutionPolicy Bypass -File .\scripts\setup_tts_box.ps1"
    exit 1
}

# TTS box overrides — never inherit kiosk remote URL
$env:BANK_TTS_ENGINE = "parler"
$env:BANK_PARLER_DTYPE = "fp16"
$env:BANK_PARLER_DO_SAMPLE = "1"
$env:BANK_TTS_CACHE_MAX = "512"
$env:BANK_PIPELINE_WORKER = "0"
$env:BANK_TTS_ALLOW_MMS = "0"
Remove-Item Env:BANK_TTS_REMOTE_URL -ErrorAction SilentlyContinue

$Port = if ($env:BANK_TTS_PORT) { $env:BANK_TTS_PORT } else { "8001" }

Write-Host "==> Kannada TTS server (Parler FP16) on 0.0.0.0:$Port" -ForegroundColor Green
Write-Host "    Parler venv: $ParlerPy"
Write-Host "    API host:    $HostPy"
Write-Host "    First start loads model (~1-2 min) - wait for Ready"
Write-Host "    Health: http://127.0.0.1:$Port/api/health"
Write-Host "    Public: https://tts.sarastralabs.com/api/health (after cloudflared)"
Write-Host ""

& $HostPy -m uvicorn api.tts_main:app --host 0.0.0.0 --port $Port
