"""Extract digits from Kannada STT text (script + spoken words)."""

from __future__ import annotations

import re

_KN_DIGIT = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")

# Spoken Kannada number words → digit (for account numbers read digit-by-digit)
_KN_WORDS: dict[str, str] = {
    "ಸೊನ್ನೆ": "0", "ಶೂನ್ಯ": "0", "ಜೀರೋ": "0",
    "ಒಂದು": "1", "ಒನ್ನೆ": "1",
    "ಎರಡು": "2", "ಮೂರು": "3", "ನಾಲ್ಕು": "4", "ನಾಲಕು": "4",
    "ಐದು": "5", "ಆರು": "6", "ಏಳು": "7", "ಎಳು": "7",
    "ಎಂಟು": "8", "ಒಂಬತ್ತು": "9", "ಒಂಭತ್ತು": "9",
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "oh": "0", "o": "0",
}

_EN_GROUPS: dict[str, str] = {
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
    "eighty": "80", "ninety": "90",
}


def _group_words() -> dict[str, str]:
    """Common 10–99 Kannada groups for customers who do not speak digit-by-digit."""
    from backend.forms.summary_kn import _int_kn

    return {
        _int_kn(number).replace(" ", ""): str(number)
        for number in range(10, 100)
    }


_KN_GROUPS = _group_words()


def extract_digits_from_kannada(text: str) -> str:
    """Return digit string from Kannada/Latin STT for account numbers."""
    if not text or not text.strip():
        return ""

    # Native Kannada numerals + ASCII digits
    t = text.translate(_KN_DIGIT)
    direct = re.sub(r"\D", "", t)
    if direct and re.fullmatch(r"[\s,.\-೦-೯0-9]+", text):
        return direct

    # Digit-by-digit spoken words
    tokens = re.findall(r"[\u0c80-\u0cff]+|[a-zA-Z]+|\d", t.lower())
    parts: list[str] = []
    index = 0
    while index < len(tokens):
        tok = tokens[index]
        if tok.isdigit() and len(tok) == 1:
            parts.append(tok)
        elif tok in _KN_WORDS:
            parts.append(_KN_WORDS[tok])
        elif tok.replace(" ", "") in _KN_GROUPS:
            group = _KN_GROUPS[tok.replace(" ", "")]
            if (
                group.endswith("0")
                and index + 1 < len(tokens)
                and tokens[index + 1] in _KN_WORDS
                and _KN_WORDS[tokens[index + 1]] != "0"
            ):
                group = str(int(group) + int(_KN_WORDS[tokens[index + 1]]))
                index += 1
            parts.append(group)
        elif tok in _EN_GROUPS:
            group = _EN_GROUPS[tok]
            if (
                group.endswith("0")
                and index + 1 < len(tokens)
                and tokens[index + 1] in _KN_WORDS
                and _KN_WORDS[tokens[index + 1]] != "0"
            ):
                group = str(int(group) + int(_KN_WORDS[tokens[index + 1]]))
                index += 1
            parts.append(group)
        elif tok.isdigit():
            parts.append(tok)
        index += 1
    joined = "".join(parts)
    return joined or direct
