"""Background warm of time-slot greeting WAV files (remote TTS safe)."""

from __future__ import annotations

import os
import sys


def warm_first_greeting_variants() -> dict:
    """
    Cache variant 0 for each time slot into data/greetings/.

    Uses remote Parler when BANK_TTS_REMOTE_URL is set — does not load local GPU.
    """
    from backend.greetings import GREET_LINES
    from backend.tts.remote_bridge import remote_tts_configured

    if not remote_tts_configured():
        return {"ok": False, "cached": 0, "error": "remote TTS not configured"}

    from api.routes import kiosk as kiosk_routes

    ok = 0
    skipped = 0
    failed = 0
    for slot in GREET_LINES:
        path = kiosk_routes._cache_path(slot, 0)
        if os.path.isfile(path) and os.path.getsize(path) > 1000:
            skipped += 1
            continue
        payload = kiosk_routes._generate_variant(slot, 0)
        if payload.get("audio_b64"):
            ok += 1
        else:
            failed += 1
            err = payload.get("error") or "unknown"
            print(f"[greet-warm] {slot}_0 failed: {err}", file=sys.stderr)

    total = ok + skipped
    print(
        f"[greet-warm] greeting cache: {ok} new, {skipped} skipped, {failed} failed",
        file=sys.stderr,
    )
    return {"ok": failed == 0, "cached": ok, "skipped": skipped, "failed": failed}
