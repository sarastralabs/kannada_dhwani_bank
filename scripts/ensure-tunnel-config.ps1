# Ensures Cloudflare kiosk config routes /api directly to uvicorn (:8000).
# Run once after copying config-kiosk.yml.example.

$ErrorActionPreference = "Stop"
$config = Join-Path $env:USERPROFILE ".cloudflared\config-kiosk.yml"
$example = Join-Path (Split-Path -Parent $PSScriptRoot) "deploy\cloudflare\config-kiosk.yml.example"

if (-not (Test-Path $config)) {
    if (Test-Path $example) {
        Copy-Item $example $config
        Write-Host "Created $config from example - edit credentials-file and tunnel id." -ForegroundColor Yellow
    } else {
        Write-Host "Missing $config" -ForegroundColor Red
        exit 1
    }
}

$content = Get-Content $config -Raw
if ($content -match "path:\s*\^/api") {
    Write-Host "Tunnel config already has /api direct routes." -ForegroundColor Green
    exit 0
}

Write-Host "Updating tunnel config with /api -> :8000 routes..." -ForegroundColor Cyan

if ($content -match "(?m)^tunnel:\s*(.+)$") { $tunnel = $Matches[1].Trim() } else { $tunnel = "sarastra-kiosk" }
if ($content -match "(?m)^credentials-file:\s*(.+)$") { $creds = $Matches[1].Trim() } else { $creds = "C:\Users\<YOUR-USER>\.cloudflared\<TUNNEL-UUID>.json" }

# Use line array (not here-string) - Windows PowerShell 5.1 misparses YAML lines starting with "-"
$lines = @(
    "tunnel: $tunnel"
    "credentials-file: $creds"
    ""
    "ingress:"
    "  - hostname: agent.sarastralabs.com"
    "    path: ^/api"
    "    service: http://127.0.0.1:8000"
    "  - hostname: admin.sarastralabs.com"
    "    path: ^/api"
    "    service: http://127.0.0.1:8000"
    "  - hostname: agent.sarastralabs.com"
    "    service: https://127.0.0.1:5173"
    "    originRequest:"
    "      noTLSVerify: true"
    "  - hostname: admin.sarastralabs.com"
    "    service: https://127.0.0.1:5174"
    "    originRequest:"
    "      noTLSVerify: true"
    "  - service: http_status:404"
)

Set-Content -Path $config -Value ($lines -join [Environment]::NewLine) -Encoding UTF8
Write-Host "Updated $config - restart cloudflared tunnel." -ForegroundColor Green
