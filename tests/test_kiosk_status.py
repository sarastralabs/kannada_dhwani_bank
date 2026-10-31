"""Kiosk status API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_kiosk_status_lite_omits_sessions():
    r = client.get("/api/kiosk/status/lite")
    assert r.status_code == 200
    data = r.json()
    assert "running" in data
    assert "phase" in data
    assert "sessions" not in data


def test_kiosk_status_includes_sessions():
    r = client.get("/api/kiosk/status")
    assert r.status_code == 200
    data = r.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


def test_health_live_is_fast():
    r = client.get("/api/health/live")
    assert r.status_code == 200
    assert r.json().get("live") is True
