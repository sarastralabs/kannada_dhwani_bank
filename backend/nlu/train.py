"""
backend/nlu/train.py

Fine-tune distilbert-base-uncased on the 301-sentence banking intent dataset.

Run once on the GPU dev machine.  The saved checkpoint is CPU-loadable
(standard HuggingFace safetensors format — no GPU lock).

Usage
-----
    python backend/nlu/train.py                          # defaults
    python backend/nlu/train.py --epochs 15 --lr 3e-5   # custom

Output
------
    models/nlu-distilbert/   — best checkpoint by val accuracy
        config.json
        model.safetensors
        tokenizer_config.json  (+ supporting tokenizer files)
        training_log.csv       — epoch-by-epoch loss/accuracy record
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import time

import numpy as np
import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from backend.nlu.dataset import BankingIntentDataset, load_dataset, split_dataset
from backend.nlu.intents import ID2LABEL, LABEL2ID, NUM_CLASSES


# ---------------------------------------------------------------------------
# Training defaults — all overridable via argparse
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "base_model":  "distilbert-base-uncased",
    "data":        "data/nlu_training_data.json",
    "output":      "models/nlu-distilbert",
    "epochs":      10,
    "batch_size":  16,
    "lr":          2e-5,
    "max_length":  128,
    "warmup_frac": 0.10,   # 10% of total steps used for LR warmup
    "patience":    3,      # early-stop after this many non-improving val epochs
    "weight_decay": 0.01,
    "seed":        42,     # fixed for reproducible training — see set_seed()
}

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def set_seed(seed: int) -> None:
    """
    Fix all random seeds so re-running training gives identical results.

    Covers Python's random, NumPy, PyTorch CPU, and PyTorch CUDA.
    Also disables CuDNN non-deterministic algorithms.

    Note: the data split uses the same seed (42 by default) via
    split_dataset(seed=seed), so both the train/val/test assignment
    AND the weight initialisation are reproducible.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def evaluate_accuracy(
    model: AutoModelForSequenceClassification,
    loader: DataLoader,
    device: str,
) -> float:
    """Compute classification accuracy on *loader* without gradient tracking."""
    model.eval()
    correct = total = 0
    with torch.inference_mode():
        for batch in loader:
            input_ids      = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels         = batch["labels"].to(device)
            logits = model(input_ids=input_ids, attention_mask=attention_mask).logits
            preds  = logits.argmax(dim=-1)
            correct += (preds == labels).sum().item()
            total   += labels.size(0)
    return correct / total if total > 0 else 0.0


# ---------------------------------------------------------------------------
# Core training loop
# ---------------------------------------------------------------------------

def train(args: argparse.Namespace) -> None:
    """
    Fine-tune DistilBERT.  Key design answers (see pre-Task-6 checklist):

    1. EPOCHS + EARLY STOPPING
       Max epochs = args.epochs (default 10).
       Early stopping: if val accuracy does not improve for `patience`
       consecutive epochs (default 3), training stops immediately.
       Best checkpoint is saved whenever val accuracy improves —
       NOT just at the final epoch.

    2. BATCH SIZE + LEARNING RATE
       batch_size=16, lr=2e-5 — standard DistilBERT fine-tuning defaults.
       With 205 training examples at batch_size=16 → 13 steps/epoch.
       10 epochs = 130 total steps, 13 warmup steps (10%).

    3. CHECKPOINTING
       model.save_pretrained() is called ONLY when val accuracy improves.
       The saved checkpoint is always the best-seen, never the last epoch.

    4. SEED
       set_seed(args.seed) fixes Python/NumPy/PyTorch/CUDA seeds before
       any weight initialisation or data shuffling.  split_dataset() also
       uses args.seed so data split AND training are both reproducible.

    5. CPU-LOADABLE OUTPUT
       model.save_pretrained() writes standard HuggingFace safetensors.
       No GPU-specific serialisation.  Loading on CPU:
           AutoModelForSequenceClassification.from_pretrained("models/nlu-distilbert")
       works identically on CPU-only hardware — device placement happens
       at load time via .to(device), not baked into the checkpoint.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device : {device}")
    print(f"Seed   : {args.seed}")

    # --- 4. Fix ALL random seeds before anything else ---
    set_seed(args.seed)

    # --- Load and split data (same seed → same test split as evaluate.py) ---
    output_dir = os.path.join(_PROJECT_ROOT, args.output) if not os.path.isabs(args.output) else args.output
    data_path  = os.path.join(_PROJECT_ROOT, args.data)   if not os.path.isabs(args.data)   else args.data

    data = load_dataset(data_path)
    train_data, val_data, _ = split_dataset(data, seed=args.seed)
    # test_data deliberately ignored here — evaluation happens in evaluate.py

    # --- Tokenizer + model ---
    print(f"\nLoading base model: {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=NUM_CLASSES,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    ).to(device)

    # --- DataLoaders ---
    train_ds = BankingIntentDataset(train_data, tokenizer, max_length=args.max_length)
    val_ds   = BankingIntentDataset(val_data,   tokenizer, max_length=args.max_length)

    # shuffle=True for training; generator seeds DataLoader's own RNG
    g = torch.Generator()
    g.manual_seed(args.seed)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,  generator=g)
    val_loader   = DataLoader(val_ds,   batch_size=args.batch_size, shuffle=False)

    # --- Optimiser + scheduler ---
    # 2. lr=2e-5, weight_decay=0.01 — standard DistilBERT fine-tuning
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    total_steps  = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * args.warmup_frac)
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    print(f"\nTraining config:")
    print(f"  train samples : {len(train_data)}")
    print(f"  val samples   : {len(val_data)}")
    print(f"  batch size    : {args.batch_size}")
    print(f"  steps/epoch   : {len(train_loader)}")
    print(f"  max epochs    : {args.epochs}")
    print(f"  warmup steps  : {warmup_steps}/{total_steps}")
    print(f"  learning rate : {args.lr}")
    print(f"  early stop    : patience={args.patience} epochs on val accuracy")
    print(f"  output dir    : {output_dir}\n")

    os.makedirs(output_dir, exist_ok=True)

    # Warn if a checkpoint already exists — avoids silently overwriting a good model
    existing_checkpoint = os.path.join(output_dir, "model.safetensors")
    if os.path.isfile(existing_checkpoint):
        print(f"\n  [WARN] Existing checkpoint found at: {output_dir}")
        print("         This run will overwrite it if val accuracy improves.")
        print("         To keep the old model, back it up first.\n")

    # --- Training loop ---
    # 1. EPOCHS + EARLY STOPPING
    best_val_acc     = -1.0
    patience_counter = 0
    log_rows         = []
    t_train_start    = time.perf_counter()

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_loss = 0.0
        t_epoch_start = time.perf_counter()

        for batch in train_loader:
            input_ids      = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels         = batch["labels"].to(device)

            optimizer.zero_grad()
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            loss = outputs.loss
            loss.backward()

            # Gradient clipping — prevents occasional large updates on small data
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()
            scheduler.step()

            epoch_loss += loss.item()

        avg_loss = epoch_loss / len(train_loader)
        val_acc  = evaluate_accuracy(model, val_loader, device)
        elapsed  = time.perf_counter() - t_epoch_start

        # 3. CHECKPOINTING — save BEST, not last
        improved = val_acc > best_val_acc
        if improved:
            best_val_acc     = val_acc
            patience_counter = 0
            model.save_pretrained(output_dir)
            tokenizer.save_pretrained(output_dir)
            saved_marker = " <- best saved"
        else:
            patience_counter += 1
            saved_marker = f" (patience {patience_counter}/{args.patience})"

        print(
            f"Epoch {epoch:02d}/{args.epochs}"
            f"  loss={avg_loss:.4f}"
            f"  val_acc={val_acc:.4f}"
            f"  {elapsed:.1f}s"
            f"{saved_marker}"
        )

        log_rows.append({
            "epoch": epoch,
            "train_loss": round(avg_loss, 4),
            "val_accuracy": round(val_acc, 4),
            "best_val_accuracy": round(best_val_acc, 4),
            "elapsed_s": round(elapsed, 1),
            "checkpoint_saved": improved,
        })

        # 1. EARLY STOPPING
        if patience_counter >= args.patience:
            print(f"\nEarly stopping triggered after epoch {epoch} "
                  f"(no improvement for {args.patience} epochs).")
            break

    total_time = time.perf_counter() - t_train_start
    print(f"\nTraining complete.")
    print(f"  Best val accuracy : {best_val_acc:.4f}")
    print(f"  Total time        : {total_time:.1f}s")
    print(f"  Checkpoint saved  : {output_dir}")

    # --- Save epoch log ---
    log_path = os.path.join(output_dir, "training_log.csv")
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=log_rows[0].keys())
        writer.writeheader()
        writer.writerows(log_rows)
    print(f"  Training log      : {log_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fine-tune DistilBERT for banking intent classification."
    )
    parser.add_argument("--base-model",   default=_DEFAULTS["base_model"])
    parser.add_argument("--data",         default=_DEFAULTS["data"])
    parser.add_argument("--output",       default=_DEFAULTS["output"])
    parser.add_argument("--epochs",       type=int,   default=_DEFAULTS["epochs"])
    parser.add_argument("--batch-size",   type=int,   default=_DEFAULTS["batch_size"])
    parser.add_argument("--lr",           type=float, default=_DEFAULTS["lr"])
    parser.add_argument("--max-length",   type=int,   default=_DEFAULTS["max_length"])
    parser.add_argument("--patience",     type=int,   default=_DEFAULTS["patience"])
    parser.add_argument("--weight-decay", type=float, default=_DEFAULTS["weight_decay"])
    parser.add_argument("--warmup-frac",  type=float, default=_DEFAULTS["warmup_frac"])
    parser.add_argument("--seed",         type=int,   default=_DEFAULTS["seed"])
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
