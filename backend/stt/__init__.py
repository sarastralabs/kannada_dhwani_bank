"""
backend/stt/__init__.py

Public API for the Kannada STT module.

Quick-start
-----------
    from backend.stt import transcribe

    # Uses BANK_STT_MODEL (vasista-medium by default)
    text = transcribe("data/stt_test_audio/clip_001.wav")

    # Explicit rollback to the previous VAANI model
    text = transcribe("data/stt_test_audio/clip_001.wav", model="specialized")

    # Use beam_size=5 for accuracy-critical paths (slower on CPU)
    text = transcribe("path/to/clip.wav", beam_size=5)

Models are loaded once and cached for the lifetime of the process.
Subsequent calls to transcribe() with the same model name reuse the
already-loaded instance, avoiding the 2–5 second reload cost.
"""

from __future__ import annotations

import os
import warnings
from typing import Literal

from backend.stt.exceptions import STTInputError
from backend.stt.transcriber import KannadaTranscriber

__all__ = ["transcribe", "warm_model", "unload_model", "STTInputError"]

# ---------------------------------------------------------------------------
# Model path configuration
# All paths are relative to the project root.  Resolve to absolute so the
# module works regardless of the caller's working directory.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

MODEL_PATHS: dict[str, str] = {
    "baseline": os.path.join(_PROJECT_ROOT, "models", "whisper-medium-ct2"),
    "specialized": os.path.join(_PROJECT_ROOT, "models", "whisper-medium-vaani-ct2"),
    "vasista-medium": os.path.join(_PROJECT_ROOT, "models", "whisper-kannada-medium-ct2"),
}
ModelName = Literal["baseline", "specialized", "vasista-medium"]
DEFAULT_MODEL: ModelName = "vasista-medium"

# ---------------------------------------------------------------------------
# Singleton cache — keyed by model name
# ---------------------------------------------------------------------------
_model_cache: dict[str, KannadaTranscriber] = {}


def active_model_name() -> ModelName:
    """Resolve the environment-selected production model."""
    selected = os.environ.get("BANK_STT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if selected not in MODEL_PATHS:
        valid = ", ".join(f'"{key}"' for key in MODEL_PATHS)
        raise ValueError(
            f"Unknown BANK_STT_MODEL '{selected}'. Valid options are: {valid}."
        )
    return selected  # type: ignore[return-value]


def _resolve_model(model: ModelName | None) -> ModelName:
    selected = model or active_model_name()
    path = MODEL_PATHS[selected]
    if (
        model is None
        and selected == DEFAULT_MODEL
        and not os.path.isdir(path)
        and os.path.isdir(MODEL_PATHS["specialized"])
    ):
        warnings.warn(
            "Default Vasista STT model is not converted yet; using the existing "
            "specialized model. Run convert_models.py --model vasista-medium.",
            stacklevel=3,
        )
        return "specialized"
    return selected


def warm_model(model: ModelName | None = None) -> ModelName:
    """Load and cache the selected STT model without transcribing audio."""
    selected = _resolve_model(model)
    if selected not in _model_cache:
        _model_cache[selected] = KannadaTranscriber(MODEL_PATHS[selected])
    return selected


def transcribe(
    audio_path: str,
    model: ModelName | None = None,
    beam_size: int = 1,
    *,
    initial_prompt: str | None = None,
    hotwords: str | None = None,
    language: Literal["kn", "en"] = "kn",
) -> str:
    """
    Transcribe a Kannada ``.wav`` file and return the Kannada text.

    This is the primary entry-point for downstream pipeline modules
    (Translation, NLU, etc.).  It lazily loads the requested model on the
    first call and reuses it on subsequent calls.

    Parameters
    ----------
    audio_path:
        Path to the ``.wav`` audio file to transcribe.
    model:
        Which model to use. When omitted, ``BANK_STT_MODEL`` selects it:

        - ``"vasista-medium"`` (default) — ``vasista22/whisper-kannada-medium``.
        - ``"specialized"`` — ``ARTPARK-IISc/whisper-medium-vaani-kannada``
          retained for rollback.
        - ``"baseline"`` — ``openai/whisper-medium``, the generic multilingual
          model.  Use this for benchmarking comparison only.
    beam_size:
        Beam search width.  ``1`` (default) is fast enough for real-time use
        on CPU.  Pass ``5`` for benchmark accuracy runs.

    Returns
    -------
    str
        Transcribed Kannada text, or ``""`` for silent/speech-free clips.

    Raises
    ------
    ValueError
        If *model* is not one of the recognised model names.
    STTInputError
        If the audio file is missing, unsupported, or corrupted.
    FileNotFoundError
        If the model directory has not been created yet.
        Run ``python backend/stt/convert_models.py --model vasista-medium`` first.
    """
    # Sarvam cloud STT when staff selected it in the admin console. The explicit
    # ``model`` argument (benchmarks) always means the local model.
    if model is None:
        cloud_text = _transcribe_cloud(audio_path, language)
        if cloud_text is not None:
            return cloud_text

    selected = warm_model(model)

    field_hints: dict[str, str] = {}
    if initial_prompt:
        field_hints["initial_prompt"] = initial_prompt
    if hotwords:
        field_hints["hotwords"] = hotwords
    if language != "kn":
        field_hints["language"] = language
    return _model_cache[selected].transcribe(
        audio_path,
        beam_size=beam_size,
        **field_hints,
    )


def _transcribe_cloud(audio_path: str, language: str) -> str | None:
    """Sarvam transcript, or None to use the local model (not selected / failed)."""
    from backend import cloud

    if not cloud.cloud_selected("stt"):
        return None
    if not cloud.use_cloud("stt"):
        if cloud.fallback_allowed():
            return None
        raise cloud.unavailable_error("speech-to-text")

    import soundfile as sf

    from backend.stt.utils import is_silent, validate_audio_file

    validate_audio_file(audio_path)
    audio_array, _sr = sf.read(audio_path, dtype="float32", always_2d=False)
    if is_silent(audio_array):
        return ""  # never spend credits on silence

    from backend.cloud import sarvam

    try:
        return cloud.call_cloud(
            "stt",
            lambda key: sarvam.transcribe(key, audio_path, language=language),
        )
    except Exception:
        if cloud.fallback_allowed():
            return None
        raise


def unload_model(model: ModelName | Literal["all"] | None = None) -> None:
    """
    Release the cached STT model from memory.

    Deletes the actual KannadaTranscriber object from the module-level
    _model_cache dict and frees GPU/CPU memory. Call this after
    transcription is complete in a memory-constrained pipeline.

    Parameters
    ----------
    model:
        A registered model, ``None`` for the active model, or ``"all"``.
    """
    import gc
    import torch

    global _model_cache
    keys = (
        list(_model_cache.keys())
        if model == "all"
        else [_resolve_model(model)]
    )
    for key in keys:
        if key in _model_cache:
            del _model_cache[key]
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
