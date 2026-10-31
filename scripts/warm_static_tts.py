"""Persist privacy-safe static Kannada speech for both assistant voices."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--speakers",
        default="Suresh,Anu",
        help="Comma-separated speakers (default: Suresh,Anu)",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate cached phrases")
    parser.add_argument("--limit", type=int, default=0, help="Limit phrases for a smoke run")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
    except Exception:
        pass

    from backend.tts.remote_bridge import remote_tts_configured
    from backend.tts.speak_cache import get_cached_b64, kannada_to_b64
    from backend.tts.static_phrases import static_kannada_phrases

    if not remote_tts_configured() and os.environ.get("BANK_TTS_ENGINE", "").lower() not in {
        "parler",
        "indic-parler",
    }:
        print("Configure remote or local Parler TTS before warming.", file=sys.stderr)
        return 2

    speakers = [
        "Anu" if item.strip().lower() == "anu" else "Suresh"
        for item in args.speakers.split(",")
        if item.strip()
    ]
    speakers = list(dict.fromkeys(speakers))
    phrases = list(static_kannada_phrases())
    if args.limit > 0:
        phrases = phrases[: args.limit]

    total = len(speakers) * len(phrases)
    ready = 0
    failed = 0
    started = time.perf_counter()
    print(f"Warming {len(phrases)} static phrases for {', '.join(speakers)} ({total} clips)")

    for speaker in speakers:
        for index, phrase in enumerate(phrases, start=1):
            if not args.force and get_cached_b64(phrase, speaker=speaker):
                ready += 1
                continue
            clip_started = time.perf_counter()
            try:
                audio = kannada_to_b64(phrase, speaker=speaker, persist=True)
            except Exception as exc:
                failed += 1
                print(
                    f"FAIL {speaker} {index}/{len(phrases)}: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            if not audio:
                failed += 1
                print(
                    f"FAIL {speaker} {index}/{len(phrases)}: empty audio",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            ready += 1
            print(
                f"OK {speaker} {index}/{len(phrases)} "
                f"{time.perf_counter() - clip_started:.1f}s",
                flush=True,
            )

    elapsed = time.perf_counter() - started
    print(f"Done: {ready}/{total} ready, {failed} failed, {elapsed:.1f}s")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
