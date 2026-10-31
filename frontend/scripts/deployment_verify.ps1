# Run full deployment verification (Windows)
# Usage:  cd c:\Sarastra\voice-based-assistant\frontend\scripts
#         .\deployment_verify.ps1
# Or:     .\deployment_verify.ps1 -Full

param(
    [switch]$Full,
    [string]$Api = "http://127.0.0.1:8000"
)

$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

Write-Host ""
Write-Host "=== Step 1: Deployment file/model check ===" -ForegroundColor Cyan
$args1 = @("-3.12", "scripts/deployment_check.py", "--api", $Api)
if ($Full) { $args1 += "--full" }
py @args1
$code1 = $LASTEXITCODE

Write-Host ""
Write-Host "=== Step 2: Unit tests ===" -ForegroundColor Cyan
py -3.12 -m unittest discover -s tests -q
$code2 = $LASTEXITCODE

Write-Host ""
Write-Host "=== Step 3: Production smoke test ===" -ForegroundColor Cyan
py -3.12 scripts/production_smoke_test.py --api $Api
$code3 = $LASTEXITCODE

Write-Host ""
Write-Host "=== Step 4: E2E (TTS ready + speak + admin) ===" -ForegroundColor Cyan
py -3.12 scripts/e2e_local_check.py
$code4 = $LASTEXITCODE

Write-Host ""
Write-Host "=== Step 5: Network (phone access) ===" -ForegroundColor Cyan
$ip = (
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -match '^192\.168\.' -and $_.InterfaceAlias -match 'Wi-Fi' } |
    Select-Object -First 1 -ExpandProperty IPAddress
)
if (-not $ip) {
    $ip = (
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -match '^192\.168\.' } |
        Select-Object -First 1 -ExpandProperty IPAddress
    )
}
if ($ip) {
    Write-Host "  Wi-Fi IP: $ip" -ForegroundColor Green
    Write-Host "  Phone Agent: https://${ip}:5173"
    Write-Host "  Phone Admin: https://${ip}:5174"
} else {
    Write-Host "  [WARN] No 192.168.x.x found — run ipconfig" -ForegroundColor Yellow
}

if ($code1 -ne 0 -or $code2 -ne 0 -or $code3 -ne 0 -or $code4 -ne 0) {
    Write-Host ""
    Write-Host "SOME CHECKS FAILED — fix before demo" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "ALL CHECKS PASSED on this machine" -ForegroundColor Green
exit 0
