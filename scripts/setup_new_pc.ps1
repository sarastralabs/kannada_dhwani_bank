# ============================================================================
# setup_new_pc.ps1 - Full first-time setup (venv + libs + models + frontend)
#
# From project root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_new_pc.ps1
#
# Options:
#   -Fresh        Delete .venv and recreate from scratch
#   -SkipModels   Skip HuggingFace downloads (venv + npm only)
#   -SkipFrontend Skip npm install
#
# Or double-click:  setup.bat  (in project root)
# ============================================================================

param(
    [switch]$Fresh,
    [switch]$SkipModels,
    [switch]$SkipFrontend,
    [string]$HfToken = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $ProjectRoot "requirements.txt"))) {
    $ProjectRoot = Get-Location
}
Set-Location $ProjectRoot

function Write-Step($n, $total, $msg) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  STEP $n/$total - $msg" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

function Fail($msg) {
    Write-Host ""
    Write-Host "ERROR: $msg" -ForegroundColor Red
    exit 1
}

function Ok($msg) {
    Write-Host "  OK: $msg" -ForegroundColor Green
}

function Write-Info($msg) {
    Write-Host "  $msg" -ForegroundColor Gray
}

function Invoke-PyScript {
    # Writes a multi-line Python script to a temp file and runs it.
    # Avoids the PowerShell -c multi-line argument splitting bug.
    param([string]$PythonExe, [string]$Code)
    $tmp = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.py'
    [System.IO.File]::WriteAllText($tmp, $Code, (New-Object System.Text.UTF8Encoding $false))
    try {
        $out = & $PythonExe $tmp 2>&1
        return $out
    } finally {
        Remove-Item $tmp -ErrorAction SilentlyContinue
    }
}

function Test-HfTokenConfigured {
    param([string]$PythonExe)
    try {
        $code = @'
from huggingface_hub import get_token
print('yes' if get_token() else 'no')
'@
        $out = Invoke-PyScript -PythonExe $PythonExe -Code $code
        return ("$out" -match "yes")
    } catch {
        return $false
    }
}

function Test-HfGatedAccess {
    param([string]$PythonExe)
    $code = @'
from huggingface_hub import model_info
for mid in (
    "ai4bharat/indictrans2-indic-en-dist-200M",
    "ai4bharat/indictrans2-en-indic-dist-200M",
    "vasista22/whisper-kannada-medium",
):
    model_info(mid)
print("HF_ACCESS_OK")
'@
    $out = Invoke-PyScript -PythonExe $PythonExe -Code $code
    return ($LASTEXITCODE -eq 0 -and ("$out" -match "HF_ACCESS_OK"))
}

function Save-HfToken {
    param(
        [string]$PythonExe,
        [string]$Token
    )
    $Token = $Token.Trim()
    if (-not $Token) { return $false }
    # Pass token via env to avoid shell escaping issues
    $env:SETUP_HF_TOKEN = $Token
    $code = @'
import os, sys
from huggingface_hub import login
token = os.environ.get("SETUP_HF_TOKEN", "").strip()
if not token:
    sys.exit(1)
login(token=token, add_to_git_credential=True)
print("HF_LOGIN_OK")
'@
    $out = Invoke-PyScript -PythonExe $PythonExe -Code $code
    Remove-Item Env:SETUP_HF_TOKEN -ErrorAction SilentlyContinue
    return ($LASTEXITCODE -eq 0 -and ("$out" -match "HF_LOGIN_OK"))
}

function Invoke-HuggingFaceWizard {
    param(
        [string]$PythonExe,
        [string]$PrefilledToken = ""
    )

    Write-Host ""
    Write-Host "  +---------------------------------------------------------+" -ForegroundColor Yellow
    Write-Host "  |  HuggingFace - one-time setup (needs a free account)   |" -ForegroundColor Yellow
    Write-Host "  +---------------------------------------------------------+" -ForegroundColor Yellow
    Write-Host ""

    if (Test-HfTokenConfigured -PythonExe $PythonExe) {
        if (Test-HfGatedAccess -PythonExe $PythonExe) {
            Ok "HuggingFace already logged in with model access"
            return $true
        }
        Write-Host "  Token found but model access failed - need license + valid token" -ForegroundColor Yellow
    }

    Write-Host "  Do these in your browser (we can open links for you):" -ForegroundColor White
    Write-Host ""
    Write-Host "    [A] Create account / log in" -ForegroundColor Cyan
    Write-Host "        https://huggingface.co/login"
    Write-Host ""
    Write-Host "    [B] Accept license - page 1 (click 'Agree and access repository')" -ForegroundColor Cyan
    Write-Host "        https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M"
    Write-Host ""
    Write-Host "    [C] Accept license - page 2 (click 'Agree and access repository')" -ForegroundColor Cyan
    Write-Host "        https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M"
    Write-Host ""
    Write-Host "    [D] Create a Read token (copy it - starts with hf_)" -ForegroundColor Cyan
    Write-Host "        https://huggingface.co/settings/tokens"
    Write-Host "        -> New token -> Name: voice-banking -> Type: Read"
    Write-Host ""

    $open = Read-Host "  Open links [A][B][C][D] in browser now? (Y/N)"
    if ($open -match "^[Yy]") {
        Start-Process "https://huggingface.co/login"
        Start-Sleep -Seconds 1
        Start-Process "https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M"
        Start-Sleep -Seconds 1
        Start-Process "https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M"
        Start-Sleep -Seconds 1
        Start-Process "https://huggingface.co/settings/tokens"
        Write-Info "Browser tabs opened - complete steps A->D, then return here."
    }

    Write-Host ""
    $lic = Read-Host "  Finished steps A-D and accepted BOTH licenses? (Y/N)"
    if ($lic -notmatch "^[Yy]") {
        Write-Host ""
        Write-Host "  Cannot download models without HuggingFace access." -ForegroundColor Yellow
        Write-Host "  Complete steps A-D, then run setup again (or setup.bat --skip-models)." -ForegroundColor Yellow
        return $false
    }

    $token = $PrefilledToken
    if (-not $token) {
        $envToken = $env:HF_TOKEN
        if ($envToken) {
            Write-Info "Using HF_TOKEN from environment"
            $token = $envToken
        }
    }

    $maxTries = 3
    for ($try = 1; $try -le $maxTries; $try++) {
        if (-not $token) {
            Write-Host ""
            Write-Host "  Paste your HuggingFace token below (hf_...)" -ForegroundColor White
            Write-Host "  Tip: right-click terminal to paste, then Enter" -ForegroundColor DarkGray
            $token = Read-Host "  Token"
        }

        if (-not ($token -match "^hf_")) {
            Write-Host "  Token should start with hf_ - please check and try again." -ForegroundColor Yellow
            $token = ""
            continue
        }

        Write-Host "  Saving token and verifying access..."
        if (-not (Save-HfToken -PythonExe $PythonExe -Token $token)) {
            Write-Host "  Login failed - token invalid?" -ForegroundColor Yellow
            $token = ""
            continue
        }

        if (Test-HfGatedAccess -PythonExe $PythonExe) {
            Ok "HuggingFace token saved - all required models accessible"
            return $true
        }

        Write-Host ""
        Write-Host "  Token saved but model access denied." -ForegroundColor Yellow
        Write-Host "  Usually means you did not click 'Agree' on BOTH license pages [B] and [C]." -ForegroundColor Yellow
        Write-Host "  Open those links, accept, wait 30 seconds, then paste token again." -ForegroundColor Yellow
        $token = ""
    }

    Fail "HuggingFace setup failed after $maxTries attempts. Complete licenses A-D and re-run setup.bat"
}

$TotalSteps = if ($SkipModels) { 7 } else { 9 }
if ($SkipFrontend) { $TotalSteps -= 1 }

Write-Host ""
Write-Host "Kannada Voice Banking - automated setup" -ForegroundColor Yellow
Write-Host "Project: $ProjectRoot"
if ($Fresh) { Write-Host "Mode:    FRESH (recreate .venv)" -ForegroundColor Yellow }
if ($SkipModels) { Write-Host "Mode:    SKIP MODEL DOWNLOADS" -ForegroundColor Yellow }
Write-Host ""

# --------------------------------------------------------------------------
# STEP 1 - Python 3.12
# --------------------------------------------------------------------------
Write-Step 1 $TotalSteps "Checking Python 3.12"

$py = $null
$PyArgs = @()

# Prefer py -3.12 launcher
try {
    & py -3.12 --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $py = "py"
        $PyArgs = @("-3.12")
        Ok "Using py -3.12"
    }
} catch { }

if (-not $py) {
    foreach ($candidate in @("python", "py")) {
        try {
            $verOut = & $candidate --version 2>&1
            if ($verOut -match "Python 3\.(1[0-2])") {
                $py = $candidate
                Ok $verOut
                break
            }
        } catch { }
    }
}

if (-not $py) {
    Fail @"
Python 3.12 not found.

Install from: https://www.python.org/downloads/release/python-31210/
Tick 'Add Python to PATH', then re-run setup.bat
"@
}

$verText = if ($PyArgs.Count) { & $py @PyArgs --version 2>&1 } else { & $py --version 2>&1 }
Ok $verText

# --------------------------------------------------------------------------
# STEP 2 - Node.js
# --------------------------------------------------------------------------
Write-Step 2 $TotalSteps "Checking Node.js / npm"

if (-not $SkipFrontend) {
    $nodeOk = $false
    try {
        $nodeVer = & node --version 2>&1
        $npmVer = & npm --version 2>&1
        if ("$nodeVer" -match "v\d+") {
            Ok "node $nodeVer"
            Ok "npm $npmVer"
            $nodeOk = $true
        }
    } catch { }

    if (-not $nodeOk) {
        Fail "Node.js 18+ required. Install from https://nodejs.org/ then re-run setup."
    }
} else {
    Write-Host "  Skipped (-SkipFrontend)" -ForegroundColor DarkGray
}

# --------------------------------------------------------------------------
# STEP 3 - Virtual environment
# --------------------------------------------------------------------------
Write-Step 3 $TotalSteps "Python virtual environment (.venv)"

$venvDir = Join-Path $ProjectRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if ($Fresh -and (Test-Path $venvDir)) {
    Write-Host "  Removing old .venv (-Fresh)..." -ForegroundColor Yellow
    Remove-Item $venvDir -Recurse -Force
}

if (-not (Test-Path $venvPython)) {
    Write-Host "  Creating .venv..."
    if ($PyArgs.Count) {
        & $py @PyArgs -m venv $venvDir
    } else {
        & $py -m venv $venvDir
    }
    if (-not (Test-Path $venvPython)) {
        Fail "Failed to create .venv"
    }
    Ok "Created .venv"
} else {
    Ok ".venv exists - $($(& $venvPython --version 2>&1))"
}

function VPy { & $venvPython @args }
function VPip { & $venvPython -m pip @args }

# --------------------------------------------------------------------------
# STEP 4 - .env file
# --------------------------------------------------------------------------
Write-Step 4 $TotalSteps "Environment file (.env)"

$envFile = Join-Path $ProjectRoot ".env"
$envExample = Join-Path $ProjectRoot ".env.example"

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Ok "Created .env from .env.example"
    } else {
        @"
BANK_TTS_ENGINE=mms
BANK_TTS_ALLOW_MMS=1
BANK_TTS_SPEAKER=Suresh
TRANSFORMERS_OFFLINE=1
HF_HUB_OFFLINE=1
HF_DATASETS_OFFLINE=1
BANK_PIPELINE_KEEP_LOADED=1
BANK_PIPELINE_WORKER=1
"@ | Set-Content $envFile -Encoding UTF8
        Ok "Created default .env"
    }
} else {
    Ok ".env already exists (not overwritten)"
}

# --------------------------------------------------------------------------
# STEP 5 - Python packages
# --------------------------------------------------------------------------
Write-Step 5 $TotalSteps "Installing Python packages (5-15 min)"

Write-Host "  Upgrading pip..."
VPip install --upgrade pip wheel

Write-Host "  Installing build deps (Cython, numpy)..."
VPip install Cython "numpy>=2.1,<3" setuptools

Write-Host "  Pinning transformers<5 before IndicTransToolkit (avoids v5 API break)..."
VPip install "transformers>=4.51.0,<5" "huggingface-hub>=0.23,<2.0"

Write-Host "  Installing IndicTransToolkit..."
try {
    VPip install IndicTransToolkit --no-build-isolation --constraint (Join-Path $ProjectRoot "scripts\constraints.txt")
} catch {
    Fail @"
IndicTransToolkit failed to build.

Install Microsoft C++ Build Tools:
  https://visualstudio.microsoft.com/visual-cpp-build-tools/
Workload: Desktop development with C++

Then run: setup.bat --fresh
"@
}

VPy -c "from IndicTransToolkit import IndicProcessor; print('IndicTransToolkit OK')"
if ($LASTEXITCODE -ne 0) { Fail "IndicTransToolkit import failed" }
Ok "IndicTransToolkit OK"

Write-Host "  Installing requirements.txt..."
VPip install -r requirements.txt

$coreCheck = @'
import fastapi, uvicorn, dotenv, transformers, faster_whisper, soundfile
print('Core imports OK')
'@
$tmp = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.py'
[System.IO.File]::WriteAllText($tmp, $coreCheck, (New-Object System.Text.UTF8Encoding $false))
& $venvPython $tmp 2>&1
$coreExit = $LASTEXITCODE
Remove-Item $tmp -ErrorAction SilentlyContinue
if ($coreExit -ne 0) { Fail "Package import check failed" }
Ok "All Python dependencies installed"

# --------------------------------------------------------------------------
# STEP 6 - HuggingFace (if downloading models)
# --------------------------------------------------------------------------
if (-not $SkipModels) {
    Write-Step 6 $TotalSteps "HuggingFace token + model download"

    $hfOk = Invoke-HuggingFaceWizard -PythonExe $venvPython -PrefilledToken $HfToken
    if (-not $hfOk) {
        $SkipModels = $true
    } else {
        $env:TRANSFORMERS_OFFLINE = "0"
        $env:HF_HUB_OFFLINE = "0"
        $env:HF_DATASETS_OFFLINE = "0"
        $env:PYTHONPATH = $ProjectRoot

        Write-Host ""
        Write-Host "  Downloading ML models (20-40 min first time, stay online)..." -ForegroundColor White

        # STT
        $sttBin = Join-Path $ProjectRoot "models\whisper-kannada-medium-ct2\model.bin"
        if (Test-Path $sttBin) {
            Ok "STT model already present"
        } else {
            Write-Host "  [1/4] STT Kannada model (~1.5 GB)..."
            VPy backend\stt\convert_models.py --model vasista-medium
            if (-not (Test-Path $sttBin)) { Fail "STT conversion failed" }
            Ok "STT model ready"
        }

        # Translation
        Write-Host "  [2/4] Translation kn -> en..."
        VPy -c "from transformers import AutoModelForSeq2SeqLM, AutoTokenizer; m='ai4bharat/indictrans2-indic-en-dist-200M'; AutoTokenizer.from_pretrained(m, trust_remote_code=True); AutoModelForSeq2SeqLM.from_pretrained(m, trust_remote_code=True); print('OK')"
        if ($LASTEXITCODE -ne 0) { Fail "IndicTrans2 kn->en failed" }

        Write-Host "  [3/4] Translation en -> kn..."
        VPy -c "from transformers import AutoModelForSeq2SeqLM, AutoTokenizer; m='ai4bharat/indictrans2-en-indic-dist-200M'; AutoTokenizer.from_pretrained(m, trust_remote_code=True); AutoModelForSeq2SeqLM.from_pretrained(m, trust_remote_code=True); print('OK')"
        if ($LASTEXITCODE -ne 0) { Fail "IndicTrans2 en->kn failed" }
        Ok "Translation models cached"

        # NLU
        $nluCfg = Join-Path $ProjectRoot "models\nlu-distilbert\config.json"
        if (Test-Path $nluCfg) {
            Ok "NLU model already present"
        } else {
            Write-Host "  [4/4] NLU training (~1-3 min)..."
            $env:PYTHONIOENCODING = "utf-8"
            VPy backend\nlu\train.py
            if (-not (Test-Path $nluCfg)) { Fail "NLU training failed" }
            Ok "NLU model ready"
        }

        # TTS
        Write-Host "  [+] TTS Kannada voice (MMS)..."
        VPy -c "from transformers import VitsModel, AutoTokenizer; m='facebook/mms-tts-kan'; AutoTokenizer.from_pretrained(m); VitsModel.from_pretrained(m); print('OK')"
        if ($LASTEXITCODE -ne 0) { Fail "TTS download failed" }
        Ok "TTS model cached"

        Write-Host "  [+] Greeting audio cache (MMS, variant 0 per slot)..."
        VPy scripts\warm_greetings.py --first-only
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  WARN: greeting cache failed - run: .\.venv\Scripts\python.exe scripts\warm_greetings.py --first-only" -ForegroundColor Yellow
        } else {
            Ok "Greeting audio cached"
        }
    }
}

# --------------------------------------------------------------------------
# STEP 7 - Frontend
# --------------------------------------------------------------------------
$stepNum = if ($SkipModels) { 6 } else { 7 }
if (-not $SkipFrontend) {
    Write-Step $stepNum $TotalSteps "Frontend (npm install)"
    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
        npm install
        if ($LASTEXITCODE -ne 0) { Fail "npm install failed" }
        Ok "Frontend dependencies installed"
    } finally {
        Pop-Location
    }
} else {
    Write-Host "  Skipped (-SkipFrontend)" -ForegroundColor DarkGray
}

# --------------------------------------------------------------------------
# STEP 8 - Verify
# --------------------------------------------------------------------------
$stepNum = if ($SkipModels) { if ($SkipFrontend) { 6 } else { 7 } } else { if ($SkipFrontend) { 7 } else { 8 } }
Write-Step $stepNum $TotalSteps "Verification"

VPy scripts\deployment_check.py
$checkCode = $LASTEXITCODE
if ($checkCode -ne 0) {
    Write-Host "  Some checks failed (API may not be running yet - that's OK)" -ForegroundColor Yellow
} else {
    Ok "Deployment check passed"
}

# --------------------------------------------------------------------------
# DONE
# --------------------------------------------------------------------------
Write-Step $TotalSteps $TotalSteps "Setup complete"

Write-Host ""
Write-Host "SUCCESS - environment ready." -ForegroundColor Green
Write-Host ""
Write-Host "HOW TO RUN (3 terminals):" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1) API"
Write-Host "     cd $ProjectRoot"
Write-Host "     .\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000"
Write-Host "     (wait 60 seconds for warm-up)"
Write-Host ""
Write-Host "  2) Frontend (agent + admin)"
Write-Host "     cd $ProjectRoot\frontend"
Write-Host "     .\scripts\dev-all.ps1"
Write-Host ""
Write-Host "  3) Verify before demo"
Write-Host "     .\.venv\Scripts\python.exe scripts\production_smoke_test.py"
Write-Host ""
Write-Host "  Phone (same Wi-Fi): https://<your-ip>:5173"
Write-Host "  Admin login: admin / bank@123"
Write-Host ""
Write-Host "  Full guide: docs\DEMO_AND_INTERACTION_GUIDE.md"
Write-Host ""
Write-Host "Tip: No need to activate .venv - always use .\.venv\Scripts\python.exe"
Write-Host ""
