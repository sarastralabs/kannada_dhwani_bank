"""Sarvam cloud providers: settings, routing, fallback to local models, key safety."""

from __future__ import annotations

import base64
import io
import json
import os
import urllib.error

import numpy as np
import pytest
import soundfile as sf

from backend import cloud
from backend.cloud import sarvam
from backend.cloud.sarvam import CloudError

_SPEECH_WAV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "stt_test_audio",
    "clip_001.wav",
)
_KEY = "sk_test_1234567890abcd"


def _wav_b64(seconds: float = 0.5, sr: int = 22050) -> str:
    buf = io.BytesIO()
    t = np.arange(int(seconds * sr)) / sr
    sf.write(buf, (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), sr, format="WAV")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("BANK_RUNTIME_SETTINGS_FILE", str(tmp_path / "runtime_settings.json"))
    monkeypatch.setenv("BANK_CLOUD_STATUS_FILE", str(tmp_path / "cloud_status.json"))
    monkeypatch.setenv("BANK_TTS_DISK_CACHE_DIR", str(tmp_path / "tts_cache"))
    monkeypatch.setenv("BANK_TTS_CACHE_VERSION", "test-cloud")
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    from backend.tts import speak_cache

    speak_cache._CACHE.clear()
    yield


# ── Error classification ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "body", "kind"),
    [
        (429, {"error": {"code": "insufficient_quota_error", "message": "No credits"}}, "quota"),
        (429, {"error": {"code": "rate_limit_exceeded_error", "message": "Slow down"}}, "rate_limit"),
        (403, {"error": {"code": "invalid_api_key_error", "message": "Invalid key"}}, "auth"),
        (401, {"message": "Unauthorized"}, "auth"),
        (500, {"error": {"code": "internal_server_error", "message": "boom"}}, "server"),
        (422, {"error": {"code": "unprocessable_entity_error", "message": "bad"}}, "bad_request"),
    ],
)
def test_errors_are_classified_for_staff(status, body, kind) -> None:
    assert sarvam._classify(status, json.dumps(body)).kind == kind


# ── Settings ──────────────────────────────────────────────────────────────────


def test_defaults_are_local_and_key_is_never_exposed() -> None:
    assert cloud.get_config()["stt"] == "local"
    cloud.save_config({"stt": "sarvam", "tts": "sarvam", "sarvam_api_key": _KEY})
    view = cloud.public_config()
    assert view["key_set"] is True
    assert view["key_hint"] == "…abcd"
    assert _KEY not in json.dumps(view)
    assert view["stages"]["stt"]["provider"] == "sarvam"
    assert view["stages"]["translation"]["provider"] == "local"


def test_settings_merge_with_voice_setting(tmp_path) -> None:
    from backend import runtime_settings

    runtime_settings.update({"speaker": "Anu"})
    cloud.save_config({"stt": "sarvam"})
    saved = json.loads((tmp_path / "runtime_settings.json").read_text(encoding="utf-8"))
    assert saved["speaker"] == "Anu"
    assert saved["cloud"]["stt"] == "sarvam"


def test_invalid_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        cloud.save_config({"stt": "openai"})
    with pytest.raises(ValueError):
        cloud.save_config({"sarvam_voice": "nobody"})
    with pytest.raises(ValueError):
        cloud.save_config({"sarvam_api_key": "has space"})


def test_env_key_used_when_none_saved_and_empty_removes_saved(monkeypatch) -> None:
    monkeypatch.setenv("SARVAM_API_KEY", "env_key_000011112222")
    assert cloud.public_config()["key_source"] == "env"
    cloud.save_config({"sarvam_api_key": _KEY})
    assert cloud.api_key() == _KEY
    cloud.save_config({"sarvam_api_key": ""})
    assert cloud.api_key() == "env_key_000011112222"


# ── Speech-to-text routing ────────────────────────────────────────────────────


def _forbid_local_stt(monkeypatch) -> None:
    import backend.stt as stt

    monkeypatch.setattr(stt, "warm_model", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("local STT used")))


def _fake_local_stt(monkeypatch, text: str = "LOCAL") -> None:
    import backend.stt as stt

    class _Fake:
        def transcribe(self, *_a, **_k):
            return text

    monkeypatch.setattr(stt, "warm_model", lambda *_a, **_k: "fake")
    monkeypatch.setitem(stt._model_cache, "fake", _Fake())


def test_stt_uses_sarvam_when_selected(monkeypatch) -> None:
    from backend.stt import transcribe

    cloud.save_config({"stt": "sarvam", "sarvam_api_key": _KEY})
    seen = {}
    monkeypatch.setattr(sarvam, "transcribe", lambda key, path, language="kn": seen.update(key=key, lang=language) or "ನಮಸ್ಕಾರ")
    _forbid_local_stt(monkeypatch)
    assert transcribe(_SPEECH_WAV, beam_size=3) == "ನಮಸ್ಕಾರ"
    assert seen == {"key": _KEY, "lang": "kn"}
    assert cloud.public_config()["stages"]["stt"]["ok"] is True


def test_stt_skips_cloud_for_silence(monkeypatch, tmp_path) -> None:
    from backend.stt import transcribe

    silent = tmp_path / "silent.wav"
    sf.write(silent, np.zeros(16000, dtype=np.float32), 16000)
    cloud.save_config({"stt": "sarvam", "sarvam_api_key": _KEY})
    monkeypatch.setattr(sarvam, "transcribe", lambda *a, **k: (_ for _ in ()).throw(AssertionError("billed silence")))
    assert transcribe(str(silent)) == ""


def test_credits_used_up_falls_back_and_blocks_until_new_key(monkeypatch) -> None:
    from backend.stt import transcribe

    cloud.save_config({"stt": "sarvam", "sarvam_api_key": _KEY})
    calls = {"n": 0}

    def no_credits(*_a, **_k):
        calls["n"] += 1
        raise CloudError("quota", "Sarvam credits are used up", 429)

    monkeypatch.setattr(sarvam, "transcribe", no_credits)
    _fake_local_stt(monkeypatch)

    assert transcribe(_SPEECH_WAV) == "LOCAL"
    assert transcribe(_SPEECH_WAV) == "LOCAL"
    assert calls["n"] == 1  # not retried while the same key is out of credits
    stage = cloud.public_config()["stages"]["stt"]
    assert stage["error_kind"] == "quota" and stage["using_local_now"] is True

    # Staff paste a new key → Sarvam is tried again.
    monkeypatch.setattr(sarvam, "transcribe", lambda *_a, **_k: "ಹೊಸ")
    cloud.save_config({"sarvam_api_key": "sk_test_new_key_9999"})
    assert transcribe(_SPEECH_WAV) == "ಹೊಸ"


def test_network_error_retries_after_cooldown(monkeypatch) -> None:
    from backend.stt import transcribe

    monkeypatch.setenv("BANK_CLOUD_RETRY_S", "0")
    cloud.save_config({"stt": "sarvam", "sarvam_api_key": _KEY})
    calls = {"n": 0}

    def offline(*_a, **_k):
        calls["n"] += 1
        raise CloudError("network", "Cannot reach Sarvam")

    monkeypatch.setattr(sarvam, "transcribe", offline)
    _fake_local_stt(monkeypatch)
    transcribe(_SPEECH_WAV)
    transcribe(_SPEECH_WAV)
    assert calls["n"] == 2


def test_no_fallback_raises_instead_of_using_local(monkeypatch) -> None:
    from backend.stt import transcribe

    cloud.save_config({"stt": "sarvam", "sarvam_api_key": _KEY, "fallback_local": False})
    monkeypatch.setattr(sarvam, "transcribe", lambda *_a, **_k: (_ for _ in ()).throw(CloudError("quota", "used up")))
    _forbid_local_stt(monkeypatch)
    with pytest.raises(CloudError):
        transcribe(_SPEECH_WAV)


def test_explicit_model_argument_stays_local(monkeypatch) -> None:
    from backend.stt import transcribe

    cloud.save_config({"stt": "sarvam", "sarvam_api_key": _KEY})
    monkeypatch.setattr(sarvam, "transcribe", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("cloud used")))
    _fake_local_stt(monkeypatch)
    assert transcribe(_SPEECH_WAV, model="vasista-medium") == "LOCAL"


# ── Translation routing ───────────────────────────────────────────────────────


def test_translation_uses_sarvam_both_directions(monkeypatch) -> None:
    import backend.translation as tr

    cloud.save_config({"translation": "sarvam", "sarvam_api_key": _KEY})
    seen = []
    monkeypatch.setattr(
        sarvam,
        "translate",
        lambda key, text, *, src_lang, tgt_lang: seen.append((src_lang, tgt_lang)) or "OK",
    )
    monkeypatch.setattr(tr, "warm_model", lambda *_a: (_ for _ in ()).throw(AssertionError("local used")))
    assert tr.translate_kn_to_en("ನಮಸ್ಕಾರ") == "OK"
    assert tr.translate_en_to_kn("Hello") == "OK"
    assert seen == [("kan_Knda", "eng_Latn"), ("eng_Latn", "kan_Knda")]


# ── Text-to-speech routing and cache separation ───────────────────────────────


def test_tts_uses_sarvam_with_its_own_cache(monkeypatch) -> None:
    from backend.tts import remote_bridge, speak_cache

    cloud.save_config({"tts": "sarvam", "sarvam_api_key": _KEY, "sarvam_voice": "ritu"})
    calls = []

    def fake_tts(key, text, *, voice=None):
        calls.append(voice)
        return np.full(11025, 0.1, dtype=np.float32), 22050

    monkeypatch.setattr(sarvam, "synthesise", fake_tts)
    monkeypatch.setattr(remote_bridge, "fetch_kannada_b64_remote", lambda *a, **k: (_ for _ in ()).throw(AssertionError("parler used")))
    monkeypatch.setattr(remote_bridge, "remote_tts_configured", lambda: True)

    first = speak_cache.kannada_to_b64("ನಮಸ್ಕಾರ", speaker="Suresh")
    second = speak_cache.kannada_to_b64("ನಮಸ್ಕಾರ", speaker="Suresh")
    assert first and first == second
    assert calls == ["ritu"]  # second call served from cache
    # A Parler clip of the same text must not be served for the Sarvam voice.
    assert speak_cache._cache_key("ನಮಸ್ಕಾರ", "Suresh") != speak_cache._cache_key(
        "ನಮಸ್ಕಾರ", profile="sarvam|bulbul:v3|ritu"
    )


def test_tts_falls_back_to_parler_when_sarvam_fails(monkeypatch) -> None:
    from backend.tts import remote_bridge, speak_cache

    monkeypatch.setenv("BANK_TTS_ENGINE", "remote")
    cloud.save_config({"tts": "sarvam", "sarvam_api_key": _KEY})
    monkeypatch.setattr(sarvam, "synthesise", lambda *a, **k: (_ for _ in ()).throw(CloudError("quota", "used up")))
    monkeypatch.setattr(remote_bridge, "remote_tts_configured", lambda: True)
    parler = _wav_b64()
    monkeypatch.setattr(remote_bridge, "fetch_kannada_b64_remote", lambda text, speaker=None: parler)
    assert speak_cache.kannada_to_b64("ನಮಸ್ಕಾರ", speaker="Suresh") == parler


# ── HTTP request shape (no network) ───────────────────────────────────────────


class _Resp:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *_a) -> None:
        return None


def test_requests_send_key_header_and_kannada_codes(monkeypatch) -> None:
    sent = []

    def fake_urlopen(req, timeout=None):
        sent.append(req)
        if req.full_url.endswith("/text-to-speech"):
            return _Resp({"audios": [_wav_b64()]})
        if req.full_url.endswith("/translate"):
            return _Resp({"translated_text": "Hello"})
        return _Resp({"transcript": "ನಮಸ್ಕಾರ"})

    monkeypatch.setattr(sarvam.urllib.request, "urlopen", fake_urlopen)
    assert sarvam.translate(_KEY, "ನಮಸ್ಕಾರ", src_lang="kan_Knda", tgt_lang="eng_Latn") == "Hello"
    audio, sr = sarvam.synthesise(_KEY, "ನಮಸ್ಕಾರ", voice="shubh")
    assert sr == 22050 and audio.size > 0
    assert sarvam.transcribe(_KEY, _SPEECH_WAV) == "ನಮಸ್ಕಾರ"

    for req in sent:
        assert req.get_header("Api-subscription-key") == _KEY
    translate_body = json.loads(sent[0].data)
    assert translate_body["source_language_code"] == "kn-IN"
    assert translate_body["target_language_code"] == "en-IN"
    tts_body = json.loads(sent[1].data)
    assert tts_body["speaker"] == "shubh" and tts_body["language_code"] == "kn-IN"
    assert b'name="language_code"\r\n\r\nkn-IN' in sent[2].data


def test_http_error_becomes_cloud_error(monkeypatch) -> None:
    def fail(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url,
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error": {"code": "insufficient_quota_error", "message": "Out of credits"}}'),
        )

    monkeypatch.setattr(sarvam.urllib.request, "urlopen", fail)
    with pytest.raises(CloudError) as info:
        sarvam.translate(_KEY, "ನಮಸ್ಕಾರ", src_lang="kan_Knda", tgt_lang="eng_Latn")
    assert info.value.kind == "quota"


def test_long_text_is_split_under_limit() -> None:
    text = "ಇದು ಒಂದು ವಾಕ್ಯ. " * 200
    pieces = sarvam._split_text(text, 300)
    assert all(len(p) <= 300 for p in pieces)
    assert "".join(pieces).replace(" ", "") == text.replace(" ", "")


# ── Admin API ─────────────────────────────────────────────────────────────────


def test_admin_cloud_routes(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from api import admin_auth
    from api.main import app

    app.dependency_overrides[admin_auth.require_admin] = lambda: {"username": "admin"}
    try:
        client = TestClient(app)
        r = client.put("/api/admin/settings/cloud", json={"tts": "sarvam", "sarvam_api_key": _KEY})
        assert r.status_code == 200
        assert _KEY not in r.text and r.json()["key_hint"] == "…abcd"
        assert client.put("/api/admin/settings/cloud", json={"stt": "bogus"}).status_code == 400

        monkeypatch.setattr(sarvam, "translate", lambda *a, **k: "Hello")
        monkeypatch.setattr(sarvam, "synthesise", lambda *a, **k: (np.full(4410, 0.1, dtype=np.float32), 22050))
        ok = client.post("/api/admin/settings/cloud/test", json={}).json()
        assert ok["ok"] is True and ok["audio_b64"]

        monkeypatch.setattr(sarvam, "translate", lambda *a, **k: (_ for _ in ()).throw(CloudError("auth", "bad key")))
        bad = client.post("/api/admin/settings/cloud/test", json={"sarvam_api_key": "sk_other_key_0000"}).json()
        assert bad == {"ok": False, "kind": "auth", "message": "bad key"}
        # Testing a different (unsaved) key must not mark the saved key as broken.
        assert client.get("/api/admin/settings/cloud").json()["stages"]["tts"]["ok"] is True
    finally:
        app.dependency_overrides.pop(admin_auth.require_admin, None)
