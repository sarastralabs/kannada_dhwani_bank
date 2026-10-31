"""Fixed Kannada lobby phrases — used for greet handoff and form UX."""

from __future__ import annotations

# Spoken once after time-of-day greeting, before the first listen.
ASK_NEED_KN = "ದಯವಿಟ್ಟು ಹೇಳಿ — ನಿಮಗೆ ಏನು ಸಹಾಯ ಬೇಕು?"

FORM_READY_KN = (
    "ಅರ್ಜಿ ಸಿದ್ಧವಾಗಿದೆ. ಇದನ್ನು ಮುದ್ರಿಸಬಹುದು. ಸೇವೆಯನ್ನು ಮುಗಿಸಲು ಮುಗಿಸು ಎಂದು ಹೇಳಿ "
    "ಅಥವಾ ಮುಂದುವರಿಯಲು ನಿಮ್ಮ ಮುಂದಿನ ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಿ."
)

FORM_CONFIRM_SUFFIX_KN = (
    "ಈ ಮಾಹಿತಿ ಸರಿಯಾಗಿದೆಯೇ? ಸರಿಯಾಗಿದ್ದರೆ ಹೌದು ಎಂದು ಹೇಳಿ; "
    "ತಪ್ಪಿದ್ದರೆ ಮಾಹಿತಿಯನ್ನು ಮತ್ತೆ ಹೇಳಿ."
)

FORM_SUMMARY_OPENER_KN = "ನಿಮ್ಮ ಅರ್ಜಿಯ ಸಾರಾಂಶ ಇಲ್ಲಿದೆ."

FORM_SUMMARY_CLOSER_KN = "ದಯವಿಟ್ಟು ಎಲ್ಲಾ ವಿವರಗಳು ಸರಿಯಾಗಿವೆಯೇ ಎಂದು ಪರಿಶೀಲಿಸಿ."

FORM_WHOLE_CONFIRM_KN = (
    "ಎಲ್ಲ ಮಾಹಿತಿಯೂ ಸರಿಯಾಗಿದೆಯೇ? ಸರಿಯಾಗಿದ್ದರೆ ಹೌದು ಎಂದು ಹೇಳಿ; "
    "ತಪ್ಪಿದ್ದರೆ ಇಲ್ಲ ಎಂದು ಹೇಳಿ."
)

# Pre-warm these on API startup so the first customer hears them instantly.
def _greet_prewarm_lines() -> tuple[str, ...]:
    from backend.greetings import GREET_LINES

    return tuple(lines[0]["line_kn"] for lines in GREET_LINES.values() if lines)


PREWARM_PHRASES: tuple[str, ...] = (
    ASK_NEED_KN,
    FORM_READY_KN,
    FORM_WHOLE_CONFIRM_KN,
    FORM_CONFIRM_SUFFIX_KN,
    FORM_SUMMARY_OPENER_KN,
    FORM_SUMMARY_CLOSER_KN,
    "ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ.",
    "ದಯವಿಟ್ಟು ಹೌದು ಅಥವಾ ಇಲ್ಲ ಎಂದು ಹೇಳಿ.",
    "ನಿಮ್ಮ ಪೂರ್ಣ ಹೆಸರು ಏನು?",
    "ಖಾತೆ ಸಂಖ್ಯೆ ಹೇಳಿ.",
    "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಖಾತೆ ಸಂಖ್ಯೆಯ ಕೊನೆಯ ನಾಲ್ಕು ಅಂಕಿಗಳನ್ನು ಹೇಳಿ",
    "ಎಷ್ಟು ಮೊತ್ತ?",
    # Pre-cache common confirm suffix so digit confirmations are fast
    "ಸರಿಯಾಗಿದ್ದರೆ ಹೌದು ಎಂದು ಹೇಳಿ; ತಪ್ಪಿದ್ದರೆ ಮಾಹಿತಿಯನ್ನು ಮತ್ತೆ ಹೇಳಿ.",
    "ಹೌದು ಅಥವಾ ಇಲ್ಲ?",
    # Balance not found
    "ಖಾತೆ ಕಂಡುಬಂದಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ.",
) + _greet_prewarm_lines()
