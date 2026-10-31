"""
backend/nlu/dataset.py

Data loading, validation, stratified splitting, and PyTorch Dataset
wrapper for the NLU training pipeline.

Design constraints
------------------
- ``split_dataset`` uses sklearn's ``train_test_split`` with
  ``stratify=labels`` at BOTH split stages.  With only 42 examples per
  intent a plain random split would give ~6 examples per intent per
  held-out split — but an unstratified split could easily land at 0 or 1
  for a class by chance, wrecking per-class F1 and the confusion matrix.
- ``seed=42`` is fixed and the same seed is used in ``train.py`` and
  ``evaluate.py``.  This guarantees the test set is identical regardless
  of when or how many times the split function is called — essential for
  a valid baseline vs fine-tuned comparison.
"""

from __future__ import annotations

import json
import os
from collections import Counter

import torch
from torch.utils.data import Dataset
from sklearn.model_selection import train_test_split

from backend.nlu.intents import INTENTS, LABEL2ID, validate_intent


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_dataset(path: str) -> list[dict]:
    """
    Load and validate the NLU training data JSON file.

    Expected format: a flat JSON array of objects, each with ``"text"``
    (non-empty string) and ``"intent"`` (one of the 7 known labels).

    Parameters
    ----------
    path:
        Path to ``nlu_training_data.json``.

    Returns
    -------
    list[dict]
        Validated list of ``{"text": str, "intent": str}`` dicts.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If any entry is malformed or contains an unknown intent label.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Training data not found: '{path}'.\n"
            "Create data/nlu_training_data.json before running training."
        )

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise ValueError(
            f"Expected a JSON array at top level, got {type(raw).__name__}. "
            "Remove any metadata wrapper."
        )

    validated: list[dict] = []
    errors: list[str] = []

    for i, entry in enumerate(raw):
        text = entry.get("text", "")
        intent = entry.get("intent", "")

        if not isinstance(text, str) or not text.strip():
            errors.append(f"  Entry {i}: empty or missing 'text'")
            continue
        if not isinstance(intent, str):
            errors.append(f"  Entry {i}: 'intent' must be a string")
            continue
        try:
            validate_intent(intent)
        except ValueError as e:
            errors.append(f"  Entry {i}: {e}")
            continue

        validated.append({"text": text.strip(), "intent": intent})

    if errors:
        raise ValueError(
            f"Found {len(errors)} invalid entries in '{path}':\n"
            + "\n".join(errors[:10])
            + ("\n  ..." if len(errors) > 10 else "")
        )

    # --- Print distribution as a sanity check ---
    dist = Counter(e["intent"] for e in validated)
    print(f"Loaded {len(validated)} entries from '{path}'")
    print("Per-intent distribution:")
    for intent in INTENTS:
        print(f"  {intent:<25} {dist.get(intent, 0)}")

    return validated


# ---------------------------------------------------------------------------
# Stratified train / val / test split
# ---------------------------------------------------------------------------

def split_dataset(
    data: list[dict],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Split *data* into train / val / test with stratification by intent.

    Both split stages use ``stratify=`` so that every intent is
    proportionally represented in all three splits.  With the default
    294-sample dataset (42 per intent) this yields ~29 train / 6 val /
    6 test examples per intent.

    The same ``seed`` must be used in every script that calls this function
    (``train.py`` and ``evaluate.py``) so that the test set is **identical**
    across runs — guaranteeing a valid baseline vs fine-tuned comparison.

    Parameters
    ----------
    data:
        Full validated dataset from :func:`load_dataset`.
    train_ratio, val_ratio, test_ratio:
        Proportions (must sum to 1.0).
    seed:
        Random seed for reproducibility.  **Do not change this value.**

    Returns
    -------
    tuple[list[dict], list[dict], list[dict]]
        ``(train_data, val_data, test_data)``

    Raises
    ------
    AssertionError
        If any intent is missing from a split (stratification failure).
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-9, \
        "Ratios must sum to 1.0"

    labels = [d["intent"] for d in data]

    # --- Stage 1: train vs (val + test) ---
    remainder_size = val_ratio + test_ratio
    train_data, remainder = train_test_split(
        data,
        test_size=remainder_size,
        random_state=seed,
        stratify=labels,
    )

    # --- Stage 2: val vs test from the remainder ---
    remainder_labels = [d["intent"] for d in remainder]
    # val gets half of remainder, test gets the other half
    val_data, test_data = train_test_split(
        remainder,
        test_size=0.50,
        random_state=seed,
        stratify=remainder_labels,
    )

    # --- Verify all 7 intents appear in every split ---
    for split_name, split in [("train", train_data), ("val", val_data), ("test", test_data)]:
        split_intents = set(d["intent"] for d in split)
        missing = set(INTENTS) - split_intents
        assert not missing, (
            f"Stratification failed: intents {missing} missing from {split_name} split. "
            "Increase dataset size or check class balance."
        )

    # --- Print split statistics ---
    print(
        f"\nSplit sizes (seed={seed}):"
        f"\n  train : {len(train_data)} ({len(train_data)/len(data)*100:.1f}%)"
        f"\n  val   : {len(val_data)} ({len(val_data)/len(data)*100:.1f}%)"
        f"\n  test  : {len(test_data)} ({len(test_data)/len(data)*100:.1f}%)"
    )
    print("\nPer-intent counts per split:")
    train_dist = Counter(d["intent"] for d in train_data)
    val_dist   = Counter(d["intent"] for d in val_data)
    test_dist  = Counter(d["intent"] for d in test_data)
    print(f"  {'intent':<25} {'train':>5} {'val':>5} {'test':>5}")
    print(f"  {'-'*25} {'-'*5} {'-'*5} {'-'*5}")
    for intent in INTENTS:
        print(
            f"  {intent:<25} {train_dist[intent]:>5}"
            f" {val_dist[intent]:>5} {test_dist[intent]:>5}"
        )

    return train_data, val_data, test_data


# ---------------------------------------------------------------------------
# PyTorch Dataset wrapper
# ---------------------------------------------------------------------------

class BankingIntentDataset(Dataset):
    """
    PyTorch Dataset wrapping the NLU banking intent data.

    Each item is tokenized on-the-fly and returns a dict of tensors
    suitable for direct use with a HuggingFace sequence classification model.

    Parameters
    ----------
    data:
        List of ``{"text": str, "intent": str}`` dicts (from a split).
    tokenizer:
        HuggingFace tokenizer (e.g. DistilBertTokenizerFast).
    max_length:
        Maximum sequence length for tokenization.  128 is sufficient
        for banking queries (<30 words) and keeps inference fast.
    """

    def __init__(
        self,
        data: list[dict],
        tokenizer,
        max_length: int = 128,
    ) -> None:
        self._data = data
        self._tokenizer = tokenizer
        self._max_length = max_length

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        entry = self._data[idx]
        text   = entry["text"]
        label  = LABEL2ID[entry["intent"]]

        encoding = self._tokenizer(
            text,
            max_length=self._max_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

        return {
            "input_ids":      encoding["input_ids"].squeeze(0),       # (max_length,)
            "attention_mask": encoding["attention_mask"].squeeze(0),   # (max_length,)
            "labels":         torch.tensor(label, dtype=torch.long),   # scalar
        }
