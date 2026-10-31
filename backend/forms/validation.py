"""Validation rules for values captured from speech before confirmation."""

from __future__ import annotations

from datetime import datetime
import re

_MOBILE_FIELDS = {"mobile_number", "old_mobile", "new_mobile"}
_ACCOUNT_FIELDS = {
    "account_number",
    "remitter_account",
    "beneficiary_account",
}
DATE_RETRY_KN = (
    "ದಿನಾಂಕ ಸರಿಯಾಗಿ ಗುರುತಿಸಲಿಲ್ಲ. ದಯವಿಟ್ಟು ದಿನ, ತಿಂಗಳು ಮತ್ತು ವರ್ಷವನ್ನು "
    "ಪ್ರತ್ಯೇಕವಾಗಿ ಹೇಳಿ. ಉದಾಹರಣೆಗೆ, ಹದಿನಾಲ್ಕು, ಹತ್ತು, ಎರಡು ಸಾವಿರ ಮೂರು."
)
FUTURE_DOB_KN = "ಜನ್ಮ ದಿನಾಂಕ ಭವಿಷ್ಯದ ದಿನಾಂಕವಾಗಿರಬಾರದು. ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ."
MOBILE_RETRY_KN = (
    "ದಯವಿಟ್ಟು ಹತ್ತು ಅಂಕಿಯ ಮೊಬೈಲ್ ಸಂಖ್ಯೆಯನ್ನು ಒಂದೊಂದೇ ಅಂಕಿಯಾಗಿ ಹೇಳಿ."
)
ACCOUNT_RETRY_KN = (
    "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಖಾತೆ ಸಂಖ್ಯೆಯ ಕೊನೆಯ ನಾಲ್ಕು ಅಂಕಿಗಳನ್ನು ಹೇಳಿ, "
    "ಅಥವಾ ಪೂರ್ತಿ ಹತ್ತು ಅಂಕಿಗಳ ಸಂಖ್ಯೆ ಹೇಳಿ."
)
CHEQUE_LEAVES_RETRY_KN = "ದಯವಿಟ್ಟು ಹತ್ತು, ಇಪ್ಪತ್ತೈದು ಅಥವಾ ಐವತ್ತು ಎಂದು ಹೇಳಿ."
DIGITS_RETRY_KN = (
    "ಸಂಖ್ಯೆಯನ್ನು ಗುರುತಿಸಲಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಒಂದೊಂದೇ ಅಂಕಿಯಾಗಿ ಮತ್ತೆ ಹೇಳಿ."
)
# Choice fields: re-ask with the options instead of saving an unrecognised word.
CHOICE_RETRY_KN = {
    "account_type": "ದಯವಿಟ್ಟು ಉಳಿತಾಯ, ಚಾಲ್ತಿ ಅಥವಾ ವೇತನ ಖಾತೆ ಎಂದು ಹೇಳಿ.",
    "loan_type": "ದಯವಿಟ್ಟು ಗೃಹ ಸಾಲ, ವೈಯಕ್ತಿಕ ಸಾಲ, ಶಿಕ್ಷಣ ಸಾಲ ಅಥವಾ ವಾಹನ ಸಾಲ ಎಂದು ಹೇಳಿ.",
    "deposit_mode": "ದಯವಿಟ್ಟು ನಗದು ಅಥವಾ ಚೆಕ್ ಎಂದು ಹೇಳಿ.",
    "interest_payout": "ದಯವಿಟ್ಟು ಮಾಸಿಕ, ತ್ರೈಮಾಸಿಕ ಅಥವಾ ಅವಧಿ ಪೂರ್ಣಗೊಂಡಾಗ ಎಂದು ಹೇಳಿ.",
}
STATIC_VALIDATION_PHRASES = (
    *CHOICE_RETRY_KN.values(),
    DATE_RETRY_KN,
    FUTURE_DOB_KN,
    MOBILE_RETRY_KN,
    ACCOUNT_RETRY_KN,
    CHEQUE_LEAVES_RETRY_KN,
    DIGITS_RETRY_KN,
)


def validate_captured_value(
    value: str,
    *,
    field_type: str,
    field_id: str,
) -> str | None:
    """Return a Kannada retry prompt when a recognized value is implausible."""
    normalized_type = (field_type or "text").strip().lower()
    normalized_id = (field_id or "").strip().lower()
    text = (value or "").strip()

    choice_key = "interest_payout" if normalized_id == "interest_payment" else normalized_id
    if choice_key in CHOICE_RETRY_KN:
        from backend.forms.extract import CHOICE_OPTIONS

        if text not in CHOICE_OPTIONS[choice_key]:
            return CHOICE_RETRY_KN[choice_key]
        return None

    if normalized_type == "date":
        try:
            parsed = datetime.strptime(text, "%d/%m/%Y")
        except ValueError:
            return DATE_RETRY_KN
        if normalized_id == "date_of_birth" and parsed.date() > datetime.now().date():
            return FUTURE_DOB_KN
        return None

    if normalized_type != "digits":
        return None

    digits = re.sub(r"\D", "", text)
    if normalized_id in _MOBILE_FIELDS and len(digits) != 10:
        return MOBILE_RETRY_KN
    if normalized_id in _ACCOUNT_FIELDS:
        from backend.forms.stt_tuning import expected_account_length

        expected = expected_account_length()
        # Allow 4 digits (last-4 shortcut) or 6 digits (disambiguation)
        if len(digits) in {4, 6, expected}:
            return None
        if expected == 10:
            return ACCOUNT_RETRY_KN
        return (
            f"ದಯವಿಟ್ಟು ಕೊನೆಯ ನಾಲ್ಕು ಅಂಕಿಗಳನ್ನು ಅಥವಾ ಪೂರ್ತಿ {expected} ಅಂಕೆಗಳ "
            "ಖಾತೆ ಸಂಖ್ಯೆಯನ್ನು ಹೇಳಿ."
        )
    if normalized_id == "number_of_leaves" and digits not in {"10", "25", "50"}:
        return CHEQUE_LEAVES_RETRY_KN
    if not digits:
        return DIGITS_RETRY_KN
    return None
