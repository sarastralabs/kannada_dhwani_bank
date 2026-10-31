"""
backend/demo_pipeline.py

End-to-end demonstration of the voice banking assistant pipeline:

    Kannada speech (.wav)
        → STT           (Whisper, specialized model)
        → Translation   (IndicTrans2 Kannada → English)
        → NLU           (fine-tuned DistilBERT intent classifier)
        → Decision Router (deterministic routing + English response_text)
        → synthesise(response_text)
              internally: split sentences → translate_en_to_kn() → MMS-TTS → audio

Usage
-----
    # Single clip
    python backend/demo_pipeline.py data/stt_test_audio/clip_001.wav

    # All 11 test clips (default when no argument given)
    python backend/demo_pipeline.py

    # Explicit --all flag
    python backend/demo_pipeline.py --all

    # Quiet mode: summary table only, no per-stage detail
    python backend/demo_pipeline.py --all --quiet

Output
------
    Per-clip: labeled stage outputs (Kannada, English, intent, route, response)
    End of run: summary table  (clip | STT quality | intent | route | conf)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tabulate import tabulate

# ---------------------------------------------------------------------------
# Lazy imports — modules are heavy; only load them when processing begins
# ---------------------------------------------------------------------------
_stt_loaded         = False
_translation_loaded = False
_nlu_loaded         = False
_router_loaded      = False


def _ensure_loaded() -> None:
    global _stt_loaded, _translation_loaded, _nlu_loaded, _router_loaded
    if not _stt_loaded:
        global transcribe
        from backend.stt import transcribe
        _stt_loaded = True
    if not _translation_loaded:
        global translate_kn_to_en
        from backend.translation import translate_kn_to_en
        _translation_loaded = True
    if not _nlu_loaded:
        global classify
        from backend.nlu import classify
        _nlu_loaded = True
    if not _router_loaded:
        global route, RouterError
        from backend.decision_router import route, RouterError
        _router_loaded = True


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DATA_DIR     = os.path.join(_PROJECT_ROOT, "data", "stt_test_audio")
_TRANSCRIPTS  = os.path.join(_DATA_DIR, "transcripts.json")

# Kannada ground truth for display (loaded once)
_KANNADA_GT: dict[str, str] = {}
if os.path.exists(_TRANSCRIPTS):
    with open(_TRANSCRIPTS, encoding="utf-8") as _f:
        _KANNADA_GT = json.load(_f)


# ---------------------------------------------------------------------------
# Single-clip pipeline
# ---------------------------------------------------------------------------

def run_clip(wav_path: str, verbose: bool = True) -> dict:
    """
    Run the full pipeline on one .wav file.

    Returns a result dict regardless of errors at any stage.
    Never raises — all exceptions are caught and stored in the result.
    """
    _ensure_loaded()

    clip_name = os.path.basename(wav_path)
    kannada_gt = _KANNADA_GT.get(clip_name, "(no ground truth)")

    result = {
        "clip":          clip_name,
        "kannada_gt":    kannada_gt,
        "stt_output":    "",
        "english":       "",
        "intent":        "",
        "confidence":    0.0,
        "route":         "",
        "response_text": "",
        "total_time_s":  0.0,
        "errors":        [],
    }

    t_start = time.perf_counter()

    # ── Stage 1: STT ─────────────────────────────────────────────────────────
    try:
        stt_output = transcribe(wav_path, beam_size=1)
        result["stt_output"] = stt_output
    except Exception as e:
        result["errors"].append(f"STT: {e}")
        stt_output = ""

    # ── Stage 2: Translation ──────────────────────────────────────────────────
    english = ""
    if stt_output:
        try:
            english = translate_kn_to_en(stt_output)
            result["english"] = english
        except Exception as e:
            result["errors"].append(f"Translation: {e}")
    else:
        result["errors"].append("Translation: skipped (empty STT output)")

    # ── Stage 3: NLU ──────────────────────────────────────────────────────────
    intent = ""
    confidence = 0.0
    if english:
        try:
            intent, confidence = classify(english)
            result["intent"]     = intent
            result["confidence"] = confidence
        except Exception as e:
            result["errors"].append(f"NLU: {e}")
    else:
        result["errors"].append("NLU: skipped (empty translation)")

    # ── Stage 4: Decision Router ──────────────────────────────────────────────
    if intent:
        try:
            routing = route(intent)
            result["route"]         = routing["route"]
            result["response_text"] = routing["response_text"]
        except Exception as e:
            result["errors"].append(f"Router: {e}")
    else:
        result["errors"].append("Router: skipped (no intent)")

    result["total_time_s"] = round(time.perf_counter() - t_start, 2)

    # ── Pretty print (verbose mode) ───────────────────────────────────────────
    if verbose:
        _print_clip_result(result)

    return result


def _print_clip_result(r: dict) -> None:
    w = 72
    print(f"\n{'─'*w}")
    print(f"  Clip       : {r['clip']}")
    print(f"  Kannada GT : {r['kannada_gt']}")
    print(f"{'─'*w}")
    print(f"  [STT]      : {r['stt_output'] or '(empty)'}")
    print(f"  [TRANSLATE]: {r['english']    or '(empty)'}")

    intent_str = f"{r['intent']} (conf={r['confidence']:.3f})" if r["intent"] else "(none)"
    print(f"  [NLU]      : {intent_str}")

    if r["route"]:
        print(f"  [ROUTER]   : route={r['route']}")
        # Wrap response_text at 65 chars for readability
        words = r["response_text"].split()
        lines, current = [], []
        for word in words:
            current.append(word)
            if len(" ".join(current)) > 65:
                lines.append(" ".join(current[:-1]))
                current = [word]
        if current:
            lines.append(" ".join(current))
        print(f"  [RESPONSE] : {lines[0]}")
        for line in lines[1:]:
            print(f"               {line}")
    else:
        print(f"  [ROUTER]   : (no route — pipeline stalled)")

    if r["errors"]:
        for err in r["errors"]:
            print(f"  [!] {err}")

    print(f"  Time       : {r['total_time_s']}s")


# ---------------------------------------------------------------------------
# All-clips run
# ---------------------------------------------------------------------------

def run_all(quiet: bool = False) -> list[dict]:
    """Run the pipeline on all 11 test clips and print a summary table."""
    if not os.path.exists(_TRANSCRIPTS):
        print(f"[ERROR] transcripts.json not found at {_TRANSCRIPTS}", file=sys.stderr)
        sys.exit(1)

    clips = sorted(_KANNADA_GT.keys())
    print(f"Running pipeline on {len(clips)} clips …")
    print("(First call loads STT + Translation + NLU models — allow ~15–20s)\n")

    results = []
    for clip in clips:
        wav_path = os.path.join(_DATA_DIR, clip)
        if not os.path.exists(wav_path):
            print(f"  SKIP {clip} — audio file missing")
            continue
        r = run_clip(wav_path, verbose=not quiet)
        results.append(r)

    _print_summary(results)
    return results


def _print_summary(results: list[dict]) -> None:
    print(f"\n{'═'*90}")
    print("  PIPELINE SUMMARY — all clips")
    print(f"{'═'*90}")

    rows = []
    for r in results:
        stt_ok = "✓" if r["stt_output"] else "✗ empty"
        trans_ok = "✓" if r["english"] else "✗ empty"
        intent_str = f"{r['intent']} ({r['confidence']:.2f})" if r["intent"] else "—"
        route_str  = r["route"] if r["route"] else "—"
        errors_str = "; ".join(r["errors"]) if r["errors"] else ""
        rows.append([
            r["clip"],
            r["kannada_gt"][:28] + ("…" if len(r["kannada_gt"]) > 28 else ""),
            stt_ok,
            trans_ok,
            intent_str,
            route_str,
            f"{r['total_time_s']}s",
        ])

    print(tabulate(
        rows,
        headers=["clip", "Kannada GT", "STT", "Trans", "intent (conf)", "route", "time"],
        tablefmt="github",
    ))

    # Accuracy against manually known correct intents
    known_correct = {
        "clip_001.wav": "check_balance",
        "clip_003.wav": "apply_loan",
        "clip_004.wav": "open_account",
        "clip_006.wav": "account_info_query",
        "clip_007.wav": "account_info_query",
        "clip_011.wav": "account_info_query",
        "clip_012.wav": "account_info_query",
        "clip_013.wav": "account_info_query",
        "clip_014.wav": "interest_rate_query",
        "clip_015.wav": "account_info_query",
        # clip_002 excluded — STT/translation too corrupted to judge
    }

    correct = total = 0
    for r in results:
        expected = known_correct.get(r["clip"])
        if expected is None:
            continue
        total += 1
        if r["intent"] == expected:
            correct += 1

    print(f"\n  Pipeline intent accuracy : {correct}/{total} = {correct/total:.1%}"
          f"  (clip_002 excluded — STT too corrupted)")
    print(f"  Total wall-clock time    : {sum(r['total_time_s'] for r in results):.1f}s")
    print(f"{'═'*90}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end voice banking assistant pipeline demo."
    )
    parser.add_argument(
        "wav_file", nargs="?", default=None,
        help="Path to a .wav file. Omit to run all 11 test clips.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all 11 test clips and print a summary table.",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-clip detail; show summary table only.",
    )
    args = parser.parse_args()

    if args.wav_file and not args.all:
        # Single clip
        if not os.path.exists(args.wav_file):
            print(f"[ERROR] File not found: {args.wav_file}", file=sys.stderr)
            sys.exit(1)
        _ensure_loaded()
        run_clip(args.wav_file, verbose=True)
    else:
        # All clips (default when no argument, or --all explicit)
        run_all(quiet=args.quiet)


if __name__ == "__main__":
    main()
