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


# ── Cloud-only mode (Render): env defaults and torch-free fallbacks ─────────

def test_cloud_provider_defaults_come_from_env(monkeypatch):
    from backend import cloud

    monkeypatch.setenv("BANK_CLOUD_PROVIDER", "sarvam")
    monkeypatch.setenv("BANK_CLOUD_FALLBACK_LOCAL", "0")
    cfg = cloud.get_config()
    assert (cfg["stt"], cfg["translation"], cfg["tts"]) == ("sarvam",) * 3
    assert cfg["fallback_local"] is False


def test_per_stage_env_overrides_global(monkeypatch):
    from backend import cloud

    monkeypatch.setenv("BANK_CLOUD_PROVIDER", "sarvam")
    monkeypatch.setenv("BANK_TTS_PROVIDER", "local")
    assert cloud.get_config()["tts"] == "local"


def test_default_config_stays_local(monkeypatch):
    from backend import cloud

    for name in ("BANK_CLOUD_PROVIDER", "BANK_STT_PROVIDER", "BANK_TRANSLATION_PROVIDER", "BANK_TTS_PROVIDER", "BANK_CLOUD_FALLBACK_LOCAL"):
        monkeypatch.delenv(name, raising=False)
    cfg = cloud.get_config()
    assert cfg["stt"] == "local" and cfg["fallback_local"] is True


def test_nlu_uses_keyword_classifier_when_model_missing(monkeypatch, tmp_path):
    from backend import nlu

    monkeypatch.setattr(nlu, "MODEL_DIR", str(tmp_path / "nope"))
    monkeypatch.setattr(nlu, "_classifier_cache", {})
    intent, conf = nlu.classify("what is my account balance", model="finetuned")
    assert intent and conf > 0
    assert type(nlu._classifier_cache["finetuned"]).__name__ == "KeywordClassifier"


def test_nlu_engine_env_forces_keyword(monkeypatch):
    from backend import nlu

    monkeypatch.setenv("BANK_NLU_ENGINE", "keyword")
    monkeypatch.setattr(nlu, "_classifier_cache", {})
    nlu.warm_model("finetuned")
    assert type(nlu._classifier_cache["finetuned"]).__name__ == "KeywordClassifier"


def test_missing_cloud_key_is_a_service_fault():
    msg = "STT failed: Sarvam is selected for speech-to-text but no API key is set"
    assert system_status.classify_error(msg) == "service_unavailable"


def test_bad_audio_is_not_a_service_fault():
    assert system_status.classify_error("STT failed: audio too short") == "not_understood"


def test_one_rejected_input_does_not_block_the_cloud_stage(monkeypatch):
    from backend import cloud
    from backend.cloud.sarvam import CloudError

    monkeypatch.setenv("SARVAM_API_KEY", "test-key-123456")
    monkeypatch.setenv("BANK_CLOUD_PROVIDER", "sarvam")
    cloud.record_error("tts", CloudError("bad_request", "Text must contain a letter"))
    assert cloud.blocked_reason("tts") is None
    assert cloud.use_cloud("tts") is True


def test_real_outage_still_backs_off(monkeypatch):
    from backend import cloud
    from backend.cloud.sarvam import CloudError

    monkeypatch.setenv("SARVAM_API_KEY", "test-key-123456")
    monkeypatch.setenv("BANK_CLOUD_PROVIDER", "sarvam")
    cloud.record_error("tts", CloudError("server", "Sarvam service error 503"))
    assert cloud.blocked_reason("tts") is not None


def test_autostart_opens_lobby_only_when_enabled(monkeypatch):
    from api import kiosk_state, main

    monkeypatch.setattr(kiosk_state, "_persist_session", lambda event: None)
    monkeypatch.delenv("BANK_KIOSK_AUTOSTART", raising=False)
    kiosk_state.stop_kiosk()
    assert main.autostart_kiosk() is False
    assert kiosk_state.get_status_lite()["running"] is False

    monkeypatch.setenv("BANK_KIOSK_AUTOSTART", "1")
    assert main.autostart_kiosk() is True
    assert kiosk_state.get_status_lite()["running"] is True
    kiosk_state.stop_kiosk()
