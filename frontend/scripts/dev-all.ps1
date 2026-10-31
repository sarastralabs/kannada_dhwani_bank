# Start Agent (5173) and Admin (5174)

# Default: HTTPS (phone + laptop). Laptop-only HTTP: $env:VITE_DEV_HTTP='1'; .\scripts\dev-all.ps1

Set-Location (Split-Path -Parent $PSScriptRoot)



function Get-LanIPv4 {

    $candidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |

        Where-Object {

            $_.PrefixOrigin -ne 'WellKnown' -and

            $_.IPAddress -notmatch '^127\.' -and

            $_.IPAddress -notmatch '^169\.254\.' -and

            $_.IPAddress -notmatch '^172\.21\.' -and

            $_.IPAddress -ne '192.168.137.1'

        }



    $wifi = $candidates | Where-Object { $_.InterfaceAlias -match 'Wi-Fi|WLAN' -and $_.IPAddress -match '^192\.168\.' } |

        Select-Object -First 1 -ExpandProperty IPAddress

    if ($wifi) { return $wifi }



    return ($candidates | Where-Object { $_.IPAddress -match '^192\.168\.' } | Select-Object -First 1 -ExpandProperty IPAddress)

}



$ip = Get-LanIPv4

$useHttp = $env:VITE_DEV_HTTP -eq '1'



if ($useHttp) {

    Remove-Item Env:VITE_DEV_LAN_HTTPS -ErrorAction SilentlyContinue

} else {

    Remove-Item Env:VITE_DEV_HTTP -ErrorAction SilentlyContinue

    & "$PSScriptRoot\setup-dev-https.ps1"

}



Write-Host ""

Write-Host "=== Kannada Voice Banking (dev) ===" -ForegroundColor Cyan

if ($useHttp) {

    Write-Host "Mode:  HTTP (laptop only - mic on phone will NOT work)" -ForegroundColor Yellow

    Write-Host "PC:    http://127.0.0.1:5173  (agent)   http://127.0.0.1:5174  (admin)" -ForegroundColor Green

    if ($ip) {

        Write-Host "Phone: http://${ip}:5173  (view only - no mic over HTTP)" -ForegroundColor Yellow

        Write-Host "       For phone demo with mic, restart WITHOUT VITE_DEV_HTTP (default HTTPS)." -ForegroundColor Yellow

    }

} else {

    Write-Host "Mode:  HTTPS (phone + laptop)" -ForegroundColor Green

    Write-Host "PC:    https://127.0.0.1:5173  (agent)   https://127.0.0.1:5174  (admin)"

    Write-Host "       Use 127.0.0.1 (NOT localhost). Accept certificate warning once."

    if ($ip) {

        Write-Host "Phone: https://${ip}:5173  (accept cert once on phone)" -ForegroundColor Green

    }

}

Write-Host "API:   http://127.0.0.1:8000  (must be running)"

Write-Host ""



$httpFlag = if ($useHttp) { '1' } else { '' }

Start-Process powershell -ArgumentList @(

    "-NoExit", "-Command",

    "cd '$PWD'; `$env:VITE_DEV_HTTP='$httpFlag'; npm run dev:agent"

)

Start-Process powershell -ArgumentList @(

    "-NoExit", "-Command",

    "cd '$PWD'; `$env:VITE_DEV_HTTP='$httpFlag'; npm run dev:admin"

)


