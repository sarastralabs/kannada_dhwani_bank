# Start Cloudflare tunnel for public agent + admin UI.
# Prereqs: dev-all.ps1 running (5173/5174), start-kiosk-api.ps1 (8000).
#
# One-time setup:
#   cloudflared tunnel login
#   cloudflared tunnel create sarastra-kiosk
#   cloudflared tunnel route dns <TUNNEL-UUID> agent.sarastralabs.com
#   cloudflared tunnel route dns <TUNNEL-UUID> admin.sarastralabs.com
#   Copy deploy/cloudflare/config-kiosk.yml.example → %USERPROFILE%\.cloudflared\config-kiosk.yml
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-kiosk-tunnel.ps1

$ErrorActionPreference = "Stop"
$config = Join-Path $env:USERPROFILE ".cloudflared\config-kiosk.yml"

if (-not (Test-Path $config)) {
    Write-Host "Missing $config" -ForegroundColor Red
    Write-Host "Copy deploy/cloudflare/config-kiosk.yml.example and set credentials-file + tunnel id."
    exit 1
}

Write-Host "Starting kiosk tunnel (agent.sarastralabs.com + admin.sarastralabs.com)..." -ForegroundColor Cyan
Write-Host "  Agent: https://agent.sarastralabs.com"
Write-Host "  Admin: https://admin.sarastralabs.com"
Write-Host ""

& (Join-Path $PSScriptRoot "ensure-tunnel-config.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$configContent = Get-Content $config -Raw
$tunnelName = "sarastra-kiosk"
if ($configContent -match "(?m)^tunnel:\s*(.+)$") {
    $tunnelName = $Matches[1].Trim()
}

cloudflared tunnel --config $config run $tunnelName
