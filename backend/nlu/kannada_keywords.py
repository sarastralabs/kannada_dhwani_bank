"""Kannada-script and transliteration keywords for intent hints before NLU."""

from __future__ import annotations

import re

from backend.nlu.intents import INTENTS

# High-signal Kannada / STT-transliteration terms per intent
KANNADA_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "check_balance": (
        "ಬ್ಯಾಲೆನ್ಸ್",
        "baaki",
        "bakki",
        "baaki tilisi",
        "balance",
        # "How much is in my account" — phrases, not a bare "ಎಷ್ಟಿದೆ", which would
        # also hijack "ಬಡ್ಡಿ ದರ ಎಷ್ಟಿದೆ" (longest match wins).
        "ಖಾತೆ ಎಷ್ಟಿದೆ",
        "ಖಾತೆಯಲ್ಲಿ ಎಷ್ಟು",
        "ಖಾತೆಯಲ್ಲಿ ಎಷ್ಟಿದೆ",
        "ಖಾತೆಯ ಬಾಕಿ",
        "ಖಾತೆ ಬಾಕಿ",
        "ಬಾಕಿ ಎಷ್ಟು",
        "ಬಾಕಿ ಎಷ್ಟಿದೆ",
        "ಎಷ್ಟು ಹಣ ಇದೆ",
        "ಎಷ್ಟು ದುಡ್ಡು",
    ),
    "withdraw_money": (
        "ಹಿಂಪಡೆ",
        "hinpade",
        "withdraw",
        "cash out",
        "ಹಣ ತೆಗೆ",
    ),
    "deposit_money": (
        "ಠೇವಣಿ",
        "thevani",
        "tevani",
        "deposit",
        "cash deposit",
    ),
    "open_account": (
        # No bare "ಖಾತೆ"/"khate" (= "account"): it sent every account question —
        # e.g. "ನನ್ನ ಖಾತೆ ಎಷ್ಟಿದೆ" (balance) — to the account-opening form.
        "ಹೊಸ ಖಾತೆ",
        "ಖಾತೆ ತೆರೆ",
        "ಖಾತೆ ತೆಗೆ",
        "ಖಾತೆ ಬೇಕು",
        "hosa khate",
        "khate tere",
        "open account",
        "new account",
    ),
    "apply_loan": (
        "ಸಾಲ",
        "sala",
        "loan",
        "salakke",
        "home loan",
        "personal loan",
    ),
    "interest_rate_query": (
        "ಬಡ್ಡಿ",
        "baddi",
        "interest rate",
        "interest",
        "fd rate",
        "fixed deposit rate",
    ),
    "account_info_query": (
        "ಮಾಹಿತಿ",
        "mahiti",
        "account info",
        "cheque book",
        "atm card",
        "pin change",
        "mobile update",
        # Kannada forms — "ಚೆಕ್ ಬುಕ್ ಬೇಕು" was routed to apply_loan.
        "ಚೆಕ್ ಬುಕ್",
        "ಚೆಕ್ಬುಕ್",
        "ಚೆಕ್ ಪುಸ್ತಕ",
        "ಬುಕ್ ಬೇಕು",  # STT often drops "ಚೆಕ್"/"ಪಾಸ್" -> still a book request
        "ಪಾಸ್ ಬುಕ್",
        "ಪಾಸ್‌ಬುಕ್",
        "ಪಿನ್",
        "ಎಟಿಎಂ",
    ),
}


# Loan repayment questions are informational (bank_info loan_repayment), but
# they almost always also say "ಸಾಲ"/"loan"/"home loan", which would otherwise
# win the longest-match and open the loan application form. Checked first.
REPAYMENT_TERMS: tuple[str, ...] = (
    "ಮರುಪಾವತಿ",
    "marupavati",
    "repay",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def match_kannada_intent(kannada: str, english: str = "") -> tuple[str, float] | None:
    """
    Match intent from Kannada text (and optional English) using keyword overlap.
    Returns (intent, confidence) or None.
    """
    combined = _norm(f"{kannada} {english}")
    if not combined:
        return None

    if any(term in combined for term in REPAYMENT_TERMS):
        return "interest_rate_query", 0.79

    best_intent: str | None = None
    best_len = 0
    for intent, keywords in KANNADA_INTENT_KEYWORDS.items():
        if intent not in INTENTS:
            continue
        for kw in keywords:
            kw_n = _norm(kw)
            if kw_n and kw_n in combined and len(kw_n) > best_len:
                best_intent = intent
                best_len = len(kw_n)

    if not best_intent:
        return None
    # Keyword hits are confident enough to bias routing
    conf = min(0.92, 0.55 + best_len * 0.04)
    return best_intent, round(conf, 4)
