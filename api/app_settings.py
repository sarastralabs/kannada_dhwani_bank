"""Runtime app settings (in-memory) — adjustable from admin without restart."""

from __future__ import annotations

import os
from threading import Lock

from backend import runtime_settings

_lock = Lock()
VALID_SPEAKERS = frozenset({"Suresh", "Anu"})


def _normalise_speaker(name: str) -> str:
    raw = (name or "").strip().lower()
    if raw == "anu":
        return "Anu"
    if raw == "suresh":
        return "Suresh"
    raise ValueError(f"Unknown speaker {name!r}. Choose Suresh or Anu.")


def _load_saved_speaker() -> str | None:
    try:
        return _normalise_speaker(str(runtime_settings.read_all().get("speaker") or ""))
    except (ValueError, TypeError):
        return None


_DEFAULT = _load_saved_speaker()
if _DEFAULT is None:
    try:
        _DEFAULT = _normalise_speaker(os.environ.get("BANK_TTS_SPEAKER", "Suresh"))
    except ValueError:
        _DEFAULT = "Suresh"
_speaker: str = _DEFAULT
os.environ["BANK_TTS_SPEAKER"] = _speaker


def get_tts_speaker() -> str:
    with _lock:
        return _speaker


def set_tts_speaker(name: str) -> str:
    global _speaker
    normalized = _normalise_speaker(name)
    with _lock:
        _speaker = normalized
        os.environ["BANK_TTS_SPEAKER"] = normalized
        # Merge so the cloud-provider settings in the same file are kept.
        runtime_settings.update({"speaker": normalized})
    return normalized
