# Poll TTS /api/health until ready=true (Parler loaded + phrases cached).
# Usage:
#   .\scripts\wait-for-tts-ready.ps1
#   .\scripts\wait-for-tts-ready.ps1 -Url http://127.0.0.1:8001 -TimeoutSec 240

param(
    [string]$Url = $(if ($env:BANK_TTS_REMOTE_URL) { $env:BANK_TTS_REMOTE_URL.TrimEnd('/') } else { "http://127.0.0.1:8001" }),
    [int]$TimeoutSec = 240,
    [int]$PollSec = 3
)

$ErrorActionPreference = "Stop"
$deadline = (Get-Date).AddSeconds($TimeoutSec)
$healthUrl = "$Url/api/health"

Write-Host "==> Waiting for TTS ready at $healthUrl (timeout ${TimeoutSec}s)" -ForegroundColor Cyan

while ((Get-Date) -lt $deadline) {
    try {
        $resp = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 8 -ErrorAction Stop
        $ready = ($resp.ready -eq $true) -or ($resp.status -eq "ready")
        if ($ready) {
            Write-Host "==> TTS ready (speaker=$($resp.speaker), status=$($resp.status))" -ForegroundColor Green
            exit 0
        }
        $status = $resp.status
        Write-Host "    ... status=$status ready=$($resp.ready) (retry in ${PollSec}s)"
    }
    catch {
        Write-Host "    ... not reachable yet ($($_.Exception.Message))"
    }
    Start-Sleep -Seconds $PollSec
}

Write-Host "==> TIMEOUT: TTS not ready at $Url" -ForegroundColor Red
Write-Host "    Start TTS first: .\scripts\run_tts_server.ps1"
exit 1
