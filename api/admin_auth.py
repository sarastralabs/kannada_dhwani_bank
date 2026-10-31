"""Demo admin authentication (token-based, no external IdP).

Default credentials (override with env):
  BANK_ADMIN_USER=admin
  BANK_ADMIN_PASS=bank@123
"""

from __future__ import annotations

import os
import secrets
import time
from threading import Lock
from typing import Any

from fastapi import Header, HTTPException

_lock = Lock()

# token -> {username, expires_at}
_sessions: dict[str, dict[str, Any]] = {}

TOKEN_TTL_S = 12 * 60 * 60  # 12 hours


def _credentials() -> tuple[str, str]:
    user = os.environ.get("BANK_ADMIN_USER", "admin").strip() or "admin"
    password = os.environ.get("BANK_ADMIN_PASS", "bank@123").strip() or "bank@123"
    return user, password


def login(username: str, password: str) -> dict[str, Any]:
    expected_user, expected_pass = _credentials()
    if username != expected_user or password != expected_pass:
        raise PermissionError("Invalid username or password")

    token = secrets.token_urlsafe(32)
    expires = time.time() + TOKEN_TTL_S
    with _lock:
        _sessions[token] = {
            "username": username,
            "expires_at": expires,
        }
    return {
        "token": token,
        "username": username,
        "expires_at": expires,
        "demo_mode": True,
        "role": "admin",
    }


def logout(token: str | None) -> None:
    if not token:
        return
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    with _lock:
        _sessions.pop(token, None)


def verify_token(token: str | None) -> dict[str, Any]:
    if not token:
        raise PermissionError("Admin login required")
    # Allow "Bearer <token>"
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    with _lock:
        session = _sessions.get(token)
        if not session:
            raise PermissionError("Invalid or expired admin session")
        if time.time() > float(session["expires_at"]):
            _sessions.pop(token, None)
            raise PermissionError("Admin session expired — please log in again")
        return {"username": session["username"], "role": "admin"}


def require_admin(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """FastAPI dependency: require Authorization: Bearer <token>."""
    try:
        return verify_token(authorization)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
