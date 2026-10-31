"""Build Kannada read-back summaries for completed voice forms."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

_DIGIT_TO_KN: dict[str, str] = {
    "0": "ಸೊನ್ನೆ",
    "1": "ಒಂದು",
    "2": "ಎರಡು",
    "3": "ಮೂರು",
    "4": "ನಾಲ್ಕು",
    "5": "ಐದು",
    "6": "ಆರು",
    "7": "ಏಳು",
    "8": "ಎಂಟು",
    "9": "ಒಂಬತ್ತು",
}

_ACCOUNT_FIELD_IDS = frozenset(
    {
        "account_number",
        "beneficiary_account",
        "remitter_account",
        "mobile_number",
        "old_mobile",
        "new_mobile",
        "cheque_number",
        "pan",
    }
)
_AMOUNT_FIELD_IDS = frozenset(
    {
        "amount",
        "loan_amount",
        "fd_amount",
        "income",
    }
)
_TEXT_VALUE_KN: dict[str, str] = {
    "savings": "ಉಳಿತಾಯ ಖಾತೆ",
    "current": "ಚಾಲ್ತಿ ಖಾತೆ",
    "salary": "ವೇತನ ಖಾತೆ",
    "fixed deposit": "ಸ್ಥಿರ ಠೇವಣಿ",
    "home loan": "ಗೃಹ ಸಾಲ",
    "personal loan": "ವೈಯಕ್ತಿಕ ಸಾಲ",
    "education loan": "ಶಿಕ್ಷಣ ಸಾಲ",
    "car loan": "ವಾಹನ ಸಾಲ",
    "gold loan": "ಚಿನ್ನದ ಸಾಲ",
    "cash": "ನಗದು",
    "cheque": "ಚೆಕ್",
    "demand draft": "ಡಿಮ್ಯಾಂಡ್ ಡ್ರಾಫ್ಟ್",
    "atm / debit card": "ಎಟಿಎಂ / ಡೆಬಿಟ್ ಕಾರ್ಡ್",
    "credit card": "ಕ್ರೆಡಿಟ್ ಕಾರ್ಡ್",
    "monthly": "ಮಾಸಿಕ",
    "quarterly": "ತ್ರೈಮಾಸಿಕ",
    "on maturity": "ಅವಧಿ ಪೂರ್ಣಗೊಂಡಾಗ",
    "cumulative / on maturity": "ಸಂಚಿತವಾಗಿ / ಅವಧಿ ಪೂರ್ಣಗೊಂಡಾಗ",
    "1 year": "ಒಂದು ವರ್ಷ",
    "2 years": "ಎರಡು ವರ್ಷ",
    "3 years": "ಮೂರು ವರ್ಷ",
    "5 years": "ಐದು ವರ್ಷ",
    "6 months": "ಆರು ತಿಂಗಳು",
    "12 months": "ಹನ್ನೆರಡು ತಿಂಗಳು",
}


def mask_account(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) <= 4:
        return digits or "—"
    return ("•" * (len(digits) - 4)) + digits[-4:]


def digits_to_kannada_words(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return raw.strip() or "—"
    return " ".join(_DIGIT_TO_KN.get(ch, ch) for ch in digits)


def _parse_amount(value: str) -> float | None:
    cleaned = (value or "").strip().replace(",", "").replace("₹", "").replace("rs", "")
    cleaned = re.sub(r"[^\d.]", "", cleaned, flags=re.I)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def amount_speak_kn(value: str) -> str:
    """Speakable Kannada amount phrase for TTS."""
    amt = _parse_amount(value)
    if amt is None:
        return (value or "").strip() or "—"
    whole = int(amt)
    paise = int(round((amt - whole) * 100))
    if paise == 100:
        whole += 1
        paise = 0
    if whole >= 100000:
        lakhs = whole // 100000
        rest = whole % 100000
        if rest == 0:
            phrase = f"{_int_kn(lakhs)} ಲಕ್ಷ ರೂಪಾಯಿ"
        else:
            phrase = f"{_int_kn(lakhs)} ಲಕ್ಷ {_int_kn(rest)} ರೂಪಾಯಿ"
    elif whole >= 1000:
        thousands = whole // 1000
        rest = whole % 1000
        if rest == 0:
            phrase = f"{_int_kn(thousands)} ಸಾವಿರ ರೂಪಾಯಿ"
        else:
            phrase = f"{_int_kn(thousands)} ಸಾವಿರ {_int_kn(rest)} ರೂಪಾಯಿ"
    else:
        phrase = f"{_int_kn(whole)} ರೂಪಾಯಿ"
    if paise:
        phrase = f"{phrase} {_int_kn(paise)} ಪೈಸೆ"
    return phrase


def _int_kn(n: int) -> str:
    """Kannada number words for amounts up to the lakh remainder."""
    if n <= 0:
        return "ಸೊನ್ನೆ"
    small = {
        1: "ಒಂದು",
        2: "ಎರಡು",
        3: "ಮೂರು",
        4: "ನಾಲ್ಕು",
        5: "ಐದು",
        6: "ಆರು",
        7: "ಏಳು",
        8: "ಎಂಟು",
        9: "ಒಂಬತ್ತು",
        10: "ಹತ್ತು",
        11: "ಹನ್ನೊಂದು",
        12: "ಹನ್ನೆರಡು",
        13: "ಹದಿಮೂರು",
        14: "ಹದಿನಾಲ್ಕು",
        15: "ಹದಿನೈದು",
        16: "ಹದಿನಾರು",
        17: "ಹದಿನೇಳು",
        18: "ಹದಿನೆಂಟು",
        19: "ಹತ್ತೊಂಬತ್ತು",
    }
    if n in small:
        return small[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        tens_words = {
            2: ("ಇಪ್ಪತ್ತು", "ಇಪ್ಪತ್ತ"),
            3: ("ಮೂವತ್ತು", "ಮೂವತ್ತ"),
            4: ("ನಲವತ್ತು", "ನಲವತ್ತ"),
            5: ("ಐವತ್ತು", "ಐವತ್ತ"),
            6: ("ಅರವತ್ತು", "ಅರವತ್ತ"),
            7: ("ಎಪ್ಪತ್ತು", "ಎಪ್ಪತ್ತ"),
            8: ("ಎಂಬತ್ತು", "ಎಂಬತ್ತ"),
            9: ("ತೊಂಬತ್ತು", "ತೊಂಬತ್ತ"),
        }
        full, stem = tens_words[tens]
        suffixes = {
            1: "ೊಂದು",
            2: "ೆರಡು",
            3: "ಮೂರು",
            4: "ನಾಲ್ಕು",
            5: "ೈದು",
            6: "ಾರು",
            7: "ೇಳು",
            8: "ೆಂಟು",
            9: "ೊಂಬತ್ತು",
        }
        return full if ones == 0 else f"{stem}{suffixes[ones]}"
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        base = "ನೂರು" if hundreds == 1 else f"{_int_kn(hundreds)} ನೂರು"
        return base if rest == 0 else f"{base[:-1]} {_int_kn(rest)}"
    if n < 100000:
        thousands, rest = divmod(n, 1000)
        base = f"{_int_kn(thousands)} ಸಾವಿರ"
        return base if rest == 0 else f"{base} {_int_kn(rest)}"
    return str(n)


def amount_display(value: str) -> str:
    amt = _parse_amount(value)
    if amt is None:
        return (value or "").strip() or "—"
    return f"₹ {amt:,.2f}"


def _date_display(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return "—"
    if raw.lower() in {"today", "indu", "ಇಂದು"}:
        return datetime.now().strftime("%d/%m/%Y")
    return raw


def _date_speak_kn(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return "—"
    today = datetime.now().strftime("%d/%m/%Y")
    if raw == today or raw.lower() in {"today", "indu", "ಇಂದು"}:
        return "ಇಂದು"
    return raw


def _field_speak(field: dict[str, Any], value: str) -> str:
    fid = str(field.get("id") or "")
    ftype = str(field.get("type") or "text").lower()
    if fid in _ACCOUNT_FIELD_IDS or ftype == "digits":
        if len(re.sub(r"\D", "", value)) >= 8:
            return digits_to_kannada_words(value)
    if fid in _AMOUNT_FIELD_IDS or ftype == "amount":
        return amount_speak_kn(value)
    if ftype == "date":
        return _date_speak_kn(value)
    cleaned = value.strip()
    return _TEXT_VALUE_KN.get(cleaned.lower(), cleaned)


def _field_display(field: dict[str, Any], value: str) -> str:
    fid = str(field.get("id") or "")
    ftype = str(field.get("type") or "text").lower()
    if fid in _ACCOUNT_FIELD_IDS or (ftype == "digits" and "account" in fid):
        return mask_account(value)
    if fid in _AMOUNT_FIELD_IDS or ftype == "amount":
        return amount_display(value)
    if ftype == "date":
        return _date_display(value)
    return value.strip() or "—"


_FORM_SUMMARY_MAX_CHARS = 1200


def _truncate_summary_kn(text: str) -> str:
    """Keep TTS under ~30s for long forms."""
    if len(text) <= _FORM_SUMMARY_MAX_CHARS:
        return text
    cut = text[: _FORM_SUMMARY_MAX_CHARS].rsplit(" ", 1)[0]
    return f"{cut} … ಹೆಚ್ಚಿನ ವಿವರಗಳು ಪರದೆಯ ಮೇಲೆ ಕಾಣಿಸುತ್ತವೆ."


def build_form_summary_kn(form: dict[str, Any], values: dict[str, str]) -> dict[str, Any]:
    """
    Build Kannada summary for voice read-back and on-screen display.

    Returns:
        summary_kn, confirm_prompt_kn, lines[{field_id, label_kn, display_kn, speak_kn}]
    """
    from backend.lobby_phrases import (
        FORM_SUMMARY_CLOSER_KN,
        FORM_SUMMARY_OPENER_KN,
        FORM_WHOLE_CONFIRM_KN,
    )

    lines: list[dict[str, str]] = []
    parts: list[str] = [FORM_SUMMARY_OPENER_KN]

    for field in form.get("fields") or []:
        if field.get("auto"):
            continue
        fid = str(field.get("id") or "")
        if not fid:
            continue
        raw = (values.get(fid) or "").strip()
        if not raw:
            if field.get("required"):
                continue
            continue
        label = (field.get("label_kn") or field.get("label_en") or fid).strip()
        display = _field_display(field, raw)
        speak = _field_speak(field, raw)
        lines.append(
            {
                "field_id": fid,
                "label_kn": label,
                "display_kn": display,
                "speak_kn": speak,
            }
        )
        parts.append(f"{label} {speak}.")

    parts.append(FORM_SUMMARY_CLOSER_KN)
    summary_kn = _truncate_summary_kn(" ".join(p for p in parts if p))

    return {
        "form_id": form.get("id") or "",
        "title_kn": form.get("title_kn") or "",
        "summary_kn": summary_kn,
        "confirm_prompt_kn": FORM_WHOLE_CONFIRM_KN,
        "lines": lines,
    }
