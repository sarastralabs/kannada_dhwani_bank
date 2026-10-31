"""Trim trailing silence from TTS WAV output (Parler often pads short phrases)."""

from __future__ import annotations

import base64
import io

import numpy as np
import soundfile as sf


def trim_trailing_silence(
    audio: np.ndarray,
    sr: int,
    *,
    threshold: float = 0.01,
    pad_ms: int = 250,
) -> np.ndarray:
    """Keep speech plus a short tail pad; drop long Parler silence tails."""
    if audio.size == 0:
        return audio
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    idx = np.where(np.abs(mono) > threshold)[0]
    if idx.size == 0:
        return audio
    end = min(len(mono), int(idx[-1]) + int(sr * pad_ms / 1000))
    # Never collapse a long synth to a tiny clip if speech is very quiet
    min_keep = int(sr * 1.5)
    if end < min_keep and len(mono) >= min_keep:
        # Quiet start: keep from first hit, but require at least 1.5s if available
        start = max(0, int(idx[0]) - int(sr * 0.05))
        end = max(end, min(len(mono), start + min_keep))
    return audio[:end]


def trim_wav_b64(b64: str, *, threshold: float = 0.01, pad_ms: int = 250) -> str:
    """Decode WAV b64, trim silence, re-encode."""
    if not b64:
        return b64
    raw = base64.b64decode(b64)
    audio, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
    trimmed = trim_trailing_silence(np.asarray(audio, dtype=np.float32), int(sr), threshold=threshold, pad_ms=pad_ms)
    buf = io.BytesIO()
    sf.write(buf, trimmed, sr, format="WAV")
    return base64.b64encode(buf.getvalue()).decode("ascii")
