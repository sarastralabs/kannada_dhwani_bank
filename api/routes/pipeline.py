"""Pipeline HTTP routes."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api import system_status
from api.audio import audio_bytes_to_wav, safe_unlink
from backend.db import store
from backend.pipeline_bridge import (
    fill_field,
    oneshot_fill,
    oneshot_process,
    process_wav,
    transcribe_wav,
    worker_enabled,
)

router = APIRouter()


class SpeakBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    speaker: Literal["Suresh", "Anu"] | None = Field(
        default=None,
        description="Suresh or Anu",
    )


def _parse_context_json(raw: str) -> dict:
    if not raw or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid context JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="context must be a JSON object")
    return parsed


@router.post("/speak-kannada")
async def speak_kannada(body: SpeakBody) -> dict:
    """Synthesise Kannada speech (remote Parler when configured)."""
    from api.app_settings import get_tts_speaker
    from backend.tts.speak_cache import kannada_to_b64

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")
    speaker = (body.speaker or "").strip() or get_tts_speaker()
    try:
        audio_b64 = await asyncio.to_thread(
            kannada_to_b64,
            text,
            speaker=speaker,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS failed: {exc}") from exc
    if not audio_b64:
        raise HTTPException(status_code=500, detail="TTS returned empty audio")
    return {"text": text, "audio_b64": audio_b64, "speaker": speaker, "engine": "remote-parler"}


@router.post("/transcribe-audio")
async def transcribe_audio(audio: UploadFile = File(...)) -> dict:
    """STT + translation only — fast path for form menu selection."""
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file provided")

    raw_bytes = await audio.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    tmp_wav: str | None = None
    try:
        tmp_wav = audio_bytes_to_wav(raw_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Audio conversion failed: {exc}") from exc

    try:
        if worker_enabled():
            try:
                result = await asyncio.to_thread(transcribe_wav, tmp_wav)
            except Exception as warm_exc:
                print(f"[pipeline] transcribe warm worker failed: {warm_exc}", file=sys.stderr)

                def _oneshot_transcribe() -> dict:
                    from backend.stt import transcribe
                    from backend.translation import translate_kn_to_en

                    kn = transcribe(tmp_wav, beam_size=3) or ""
                    en = translate_kn_to_en(kn) if kn.strip() else ""
                    return {
                        "kannada_text": kn,
                        "english_text": en,
                        "error": None if kn.strip() else "STT returned empty",
                    }

                result = await asyncio.to_thread(_oneshot_transcribe)
        else:

            def _transcribe() -> dict:
                from backend.stt import transcribe
                from backend.translation import translate_kn_to_en

                kn = transcribe(tmp_wav, beam_size=1) or ""
                en = translate_kn_to_en(kn) if kn.strip() else ""
                return {
                    "kannada_text": kn,
                    "english_text": en,
                    "error": None if kn.strip() else "STT returned empty",
                }

            result = await asyncio.to_thread(_transcribe)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcribe failed: {exc}") from exc
    finally:
        safe_unlink(tmp_wav)

    return result


@router.post("/process-audio")
async def process_audio(
    audio: UploadFile = File(...),
    context: str = Form(""),
    kiosk_session_id: str = Form(""),
    include_audio: bool = Form(True),
) -> dict:
    """Accept audio upload, run pipeline (warm worker by default), return JSON."""
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file provided")

    raw_bytes = await audio.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    ctx = _parse_context_json(context)
    from api.app_settings import get_tts_speaker

    tts_speaker = get_tts_speaker()
    if kiosk_session_id.strip():
        ctx["kiosk_session_id"] = kiosk_session_id.strip()

    tmp_wav: str | None = None
    try:
        tmp_wav = audio_bytes_to_wav(raw_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Audio conversion failed: {exc}") from exc

    try:
        if worker_enabled():
            try:
                result = await asyncio.to_thread(
                    process_wav,
                    tmp_wav,
                    ctx or None,
                    include_audio=include_audio,
                )
            except Exception as warm_exc:
                print(f"[pipeline] warm worker failed, oneshot fallback: {warm_exc}", file=sys.stderr)
                result = await asyncio.to_thread(
                    oneshot_process,
                    tmp_wav,
                    ctx or None,
                    include_audio=include_audio,
                )
        else:
            result = await asyncio.to_thread(
                oneshot_process,
                tmp_wav,
                ctx or None,
                include_audio=include_audio,
            )
    except Exception as exc:
        system_status.record(False, str(exc))
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {exc}") from exc
    finally:
        safe_unlink(tmp_wav)

    system_status.record(not result.get("error"), result.get("error"))
    if result.get("error"):
        result["error_code"] = system_status.classify_error(result.get("error"))
    if ctx.get("kiosk_session_id"):
        result["kiosk_session_id"] = ctx["kiosk_session_id"]
    result["tts_speaker"] = tts_speaker

    if not result.get("error"):
        try:
            saved = store.save_query(result)
            result["history_id"] = saved["id"]
        except Exception as exc:
            print(f"[history] save failed: {exc}", file=sys.stderr)
            result["history_id"] = None

    return result
