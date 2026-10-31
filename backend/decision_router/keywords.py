"""Keyword routing for account_info_query → specific bank_info procedures."""

from __future__ import annotations

import re

# Maps spoken keywords → bank_info.json account_procedures key.
# Each tuple contains English terms, Kannada script terms, and common
# transliterations so matching works whether query_text is the original
# Kannada from STT or the English translation from IndicTrans2.
ACCOUNT_INFO_KEYWORDS: dict[str, tuple[str, ...]] = {
    "atm_block": (
        # English / transliteration
        "block atm", "block card", "atm block", "card block", "lost card",
        "stolen card", "atm card block", "debit block", "atm lost",
        # Kannada script
        "ಎಟಿಎಂ ಬ್ಲಾಕ್", "ಕಾರ್ಡ್ ಬ್ಲಾಕ್", "ಕಾರ್ಡ್ ಕಳೆದಿದೆ",
        "ಎಟಿಎಂ ಕಾರ್ಡ್ ಬ್ಲಾಕ್",
    ),
    "pin_change": (
        "pin change", "change pin", "atm pin", "new pin", "reset pin",
        "pin reset", "pin forgot", "forgot pin",
        # Kannada script
        "ಪಿನ್ ಬದಲಾವಣೆ", "ಪಿನ್ ಮರೆತಿದೆ", "ಹೊಸ ಪಿನ್",
    ),
    "cheque_book": (
        "cheque book", "check book", "chequebook", "new cheque book",
        "cheque request",
        # Kannada script
        "ಚೆಕ್ ಪುಸ್ತಕ", "ಚೆಕ್ ಬುಕ್",
    ),
    "mobile_update": (
        "mobile update", "change mobile", "update mobile", "phone number",
        "registered mobile", "mobile number", "change phone",
        # Kannada script
        "ಮೊಬೈಲ್ ನವೀಕರಣ", "ಮೊಬೈಲ್ ಬದಲಾವಣೆ", "ಫೋನ್ ನಂಬರ್",
    ),
    "name_change": (
        "name change", "change name", "update name", "name correction",
        "name update",
        # Kannada script
        "ಹೆಸರು ಬದಲಾವಣೆ", "ಹೆಸರು ಬದಲಾಯಿಸು",
    ),
    "internet_banking": (
        "internet banking", "net banking", "online banking", "activate banking",
        "ibanking", "netbanking",
        # Kannada script
        "ಇಂಟರ್ನೆಟ್ ಬ್ಯಾಂಕಿಂಗ್", "ನೆಟ್ ಬ್ಯಾಂಕಿಂಗ್",
    ),
    "mini_statement": (
        "mini statement", "last transactions", "statement",
        "transaction history", "account statement", "last 5",
        # Kannada script
        "ಮಿನಿ ಸ್ಟೇಟ್‌ಮೆಂಟ್", "ವ್ಯವಹಾರ ಇತಿಹಾಸ",
    ),
    "branch_locator": (
        "nearest branch", "branch location", "find branch", "branch address",
        "where is branch",
        # Kannada script
        "ಹತ್ತಿರದ ಶಾಖೆ", "ಶಾಖೆ ವಿಳಾಸ",
    ),
    "nominee_update": (
        "nominee", "nominee update", "change nominee", "add nominee",
        # Kannada script
        "ನಾಮಿನಿ", "ನಾಮಿನಿ ನವೀಕರಣ",
    ),
}


def match_account_procedure(query_text: str) -> str | None:
    """
    Return bank_info account_procedures key or None.

    Works on both English translations and original Kannada-script text.
    Longer matches win over shorter ones to avoid false positives.
    """
    text = re.sub(r"\s+", " ", (query_text or "").lower()).strip()
    if not text:
        return None
    best_key: str | None = None
    best_len = 0
    for key, keywords in ACCOUNT_INFO_KEYWORDS.items():
        for kw in keywords:
            kw_l = kw.lower()
            if kw_l and kw_l in text and len(kw_l) > best_len:
                best_key = key
                best_len = len(kw_l)
    return best_key
