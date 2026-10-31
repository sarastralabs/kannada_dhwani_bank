param(
    [switch]$Background,
    [switch]$Force,
    [string]$Speakers = "Suresh,Anu"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = (Get-Command py).Source
    $pythonArgs = @("-3.12")
}
else {
    $pythonArgs = @()
}

$arguments = @($pythonArgs) + @(
    (Join-Path $Root "scripts\warm_static_tts.py"),
    "--speakers",
    $Speakers
)
if ($Force) {
    $arguments += "--force"
}

if (-not $Background) {
    & $python @arguments
    exit $LASTEXITCODE
}

$logDir = Join-Path $Root "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdout = Join-Path $logDir "static-tts-warm.log"
$stderr = Join-Path $logDir "static-tts-warm-error.log"
$process = Start-Process `
    -FilePath $python `
    -ArgumentList $arguments `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru
Write-Host "Static TTS warm started in background (PID $($process.Id))."
Write-Host "Progress: $stdout"
