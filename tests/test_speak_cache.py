"""TTS cache concurrency, privacy, and restart behavior."""

from __future__ import annotations

import base64
import io
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import soundfile as sf

from backend.tts import speak_cache

# A real 0.5 s WAV — the cache refuses empty/too-short clips.
_buf = io.BytesIO()
sf.write(_buf, np.zeros(22050, dtype=np.float32), 44100, format="WAV")
_WAV = _buf.getvalue()
_WAV_B64 = base64.b64encode(_WAV).decode("ascii")


def _configure(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BANK_TTS_DISK_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("BANK_TTS_ENGINE", "remote")
    monkeypatch.setenv("BANK_TTS_REMOTE_URL", "https://tts.invalid")
    monkeypatch.setenv("BANK_TTS_CACHE_VERSION", "test")
    speak_cache._CACHE.clear()


def test_static_disk_cache_survives_memory_clear(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    speak_cache.put_cached_b64(
        "ಸ್ಥಿರ ಸಂದೇಶ",
        _WAV_B64,
        speaker="Suresh",
        persist=True,
    )
    speak_cache._CACHE.clear()
    assert speak_cache.get_cached_b64("ಸ್ಥಿರ ಸಂದೇಶ", speaker="Suresh") == _WAV_B64
    assert speak_cache.get_cached_b64("ಸ್ಥಿರ ಸಂದೇಶ", speaker="Anu") is None


def test_dynamic_audio_is_not_written_to_disk(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    speak_cache.put_cached_b64(
        "ಖಾತೆಯ ಖಾಸಗಿ ಮಾಹಿತಿ",
        _WAV_B64,
        speaker="Suresh",
        persist=False,
    )
    assert list(tmp_path.iterdir()) == []


def test_concurrent_identical_misses_synthesise_once(monkeypatch, tmp_path) -> None:
    _configure(monkeypatch, tmp_path)
    calls = 0

    def fake_remote(_text: str, *, speaker: str | None = None) -> str:
        nonlocal calls
        calls += 1
        time.sleep(0.03)
        return _WAV_B64

    monkeypatch.setattr(
        "backend.tts.remote_bridge.fetch_kannada_b64_remote",
        fake_remote,
    )
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(
            pool.map(
                lambda _index: speak_cache.kannada_to_b64(
                    "ಒಂದೇ ಸಂದೇಶ",
                    speaker="Suresh",
                ),
                range(12),
            )
        )

    assert results == [_WAV_B64] * 12
    assert calls == 1


def test_prewarm_uses_explicit_speaker(monkeypatch) -> None:
    seen: list[tuple[str, str, bool]] = []
    monkeypatch.setattr(speak_cache, "get_cached_b64", lambda *_args, **_kwargs: None)

    def fake_synth(text: str, *, speaker: str, persist: bool, **_kwargs) -> str:
        seen.append((text, speaker, persist))
        return _WAV_B64

    monkeypatch.setattr(speak_cache, "kannada_to_b64", fake_synth)

    assert speak_cache.prewarm_phrases(["ಸ್ಥಿರ ಸಂದೇಶ"], speaker="Anu") == 1
    assert seen == [("ಸ್ಥಿರ ಸಂದೇಶ", "Anu", True)]
