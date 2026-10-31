"""Load voice-fill bank form schemas from data/forms.json."""

from __future__ import annotations

import json
import os
from typing import Any

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FORMS_PATH = os.path.join(_PROJECT_ROOT, "data", "forms.json")


def _load() -> dict[str, Any]:
    with open(_FORMS_PATH, encoding="utf-8") as f:
        return json.load(f)


def list_forms() -> dict[str, Any]:
    data = _load()
    forms = [
        {
            "id": form["id"],
            "title_kn": form["title_kn"],
            "title_en": form["title_en"],
            "description_kn": form["description_kn"],
            "description_en": form["description_en"],
            "field_count": sum(1 for f in form["fields"] if not f.get("auto")),
        }
        for form in data["forms"]
    ]
    return {
        "disclaimer_kn": data["disclaimer_kn"],
        "disclaimer_en": data["disclaimer_en"],
        "intent_map": data.get("intent_map") or {},
        "forms": forms,
    }


def get_form(form_id: str) -> dict[str, Any] | None:
    data = _load()
    for form in data["forms"]:
        if form["id"] == form_id:
            return {
                **form,
                "disclaimer_kn": data["disclaimer_kn"],
                "disclaimer_en": data["disclaimer_en"],
            }
    return None


def form_id_for_intent(intent: str) -> str | None:
    """Resolve NLU intent → form id from forms.json intent_map."""
    data = _load()
    mapping = data.get("intent_map") or {}
    return mapping.get(intent)
