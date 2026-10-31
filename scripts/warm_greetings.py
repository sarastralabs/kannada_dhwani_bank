"""
Pre-cache Kannada greeting WAV files for all time slots.

Preferred (deployed Parler TTS box):
    py -3.12 scripts/warm_greetings.py --remote --force
    py -3.12 scripts/warm_greetings.py --remote --force --first-only

If BANK_TTS_REMOTE_URL is set, --remote is the default (no MMS).

Local MMS only when remote is NOT configured:
    py -3.12 scripts/warm_greetings.py --mms
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from backend.greetings import GREET_LINES  # noqa: E402

GREET_SCRIPT = os.path.join(ROOT, "run_kiosk_greet_subprocess.py")
GREET_DIR = os.path.join(ROOT, "data", "greetings")

_OFFLINE_ENV = {
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "BANK_TTS_ENGINE": "mms",
}


def _cache_path(slot: str, variant: int) -> str:
    speaker = (
        "Anu"
        if os.environ.get("BANK_TTS_SPEAKER", "Suresh").strip().lower() == "anu"
        else "Suresh"
    )
    return os.path.join(GREET_DIR, f"{slot}_{variant}_{speaker.lower()}.wav")


def _is_cached(slot: str, variant: int) -> bool:
    path = _cache_path(slot, variant)
    return os.path.isfile(path) and os.path.getsize(path) > 1000


def _write_cache_from_stdout(slot: str, variant: int, stdout: str) -> bool:
    """Parse JSON line from greet subprocess and write data/greetings/*.wav."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("error"):
            return False
        b64 = payload.get("audio_b64") or ""
        if not b64:
            return False
        os.makedirs(GREET_DIR, exist_ok=True)
        with open(_cache_path(slot, variant), "wb") as f:
            f.write(base64.b64decode(b64))
        return True
    return False


def _generate(slot: str, variant: int, *, env: dict[str, str], timeout: int) -> bool:
    print(f"  Generating {slot}_{variant}…", flush=True)
    try:
        proc = subprocess.run(
            [sys.executable, GREET_SCRIPT, slot, str(variant)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env={**os.environ, **env},
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"  FAIL {slot}_{variant}: timeout", flush=True)
        return False
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:200]
        print(f"  FAIL {slot}_{variant}: {err}", flush=True)
        return False
    if not _is_cached(slot, variant):
        if not _write_cache_from_stdout(slot, variant, proc.stdout or ""):
            print(f"  FAIL {slot}_{variant}: no WAV written", flush=True)
            return False
    print(f"  OK   {slot}_{variant}", flush=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache Kannada lobby greeting WAVs")
    parser.add_argument(
        "--first-only",
        action="store_true",
        help="Only warm variant 0 for each time slot (enough for demos)",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Use BANK_TTS_REMOTE_URL (remote Parler) — no local GPU",
    )
    parser.add_argument(
        "--mms",
        action="store_true",
        help="Force local MMS-TTS (only if remote TTS is not configured)",
    )
    parser.add_argument(
        "--parler",
        action="store_true",
        help="Use local Indic Parler-TTS (Suresh) — stop API first",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if cache files already exist",
    )
    parser.add_argument(
        "--speaker",
        choices=("Suresh", "Anu"),
        default="Suresh",
        help="Voice to warm (default: Suresh)",
    )
    args = parser.parse_args()

    # Load .env so BANK_TTS_REMOTE_URL is visible when run from shell
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(ROOT, ".env"), override=False)
    except Exception:
        pass
    os.environ["BANK_TTS_SPEAKER"] = args.speaker

    os.makedirs(GREET_DIR, exist_ok=True)
    total = 0
    ok = 0
    skipped = 0

    remote_url = os.environ.get("BANK_TTS_REMOTE_URL", "").strip()
    use_remote = args.remote or (bool(remote_url) and not args.mms and not args.parler)

    if use_remote:
        args.remote = True

    if args.remote:
        from backend.tts.remote_bridge import remote_tts_configured

        if not remote_tts_configured():
            print("BANK_TTS_REMOTE_URL not set — cannot use --remote", flush=True)
            return 1
        warm_env = dict(os.environ)
        label = f"remote Parler ({os.environ.get('BANK_TTS_REMOTE_URL', '').strip()})"

        def _generate_remote(slot: str, variant: int) -> bool:
            from backend.greetings import pick_greeting
            from backend.tts.speak_cache import kannada_to_b64

            greet = pick_greeting(slot=slot, variant=variant)  # type: ignore[arg-type]
            line = (greet.get("line_kn") or "").strip()
            if not line:
                return False
            print(f"  Remote TTS {slot}_{variant}…", flush=True)
            try:
                b64 = kannada_to_b64(line, speaker=args.speaker)
            except Exception as exc:
                print(f"  FAIL {slot}_{variant}: {exc}", flush=True)
                return False
            if not b64:
                return False
            os.makedirs(GREET_DIR, exist_ok=True)
            with open(_cache_path(slot, variant), "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"  OK   {slot}_{variant}", flush=True)
            return True

        print(f"Warming greeting audio cache ({label})…")
        for slot, lines in GREET_LINES.items():
            variants = [0] if args.first_only else list(range(len(lines)))
            for variant in variants:
                total += 1
                if not args.force and _is_cached(slot, variant):
                    print(f"  SKIP {slot}_{variant} (cached)", flush=True)
                    skipped += 1
                    ok += 1
                    continue
                if _generate_remote(slot, variant):
                    ok += 1
        print(f"\nDone: {ok}/{total} ready ({skipped} already cached)")
        return 0 if ok >= total else 1

    if not args.parler and not args.mms:
        print(
            "Refusing default MMS. Set BANK_TTS_REMOTE_URL and run:\n"
            "  py -3.12 scripts\\warm_greetings.py --remote --force --first-only\n"
            "Or pass --mms / --parler explicitly.",
            flush=True,
        )
        return 1

    if args.parler:
        warm_env = {
            "BANK_GREET_TTS_ENGINE": "parler",
            "BANK_TTS_ENGINE": "parler",
            "BANK_TTS_SPEAKER": args.speaker,
            "BANK_GREET_ALLOW_ONLINE": "1",
        }
        label = f"Indic Parler-TTS ({args.speaker})"
        timeout = 600
    else:
        warm_env = dict(_OFFLINE_ENV)
        label = "MMS-TTS (offline)"
        timeout = 180

    print(f"Warming greeting audio cache ({label})…")
    for slot, lines in GREET_LINES.items():
        variants = [0] if args.first_only else list(range(len(lines)))
        for variant in variants:
            total += 1
            if not args.force and _is_cached(slot, variant):
                print(f"  SKIP {slot}_{variant} (cached)", flush=True)
                skipped += 1
                ok += 1
                continue
            if args.force and _is_cached(slot, variant):
                try:
                    os.remove(_cache_path(slot, variant))
                except OSError:
                    pass
            if _generate(slot, variant, env=warm_env, timeout=timeout):
                ok += 1

    print(f"\nDone: {ok}/{total} ready ({skipped} already cached)")
    if ok < total:
        engine_hint = "Run: .\\scripts\\setup_parler_venv.ps1 then retry --parler" if args.parler else "BANK_TTS_ENGINE=mms"
        print(f"Some greetings failed — {engine_hint}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
