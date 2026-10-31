# Generate dev HTTPS cert (localhost + Wi-Fi IP) - fixes blank agent on LAN HTTPS
# Run: powershell -ExecutionPolicy Bypass -File .\frontend\scripts\setup-dev-https.ps1

$ErrorActionPreference = "Stop"
$Frontend = Split-Path -Parent $PSScriptRoot
Set-Location $Frontend

function Get-WifiLanIp {
    $wifi = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.InterfaceAlias -match 'Wi-Fi|WLAN' -and
            $_.IPAddress -match '^192\.168\.' -and
            $_.IPAddress -ne '192.168.137.1'
        } |
        Select-Object -First 1 -ExpandProperty IPAddress
    if ($wifi) { return $wifi }
    return (
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -match '^192\.168\.' -and $_.IPAddress -ne '192.168.137.1' } |
        Select-Object -First 1 -ExpandProperty IPAddress
    )
}

$ip = Get-WifiLanIp
if (-not $ip) {
    Write-Host "WARN: No 192.168.x.x found - cert covers localhost only." -ForegroundColor Yellow
    $ip = "127.0.0.1"
}

Write-Host "==> Generating dev HTTPS cert for localhost + $ip"
node "$PSScriptRoot\generate-dev-cert.mjs" $ip

Write-Host ""
Write-Host "Restart frontend:  cd frontend; .\scripts\dev-all.ps1" -ForegroundColor Green
Write-Host "Laptop:  https://127.0.0.1:5173"
if ($ip -ne "127.0.0.1") {
    Write-Host "Phone:   https://${ip}:5173  (accept cert warning once)" -ForegroundColor Green
}
