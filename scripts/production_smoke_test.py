"""
Production smoke test — run after changes or before demo.

    py -3.12 scripts/production_smoke_test.py
    py -3.12 scripts/production_smoke_test.py --api http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("BANK_TTS_ENGINE", "mms")


def _get(url: str, timeout: float = 30) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def _post_json(url: str, body: dict, timeout: float = 120) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=os.environ.get("BANK_API", "http://127.0.0.1:8000"))
    args = parser.parse_args()
    api = args.api.rstrip("/")
    failed: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            failed.append(name)

    print(f"\n=== Production smoke test ({api}) ===\n")

    # ── Offline unit checks (no server) ─────────────────────────────────────
    print("Offline modules:")
    try:
        from backend.forms.kannada_digits import extract_digits_from_kannada

        d1 = extract_digits_from_kannada("1234567890")
        d2 = extract_digits_from_kannada("my account is 1234567890")
        check("kannada_digits ASCII", d1 == "1234567890" and d2 == "1234567890")
    except Exception as exc:
        check("kannada_digits", False, str(exc))

    try:
        from backend.balance_lookup import lookup_balance

        r = lookup_balance("1234567890")
        check("balance_lookup", r.get("found") is True and r.get("balance_inr") == 45230.50)
    except Exception as exc:
        check("balance_lookup", False, str(exc))

    try:
        from backend.decision_router import route

        r = route("check_balance")
        check(
            "router check_balance transactional",
            r.get("route") == "transactional" and "account" in r.get("response_text", "").lower(),
        )
    except Exception as exc:
        check("router check_balance", False, str(exc))

    try:
        from backend.forms.intent_map import form_id_for_intent

        check("intent_map check_balance", form_id_for_intent("check_balance") == "balance_inquiry")
    except Exception as exc:
        check("intent_map", False, str(exc))

    try:
        from backend.tts.speak_cache import get_cached_b64, put_cached_b64

        put_cached_b64("smoke_test_phrase", "dGVzdA==")
        hit = get_cached_b64("smoke_test_phrase")
        check("speak_cache roundtrip", hit == "dGVzdA==")
    except Exception as exc:
        check("speak_cache", False, str(exc))

    # ── API checks ────────────────────────────────────────────────────────────
    print("\nAPI endpoints:")
    try:
        h = _get(f"{api}/api/health/live", timeout=5)
        check("GET /api/health/live", h.get("live") is True)
    except Exception as exc:
        check("GET /api/health/live", False, str(exc))

    try:
        h = _get(f"{api}/api/health", timeout=15)
        check("GET /api/health", h.get("status") in ("ok", "degraded"))
    except Exception as exc:
        check("GET /api/health", False, str(exc))
        print("\n  API not reachable — start: py -3.12 -m uvicorn api.main:app --host 0.0.0.0 --port 8000")
        print(f"\n=== {len(failed)} failure(s) ===\n")
        return 1

    try:
        lite = _get(f"{api}/api/kiosk/status/lite", timeout=5)
        check(
            "GET /api/kiosk/status/lite",
            "running" in lite and "sessions" not in lite,
        )
    except Exception as exc:
        check("GET /api/kiosk/status/lite", False, str(exc))

    try:
        form = _get(f"{api}/api/forms/balance_inquiry")
        check("GET /api/forms/balance_inquiry", form.get("id") == "balance_inquiry")
    except Exception as exc:
        check("GET balance_inquiry form", False, str(exc))

    try:
        bal = _get(f"{api}/api/balance/1234567890")
        check(
            "GET /api/balance/{acct}",
            bal.get("found") is True
            and bal.get("balance_inr") == 45230.50
            and "45,230" in bal.get("message_kn", ""),
        )
    except Exception as exc:
        check("GET /api/balance", False, str(exc))

    wav = os.path.join(ROOT, "data", "stt_test_audio", "clip_001.wav")
    if os.path.isfile(wav):
        try:
            with open(wav, "rb") as wf:
                audio_bytes = wf.read()
            boundary = "----SmokeTestBoundary"
            body = (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="audio"; filename="clip_001.wav"\r\n'
                "Content-Type: audio/wav\r\n\r\n"
            ).encode("utf-8") + audio_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
            req = urllib.request.Request(
                f"{api}/api/process-audio",
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read())
            check(
                "POST /api/process-audio clip_001",
                not data.get("error") and data.get("intent") == "check_balance",
                data.get("error") or f"intent={data.get('intent')}",
            )
        except Exception as exc:
            detail = str(exc)
            if isinstance(exc, urllib.error.HTTPError):
                detail = exc.read().decode()[:200]
            check("POST /api/process-audio", False, detail)
    else:
        print("  [SKIP] process-audio — no clip_001.wav")

    try:
        speak = _post_json(f"{api}/api/speak-kannada", {"text": "ದಯವಿಟ್ಟು ಹೇಳಿ"})
        check("POST /api/speak-kannada", len(speak.get("audio_b64") or "") > 1000)
        speak2 = _post_json(f"{api}/api/speak-kannada", {"text": "ನಮಸ್ಕಾರ"})
        check("POST /api/speak-kannada (repeat)", len(speak2.get("audio_b64") or "") > 1000)
    except Exception as exc:
        detail = str(exc)
        if isinstance(exc, urllib.error.HTTPError):
            detail = exc.read().decode()[:200]
        check("POST /api/speak-kannada", False, detail)

    try:
        prompts = _get(f"{api}/api/forms/balance_inquiry/prompt-audio", timeout=120)
        audio = prompts.get("audio") or {}
        check(
            "GET prompt-audio balance_inquiry",
            "account_number" in audio and len(audio.get("account_number") or "") > 100,
        )
    except Exception as exc:
        detail = str(exc)
        if isinstance(exc, urllib.error.HTTPError):
            detail = exc.read().decode()[:200]
        check("GET prompt-audio", False, detail)

    try:
        summary = _post_json(
            f"{api}/api/forms/cash_withdrawal/summary",
            {
                "values": {
                    "full_name": "ರಾಮೇಶ್ ಕುಮಾರ್",
                    "account_number": "1234567890",
                    "amount": "5000",
                }
            },
            timeout=30,
        )
        check(
            "POST /api/forms/cash_withdrawal/summary",
            bool(summary.get("summary_kn")) and len(summary.get("lines") or []) >= 2,
        )
    except Exception as exc:
        detail = str(exc)
        if isinstance(exc, urllib.error.HTTPError):
            detail = exc.read().decode()[:200]
        check("POST form summary", False, detail)

    print("\nOffline TTS (after API — avoids GPU clash with pipeline worker):")
    try:
        from backend.tts.speak_cache import kannada_to_b64

        os.environ["BANK_TTS_DEVICE"] = "cpu"
        b64 = kannada_to_b64("ನಮಸ್ಕಾರ")
        check("speak_cache TTS synth", len(b64 or "") > 1000)
    except Exception as exc:
        check("speak_cache TTS synth", False, str(exc))

    print(f"\n=== {'ALL PASS' if not failed else f'{len(failed)} FAILURE(S)'} ===")
    for f in failed:
        print(f"  - {f}")
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
