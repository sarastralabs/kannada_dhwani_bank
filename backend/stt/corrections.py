"""
Post-processing corrections for common Whisper mistakes on Kannada banking speech.

Whisper sometimes substitutes visually similar Kannada characters or mishears
common banking words. These corrections are applied after transcription to
fix the most frequent errors observed in testing.
"""
from __future__ import annotations

import re

# Direct word substitutions — order matters (longer matches first)
_WORD_CORRECTIONS: list[tuple[str, str]] = [
    # "ಎಷ್ಟಿದೆ" (how much is) often transcribed as "ಎಸೆದಿದೆ" (thrown)
    ("ಎಸೆದಿದೆ", "ಎಷ್ಟಿದೆ"),
    ("ಎಸೆದು", "ಎಷ್ಟು"),
    ("ಎಸೆ", "ಎಷ್ಟು"),
    # "ಬಾಕಿ" (balance/remaining) sometimes heard as "ಬಾಖಿ"
    ("ಬಾಖಿ", "ಬಾಕಿ"),
    # "ಹಿಂಪಡೆ" (withdraw) variations
    ("ಹಿಂಪಡೆಯ", "ಹಿಂಪಡೆ"),
    ("ಹಿಂಪಡೇ", "ಹಿಂಪಡೆ"),
    # "ಮರುಪಾವತಿ" (repayment) variations
    ("ಮರುಪಾವತಿಯ", "ಮರುಪಾವತಿ"),
    ("ಮರು ಪಾವತಿ", "ಮರುಪಾವತಿ"),
    # "ಪಿನ್" (PIN) variations
    ("ಪಿನ್ನ", "ಪಿನ್"),
    ("ಪಿನ", "ಪಿನ್"),
    # "ಖಾತೆ" (account) variations
    ("ಖಾತೇ", "ಖಾತೆ"),
    ("ಕಾತೆ", "ಖಾತೆ"),
    # "ಅರ್ಜಿ" (application/form) variations
    ("ಅರ್ಝಿ", "ಅರ್ಜಿ"),
    ("ಅರ್ಜ", "ಅರ್ಜಿ"),
    # "ಸಾಲ" (loan) — make sure STT doesn't lose it
    ("ಸಾಳ", "ಸಾಲ"),
    # "ಬ್ಲಾಕ್" (block) variations
    ("ಬ್ಲಾಕ", "ಬ್ಲಾಕ್"),
    ("ಬ್ಲಾಕ್ ಮಾಡಿ", "ಬ್ಲಾಕ್ ಮಾಡಿ"),  # keep as-is
    # "ಠೇವಣಿ" (deposit) variations
    ("ಠೇವಣ", "ಠೇವಣಿ"),
    ("ಥೇವಣಿ", "ಠೇವಣಿ"),
    # "ಬಡ್ಡಿ" (interest) variations
    ("ಬಡ್ಡ", "ಬಡ್ಡಿ"),
    ("ಬಡ್ಡಿಯ", "ಬಡ್ಡಿ"),
    # Romanized fallbacks when Whisper outputs Latin instead of Kannada
    ("sala arji", "ಸಾಲ ಅರ್ಜಿ"),
    ("khate", "ಖಾತೆ"),
    ("baddi dara", "ಬಡ್ಡಿ ದರ"),
    ("hinpade", "ಹಿಂಪಡೆ"),
    ("thevani", "ಠೇವಣಿ"),
]


def apply_corrections(text: str) -> str:
    """Apply post-processing corrections to STT output."""
    if not text or not text.strip():
        return text

    result = text
    for wrong, correct in _WORD_CORRECTIONS:
        # Case-insensitive replacement for Romanized words
        if all(c.isascii() for c in wrong):
            result = re.sub(re.escape(wrong), correct, result, flags=re.IGNORECASE)
        else:
            result = result.replace(wrong, correct)

    return result.strip()
