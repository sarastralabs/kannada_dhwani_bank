"""
Names and addresses are kept as the customer said them — never translated.

Translating a name or a place produces nonsense ("ಬುಜ್ಜಿರಿ" → "Be Aware",
"ನಾವು ಬಂದ" → "We've come to"). These fields take the Kannada the speech
model heard, drop lead-ins such as "ನನ್ನ ಹೆಸರು", and spell it in English
letters for the printed form (ಅಶ್ವಿನ್ → "Ashwin", ಬಂಟ್ವಾಳ → "Bantwala").
"""

from __future__ import annotations

import re

from backend.forms.stt_tuning import NAME_FIELD_IDS

ADDRESS_FIELD_IDS = frozenset({"address", "residential_address", "branch_address"})


def is_as_spoken_field(field_id: str) -> bool:
    fid = (field_id or "").strip().lower()
    return fid in NAME_FIELD_IDS or fid in ADDRESS_FIELD_IDS or fid.endswith("_address")


_VOWEL_SIGNS = {
    "ಾ": "a", "ಿ": "i", "ೀ": "i", "ು": "u", "ೂ": "u", "ೃ": "ru",
    "ೆ": "e", "ೇ": "e", "ೈ": "ai", "ೊ": "o", "ೋ": "o", "ೌ": "au",
}
_INDEPENDENT_VOWELS = {
    "ಅ": "a", "ಆ": "aa", "ಇ": "i", "ಈ": "i", "ಉ": "u", "ಊ": "u", "ಋ": "ru",
    "ಎ": "e", "ಏ": "e", "ಐ": "ai", "ಒ": "o", "ಓ": "o", "ಔ": "au",
}
_CONSONANTS = {
    "ಕ": "k", "ಖ": "kh", "ಗ": "g", "ಘ": "gh", "ಙ": "ng",
    "ಚ": "ch", "ಛ": "chh", "ಜ": "j", "ಝ": "jh", "ಞ": "ny",
    "ಟ": "t", "ಠ": "th", "ಡ": "d", "ಢ": "dh", "ಣ": "n",
    "ತ": "t", "ಥ": "th", "ದ": "d", "ಧ": "dh", "ನ": "n",
    "ಪ": "p", "ಫ": "ph", "ಬ": "b", "ಭ": "bh", "ಮ": "m",
    "ಯ": "y", "ರ": "r", "ಱ": "r", "ಲ": "l", "ವ": "v",
    "ಶ": "sh", "ಷ": "sh", "ಸ": "s", "ಹ": "h", "ಳ": "l",
}
_VIRAMA = "್"
_ANUSVARA = "ಂ"
_VISARGA = "ಃ"
_LABIALS = frozenset("ಪಫಬಭಮ")

_KANNADA_RE = re.compile(r"[ಀ-೿]")
_KN_DIGITS = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")


def has_kannada(text: str) -> bool:
    return bool(_KANNADA_RE.search(text or ""))


def transliterate_kannada(text: str) -> str:
    """
    Kannada script → English letters, title-cased per word. Latin text passes through.

    Spelling rules that matter for names and places:
      ಂ before ಪ/ಫ/ಬ/ಭ/ಮ is "m", otherwise "n"   (ಸಂಪತ್ → Sampat, ಬಂಟ್ವಾಳ → Bantwala)
      ವ joined to a consonant is "w"               (ಅಶ್ವಿನ್ → Ashwin, ಸ್ವಾಮಿ → Swami)
    """
    text = (text or "").strip().translate(_KN_DIGITS)
    if not text:
        return ""
    if not has_kannada(text):
        return text

    out: list[str] = []
    chars = list(text)
    i = 0
    while i < len(chars):
        ch = chars[i]
        if ch.isspace():
            out.append(" ")
            i += 1
            continue
        if ch in _INDEPENDENT_VOWELS:
            out.append(_INDEPENDENT_VOWELS[ch])
            i += 1
            continue
        if ch in _CONSONANTS:
            base = _CONSONANTS[ch]
            i += 1
            # Conjuncts: consonant + virama + consonant …
            while (
                i + 1 < len(chars)
                and chars[i] == _VIRAMA
                and chars[i + 1] in _CONSONANTS
            ):
                nxt = chars[i + 1]
                base += "w" if nxt == "ವ" else _CONSONANTS[nxt]
                i += 2
            if i < len(chars) and chars[i] == _VIRAMA:
                i += 1  # dead consonant — no vowel
            elif i < len(chars) and chars[i] in _VOWEL_SIGNS:
                base += _VOWEL_SIGNS[chars[i]]
                i += 1
            else:
                base += "a"
            out.append(base)
            continue
        if ch == _ANUSVARA:
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            out.append("m" if nxt in _LABIALS else "n")
            i += 1
            continue
        if ch == _VISARGA:
            out.append("h")
            i += 1
            continue
        if ch in _VOWEL_SIGNS or ch == _VIRAMA:
            i += 1  # stray mark
            continue
        out.append(ch)
        i += 1

    words = "".join(out).split()
    return " ".join(w[:1].upper() + w[1:].lower() for w in words)


# Lead-ins customers say before the answer (longest first).
_LEAD_INS = (
    "ನನ್ನ ಪೂರ್ತಿ ಹೆಸರು", "ನನ್ನ ಪೂರ್ಣ ಹೆಸರು", "ನನ್ನ ಮನೆಯ ವಿಳಾಸ", "ನನ್ನ ಮನೆ ವಿಳಾಸ",
    "ನನ್ನ ಹೆಸರು", "ನನ್ನ ಹೆಸರ", "ನನ್ನ ವಿಳಾಸ", "ನನ್ನ ಊರು", "ನಮ್ಮ ಊರು", "ನಮ್ಮ ವಿಳಾಸ",
    "ಹೆಸರು", "ವಿಳಾಸ", "ನಾನು",
)
# Endings like "… ಅಂತ / ಎಂದು / ಆಗಿದೆ / ಇದೆ".
_TRAILERS = ("ಅಂತ", "ಅಂತಾ", "ಎಂದು", "ಆಗಿದೆ", "ಇದೆ", "ಆಗಿರುತ್ತದೆ")
_EN_LEAD_INS = re.compile(
    r"^\s*(?:my\s+)?(?:full\s+)?(?:name|address)\s+(?:is\s+)?|^\s*(?:i\s+am|i'm|this\s+is)\s+",
    re.IGNORECASE,
)
_PUNCT_EDGES = re.compile(r"^[\s.,!?।]+|[\s.,!?।]+$")


def clean_spoken(text: str) -> str:
    """Drop lead-ins / endings and edge punctuation; keep the answer itself."""
    t = _PUNCT_EDGES.sub("", (text or "").replace("�", ""))
    for lead in _LEAD_INS:
        if t.startswith(lead + " "):
            t = t[len(lead):].strip()
            break
    words = t.split()
    while len(words) > 1 and words[-1].strip(".,") in _TRAILERS:
        words.pop()
    t = " ".join(words)
    t = _EN_LEAD_INS.sub("", t)
    return _PUNCT_EDGES.sub("", t)


def as_spoken_value(kannada_text: str) -> str:
    """Form value for a name/address: what was heard, in English letters."""
    return transliterate_kannada(clean_spoken(kannada_text))
