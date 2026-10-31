# Open the customer screen full-screen (no address bar, no tabs) — for the kiosk display.
# Usage (from repo root, after the API and frontend are running):
#   powershell -ExecutionPolicy Bypass -File .\scripts\open-kiosk-fullscreen.ps1
# Exit kiosk mode with Alt+F4.

param(
    [string]$Url = "http://127.0.0.1:5173/"
)

$candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)
$browser = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $browser) {
    Write-Host "Chrome or Edge not found - open $Url and press F11 instead." -ForegroundColor Yellow
    exit 1
}

# Own profile so the microphone / camera permission is remembered after the first "Allow".
$profileDir = Join-Path $env:LOCALAPPDATA "KannadaKioskProfile"
New-Item -ItemType Directory -Force $profileDir | Out-Null

Start-Process $browser -ArgumentList @(
    "--kiosk",
    "--app=$Url",
    "--user-data-dir=$profileDir",
    "--autoplay-policy=no-user-gesture-required",
    "--no-first-run",
    "--disable-features=Translate"
)
Write-Host "Kiosk opened full-screen: $Url (Alt+F4 to close)" -ForegroundColor Green
