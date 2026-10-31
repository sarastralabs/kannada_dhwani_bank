"""Resolve short follow-up utterances using prior dialog intent."""

from __future__ import annotations

import re

from backend.forms.form_menu import match_form_from_speech


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


# Product hints after an interest-rate answer
_INTEREST_PRODUCT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fixed_deposit": ("fixed deposit", "fd", "term deposit", "sthira thevani", "sthira"),
    "savings": ("savings", "sb account", "savings account"),
    "loan": ("loan", "home loan", "personal loan", "car loan", "sala"),
}


def resolve_follow_up(
    last_intent: str,
    kannada: str,
    english: str,
) -> dict | None:
    """
    If the user is clarifying or continuing the previous topic, return routing hints.
    Keys: type ('form' | 'interest_product'), form_id, intent, english_hint
    """
    combined = _norm(f"{english} {kannada}")
    if not combined or len(combined.split()) > 12:
        return None

    if last_intent == "interest_rate_query":
        for product, keywords in _INTEREST_PRODUCT_KEYWORDS.items():
            if any(kw in combined for kw in keywords):
                return {"type": "interest_product", "product": product}

    if last_intent in {"interest_rate_query", "account_info_query", "form_menu", "clarification"}:
        form_id = match_form_from_speech(kannada, english)
        if form_id:
            return {"type": "form", "form_id": form_id}

    # Short affirmations / continuations after informational answers
    if last_intent in {"account_info_query", "interest_rate_query"}:
        cont = (
            "what about",
            "how about",
            "and ",
            "also ",
            "tell me about",
            "fd",
            "rtgs",
            "cheque",
            "atm",
        )
        if any(combined.startswith(c) or f" {c}" in combined for c in cont):
            form_id = match_form_from_speech(kannada, english)
            if form_id:
                return {"type": "form", "form_id": form_id}

    return None
