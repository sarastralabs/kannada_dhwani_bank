"""
Persistent Indic Parler-TTS worker (runs inside .venv-parler only).

Protocol (stdin/stdout, one JSON object per line):
  Request:  {"cmd":"synth","text":"<kannada>","speaker":"Suresh"|"Anu"}
  Response: {"ok":true,"audio_b64":"...","sr":22050,"speaker":"Suresh"}
            {"ok":false,"error":"..."}
  Request:  {"cmd":"ping"}
  Response: {"ok":true,"pong":true,"ready":true}

All logs go to stderr so stdout stays clean JSON.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import traceback

import numpy as np

os.environ.setdefault("TRANSFORMERS_OFFLINE", os.environ.get("TRANSFORMERS_OFFLINE", "0"))
# Triton is often unavailable on Windows CUDA wheels; keep compile off unless opted in.
os.environ.setdefault("BANK_PARLER_COMPILE", "0")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
os.environ.setdefault("TORCH_COMPILE_DISABLE", "1")

from parler_model_utils import (  # noqa: E402
    chunk_pause_s,
    max_new_tokens_for_text,
    split_tts_chunks,
)

SPEAKER_DESCRIPTIONS = {
    "Suresh": (
        "Suresh's voice is clear, warm, and professional, speaking at a moderate "
        "pace with a friendly bank-counter tone. The recording is of very high "
        "quality, with the speaker's voice sounding clear and very close up."
    ),
    "Anu": (
        "Anu's voice is clear, warm, and expressive, speaking at a moderate pace "
        "with a friendly helpful tone. The recording is of very high quality, "
        "with the speaker's voice sounding clear and very close up."
    ),
}

MODEL_ID = os.environ.get("BANK_PARLER_MODEL", "ai4bharat/indic-parler-tts")


def _load_model(device: str):
    from parler_model_utils import dtype_label, load_parler_model

    model, dtype = load_parler_model(MODEL_ID, device)
    return model, dtype_label(dtype)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def main() -> int:
    import torch
    import soundfile as sf
    from transformers import AutoTokenizer

    requested_device = os.environ.get("BANK_PARLER_DEVICE", "").strip().lower()
    device = requested_device or ("cuda:0" if torch.cuda.is_available() else "cpu")
    require_cuda = os.environ.get("BANK_PARLER_REQUIRE_CUDA", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError(
            f"BANK_PARLER_DEVICE={device} was requested, but CUDA is unavailable"
        )
    if require_cuda and not device.startswith("cuda"):
        raise RuntimeError(
            "CUDA is required for production Parler TTS, but PyTorch cannot access a GPU"
        )
    if device == "cpu" and os.environ.get("BANK_PARLER_DTYPE", "auto").lower() in {
        "fp16",
        "float16",
        "16",
        "half",
    }:
        raise RuntimeError("BANK_PARLER_DTYPE=fp16 is invalid for CPU inference")
    if device.startswith("cuda"):
        device_index = torch.device(device).index or 0
        if device_index >= torch.cuda.device_count():
            raise RuntimeError(
                f"BANK_PARLER_DEVICE={device} is invalid; "
                f"only {torch.cuda.device_count()} CUDA device(s) are visible"
            )
        # Off by default: Parler's audio decoder sees a new input shape on almost
        # every request, so cuDNN autotuning re-ran each time and made generation
        # 2-4x slower (measured on RTX 4060: 15 s -> 6 s for a 370-char reply).
        torch.backends.cudnn.benchmark = os.environ.get(
            "BANK_PARLER_CUDNN_BENCHMARK", "0"
        ).strip().lower() in {"1", "true", "yes", "on"}
        torch.backends.cuda.matmul.allow_tf32 = True
    _log(f"[parler-worker] loading {MODEL_ID} on {device}")

    model, precision = _load_model(device)
    # Samples per generated audio frame (DAC hop) — max_new_tokens counts frames.
    HOP = int(getattr(model.config.audio_encoder, "hop_length", 0) or 512)
    eager_forward = model.forward
    compile_mode = os.environ.get("BANK_PARLER_COMPILE", "0").strip().lower()
    compiled = compile_mode not in {"", "0", "false", "off", "no"}
    if compiled:
        requested_mode = (
            "default" if compile_mode in {"1", "true", "yes", "on"} else compile_mode
        )
        try:
            model.generation_config.cache_implementation = "static"
            model.forward = torch.compile(model.forward, mode=requested_mode)
            _log(f"[parler-worker] torch.compile enabled mode={requested_mode}")
        except Exception as exc:
            compiled = False
            model.forward = eager_forward
            model.generation_config.cache_implementation = None
            _log(f"[parler-worker] torch.compile unavailable, using eager: {exc}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    desc_tokenizer = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)
    description_inputs = {
        speaker: desc_tokenizer(description, return_tensors="pt").to(device)
        for speaker, description in SPEAKER_DESCRIPTIONS.items()
    }
    if device.startswith("cuda"):
        device_index = torch.device(device).index or 0
        device_name = torch.cuda.get_device_name(device_index)
        free_bytes, total_bytes = torch.cuda.mem_get_info(device_index)
        free_vram_mb = round(free_bytes / (1024 * 1024))
        total_vram_mb = round(total_bytes / (1024 * 1024))
    else:
        device_name = "CPU"
        free_vram_mb = None
        total_vram_mb = None
    _log(f"[parler-worker] ready ({precision})")

    # Signal ready on stdout for parent
    print(
        json.dumps(
            {
                "ok": True,
                "ready": True,
                "device": device,
                "device_name": device_name,
                "dtype": precision,
                "model": MODEL_ID,
                "cuda_version": torch.version.cuda,
                "free_vram_mb": free_vram_mb,
                "total_vram_mb": total_vram_mb,
            }
        ),
        flush=True,
    )

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            print(json.dumps({"ok": False, "error": f"bad json: {exc}"}), flush=True)
            continue

        cmd = (req.get("cmd") or "synth").lower()
        if cmd == "ping":
            print(json.dumps({"ok": True, "pong": True, "ready": True}), flush=True)
            continue
        if cmd == "quit":
            print(json.dumps({"ok": True, "bye": True}), flush=True)
            return 0

        text = (req.get("text") or "").strip()
        speaker = (req.get("speaker") or "Suresh").strip()
        if speaker not in SPEAKER_DESCRIPTIONS:
            speaker = "Suresh"
        if not text:
            print(json.dumps({"ok": False, "error": "empty text"}), flush=True)
            continue

        total_started = time.perf_counter()
        try:
            tokenize_started = time.perf_counter()
            desc_ids = description_inputs[speaker]
            # Long replies are split into short chunks generated as ONE batch:
            # time follows the longest chunk, and each chunk has its own token
            # budget (a single pass cut long replies off at the cap).
            batch_on = os.environ.get("BANK_PARLER_BATCH_CHUNKS", "1").strip().lower() not in {
                "0",
                "false",
                "off",
                "no",
            }
            chunks = (split_tts_chunks(text) if batch_on else []) or [text]
            max_batch = max(1, int(os.environ.get("BANK_PARLER_MAX_BATCH", "16")))
            tokenize_s = time.perf_counter() - tokenize_started
            # Greedy decode (do_sample=0) often collapses to ~1 word / silence.
            # Sampling matches prior working behavior for full Kannada sentences.
            do_sample = os.environ.get("BANK_PARLER_DO_SAMPLE", "1").strip().lower() in {
                "1",
                "true",
                "yes",
            }
            temperature = float(os.environ.get("BANK_PARLER_TEMPERATURE", "0.9"))
            sr = int(model.config.sampling_rate)
            if device.startswith("cuda"):
                torch.cuda.synchronize(device)
                torch.cuda.reset_peak_memory_stats(device)
            generation_started = time.perf_counter()

            from backend.tts.audio_util import trim_trailing_silence

            chunk_audio: list[np.ndarray] = [np.zeros(0, dtype=np.float32)] * len(chunks)
            max_tokens = 0
            max_frames = 0
            hit_limit = False
            # Parler sometimes ends a phrase immediately (1-sample output; mostly
            # Anu-voice short phrases, 20-40% of tries). Regenerate just those chunks instead of
            # returning silence that would then be cached.
            min_samples = int(sr * 0.12)
            empty_retries = max(0, int(os.environ.get("BANK_PARLER_EMPTY_RETRIES", "5")))
            todo = list(range(len(chunks)))
            for attempt in range(empty_retries + 1):
                raw_len: dict[int, int] = {}
                for start in range(0, len(todo), max_batch):
                    idxs = todo[start : start + max_batch]
                    group = [chunks[i] for i in idxs]
                    n = len(group)
                    prompt_ids = tokenizer(group, return_tensors="pt", padding=True).to(device)
                    budget = max(max_new_tokens_for_text(c) for c in group)
                    max_tokens = max(max_tokens, budget)
                    gen_kwargs: dict = {
                        "input_ids": desc_ids.input_ids.repeat(n, 1),
                        "attention_mask": desc_ids.attention_mask.repeat(n, 1),
                        "prompt_input_ids": prompt_ids.input_ids,
                        "prompt_attention_mask": prompt_ids.attention_mask,
                        "max_new_tokens": budget,
                        "do_sample": do_sample,
                        "return_dict_in_generate": True,
                    }
                    if do_sample:
                        gen_kwargs["temperature"] = temperature
                    try:
                        with torch.inference_mode():
                            out = model.generate(**gen_kwargs)
                    except Exception as compile_exc:
                        if not compiled:
                            raise
                        _log(
                            "[parler-worker] compiled generation failed; "
                            f"retrying eager: {compile_exc}"
                        )
                        compiled = False
                        model.forward = eager_forward
                        model.generation_config.cache_implementation = None
                        if device.startswith("cuda"):
                            torch.cuda.empty_cache()
                        with torch.inference_mode():
                            out = model.generate(**gen_kwargs)

                    lengths = getattr(out, "audios_length", None)
                    for j, ci in enumerate(idxs):
                        seq = out.sequences[j]
                        if lengths is not None:
                            seq = seq[: int(lengths[j])]
                        audio = seq.float().cpu().numpy().reshape(-1).astype(np.float32)
                        raw_len[ci] = len(audio)
                        # Parler emits audio frames of HOP samples; the budget is in frames.
                        frames = -(-len(audio) // HOP)
                        max_frames = max(max_frames, frames)
                        # Parler stops ~9 frames short of the budget (codebook delay pattern).
                        hit_limit = hit_limit or frames >= budget - 12
                        chunk_audio[ci] = trim_trailing_silence(
                            audio, sr, threshold=0.01, pad_ms=120
                        )
                todo = [i for i in todo if raw_len.get(i, 0) < min_samples]
                if not todo:
                    break
                if attempt < empty_retries:
                    _log(
                        f"[parler-worker] {len(todo)} empty chunk(s); "
                        f"regenerating ({attempt + 1}/{empty_retries})"
                    )
            if todo:
                # Fail loudly: an error is never cached, the kiosk falls back.
                raise RuntimeError(
                    f"Parler returned empty audio for {len(todo)} chunk(s) "
                    f"after {empty_retries} retries"
                )
            if device.startswith("cuda"):
                torch.cuda.synchronize(device)
            generation_s = time.perf_counter() - generation_started

            encode_started = time.perf_counter()
            pieces: list[np.ndarray] = []
            for i, (chunk, audio) in enumerate(zip(chunks, chunk_audio)):
                pieces.append(audio)
                if i < len(chunks) - 1:
                    pieces.append(np.zeros(int(sr * chunk_pause_s(chunk)), dtype=np.float32))
            audio_arr = np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)
            # Trim only long trailing silence — keep quiet speech (threshold 0.01)
            audio_arr = trim_trailing_silence(audio_arr, sr, threshold=0.01, pad_ms=250)
            buf = io.BytesIO()
            sf.write(buf, audio_arr, sr, format="WAV")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            encode_s = time.perf_counter() - encode_started
            total_s = time.perf_counter() - total_started
            audio_duration_s = len(audio_arr) / sr if sr else 0.0
            metrics = {
                "text_chars": len(text),
                "chunks": len(chunks),
                "max_new_tokens": max_tokens,
                "generated_frames": max_frames,
                "hit_token_limit": hit_limit,
                "tokenize_s": round(tokenize_s, 3),
                "generation_s": round(generation_s, 3),
                "encode_s": round(encode_s, 3),
                "total_s": round(total_s, 3),
                "audio_duration_s": round(audio_duration_s, 3),
                "realtime_factor": round(generation_s / audio_duration_s, 3)
                if audio_duration_s
                else None,
                "device": device,
                "device_name": device_name,
                "dtype": precision,
                "cuda_allocated_mb": round(torch.cuda.memory_allocated(device) / 1048576)
                if device.startswith("cuda")
                else None,
                "cuda_reserved_mb": round(torch.cuda.memory_reserved(device) / 1048576)
                if device.startswith("cuda")
                else None,
                "cuda_peak_mb": round(torch.cuda.max_memory_allocated(device) / 1048576)
                if device.startswith("cuda")
                else None,
            }
            _log(
                "[parler-worker] "
                f"speaker={speaker} chars={len(text)} chunks={len(chunks)} "
                f"max_tokens={max_tokens} frames={max_frames} hit_limit={int(hit_limit)} "
                f"generation_s={generation_s:.3f} audio_s={audio_duration_s:.3f} "
                f"total_s={total_s:.3f}"
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "audio_b64": b64,
                        "sr": sr,
                        "speaker": speaker,
                        "engine": "indic-parler-tts",
                        "dtype": precision,
                        "max_new_tokens": max_tokens,
                        "metrics": metrics,
                    }
                ),
                flush=True,
            )
        except Exception as exc:
            _log(traceback.format_exc())
            print(json.dumps({"ok": False, "error": str(exc)}), flush=True)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"ok": False, "error": "worker crashed on startup"}), flush=True)
        raise SystemExit(1)
