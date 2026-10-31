"""Admin / Agent kiosk control routes."""

from __future__ import annotations

import base64
import json
import os
import random
import subprocess
import sys
import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api import admin_auth, kiosk_state
from backend.greetings import GREET_LINES, all_greetings, pick_greeting, slot_for_hour

router = APIRouter(tags=["kiosk"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GREET_SCRIPT = os.path.join(PROJECT_ROOT, "run_kiosk_greet_subprocess.py")
GREET_DIR = os.path.join(PROJECT_ROOT, "data", "greetings")

_OFFLINE_ENV = {
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
}

_warm_lock = threading.Lock()
_warm_running = False


class PresenceBody(BaseModel):
    present: bool


class PhaseBody(BaseModel):
    phase: str = Field(..., description="idle | greeting | conversation")


class EndBody(BaseModel):
    note: str = ""


def _current_speaker() -> str:
    from api.app_settings import get_tts_speaker

    return get_tts_speaker()


def _cloud_voice_tag() -> str | None:
    """File tag for greetings spoken by a Sarvam voice (None = local Parler voice)."""
    try:
        from backend.tts import cloud_tts_profile

        profile = cloud_tts_profile()
    except Exception:
        return None
    if not profile:
        return None
    return "sarvam-" + profile.rsplit("|", 1)[-1]


def _voice_tag() -> str:
    return _cloud_voice_tag() or _current_speaker()


def _cache_path(slot: str, variant: int, speaker: str | None = None) -> str:
    selected = speaker or _voice_tag()
    return os.path.join(GREET_DIR, f"{slot}_{variant}_{selected.lower()}.wav")


def _read_cache(slot: str, variant: int) -> str | None:
    speaker = _voice_tag()
    paths = [_cache_path(slot, variant, speaker)]
    # Existing unlabelled greeting files were generated with the Suresh default.
    if speaker == "Suresh":
        paths.append(os.path.join(GREET_DIR, f"{slot}_{variant}.wav"))
    for path in paths:
        if os.path.isfile(path) and os.path.getsize(path) > 1000:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")
    return None


def _extract_json_blob(text: str) -> dict:
    text = (text or "").strip()
    for chunk in reversed(text.splitlines()):
        chunk = chunk.strip()
        if chunk.startswith("{") and chunk.endswith("}"):
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                continue
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise json.JSONDecodeError("no json", text, 0)


def _generate_variant(slot: str, variant: int) -> dict:
    """Synthesise one greeting line; uses remote Parler when BANK_TTS_REMOTE_URL is set."""
    from backend.tts.remote_bridge import remote_tts_configured

    greet = pick_greeting(slot=slot, variant=variant)  # type: ignore[arg-type]
    line_kn = greet.get("line_kn") or ""
    speaker = _current_speaker()
    cloud_tag = _cloud_voice_tag()

    if (remote_tts_configured() or cloud_tag) and line_kn.strip():
        try:
            from backend.tts.speak_cache import kannada_to_b64

            audio_b64 = kannada_to_b64(line_kn, speaker=speaker)
            if audio_b64:
                try:
                    os.makedirs(GREET_DIR, exist_ok=True)
                    # Re-check: if Sarvam failed just now, this clip is the local voice.
                    saved_tag = _cloud_voice_tag() if cloud_tag else None
                    with open(_cache_path(slot, variant, saved_tag or speaker), "wb") as f:
                        f.write(base64.b64decode(audio_b64))
                except OSError:
                    pass
                return {
                    "audio_b64": audio_b64,
                    "slot": slot,
                    "variant": variant,
                    "error": None,
                    "cached": False,
                }
        except Exception as exc:
            return {
                "audio_b64": "",
                "slot": slot,
                "variant": variant,
                "error": str(exc),
                "cached": False,
            }

    # Remote TTS configured: never fall back to local MMS for greetings.
    if remote_tts_configured():
        return {
            "audio_b64": "",
            "slot": slot,
            "variant": variant,
            "error": "Remote TTS failed — MMS greeting fallback disabled",
            "cached": False,
        }

    # Local-only deploy (no BANK_TTS_REMOTE_URL): MMS subprocess.
    try:
        proc = subprocess.run(
            [sys.executable, GREET_SCRIPT, slot, str(variant)],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            env={
                **os.environ,
                **_OFFLINE_ENV,
                "BANK_TTS_ENGINE": "mms",
                "BANK_TTS_SPEAKER": speaker,
            },
            timeout=180,
        )
    except Exception as exc:
        return {
            "audio_b64": "",
            "slot": slot,
            "variant": variant,
            "error": str(exc),
            "cached": False,
        }

    try:
        payload = _extract_json_blob(proc.stdout or "")
    except json.JSONDecodeError:
        return {
            "audio_b64": "",
            "slot": slot,
            "variant": variant,
            "error": (proc.stderr or proc.stdout or "")[:300],
            "cached": False,
        }

    audio_b64 = payload.get("audio_b64") or ""
    if proc.returncode != 0 or payload.get("error") or not audio_b64:
        return {
            "audio_b64": "",
            "slot": slot,
            "variant": variant,
            "error": payload.get("error") or (proc.stderr or "").strip() or "TTS failed",
            "cached": False,
        }

    try:
        os.makedirs(GREET_DIR, exist_ok=True)
        with open(_cache_path(slot, variant, speaker), "wb") as f:
            f.write(base64.b64decode(audio_b64))
    except OSError:
        pass

    return {
        "audio_b64": audio_b64,
        "slot": slot,
        "variant": variant,
        "error": None,
        "cached": False,
    }


def _warm_all_variants() -> None:
    global _warm_running
    with _warm_lock:
        if _warm_running:
            return
        _warm_running = True
    try:
        for slot, lines in GREET_LINES.items():
            for variant in range(len(lines)):
                if _read_cache(slot, variant):
                    continue
                _generate_variant(slot, variant)
    finally:
        with _warm_lock:
            _warm_running = False


@router.get("/kiosk/status")
def kiosk_status() -> dict:
    """Public for Agent screen polling — does not expose admin secrets."""
    return kiosk_state.get_status()


@router.get("/kiosk/status/lite")
def kiosk_status_lite() -> dict:
    """Frequent polling — omits session history for smaller payloads."""
    return kiosk_state.get_status_lite()


@router.post("/kiosk/start")
def kiosk_start(admin: dict = Depends(admin_auth.require_admin)) -> dict:
    _ = admin
    status = kiosk_state.start_kiosk()
    # Do NOT auto-warm greetings on start — that loads TTS on the GPU and
    # races the conversation pipeline (cudnn crashes / empty replies).
    # Warm offline with: python scripts/warm_greetings.py  (optional)
    return status


@router.post("/kiosk/stop")
def kiosk_stop(admin: dict = Depends(admin_auth.require_admin)) -> dict:
    _ = admin
    return kiosk_state.stop_kiosk()


@router.post("/kiosk/presence")
def kiosk_presence(body: PresenceBody) -> dict:
    return kiosk_state.set_presence(body.present)


@router.post("/kiosk/session/begin")
def kiosk_begin_session() -> dict:
    try:
        return kiosk_state.begin_session()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/kiosk/session/phase")
def kiosk_set_phase(body: PhaseBody) -> dict:
    try:
        return kiosk_state.set_phase(body.phase)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/kiosk/session/end")
def kiosk_end_session(body: EndBody | None = None) -> dict:
    note = body.note if body else ""
    return kiosk_state.end_session(note=note)


@router.post("/kiosk/session/end-admin")
def kiosk_end_session_admin(
    body: EndBody | None = None,
    admin: dict = Depends(admin_auth.require_admin),
) -> dict:
    _ = admin
    note = (body.note if body else "") or "Ended by admin"
    return kiosk_state.end_session(note=note)


@router.get("/kiosk/greetings")
def kiosk_greetings(
    hour: int | None = Query(default=None, ge=0, le=23),
    random_line: bool = Query(default=True, alias="random"),
) -> dict:
    """Full catalog + one picked line for the current time slot."""
    h = hour if hour is not None else None
    if random_line:
        current = pick_greeting(hour=h)
    else:
        current = pick_greeting(hour=h, variant=0)
    return {
        "current": current,
        "slot": current["slot"],
        "greetings": all_greetings(),
    }


@router.get("/kiosk/greet-audio")
def kiosk_greet_audio(
    slot: str | None = Query(default=None),
    hour: int | None = Query(default=None, ge=0, le=23),
    variant: int | None = Query(default=None, ge=0),
    random_line: bool = Query(default=True, alias="random"),
    generate: bool = Query(default=False, description="If uncached, generate now (slow)"),
) -> dict:
    """
    Time-based Kannada greeting — random full sentence from slot pool.

    Returns line_kn immediately; audio from remote Parler cache when available.
    """
    if slot and slot in GREET_LINES:
        if variant is not None:
            greet = pick_greeting(slot=slot, variant=variant)  # type: ignore[arg-type]
        elif random_line:
            greet = pick_greeting(slot=slot)  # type: ignore[arg-type]
        else:
            greet = pick_greeting(slot=slot, variant=0)  # type: ignore[arg-type]
    elif hour is not None:
        s = slot_for_hour(hour)
        if variant is not None:
            greet = pick_greeting(hour=hour, variant=variant)
        elif random_line:
            greet = pick_greeting(hour=hour)
        else:
            greet = pick_greeting(hour=hour, variant=0)
        slot = s
    else:
        if variant is not None:
            greet = pick_greeting(variant=variant)
        elif random_line:
            greet = pick_greeting()
        else:
            greet = pick_greeting(variant=0)
        slot = greet["slot"]

    assert slot is not None
    v = greet["variant"]
    cached = _read_cache(slot, v)
    if cached:
        return {**greet, "audio_b64": cached, "cached": True, "error": None}

    if not generate:
        return {
            **greet,
            "audio_b64": "",
            "cached": False,
            "error": None,
            "hint": "Uncached — agent uses /api/speak-kannada (remote Parler)",
        }

    payload = _generate_variant(slot, v)
    if payload.get("error") or not payload.get("audio_b64"):
        raise HTTPException(
            status_code=500,
            detail=payload.get("error") or "Greeting TTS failed",
        )
    return {**greet, **payload}
