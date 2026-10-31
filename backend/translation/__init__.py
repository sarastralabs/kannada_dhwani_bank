"""
backend/translation/__init__.py

Public API for the Kannada ↔ English Translation module.

Quick-start
-----------
    from backend.translation import translate

    # Kannada → English  (STT output → NLU input)
    en = translate("ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟಿದೆ")
    # "What is the balance in my account?"

    # English → Kannada  (banking response → TTS input)
    kn = translate(
        "Your account balance is 5000 rupees.",
        src_lang="eng_Latn",
        tgt_lang="kan_Knda",
    )

Models are loaded on the first call for each direction and cached for the
lifetime of the process.  Calling translate() a second time for the same
direction reuses the already-loaded IndicTranslator instance — no reload.
"""

from __future__ import annotations

from backend.translation.exceptions import TranslationInputError
from backend.translation.translator import IndicTranslator
from backend.translation.utils import is_empty_input, validate_direction

__all__ = [
    "translate",
    "translate_kn_to_en",
    "translate_en_to_kn",
    "warm_model",
    "unload_model",
    "TranslationInputError",
]

# ---------------------------------------------------------------------------
# Model ID registry
# Maps (src_lang, tgt_lang) direction tuples to HuggingFace model IDs.
# Each direction has its own dedicated checkpoint — there is no shared
# bidirectional 200M model.
# ---------------------------------------------------------------------------
MODEL_IDS: dict[tuple[str, str], str] = {
    ("kan_Knda", "eng_Latn"): "ai4bharat/indictrans2-indic-en-dist-200M",
    ("eng_Latn", "kan_Knda"): "ai4bharat/indictrans2-en-indic-dist-200M",
}

# ---------------------------------------------------------------------------
# Singleton cache
# Keyed by HuggingFace model ID string.  Two separate IndicTranslator objects
# are created if both directions are used in the same session — one per
# checkpoint, never shared.
# ---------------------------------------------------------------------------
_model_cache: dict[str, IndicTranslator] = {}


def warm_model(direction: str = "kn_to_en") -> str:
    """Load and cache a translation model without running inference."""
    directions = {
        "kn_to_en": ("kan_Knda", "eng_Latn"),
        "en_to_kn": ("eng_Latn", "kan_Knda"),
    }
    if direction not in directions:
        raise ValueError(f"Unknown translation direction {direction!r}.")
    model_id = MODEL_IDS[directions[direction]]
    if model_id not in _model_cache:
        _model_cache[model_id] = IndicTranslator(model_id)
    return model_id


def translate(
    text: str,
    src_lang: str = "kan_Knda",
    tgt_lang: str = "eng_Latn",
) -> str:
    """
    Translate a single string between Kannada and English.

    This is the primary entry-point for all downstream pipeline modules
    (NLU for Kannada→English; TTS for English→Kannada).

    The underlying ``IndicTranslator`` is lazily instantiated on the first
    call for each direction and reused on all subsequent calls, avoiding the
    2–5 second model-load cost per request.

    Parameters
    ----------
    text:
        Source-language string to translate.
    src_lang:
        IndicTrans2 source language code.  Default ``"kan_Knda"`` (Kannada)
        — the common case for STT output flowing into NLU.
    tgt_lang:
        IndicTrans2 target language code.  Default ``"eng_Latn"`` (English).

    Returns
    -------
    str
        Translated string, or ``""`` if *text* is empty or whitespace-only.

    Raises
    ------
    TranslationInputError
        If ``(src_lang, tgt_lang)`` is not a supported direction, or if
        *text* is not a string.
    ValueError
        If *text* is not a string (caught before the model is touched).
    FileNotFoundError / OSError
        If the HuggingFace model files cannot be downloaded or found in the
        local cache.

    Examples
    --------
    >>> from backend.translation import translate
    >>> translate("ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟಿದೆ")
    'What is the balance in my account?'

    >>> translate("Block my ATM card", src_lang="eng_Latn", tgt_lang="kan_Knda")
    'ನನ್ನ ಎಟಿಎಂ ಕಾರ್ಡ್ ಬ್ಲಾಕ್ ಮಾಡಿ'
    """
    # --- Type check before anything else ---
    if not isinstance(text, str):
        raise TranslationInputError(
            f"translate() expects a string, got {type(text).__name__!r}."
        )

    # --- Short-circuit for empty/whitespace input (AC-1.2) ---
    # No model load, no network call, no exception — matches STT behaviour.
    if is_empty_input(text):
        return ""

    # --- Validate direction (raises TranslationInputError if unsupported) ---
    validate_direction(src_lang, tgt_lang)

    # --- Sarvam cloud translation when selected in the admin console ---
    cloud_text = _translate_cloud(text, src_lang, tgt_lang)
    if cloud_text is not None:
        return cloud_text

    # --- Lazy-load the correct model for this direction ---
    model_id = MODEL_IDS[(src_lang, tgt_lang)]

    if model_id not in _model_cache:
        direction = "kn_to_en" if src_lang == "kan_Knda" else "en_to_kn"
        warm_model(direction)

    # --- Translate and return the single string ---
    return _model_cache[model_id].translate([text], src_lang, tgt_lang)[0]


def _translate_cloud(text: str, src_lang: str, tgt_lang: str) -> str | None:
    """Sarvam translation, or None to use the local model (not selected / failed)."""
    from backend import cloud

    if not cloud.cloud_selected("translation"):
        return None
    if not cloud.use_cloud("translation"):
        if cloud.fallback_allowed():
            return None
        raise cloud.unavailable_error("translation")

    from backend.cloud import sarvam

    try:
        result = cloud.call_cloud(
            "translation",
            lambda key: sarvam.translate(key, text, src_lang=src_lang, tgt_lang=tgt_lang),
        )
    except Exception:
        if cloud.fallback_allowed():
            return None
        raise
    return result or None


def translate_kn_to_en(text: str) -> str:
    """
    Translate Kannada text to English.

    Convenience wrapper around :func:`translate` with language codes
    pre-filled, so downstream modules (NLU) never need to handle
    language code strings directly — eliminating the risk of a typo'd
    language code causing a silent mistranslation or a hard-to-debug
    ``TranslationInputError`` at runtime.

    Parameters
    ----------
    text:
        Kannada text string — typically the output of the STT module.

    Returns
    -------
    str
        English translation, or ``""`` for empty/whitespace input.

    Examples
    --------
    >>> from backend.translation import translate_kn_to_en
    >>> translate_kn_to_en("ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟಿದೆ")
    'What is the balance in my account?'
    """
    return translate(text, src_lang="kan_Knda", tgt_lang="eng_Latn")


def translate_en_to_kn(text: str) -> str:
    """
    Translate English text to Kannada.

    Convenience wrapper around :func:`translate` with language codes
    pre-filled, so downstream modules (TTS) never need to handle
    language code strings directly.

    Parameters
    ----------
    text:
        English text string — typically a templated banking response.

    Returns
    -------
    str
        Kannada translation suitable for TTS input, or ``""`` for
        empty/whitespace input.

    Examples
    --------
    >>> from backend.translation import translate_en_to_kn
    >>> translate_en_to_kn("Your account balance is 5000 rupees.")
    'ನಿಮ್ಮ ಖಾತೆ ಬಾಕಿ ಐದು ಸಾವಿರ ರೂಪಾಯಿ.'
    """
    return translate(text, src_lang="eng_Latn", tgt_lang="kan_Knda")


def unload_model(direction: str = "all") -> None:
    """
    Release cached Translation model(s) from memory.

    Parameters
    ----------
    direction:
        ``"kn_to_en"``, ``"en_to_kn"``, or ``"all"`` (default).
    """
    import gc
    import torch

    global _model_cache
    if direction == "kn_to_en":
        keys = [MODEL_IDS[("kan_Knda", "eng_Latn")]]
    elif direction == "en_to_kn":
        keys = [MODEL_IDS[("eng_Latn", "kan_Knda")]]
    else:
        keys = list(_model_cache.keys())

    for key in keys:
        if key in _model_cache:
            del _model_cache[key]
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
