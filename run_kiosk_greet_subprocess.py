"""
Synthesise a Kannada greeting line (Parler Suresh or MMS fallback).
Usage: python run_kiosk_greet_subprocess.py [morning|afternoon|evening|night] [variant_index]

Env:
  BANK_GREET_TTS_ENGINE=parler|mms  (default mms; use parler for natural voice cache)

Prints JSON: { audio_b64, slot, variant, error }
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile

_greet_engine = os.environ.get("BANK_GREET_TTS_ENGINE", "mms").strip().lower()
if _greet_engine in {"parler", "indic-parler", "auto"}:
    os.environ["BANK_TTS_ENGINE"] = "parler"
    os.environ.setdefault("BANK_TTS_SPEAKER", "Suresh")
    # Allow hub read if model still downloading during first warm
    if os.environ.get("BANK_GREET_ALLOW_ONLINE", "").strip().lower() in {"1", "true", "yes"}:
        os.environ.pop("TRANSFORMERS_OFFLINE", None)
        os.environ.pop("HF_HUB_OFFLINE", None)
        os.environ.pop("HF_DATASETS_OFFLINE", None)
else:
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["BANK_TTS_ENGINE"] = "mms"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
GREET_DIR = os.path.join(PROJECT_ROOT, "data", "greetings")

sys.path.insert(0, PROJECT_ROOT)

from backend.greetings import GREET_LINES, pick_greeting, slot_for_hour  # noqa: E402

slot_arg = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
variant_arg: int | None = None
if len(sys.argv) > 2:
    try:
        variant_arg = int(sys.argv[2])
    except ValueError:
        variant_arg = 0

if slot_arg in GREET_LINES:
    greet = pick_greeting(slot=slot_arg, variant=variant_arg if variant_arg is not None else 0)  # type: ignore[arg-type]
else:
    greet = pick_greeting(variant=variant_arg if variant_arg is not None else 0)

slot = greet["slot"]
variant = greet["variant"]
line_kn = greet["line_kn"]

# Protocol: only JSON on stdout
_REAL_STDOUT = sys.stdout
sys.stdout = sys.stderr


def _emit(payload: dict) -> None:
    _REAL_STDOUT.write(json.dumps(payload) + "\n")
    _REAL_STDOUT.flush()


try:
    import soundfile as sf
    from backend.tts import synthesise_kannada, unload_model

    result = synthesise_kannada(line_kn)
    if result is None:
        _emit({"audio_b64": "", "slot": slot, "variant": variant, "error": "TTS returned empty"})
        sys.exit(1)

    audio, sr = result
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    sf.write(tmp.name, audio, sr)
    with open(tmp.name, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    try:
        os.unlink(tmp.name)
    except OSError:
        pass
    # Persist cache WAV so warm_greetings.py and /api/kiosk/greet-audio can reuse it
    try:
        os.makedirs(GREET_DIR, exist_ok=True)
        cache_path = os.path.join(GREET_DIR, f"{slot}_{variant}.wav")
        with open(cache_path, "wb") as cf:
            cf.write(base64.b64decode(b64))
    except OSError:
        pass
    try:
        unload_model()
    except Exception:
        pass
    _emit({"audio_b64": b64, "slot": slot, "variant": variant, "error": None})
except Exception as exc:
    _emit({"audio_b64": "", "slot": slot, "variant": variant, "error": str(exc)})
    sys.exit(1)
