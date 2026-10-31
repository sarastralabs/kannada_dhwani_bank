"""
backend/nlu/distilbert_classifier.py

Inference wrapper for the fine-tuned DistilBERT intent classifier.

This file is the PRODUCTION path — it only loads and runs the saved
checkpoint.  Training dependencies (DataLoader, optimizer, scheduler)
are NOT imported here; they live exclusively in train.py.

Usage
-----
    from backend.nlu.distilbert_classifier import DistilBERTClassifier

    clf = DistilBERTClassifier("models/nlu-distilbert")
    label, confidence = clf.classify("What is my account balance?")
    # ("check_balance", 0.9873)

    # Batch inference (more efficient for evaluate.py)
    results = clf.classify_batch([
        "I want to withdraw money",
        "Apply for a home loan",
    ])
    # [("withdraw_money", 0.994), ("apply_loan", 0.981)]
"""

from __future__ import annotations

import os

import torch
import torch.nn.functional as F
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from backend.nlu.intents import ID2LABEL, LABEL2ID, NUM_CLASSES


def _detect_device() -> str:
    """Return 'cuda' if a GPU is available, else 'cpu'. Same pattern as STT and Translation."""
    return "cuda" if torch.cuda.is_available() else "cpu"


class DistilBERTClassifier:
    """
    Run inference with a fine-tuned DistilBERT intent classifier.

    Loads a checkpoint saved by ``train.py`` via
    ``model.save_pretrained()`` and ``tokenizer.save_pretrained()``.

    Parameters
    ----------
    model_dir:
        Path to the saved checkpoint directory (e.g. ``"models/nlu-distilbert"``).
        Must contain ``config.json``, ``model.safetensors`` (or ``pytorch_model.bin``),
        and a ``tokenizer_config.json``.
    device:
        ``"cpu"`` or ``"cuda"``.  Auto-detected if ``None``.

    Attributes
    ----------
    last_inference_time_s : float
        Wall-clock seconds for the most recent ``classify()`` call.

    Raises
    ------
    FileNotFoundError
        If ``model_dir`` does not exist, with a message pointing to ``train.py``.
    """

    _MAX_LENGTH: int = 128   # sufficient for banking queries (<30 words)

    def __init__(
        self,
        model_dir: str,
        device: str | None = None,
    ) -> None:
        if not os.path.isdir(model_dir):
            raise FileNotFoundError(
                f"NLU model checkpoint not found: '{model_dir}'.\n"
                "Fine-tune the model first:\n"
                "    python backend/nlu/train.py"
            )

        self._model_dir = model_dir
        self._device    = device if device is not None else _detect_device()
        self.last_inference_time_s: float = 0.0

        self._tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self._model = (
            AutoModelForSequenceClassification
            .from_pretrained(model_dir)
            .to(self._device)
        )
        self._model.eval()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def classify(self, text: str) -> tuple[str, float]:
        """
        Classify a single English text string.

        Parameters
        ----------
        text:
            English banking query (output of ``translate_kn_to_en()``).

        Returns
        -------
        tuple[str, float]
            ``(intent_label, confidence)`` where confidence is a
            probability in (0, 1].  Never returns ``None``.
        """
        import time  # noqa: PLC0415 — local import keeps top-level clean
        t_start = time.perf_counter()

        results = self.classify_batch([text])

        self.last_inference_time_s = time.perf_counter() - t_start
        return results[0]

    def classify_batch(
        self,
        texts: list[str],
    ) -> list[tuple[str, float]]:
        """
        Classify a batch of texts in a single forward pass.

        More efficient than calling :meth:`classify` in a loop when
        evaluating many examples (e.g. in ``evaluate.py``).

        Parameters
        ----------
        texts:
            List of English strings to classify.

        Returns
        -------
        list[tuple[str, float]]
            One ``(intent_label, confidence)`` pair per input string,
            in the same order as *texts*.
        """
        if not texts:
            return []

        encoding = self._tokenizer(
            texts,
            max_length=self._MAX_LENGTH,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        # Move all tensor values to the target device
        encoding = {k: v.to(self._device) for k, v in encoding.items()}

        with torch.inference_mode():
            logits = self._model(**encoding).logits  # (batch, num_classes)

        probs   = F.softmax(logits, dim=-1)          # (batch, num_classes)
        pred_ids    = probs.argmax(dim=-1).tolist()   # list[int]
        confidences = probs.max(dim=-1).values.tolist()  # list[float]

        return [
            (ID2LABEL[pred_id], round(float(conf), 4))
            for pred_id, conf in zip(pred_ids, confidences)
        ]

    def classify_top_k(self, text: str, k: int = 2) -> list[tuple[str, float]]:
        """Return top-k (intent, confidence) pairs for disambiguation."""
        if not text.strip():
            return []

        encoding = self._tokenizer(
            text,
            max_length=self._MAX_LENGTH,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        encoding = {key: val.to(self._device) for key, val in encoding.items()}

        with torch.inference_mode():
            logits = self._model(**encoding).logits

        probs = F.softmax(logits, dim=-1)[0]
        k = min(k, NUM_CLASSES)
        topk = torch.topk(probs, k)
        out: list[tuple[str, float]] = []
        for idx in topk.indices.tolist():
            label = ID2LABEL[int(idx)]
            out.append((label, round(float(probs[int(idx)].item()), 4)))
        return out
