"""
Typed field extractors for English text (after IndicTrans2 Kn→En).

No API keys — pure rules on translated English so form boxes get clean values.
"""

from __future__ import annotations

import re
from datetime import datetime

# Spoken English number words → digits (IndicTrans2 often outputs English words)
_ONES = {
    "zero": 0, "oh": 0, "o": 0,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SCALES = {
    "hundred": 100,
    "thousand": 1000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
}

_NAME_PREFIXES = re.compile(
    r"^(?:my\s+name\s+is|i\s+am|i'm|name\s+is|it\s+is|this\s+is)\s+",
    re.IGNORECASE,
)
_AMOUNT_PREFIXES = re.compile(
    r"^(?:the\s+)?(?:amount\s+is|i\s+(?:want|need|wish)\s+(?:to\s+)?"
    r"(?:withdraw|deposit|apply\s+for)?\s*|rupees?|rs\.?|inr)\s*",
    re.IGNORECASE,
)
_ACCOUNT_PREFIXES = re.compile(
    r"^(?:my\s+)?(?:account\s+(?:number|no\.?)\s*(?:is)?|a/?c\s*(?:no\.?)?\s*(?:is)?)\s*",
    re.IGNORECASE,
)

_ACCOUNT_TYPES = {
    "savings": "Savings",
    "saving": "Savings",
    "current": "Current",
    "salary": "Salary",
    "fixed deposit": "Fixed Deposit",
    "fd": "Fixed Deposit",
}
_LOAN_TYPES = {
    "home": "Home Loan",
    "housing": "Home Loan",
    "personal": "Personal Loan",
    "education": "Education Loan",
    "educational": "Education Loan",
    "car": "Car Loan",
    "vehicle": "Car Loan",
    "auto": "Car Loan",
    "gold": "Gold Loan",
}
_DEPOSIT_MODES = {
    "cash": "Cash",
    "cheque": "Cheque",
    "check": "Cheque",
    "dd": "Demand Draft",
    "demand draft": "Demand Draft",
}
_CHEQUE_LEAVES = {
    "10": "10",
    "ten": "10",
    "25": "25",
    "twenty five": "25",
    "twentyfive": "25",
    "50": "50",
    "fifty": "50",
    "100": "100",
    "hundred": "100",
}
_CARD_TYPES = {
    "atm": "ATM / Debit Card",
    "debit": "ATM / Debit Card",
    "credit": "Credit Card",
}
_FD_TENURE = {
    "1 year": "1 year",
    "one year": "1 year",
    "2 year": "2 years",
    "two year": "2 years",
    "3 year": "3 years",
    "three year": "3 years",
    "5 year": "5 years",
    "five year": "5 years",
    "6 month": "6 months",
    "six month": "6 months",
    "12 month": "12 months",
}
_INTEREST_PAYOUT = {
    "monthly": "Monthly",
    "quarterly": "Quarterly",
    "on maturity": "On maturity",
    "maturity": "On maturity",
    "cumulative": "Cumulative / On maturity",
}

# Kannada option words (incl. common English loanwords as spoken) for choice fields.
# Matched on the Kannada transcript, so a slightly misheard word ("ಉಳಿದಾಯ" for
# "ಉಳಿತಾಯ") still lands on the right option instead of a wrong translation
# ("Remaining").
_KN_CHOICES: dict[str, dict[str, str]] = {
    "account_type": {
        "ಉಳಿತಾಯ": "Savings",
        "ಸೇವಿಂಗ್ಸ್": "Savings",
        "ಚಾಲ್ತಿ": "Current",
        "ಕರೆಂಟ್": "Current",
        "ವೇತನ": "Salary",
        "ಸ್ಯಾಲರಿ": "Salary",
    },
    "loan_type": {
        "ಗೃಹ": "Home Loan",
        "ಮನೆ": "Home Loan",
        "ವೈಯಕ್ತಿಕ": "Personal Loan",
        "ಪರ್ಸನಲ್": "Personal Loan",
        "ಶಿಕ್ಷಣ": "Education Loan",
        "ಎಜುಕೇಶನ್": "Education Loan",
        "ವಾಹನ": "Car Loan",
        "ಕಾರ್": "Car Loan",
        "ಚಿನ್ನ": "Gold Loan",
        "ಗೋಲ್ಡ್": "Gold Loan",
    },
    "deposit_mode": {
        "ನಗದು": "Cash",
        "ಕ್ಯಾಶ್": "Cash",
        "ಚೆಕ್": "Cheque",
        "ಡಿಡಿ": "Demand Draft",
    },
    "interest_payout": {
        "ತ್ರೈಮಾಸಿಕ": "Quarterly",
        "ಮಾಸಿಕ": "Monthly",
        "ತಿಂಗಳು": "Monthly",
        "ಮುಕ್ತಾಯ": "On maturity",
        "ಅವಧಿ ಪೂರ್ಣ": "On maturity",
    },
}

# Choice fields whose answer MUST be one of these values. An unrecognised answer
# returns "" (→ validation asks again, listing the options) rather than saving
# whatever the translation produced.
CHOICE_OPTIONS: dict[str, frozenset[str]] = {
    "account_type": frozenset({"Savings", "Current", "Salary", "Fixed Deposit"}),
    "loan_type": frozenset(
        {"Home Loan", "Personal Loan", "Education Loan", "Car Loan", "Gold Loan"}
    ),
    "deposit_mode": frozenset({"Cash", "Cheque", "Demand Draft"}),
    "interest_payout": frozenset(
        {"Monthly", "Quarterly", "On maturity", "Cumulative / On maturity"}
    ),
}


def _match_choice_kannada(kannada: str, field_id: str, *, fuzzy: bool = True) -> str | None:
    """Exact Kannada option word first, then (if fuzzy) a near match one or two letters off."""
    options = _KN_CHOICES.get(field_id)
    text = (kannada or "").strip()
    if not options or not text:
        return None
    for key in sorted(options, key=len, reverse=True):
        if key in text:
            return options[key]
    if not fuzzy:
        return None
    from difflib import SequenceMatcher

    best, best_ratio = None, 0.0
    for word in re.findall(r"\S+", text):
        for key, value in options.items():
            if len(key) < 4:  # too short to fuzzy-match safely
                continue
            ratio = SequenceMatcher(None, word, key).ratio()
            if ratio > best_ratio:
                best, best_ratio = value, ratio
    return best if best_ratio >= 0.8 else None


_IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", re.I)
_PAN_RE = re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b", re.I)
_MOBILE_RE = re.compile(r"\b([6-9]\d{9})\b")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]+|\d+", text.lower())


def _words_to_number(tokens: list[str]) -> int | None:
    """Parse a sequence of English number words into an integer."""
    if not tokens:
        return None
    if len(tokens) == 1 and tokens[0].isdigit():
        return int(tokens[0])

    total = 0
    current = 0
    seen = False
    for tok in tokens:
        if tok.isdigit():
            current += int(tok)
            seen = True
        elif tok in _ONES:
            current += _ONES[tok]
            seen = True
        elif tok in _TENS:
            current += _TENS[tok]
            seen = True
        elif tok in _SCALES:
            scale = _SCALES[tok]
            if current == 0:
                current = 1
            current *= scale
            if scale >= 1000:
                total += current
                current = 0
            seen = True
        elif tok in {"and", "rupee", "rupees", "only", "rs", "inr"}:
            continue
        else:
            if seen:
                break
            return None
    result = total + current
    return result if seen else None


def _extract_digits(text: str) -> str:
    """Prefer Arabic digits already present; else digit-by-digit spoken words."""
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 4:
        return digits

    tokens = _tokenize(text)
    if tokens and all(t in _ONES or t.isdigit() for t in tokens if t not in {"and"}):
        out = []
        for t in tokens:
            if t in {"and"}:
                continue
            if t.isdigit():
                out.append(t)
            elif t in _ONES and _ONES[t] < 10:
                out.append(str(_ONES[t]))
        if out:
            return "".join(out)

    n = _words_to_number(tokens)
    return str(n) if n is not None else digits


_KN_DIGITS = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")
_KN = r"[ಀ-೿]*"  # rest of a Kannada word ("ಲಕ್ಷದ", "ಸಾವಿರ")
# A figure followed by a scale word: "10 lakh", "2.5 ಲಕ್ಷ", "5 thousand", "1 ಕೋಟಿ".
_SCALED_FIGURE = re.compile(
    r"(\d+(?:\.\d+)?)\s*("
    r"crores?|lakhs?|lacs?|millions?|billions?|thousands?|hundreds?|"
    rf"ಕೋಟಿ{_KN}|ಲಕ್ಷ{_KN}|ಸಾವಿರ{_KN}|ಸಾವ್ರ{_KN}|ನೂರ{_KN}"
    r")",
    re.IGNORECASE,
)
_SCALE_OF = (
    ("crore", 10_000_000), ("ಕೋಟಿ", 10_000_000),
    ("billion", 1_000_000_000), ("million", 1_000_000),
    ("lakh", 100_000), ("lac", 100_000), ("ಲಕ್ಷ", 100_000),
    ("thousand", 1000), ("ಸಾವಿರ", 1000), ("ಸಾವ್ರ", 1000),
    ("hundred", 100), ("ನೂರ", 100),
)


def _scale_value(word: str) -> int:
    w = word.lower()
    for stem, value in _SCALE_OF:
        if w.startswith(stem):
            return value
    return 1


def amount_with_scales(text: str) -> str | None:
    """Rupees from figures with scale words ("10 lakh" → 1000000, "2 lakh 50 thousand"
    → 250000), in Kannada or English. None when the text has no figure + scale word."""
    t = (text or "").translate(_KN_DIGITS)
    t = re.sub(r"(?<=\d),(?=\d)", "", t)
    matches = list(_SCALED_FIGURE.finditer(t))
    if not matches:
        return None
    total = sum(float(m.group(1)) * _scale_value(m.group(2)) for m in matches)
    # A plain figure after the last scale word: "2 lakh 500".
    tail = re.match(r"\s*(?:and\s+|ಮತ್ತು\s+)?(\d+)\b", t[matches[-1].end():])
    if tail:
        rest = int(tail.group(1))
        if rest < min(_scale_value(m.group(2)) for m in matches):
            total += rest
    return str(int(round(total)))


def _extract_amount(text: str) -> str:
    scaled = amount_with_scales(text)
    if scaled:
        return scaled
    cleaned = _AMOUNT_PREFIXES.sub("", text.strip())
    m = re.search(r"(\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?", cleaned.replace(" ", ""))
    if m:
        return m.group(1).replace(",", "")
    m2 = re.search(r"(\d{1,3}(?:,\d{2,3})+|\d+)", cleaned)
    if m2:
        return m2.group(1).replace(",", "")

    n = _words_to_number(_tokenize(cleaned))
    return str(n) if n is not None else cleaned.strip()


def _extract_name(text: str) -> str:
    cleaned = _NAME_PREFIXES.sub("", text.strip())
    cleaned = re.sub(
        r"^(?:ನ(?:ನ್ನ|ನ)?\s*ಹೆಸರು|ಹೆಸರು|ಪೂರ್ಣ\s*ಹೆಸರು)\s*",
        "",
        cleaned,
    ).strip()
    cleaned = re.sub(r"[.؟!]+$", "", cleaned).strip()
    cleaned = re.sub(r"\b(?:please|sir|madam)\b\.?$", "", cleaned, flags=re.I).strip()
    if not cleaned:
        return text.strip()
    return " ".join(w.capitalize() for w in cleaned.split())


def _words_to_date_part(tokens: list[str]) -> int | None:
    """Convert a list of English number word tokens to an integer (for day/month/year).
    Handles: 'fourteen'=14, 'two thousand five'=2005, 'nineteen ninety five'=1995.
    """
    # Special: "nineteen|eighteen|seventeen... <tens><ones>" = 1900s/1800s etc.
    # e.g. 'nineteen ninety five' -> 1995, 'nineteen eighty' -> 1980
    if len(tokens) >= 2 and tokens[0] in _ONES:
        century_prefix = _ONES[tokens[0]]  # e.g. nineteen=19
        if 13 <= century_prefix <= 20:
            rest = _words_to_number(tokens[1:])
            if rest is not None and 0 <= rest <= 99:
                return century_prefix * 100 + rest
    return _words_to_number(tokens)


def _extract_date(text: str) -> str:
    t = text.strip()

    # 1. Try digit patterns first (21/06/2005 or 21-06-2005)
    for fmt, out_fmt in (
        (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "%d/%m/%Y"),
        (r"(\d{1,2})[/-](\d{1,2})[/-](\d{2})", "%d/%m/%y"),
    ):
        m = re.search(fmt, t)
        if m:
            try:
                if out_fmt.endswith("%y"):
                    dt = datetime.strptime(
                        f"{m.group(1)}/{m.group(2)}/{m.group(3)}", "%d/%m/%y"
                    )
                else:
                    dt = datetime.strptime(
                        f"{m.group(1)}/{m.group(2)}/{m.group(3)}", "%d/%m/%Y"
                    )
                return dt.strftime("%d/%m/%Y")
            except ValueError:
                pass

    if re.search(r"\btoday\b", t, re.I):
        return datetime.now().strftime("%d/%m/%Y")

    # 2. Try English number words — handles "twenty one six two thousand five"
    #    Strategy: tokenize, then greedily parse day/month/year groups.
    #    Day = first 1–2 word group (1–31)
    #    Month = second 1–2 word group (1–12)
    #    Year = remaining tokens (e.g. "two thousand five" = 2005)
    clean = re.sub(r"[,./\-]+", " ", t.lower()).strip()
    clean = re.sub(r"\b(of|the|st|nd|rd|th|born|dob|date|birth|my|is)\b", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    tokens = [tok for tok in clean.split() if tok]

    # All-word tokens — try to extract 3 groups
    # Use a sliding window: try all split points [i, j] where
    # tokens[0:i] = day, tokens[i:j] = month, tokens[j:] = year
    best: tuple[int, int, int] | None = None
    day_splits = list(range(1, min(3, len(tokens))))
    # "twenty one six …" — a tens word + a ones word is one day (21), not day 20 + month 1.
    if len(tokens) > 2 and tokens[0] in _TENS and 1 <= _ONES.get(tokens[1], 0) <= 9:
        day_splits = [2, 1]
    for i in day_splits:
        for j in range(i + 1, min(i + 3, len(tokens))):
            day_tok = tokens[:i]
            mon_tok = tokens[i:j]
            yr_tok = tokens[j:]
            if not yr_tok:
                continue
            day = _words_to_date_part(day_tok)
            mon = _words_to_date_part(mon_tok)
            yr = _words_to_date_part(yr_tok)
            if day is None or mon is None or yr is None:
                continue
            if not (1 <= day <= 31 and 1 <= mon <= 12):
                continue
            # Prefer 4-digit years; handle 2-digit years (e.g. "five" = 2005? no — 5)
            # Only accept years >= 1900
            if yr < 100:
                yr = 2000 + yr if yr < 50 else 1900 + yr
            if yr < 1900 or yr > 2100:
                continue
            best = (day, mon, yr)
            break
        if best:
            break

    if best:
        day, mon, yr = best
        try:
            dt = datetime(yr, mon, day)
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            pass

    # 3. Mixed: some digits, some words — try to extract 3 numeric tokens
    num_tokens: list[int] = []
    all_toks = _tokenize(t)
    i = 0
    while i < len(all_toks) and len(num_tokens) < 4:
        tok = all_toks[i]
        if tok.isdigit():
            num_tokens.append(int(tok))
            i += 1
        elif tok in _ONES:
            # Try to build a multi-word number (for year like "two thousand five")
            sub: list[str] = []
            while i < len(all_toks):
                t2 = all_toks[i]
                if t2 in _ONES or t2 in _TENS or t2 in _SCALES or t2.isdigit():
                    sub.append(t2)
                    i += 1
                    # Stop if we have enough for day/month (1-2 words) or a year
                    n = _words_to_number(sub)
                    if n is not None and (1 <= n <= 31 or n >= 1000):
                        # If it's a plausible year (>100), stop here
                        if n > 31:
                            num_tokens.append(n)
                            break
                        # Otherwise see if next token extends the number
                        if i < len(all_toks) and all_toks[i] not in _ONES and all_toks[i] not in _TENS and all_toks[i] not in _SCALES:
                            num_tokens.append(n)
                            break
                else:
                    n = _words_to_number(sub)
                    if n is not None:
                        num_tokens.append(n)
                    break
        elif tok in _TENS:
            sub = [tok]
            i += 1
            if i < len(all_toks) and all_toks[i] in _ONES:
                sub.append(all_toks[i])
                i += 1
            n = _words_to_number(sub)
            if n is not None:
                num_tokens.append(n)
        else:
            i += 1

    if len(num_tokens) >= 3:
        d, m2, y = num_tokens[0], num_tokens[1], num_tokens[2]
        if y < 100:
            y = 2000 + y if y < 50 else 1900 + y
        try:
            dt = datetime(y, m2, d)
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            pass

    return t


def _match_choice(text: str, mapping: dict[str, str]) -> str | None:
    lower = text.lower()
    for key in sorted(mapping.keys(), key=len, reverse=True):
        if key in lower:
            return mapping[key]
    return None


def _extract_address(text: str) -> str:
    cleaned = re.sub(
        r"^(?:my\s+)?(?:address\s+is|i\s+live\s+at|i\s+stay\s+at)\s+",
        "",
        text.strip(),
        flags=re.I,
    )
    return cleaned.strip() or text.strip()


def _extract_ifsc(text: str) -> str:
    m = _IFSC_RE.search(text.replace(" ", ""))
    if m:
        return m.group(1).upper()
    compact = re.sub(r"[^A-Za-z0-9]", "", text.upper())
    m2 = _IFSC_RE.search(compact)
    if m2:
        return m2.group(1).upper()
    return text.strip().upper()


def _extract_pan(text: str) -> str:
    m = _PAN_RE.search(text.replace(" ", "").upper())
    if m:
        return m.group(1).upper()
    compact = re.sub(r"[^A-Za-z0-9]", "", text.upper())
    m2 = _PAN_RE.search(compact)
    return m2.group(1).upper() if m2 else text.strip().upper()


def _extract_mobile(text: str) -> str:
    m = _MOBILE_RE.search(re.sub(r"\s+", "", text))
    if m:
        return m.group(1)
    digits = _extract_digits(text)
    if len(digits) >= 10:
        return digits[-10:]
    return digits or text.strip()


def extract_field_value(
    english_text: str,
    field_type: str = "text",
    field_id: str = "",
    kannada_text: str = "",
) -> str:
    """
    Turn IndicTrans2 English output into a clean form-box value.

    Parameters
    ----------
    english_text:
        English string from translate_kn_to_en().
    field_type:
        One of text | digits | amount | date | choice.
    field_id:
        Field id for specialized maps (account_type, loan_type, ifsc, …).
    """
    text = (english_text or "").strip()
    fid = (field_id or "").lower()
    ftype = (field_type or "text").lower()

    choice_key = "interest_payout" if fid == "interest_payment" else fid
    if choice_key in CHOICE_OPTIONS:
        english_map = {
            "account_type": _ACCOUNT_TYPES,
            "loan_type": _LOAN_TYPES,
            "deposit_mode": _DEPOSIT_MODES,
            "interest_payout": _INTEREST_PAYOUT,
        }[choice_key]
        # Customer's own Kannada word > translation > near-miss Kannada word.
        # No match -> "" so validation re-asks with the options (never "Remaining").
        return (
            _match_choice_kannada(kannada_text, choice_key, fuzzy=False)
            or _match_choice(text, english_map)
            or _match_choice_kannada(kannada_text, choice_key)
            or ""
        )

    from backend.forms.as_spoken import as_spoken_value, is_as_spoken_field

    if is_as_spoken_field(fid) and (kannada_text or "").strip():
        spoken = as_spoken_value(kannada_text)
        if spoken:
            return spoken

    if not text:
        return ""

    if fid in {"card_type", "atm_card_type"}:
        return _match_choice(text, _CARD_TYPES) or "ATM / Debit Card"

    if fid in {"number_of_leaves", "cheque_leaves"}:
        hit = _match_choice(text, _CHEQUE_LEAVES)
        if hit:
            return hit
        digits = _extract_digits(text)
        return digits or text.strip()

    if fid in {"tenure", "fd_tenure", "deposit_tenure"}:
        return _match_choice(text, _FD_TENURE) or text.strip()

    if fid in {"ifsc", "ifsc_code", "beneficiary_ifsc"}:
        return _extract_ifsc(text)

    if fid in {"pan", "pan_number"}:
        return _extract_pan(text)

    if fid in {
        "full_name", "name", "applicant_name", "beneficiary_name",
        "remitter_name", "nominee_name",
    }:
        return _extract_name(text)

    if fid == "address" or fid.endswith("_address"):
        return _extract_address(text)

    if fid in {
        "mobile", "mobile_number", "phone", "new_mobile", "old_mobile",
        "registered_mobile",
    }:
        return _extract_mobile(text)

    if ftype == "digits" or fid in {
        "account_number", "beneficiary_account", "remitter_account",
        "cheque_number", "from_cheque", "to_cheque",
    }:
        cleaned = _ACCOUNT_PREFIXES.sub("", text)
        return _extract_digits(cleaned)

    if ftype == "amount" or fid in {
        "amount", "loan_amount", "income", "fd_amount", "deposit_amount",
    }:
        # The customer's own "10 ಲಕ್ಷ" beats the translation ("1 million", "10 lakh.").
        return amount_with_scales(kannada_text or "") or _extract_amount(text)

    if ftype == "date" or "date" in fid or fid == "date_of_birth":
        return _extract_date(text)

    if fid in {"purpose", "remarks", "reason"}:
        return text.strip().capitalize()

    cleaned = _NAME_PREFIXES.sub("", text)
    if len(cleaned.split()) <= 6:
        return " ".join(w.capitalize() for w in cleaned.split())
    return cleaned.strip()
