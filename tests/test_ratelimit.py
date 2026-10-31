"""Rate limits, daily cap and login lockout (mini app, fake clock)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api import ratelimit


@pytest.fixture
def client(monkeypatch):
    ratelimit.reset()
    clock = {"t": 1_800_000_000.0}
    monkeypatch.setattr(ratelimit, "_clock", lambda: clock["t"])
    for name in ("BANK_RATE_LIMIT", "BANK_RATE_PER_MIN", "BANK_DAILY_CAP", "BANK_LOGIN_MAX_FAILS", "BANK_LOGIN_LOCK_S"):
        monkeypatch.delenv(name, raising=False)

    app = FastAPI()
    app.add_middleware(ratelimit.RateLimitMiddleware)

    @app.post("/api/speak-kannada")
    def speak():
        return {"ok": True}

    @app.get("/api/forms/menu")
    def menu():
        return {"ok": True}

    @app.post("/api/admin/login")
    def login(body: dict):
        if body.get("password") != "right":
            raise HTTPException(status_code=401, detail="bad")
        return {"token": "t"}

    c = TestClient(app)
    c.clock = clock
    yield c
    ratelimit.reset()


def test_per_minute_limit_then_recovers(client, monkeypatch):
    monkeypatch.setenv("BANK_RATE_PER_MIN", "3")
    assert [client.post("/api/speak-kannada").status_code for _ in range(3)] == [200, 200, 200]
    blocked = client.post("/api/speak-kannada")
    assert blocked.status_code == 429
    assert blocked.json()["error_code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1
    client.clock["t"] += 61
    assert client.post("/api/speak-kannada").status_code == 200


def test_limits_are_per_ip(client, monkeypatch):
    monkeypatch.setenv("BANK_RATE_PER_MIN", "1")
    assert client.post("/api/speak-kannada", headers={"x-forwarded-for": "1.1.1.1"}).status_code == 200
    assert client.post("/api/speak-kannada", headers={"x-forwarded-for": "1.1.1.1"}).status_code == 429
    assert client.post("/api/speak-kannada", headers={"x-forwarded-for": "2.2.2.2"}).status_code == 200


def test_daily_cap_blocks_everyone_until_tomorrow(client, monkeypatch):
    monkeypatch.setenv("BANK_DAILY_CAP", "2")
    monkeypatch.setenv("BANK_RATE_PER_MIN", "100")
    for ip in ("1.1.1.1", "2.2.2.2"):
        assert client.post("/api/speak-kannada", headers={"x-forwarded-for": ip}).status_code == 200
    capped = client.post("/api/speak-kannada", headers={"x-forwarded-for": "3.3.3.3"})
    assert capped.status_code == 429 and capped.json()["error_code"] == "daily_cap"
    client.clock["t"] += 86_400
    assert client.post("/api/speak-kannada", headers={"x-forwarded-for": "3.3.3.3"}).status_code == 200


def test_reads_and_other_routes_are_never_limited(client, monkeypatch):
    monkeypatch.setenv("BANK_RATE_PER_MIN", "1")
    assert all(client.get("/api/forms/menu").status_code == 200 for _ in range(20))


def test_login_lockout_after_repeated_failures(client, monkeypatch):
    monkeypatch.setenv("BANK_LOGIN_MAX_FAILS", "3")
    for _ in range(3):
        assert client.post("/api/admin/login", json={"password": "wrong"}).status_code == 401
    locked = client.post("/api/admin/login", json={"password": "right"})
    assert locked.status_code == 429 and locked.json()["error_code"] == "login_locked"
    client.clock["t"] += 901
    assert client.post("/api/admin/login", json={"password": "right"}).status_code == 200


def test_successful_login_clears_failures(client, monkeypatch):
    monkeypatch.setenv("BANK_LOGIN_MAX_FAILS", "3")
    for _ in range(2):
        client.post("/api/admin/login", json={"password": "wrong"})
    assert client.post("/api/admin/login", json={"password": "right"}).status_code == 200
    for _ in range(2):
        assert client.post("/api/admin/login", json={"password": "wrong"}).status_code == 401


def test_can_be_switched_off(client, monkeypatch):
    monkeypatch.setenv("BANK_RATE_LIMIT", "0")
    monkeypatch.setenv("BANK_RATE_PER_MIN", "1")
    assert all(client.post("/api/speak-kannada").status_code == 200 for _ in range(5))


def test_snapshot_reports_usage(client, monkeypatch):
    monkeypatch.setenv("BANK_DAILY_CAP", "10")
    client.post("/api/speak-kannada")
    snap = ratelimit.snapshot()
    assert snap["daily_used"] == 1 and snap["daily_cap"] == 10
