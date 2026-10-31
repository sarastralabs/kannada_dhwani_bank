"""An empty Parler clip must never be cached (it would make that phrase silent forever)."""
from __future__ import annotations

import base64
import io

import numpy as np
import pytest
import soundfile as sf


def _wav_b64(seconds: float, sr: int = 44100) -> str:
    n = max(1, int(sr * seconds))
    buf = io.BytesIO()
    sf.write(buf, (np.random.default_rng(0).standard_normal(n) * 0.1).astype(np.float32), sr, format="WAV")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture()
def cache(tmp_path, monkeypatch):
    from backend.tts import speak_cache

    monkeypatch.setenv("BANK_TTS_DISK_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(speak_cache, "_CACHE", {})
    return speak_cache


def test_one_sample_clip_is_not_cached(cache) -> None:
    cache.put_cached_b64("ಐದು ಸಾವಿರ ರೂಪಾಯಿ", _wav_b64(0), speaker="Anu", persist=True)
    assert cache.get_cached_b64("ಐದು ಸಾವಿರ ರೂಪಾಯಿ", speaker="Anu") is None


def test_normal_clip_is_cached(cache) -> None:
    b64 = _wav_b64(0.8)
    cache.put_cached_b64("ಹೌದು", b64, speaker="Anu", persist=True)
    assert cache.get_cached_b64("ಹೌದು", speaker="Anu") == b64


def test_empty_clip_already_on_disk_is_ignored(cache, tmp_path) -> None:
    key = cache._cache_key("ನಗದು", "Suresh")
    (tmp_path / f"{key}.wav").write_bytes(base64.b64decode(_wav_b64(0)))
    assert cache.get_cached_b64("ನಗದು", speaker="Suresh") is None
