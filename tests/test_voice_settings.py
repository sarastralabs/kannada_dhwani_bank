"""Runtime voice selection must persist and reach every TTS process."""

from __future__ import annotations

import json

import numpy as np


def test_voice_setting_persists_atomically(tmp_path, monkeypatch) -> None:
    from api import app_settings

    settings_path = tmp_path / "runtime_settings.json"
    settings_path.write_text(json.dumps({"cloud": {"stt": "sarvam"}}), encoding="utf-8")
    monkeypatch.setenv("BANK_RUNTIME_SETTINGS_FILE", str(settings_path))
    previous = app_settings.get_tts_speaker()

    try:
        assert app_settings.set_tts_speaker("anu") == "Anu"
        assert app_settings.get_tts_speaker() == "Anu"
        # Other settings in the file (cloud providers) must survive a voice change.
        assert json.loads(settings_path.read_text(encoding="utf-8")) == {
            "cloud": {"stt": "sarvam"},
            "speaker": "Anu",
        }
    finally:
        app_settings.set_tts_speaker(previous)


def test_worker_voice_update_uses_control_message(monkeypatch) -> None:
    from backend import pipeline_bridge

    seen: dict = {}
    monkeypatch.setattr(pipeline_bridge, "worker_enabled", lambda: True)
    monkeypatch.setattr(
        pipeline_bridge,
        "_request",
        lambda payload: seen.update(payload) or {"ok": True, "speaker": payload["speaker"]},
    )

    assert pipeline_bridge.set_worker_speaker("Anu") == "Anu"
    assert seen == {"cmd": "set_speaker", "speaker": "Anu"}


def test_pipeline_tts_passes_runtime_speaker_to_remote(monkeypatch) -> None:
    from api import app_settings
    from backend import tts
    from backend.tts import parler_bridge, remote_bridge

    seen: dict[str, str | None] = {}
    monkeypatch.setattr(app_settings, "get_tts_speaker", lambda: "Anu")
    monkeypatch.setattr(remote_bridge, "remote_tts_configured", lambda: True)
    monkeypatch.setattr(parler_bridge, "parler_available", lambda: False)

    def fake_remote(text: str, *, speaker: str | None = None):
        seen.update(text=text, speaker=speaker)
        return np.zeros(160, dtype=np.float32), 16000

    monkeypatch.setattr(remote_bridge, "synthesise_kannada_remote", fake_remote)
    monkeypatch.setenv("BANK_TTS_ENGINE", "auto")

    result = tts.synthesise_kannada("ನಮಸ್ಕಾರ")
    assert result is not None
    assert seen == {"text": "ನಮಸ್ಕಾರ", "speaker": "Anu"}
