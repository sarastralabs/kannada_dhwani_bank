"""Benchmark remote Kannada TTS latency for both supported speakers."""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import statistics
import sys
import time
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROMPTS = {
    "short": "ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ.",
    "medium": "ನಿಮ್ಮ ಖಾತೆ ಸಂಖ್ಯೆಯನ್ನು ಒಂದೊಂದೇ ಅಂಕಿಯಾಗಿ ಹೇಳಿ.",
    "long": (
        "ನಮಸ್ಕಾರ. ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್ ಸೇವೆಗೆ ಸುಸ್ವಾಗತ. "
        "ಖಾತೆಯ ಶಿಲ್ಕು, ಅರ್ಜಿ ನಮೂನೆ ಅಥವಾ ಸಾಲದ ಮಾಹಿತಿಗಾಗಿ ಕೇಳಬಹುದು."
    ),
}


def _post(url: str, key: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{url.rstrip('/')}/api/speak-kannada",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "BankAssistantTTSBenchmark/1.0",
            **({"X-Bank-Tts-Key": key} if key else {}),
        },
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))
    result["client_total_s"] = round(time.perf_counter() - started, 3)
    return result


def _audio_duration(audio_b64: str) -> float | None:
    try:
        with wave.open(io.BytesIO(base64.b64decode(audio_b64)), "rb") as wav:
            return round(wav.getnframes() / wav.getframerate(), 3)
    except (ValueError, wave.Error, ZeroDivisionError):
        return None


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--cached-only", action="store_true")
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--audio-dir",
        default="",
        help="Write generated WAV files for Kannada listening checks",
    )
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
    except Exception:
        pass

    url = args.url or os.environ.get("BANK_TTS_REMOTE_URL", "")
    key = os.environ.get("BANK_TTS_REMOTE_KEY", "")
    if not url:
        print("Set BANK_TTS_REMOTE_URL or pass --url.", file=sys.stderr)
        return 2

    rows: list[dict] = []
    modes = ["cached"] if args.cached_only else ["cached", "uncached"]
    for speaker in ("Suresh", "Anu"):
        for label, text in PROMPTS.items():
            _post(url, key, {"text": text, "speaker": speaker})
            for mode in modes:
                for run in range(1, max(1, args.repeats) + 1):
                    result = _post(
                        url,
                        key,
                        {
                            "text": text,
                            "speaker": speaker,
                            "bypass_cache": mode == "uncached",
                        },
                    )
                    timing = result.get("timing") or {}
                    row = {
                        "speaker": speaker,
                        "prompt": label,
                        "mode": mode,
                        "run": run,
                        "client_total_s": result["client_total_s"],
                        "server_total_s": timing.get("total_s"),
                        "generation_s": timing.get("generation_s"),
                        "queue_wait_s": timing.get("queue_wait_s"),
                        "audio_duration_s": timing.get("audio_duration_s")
                        or _audio_duration(result.get("audio_b64") or ""),
                        "max_new_tokens": timing.get("max_new_tokens"),
                        "device": timing.get("device"),
                        "dtype": timing.get("dtype"),
                    }
                    rows.append(row)
                    if args.audio_dir:
                        audio_dir = Path(args.audio_dir)
                        audio_dir.mkdir(parents=True, exist_ok=True)
                        audio_path = audio_dir / f"{speaker}_{label}_{mode}_{run}.wav"
                        audio_path.write_bytes(
                            base64.b64decode(result.get("audio_b64") or "")
                        )
                    print(
                        f"{speaker:7} {label:6} {mode:8} run={run} "
                        f"client={row['client_total_s']:.3f}s "
                        f"generate={row['generation_s']}s audio={row['audio_duration_s']}s"
                    )

    print("\nSummary")
    groups = {
        (row["speaker"], row["prompt"], row["mode"])
        for row in rows
    }
    for speaker, prompt, mode in sorted(groups):
        values = [
            float(row["client_total_s"])
            for row in rows
            if (row["speaker"], row["prompt"], row["mode"])
            == (speaker, prompt, mode)
        ]
        print(
            f"{speaker:7} {prompt:6} {mode:8} "
            f"p50={statistics.median(values):.3f}s p95={_percentile(values, 0.95):.3f}s"
        )

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
