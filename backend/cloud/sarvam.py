"""
Minimal Sarvam AI client (https://docs.sarvam.ai) — speech-to-text, translation
and Kannada text-to-speech with one API key. Standard library only.

Every failure raises :class:`CloudError` with a ``kind`` the admin console
explains to staff:

  auth        key missing / wrong / revoked              → paste a new key
  quota       free credits used up (insufficient_quota)  → paste a new key
  rate_limit  too many requests right now                → retried later
  network     no internet / timeout                      → retried later
  server      Sarvam-side error (5xx)                    → retried later
  bad_request request rejected (4xx)                     → see message
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

BASE_URL = "https://api.sarvam.ai"

STT_MODEL_DEFAULT = "saaras:v4"
TRANSLATE_MODEL_DEFAULT = "mayura:v1"
TTS_MODEL_DEFAULT = "bulbul:v3"
TTS_SAMPLE_RATE = 22050

# Voices offered in the admin console (bulbul:v3). Staff pick by ear with "Play sample".
TTS_VOICES: tuple[str, ...] = (
    "shubh", "aditya", "rahul", "rohan", "amit", "dev", "varun", "kabir", "anand",
    "ritu", "priya", "neha", "pooja", "simran", "kavya", "ishita", "shreya",
    "roopa", "kavitha", "shruti",
)
TTS_VOICE_DEFAULT = "shubh"

_LANG = {"kan_Knda": "kn-IN", "eng_Latn": "en-IN", "kn": "kn-IN", "en": "en-IN"}

# Per-request text limits (characters) — stay safely under the documented maximums.
_TTS_MAX_CHARS = 1400
_TRANSLATE_MAX_CHARS = 900


class CloudError(RuntimeError):
    def __init__(self, kind: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


def _env(name: str, default: str) -> str:
    return os.environ.get(name, "").strip() or default


def _timeout_s() -> float:
    try:
        return max(3.0, float(os.environ.get("SARVAM_TIMEOUT_S", "20")))
    except ValueError:
        return 20.0


def _classify(status: int, body: str) -> CloudError:
    code = ""
    message = ""
    try:
        payload = json.loads(body)
        err = payload.get("error", payload) if isinstance(payload, dict) else {}
        if isinstance(err, dict):
            code = str(err.get("code") or "")
            message = str(err.get("message") or "")
        elif isinstance(err, str):
            message = err
        if not message and isinstance(payload, dict):
            message = str(payload.get("message") or payload.get("detail") or "")
    except (ValueError, AttributeError):
        message = body[:200]
    message = message.strip() or f"HTTP {status}"
    lowered = f"{code} {message}".lower()

    if "quota" in lowered or "credit" in lowered or "billing" in lowered or status == 402:
        return CloudError("quota", f"Sarvam credits are used up ({message})", status)
    if status in (401, 403) or "api_key" in lowered or "authentication" in lowered:
        return CloudError("auth", f"Sarvam rejected the API key ({message})", status)
    if status == 429 or "rate_limit" in lowered:
        return CloudError("rate_limit", f"Sarvam rate limit reached ({message})", status)
    if status >= 500:
        return CloudError("server", f"Sarvam service error {status} ({message})", status)
    return CloudError("bad_request", f"Sarvam rejected the request ({message})", status)


def _post(api_key: str, path: str, *, body: bytes, content_type: str) -> dict[str, Any]:
    if not api_key:
        raise CloudError("auth", "No Sarvam API key is set")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method="POST",
        headers={
            "api-subscription-key": api_key,
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "SarastraBankAssistant/1.0",
        },
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=_timeout_s()) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        raise _classify(exc.code, detail) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise CloudError("network", f"Cannot reach Sarvam ({reason})") from None
    elapsed = round((time.perf_counter() - started) * 1000)
    print(f"[sarvam] {path} ok ms={elapsed}", file=sys.stderr, flush=True)
    try:
        payload = json.loads(raw)
    except ValueError:
        raise CloudError("server", "Sarvam returned an unreadable response") from None
    return payload if isinstance(payload, dict) else {}


def _post_json(api_key: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _post(
        api_key,
        path,
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )


def _multipart(fields: dict[str, str], file_field: str, filename: str, data: bytes) -> tuple[bytes, str]:
    boundary = f"----sarastra{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
            f'filename="{filename}"\r\nContent-Type: audio/wav\r\n\r\n'
        ).encode()
        + data
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


# ---------------------------------------------------------------------------
# Speech-to-text
# ---------------------------------------------------------------------------
def transcribe(api_key: str, wav_path: str, *, language: str = "kn") -> str:
    with open(wav_path, "rb") as handle:
        audio = handle.read()
    body, content_type = _multipart(
        {
            "model": _env("SARVAM_STT_MODEL", STT_MODEL_DEFAULT),
            "language_code": _LANG.get(language, "kn-IN"),
        },
        "file",
        os.path.basename(wav_path) or "audio.wav",
        audio,
    )
    payload = _post(api_key, "/speech-to-text", body=body, content_type=content_type)
    return str(payload.get("transcript") or "").replace("�", "").strip()


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------
def _split_text(text: str, limit: int) -> list[str]:
    """Split on sentence ends, then on spaces, so each piece fits one request."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    pieces: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.!?।])\s+", text):
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if current and len(current) + 1 + len(sentence) > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return [p for p in pieces if p]


def translate(api_key: str, text: str, *, src_lang: str, tgt_lang: str) -> str:
    out: list[str] = []
    for piece in _split_text(text, _TRANSLATE_MAX_CHARS):
        payload = _post_json(
            api_key,
            "/translate",
            {
                "input": piece,
                "source_language_code": _LANG.get(src_lang, "kn-IN"),
                "target_language_code": _LANG.get(tgt_lang, "en-IN"),
                "model": _env("SARVAM_TRANSLATE_MODEL", TRANSLATE_MODEL_DEFAULT),
                "numerals_format": "international",
            },
        )
        out.append(str(payload.get("translated_text") or "").strip())
    return " ".join(p for p in out if p).strip()


# ---------------------------------------------------------------------------
# Text-to-speech
# ---------------------------------------------------------------------------
def _wav_from_b64(audio_b64: str) -> tuple["Any", int]:
    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(io.BytesIO(base64.b64decode(audio_b64)), dtype="float32", always_2d=False)
    if getattr(audio, "ndim", 1) > 1:
        audio = audio.mean(axis=1)
    return np.asarray(audio, dtype=np.float32), int(sr)


def synthesise(api_key: str, kannada_text: str, *, voice: str | None = None) -> tuple["Any", int]:
    """Kannada text → (float32 mono audio, sample rate)."""
    import numpy as np

    speaker = (voice or TTS_VOICE_DEFAULT).strip().lower()
    parts: list[Any] = []
    sr_out = TTS_SAMPLE_RATE
    for piece in _split_text(kannada_text, _TTS_MAX_CHARS):
        payload = _post_json(
            api_key,
            "/text-to-speech",
            {
                "text": piece,
                "target_language_code": "kn-IN",
                "language_code": "kn-IN",
                "speaker": speaker,
                "model": _env("SARVAM_TTS_MODEL", TTS_MODEL_DEFAULT),
                "speech_sample_rate": TTS_SAMPLE_RATE,
                "output_audio_codec": "wav",
            },
        )
        audios = payload.get("audios") or []
        if not audios or not audios[0]:
            raise CloudError("server", "Sarvam returned no audio")
        for item in audios:
            audio, sr_out = _wav_from_b64(str(item))
            if parts:
                parts.append(np.zeros(int(0.25 * sr_out), dtype=np.float32))
            parts.append(audio)
    if not parts:
        raise CloudError("bad_request", "Nothing to speak")
    return np.concatenate(parts), sr_out
