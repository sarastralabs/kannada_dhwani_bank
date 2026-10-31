"""Convert uploaded audio bytes to 16 kHz mono WAV for the pipeline."""

from __future__ import annotations

import io
import os
import tempfile

import numpy as np


def _audio_bytes_to_wav_pydub(audio_bytes: bytes) -> str:
    from pydub import AudioSegment

    buf = io.BytesIO(audio_bytes)
    audio = AudioSegment.from_file(buf)
    audio = audio.set_frame_rate(16000).set_channels(1)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio.export(tmp.name, format="wav")
    return tmp.name


def _audio_bytes_to_wav_av(audio_bytes: bytes) -> str:
    import av
    import soundfile as sf

    container = av.open(io.BytesIO(audio_bytes))
    if not container.streams.audio:
        raise ValueError("No audio stream found in uploaded file")

    resampler = av.audio.resampler.AudioResampler(format="fltp", layout="mono", rate=16000)
    chunks: list[np.ndarray] = []

    for frame in container.decode(audio=0):
        resampled = resampler.resample(frame)
        frames = resampled if isinstance(resampled, list) else [resampled]
        for resampled_frame in frames:
            if resampled_frame is None:
                continue
            arr = resampled_frame.to_ndarray()
            if arr.ndim > 1:
                arr = arr.mean(axis=0)
            chunks.append(arr.astype(np.float32))

    # Flush resampler
    for resampled_frame in resampler.resample(None) or []:
        if resampled_frame is None:
            continue
        arr = resampled_frame.to_ndarray()
        if arr.ndim > 1:
            arr = arr.mean(axis=0)
        chunks.append(arr.astype(np.float32))

    if not chunks:
        raise ValueError("No audio data found in uploaded file")

    audio = np.concatenate(chunks)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio, 16000)
    return tmp.name


def audio_bytes_to_wav(audio_bytes: bytes) -> str:
    """Convert any supported audio format to 16 kHz mono WAV temp file."""
    errors: list[str] = []

    try:
        return _audio_bytes_to_wav_pydub(audio_bytes)
    except Exception as exc:
        errors.append(f"pydub: {exc}")

    try:
        return _audio_bytes_to_wav_av(audio_bytes)
    except Exception as exc:
        errors.append(f"PyAV: {exc}")

    raise RuntimeError(
        "Could not convert audio to WAV. "
        + " | ".join(errors)
        + ". Try uploading a .wav file, or install ffmpeg for broader format support."
    )


def safe_unlink(path: str | None) -> None:
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass
