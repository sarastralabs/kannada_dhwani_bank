# Setup isolated Parler-TTS venv (does not touch main project packages).
# Run from repo root:  .\scripts\setup_parler_venv.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Venv = Join-Path $Root ".venv-parler"
$Py = Join-Path $Venv "Scripts\python.exe"

Write-Host "==> Creating .venv-parler (isolated Indic Parler-TTS)"
if (-not (Test-Path $Py)) {
  python -m venv $Venv
  if ($LASTEXITCODE -ne 0) { throw "Could not create .venv-parler" }
}

Write-Host "==> Upgrading pip"
& $Py -m pip install --upgrade pip wheel setuptools
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip tooling" }

Write-Host "==> Installing CUDA-enabled torch"
& $Py -m pip install "torch>=2.1,<2.5" "torchaudio>=2.1,<2.5" --index-url https://download.pytorch.org/whl/cu124
if ($LASTEXITCODE -ne 0) {
  Write-Host "CUDA wheel install failed; trying the default package index." -ForegroundColor Yellow
  & $Py -m pip install "torch>=2.1,<2.5" "torchaudio>=2.1,<2.5"
  if ($LASTEXITCODE -ne 0) { throw "Could not install PyTorch" }
}

Write-Host "==> Installing transformers==4.46.1 + deps"
& $Py -m pip install "transformers==4.46.1" "accelerate>=0.25" "sentencepiece>=0.2" "soundfile>=0.12" "numpy>=1.24,<2.1" "huggingface_hub>=0.23,<1" "protobuf>=4" 
if ($LASTEXITCODE -ne 0) { throw "Could not install Parler dependencies" }

Write-Host "==> Installing parler-tts (--no-deps so transformers stays 4.46.1)"
& $Py -m pip install "git+https://github.com/huggingface/parler-tts.git" --no-deps
if ($LASTEXITCODE -ne 0) { throw "Could not install parler-tts" }
# descript-audiotools pins protobuf<3.20; parler needs protobuf>=4 — install codec with --no-deps
& $Py -m pip install "descript-audiotools>=0.7.0"
if ($LASTEXITCODE -ne 0) { throw "Could not install descript-audiotools" }
& $Py -m pip install "descript-audio-codec==1.0.0" --no-deps
if ($LASTEXITCODE -ne 0) { throw "Could not install descript-audio-codec" }
& $Py -m pip install einops "protobuf>=4.0,<5"
if ($LASTEXITCODE -ne 0) { throw "Could not finalize Parler dependencies" }

Write-Host "==> Verifying production CUDA access"
& $Py -c @"
import torch
if not torch.cuda.is_available():
    raise SystemExit('CUDA is unavailable in .venv-parler; production TTS cannot run on CPU')
print('CUDA:', torch.version.cuda)
print('GPU:', torch.cuda.get_device_name(0))
"@
if ($LASTEXITCODE -ne 0) { throw "CUDA verification failed" }

Write-Host "==> Warming Hugging Face cache for ai4bharat/indic-parler-tts (large download)"
Write-Host "    Accept license first: https://huggingface.co/ai4bharat/indic-parler-tts"
& $Py -c @"
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer
print('Downloading model...')
m = ParlerTTSForConditionalGeneration.from_pretrained('ai4bharat/indic-parler-tts')
AutoTokenizer.from_pretrained('ai4bharat/indic-parler-tts')
AutoTokenizer.from_pretrained(m.config.text_encoder._name_or_path)
print('Parler model ready')
"@
if ($LASTEXITCODE -ne 0) { throw "Could not download or load the Parler model" }

Write-Host ""
Write-Host "Done. Parler python: $Py"
Write-Host "Set BANK_TTS_ENGINE=parler (default when .venv-parler exists)."
Write-Host "Speakers: BANK_TTS_SPEAKER=Suresh|Anu (default Suresh)"
