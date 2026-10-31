"""
backend/stt/exceptions.py

Custom exceptions for the STT module.
Import and catch STTInputError in any code that calls transcribe().
"""


class STTInputError(Exception):
    """
    Raised when the input audio file is missing, corrupted, or in an
    unsupported format.

    This is intentionally distinct from built-in exceptions so callers
    can catch STT-specific input problems without masking unrelated errors.

    Example
    -------
    >>> from backend.stt.exceptions import STTInputError
    >>> try:
    ...     transcribe("missing.wav")
    ... except STTInputError as e:
    ...     print(f"Bad input: {e}")
    """
