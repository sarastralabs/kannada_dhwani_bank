"""Canonical privacy-safe Kannada phrases eligible for persistent TTS caching."""

from __future__ import annotations

import json
import os
import re
import unicodedata

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_FORMS_PATH = os.path.join(_ROOT, "data", "forms.json")

_CONVERSATION_PHRASES = (
    "ನಮಸ್ಕಾರ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
    "ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ.",
    "ದಯವಿಟ್ಟು ಅರ್ಜಿಯ ಸಂಖ್ಯೆ ಅಥವಾ ಹೆಸರನ್ನು ಮತ್ತೆ ಹೇಳಿ.",
    "ದಯವಿಟ್ಟು ಹೌದು ಅಥವಾ ಇಲ್ಲ ಎಂದು ಹೇಳಿ.",
    "ನಿಮ್ಮ ಉತ್ತರ ಕೇಳಿಸಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಸ್ಪಷ್ಟವಾಗಿ ಹೇಳಿ.",
    "ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಜೋರಾಗಿ ಮತ್ತು ಸ್ಪಷ್ಟವಾಗಿ ಹೇಳಿ.",
    "ಖಾತೆಯ ಶಿಲ್ಕು ಪರಿಶೀಲನೆಯನ್ನು ಪ್ರಾರಂಭಿಸುತ್ತೇನೆ.",
)


def _form_prompts() -> list[str]:
    try:
        with open(_FORMS_PATH, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return []

    forms = payload.get("forms") if isinstance(payload, dict) else payload
    if not isinstance(forms, list):
        return []
    phrases: list[str] = []
    menu_titles: list[str] = []
    for form in forms:
        if not isinstance(form, dict):
            continue
        title = str(form.get("title_kn") or "").strip()
        if title:
            phrases.append(
                f"ಈಗ {title} ಪ್ರಾರಂಭವಾಗುತ್ತದೆ. ಪ್ರತಿ ಪ್ರಶ್ನೆಗೆ ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ."
            )
            if form.get("id") != "balance_inquiry":
                menu_titles.append(title)
        for field in form.get("fields") or []:
            if not isinstance(field, dict) or field.get("auto"):
                continue
            prompt = str(field.get("prompt_kn") or "").strip()
            if prompt:
                phrases.append(prompt)
    if menu_titles:
        phrases.append(
            " ".join(
                [
                    "ಈ ಬ್ಯಾಂಕ್ ಅರ್ಜಿ ನಮೂನೆಗಳನ್ನು ಕನ್ನಡದಲ್ಲಿ ಭರ್ತಿ ಮಾಡಲು ನಾನು ಸಹಾಯ ಮಾಡುತ್ತೇನೆ.",
                    "ದಯವಿಟ್ಟು ನಿಮಗೆ ಬೇಕಾದ ಅರ್ಜಿಯ ಸಂಖ್ಯೆ ಅಥವಾ ಹೆಸರನ್ನು ಹೇಳಿ.",
                    *(
                        f"{index}. {title}"
                        for index, title in enumerate(menu_titles, start=1)
                    ),
                ]
            )
        )
    return phrases


def static_kannada_phrases() -> tuple[str, ...]:
    """Collect fixed phrases only; never include captured customer data."""
    from backend.greetings import GREET_LINES
    from backend import lobby_phrases
    from backend.forms.validation import STATIC_VALIDATION_PHRASES

    phrases: list[str] = []
    phrases.extend(
        str(line.get("line_kn") or "").strip()
        for lines in GREET_LINES.values()
        for line in lines
        if isinstance(line, dict)
    )
    phrases.extend(
        value.strip()
        for name, value in vars(lobby_phrases).items()
        if name.endswith("_KN") and isinstance(value, str)
    )
    phrases.extend(_form_prompts())
    phrases.extend(STATIC_VALIDATION_PHRASES)
    phrases.extend(_CONVERSATION_PHRASES)
    normalized = (
        re.sub(r"\s+", " ", unicodedata.normalize("NFC", phrase)).strip()
        for phrase in phrases
        if phrase
    )
    return tuple(dict.fromkeys(phrase for phrase in normalized if phrase))
