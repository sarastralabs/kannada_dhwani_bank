"""Shared test setup."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_runtime_settings(tmp_path, monkeypatch):
    """
    Never read or write the kiosk's real data/runtime_settings.json or
    data/cloud_status.json. Those hold the staff's live choices (e.g. Speaking →
    Sarvam) and the Sarvam key; without this, tests would follow them — taking
    the wrong code path and spending real cloud credits.
    """
    monkeypatch.setenv("BANK_RUNTIME_SETTINGS_FILE", str(tmp_path / "runtime_settings.json"))
    monkeypatch.setenv("BANK_CLOUD_STATUS_FILE", str(tmp_path / "cloud_status.json"))
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
