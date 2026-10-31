"""STT beam / field hints for voice form fill."""

from __future__ import annotations

import os

NAME_FIELD_IDS = frozenset(
    {
        "full_name",
        "name",
        "applicant_name",
        "beneficiary_name",
        "remitter_name",
        "nominee_name",
    }
)
MOBILE_FIELD_IDS = frozenset({"mobile_number", "old_mobile", "new_mobile"})
ACCOUNT_FIELD_IDS = frozenset(
    {"account_number", "remitter_account", "beneficiary_account"}
)


def expected_account_length() -> int:
    """Demo kiosk account length (default 10)."""
    try:
        return max(4, int(os.environ.get("BANK_DEMO_ACCOUNT_LENGTH", "10")))
    except ValueError:
        return 10


def form_fill_beam_size(field_type: str, field_id: str) -> int:
    """Higher beam = clearer STT for names and text; confirm kept moderate."""
    fid = (field_id or "").lower()
    ftype = (field_type or "text").lower()
    if fid == "confirm":
        return 3
    if fid in NAME_FIELD_IDS or ftype == "text":
        return 5
    return 3


def form_fill_stt_hints(field_type: str, field_id: str) -> tuple[str | None, str | None]:
    """Return field-aware Whisper context without changing general conversation."""
    fid = (field_id or "").lower()
    ftype = (field_type or "text").lower()
    if ftype == "date" or "date" in fid:
        return (
            "ಇದು ಬ್ಯಾಂಕ್ ಅರ್ಜಿಯ ದಿನಾಂಕ. ಉತ್ತರದಲ್ಲಿ ದಿನ, ತಿಂಗಳು ಮತ್ತು ನಾಲ್ಕು ಅಂಕಿಯ ವರ್ಷ ಇದೆ.",
            (
                "ದಿನಾಂಕ ಜನ್ಮ ದಿನಾಂಕ ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು ಐದು ಆರು ಏಳು ಎಂಟು ಒಂಬತ್ತು "
                "ಹತ್ತು ಹನ್ನೊಂದು ಹನ್ನೆರಡು ಹದಿಮೂರು ಹದಿನಾಲ್ಕು ಹದಿನೈದು ಹದಿನಾರು "
                "ಹದಿನೇಳು ಹದಿನೆಂಟು ಹತ್ತೊಂಬತ್ತು ಇಪ್ಪತ್ತು ಮೂವತ್ತು "
                "ಸಾವಿರ ಎರಡು ಸಾವಿರ ಎರಡು ಸಾವಿರ ಮೂರು"
            ),
        )
    if ftype == "digits":
        if fid in MOBILE_FIELD_IDS:
            return (
                "ಇದು ಹತ್ತು ಅಂಕಿಯ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ. ಪ್ರತಿಯೊಂದು ಅಂಕಿಯನ್ನು ಪ್ರತ್ಯೇಕವಾಗಿ ಹೇಳಲಾಗಿದೆ.",
                (
                    "ಸೊನ್ನೆ ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು ಐದು ಆರು ಏಳು ಎಂಟು ಒಂಬತ್ತು "
                    "zero one two three four five six seven eight nine"
                ),
            )
        if fid in ACCOUNT_FIELD_IDS:
            # Neutral on length: customers say the last 4, last 6, or all digits.
            # The old "10-digit … may end in zero" prompt made Whisper add digits
            # (spoken 7890 -> "…ಸೊನ್ನೆ ಸೊನ್ನೆ" = 78900); measured 2/4 -> 4/4.
            return (
                "ಇದು ಖಾತೆ ಸಂಖ್ಯೆಯ ಅಂಕಿಗಳು. ಪ್ರತಿಯೊಂದು ಅಂಕಿಯನ್ನು ಪ್ರತ್ಯೇಕವಾಗಿ ಹೇಳಲಾಗಿದೆ.",
                (
                    "ಸೊನ್ನೆ ಶೂನ್ಯ ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು ಐದು ಆರು ಏಳು ಎಂಟು ಒಂಬತ್ತು "
                    "zero oh o one two three four five six seven eight nine"
                ),
            )
        return (
            "ಇದು ಬ್ಯಾಂಕ್ ಅರ್ಜಿಯ ಸಂಖ್ಯೆ. ಪ್ರತಿಯೊಂದು ಅಂಕಿಯನ್ನು ಕನ್ನಡದಲ್ಲಿ ಹೇಳಲಾಗಿದೆ.",
            "ಸೊನ್ನೆ ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು ಐದು ಆರು ಏಳು ಎಂಟು ಒಂಬತ್ತು",
        )
    # Every other answer gets a SHORT prompt. Left at None, the transcriber falls
    # back to its long banking prompt, which together with its hotwords leaves
    # Whisper too little room and cuts answers mid-word: "ರಮೇಶ್ ಕುಮಾರ್" -> "ರಮೇಶ್ ಕ",
    # "ನನ್ನ ವಿಳಾಸ ಮೂವತ್ತೆರಡು, …" -> "ನನ್ನ ವಿಳಾಸ ಮೂವತ್ತ".
    if fid in NAME_FIELD_IDS:
        return "ಇದು ಗ್ರಾಹಕರ ಪೂರ್ಣ ಹೆಸರು.", None
    return "ಇದು ಬ್ಯಾಂಕ್ ಅರ್ಜಿಗೆ ಗ್ರಾಹಕರ ಉತ್ತರ.", None


def plausible_digit_capture(digits: str, field_id: str) -> bool:
    """Whether a numeric transcript has a plausible field-specific length."""
    fid = (field_id or "").lower()
    if fid in MOBILE_FIELD_IDS:
        return len(digits) == 10
    if fid in ACCOUNT_FIELD_IDS:
        # Same lengths validation accepts: last 4, last 6 (shared last 4), or full.
        return len(digits) in {4, 6, expected_account_length()}
    if fid == "number_of_leaves":
        return digits in {"10", "25", "50"}
    return bool(digits)


def english_digit_retry_hints(field_id: str) -> tuple[str, str]:
    """Context for a same-model English decode when Kannada digit decode fails."""
    fid = (field_id or "").lower()
    if fid in MOBILE_FIELD_IDS:
        subject = "ten digit mobile number"
    elif fid in ACCOUNT_FIELD_IDS:
        subject = f"{expected_account_length()} digit bank account number"
    else:
        subject = "banking number"
    return (
        f"The speaker is saying a {subject}, one digit at a time including any final zero.",
        "zero oh o one two three four five six seven eight nine",
    )
