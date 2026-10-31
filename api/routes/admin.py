"""Admin login routes (separate from the lobby agent)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from api import admin_auth

router = APIRouter(tags=["admin"])


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class VoiceSettingsBody(BaseModel):
    speaker: str = Field(..., min_length=1, max_length=32)


@router.get("/admin/settings/voice")
def get_voice_settings(_admin: dict = Depends(admin_auth.require_admin)) -> dict:
    from api.app_settings import VALID_SPEAKERS, get_tts_speaker

    current = get_tts_speaker()
    return {
        "speaker": current,
        "options": [
            {
                "id": "Suresh",
                "label_en": "Suresh",
                "label_kn": "ಸುರೇಶ್",
                "description_en": "Warm, professional male voice — default for bank counter",
                "description_kn": "ಬ್ಯಾಂಕ್ ಕೌಂಟರ್‌ಗೆ ಸೂಕ್ತ — ವೃತ್ತಿಪರ ಪುರುಷ ಧ್ವನಿ",
            },
            {
                "id": "Anu",
                "label_en": "Anu",
                "label_kn": "ಅನು",
                "description_en": "Clear, expressive female voice",
                "description_kn": "ಸ್ಪಷ್ಟ, ಸಹಜ ಸ್ತ್ರೀ ಧ್ವನಿ",
            },
        ],
        "valid": sorted(VALID_SPEAKERS),
    }


@router.put("/admin/settings/voice")
def set_voice_settings(
    body: VoiceSettingsBody,
    _admin: dict = Depends(admin_auth.require_admin),
) -> dict:
    from api.app_settings import get_tts_speaker, set_tts_speaker
    from backend.pipeline_bridge import set_worker_speaker

    previous = get_tts_speaker()
    try:
        speaker = set_tts_speaker(body.speaker)
        set_worker_speaker(speaker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        try:
            set_tts_speaker(previous)
            set_worker_speaker(previous)
        except Exception:
            pass
        raise HTTPException(
            status_code=503,
            detail=f"Could not apply voice to the speech worker: {exc}",
        ) from exc
    return {"ok": True, "speaker": speaker}


class CloudSettingsBody(BaseModel):
    stt: str | None = Field(None, max_length=16)
    translation: str | None = Field(None, max_length=16)
    tts: str | None = Field(None, max_length=16)
    sarvam_voice: str | None = Field(None, max_length=32)
    fallback_local: bool | None = None
    # "" removes the saved key (falls back to SARVAM_API_KEY in .env, if any).
    sarvam_api_key: str | None = Field(None, max_length=256)


class CloudTestBody(BaseModel):
    # Test a key before saving it; omit to test the saved key.
    sarvam_api_key: str | None = Field(None, max_length=256)
    sarvam_voice: str | None = Field(None, max_length=32)


_CLOUD_TEST_KN = "ನಮಸ್ಕಾರ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?"


@router.get("/admin/settings/cloud")
def get_cloud_settings(_admin: dict = Depends(admin_auth.require_admin)) -> dict:
    from backend import cloud

    return cloud.public_config()


@router.put("/admin/settings/cloud")
def set_cloud_settings(
    body: CloudSettingsBody,
    _admin: dict = Depends(admin_auth.require_admin),
) -> dict:
    from backend import cloud

    changes = body.model_dump(exclude_none=True)
    if changes.get("tts") == "local" and not cloud.open_source_voice_online():
        raise HTTPException(
            status_code=409,
            detail="The open-source voice server is offline. Start it first, then switch Speaking to Open-source.",
        )
    try:
        cloud.save_config(changes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **cloud.public_config()}


@router.post("/admin/settings/cloud/test")
def test_cloud_settings(
    body: CloudTestBody,
    _admin: dict = Depends(admin_auth.require_admin),
) -> dict:
    """Translate and speak one short phrase with Sarvam (uses a few credits)."""
    import base64
    import io
    import time

    import soundfile as sf

    from backend import cloud
    from backend.cloud import sarvam

    candidate = (body.sarvam_api_key or "").strip()
    key = candidate or cloud.api_key()
    if not key:
        return {"ok": False, "kind": "auth", "message": "No Sarvam API key is set yet."}
    voice = (body.sarvam_voice or cloud.get_config()["sarvam_voice"]).strip().lower()
    if voice not in sarvam.TTS_VOICES:
        raise HTTPException(status_code=400, detail=f"Unknown Sarvam voice {voice!r}.")
    # Only the key in use updates the shared status (unblocks stages after a fix).
    is_current = cloud.key_fingerprint(key) == cloud.key_fingerprint()

    started = time.perf_counter()
    try:
        english = sarvam.translate(key, _CLOUD_TEST_KN, src_lang="kan_Knda", tgt_lang="eng_Latn")
        if is_current:
            cloud.record_ok("translation", round((time.perf_counter() - started) * 1000))
        started = time.perf_counter()
        audio, sr = sarvam.synthesise(key, _CLOUD_TEST_KN, voice=voice)
        if is_current:
            cloud.record_ok("tts", round((time.perf_counter() - started) * 1000))
            # STT uses the same key and credits — a working key clears its error too.
            cloud.record_ok("stt", 0)
    except sarvam.CloudError as exc:
        if is_current:
            for stage in cloud.STAGES:
                cloud.record_error(stage, exc)
        return {"ok": False, "kind": exc.kind, "message": str(exc)}

    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return {
        "ok": True,
        "kind": None,
        "message": "The key works.",
        "translation": english,
        "audio_b64": base64.b64encode(buf.getvalue()).decode("ascii"),
    }


@router.post("/admin/login")
def admin_login(body: LoginBody) -> dict:
    try:
        return admin_auth.login(body.username.strip(), body.password)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/admin/me")
def admin_me(admin: dict = Depends(admin_auth.require_admin)) -> dict:
    return {**admin, "demo_mode": True}


@router.post("/admin/logout")
def admin_logout(authorization: str | None = Header(default=None)) -> dict:
    admin_auth.logout(authorization)
    return {"ok": True}


@router.get("/admin/customers")
def admin_customers(
    limit: int = 100,
    _admin: dict = Depends(admin_auth.require_admin),
) -> dict:
    from backend.db.customers import list_balance_audit, list_customers, store_mode

    _ = _admin
    return {
        "store": store_mode(),
        "customers": list_customers(limit=limit),
        "balance_audit": list_balance_audit(limit=40),
    }


@router.get("/admin/conversation-flow")
def admin_conversation_flow(_admin: dict = Depends(admin_auth.require_admin)) -> dict:
    from backend.admin_flow import build_conversation_flow

    _ = _admin
    return build_conversation_flow()


@router.get("/admin/history")
def admin_history(
    limit: int = 50,
    _admin: dict = Depends(admin_auth.require_admin),
) -> dict:
    from backend.db import store

    _ = _admin
    items = store.list_queries(limit=max(1, min(limit, 200)))
    return {"items": items, "count": len(items)}


@router.get("/admin/history/{item_id}")
def admin_history_item(
    item_id: str,
    _admin: dict = Depends(admin_auth.require_admin),
) -> dict:
    from backend.db import store

    _ = _admin
    item = store.get_query(item_id, include_audio=True)
    if not item:
        raise HTTPException(status_code=404, detail="History item not found")
    return item
