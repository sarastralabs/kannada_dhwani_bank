"""
backend/translation/benchmark.py

BLEU / chrF2++ benchmark for the Kannada→English translation module.

Loads the 15 ground-truth Kannada banking phrases (from the STT test set),
translates each through the IndicTrans2 indic-en model, and compares the
output against manually-written English reference translations using
sacrebleu.

Using ground-truth Kannada text (not STT output) as the source deliberately
isolates translation quality from STT errors, giving a clean measure of
Module 2 performance.

Usage
-----
    python backend/translation/benchmark.py

    # Custom paths
    python backend/translation/benchmark.py \\
        --kannada-data  data/stt_test_audio/transcripts.json \\
        --reference-data data/translation_test/reference_translations.json \\
        --output translation_benchmark_results.csv

Output CSV columns
------------------
    phrase_id, kannada_source, reference_translation,
    model_translation, bleu_score, chrf_score

A SUMMARY row is appended at the end with averages across all phrases.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time

import sacrebleu
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Project root — allows running from any working directory
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

_DEFAULT_KANNADA  = os.path.join(_PROJECT_ROOT, "data", "stt_test_audio", "transcripts.json")
_DEFAULT_REFS     = os.path.join(_PROJECT_ROOT, "data", "translation_test", "reference_translations.json")
_DEFAULT_OUTPUT   = os.path.join(_PROJECT_ROOT, "translation_benchmark_results.csv")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_test_data(
    kannada_path: str,
    reference_path: str,
) -> list[tuple[str, str, str]]:
    """
    Load and zip the Kannada source phrases with their English references.

    Parameters
    ----------
    kannada_path:
        Path to ``transcripts.json``  {filename: kannada_text}
    reference_path:
        Path to ``reference_translations.json``  {filename: english_text}

    Returns
    -------
    list of (phrase_id, kannada_source, english_reference) tuples,
    sorted by phrase_id for reproducible ordering.

    Raises
    ------
    FileNotFoundError
        If either JSON file is missing.
    ValueError
        If the key sets don't match.
    """
    for path in (kannada_path, reference_path):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Required data file not found: '{path}'\n"
                "Run Task 5 setup to create reference_translations.json."
            )

    with open(kannada_path,  encoding="utf-8") as f:
        kannada_dict: dict[str, str] = json.load(f)
    with open(reference_path, encoding="utf-8") as f:
        reference_dict: dict[str, str] = json.load(f)

    missing  = set(kannada_dict) - set(reference_dict)
    extra    = set(reference_dict) - set(kannada_dict)
    if missing:
        raise ValueError(f"Keys in transcripts.json missing from reference file: {sorted(missing)}")
    if extra:
        raise ValueError(f"Extra keys in reference file not in transcripts.json: {sorted(extra)}")

    return [
        (key, kannada_dict[key], reference_dict[key])
        for key in sorted(kannada_dict.keys())
    ]


# ---------------------------------------------------------------------------
# Per-sentence metrics
# ---------------------------------------------------------------------------

def sentence_bleu(hypothesis: str, reference: str) -> float:
    """
    Compute sentence-level BLEU (0–100) using sacrebleu.

    sacrebleu's ``sentence_bleu`` applies smoothing (method 1) to handle
    the zero n-gram issue on very short sentences.
    """
    result = sacrebleu.sentence_bleu(hypothesis, [reference])
    return round(result.score, 2)


def sentence_chrf(hypothesis: str, reference: str) -> float:
    """
    Compute sentence-level chrF2++ (0–100) using sacrebleu.

    chrF2++ uses character n-grams and is more robust than BLEU for
    agglutinative-adjacent translations and valid paraphrases.
    """
    result = sacrebleu.sentence_chrf(hypothesis, [reference])
    return round(result.score, 2)


# ---------------------------------------------------------------------------
# Corpus-level metrics
# ---------------------------------------------------------------------------

def corpus_metrics(
    hypotheses: list[str],
    references: list[str],
) -> tuple[float, float]:
    """
    Compute corpus-level BLEU and chrF2++ across all sentences.

    Corpus BLEU is more statistically meaningful than averaging sentence
    BLEUs — use this for the project report headline number.

    Returns
    -------
    tuple[float, float]
        (corpus_bleu, corpus_chrf) both rounded to 2 decimal places.
    """
    bleu = sacrebleu.corpus_bleu(
        hypotheses,
        [references],
        tokenize="flores200",   # correct tokenizer for Indic-adjacent scripts
    )
    chrf = sacrebleu.corpus_chrf(hypotheses, [references])
    return round(bleu.score, 2), round(chrf.score, 2)


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(
    test_data: list[tuple[str, str, str]],
) -> list[dict]:
    """
    Translate all Kannada phrases and collect per-phrase results.

    Parameters
    ----------
    test_data:
        List of (phrase_id, kannada_source, english_reference) tuples.

    Returns
    -------
    List of result dicts, one per phrase.
    """
    # Import here so the module can be imported for unit testing without
    # triggering a model load.
    from backend.translation import translate_kn_to_en  # noqa: PLC0415

    results = []
    total_phrases = len(test_data)

    print(f"\nTranslating {total_phrases} phrases using indic-en-dist-200M ...")
    print("(First call downloads and caches the model if not already present)\n")

    for i, (phrase_id, kannada, reference) in enumerate(test_data, start=1):
        t_start = time.perf_counter()
        translation = translate_kn_to_en(kannada)
        elapsed = round(time.perf_counter() - t_start, 3)

        bleu  = sentence_bleu(translation, reference)
        chrf  = sentence_chrf(translation, reference)

        results.append({
            "phrase_id":           phrase_id,
            "kannada_source":      kannada,
            "reference_translation": reference,
            "model_translation":   translation,
            "bleu_score":          bleu,
            "chrf_score":          chrf,
            "inference_time_s":    elapsed,
        })

        print(
            f"  [{i:02d}/{total_phrases}] {phrase_id}\n"
            f"    KN : {kannada}\n"
            f"    REF: {reference}\n"
            f"    HYP: {translation}\n"
            f"    BLEU={bleu:.1f}  chrF2++={chrf:.1f}  ({elapsed:.2f}s)\n"
        )

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_results(results: list[dict], output_path: str) -> None:
    """
    Save per-phrase results to CSV and print a summary table.

    The CSV contains one row per phrase plus a SUMMARY row at the end
    with corpus-level BLEU, average chrF2++, and average inference time.
    """
    hypotheses = [r["model_translation"]   for r in results]
    references = [r["reference_translation"] for r in results]
    inf_times  = [r["inference_time_s"]     for r in results]

    corpus_bleu, corpus_chrf = corpus_metrics(hypotheses, references)
    avg_time   = round(sum(inf_times) / len(inf_times), 3)
    total_time = round(sum(inf_times), 3)

    # ── CSV output ────────────────────────────────────────────────────────────
    fieldnames = [
        "phrase_id", "kannada_source", "reference_translation",
        "model_translation", "bleu_score", "chrf_score", "inference_time_s",
    ]

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r[k] for k in fieldnames})
        # Summary row
        writer.writerow({
            "phrase_id":              "SUMMARY",
            "kannada_source":         f"{len(results)} phrases",
            "reference_translation":  "corpus-level metrics",
            "model_translation":      "",
            "bleu_score":             corpus_bleu,
            "chrf_score":             corpus_chrf,
            "inference_time_s":       avg_time,
        })

    # ── Stdout summary table ──────────────────────────────────────────────────
    table_rows = [
        [
            r["phrase_id"],
            r["bleu_score"],
            r["chrf_score"],
            r["inference_time_s"],
        ]
        for r in results
    ]

    print("\n" + "=" * 72)
    print("  PER-PHRASE RESULTS")
    print("=" * 72)
    print(tabulate(
        table_rows,
        headers=["phrase_id", "BLEU", "chrF2++", "time_s"],
        tablefmt="github",
        floatfmt=".2f",
    ))

    print("\n" + "=" * 72)
    print("  SUMMARY  (corpus-level, IndicTrans2 indic-en-dist-200M)")
    print("=" * 72)
    summary_table = [
        ["Corpus BLEU",     f"{corpus_bleu:.2f}",  "(primary metric for MT)"],
        ["Corpus chrF2++",  f"{corpus_chrf:.2f}",  "(more robust; lead with this)"],
        ["Avg time/phrase", f"{avg_time:.3f} s",   ""],
        ["Total time",      f"{total_time:.1f} s", f"({len(results)} phrases)"],
    ]
    print(tabulate(summary_table, tablefmt="plain"))
    print("=" * 72)
    print(f"\n  Results saved to: {output_path}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark IndicTrans2 Kannada→English translation quality.\n"
            "Uses ground-truth Kannada text (not STT output) as source,\n"
            "isolating translation quality from STT errors."
        )
    )
    parser.add_argument(
        "--kannada-data",
        default=_DEFAULT_KANNADA,
        help=f"Path to Kannada source JSON (default: {_DEFAULT_KANNADA})",
    )
    parser.add_argument(
        "--reference-data",
        default=_DEFAULT_REFS,
        help=f"Path to English reference JSON (default: {_DEFAULT_REFS})",
    )
    parser.add_argument(
        "--output",
        default=_DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {_DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    print(f"Kannada source  : {args.kannada_data}")
    print(f"References      : {args.reference_data}")
    print(f"Output CSV      : {args.output}")

    test_data = load_test_data(args.kannada_data, args.reference_data)
    print(f"Loaded {len(test_data)} phrase pairs.")

    results = run_benchmark(test_data)
    save_results(results, args.output)


if __name__ == "__main__":
    main()
