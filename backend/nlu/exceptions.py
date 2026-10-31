"""
backend/nlu/exceptions.py

Custom exceptions for the NLU module.
"""


class NLUInputError(Exception):
    """
    Raised when the input to the NLU module is invalid.

    Covers cases such as:
    - A non-string value passed as the text argument
    - An unrecognised ``model`` argument in ``classify()``

    This is intentionally distinct from built-in exceptions so callers
    can catch NLU-specific input problems without masking unrelated errors
    such as model loading failures.

    Example
    -------
    >>> from backend.nlu.exceptions import NLUInputError
    >>> try:
    ...     classify(42)
    ... except NLUInputError as e:
    ...     print(f"Bad input: {e}")
    """
