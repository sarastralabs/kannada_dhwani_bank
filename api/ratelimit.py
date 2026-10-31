"""Abuse protection for the public API: per-IP rate limits, a daily cap, login lockout.

The kiosk endpoints need no login, and every speech call spends Sarvam credits, so
anyone who finds the URL could drain them. Limits are in-memory (one process), which
matches the single Render instance; configure with environment variables:

    BANK_RATE_LIMIT      0 turns everything off (default on)
    BANK_RATE_PER_MIN    speech calls per IP per minute (default 60; one kiosk ≈ 2 per turn)
    BANK_DAILY_CAP       speech calls per day across all IPs (default 0 = unlimited)
    BANK_LOOKUP_PER_MIN  application-status checks per IP per minute (default 20)
    BANK_LOGIN_MAX_FAILS failed staff logins per IP before lockout (default 5)
    BANK_LOGIN_LOCK_S    lockout length in seconds (default 900)
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# POST routes that call Sarvam (speech in, speech out).
SPEECH_PATHS = frozenset(
    {"/api/process-audio", "/api/speak-kannada", "/api/forms/transcribe", "/api/forms/fill-field"}
)
LOGIN_PATH = "/api/admin/login"
# Public lookups that take a number from the customer: limited so numbers cannot be guessed.
LOOKUP_PATHS = frozenset({"/api/applications/status", "/api/customer/summary"})

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)
_login_fails: dict[str, deque[float]] = defaultdict(deque)
_daily = {"day": "", "count": 0}
_blocked_recent: deque[float] = deque(maxlen=500)
_clock = time.time  # tests replace this


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def enabled() -> bool:
    return os.environ.get("BANK_RATE_LIMIT", "1").strip().lower() not in {"0", "false", "off", "no"}


def client_ip(request: Request) -> str:
    """Real client address behind Render/Cloudflare (first X-Forwarded-For hop)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _prune(bucket: deque[float], window_s: float, now: float) -> None:
    while bucket and now - bucket[0] > window_s:
        bucket.popleft()


def _today(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")


def check_speech(ip: str) -> tuple[bool, str, int]:
    """Count one speech call. Returns (allowed, reason, retry_after_s)."""
    now = _clock()
    per_min = _int_env("BANK_RATE_PER_MIN", 60)
    cap = _int_env("BANK_DAILY_CAP", 0)
    with _lock:
        if _daily["day"] != _today(now):
            _daily["day"], _daily["count"] = _today(now), 0
        if cap > 0 and _daily["count"] >= cap:
            _blocked_recent.append(now)
            return False, "daily_cap", 3600
        bucket = _hits[ip]
        _prune(bucket, 60, now)
        if per_min > 0 and len(bucket) >= per_min:
            _blocked_recent.append(now)
            return False, "rate_limited", max(1, int(60 - (now - bucket[0])))
        bucket.append(now)
        _daily["count"] += 1
        if len(_hits) > 5000:  # forget idle addresses
            for key in [k for k, v in _hits.items() if not v or now - v[-1] > 120]:
                _hits.pop(key, None)
    return True, "", 0


def check_lookup(ip: str) -> tuple[bool, int]:
    """Count one status lookup. Returns (allowed, retry_after_s)."""
    now = _clock()
    per_min = _int_env("BANK_LOOKUP_PER_MIN", 20)
    with _lock:
        bucket = _hits[f"lookup:{ip}"]
        _prune(bucket, 60, now)
        if per_min > 0 and len(bucket) >= per_min:
            _blocked_recent.append(now)
            return False, max(1, int(60 - (now - bucket[0])))
        bucket.append(now)
    return True, 0


def login_locked(ip: str) -> int:
    """Seconds left on a lockout for this IP (0 = not locked)."""
    now = _clock()
    max_fails = _int_env("BANK_LOGIN_MAX_FAILS", 5)
    lock_s = _int_env("BANK_LOGIN_LOCK_S", 900)
    with _lock:
        bucket = _login_fails[ip]
        _prune(bucket, lock_s, now)
        if max_fails > 0 and len(bucket) >= max_fails:
            return max(1, int(lock_s - (now - bucket[0])))
    return 0


def record_login(ip: str, ok: bool) -> None:
    with _lock:
        if ok:
            _login_fails.pop(ip, None)
        else:
            _login_fails[ip].append(_clock())


def snapshot() -> dict:
    now = _clock()
    with _lock:
        used = _daily["count"] if _daily["day"] == _today(now) else 0
        recent = sum(1 for t in _blocked_recent if now - t <= 900)
    return {
        "enabled": enabled(),
        "daily_used": used,
        "daily_cap": _int_env("BANK_DAILY_CAP", 0),
        "per_min": _int_env("BANK_RATE_PER_MIN", 60),
        "blocked_recent": recent,
    }


def reset() -> None:
    with _lock:
        _hits.clear()
        _login_fails.clear()
        _blocked_recent.clear()
        _daily["day"], _daily["count"] = "", 0


def _too_many(reason: str, retry_after: int) -> JSONResponse:
    message = {
        "daily_cap": "Daily voice limit reached. Please try again tomorrow.",
        "rate_limited": "Too many requests. Please wait a moment.",
        "login_locked": "Too many failed sign-in attempts. Try again later.",
    }[reason]
    return JSONResponse(
        status_code=429,
        content={"detail": message, "error_code": reason},
        headers={"Retry-After": str(retry_after)},
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not enabled():
            return await call_next(request)
        path = request.url.path
        ip = client_ip(request)

        if path in LOOKUP_PATHS:
            allowed, retry = check_lookup(ip)
            return await call_next(request) if allowed else _too_many("rate_limited", retry)

        if request.method != "POST":
            return await call_next(request)

        if path in SPEECH_PATHS:
            allowed, reason, retry = check_speech(ip)
            if not allowed:
                return _too_many(reason, retry)
            return await call_next(request)

        if path == LOGIN_PATH:
            locked = login_locked(ip)
            if locked:
                return _too_many("login_locked", locked)
            response = await call_next(request)
            if response.status_code == 401:
                record_login(ip, False)
            elif response.status_code == 200:
                record_login(ip, True)
            return response

        return await call_next(request)
