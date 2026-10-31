"""Time-of-day Kannada lobby greetings — multiple full sentences per slot.

Phrases follow common Karnataka usage (ಶುಭೋದಯ, ಶುಭ ಮಧ್ಯಾಹ್ನ, ಶುಭ ಸಂಜೆ, ನಮಸ್ಕಾರ)
and polite bank-counter tone (ದಯವಿಟ್ಟು, ನಿಮಗೆ, ಸಹಾಯ ಮಾಡಬಹುದು).
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Literal, TypedDict

GreetSlot = Literal["morning", "afternoon", "evening", "night"]


class GreetLine(TypedDict):
    line_kn: str
    line_en: str


class SlotMeta(TypedDict):
    slot: GreetSlot
    title_kn: str
    title_en: str
    hours: str
    alt_titles_kn: list[str]


SLOT_META: dict[GreetSlot, SlotMeta] = {
    "morning": {
        "slot": "morning",
        "title_kn": "ಶುಭೋದಯ",
        "title_en": "Good morning",
        "hours": "05:00–11:59",
        "alt_titles_kn": ["ಸುಪ್ರಭಾತ", "ನಮಸ್ಕಾರ"],
    },
    "afternoon": {
        "slot": "afternoon",
        "title_kn": "ಶುಭ ಮಧ್ಯಾಹ್ನ",
        "title_en": "Good afternoon",
        "hours": "12:00–15:59",
        "alt_titles_kn": ["ನಮಸ್ಕಾರ"],
    },
    "evening": {
        "slot": "evening",
        "title_kn": "ಶುಭ ಸಂಜೆ",
        "title_en": "Good evening",
        "hours": "16:00–19:59",
        "alt_titles_kn": ["ಶುಭ ಸಾಯಂಕಾಲ", "ನಮಸ್ಕಾರ"],
    },
    "night": {
        "slot": "night",
        "title_kn": "ನಮಸ್ಕಾರ",
        "title_en": "Namaskara",
        "hours": "20:00–04:59",
        "alt_titles_kn": ["ಶುಭ ರಾತ್ರಿ"],
    },
}

# Full spoken lines — picked at random per session (not single-word titles only).
GREET_LINES: dict[GreetSlot, list[GreetLine]] = {
    "morning": [
        {
            "line_kn": (
                "ಶುಭೋದಯ. ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್ ಸೇವೆಗೆ ಸುಸ್ವಾಗತ. "
                "ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?"
            ),
            "line_en": (
                "Good morning. Welcome to the Kannada voice banking agent. "
                "How may I help you?"
            ),
        },
        {
            "line_kn": (
                "ಶುಭೋದಯ, ನಮಸ್ಕಾರ. ಬ್ಯಾಂಕ್ ಮಾಹಿತಿ, ಖಾತೆ ಅಥವಾ ಅರ್ಜಿ ತುಂಬಲು "
                "ನಾನು ಕನ್ನಡದಲ್ಲಿ ನಿಮಗೆ ಸಹಾಯ ಮಾಡುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good morning. I can help you in Kannada with bank information, "
                "accounts, or filling forms."
            ),
        },
        {
            "line_kn": (
                "ಸುಪ್ರಭಾತ. ದಯವಿಟ್ಟು ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡಿ — "
                "ನಿಮಗೆ ಬೇಕಾದ ಮಾರ್ಗದರ್ಶನ ನಾನು ನೀಡುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good morning. Please speak in Kannada — I will guide you "
                "with what you need."
            ),
        },
        {
            "line_kn": (
                "ಶುಭೋದಯ. ಠೇವಣಿ, ಹಿಂಪಡೆಯುವಿಕೆ, ಸಾಲ ಅಥವಾ ಹೊಸ ಖಾತೆ — "
                "ಯಾವ ವಿಷಯದಲ್ಲಾದರೂ ಕೇಳಬಹುದು."
            ),
            "line_en": (
                "Good morning. Ask about deposit, withdrawal, loan, or a new account — "
                "any topic is fine."
            ),
        },
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ, ಶುಭೋದಯ. ಈ ಕೌಂಟರ್‌ನಲ್ಲಿ ನೀವು ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡಬಹುದು; "
                "ಇಂಗ್ಲಿಷ್ ಅರ್ಜಿ ನಮೂನೆಯನ್ನು ಭರ್ತಿ ಮಾಡಲು ನಾನು ಸಹಾಯ ಮಾಡುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good morning. You may speak Kannada here; I will help fill "
                "the English forms."
            ),
        },
        {
            "line_kn": (
                "ಶುಭೋದಯ. ನಿಮ್ಮ ಬ್ಯಾಂಕಿಂಗ್ ಪ್ರಶ್ನೆಗಳಿಗೆ ನಾನು ಇಲ್ಲಿ ಸಿದ್ಧ. "
                "ದಯವಿಟ್ಟು ಹೇಳಿ — ಏನು ಸಹಾಯ ಬೇಕು?"
            ),
            "line_en": (
                "Good morning. I am ready for your banking questions. "
                "Please tell me what you need."
            ),
        },
        {
            "line_kn": (
                "ಶುಭೋದಯ. ಬ್ಯಾಂಕ್ ಪ್ರಕ್ರಿಯೆ, ಬಡ್ಡಿ ದರ, ಅಥವಾ ಅರ್ಜಿ — "
                "ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು ಎಂದು ಹೇಳಿ."
            ),
            "line_en": (
                "Good morning. Bank process, interest rates, or an application — "
                "tell me how I can help."
            ),
        },
        {
            "line_kn": (
                "ಶುಭೋದಯ. ಕ್ಯಾಮೆರಾ ಎದುರು ನಿಂತು ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡಿ; "
                "ನಾನು ಕೇಳಿ, ಅರ್ಥ ಮಾಡಿಕೊಂಡು ಉತ್ತರಿಸುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good morning. Stand before the camera and speak in Kannada; "
                "I will listen and respond."
            ),
        },
    ],
    "afternoon": [
        {
            "line_kn": (
                "ಶುಭ ಮಧ್ಯಾಹ್ನ. ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್ ಸೇವೆಗೆ ಸ್ವಾಗತ. "
                "ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?"
            ),
            "line_en": (
                "Good afternoon. Welcome to the Kannada voice banking agent. "
                "How may I help you?"
            ),
        },
        {
            "line_kn": (
                "ಶುಭ ಮಧ್ಯಾಹ್ನ, ನಮಸ್ಕಾರ. ಬ್ಯಾಂಕ್ ಅರ್ಜಿ ಅಥವಾ ಮಾಹಿತಿಗಾಗಿ "
                "ದಯವಿಟ್ಟು ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡಿ."
            ),
            "line_en": (
                "Good afternoon. For bank forms or information, please speak in Kannada."
            ),
        },
        {
            "line_kn": (
                "ಶುಭ ಮಧ್ಯಾಹ್ನ. ನಿಮ್ಮ ದಿನ ಚೆನ್ನಾಗಿ ಸಾಗುತ್ತಿದೆಯೇ? "
                "ನಾನು ಯಾವ ಬ್ಯಾಂಕಿಂಗ್ ವಿಷಯದಲ್ಲಿ ಸಹಾಯ ಮಾಡಬಹುದು?"
            ),
            "line_en": (
                "Good afternoon. How is your day? "
                "Which banking matter may I help with?"
            ),
        },
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ. ಮಧ್ಯಾಹ್ನದ ಸಮಯದಲ್ಲೂ ನಿಮಗೆ ಕನ್ನಡದಲ್ಲಿ "
                "ಬ್ಯಾಂಕಿಂಗ್ ಮಾರ್ಗದರ್ಶನ ಸಿಗುತ್ತದೆ."
            ),
            "line_en": (
                "Good afternoon. You can get banking guidance in Kannada "
                "even at this hour."
            ),
        },
        {
            "line_kn": (
                "ಶುಭ ಮಧ್ಯಾಹ್ನ. ಖಾತೆ, ಚೆಕ್, ಎನ್‌ಇಎಫ್‌ಟಿ ಅಥವಾ ಅರ್ಜಿ ನಮೂನೆ — "
                "ಏನು ಬೇಕಾದರೂ ಕೇಳಿ, ನಾನು ವಿವರಿಸುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good afternoon. Account, cheque, NEFT, or forms — "
                "ask anything and I will explain."
            ),
        },
        {
            "line_kn": (
                "ಶುಭ ಮಧ್ಯಾಹ್ನ. ದಯವಿಟ್ಟು ಹತ್ತಿರ ಬನ್ನಿ — "
                "ನಿಮಗೆ ಬೇಕಾದ ಸೇವೆಗೆ ನಾನು ಮಾರ್ಗ ತೋರಿಸುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good afternoon. Please come closer — "
                "I will guide you to the service you need."
            ),
        },
        {
            "line_kn": (
                "ಶುಭ ಮಧ್ಯಾಹ್ನ. ಅರ್ಜಿ ನಮೂನೆಯನ್ನು ಭರ್ತಿ ಮಾಡಲು ಅಥವಾ ನಿಮ್ಮ ಪ್ರಶ್ನೆಗಳಿಗೆ "
                "ಉತ್ತರಿಸಲು ನಾನು ಕನ್ನಡದಲ್ಲಿ ಸಹಾಯ ಮಾಡುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good afternoon. For form filling or questions, "
                "I am here with you in Kannada."
            ),
        },
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ, ಶುಭ ಮಧ್ಯಾಹ್ನ. ನಿಮ್ಮ ಸಮಸ್ಯೆಯನ್ನು ಕನ್ನಡದಲ್ಲಿ ಹೇಳಿ; "
                "ನಿಮಗೆ ಬೇಕಾದ ಸಹಾಯವನ್ನು ನಾನು ನೀಡುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good afternoon. Describe your issue in Kannada; "
                "I will show how I can help."
            ),
        },
    ],
    "evening": [
        {
            "line_kn": (
                "ಶುಭ ಸಂಜೆ. ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್ ಸೇವೆಗೆ ಸ್ವಾಗತ. "
                "ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?"
            ),
            "line_en": (
                "Good evening. Welcome to the Kannada voice banking agent. "
                "How may I help you?"
            ),
        },
        {
            "line_kn": (
                "ಶುಭ ಸಂಜೆ, ನಮಸ್ಕಾರ. ಸಂಜೆಯ ಸಮಯದಲ್ಲೂ "
                "ನಿಮಗೆ ಸಹಾಯ ಮಾಡಲು ನಾನು ಇಲ್ಲಿದ್ದೇನೆ."
            ),
            "line_en": (
                "Good evening. Even in the evening, I am here to help you."
            ),
        },
        {
            "line_kn": (
                "ಶುಭ ಸಂಜೆ. ಬ್ಯಾಂಕ್ ಸೇವೆ, ಅರ್ಜಿ ತುಂಬುವುದು ಅಥವಾ ಮಾಹಿತಿ — "
                "ನನ್ನೊಂದಿಗೆ ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡಿ."
            ),
            "line_en": (
                "Good evening. Bank services, forms, or information — "
                "speak with me in Kannada."
            ),
        },
        {
            "line_kn": (
                "ಶುಭ ಸಂಜೆ. ದಯವಿಟ್ಟು ಹೇಳಿ — "
                "ನಿಮಗೆ ಯಾವ ಬ್ಯಾಂಕಿಂಗ್ ಸಹಾಯ ಬೇಕು?"
            ),
            "line_en": (
                "Good evening. Please tell me — "
                "what banking help do you need?"
            ),
        },
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ, ಶುಭ ಸಂಜೆ. ನಿಮ್ಮ ಪ್ರಶ್ನೆಗಳಿಗೆ "
                "ನಾನು ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good evening. I will answer your questions in Kannada."
            ),
        },
        {
            "line_kn": (
                "ಶುಭ ಸಾಯಂಕಾಲ. ಅರ್ಜಿ ನಮೂನೆಯನ್ನು ಭರ್ತಿ ಮಾಡಲು ಅಥವಾ ಮಾರ್ಗದರ್ಶನಕ್ಕಾಗಿ "
                "ದಯವಿಟ್ಟು ಮಾತನಾಡಿ."
            ),
            "line_en": (
                "Good evening. For form filling or guidance, please start speaking."
            ),
        },
        {
            "line_kn": (
                "ಶುಭ ಸಂಜೆ. ಖಾತೆ ವಿವರ, ಠೇವಣಿ, ಅಥವಾ ಸಾಲ — "
                "ಯಾವುದಾದರೂ ಕೇಳಬಹುದು, ನಾನು ಮಾರ್ಗ ತೋರಿಸುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good evening. Account details, deposit, or loan — "
                "ask anything; I will guide you."
            ),
        },
        {
            "line_kn": (
                "ಶುಭ ಸಂಜೆ. ಇಲ್ಲಿ ನೀವು ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡಬಹುದು; "
                "ನಾನು ಕೇಳಿ, ಅರ್ಥ ಮಾಡಿಕೊಂಡು ಸಹಾಯ ಮಾಡುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good evening. Speak Kannada here; "
                "I will listen, understand, and help."
            ),
        },
    ],
    "night": [
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ. ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್ ಸೇವೆಗೆ ಸ್ವಾಗತ. "
                "ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?"
            ),
            "line_en": (
                "Namaskara. Welcome to the Kannada voice banking agent. "
                "How may I help you?"
            ),
        },
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ. ರಾತ್ರಿಯ ಸಮಯದಲ್ಲೂ ನಿಮಗೆ ಬ್ಯಾಂಕಿಂಗ್ ಮಾರ್ಗದರ್ಶನ "
                "ಸಿಗುತ್ತದೆ — ದಯವಿಟ್ಟು ಮಾತನಾಡಿ."
            ),
            "line_en": (
                "Namaskara. Banking guidance is available even at night — "
                "please speak."
            ),
        },
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ. ಬ್ಯಾಂಕ್ ಅರ್ಜಿ ನಮೂನೆ ಅಥವಾ ಮಾಹಿತಿಗಾಗಿ "
                "ನಾನು ನಿಮಗೆ ಸಹಾಯ ಮಾಡುತ್ತೇನೆ."
            ),
            "line_en": (
                "Good night. For bank forms or information, I will help you."
            ),
        },
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ. ಖಾತೆ, ಠೇವಣಿ, ಸಾಲ — "
                "ಯಾವ ವಿಷಯದಲ್ಲಾದರೂ ಕನ್ನಡದಲ್ಲಿ ಕೇಳಬಹುದು."
            ),
            "line_en": (
                "Namaskara. Account, deposit, loan — "
                "you may ask about any topic in Kannada."
            ),
        },
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ. ದಯವಿಟ್ಟು ಹತ್ತಿರ ಬನ್ನಿ — "
                "ನಿಮಗೆ ಬೇಕಾದ ಎಲ್ಲ ಮಾಹಿತಿ ನಾನು ನೀಡುತ್ತೇನೆ."
            ),
            "line_en": (
                "Namaskara. Please come closer — "
                "I will give you all the information you need."
            ),
        },
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ. ಇಲ್ಲಿ ನೀವು ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡಬಹುದು; "
                "ಇಂಗ್ಲಿಷ್ ಅರ್ಜಿ ನಮೂನೆಯನ್ನು ಭರ್ತಿ ಮಾಡಲು ನಾನು ಸಹಾಯ ಮಾಡುತ್ತೇನೆ."
            ),
            "line_en": (
                "Namaskara. Speak Kannada here; "
                "I will help fill the English application."
            ),
        },
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ. ಬ್ಯಾಂಕಿಂಗ್ ಪ್ರಕ್ರಿಯೆ ಅಥವಾ ಅರ್ಜಿ ನಮೂನೆಯ ಬಗ್ಗೆ "
                "ಪ್ರಶ್ನೆ ಇದೆಯೇ? ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?"
            ),
            "line_en": (
                "Namaskara. Do you have a question about bank process or forms? "
                "How may I help?"
            ),
        },
        {
            "line_kn": (
                "ನಮಸ್ಕಾರ. ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್ ಸೇವೆಗೆ ಸ್ವಾಗತ — "
                "ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?"
            ),
            "line_en": (
                "Namaskara. Welcome to the Kannada voice banking service — "
                "how may I help you?"
            ),
        },
    ],
}


def slot_for_hour(hour: int) -> GreetSlot:
    """Map local hour (0–23) to greeting slot."""
    if 5 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 15:
        return "afternoon"
    if 16 <= hour <= 19:
        return "evening"
    return "night"


def pick_greeting(
    hour: int | None = None,
    *,
    slot: GreetSlot | None = None,
    variant: int | None = None,
    rng: random.Random | None = None,
) -> dict:
    """
    Return one greeting with metadata + line_kn/line_en.
    variant: 0-based index; None = random from slot pool.
    """
    if hour is None:
        hour = datetime.now().hour
    if slot is None:
        slot = slot_for_hour(hour)

    meta = SLOT_META[slot]
    lines = GREET_LINES[slot]
    if variant is None:
        r = rng if rng is not None else random
        variant = r.randrange(len(lines))
    else:
        variant = max(0, min(variant, len(lines) - 1))

    line = lines[variant]
    return {
        "slot": slot,
        "title_kn": meta["title_kn"],
        "title_en": meta["title_en"],
        "hours": meta["hours"],
        "alt_titles_kn": meta["alt_titles_kn"],
        "variant": variant,
        "variant_count": len(lines),
        "line_kn": line["line_kn"],
        "line_en": line["line_en"],
    }


def greeting_for_hour(hour: int | None = None) -> dict:
    """Backward-compatible: random line for the hour's slot."""
    return pick_greeting(hour=hour)


def all_greetings() -> list[dict]:
    """Catalog for API — each slot with all line variants."""
    out: list[dict] = []
    for slot, meta in SLOT_META.items():
        out.append(
            {
                **meta,
                "lines": GREET_LINES[slot],
                "variant_count": len(GREET_LINES[slot]),
            }
        )
    return out


def line_for_slot_variant(slot: GreetSlot, variant: int) -> GreetLine:
    lines = GREET_LINES[slot]
    variant = max(0, min(variant, len(lines) - 1))
    return lines[variant]
