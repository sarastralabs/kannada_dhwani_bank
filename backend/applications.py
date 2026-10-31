"""Application workflow: a customer submits a form at the kiosk, staff decide, the customer
comes back and sees the outcome.

    submitted ──approve──▶ approved   (open_account: the account now exists)
        │      ──reject───▶ rejected  (with a message for the customer)
        └──────needs_info─▶ needs_info (customer is asked to visit / resubmit)

Only the account-opening effect is automatic today; other forms are recorded as approved
and fulfilled by staff. Everything here works on demo money.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from typing import Any

from backend.db import store

STATUSES = ("submitted", "approved", "rejected", "needs_info")
OPEN = ("submitted", "needs_info")  # states a decision can still be made from

STATUS_KN = {
    "submitted": "ನಿಮ್ಮ ಅರ್ಜಿ ಪರಿಶೀಲನೆಯಲ್ಲಿದೆ",
    "approved": "ನಿಮ್ಮ ಅರ್ಜಿಯನ್ನು ಅನುಮೋದಿಸಲಾಗಿದೆ",
    "rejected": "ನಿಮ್ಮ ಅರ್ಜಿಯನ್ನು ತಿರಸ್ಕರಿಸಲಾಗಿದೆ",
    "needs_info": "ನಿಮ್ಮ ಅರ್ಜಿಗೆ ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ಬೇಕು, ದಯವಿಟ್ಟು ಶಾಖೆಗೆ ಭೇಟಿ ನೀಡಿ",
}

_ACTION_STATUS = {"approve": "approved", "reject": "rejected", "needs_info": "needs_info"}
_MOBILE_FIELDS = ("mobile_number", "new_mobile", "old_mobile")
_decide_lock = threading.Lock()


class DecisionError(ValueError):
    """The decision cannot be made (already decided, missing message, bad action)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def application_mobile(values: dict[str, str]) -> str:
    """Mobile number on the form, if there is one (digits only)."""
    for key in _MOBILE_FIELDS:
        digits = _digits(values.get(key))
        if len(digits) >= 4:
            return digits
    return ""


def _account_type(text: str) -> str:
    t = (text or "").lower()
    if "ಚಾಲ್ತಿ" in t or "current" in t:
        return "Current"
    return "Savings"


def _open_account(app: dict[str, Any]) -> dict[str, Any]:
    from backend.db import customers

    v = app["values"]
    name = (v.get("full_name") or "").strip()
    if not name:
        raise DecisionError("The application has no name, so an account cannot be opened.")
    mobile = _digits(v.get("mobile_number"))
    existing = customers.find_customer_by_mobile(mobile) if len(mobile) >= 10 else None
    kannada = bool(re.search(r"[ಀ-೿]", name))
    opened = customers.create_customer_with_account(
        name,
        full_name_kn=name if kannada else "",
        mobile=mobile or None,
        account_type=_account_type(v.get("account_type", "")),
        customer_id=existing["customer_id"] if existing else None,
    )
    return {
        "account_number": opened["account_number"],
        "account_type": opened["account_type"],
        "customer_id": opened["customer_id"],
        "existing_customer": bool(existing),
    }


def decide(app_id: str, action: str, *, admin: str, note: str = "") -> dict[str, Any]:
    """Approve, reject or ask for more information. Returns the updated application."""
    if action not in _ACTION_STATUS:
        raise DecisionError(f"Unknown action {action!r}.")
    note = (note or "").strip()
    with _decide_lock:  # one decision at a time, so an account can never be opened twice
        app = store.get_application(app_id)
        if app is None:
            raise LookupError("Application not found")
        if app["status"] not in OPEN:
            raise DecisionError(f"This application is already {app['status']}.")
        if action in ("reject", "needs_info") and not note:
            raise DecisionError("Write a short message for the customer.")
        result: dict[str, Any] = {}
        if action == "approve" and app["form_id"] == "open_account":
            result = _open_account(app)
        decision = {"action": action, "by": admin, "at": _now(), "note": note, "result": result}
        updated = store.decide_application(app["id"], status=_ACTION_STATUS[action], decision=decision)
    if updated is None:
        raise LookupError("Application not found")
    return updated


def normalize_ref(ref: str) -> str:
    """DH-26-000123, dh-26-000123 or just the spoken digits 26000123 -> DH-26-000123."""
    text = (ref or "").strip().upper()
    digits = _digits(text)
    if len(digits) == 8 and not text.startswith("DH"):
        return f"DH-{digits[:2]}-{digits[2:]}"
    return text


def _spoken(digits: str) -> str:
    return " ".join(digits)


def public_status(ref: str, mobile_last4: str = "") -> dict[str, Any] | None:
    """What a customer may see when they come back with their application number.

    If the form carried a mobile number, its last 4 digits must match; a wrong or missing
    answer looks exactly like an unknown number (nothing to guess from).
    """
    app = store.get_application(normalize_ref(ref))
    if app is None or not app.get("ref"):
        return None
    mobile = application_mobile(app["values"])
    if mobile and _digits(mobile_last4)[-4:] != mobile[-4:]:
        return None
    decision = app.get("decision") or {}
    out: dict[str, Any] = {
        "ref": app["ref"],
        "form_id": app["form_id"],
        "title_kn": app["title_kn"],
        "title_en": app["title_en"],
        "status": app["status"],
        "status_kn": STATUS_KN.get(app["status"], ""),
        "submitted_at": app["created_at"],
        "decided_at": decision.get("at"),
        "message": decision.get("note") or "",
    }
    if app["status"] == "approved" and app["form_id"] == "open_account":
        out["account_number"] = (decision.get("result") or {}).get("account_number")
    out["message_kn"] = _message_kn(out)
    return out


def _message_kn(info: dict[str, Any]) -> str:
    """The sentence the kiosk reads to the customer."""
    text = f"{STATUS_KN.get(info['status'], '')}."
    if info.get("account_number"):
        text += f" ನಿಮ್ಮ ಹೊಸ ಖಾತೆ ಸಂಖ್ಯೆ {_spoken(info['account_number'])}."
    if info.get("message"):
        text += f" {info['message']}."
    return text
