"""
backend/nlu/__init__.py

Public API for the NLU intent classification module.

Quick-start
-----------
    from backend.nlu import classify

    label, confidence = classify("What is my account balance?")
    # ("check_balance", 0.9873)

    # Use keyword baseline (no model load)
    label, confidence = classify("I want a loan", model="baseline")
    # ("apply_loan", 0.25)

Models are loaded on first call and cached for the process lifetime.
"""

from __future__ import annotations

import os
from typing import Any

from backend.nlu.exceptions import NLUInputError
from backend.nlu.intents import INTENTS

__all__ = ["classify", "classify_top_k", "warm_model", "unload_model", "NLUInputError", "INTENTS"]

def is_empty_input(text: str) -> bool:
    return not text.strip()

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

MODEL_DIR: str = os.path.join(_PROJECT_ROOT, "models", "nlu-distilbert")

_VALID_MODELS = {"baseline", "finetuned"}

# Singleton cache — keyed by model name
_classifier_cache: dict[str, Any] = {}


def warm_model(model: str = "finetuned") -> str:
    """Load and cache an NLU classifier without classifying a request."""
    if model not in _VALID_MODELS:
        raise ValueError(f"Unknown model {model!r}. Valid options: {sorted(_VALID_MODELS)}.")
    if model not in _classifier_cache:
        if model == "baseline":
            from backend.nlu.keyword_classifier import KeywordClassifier

            _classifier_cache[model] = KeywordClassifier()
        else:
            from backend.nlu.distilbert_classifier import DistilBERTClassifier

            _classifier_cache[model] = DistilBERTClassifier(MODEL_DIR)
    return model


def classify(
    text: str,
    model: str = "finetuned",
) -> tuple[str, float]:
    """
    Classify an English banking query into one of 7 intents.

    Parameters
    ----------
    text:
        English text string (output of ``translate_kn_to_en()``).
    model:
        Which classifier to use:

        - ``"finetuned"`` (default) — DistilBERT checkpoint from ``models/nlu-distilbert/``
        - ``"baseline"``            — keyword-matching rule engine (no model download)

    Returns
    -------
    tuple[str, float]
        ``(intent_label, confidence)`` where confidence is in [0, 1].
        Returns ``("", 0.0)`` for empty/whitespace input — no exception.

    Raises
    ------
    NLUInputError
        If *text* is not a string.
    ValueError
        If *model* is not ``"finetuned"`` or ``"baseline"``.
    FileNotFoundError
        If ``model="finetuned"`` and the checkpoint directory does not exist.
        Run ``python backend/nlu/train.py`` first.
    """
    if not isinstance(text, str):
        raise NLUInputError(
            f"classify() expects a string, got {type(text).__name__!r}."
        )

    if model not in _VALID_MODELS:
        raise ValueError(
            f"Unknown model {model!r}. Valid options: {sorted(_VALID_MODELS)}."
        )

    # Short-circuit for empty input — no model load, no exception
    if is_empty_input(text):
        return ("", 0.0)

    # Lazy-load and cache
    warm_model(model)

    return _classifier_cache[model].classify(text)


def classify_top_k(text: str, k: int = 2, model: str = "finetuned") -> list[tuple[str, float]]:
    """Return top-k intent candidates for disambiguation."""
    if not isinstance(text, str):
        raise NLUInputError(
            f"classify_top_k() expects a string, got {type(text).__name__!r}."
        )
    if model not in _VALID_MODELS:
        raise ValueError(
            f"Unknown model {model!r}. Valid options: {sorted(_VALID_MODELS)}."
        )
    if is_empty_input(text):
        return []

    warm_model(model)

    clf = _classifier_cache[model]
    if hasattr(clf, "classify_top_k"):
        return clf.classify_top_k(text, k=k)
    intent, conf = clf.classify(text)
    return [(intent, conf)]


def unload_model(model: str = "all") -> None:
    """
    Release cached NLU classifier(s) from memory.

    Parameters
    ----------
    model:
        ``"finetuned"``, ``"baseline"``, or ``"all"`` (default).
    """
    import gc
    import torch

    global _classifier_cache
    keys = list(_classifier_cache.keys()) if model == "all" else [model]
    for key in keys:
        if key in _classifier_cache:
            del _classifier_cache[key]
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
