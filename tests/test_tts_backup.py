"""Voice server down → Sarvam speaks; Speaking cannot be switched to it while it is down."""

from __future__ import annotations

import numpy as np
import pytest

from backend import cloud
from backend.cloud import sarvam
from backend.tts import remote_bridge, speak_cache


@pytest.fixture
def remote_voice(monkeypatch):
    """Kiosk set up with a remote open-source voice server; health is controlled per test."""
    monkeypatch.setenv("BANK_TTS_ENGINE", "remote")
    monkeypatch.setenv("BANK_TTS_REMOTE_URL", "https://voice.example.test")
    monkeypatch.setattr(speak_cache, "get_cached_b64", lambda *a, **k: None)
    monkeypatch.setattr(speak_cache, "put_cached_b64", lambda *a, **k: None)
    calls = {"remote": 0, "sarvam": 0}

    def fake_remote(text, speaker=None):
        calls["remote"] += 1
        return "UkVNT1RF"

    def fake_sarvam(key, text, voice=None):
        calls["sarvam"] += 1
        return np.zeros(1600, dtype=np.float32), 16000

    monkeypatch.setattr(remote_bridge, "fetch_kannada_b64_remote", fake_remote)
    monkeypatch.setattr(sarvam, "synthesise", fake_sarvam)
    return calls


def _health(monkeypatch, up: bool) -> None:
    monkeypatch.setattr(remote_bridge, "remote_tts_healthy", lambda timeout_s=None: up)


def test_voice_server_up_uses_open_source(monkeypatch, remote_voice):
    _health(monkeypatch, True)
    monkeypatch.setenv("SARVAM_API_KEY", "sk_test")
    assert speak_cache.kannada_to_b64("ನಮಸ್ಕಾರ") == "UkVNT1RF"
    assert remote_voice == {"remote": 1, "sarvam": 0}


def test_voice_server_down_uses_sarvam(monkeypatch, remote_voice):
    _health(monkeypatch, False)
    monkeypatch.setenv("SARVAM_API_KEY", "sk_test")
    b64 = speak_cache.kannada_to_b64("ನಮಸ್ಕಾರ")
    assert b64 and b64 != "UkVNT1RF"
    assert remote_voice == {"remote": 0, "sarvam": 1}


def test_voice_server_fails_mid_request_uses_sarvam(monkeypatch, remote_voice):
    _health(monkeypatch, True)
    monkeypatch.setenv("SARVAM_API_KEY", "sk_test")

    def broken(text, speaker=None):
        raise RuntimeError("530 tunnel down")

    monkeypatch.setattr(remote_bridge, "fetch_kannada_b64_remote", broken)
    assert speak_cache.kannada_to_b64("ನಮಸ್ಕಾರ")
    assert remote_voice["sarvam"] == 1


def test_voice_server_down_without_key_still_reports_the_error(monkeypatch, remote_voice):
    _health(monkeypatch, False)

    def broken(text, speaker=None):
        raise RuntimeError("530 tunnel down")

    monkeypatch.setattr(remote_bridge, "fetch_kannada_b64_remote", broken)
    with pytest.raises(RuntimeError, match="530"):
        speak_cache.kannada_to_b64("ನಮಸ್ಕಾರ")
    assert remote_voice["sarvam"] == 0


def test_cannot_switch_speaking_to_open_source_while_offline(monkeypatch):
    from fastapi import HTTPException

    from api.routes import admin

    monkeypatch.setattr(cloud, "open_source_voice_online", lambda: False)
    with pytest.raises(HTTPException) as exc:
        admin.set_cloud_settings(admin.CloudSettingsBody(tts="local"), {})
    assert exc.value.status_code == 409

    # Other changes still save while the voice server is down.
    monkeypatch.setattr(cloud, "open_source_voice_online", lambda: False)
    out = admin.set_cloud_settings(admin.CloudSettingsBody(tts="sarvam"), {})
    assert out["stages"]["tts"]["provider"] == "sarvam"
    assert out["open_source_voice_online"] is False


def test_can_switch_speaking_to_open_source_when_online(monkeypatch):
    from api.routes import admin

    monkeypatch.setattr(cloud, "open_source_voice_online", lambda: True)
    out = admin.set_cloud_settings(admin.CloudSettingsBody(tts="local"), {})
    assert out["stages"]["tts"]["provider"] == "local"
