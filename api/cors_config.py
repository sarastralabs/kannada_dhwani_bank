"""CORS settings — LAN, ngrok, Cloudflare tunnel, and custom origins."""

from __future__ import annotations

import os


def _extra_origins() -> list[str]:
    raw = os.environ.get("BANK_CORS_ORIGINS", "").strip()
    if not raw:
        return []
    return [o.strip() for o in raw.split(",") if o.strip()]


def cors_middleware_kwargs() -> dict:
    """Kwargs for FastAPI CORSMiddleware."""
    base = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://localhost:5173",
        "https://127.0.0.1:5173",
        "https://localhost:5174",
        "https://127.0.0.1:5174",
    ]
    return {
        "allow_origins": base + _extra_origins(),
        # LAN IPs + ngrok + Cloudflare quick-tunnel hostnames
        "allow_origin_regex": (
            r"https?://("
            r"localhost|127\.0\.0\.1|"
            r"192\.168\.\d{1,3}\.\d{1,3}|"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
            r"[a-z0-9-]+\.ngrok-free\.app|"
            r"[a-z0-9-]+\.ngrok\.io|"
            r"[a-z0-9-]+\.trycloudflare\.com|"
            r"[a-z0-9-]+\.sarastralabs\.com"
            r")(:\d+)?"
        ),
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
