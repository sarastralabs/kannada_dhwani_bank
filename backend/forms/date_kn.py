"""Deterministic date extraction from Kannada STT output."""

from __future__ import annotations

from datetime import datetime
import re

from backend.forms.kannada_digits import extract_digits_from_kannada
from backend.forms.summary_kn import _int_kn

_KN_DIGITS = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")


def _valid_date(day: int, month: int, year: int) -> str:
    try:
        parsed = datetime(year, month, day)
    except ValueError:
        return ""
    return parsed.strftime("%d/%m/%Y")


def _number_matches(text: str) -> list[tuple[int, int, int]]:
    """Return non-overlapping Kannada number-word matches, longest first."""
    candidates = [
        (_int_kn(number), number)
        for number in [*range(1900, 2100), *range(0, 32)]
    ]
    occupied: list[tuple[int, int]] = []
    matches: list[tuple[int, int, int]] = []

    for phrase, number in sorted(candidates, key=lambda item: len(item[0]), reverse=True):
        pattern = rf"(?<!\S){re.escape(phrase)}(?!\S)"
        for found in re.finditer(pattern, text):
            span = found.span()
            if any(span[0] < end and start < span[1] for start, end in occupied):
                continue
            occupied.append(span)
            matches.append((span[0], span[1], number))

    return sorted(matches)


def extract_date_from_kannada(text: str) -> str:
    """Extract a valid ``DD/MM/YYYY`` date before translation can alter numbers."""
    if not text or not text.strip():
        return ""

    normalized = text.translate(_KN_DIGITS)

    # Handles "21 06 2005", "21/06/2005", and correction sentences containing it.
    numeric = re.search(
        r"(?<!\d)(\d{1,2})\s*[/.\-\s]\s*(\d{1,2})\s*[/.\-\s]\s*(\d{4})(?!\d)",
        normalized,
    )
    if numeric:
        parsed = _valid_date(*(int(group) for group in numeric.groups()))
        if parsed:
            return parsed

    # Handles digit-by-digit Kannada/English speech.
    digits = extract_digits_from_kannada(normalized)
    if len(digits) == 8:
        parsed = _valid_date(int(digits[:2]), int(digits[2:4]), int(digits[4:]))
        if parsed:
            return parsed

    # Handles grouped Kannada speech such as
    # "ಇಪ್ಪತ್ತೊಂದು ಆರು ಎರಡು ಸಾವಿರ ಐದು".
    cleaned = re.sub(r"[^\u0c80-\u0cff\s]", " ", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    values = [number for _start, _end, number in _number_matches(cleaned)]
    for index in range(len(values) - 2):
        day, month, year = values[index : index + 3]
        if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2099:
            parsed = _valid_date(day, month, year)
            if parsed:
                return parsed

    return ""
