# Single-PC demo — opens 3 terminals in correct order (TTS → API → Frontend).
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File .\scripts\start-local-all.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "=== Single-PC local demo ===" -ForegroundColor Cyan
Write-Host "Opening 3 terminals in order:"
Write-Host "  1. TTS server  :8001  (loads Parler - wait for Ready log)"
Write-Host "  2. Main API    :8000  (waits for TTS, then starts)"
Write-Host "  3. Frontend    :5173 / :5174"
Write-Host ""
Write-Host "Ensure .env has: BANK_TTS_REMOTE_URL=http://127.0.0.1:8001"
Write-Host ""

Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$Root'; Write-Host '=== Terminal 1: TTS (start first) ===' -ForegroundColor Cyan; powershell -ExecutionPolicy Bypass -File .\scripts\run_tts_server.ps1"
)

Start-Sleep -Seconds 5

Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$Root'; Write-Host '=== Terminal 2: Main API ===' -ForegroundColor Cyan; powershell -ExecutionPolicy Bypass -File .\scripts\start-kiosk-api.ps1"
)

Start-Sleep -Seconds 3

Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$Root\frontend'; Write-Host '=== Terminal 3: Frontend ===' -ForegroundColor Cyan; .\scripts\dev-all.ps1"
)

Write-Host "Terminals launched. Wait for TTS 'Ready' before testing speak." -ForegroundColor Green
