"""Dialog state passed from the frontend so routing understands the current turn."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DialogContext:
    mode: str = "assist"  # assist | form_select | form
    form_id: str = ""
    field_id: str = ""
    last_intent: str = ""
    last_route: str = ""
    menu_form_ids: list[str] = field(default_factory=list)
    pending_intents: list[str] = field(default_factory=list)
    clarify_attempts: int = 0
    last_kannada_text: str = ""
    last_english_text: str = ""
    kiosk_session_id: str = ""


_VALID_MODES: frozenset[str] = frozenset({"assist", "form_select", "form"})


def parse_dialog_context(raw: dict[str, Any] | None) -> DialogContext:
    if not raw:
        return DialogContext()

    menu = raw.get("menu_form_ids") or raw.get("menuFormIds") or []
    if not isinstance(menu, list):
        menu = []

    pending = raw.get("pending_intents") or raw.get("pendingIntents") or []
    if not isinstance(pending, list):
        pending = []

    try:
        clarify_attempts = int(raw.get("clarify_attempts") or raw.get("clarifyAttempts") or 0)
    except (TypeError, ValueError):
        clarify_attempts = 0

    raw_mode = str(raw.get("mode") or "assist").strip().lower()
    mode = raw_mode if raw_mode in _VALID_MODES else "assist"

    return DialogContext(
        mode=mode,
        form_id=str(raw.get("form_id") or raw.get("formId") or "").strip(),
        field_id=str(raw.get("field_id") or raw.get("fieldId") or "").strip(),
        last_intent=str(raw.get("last_intent") or raw.get("lastIntent") or "").strip(),
        last_route=str(raw.get("last_route") or raw.get("lastRoute") or "").strip(),
        menu_form_ids=[str(x) for x in menu if x],
        pending_intents=[str(x) for x in pending if x],
        clarify_attempts=max(0, clarify_attempts),
        last_kannada_text=str(raw.get("last_kannada_text") or raw.get("lastKannadaText") or "").strip(),
        last_english_text=str(raw.get("last_english_text") or raw.get("lastEnglishText") or "").strip(),
        kiosk_session_id=str(
            raw.get("kiosk_session_id") or raw.get("kioskSessionId") or ""
        ).strip(),
    )
