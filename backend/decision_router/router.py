"""
backend/decision_router/router.py

Core routing logic for the Decision Router module.

Given an intent label from the NLU module, determines whether the query
is informational (answer from bank_info.json) or transactional (collect
entity fields, generate a form), and returns a structured result dict.

No ML, no external dependencies — pure Python dictionary lookups.

Changes
-------
- All informational responses now return ``response_text_kn`` (pre-written
  Kannada) in addition to ``response_text`` (English).  This means the TTS
  module skips the EN→KN translation step, producing faster and more natural
  Kannada output for banking phrases.

- ``interest_rate_query`` now detects specific product keywords in the query
  and returns only the rate for that product instead of always dumping all 8
  rates.  The full list is still returned when no specific product is mentioned.

- ``account_info_query`` keyword matching now runs against BOTH the English
  translation AND the original Kannada text, so ATM/PIN/cheque queries are
  correctly identified even when the translation loses nuance.
"""

from __future__ import annotations

import json
import os

from backend.decision_router.exceptions import RouterError
from backend.nlu.kannada_keywords import REPAYMENT_TERMS

# ---------------------------------------------------------------------------
# Load bank_info.json once at import time
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_BANK_INFO_PATH = os.path.join(_PROJECT_ROOT, "data", "bank_info.json")

if not os.path.exists(_BANK_INFO_PATH):
    raise FileNotFoundError(
        f"bank_info.json not found at '{_BANK_INFO_PATH}'.\n"
        "Create data/bank_info.json before importing this module."
    )

with open(_BANK_INFO_PATH, encoding="utf-8") as _f:
    _BANK_INFO: dict = json.load(_f)

# ---------------------------------------------------------------------------
# Intent category constants — single source of truth
# ---------------------------------------------------------------------------
INFORMATIONAL_INTENTS: frozenset[str] = frozenset({
    "account_info_query",
    "interest_rate_query",
})

TRANSACTIONAL_INTENTS: frozenset[str] = frozenset({
    "open_account",
    "apply_loan",
    "deposit_money",
    "withdraw_money",
    "check_balance",
})

ALL_INTENTS: frozenset[str] = INFORMATIONAL_INTENTS | TRANSACTIONAL_INTENTS

# ---------------------------------------------------------------------------
# Required entity fields per transactional intent
# ---------------------------------------------------------------------------
REQUIRED_FIELDS: dict[str, list[str]] = {
    "check_balance": ["account_number"],
    "open_account":  ["full_name", "date_of_birth", "address", "account_type"],
    "apply_loan":    ["full_name", "loan_type", "loan_amount", "income"],
    "deposit_money": ["account_number", "amount"],
    "withdraw_money":["account_number", "amount"],
}

# ---------------------------------------------------------------------------
# Specific interest-rate product keyword detection
# Maps keywords (English + Kannada) → bank_info key
# ---------------------------------------------------------------------------
_RATE_PRODUCT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "savings_account": (
        "savings", "saving", "sb account", "savings account",
        "ಉಳಿತಾಯ", "ulitaaya",
    ),
    "fixed_deposit_1yr": (
        "1 year fd", "one year fd", "1yr", "fd 1",
        "ಒಂದು ವರ್ಷ", "ondu varsha",
    ),
    "fixed_deposit_3yr": (
        "3 year fd", "three year fd", "3yr", "fd 3",
        "ಮೂರು ವರ್ಷ", "mooru varsha",
    ),
    "fixed_deposit_5yr": (
        "5 year fd", "five year fd", "5yr", "fd 5",
        "ಐದು ವರ್ಷ", "aidu varsha",
    ),
    "home_loan": (
        "home loan", "housing loan", "house loan",
        "ಗೃಹ ಸಾಲ", "gruha sala",
    ),
    "personal_loan": (
        "personal loan", "personal",
        "ವೈಯಕ್ತಿಕ ಸಾಲ", "vaiyaktika sala",
    ),
    "education_loan": (
        "education loan", "study loan", "student loan",
        "ಶಿಕ್ಷಣ ಸಾಲ", "shikshana sala",
    ),
    "car_loan": (
        "car loan", "vehicle loan", "auto loan",
        "ವಾಹನ ಸಾಲ", "vahana sala",
    ),
    # Generic FD — no specific year mentioned
    "fixed_deposit": (
        "fd", "fixed deposit", "term deposit",
        "ಸ್ಥಿರ ಠೇವಣಿ", "sthira thevani",
    ),
}


def _detect_rate_product(query: str) -> str | None:
    """
    Return the most specific bank_info interest_rates key mentioned in query,
    or None if no specific product is found.
    Longer / more-specific matches win over generic ones (fd 1yr > fd).
    """
    text = (query or "").lower()
    best_key: str | None = None
    best_len = 0
    for key, keywords in _RATE_PRODUCT_KEYWORDS.items():
        for kw in keywords:
            kw_l = kw.lower()
            if kw_l in text and len(kw_l) > best_len:
                best_key = key
                best_len = len(kw_l)
    return best_key


# ---------------------------------------------------------------------------
# Response text builders (private)
# ---------------------------------------------------------------------------

def _build_interest_rate_response(
    query_text: str = "", kannada_text: str = ""
) -> tuple[str, str]:
    """
    Return (english, kannada) interest rate response.

    If query_text mentions a specific product, returns only that rate.
    Otherwise returns all rates (full list).
    """
    rates = _BANK_INFO["interest_rates"]
    rates_kn = _BANK_INFO.get("interest_rates_kn", {})
    loan_info = _BANK_INFO["loan_repayment"]["info"]
    loan_info_kn = _BANK_INFO["loan_repayment"].get("info_kn", loan_info)

    # Repayment question — answer just that, not the full rate list (which is
    # also ~4x longer to speak on the TTS box).
    asked = f"{query_text} {kannada_text}".lower()
    if any(term in asked for term in REPAYMENT_TERMS):
        return loan_info, loan_info_kn

    product = _detect_rate_product(query_text)

    # Specific product detected
    if product and product != "fixed_deposit":
        rate_en = rates.get(product)
        rate_kn = rates_kn.get(product)
        if rate_en:
            label_map = {
                "savings_account":   "Savings Account",
                "fixed_deposit_1yr": "Fixed Deposit for 1 year",
                "fixed_deposit_3yr": "Fixed Deposit for 3 years",
                "fixed_deposit_5yr": "Fixed Deposit for 5 years",
                "home_loan":         "Home Loan",
                "personal_loan":     "Personal Loan",
                "education_loan":    "Education Loan",
                "car_loan":          "Car Loan",
            }
            label = label_map.get(product, product.replace("_", " ").title())
            en = f"The interest rate for {label} is {rate_en}."
            kn = rate_kn or en
            return en, kn

    # Generic FD — show all three FD rates
    if product == "fixed_deposit":
        en_parts = [
            "Here are our Fixed Deposit interest rates.",
            f"1 year: {rates['fixed_deposit_1yr']}.",
            f"3 years: {rates['fixed_deposit_3yr']}.",
            f"5 years: {rates['fixed_deposit_5yr']}.",
            loan_info,
        ]
        kn_parts = [
            "ಇಲ್ಲಿ ನಮ್ಮ ಸ್ಥಿರ ಠೇವಣಿ ಬಡ್ಡಿ ದರಗಳು:",
            rates_kn.get("fixed_deposit_1yr", ""),
            rates_kn.get("fixed_deposit_3yr", ""),
            rates_kn.get("fixed_deposit_5yr", ""),
            loan_info_kn,
        ]
        return " ".join(en_parts), " ".join(kn_parts)

    # No specific product — return full list
    en_lines = [
        "Here are our current interest rates.",
        f"Savings Account: {rates['savings_account']}.",
        f"Fixed Deposit for 1 year: {rates['fixed_deposit_1yr']}.",
        f"Fixed Deposit for 3 years: {rates['fixed_deposit_3yr']}.",
        f"Fixed Deposit for 5 years: {rates['fixed_deposit_5yr']}.",
        f"Home Loan: {rates['home_loan']}.",
        f"Personal Loan: {rates['personal_loan']}.",
        f"Education Loan: {rates['education_loan']}.",
        f"Car Loan: {rates['car_loan']}.",
        loan_info,
    ]
    en = " ".join(en_lines)
    kn = _BANK_INFO.get("interest_rates_all_kn", en)
    return en, kn


def _build_account_info_response(query_text: str = "", kannada_text: str = "") -> tuple[str, str]:
    """
    Return (english, kannada) account procedure response.

    Keyword matching runs against BOTH the English translation AND the
    original Kannada text so that ATM/PIN/cheque queries are correctly
    identified even when translation loses nuance.
    """
    from backend.decision_router.keywords import match_account_procedure

    # Try English query first, then fall back to Kannada
    key = match_account_procedure(query_text) or match_account_procedure(kannada_text)

    procs = _BANK_INFO["account_procedures"]
    if key and key in procs:
        en = procs[key]
        kn = procs.get(f"{key}_kn", en)
        return en, kn

    en = procs["general"]
    kn = procs.get("general_kn", en)
    return en, kn


def _build_transactional_response(intent: str, fields: list[str]) -> tuple[str, str]:
    """
    Return (english, kannada) prompt for a transactional intent.
    """
    if intent == "check_balance":
        en = (
            "To check your balance, please tell me the last 4 digits of your account number. "
            "I will look it up and tell you the available balance."
        )
        kn = _BANK_INFO.get("check_balance_note_kn", en)
        return en, kn

    intent_phrases_en = {
        "open_account":  "open a new bank account",
        "apply_loan":    "process your loan application",
        "deposit_money": "process your deposit",
        "withdraw_money":"process your withdrawal",
    }
    intent_phrases_kn = {
        "open_account":  "ಹೊಸ ಬ್ಯಾಂಕ್ ಖಾತೆ ತೆರೆಯಲು",
        "apply_loan":    "ನಿಮ್ಮ ಸಾಲ ಅರ್ಜಿ ಪ್ರಕ್ರಿಯೆಗೆ",
        "deposit_money": "ನಿಮ್ಮ ಠೇವಣಿ ಪ್ರಕ್ರಿಯೆಗೆ",
        "withdraw_money":"ನಿಮ್ಮ ಹಣ ಹಿಂಪಡೆಯುವ ಪ್ರಕ್ರಿಯೆಗೆ",
    }
    field_phrases_kn = {
        "full_name":   "ಪೂರ್ಣ ಹೆಸರು",
        "date_of_birth": "ಜನ್ಮ ದಿನಾಂಕ",
        "address":     "ವಿಳಾಸ",
        "account_type": "ಖಾತೆ ವಿಧ",
        "loan_type":   "ಸಾಲದ ವಿಧ",
        "loan_amount": "ಸಾಲದ ಮೊತ್ತ",
        "income":      "ಆದಾಯ",
        "account_number": "ಖಾತೆ ಸಂಖ್ಯೆ",
        "amount":      "ಮೊತ್ತ",
    }

    action_en = intent_phrases_en.get(intent, f"complete the {intent.replace('_', ' ')} request")
    action_kn = intent_phrases_kn.get(intent, action_en)
    spoken_fields_en = ", ".join(f.replace("_", " ") for f in fields)
    spoken_fields_kn = ", ".join(field_phrases_kn.get(f, f.replace("_", " ")) for f in fields)

    en = (
        f"To {action_en}, I will need to collect the following details: "
        f"{spoken_fields_en}. "
        f"Please have these ready."
    )
    kn = (
        f"{action_kn}, ನಾನು ಈ ಕೆಳಗಿನ ವಿವರಗಳನ್ನು ಸಂಗ್ರಹಿಸಬೇಕು: "
        f"{spoken_fields_kn}. "
        f"ದಯವಿಟ್ಟು ಸಿದ್ಧರಾಗಿರಿ."
    )
    return en, kn


# ---------------------------------------------------------------------------
# Public routing function
# ---------------------------------------------------------------------------

def route(intent: str, query_text: str = "", kannada_text: str = "") -> dict:
    """
    Route an intent to its handling path and return a structured result.

    Parameters
    ----------
    intent:
        Intent label string from the NLU module.  Must be one of the 7
        known intents; see ``ALL_INTENTS``.
    query_text:
        English translation of the user's query (used for keyword matching).
    kannada_text:
        Original Kannada text from STT (used as fallback for keyword matching).

    Returns
    -------
    dict
        Always contains ``"route"``, ``"intent"``, ``"response_text"``, and
        ``"response_text_kn"``.  Having ``response_text_kn`` set means the
        TTS pipeline will use it directly and skip the EN→KN translation step,
        giving faster and more natural Kannada output.

        Transactional results also contain ``"required_fields"``.

        Informational::

            {
                "route":            "informational",
                "intent":           "interest_rate_query",
                "response_text":    "Here are our current interest rates...",
                "response_text_kn": "ಇಲ್ಲಿ ನಮ್ಮ ಪ್ರಸ್ತುತ ಬಡ್ಡಿ ದರಗಳು...",
            }

        Transactional::

            {
                "route":            "transactional",
                "intent":           "open_account",
                "required_fields":  ["full_name", "date_of_birth", ...],
                "response_text":    "To open a new bank account...",
                "response_text_kn": "ಹೊಸ ಬ್ಯಾಂಕ್ ಖಾತೆ ತೆರೆಯಲು...",
            }

    Raises
    ------
    RouterError
        If ``intent`` is not in ``ALL_INTENTS``.
    """
    if intent not in ALL_INTENTS:
        raise RouterError(
            f"Unknown intent '{intent}'. "
            f"Valid intents are: {sorted(ALL_INTENTS)}."
        )

    if intent in INFORMATIONAL_INTENTS:
        if intent == "interest_rate_query":
            en, kn = _build_interest_rate_response(query_text, kannada_text)
        else:
            # account_info_query — pass both English and Kannada for matching
            en, kn = _build_account_info_response(query_text, kannada_text)

        return {
            "route":            "informational",
            "intent":           intent,
            "response_text":    en,
            "response_text_kn": kn,
        }

    # Transactional
    fields = REQUIRED_FIELDS[intent]
    en, kn = _build_transactional_response(intent, fields)
    return {
        "route":            "transactional",
        "intent":           intent,
        "required_fields":  fields,
        "response_text":    en,
        "response_text_kn": kn,
    }
