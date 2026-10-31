"""Shared Parler load helpers (used by run_parler_tts_worker.py and test scripts)."""

from __future__ import annotations

import os
import re


def resolve_parler_dtype(device: str):
    """
    Choose torch dtype for Parler weights.

    BANK_PARLER_DTYPE:
      auto  — fp16 on CUDA, fp32 on CPU (default)
      fp16  — half precision (less VRAM, faster on GPU)
      fp32  — full precision
    """
    import torch

    raw = os.environ.get("BANK_PARLER_DTYPE", "auto").strip().lower()
    if raw in {"fp32", "float32", "32"}:
        return torch.float32
    if raw in {"fp16", "float16", "16", "half"}:
        return torch.float16
    return torch.float16 if str(device).startswith("cuda") else torch.float32


def dtype_label(dtype) -> str:
    import torch

    if dtype == torch.float16:
        return "fp16"
    if dtype == torch.bfloat16:
        return "bf16"
    return "fp32"


def max_new_tokens_for_text(text: str) -> int:
    """
    Scale Parler audio token budget to phrase length.

    Fixed max_new_tokens=1800 makes even short replies slow on GPU.
    """
    # Balanced defaults reduce needless generation for kiosk-sized sentences.
    # The prior 1800/320/45 profile remains available through environment
    # overrides if a listening benchmark finds clipping on specific hardware.
    cap = int(os.environ.get("BANK_PARLER_MAX_NEW_TOKENS", "1500"))
    floor = int(os.environ.get("BANK_PARLER_MIN_NEW_TOKENS", "280"))
    per_char = int(os.environ.get("BANK_PARLER_TOKENS_PER_CHAR", "40"))
    n = len((text or "").strip())
    if n <= 0:
        return floor
    est = n * per_char + 180
    return max(floor, min(cap, est))


# Defaults tuned for short kiosk phrases — old floor/cap caused 20s silent WAV tails.


def _split_at_middle_space(text: str, max_chars: int) -> list[str]:
    """Last resort for a long run with no punctuation: cut at the space nearest the middle."""
    if len(text) <= max_chars or " " not in text:
        return [text]
    mid = len(text) // 2
    spaces = [i for i, ch in enumerate(text) if ch == " "]
    cut = min(spaces, key=lambda i: abs(i - mid))
    left, right = text[:cut].strip(), text[cut + 1 :].strip()
    if not left or not right:
        return [text]
    return _split_at_middle_space(left, max_chars) + _split_at_middle_space(right, max_chars)


def split_tts_chunks(text: str, max_chars: int | None = None) -> list[str]:
    """
    Split a reply into short chunks that Parler can generate as one batch.

    Generation time follows the longest item in a batch, so a long reply split
    into ~60-char chunks is 2-4x faster than one pass — and each chunk gets its
    own token budget, so long replies are no longer cut off at the cap.

    Order of preference: sentence end (. ? ! ।) → clause (, : ;) → word nearest
    the middle. Chunks never split a word.
    """
    if max_chars is None:
        max_chars = int(os.environ.get("BANK_PARLER_CHUNK_CHARS", "60"))
    max_chars = max(20, max_chars)
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []

    sentences = [s for s in re.split(r"(?<=[.?!।])\s+", cleaned) if s]
    chunks: list[str] = []
    for sentence in sentences:
        if len(sentence) <= max_chars:
            chunks.append(sentence)
            continue
        buf = ""
        for clause in re.split(r"(?<=[,:;])\s+", sentence):
            if buf and len(buf) + 1 + len(clause) > max_chars:
                chunks.extend(_split_at_middle_space(buf, max_chars))
                buf = clause
            else:
                buf = f"{buf} {clause}".strip()
        if buf:
            chunks.extend(_split_at_middle_space(buf, max_chars))
    return chunks


def chunk_pause_s(chunk: str) -> float:
    """Pause after a chunk: longer after a sentence end than after a clause."""
    return 0.28 if re.search(r"[.?!।]$", chunk.strip()) else 0.14


def load_parler_model(model_id: str, device: str):
    """Load Indic Parler with configured precision."""
    from parler_tts import ParlerTTSForConditionalGeneration

    dtype = resolve_parler_dtype(device)
    load_kwargs = {"torch_dtype": dtype}
    attention = os.environ.get("BANK_PARLER_ATTN_IMPLEMENTATION", "sdpa").strip()
    if attention:
        load_kwargs["attn_implementation"] = attention
    try:
        model = ParlerTTSForConditionalGeneration.from_pretrained(
            model_id,
            **load_kwargs,
        ).to(device)
    except (TypeError, ValueError):
        # Older Parler/Transformers builds may not expose attn_implementation.
        load_kwargs.pop("attn_implementation", None)
        model = ParlerTTSForConditionalGeneration.from_pretrained(
            model_id,
            **load_kwargs,
        ).to(device)
    model.eval()
    return model, dtype
