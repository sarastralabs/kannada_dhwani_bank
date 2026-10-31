"""
backend/stt/utils.py

Audio validation helpers for the STT module.
These functions run before any model inference so bad inputs are rejected
early with clear, catchable errors.
"""

import os
from typing import Optional

import numpy as np
import soundfile as sf

from backend.stt.exceptions import STTInputError

# Only .wav is accepted in this phase (Whisper's native format at 16 kHz mono).
# Extending to other formats would require a resampling step not in scope here.
_SUPPORTED_EXTENSIONS = {".wav"}


def validate_audio_file(path: str) -> None:
    """
    Validate that *path* points to a readable, supported audio file.

    Checks performed (in order):
    1. The file exists on disk.
    2. The file extension is ``.wav``.
    3. The file can be opened by soundfile (detects corruption / truncation).

    Parameters
    ----------
    path:
        Filesystem path to the audio file to validate.

    Raises
    ------
    STTInputError
        On any of the three failure conditions above, with a human-readable
        message describing what went wrong.
    """
    # --- 1. Existence check ---
    if not os.path.exists(path):
        raise STTInputError(
            f"Audio file not found: '{path}'. "
            "Check that the path is correct and the file has been saved."
        )

    # --- 2. Extension check ---
    _, ext = os.path.splitext(path)
    if ext.lower() not in _SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(_SUPPORTED_EXTENSIONS))
        raise STTInputError(
            f"Unsupported audio format '{ext}' for file '{path}'. "
            f"Only {supported} files are accepted in this phase."
        )

    # --- 3. Readability / corruption check ---
    try:
        sf.info(path)
    except Exception as exc:
        raise STTInputError(
            f"Could not read audio file '{path}'. "
            f"The file may be corrupted or incomplete. "
            f"Underlying error: {exc}"
        ) from exc


def is_silent(
    audio_array: np.ndarray,
    threshold: float = 0.01,
) -> bool:
    """
    Return ``True`` if the audio clip contains no meaningful speech signal.

    Uses the Root Mean Square (RMS) energy of the waveform as a simple
    silence detector.  A clip whose RMS falls below *threshold* is treated
    as silent — the transcriber will return an empty string instead of
    running full model inference.

    Parameters
    ----------
    audio_array:
        1-D float32 NumPy array of audio samples (values in [-1.0, 1.0]).
    threshold:
        RMS energy below which the clip is considered silent.
        Default ``0.01`` works for 16-bit PCM data normalised to [-1, 1].
        Increase if short breath-sounds are triggering false-positives;
        decrease if soft speech is being missed.

    Returns
    -------
    bool
        ``True`` if the clip is silent, ``False`` if it contains speech.

    Notes
    -----
    This is a lightweight pre-check only.  ``faster-whisper``'s built-in
    ``vad_filter=True`` provides more robust silence/speech segmentation
    inside the model pipeline.
    """
    if audio_array.size == 0:
        return True

    rms = float(np.sqrt(np.mean(audio_array.astype(np.float64) ** 2)))
    return rms < threshold
