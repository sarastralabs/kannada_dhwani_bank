"""Combined intent resolution: Kannada keywords → English keywords → DistilBERT."""

from __future__ import annotations

from backend.nlu import classify, classify_top_k
from backend.nlu.kannada_keywords import match_kannada_intent


def classify_with_hints(
    kannada: str,
    english: str,
) -> tuple[str, float, str]:
    """
    Resolve intent using layered hints.

    Returns (intent, confidence, source).
    """
    kn_hit = match_kannada_intent(kannada, english)
    if kn_hit and kn_hit[1] >= 0.6:
        return kn_hit[0], kn_hit[1], "kannada_keywords"

    kw_intent, kw_conf = classify(english, model="baseline")
    if kw_conf >= 0.35:
        return kw_intent, kw_conf, "english_keywords"

    if kn_hit:
        return kn_hit[0], kn_hit[1], "kannada_keywords"

    intent, conf = classify(english, model="finetuned")
    return intent, conf, "finetuned"


def top_intents_for_clarification(english: str, k: int = 2) -> list[tuple[str, float]]:
    return classify_top_k(english, k=k)
