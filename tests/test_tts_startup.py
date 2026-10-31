"""Dedicated TTS service startup and speaker isolation tests."""

import importlib

import anyio
import pytest
from pydantic import ValidationError


def _tts_main():
    """Import the isolated TTS service only when a TTS test actually runs."""
    return importlib.import_module("api.tts_main")


def test_lifespan_warms_model_and_phrases(monkeypatch) -> None:
    tts_main = _tts_main()
    calls: list[str] = []
    monkeypatch.setattr(
        tts_main,
        "warm_parler_service",
        lambda: calls.append("warm")
        or {
            "ok": True,
            "ready": True,
            "phrases_cached": 4,
            "speaker": "Suresh",
        },
    )
    monkeypatch.setattr(
        tts_main,
        "ensure_parler_ready",
        lambda: True,
    )
    monkeypatch.setattr(
        tts_main,
        "stop_worker",
        lambda: calls.append("stop"),
    )

    async def run() -> None:
        async with tts_main._lifespan(tts_main.app):
            assert tts_main._warm_stats["model_ready"] is True
            assert tts_main._warm_stats["phrases_cached"] == 4
            assert tts_main._warm_stats["cache_warm"] == "startup-prewarm"

    anyio.run(run)
    assert calls == ["warm", "stop"]


def test_requested_speaker_is_passed_explicitly(monkeypatch) -> None:
    tts_main = _tts_main()
    seen: dict[str, str] = {}
    monkeypatch.setattr(tts_main, "get_cached_b64", lambda *_args, **_kwargs: None)

    def fake_synth(text: str, *, speaker: str) -> str:
        seen.update(text=text, speaker=speaker)
        return "audio"

    monkeypatch.setattr(tts_main, "kannada_to_b64", fake_synth)
    audio, cached = tts_main._synth_b64("ನಮಸ್ಕಾರ", "Anu")

    assert audio == "audio"
    assert cached is False
    assert seen == {"text": "ನಮಸ್ಕಾರ", "speaker": "Anu"}


def test_benchmark_can_bypass_tts_cache(monkeypatch) -> None:
    tts_main = _tts_main()
    seen: dict = {}
    monkeypatch.setattr(
        tts_main,
        "get_cached_b64",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cache should not be read")
        ),
    )

    def fake_synth(text: str, **kwargs) -> str:
        seen.update(text=text, **kwargs)
        return "fresh-audio"

    monkeypatch.setattr(tts_main, "kannada_to_b64", fake_synth)
    audio, cached = tts_main._synth_b64(
        "ನಮಸ್ಕಾರ",
        "Suresh",
        bypass_cache=True,
    )

    assert audio == "fresh-audio"
    assert cached is False
    assert seen["bypass_cache"] is True


def test_tts_api_rejects_unknown_speaker() -> None:
    tts_main = _tts_main()
    with pytest.raises(ValidationError):
        tts_main.SpeakBody(text="ನಮಸ್ಕಾರ", speaker="Unknown")
