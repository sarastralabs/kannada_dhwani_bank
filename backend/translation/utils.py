"""
backend/translation/utils.py

Language code validation and text normalisation helpers for the
Translation module.

These functions run before any model inference so bad inputs and
unsupported language directions are rejected early with clear,
catchable errors.
"""

import re

from backend.translation.exceptions import TranslationInputError

# ---------------------------------------------------------------------------
# Supported translation directions
# ---------------------------------------------------------------------------
# Only Kannada ↔ English is in scope for this pipeline phase.
# Adding a new direction means adding one tuple here — nothing else changes.
SUPPORTED_DIRECTIONS: set[tuple[str, str]] = {
    ("kan_Knda", "eng_Latn"),  # Kannada → English  (STT output → NLU input)
    ("eng_Latn", "kan_Knda"),  # English → Kannada  (response → TTS input)
}

# Mapping from direction to the human-readable names used in error messages.
_LANG_NAMES: dict[str, str] = {
    "kan_Knda": "Kannada (kan_Knda)",
    "eng_Latn": "English (eng_Latn)",
}

# Pre-compiled pattern for collapsing runs of whitespace (faster than split/join
# for the repeated calls that happen during batched preprocessing).
_MULTI_SPACE_RE = re.compile(r" {2,}")


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def validate_direction(src_lang: str, tgt_lang: str) -> None:
    """
    Check that the requested translation direction is supported.

    Parameters
    ----------
    src_lang:
        IndicTrans2 source language code (e.g. ``"kan_Knda"``).
    tgt_lang:
        IndicTrans2 target language code (e.g. ``"eng_Latn"``).

    Raises
    ------
    TranslationInputError
        If the ``(src_lang, tgt_lang)`` pair is not in
        :data:`SUPPORTED_DIRECTIONS`, with a message that lists the
        valid options so the caller knows exactly what to fix.

    Examples
    --------
    >>> validate_direction("kan_Knda", "eng_Latn")   # passes silently
    >>> validate_direction("eng_Latn", "kan_Knda")   # passes silently
    >>> validate_direction("hin_Deva", "eng_Latn")   # raises TranslationInputError
    """
    if (src_lang, tgt_lang) not in SUPPORTED_DIRECTIONS:
        valid = ", ".join(
            f"'{s}' → '{t}'" for s, t in sorted(SUPPORTED_DIRECTIONS)
        )
        src_label = _LANG_NAMES.get(src_lang, src_lang)
        tgt_label = _LANG_NAMES.get(tgt_lang, tgt_lang)
        raise TranslationInputError(
            f"Unsupported translation direction: {src_label} → {tgt_label}. "
            f"Supported directions are: {valid}."
        )


def normalise_input(text: str) -> str:
    """
    Normalise a text string before passing it to the translation model.

    Operations applied (in order):
    1. Strip leading and trailing whitespace.
    2. Collapse runs of two or more internal spaces to a single space.

    This is intentionally minimal — aggressive normalisation (lowercasing,
    punctuation removal) would distort the input for a translation model.

    Parameters
    ----------
    text:
        Raw input string from the caller.

    Returns
    -------
    str
        Normalised string.  If ``text`` is empty or whitespace-only,
        returns ``""`` (the strip step handles this naturally).

    Examples
    --------
    >>> normalise_input("  ನನ್ನ  ಖಾತೆ  ")
    'ನನ್ನ ಖಾತೆ'
    >>> normalise_input("")
    ''
    >>> normalise_input("   ")
    ''
    """
    stripped = text.strip()
    if not stripped:
        return ""
    return _MULTI_SPACE_RE.sub(" ", stripped)


def is_empty_input(text: str) -> bool:
    """
    Return ``True`` if *text* is empty or whitespace-only.

    Used by :func:`backend.translation.translate` to short-circuit
    before loading or calling any model, matching the STT module's
    pattern of returning ``""`` for empty inputs without raising.

    Parameters
    ----------
    text:
        Input string to check.

    Returns
    -------
    bool
        ``True`` if the string contains no non-whitespace characters.

    Examples
    --------
    >>> is_empty_input("")
    True
    >>> is_empty_input("   ")
    True
    >>> is_empty_input("hello")
    False
    >>> is_empty_input("ನನ್ನ ಖಾತೆ")
    False
    """
    return not text.strip()
