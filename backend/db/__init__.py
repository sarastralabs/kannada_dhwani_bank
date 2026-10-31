"""Optional MongoDB persistence — falls back to SQLite for query history."""

from backend.db.store import (
    list_form_submissions,
    mongo_enabled,
    save_form_submission,
    save_kiosk_session,
    save_query,
)

__all__ = [
    "mongo_enabled",
    "save_query",
    "save_form_submission",
    "save_kiosk_session",
    "list_form_submissions",
]
