"""
Voice form menu — list available forms and match user choice from speech.

Used when customer says "I want to fill a form" in Kannada/English without
naming a specific form, or when picking from the numbered menu.
"""

from __future__ import annotations

import re
from typing import Any

from api import forms_catalog

# Keywords per form (English + common Kannada transliterations in STT output)
# IMPORTANT: Only include keywords that are UNAMBIGUOUSLY transactional.
# Do NOT include short words like "atm", "loan", "fd", "transfer" that also appear
# in informational queries ("what is ATM block procedure", "loan interest rate").
# Those queries should go through NLU, not form matching.
FORM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "balance_inquiry": (
        # Balance uses NLU check_balance intent — not direct form keyword bypass
    ),
    "cash_withdrawal": (
        "cash withdrawal", "withdraw cash", "hinpade", "hinpaduva",
        "withdraw money", "take cash", "cash out", "ಹಣ ಹಿಂಪಡೆ",
    ),
    "cash_deposit": (
        "cash deposit", "deposit money", "thevani", "tevani",
        "cheque deposit", "check deposit", "ಠೇವಣಿ ಮಾಡ",
    ),
    "open_account": (
        "open account", "new account", "account opening",
        "khate tege", "khata terey", "ಖಾತೆ ತೆರೆ",
    ),
    "apply_loan": (
        "loan application", "apply for loan", "apply loan",
        "loan apply", "salakke arji", "ಸಾಲ ಅರ್ಜಿ",
    ),
    "rtgs_neft": (
        "rtgs", "neft", "fund transfer", "wire transfer", "imps",
        "rtgs form", "neft form",
    ),
    "cheque_book_request": (
        "cheque book", "check book", "chequebook", "chek buk",
        "new cheque book", "cheque leaves request",
    ),
    "atm_debit_card": (
        # "atm" alone is too short — matches "block ATM" informational queries
        # Only match clear NEW CARD requests
        "new atm card", "atm card apply", "debit card apply",
        "new debit card", "card application", "atm card request",
        "ಹೊಸ ಎಟಿಎಂ ಕಾರ್ಡ್",
    ),
    "fixed_deposit": (
        # "fd" alone is too ambiguous — matches "what is FD rate" informational
        # Only match clear OPEN/CREATE FD requests
        "open fd", "create fd", "new fixed deposit", "open fixed deposit",
        "fd open", "sthira thevani open", "ಸ್ಥಿರ ಠೇವಣಿ ತೆರೆ",
    ),
    "mobile_update": (
        "mobile update", "update mobile", "change mobile number",
        "mobile number change", "registered mobile update",
        "ಮೊಬೈಲ್ ಬದಲಾ", "ಮೊಬೈಲ್ ನವೀಕರಣ",
    ),
    "stop_cheque": (
        "stop cheque", "stop check", "stop payment", "cheque stop",
        "cancel cheque", "ಚೆಕ್ ನಿಲ್ಲಿಸ",
    ),
}

MENU_TRIGGERS = (
    "fill form", "fill the form", "fill a form", "form fill", "application form",
    "which form", "what forms", "available forms", "list forms", "open form",
    "form menu", "form option", "form options", "need form", "want form",
    "arji", "arzi", "apply form",
    "ಅರ್ಜಿ", "ಫಾರ್ಮ್", "ಫಾರಂ", "ಅರ್ಜಿ ತುಂಬ", "ಫಾರ್ಮ್ ತುಂಬ",
    "ಯಾವ ಅರ್ಜಿ", "ಅರ್ಜಿಗಳು", "ಫಾರ್ಮ್ ಬೇಕು",
)

# Standalone words — word-boundary only (avoid matching "information" → "form")
_MENU_WORD_TRIGGERS = ("form", "application")

_ORDINALS = {
    "1": 1, "೧": 1, "one": 1, "first": 1, "ondu": 1, "onduvadu": 1,
    "first one": 1, "ಒಂದು": 1, "ಮೊದಲ": 1, "ಮೊದಲನೆಯದು": 1,
    "2": 2, "೨": 2, "two": 2, "second": 2, "eradu": 2, "second one": 2,
    "ಎರಡು": 2, "ಎರಡನೆಯದು": 2,
    "3": 3, "೩": 3, "three": 3, "third": 3, "mooru": 3,
    "ಮೂರು": 3, "ಮೂರನೆಯದು": 3,
    "4": 4, "೪": 4, "four": 4, "fourth": 4, "nalku": 4,
    "ನಾಲ್ಕು": 4, "ನಾಲ್ಕನೆಯದು": 4,
    "5": 5, "೫": 5, "five": 5, "fifth": 5, "aidu": 5,
    "ಐದು": 5, "ಐದನೆಯದು": 5,
    "6": 6, "೬": 6, "six": 6, "sixth": 6, "ಆರು": 6, "ಆರನೆಯದು": 6,
    "7": 7, "೭": 7, "seven": 7, "seventh": 7, "ಏಳು": 7, "ಏಳನೆಯದು": 7,
    "8": 8, "೮": 8, "eight": 8, "eighth": 8, "ಎಂಟು": 8, "ಎಂಟನೆಯದು": 8,
    "9": 9, "೯": 9, "nine": 9, "ninth": 9, "ಒಂಬತ್ತು": 9, "ಒಂಬತ್ತನೆಯದು": 9,
    "10": 10, "೧೦": 10, "ten": 10, "tenth": 10, "ಹತ್ತು": 10, "ಹತ್ತನೆಯದು": 10,
    "11": 11, "೧೧": 11, "eleven": 11, "eleventh": 11,
    "ಹನ್ನೊಂದು": 11, "ಹನ್ನೊಂದನೆಯದು": 11,
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _speech_tokens(text: str) -> list[str]:
    """Keep Kannada combining marks together when tokenising menu choices."""
    return re.findall(r"[\u0c80-\u0cff]+|[a-z0-9]+", text.lower())


def _menu_forms() -> list[dict[str, Any]]:
    """Customer-facing forms (exclude balance from menu — direct intent handles it)."""
    data = forms_catalog.list_forms()
    return [f for f in data["forms"] if f["id"] != "balance_inquiry"]


def is_form_menu_request(kannada: str, english: str) -> bool:
    """Generic 'I want to fill a form' without a specific form name."""
    combined = _norm(f"{english} {kannada}")
    triggered = any(t in combined for t in MENU_TRIGGERS)
    if not triggered:
        for word in _MENU_WORD_TRIGGERS:
            if re.search(rf"\b{re.escape(word)}\b", combined):
                triggered = True
                break
    if not triggered:
        return False
    # Specific form named → not generic menu
    if match_form_from_speech(kannada, english):
        return False
    return True


def match_form_in_menu(kannada: str, english: str, form_ids: list[str]) -> str | None:
    """Match spoken choice against a numbered menu subset (1..n in form_ids order)."""
    if not form_ids:
        return match_form_from_speech(kannada, english)

    combined = _norm(f"{english} {kannada}")
    if not combined:
        return None

    for token in _speech_tokens(combined):
        if token in _ORDINALS:
            idx = _ORDINALS[token] - 1
            if 0 <= idx < len(form_ids):
                return form_ids[idx]

    m = re.search(r"\b(?:number|option|no|form)\s*(\d{1,2})\b", combined)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(form_ids):
            return form_ids[idx]

    if re.fullmatch(r"\d{1,2}", combined.strip()):
        idx = int(combined.strip()) - 1
        if 0 <= idx < len(form_ids):
            return form_ids[idx]

    allowed = set(form_ids)
    best_id: str | None = None
    best_len = 0
    for form_id, keywords in FORM_KEYWORDS.items():
        if form_id not in allowed:
            continue
        for kw in keywords:
            if kw in combined and len(kw) > best_len:
                best_id = form_id
                best_len = len(kw)

    for fid in form_ids:
        form = forms_catalog.get_form(fid)
        if not form:
            continue
        title = _norm(form.get("title_en") or "")
        title_kn = form.get("title_kn") or ""
        if title and title in combined and len(title) > best_len:
            best_id = fid
            best_len = len(title)
        if title_kn and title_kn in (kannada or ""):
            best_id = fid
            best_len = max(best_len, len(title_kn))

    return best_id


def match_form_from_speech(kannada: str, english: str) -> str | None:
    """Return form_id if user named a form, by keyword or menu number."""
    combined = _norm(f"{english} {kannada}")
    forms = _menu_forms()

    # Number pick: "number 3", "option 2", "3", "third form"
    for token in _speech_tokens(combined):
        if token in _ORDINALS:
            idx = _ORDINALS[token] - 1
            if 0 <= idx < len(forms):
                return forms[idx]["id"]
    m = re.search(r"\b(?:number|option|no|form)\s*(\d{1,2})\b", combined)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(forms):
            return forms[idx]["id"]

    best_id: str | None = None
    best_len = 0
    for form_id, keywords in FORM_KEYWORDS.items():
        for kw in keywords:
            if not kw:
                continue
            if kw in combined and len(kw) > best_len:
                best_id = form_id
                best_len = len(kw)

    # Title match
    for form in forms:
        title = _norm(form.get("title_en") or "")
        title_kn = form.get("title_kn") or ""
        if title and title in combined:
            if len(title) > best_len:
                best_id = form["id"]
                best_len = len(title)
        if title_kn and title_kn in (kannada or ""):
            best_id = form["id"]
            best_len = max(best_len, len(title_kn))

    return best_id


def build_form_menu_payload() -> dict[str, Any]:
    """Build spoken menu + structured list for frontend."""
    forms = _menu_forms()
    lines_kn: list[str] = [
        "ಈ ಬ್ಯಾಂಕ್ ಅರ್ಜಿ ನಮೂನೆಗಳನ್ನು ಕನ್ನಡದಲ್ಲಿ ಭರ್ತಿ ಮಾಡಲು ನಾನು ಸಹಾಯ ಮಾಡುತ್ತೇನೆ.",
        "ದಯವಿಟ್ಟು ನಿಮಗೆ ಬೇಕಾದ ಅರ್ಜಿಯ ಸಂಖ್ಯೆ ಅಥವಾ ಹೆಸರನ್ನು ಹೇಳಿ.",
    ]
    items: list[dict[str, Any]] = []
    for i, form in enumerate(forms, start=1):
        lines_kn.append(f"{i}. {form['title_kn']}")
        items.append(
            {
                "index": i,
                "id": form["id"],
                "title_kn": form["title_kn"],
                "title_en": form["title_en"],
                "description_kn": form.get("description_kn") or "",
            }
        )

    speech_kn = " ".join(lines_kn)
    speech_en = (
        "We can help you fill these bank forms in Kannada. "
        + " ".join(f"{i}. {f['title_en']}" for i, f in enumerate(forms, start=1))
        + " Please say the number or name of the form you need."
    )
    return {
        "forms": items,
        "speech_kn": speech_kn,
        "speech_en": speech_en,
    }


def opening_line_for_form(form_id: str) -> tuple[str, str]:
    form = forms_catalog.get_form(form_id)
    if not form:
        return ("ಅರ್ಜಿಯನ್ನು ಪ್ರಾರಂಭಿಸುತ್ತಿದ್ದೇನೆ.", "Starting the form.")
    kn = f"ಈಗ {form['title_kn']} ಪ್ರಾರಂಭವಾಗುತ್ತದೆ. ಪ್ರತಿ ಪ್ರಶ್ನೆಗೆ ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ."
    en = f"Starting {form['title_en']}. Please answer each question in Kannada."
    return kn, en
