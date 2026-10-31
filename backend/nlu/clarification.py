"""Build targeted clarification prompts when NLU confidence is low."""

from __future__ import annotations

INTENT_PHRASES_EN: dict[str, str] = {
    "open_account": "open a new account",
    "check_balance": "check your balance",
    "apply_loan": "apply for a loan",
    "deposit_money": "deposit money",
    "withdraw_money": "withdraw cash",
    "account_info_query": "account information",
    "interest_rate_query": "interest rates",
}

INTENT_PHRASES_KN: dict[str, str] = {
    "open_account": "ಹೊಸ ಖಾತೆ ತೆರೆಯುವುದು",
    "check_balance": "ಖಾತೆಯ ಶಿಲ್ಕು ತಿಳಿಯುವುದು",
    "apply_loan": "ಸಾಲ ಅರ್ಜಿ",
    "deposit_money": "ಠೇವಣಿ",
    "withdraw_money": "ಹಣ ಹಿಂಪಡೆಯುವುದು",
    "account_info_query": "ಖಾತೆ ಮಾಹಿತಿ",
    "interest_rate_query": "ಬಡ್ಡಿ ದರ",
}


def build_clarification(top: list[tuple[str, float]], attempt: int = 0) -> tuple[str, str]:
    """Return (english, kannada) clarification for the top two intent candidates."""
    if attempt >= 2:
        en = (
            "I still did not catch that. Please say one service clearly — "
            "for example: check balance, open account, loan, deposit, or withdraw."
        )
        kn = (
            "ನೀವು ಹೇಳಿದ್ದು ಇನ್ನೂ ಸ್ಪಷ್ಟವಾಗಿ ಅರ್ಥವಾಗಲಿಲ್ಲ. ಒಂದು ಸೇವೆಯನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ಹೇಳಿ — "
            "ಉದಾಹರಣೆಗೆ: ಖಾತೆಯ ಶಿಲ್ಕು, ಖಾತೆ ತೆರೆಯುವುದು, ಸಾಲ, ಠೇವಣಿ, ಅಥವಾ ಹಣ ಹಿಂಪಡೆಯುವುದು."
        )
        return en, kn

    if len(top) < 2:
        en = (
            "Sorry, I did not understand clearly. "
            "Please say again — for example balance inquiry, open account, loan, or deposit."
        )
        kn = (
            "ಕ್ಷಮಿಸಿ, ಸ್ಪಷ್ಟವಾಗಿ ಅರ್ಥವಾಗಲಿಲ್ಲ. "
            "ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ — ಉದಾಹರಣೆಗೆ: ಖಾತೆಯ ಶಿಲ್ಕು, ಖಾತೆ ತೆರೆಯುವುದು, ಸಾಲ, ಅಥವಾ ಠೇವಣಿ."
        )
        return en, kn

    a, b = top[0][0], top[1][0]
    a_en = INTENT_PHRASES_EN.get(a, a.replace("_", " "))
    b_en = INTENT_PHRASES_EN.get(b, b.replace("_", " "))
    a_kn = INTENT_PHRASES_KN.get(a, a_en)
    b_kn = INTENT_PHRASES_KN.get(b, b_en)

    if attempt >= 1:
        en = f"I heard you, but need one choice: {a_en} or {b_en}?"
        kn = f"ಒಂದು ಆಯ್ಕೆಯನ್ನು ಹೇಳಿ: {a_kn} ಅಥವಾ {b_kn}?"
        return en, kn

    en = f"Did you mean {a_en} or {b_en}? Please say again clearly."
    kn = f"ನೀವು {a_kn} ಅಥವಾ {b_kn} ಸೇವೆಯನ್ನು ಕೇಳುತ್ತಿದ್ದೀರಾ? ದಯವಿಟ್ಟು ಮತ್ತೆ ಸ್ಪಷ್ಟವಾಗಿ ಹೇಳಿ."
    return en, kn


def resolve_clarified_intent(
    pending: list[str],
    kannada: str,
    english: str,
) -> tuple[str, float] | None:
    """Pick one of the pending intents from the user's clarification answer."""
    if not pending:
        return None

    combined = f"{english} {kannada}".lower()
    allowed = set(pending)

    for intent in pending:
        for phrase in (
            INTENT_PHRASES_EN.get(intent, ""),
            INTENT_PHRASES_KN.get(intent, ""),
            intent.replace("_", " "),
        ):
            p = (phrase or "").lower().strip()
            if len(p) >= 3 and p in combined:
                return intent, 0.88

    from backend.nlu.kannada_keywords import match_kannada_intent

    kn_hit = match_kannada_intent(kannada, english)
    if kn_hit and kn_hit[0] in allowed:
        return kn_hit[0], kn_hit[1]

    from backend.nlu.resolve import classify_with_hints, top_intents_for_clarification

    intent, conf, _ = classify_with_hints(kannada, english)
    if intent in allowed and conf >= 0.25:
        return intent, conf

    for candidate, score in top_intents_for_clarification(english, k=3):
        if candidate in allowed and score >= 0.2:
            return candidate, score

    return None
