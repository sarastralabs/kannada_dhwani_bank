"""
backend/translation/exceptions.py

Custom exceptions for the Translation module.
Import and catch TranslationInputError in any code that calls translate().
"""


class TranslationInputError(Exception):
    """
    Raised when the input to the translator is invalid.

    Covers cases such as:
    - A non-string value passed as the text argument
    - An unsupported (src_lang, tgt_lang) direction pair

    This is intentionally distinct from built-in exceptions so callers
    can catch translation-specific input problems without masking
    unrelated errors such as model loading failures or network issues.

    Example
    -------
    >>> from backend.translation.exceptions import TranslationInputError
    >>> try:
    ...     translate(42)
    ... except TranslationInputError as e:
    ...     print(f"Bad input: {e}")
    """
