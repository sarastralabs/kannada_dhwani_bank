"""
backend/stt/benchmark.py

WER/CER benchmark harness — runs both Whisper models against the held-out
Kannada test set and produces a comparison CSV + stdout table.

Usage
-----
    # Run full benchmark (both models, default paths)
    python backend/stt/benchmark.py

    # Benchmark a single model only
    python backend/stt/benchmark.py --models baseline
    python backend/stt/benchmark.py --models specialized

    # Custom data directory and output path
    python backend/stt/benchmark.py \\
        --data-dir data/stt_test_audio \\
        --output results/benchmark_results.csv

Output CSV columns
------------------
    model_name, wer_percent, cer_percent, avg_inference_time_s,
    num_clips, total_time_s, beam_size

Notes on metrics
----------------
- WER (Word Error Rate): standard word-level edit distance metric.
  Works for Kannada because words are space-separated in standard script.
- CER (Character Error Rate): character-level edit distance.
  More informative for Kannada's conjunct characters (ಒತ್ತಕ್ಷರ) where a
  single misrecognised character makes an entire word wrong under WER.
  Both are reported; CER is the primary metric for this project.

Notes on beam_size
------------------
The benchmark intentionally uses beam_size=5 (not the production default
of 1) for both models.  This maximises transcription accuracy so the WER/CER
comparison reflects model quality, not decoding speed shortcuts.
The inference times recorded here are therefore SLOWER than production
latency — that is expected and should be noted in the project report.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import jiwer
from tabulate import tabulate

from backend.stt.transcriber import KannadaTranscriber

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Mirrors MODEL_PATHS in __init__.py — kept explicit here so benchmark.py
# can be run as a standalone script without importing the full package.
_MODEL_PATHS: dict[str, str] = {
    "baseline": os.path.join(_PROJECT_ROOT, "models", "whisper-medium-ct2"),
    "specialized": os.path.join(_PROJECT_ROOT, "models", "whisper-medium-vaani-ct2"),
    "vasista-medium": os.path.join(_PROJECT_ROOT, "models", "whisper-kannada-medium-ct2"),
}

# beam_size used for all benchmark runs (accuracy-focused, not latency-focused)
_BENCHMARK_BEAM_SIZE = 5

# Kannada-appropriate transforms for WER and CER.
# Must end with the matching tokenizer step that jiwer requires.
# We do NOT include ToLowerCase() — Kannada script has no case distinction.
#
# jiwer 4.x API: jiwer.wer() / jiwer.cer() accept
#   reference_transform= and hypothesis_transform=
# The old 'truth_transform' keyword was removed in jiwer 3.x.
_WER_TRANSFORM = jiwer.Compose([
    jiwer.Strip(),
    jiwer.RemoveMultipleSpaces(),
    jiwer.ReduceToListOfListOfWords(),   # required final step for WER
])
_CER_TRANSFORM = jiwer.Compose([
    jiwer.Strip(),
    jiwer.ReduceToListOfListOfChars(),   # required final step for CER
])


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_test_data(data_dir: str) -> dict[str, str]:
    """
    Load ground-truth transcripts from ``transcripts.json``.

    Parameters
    ----------
    data_dir:
        Directory containing ``transcripts.json`` and the ``.wav`` clip files.

    Returns
    -------
    dict[str, str]
        Mapping of ``{filename: ground_truth_kannada_text}``.

    Raises
    ------
    FileNotFoundError
        If ``transcripts.json`` is not found in *data_dir*.
    ValueError
        If ``transcripts.json`` is empty or contains no entries.
    """
    json_path = os.path.join(data_dir, "transcripts.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"transcripts.json not found in '{data_dir}'.\n"
            "Populate data/stt_test_audio/ with .wav files and transcripts.json "
            "before running the benchmark."
        )

    with open(json_path, encoding="utf-8") as f:
        data: dict[str, str] = json.load(f)

    if not data:
        raise ValueError(
            "transcripts.json is empty.  Add at least one entry before benchmarking."
        )

    return data


# ---------------------------------------------------------------------------
# Benchmarking
# ---------------------------------------------------------------------------

def run_model_benchmark(
    model_key: str,
    test_data: dict[str, str],
    data_dir: str,
    beam_size: int = _BENCHMARK_BEAM_SIZE,
) -> dict:
    """
    Run one model over all test clips and collect hypotheses + timings.

    Parameters
    ----------
    model_key:
        ``"baseline"`` or ``"specialized"``.
    test_data:
        ``{filename: ground_truth}`` mapping from :func:`load_test_data`.
    data_dir:
        Directory containing the ``.wav`` clip files.
    beam_size:
        Beam search width for this benchmark run.

    Returns
    -------
    dict with keys:
        ``model_key``, ``hypotheses``, ``ground_truths``,
        ``inference_times``, ``skipped_clips``.
    """
    model_path = _MODEL_PATHS[model_key]
    print(f"\n[{model_key}] Loading model from: {model_path}")

    transcriber = KannadaTranscriber(model_path)

    hypotheses: list[str] = []
    ground_truths: list[str] = []
    inference_times: list[float] = []
    skipped_clips: list[str] = []

    total_clips = len(test_data)
    print(f"[{model_key}] Running inference on {total_clips} clip(s) "
          f"(beam_size={beam_size}) ...")

    for i, (filename, ground_truth) in enumerate(test_data.items(), start=1):
        clip_path = os.path.join(data_dir, filename)

        if not os.path.exists(clip_path):
            print(f"  [{i}/{total_clips}] SKIP — file not found: {clip_path}")
            skipped_clips.append(filename)
            continue

        hypothesis = transcriber.transcribe(clip_path, beam_size=beam_size)
        elapsed = transcriber.last_inference_time_s

        print(
            f"  [{i}/{total_clips}] {filename} | {elapsed:.2f}s\n"
            f"    REF: {ground_truth}\n"
            f"    HYP: {hypothesis}"
        )

        hypotheses.append(hypothesis)
        ground_truths.append(ground_truth)
        inference_times.append(elapsed)

    if skipped_clips:
        print(f"\n[{model_key}] WARNING: {len(skipped_clips)} clip(s) skipped "
              f"(files not found): {skipped_clips}")

    return {
        "model_key": model_key,
        "hypotheses": hypotheses,
        "ground_truths": ground_truths,
        "inference_times": inference_times,
        "skipped_clips": skipped_clips,
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(
    ground_truths: list[str],
    hypotheses: list[str],
) -> tuple[float, float]:
    """
    Compute Word Error Rate and Character Error Rate.

    Parameters
    ----------
    ground_truths:
        List of reference (human-written) Kannada transcripts.
    hypotheses:
        List of model-generated transcripts (same order).

    Returns
    -------
    tuple[float, float]
        ``(wer_percent, cer_percent)`` rounded to 2 decimal places.
        Values are in the range [0, 100+].

    Notes
    -----
    jiwer.wer() and jiwer.cer() both return a fraction in [0, 1+].
    Multiplied by 100 to give a percentage.
    """
    if not ground_truths:
        return 0.0, 0.0

    wer = jiwer.wer(
        ground_truths,
        hypotheses,
        reference_transform=_WER_TRANSFORM,
        hypothesis_transform=_WER_TRANSFORM,
    )
    cer = jiwer.cer(
        ground_truths,
        hypotheses,
        reference_transform=_CER_TRANSFORM,
        hypothesis_transform=_CER_TRANSFORM,
    )

    return round(wer * 100, 2), round(cer * 100, 2)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_results(results: list[dict], output_path: str) -> None:
    """
    Save benchmark results to a CSV file and print a formatted table.

    Parameters
    ----------
    results:
        List of result dicts, one per model.  Each dict must contain the
        keys produced by :func:`run_model_benchmark` plus computed metrics.
    output_path:
        File path for the output CSV.
    """
    fieldnames = [
        "model_name",
        "wer_percent",
        "cer_percent",
        "avg_inference_time_s",
        "num_clips",
        "total_time_s",
        "beam_size",
    ]

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    rows = []
    for r in results:
        times = r["inference_times"]
        avg_t = round(sum(times) / len(times), 3) if times else 0.0
        total_t = round(sum(times), 3)
        row = {
            "model_name": r["model_key"],
            "wer_percent": r["wer_percent"],
            "cer_percent": r["cer_percent"],
            "avg_inference_time_s": avg_t,
            "num_clips": len(r["inference_times"]),
            "total_time_s": total_t,
            "beam_size": r.get("beam_size", _BENCHMARK_BEAM_SIZE),
        }
        rows.append(row)

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Print table to stdout
    print("\n" + "=" * 70)
    print("  BENCHMARK RESULTS")
    print("=" * 70)
    print(
        tabulate(
            [[r[k] for k in fieldnames] for r in rows],
            headers=fieldnames,
            tablefmt="github",
            floatfmt=".2f",
        )
    )
    print("=" * 70)
    print(f"\n  Results saved to: {output_path}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark baseline vs Kannada-specialized Whisper models.\n"
            "Computes WER and CER on the held-out Kannada test set."
        )
    )
    parser.add_argument(
        "--data-dir",
        default=os.path.join(_PROJECT_ROOT, "data", "stt_test_audio"),
        help="Directory containing .wav clips and transcripts.json "
             "(default: data/stt_test_audio)",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(_PROJECT_ROOT, "benchmark_results.csv"),
        help="Output CSV file path (default: benchmark_results.csv)",
    )
    parser.add_argument(
        "--models",
        choices=[*_MODEL_PATHS.keys(), "all"],
        default="all",
        help="Which model(s) to benchmark (default: all)",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=_BENCHMARK_BEAM_SIZE,
        help=f"Beam size for decoding (default: {_BENCHMARK_BEAM_SIZE}). "
             "Use 1 to benchmark production-latency mode.",
    )
    args = parser.parse_args()

    # --- Load test data ---
    print(f"Loading test data from: {args.data_dir}")
    test_data = load_test_data(args.data_dir)
    print(f"Loaded {len(test_data)} clip(s).\n")

    # --- Run benchmarks ---
    model_keys = (
        list(_MODEL_PATHS.keys()) if args.models == "all" else [args.models]
    )

    all_results = []
    benchmark_start = time.perf_counter()

    for key in model_keys:
        if not os.path.isdir(_MODEL_PATHS[key]):
            print(
                f"[ERROR] Model directory not found for '{key}': {_MODEL_PATHS[key]}\n"
                "        Run: python backend/stt/convert_models.py --model all",
                file=sys.stderr,
            )
            sys.exit(1)

        result = run_model_benchmark(
            key, test_data, args.data_dir, beam_size=args.beam_size
        )
        wer_pct, cer_pct = compute_metrics(
            result["ground_truths"], result["hypotheses"]
        )
        result["wer_percent"] = wer_pct
        result["cer_percent"] = cer_pct
        result["beam_size"] = args.beam_size
        all_results.append(result)

    total_benchmark_time = time.perf_counter() - benchmark_start
    print(f"\nTotal benchmark wall-clock time: {total_benchmark_time:.1f}s")

    # --- Save & display results ---
    save_results(all_results, args.output)


if __name__ == "__main__":
    main()
