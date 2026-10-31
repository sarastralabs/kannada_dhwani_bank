# Production static UI + API tunnel helper
# Builds frontend, serves dist/ on :5173 and dist-admin/ on :5174 with /api proxy.
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-kiosk-prod.ps1
#
# Prereqs: API on :8000 (start-kiosk-api.ps1), Node/npm in PATH.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "frontend"

Push-Location $Frontend
try {
    Write-Host "Building production frontend..." -ForegroundColor Cyan
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host ""
    Write-Host "Starting production previews:" -ForegroundColor Green
    Write-Host "  Agent  https://127.0.0.1:5173  (dist/)"
    Write-Host "  Admin  https://127.0.0.1:5174  (dist-admin/)"
    Write-Host "  API proxy /api -> http://127.0.0.1:8000"
    Write-Host ""

    $agent = Start-Process -PassThru -WindowStyle Normal powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$Frontend'; npx vite preview --config vite.config.ts --port 5173 --host"
    )
    $admin = Start-Process -PassThru -WindowStyle Normal powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$Frontend'; npx vite preview --config vite.admin.config.ts --port 5174 --host"
    )

    Write-Host "Agent preview PID: $($agent.Id)"
    Write-Host "Admin preview PID: $($admin.Id)"
    Write-Host "Press Ctrl+C here to stop (previews run in separate windows)."
    while ($true) { Start-Sleep -Seconds 3600 }
}
finally {
    Pop-Location
}
