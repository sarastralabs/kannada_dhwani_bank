"""Eager Parler load + phrase cache — first customer speak should be instant."""

from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def warm_parler_service(*, extra_phrases: tuple[str, ...] = ()) -> dict[str, Any]:
    """
    Load the Parler worker (FP16 model into GPU) and pre-synthesise lobby phrases.
    Safe to call multiple times; only the first call pays model-load cost.
    """
    from backend.lobby_phrases import PREWARM_PHRASES
    from backend.tts.parler_bridge import default_speaker, ensure_parler_ready, parler_ready
    from backend.tts.speak_cache import prewarm_phrases

    t0 = time.perf_counter()
    if not ensure_parler_ready():
        return {"ok": False, "error": "Parler not available on this machine"}

    phrases = tuple(PREWARM_PHRASES) + tuple(extra_phrases)
    speaker = default_speaker()
    n = prewarm_phrases(phrases, speaker=speaker)
    elapsed = round(time.perf_counter() - t0, 1)
    return {
        "ok": True,
        "ready": parler_ready(),
        "speaker": speaker,
        "phrases_cached": n,
        "elapsed_s": elapsed,
    }


def wait_for_remote_tts_ready(
    url: str | None = None,
    *,
    timeout_s: float = 180.0,
    poll_s: float = 2.0,
) -> bool:
    """Poll remote TTS /api/health until ready=true (model loaded + warmed)."""
    base = (url or os.environ.get("BANK_TTS_REMOTE_URL", "")).strip().rstrip("/")
    if not base:
        return False
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        try:
            from backend.tts.remote_bridge import _http_headers

            req = urllib.request.Request(
                f"{base}/api/health",
                headers=_http_headers(),
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                import json

                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("ready") is True or payload.get("status") == "ready":
                return True
            if payload.get("status") == "ok" and payload.get("ready") is None:
                # Older server — treat parler flag as enough
                if payload.get("parler"):
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(poll_s)
    return False


def warm_via_remote_phrases(*, extra_phrases: tuple[str, ...] = ()) -> dict[str, Any]:
    """After remote TTS is ready, cache common phrases on the kiosk API."""
    from backend.lobby_phrases import PREWARM_PHRASES
    from backend.tts.parler_bridge import default_speaker
    from backend.tts.remote_bridge import remote_tts_configured
    from backend.tts.speak_cache import prewarm_phrases

    if not remote_tts_configured():
        return {"ok": False, "error": "remote TTS not configured"}

    url = os.environ.get("BANK_TTS_REMOTE_URL", "").strip()
    t0 = time.perf_counter()
    if not wait_for_remote_tts_ready(url):
        return {"ok": False, "error": f"remote TTS not ready at {url}"}

    phrases = tuple(PREWARM_PHRASES) + tuple(extra_phrases)
    try:
        n = prewarm_phrases(phrases, speaker=default_speaker())
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    elapsed = round(time.perf_counter() - t0, 1)
    print(
        f"[warmup] remote TTS ready; cached {n} phrase(s) in {elapsed}s ({url})",
        file=sys.stderr,
    )
    return {"ok": True, "phrases_cached": n, "elapsed_s": elapsed, "remote": url}
