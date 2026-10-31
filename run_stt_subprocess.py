"""
Run Kannada STT on a single wav and print JSON.
Used by the Forms feature so the API process stays light.

Usage: python run_stt_subprocess.py <wav_path>
"""
from __future__ import annotations

import json
import os
import sys

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.stt import transcribe

wav_path = sys.argv[1]
try:
    text = transcribe(wav_path, beam_size=5)
    print(json.dumps({"text": text or "", "error": None}))
except Exception as exc:
    print(json.dumps({"text": "", "error": str(exc)}))
    sys.exit(1)
