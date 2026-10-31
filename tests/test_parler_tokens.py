"""Parler TTS token budget helpers."""

from __future__ import annotations

from parler_model_utils import max_new_tokens_for_text


def test_short_phrase_uses_fewer_tokens_than_cap():
    short = max_new_tokens_for_text("ಸರಿ")
    long = max_new_tokens_for_text("ಒ" * 120)
    assert short < long
    assert short >= 280
    assert long <= 1500


def test_empty_text_uses_floor():
    assert max_new_tokens_for_text("") >= 280


def test_legacy_quality_profile_remains_available(monkeypatch):
    monkeypatch.setenv("BANK_PARLER_MAX_NEW_TOKENS", "1800")
    monkeypatch.setenv("BANK_PARLER_MIN_NEW_TOKENS", "320")
    monkeypatch.setenv("BANK_PARLER_TOKENS_PER_CHAR", "45")

    assert max_new_tokens_for_text("") == 320
    assert max_new_tokens_for_text("ಒ" * 120) == 1800
