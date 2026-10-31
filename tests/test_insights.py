"""System status classification, stats and CSV exports (temp storage only)."""

from __future__ import annotations

import pytest

from api import history as sqlite_history
from api import system_status
from api.routes import insights
from backend.db import store


@pytest.fixture(autouse=True)
def _clean_status():
    system_status.reset()
    yield
    system_status.reset()


@pytest.fixture
def temp_store(tmp_path, monkeypatch):
    audio_dir = tmp_path / "history_audio"
    audio_dir.mkdir()
    monkeypatch.setattr(sqlite_history, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(sqlite_history, "AUDIO_DIR", str(audio_dir))
    monkeypatch.setattr(store, "_get_db", lambda: None)
    monkeypatch.setattr(store, "_submissions_path", lambda: str(tmp_path / "subs.jsonl"))
    sqlite_history.init_db()


def test_model_load_failure_is_a_service_fault():
    msg = "We couldn't connect to 'https://huggingface.co' to load the files"
    assert system_status.classify_error(msg) == "service_unavailable"


def test_plain_failure_is_just_not_understood():
    assert system_status.classify_error("no speech detected") == "not_understood"
    assert system_status.classify_error(None) == "not_understood"


def test_only_service_faults_count_as_failures():
    system_status.record(False, "no speech detected")
    assert system_status.snapshot()["service_failures"] == 0
    system_status.record(False, "model failed to load")
    snap = system_status.snapshot()
    assert snap["service_failures"] == 1
    assert snap["last_error"]["message"] == "model failed to load"
    assert snap["healthy"] is False


def test_recovery_marks_healthy_again():
    system_status.record(False, "worker not ready")
    system_status.record(True)
    assert system_status.snapshot()["healthy"] is True


def test_stats_counts_intents_and_days(temp_store):
    for intent in ("balance", "balance", "loan"):
        store.save_query(
            {"kannada_text": "ಕ", "english_text": "e", "intent": intent, "confidence": 0.9,
             "route": "informational", "response_text": "r", "total_time_s": 2.0}
        )
    out = insights.admin_stats(days=3, _admin={})
    assert out["sample_size"] == 3
    assert out["intents"][0] == {"intent": "balance", "count": 2}
    assert sum(d["count"] for d in out["days"]) == 3
    assert out["avg_response_s"] == 2.0


def test_history_csv_has_bom_and_kannada(temp_store):
    store.save_query(
        {"kannada_text": "ಬ್ಯಾಂಕ್ ಖಾತೆ", "english_text": "bank account", "intent": "account",
         "confidence": 0.8, "route": "transactional", "response_text": "ok", "total_time_s": 1.5}
    )
    res = insights.export_history(_admin={})
    body = res.body.decode("utf-8")
    assert body.startswith("﻿created_at,kannada_text")
    assert "ಬ್ಯಾಂಕ್ ಖಾತೆ" in body
    assert "attachment" in res.headers["content-disposition"]


def test_submissions_csv_serialises_values(temp_store):
    store.save_form_submission(
        form_id="new_account", title_kn="ಖಾತೆ", title_en="New account",
        values={"name": "ರಾಮ"}, kiosk_session_id="s1",
    )
    body = insights.export_submissions(_admin={}).body.decode("utf-8")
    assert "new_account" in body
    assert "ರಾಮ" in body


def test_system_flags_default_admin_password(monkeypatch):
    monkeypatch.delenv("BANK_ADMIN_PASS", raising=False)
    assert insights.admin_system(_admin={})["default_admin_password"] is True
    monkeypatch.setenv("BANK_ADMIN_PASS", "a-strong-one")
    assert insights.admin_system(_admin={})["default_admin_password"] is False
