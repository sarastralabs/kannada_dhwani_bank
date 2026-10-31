"""
backend/nlu/evaluate.py

Evaluate both classifiers (keyword baseline + fine-tuned DistilBERT) on
the identical held-out test split and emit a comparison table.

Both classifiers are evaluated on the SAME 45-sentence test split
produced by split_dataset(seed=42) — the same seed used in train.py.
This guarantees a fair, uncontaminated comparison.

Usage
-----
    python -m backend.nlu.evaluate

Output (all in --output-dir, default: models/nlu-distilbert/)
------
    nlu_baseline_results.csv          — per-intent metrics, keyword baseline
    nlu_finetuned_results.csv         — per-intent metrics, DistilBERT
    nlu_baseline_confusion_matrix.png
    nlu_finetuned_confusion_matrix.png
    nlu_comparison_results.csv        — side-by-side accuracy/F1 summary
"""

from __future__ import annotations

import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")   # non-interactive backend — safe on all platforms
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix
from tabulate import tabulate

from backend.nlu.dataset import load_dataset, split_dataset
from backend.nlu.distilbert_classifier import DistilBERTClassifier
from backend.nlu.intents import INTENTS
from backend.nlu.keyword_classifier import KeywordClassifier

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_DEFAULT_OUTPUT = os.path.join(_PROJECT_ROOT, "models", "nlu-distilbert")
_DEFAULT_DATA   = os.path.join(_PROJECT_ROOT, "data", "nlu_training_data.json")
_DEFAULT_MODEL  = _DEFAULT_OUTPUT


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------

def evaluate_model(classifier, test_data: list[dict]) -> dict:
    """
    Run *classifier* over *test_data* and return metrics dict.

    Parameters
    ----------
    classifier:
        Any object with a ``.classify(text) -> (label, confidence)`` method.
    test_data:
        List of ``{"text": str, "intent": str}`` dicts (held-out test split).

    Returns
    -------
    dict with keys: true_labels, pred_labels, accuracy,
                    per_class_report (dict), macro_f1, weighted_f1
    """
    true_labels, pred_labels = [], []
    for entry in test_data:
        pred, _ = classifier.classify(entry["text"])
        true_labels.append(entry["intent"])
        pred_labels.append(pred)

    report = classification_report(
        true_labels, pred_labels,
        labels=INTENTS,
        target_names=INTENTS,
        digits=3,
        zero_division=0,
        output_dict=True,
    )
    accuracy    = report["accuracy"]
    macro_f1    = report["macro avg"]["f1-score"]
    weighted_f1 = report["weighted avg"]["f1-score"]

    return {
        "true_labels":      true_labels,
        "pred_labels":      pred_labels,
        "accuracy":         accuracy,
        "per_class_report": report,
        "macro_f1":         macro_f1,
        "weighted_f1":      weighted_f1,
    }


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def save_per_class_csv(metrics: dict, model_name: str, output_dir: str) -> str:
    """Write per-intent metrics CSV.  Returns the file path."""
    report = metrics["per_class_report"]
    path   = os.path.join(output_dir, f"nlu_{model_name}_results.csv")
    fieldnames = ["intent", "precision", "recall", "f1", "support"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for intent in INTENTS:
            r = report[intent]
            writer.writerow({
                "intent":    intent,
                "precision": round(r["precision"],  3),
                "recall":    round(r["recall"],     3),
                "f1":        round(r["f1-score"],   3),
                "support":   int(r["support"]),
            })
        # Summary rows
        writer.writerow({
            "intent": "ACCURACY", "precision": "", "recall": "",
            "f1": round(metrics["accuracy"], 3),
            "support": sum(r["support"] for r in
                          [report[i] for i in INTENTS if isinstance(report[i], dict)]),
        })
        for avg_key, row_label in [("macro avg", "MACRO_AVG"),
                                   ("weighted avg", "WEIGHTED_AVG")]:
            r = report[avg_key]
            writer.writerow({
                "intent":    row_label,
                "precision": round(r["precision"],  3),
                "recall":    round(r["recall"],     3),
                "f1":        round(r["f1-score"],   3),
                "support":   int(r["support"]),
            })
    return path


def save_confusion_matrix(
    true_labels: list[str],
    pred_labels: list[str],
    model_name: str,
    accuracy: float,
    n_test: int,
    output_dir: str,
) -> str:
    """Save confusion matrix as a PNG heatmap.  Returns the file path."""
    cm = confusion_matrix(true_labels, pred_labels, labels=INTENTS)
    short = [i.replace("_", "\n") for i in INTENTS]

    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=short, yticklabels=short,
        ax=ax, linewidths=0.5,
    )
    ax.set_xlabel("Predicted", fontsize=12)
    ax.set_ylabel("True",      fontsize=12)
    title_name = "Keyword Baseline" if model_name == "baseline" else "Fine-tuned DistilBERT"
    ax.set_title(
        f"{title_name} — Confusion Matrix\n"
        f"Accuracy {round(accuracy * n_test)}/{n_test} = {accuracy:.1%}  "
        f"(test split, seed=42)",
        fontsize=11,
    )
    plt.tight_layout()
    path = os.path.join(output_dir, f"nlu_{model_name}_confusion_matrix.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def save_comparison_csv(
    baseline_metrics: dict,
    finetuned_metrics: dict,
    output_dir: str,
) -> str:
    """Write the side-by-side comparison CSV and print to stdout."""
    path = os.path.join(output_dir, "nlu_comparison_results.csv")
    rows = [
        {
            "model":        "keyword_baseline",
            "accuracy":     round(baseline_metrics["accuracy"],    3),
            "macro_f1":     round(baseline_metrics["macro_f1"],    3),
            "weighted_f1":  round(baseline_metrics["weighted_f1"], 3),
        },
        {
            "model":        "distilbert_finetuned",
            "accuracy":     round(finetuned_metrics["accuracy"],    3),
            "macro_f1":     round(finetuned_metrics["macro_f1"],    3),
            "weighted_f1":  round(finetuned_metrics["weighted_f1"], 3),
        },
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["model","accuracy","macro_f1","weighted_f1"])
        writer.writeheader()
        writer.writerows(rows)

    # Stdout table
    print("\n" + "=" * 62)
    print("  NLU COMPARISON — keyword baseline vs fine-tuned DistilBERT")
    print("  Test split: seed=42, 45 sentences, 7 intents")
    print("=" * 62)
    print(tabulate(
        [[r["model"], f"{r['accuracy']:.1%}", f"{r['macro_f1']:.3f}", f"{r['weighted_f1']:.3f}"]
         for r in rows],
        headers=["model", "accuracy", "macro_f1", "weighted_f1"],
        tablefmt="github",
    ))
    print("=" * 62)
    print(f"\n  Saved: {path}\n")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate keyword baseline and fine-tuned DistilBERT on the NLU test split."
    )
    parser.add_argument("--data",       default=_DEFAULT_DATA)
    parser.add_argument("--model-dir",  default=_DEFAULT_MODEL,
                        help="Path to fine-tuned DistilBERT checkpoint")
    parser.add_argument("--output-dir", default=_DEFAULT_OUTPUT)
    parser.add_argument("--seed",       type=int, default=42)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # ── Load the SAME test split as train.py ─────────────────────────────────
    print(f"Loading data from: {args.data}")
    data = load_dataset(args.data)
    _, _, test_data = split_dataset(data, seed=args.seed)
    n_test = len(test_data)
    print(f"Test split: {n_test} sentences (seed={args.seed})\n")

    # ── 1. Keyword baseline ───────────────────────────────────────────────────
    print("Evaluating keyword baseline ...")
    baseline_clf     = KeywordClassifier()
    baseline_metrics = evaluate_model(baseline_clf, test_data)

    baseline_csv = save_per_class_csv(baseline_metrics, "baseline", args.output_dir)
    baseline_png = save_confusion_matrix(
        baseline_metrics["true_labels"], baseline_metrics["pred_labels"],
        "baseline", baseline_metrics["accuracy"], n_test, args.output_dir,
    )
    print(f"  Accuracy : {baseline_metrics['accuracy']:.1%}")
    print(f"  Macro F1 : {baseline_metrics['macro_f1']:.3f}")
    print(f"  CSV      : {baseline_csv}")
    print(f"  PNG      : {baseline_png}")

    # ── 2. Fine-tuned DistilBERT ──────────────────────────────────────────────
    print("\nEvaluating fine-tuned DistilBERT ...")
    finetuned_clf     = DistilBERTClassifier(args.model_dir)
    finetuned_metrics = evaluate_model(finetuned_clf, test_data)

    finetuned_csv = save_per_class_csv(finetuned_metrics, "finetuned", args.output_dir)
    finetuned_png = save_confusion_matrix(
        finetuned_metrics["true_labels"], finetuned_metrics["pred_labels"],
        "finetuned", finetuned_metrics["accuracy"], n_test, args.output_dir,
    )

    print(f"  Accuracy : {finetuned_metrics['accuracy']:.1%}")
    print(f"  Macro F1 : {finetuned_metrics['macro_f1']:.3f}")
    print(f"  CSV      : {finetuned_csv}")
    print(f"  PNG      : {finetuned_png}")

    # ── 3. Per-intent detail for fine-tuned model ─────────────────────────────
    print("\nFine-tuned DistilBERT — per-intent detail:")
    report = finetuned_metrics["per_class_report"]
    rows = [[i,
             f"{report[i]['precision']:.3f}",
             f"{report[i]['recall']:.3f}",
             f"{report[i]['f1-score']:.3f}",
             int(report[i]['support'])]
            for i in INTENTS]
    print(tabulate(rows, headers=["intent","precision","recall","f1","support"], tablefmt="github"))

    # ── 4. Comparison table ───────────────────────────────────────────────────
    save_comparison_csv(baseline_metrics, finetuned_metrics, args.output_dir)

    # ── 5. Misclassifications from fine-tuned model ───────────────────────────
    misses = [
        (true, pred, text)
        for true, pred, text in zip(
            finetuned_metrics["true_labels"],
            finetuned_metrics["pred_labels"],
            [e["text"] for e in test_data],
        )
        if true != pred
    ]
    print(f"Fine-tuned misclassifications: {len(misses)}")
    for true, pred, text in sorted(misses, key=lambda x: x[0]):
        print(f"  TRUE={true:<25} PRED={pred:<25} \"{text}\"")


if __name__ == "__main__":
    main()
