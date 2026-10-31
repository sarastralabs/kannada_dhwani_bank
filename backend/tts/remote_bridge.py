"""
HTTP client for remote Indic Parler-TTS (second GPU machine).

Set on the kiosk / main API machine:
  BANK_TTS_REMOTE_URL=https://tts.yourdomain.com
  BANK_TTS_REMOTE_KEY=shared-secret   (optional)

Run the TTS box with:  .\\scripts\\run_tts_server.ps1
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any

import numpy as np
import soundfile as sf

_session_lock = threading.Lock()
_opener: urllib.request.OpenerDirector | None = None


def remote_tts_url() -> str:
    return os.environ.get("BANK_TTS_REMOTE_URL", "").strip().rstrip("/")


def remote_tts_configured() -> bool:
    return bool(remote_tts_url())


def _timeout_s() -> float | None:
    """
    Remote speak timeout in seconds.
    Use ``none``/``inf`` only for an intentional unlimited development wait.
    Zero and invalid values fall back to the production-safe 90 second limit.
    """
    raw = os.environ.get("BANK_TTS_REMOTE_TIMEOUT", "90").strip().lower()
    if raw in {"none", "inf", "infinite", "wait"}:
        return None
    try:
        val = float(raw)
    except ValueError:
        return 90.0
    if val <= 0:
        return 90.0
    return val


def _opener_get() -> urllib.request.OpenerDirector:
    global _opener
    with _session_lock:
        if _opener is None:
            _opener = urllib.request.build_opener()
        return _opener


def _http_headers(*, json_body: bool = False) -> dict[str, str]:
    """Headers for remote TTS — Cloudflare blocks default Python-urllib User-Agent (error 1010)."""
    ua = os.environ.get(
        "BANK_TTS_REMOTE_USER_AGENT",
        "SarastraBankAssistant/1.0 (+https://sarastralabs.com)",
    ).strip()
    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": ua or "SarastraBankAssistant/1.0",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    key = os.environ.get("BANK_TTS_REMOTE_KEY", "").strip()
    if key:
        headers["X-Bank-Tts-Key"] = key
    return headers


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{remote_tts_url()}{path}"
    data = None
    headers = _http_headers(json_body=body is not None)
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    retries = max(1, int(os.environ.get("BANK_TTS_REMOTE_RETRIES", "2")))
    # The TTS box serves one request at a time and answers 429 when another is
    # running (503 while warming). The kiosk prefetches the next prompt while one
    # plays, so overlaps are normal — wait and retry instead of failing at once.
    busy_wait_s = max(0.0, float(os.environ.get("BANK_TTS_BUSY_WAIT_S", "45")))
    busy_deadline = time.monotonic() + busy_wait_s
    busy_delay = 1.0
    attempt = 0
    while True:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        started = time.perf_counter()
        try:
            if attempt == 0:
                print(f"[remote-tts] {method} {url}", file=sys.stderr, flush=True)
            with _opener_get().open(req, timeout=_timeout_s()) as resp:
                raw = resp.read().decode("utf-8")
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            print(
                f"[remote-tts] response attempt={attempt + 1} request_ms={elapsed_ms}",
                file=sys.stderr,
                flush=True,
            )
            try:
                payload = json.loads(raw)
                timing = payload.get("timing") if isinstance(payload, dict) else None
                if isinstance(timing, dict):
                    print(
                        "[remote-tts] "
                        f"cache_hit={int(bool(timing.get('cache_hit')))} "
                        f"queue_s={timing.get('queue_wait_s', 0)} "
                        f"generation_s={timing.get('generation_s', 0)} "
                        f"server_total_s={timing.get('total_s', 0)}",
                        file=sys.stderr,
                        flush=True,
                    )
                return payload
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Remote TTS bad JSON: {raw[:200]}") from exc
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            if exc.code in (429, 503) and time.monotonic() + busy_delay <= busy_deadline:
                print(
                    f"[remote-tts] busy (HTTP {exc.code}); retrying in {busy_delay:.1f}s",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(busy_delay)
                busy_delay = min(busy_delay * 1.6, 5.0)
                continue
            raise RuntimeError(f"Remote TTS HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            attempt += 1
            if attempt < retries:
                continue
            raise RuntimeError(f"Remote TTS unreachable at {url}: {exc.reason}") from exc


_health_cache: dict[str, Any] = {"at": 0.0, "payload": None, "failed_at": 0.0}
_HEALTH_CACHE_TTL_S = 15.0
_REMOTE_HEALTH_TIMEOUT_S = 8.0
# A down server is re-checked at most this often (every phrase would otherwise wait).
_HEALTH_FAIL_TTL_S = 10.0
# Past this age a "healthy" answer is not trusted when the server stops answering.
_HEALTH_STALE_MAX_S = 60.0


def _fetch_remote_health(timeout_s: float | None = None) -> dict[str, Any] | None:
    if not remote_tts_configured():
        return None
    t = timeout_s if timeout_s is not None else _REMOTE_HEALTH_TIMEOUT_S
    now = time.monotonic()
    cached = _health_cache.get("payload")
    if cached is not None and now - float(_health_cache["at"]) < _HEALTH_CACHE_TTL_S:
        return cached
    if cached is None and now - float(_health_cache.get("failed_at") or 0.0) < _HEALTH_FAIL_TTL_S:
        return None
    try:
        url = f"{remote_tts_url()}/api/health"
        req = urllib.request.Request(url, headers=_http_headers())
        with _opener_get().open(req, timeout=t) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        _health_cache["at"] = now
        _health_cache["payload"] = payload
        return payload
    except Exception:
        # Return stale cache on transient Cloudflare slowness instead of false "unhealthy".
        if cached is not None and now - float(_health_cache["at"]) < _HEALTH_STALE_MAX_S:
            return cached
        _health_cache["payload"] = None
        _health_cache["failed_at"] = now
        return None


def _is_tts_health_ok(payload: dict[str, Any]) -> bool:
    status = str(payload.get("status", "")).lower()
    if status in {"ok", "ready"}:
        return True
    if payload.get("ready") is True:
        return True
    # Legacy / warming — reachable and Parler available counts as healthy
    if payload.get("parler") and status not in {"unavailable", "error"}:
        return True
    return False


def remote_tts_healthy(timeout_s: float | None = None) -> bool:
    if not remote_tts_configured():
        return False
    speak_t = _timeout_s()
    if timeout_s is not None:
        t = timeout_s
    elif speak_t is None:
        t = 8.0
    else:
        t = min(speak_t, 8.0)
    payload = _fetch_remote_health(timeout_s=t)
    return bool(payload and _is_tts_health_ok(payload))


def remote_tts_status(*, fast: bool = False) -> dict[str, Any]:
    configured = remote_tts_configured()
    healthy = False
    ready = False
    warmup: dict[str, Any] | None = None
    if configured:
        if fast:
            payload = _health_cache.get("payload")
        else:
            payload = _fetch_remote_health()
        if payload:
            healthy = _is_tts_health_ok(payload)
            ready = bool(payload.get("ready")) or str(payload.get("status", "")).lower() == "ready"
            warmup = payload.get("warmup") if isinstance(payload.get("warmup"), dict) else None
    return {
        "configured": configured,
        "url": remote_tts_url(),
        "healthy": healthy,
        "ready": ready,
        "warmup": warmup,
    }


def synthesise_kannada_remote(
    kannada_text: str,
    *,
    speaker: str | None = None,
) -> tuple[np.ndarray, int]:
    """POST text to remote speak-kannada; return float32 mono audio + sample rate."""
    text = (kannada_text or "").strip()
    if not text:
        raise ValueError("empty text")

    body: dict[str, Any] = {"text": text}
    if speaker:
        body["speaker"] = speaker

    payload = _request("POST", "/api/speak-kannada", body)
    b64 = (payload.get("audio_b64") or "").strip()
    if not b64:
        err = payload.get("error") or payload.get("detail") or "empty audio_b64"
        raise RuntimeError(f"Remote TTS returned no audio: {err}")

    raw = base64.b64decode(b64)
    audio, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
    if isinstance(audio, np.ndarray) and audio.ndim > 1:
        audio = audio.mean(axis=1)
    return np.asarray(audio, dtype=np.float32), int(sr)


def fetch_kannada_b64_remote(text: str, *, speaker: str | None = None) -> str:
    """Return base64 WAV from remote (for speak_cache / API routes)."""
    text = (text or "").strip()
    if not text:
        return ""
    if not speaker:
        try:
            from api.app_settings import get_tts_speaker

            speaker = get_tts_speaker()
        except Exception:
            speaker = os.environ.get("BANK_TTS_SPEAKER", "Suresh")
    body: dict[str, Any] = {"text": text, "speaker": speaker}
    payload = _request("POST", "/api/speak-kannada", body)
    b64 = (payload.get("audio_b64") or "").strip()
    if not b64:
        return ""
    from backend.tts.audio_util import trim_wav_b64

    return trim_wav_b64(b64)
