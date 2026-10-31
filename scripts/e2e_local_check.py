"""Quick end-to-end smoke test for local single-PC deployment."""

from __future__ import annotations



import json

import os

import sys

import time

import urllib.error

import urllib.request



ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT)



API = os.environ.get("BANK_API_URL", "http://127.0.0.1:8000")

TTS = os.environ.get("BANK_TTS_URL", "http://127.0.0.1:8001")

KEY = os.environ.get("BANK_TTS_REMOTE_KEY", "")





def _get(url: str, timeout: float = 5.0) -> tuple[float, dict | str]:

    t0 = time.perf_counter()

    try:

        with urllib.request.urlopen(url, timeout=timeout) as resp:

            body = resp.read().decode("utf-8")

        dt = time.perf_counter() - t0

        try:

            return dt, json.loads(body)

        except json.JSONDecodeError:

            return dt, body[:200]

    except Exception as exc:

        return time.perf_counter() - t0, str(exc)





def _post_json(url: str, payload: dict, headers: dict | None = None, timeout: float = 120.0) -> tuple[float, dict | str]:

    t0 = time.perf_counter()

    data = json.dumps(payload).encode("utf-8")

    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}

    if headers:

        hdrs.update(headers)

    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")

    try:

        with urllib.request.urlopen(req, timeout=timeout) as resp:

            body = resp.read().decode("utf-8")

        dt = time.perf_counter() - t0

        try:

            return dt, json.loads(body)

        except json.JSONDecodeError:

            return dt, body[:200]

    except urllib.error.HTTPError as exc:

        detail = exc.read().decode("utf-8", errors="replace")[:300]

        return time.perf_counter() - t0, f"HTTP {exc.code}: {detail}"

    except Exception as exc:

        return time.perf_counter() - t0, str(exc)





def _wait_tts_ready(timeout_s: float = 180.0) -> tuple[float, dict | str]:

    """Poll TTS /api/health until ready=true (Parler loaded at startup)."""

    t0 = time.perf_counter()

    last: dict | str = {}

    while time.perf_counter() - t0 < timeout_s:

        dt, payload = _get(f"{TTS}/api/health", timeout=8)

        last = payload

        if isinstance(payload, dict) and (

            payload.get("ready") is True or payload.get("status") == "ready"

        ):

            return time.perf_counter() - t0, payload

        time.sleep(2)

    return time.perf_counter() - t0, last





def main() -> int:

    print("=== End-to-end local check ===")

    print(f"API: {API}")

    print(f"TTS: {TTS}")

    print()



    dt, api_health = _get(f"{API}/api/health", timeout=12)

    print(f"[API health] {dt:.2f}s -> {api_health}")



    print("[TTS ready]  waiting for Parler warmup (first start ~1-2 min)…")

    dt, tts_health = _wait_tts_ready(timeout_s=180)

    ready = isinstance(tts_health, dict) and (

        tts_health.get("ready") is True or tts_health.get("status") == "ready"

    )

    print(f"[TTS ready]  {dt:.1f}s -> {'OK' if ready else tts_health}")



    dt, tts_speak = _post_json(

        f"{TTS}/api/speak-kannada",

        {"text": "ನಮಸ್ಕಾರ. ಬ್ಯಾಲೆನ್ಸ್ ತಿಳಿಸಿ."},

        headers={"X-Bank-Tts-Key": KEY} if KEY else None,

        timeout=30,

    )

    ok = isinstance(tts_speak, dict) and bool(tts_speak.get("audio_b64"))

    print(f"[TTS speak]  {dt:.2f}s -> {'OK' if ok else tts_speak}")



    dt, admin = _post_json(f"{API}/api/admin/login", {"username": "admin", "password": "bank@123"}, timeout=15)

    admin_ok = isinstance(admin, dict) and bool(admin.get("token"))

    print(f"[Admin login] {dt:.2f}s -> {'OK' if admin_ok else admin}")



    print()

    if ok and admin_ok and ready and isinstance(api_health, dict) and api_health.get("status") == "ok":

        print("RESULT: PASS")

        return 0

    print("RESULT: ISSUES FOUND — ensure TTS server started first and wait for 'Ready' in its log")

    return 1





if __name__ == "__main__":

    raise SystemExit(main())

