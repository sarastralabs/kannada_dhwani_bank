"""Admin "Clear all": conversations (with recordings) and form submissions. Uses temp files only."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api import admin_auth
from api import history as sqlite_history
from api.routes import forms as forms_routes
from api.routes import history as history_routes
from backend.db import store


@pytest.fixture
def temp_history(tmp_path, monkeypatch):
    audio_dir = tmp_path / "history_audio"
    audio_dir.mkdir()
    monkeypatch.setattr(sqlite_history, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(sqlite_history, "AUDIO_DIR", str(audio_dir))
    monkeypatch.setattr(store, "_get_db", lambda: None)
    return audio_dir


@pytest.fixture
def temp_submissions(tmp_path, monkeypatch):
    path = tmp_path / "form_submissions.jsonl"
    monkeypatch.setattr(store, "_submissions_path", lambda: str(path))
    monkeypatch.setattr(store, "_get_db", lambda: None)
    return path


def test_clear_conversations_deletes_rows_and_recordings(temp_history):
    sqlite_history.init_db()
    recording = temp_history / "query_1.wav"
    recording.write_bytes(b"RIFF")
    with sqlite_history._connect() as conn:
        conn.execute(
            "INSERT INTO query_history (created_at, kannada_text, audio_filename) VALUES (?, ?, ?)",
            ("2026-10-12T10:00:00Z", "ಹೌದು", recording.name),
        )
    assert history_routes.clear_all({}) == {"ok": True, "deleted": 1}
    assert not recording.exists()
    assert store.list_queries(limit=10) == []


def test_clear_form_submissions(temp_submissions):
    for name in ("Ashwin", "Suresh"):
        store.save_form_submission("cash_deposit", "ನಗದು", "Cash", {"full_name": name})
    assert len(store.list_form_submissions()) == 2
    assert forms_routes.clear_submissions({}) == {"ok": True, "deleted": 2}
    assert store.list_form_submissions() == []
    assert forms_routes.clear_submissions({}) == {"ok": True, "deleted": 0}


def test_clearing_needs_the_admin_login():
    with pytest.raises(HTTPException) as exc:
        admin_auth.require_admin(authorization=None)
    assert exc.value.status_code == 401
