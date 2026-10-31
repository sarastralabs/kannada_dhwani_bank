"""
backend/decision_router/exceptions.py
"""


class RouterError(Exception):
    """
    Raised when the Decision Router receives an intent it does not recognise.

    This is always a programming error in the calling code, not a user error —
    the NLU module should only ever produce one of the 7 known intent labels.
    Raising here rather than silently defaulting ensures bugs surface
    immediately rather than producing a nonsensical routing decision.

    Example
    -------
    >>> from backend.decision_router import route, RouterError
    >>> try:
    ...     route("transfer_money")   # not a valid intent
    ... except RouterError as e:
    ...     print(e)
    """
