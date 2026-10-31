"""
Minimal TTS-only API for a dedicated GPU machine (Parler Suresh/Anu).

Usage (TTS box):
    .\\scripts\\run_tts_server.ps1

Expose via Cloudflare tunnel, then on the kiosk machine set:
    BANK_TTS_REMOTE_URL=https://tts.sarastralabs.com
    BANK_TTS_REMOTE_KEY=same-secret-as-TTS-box
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Literal

from dotenv import load_dotenv

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(_ROOT, ".env"), override=True)

from backend.quiet_torch import install_quiet_triton_stderr  # noqa: E402

install_quiet_triton_stderr()

# TTS box: Parler only — no pipeline worker, no STT on GPU
os.environ.setdefault("BANK_TTS_ENGINE", "parler")
os.environ.setdefault("BANK_PIPELINE_WORKER", "0")
os.environ.setdefault("BANK_TTS_ALLOW_MMS", "0")
os.environ.setdefault("BANK_TTS_SPEAKER", "Suresh")
os.environ.setdefault("BANK_PARLER_DTYPE", "fp16")
os.environ.setdefault("BANK_PARLER_DO_SAMPLE", "1")
os.environ.setdefault("BANK_PARLER_REQUIRE_CUDA", "1")
os.environ.setdefault("BANK_PARLER_ATTN_IMPLEMENTATION", "sdpa")
# Avoid torch.compile/Triton on Windows CUDA builds (noise + failed compiles).
os.environ.setdefault("BANK_PARLER_COMPILE", "0")
os.environ.setdefault("BANK_PARLER_MAX_NEW_TOKENS", "1500")
os.environ.setdefault("BANK_PARLER_MIN_NEW_TOKENS", "280")
os.environ.setdefault("BANK_PARLER_TOKENS_PER_CHAR", "40")
os.environ.setdefault("BANK_TTS_CACHE_MAX", "512")
# Never call remote TTS from the TTS service itself (would loop to localhost:8001).
os.environ.pop("BANK_TTS_REMOTE_URL", None)

from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.tts.parler_bridge import (  # noqa: E402
    default_speaker,
    ensure_parler_ready,
    parler_available,
    parler_ready,
    parler_runtime_info,
    parler_warm_error,
    stop_worker,
)
from backend.tts.speak_cache import get_cached_b64, kannada_to_b64  # noqa: E402
from backend.tts.warmup import warm_parler_service  # noqa: E402
_warm_stats: dict = {}
_synth_semaphore = asyncio.Semaphore(
    max(1, int(os.environ.get("BANK_TTS_CONCURRENCY", "1")))
)


def _synth_b64(
    text: str,
    speaker: str | None,
    *,
    bypass_cache: bool = False,
) -> tuple[str, bool]:
    """Returns (audio_b64, cache_hit)."""
    sp = speaker or default_speaker()
    if not bypass_cache:
        hit = get_cached_b64(text, speaker=sp)
        if hit:
            return hit, True
    if bypass_cache:
        b64 = kannada_to_b64(text, speaker=sp, bypass_cache=True)
    else:
        b64 = kannada_to_b64(text, speaker=sp)
    return b64, False


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Load Parler and pre-cache common lobby phrases so first speak is fast."""
    global _warm_stats
    print(
        "[tts-server] Loading Parler + warming common phrases "
        "(first start may take several minutes)…",
        file=sys.stderr,
        flush=True,
    )
    started = time.perf_counter()
    warm = await asyncio.to_thread(warm_parler_service)
    ready = bool(warm.get("ok")) and bool(warm.get("ready") or ensure_parler_ready())
    _warm_stats = {
        "ok": ready,
        "model_ready": ready,
        "phrases_cached": int(warm.get("phrases_cached") or 0),
        "cache_warm": "startup-prewarm",
        "speaker": warm.get("speaker") or default_speaker(),
        "elapsed_s": round(time.perf_counter() - started, 1),
        "error": None if ready else (warm.get("error") or parler_warm_error()),
    }
    if _warm_stats.get("ok"):
        print(
            f"[tts-server] Ready — speaker={_warm_stats.get('speaker')} "
            f"phrases={_warm_stats.get('phrases_cached')} "
            f"elapsed={_warm_stats.get('elapsed_s')}s",
            file=sys.stderr,
            flush=True,
        )
    else:
        print(
            f"[tts-server] WARN: warmup incomplete — {_warm_stats.get('error')}",
            file=sys.stderr,
            flush=True,
        )
        if os.environ.get("BANK_PARLER_REQUIRE_CUDA", "1").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            raise RuntimeError(
                f"Production TTS failed to become ready: {_warm_stats.get('error')}"
            )
    yield
    stop_worker()


app = FastAPI(title="Kannada TTS Service (Parler)", version="1.0.0", lifespan=_lifespan)


class SpeakBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    speaker: Literal["Suresh", "Anu"] | None = Field(
        default=None,
        description="Suresh or Anu",
    )
    bypass_cache: bool = Field(default=False, description="Benchmark only")


def _require_key(x_bank_tts_key: str | None = Header(default=None, alias="X-Bank-Tts-Key")) -> None:
    expected = os.environ.get("BANK_TTS_REMOTE_KEY", "").strip()
    if expected and x_bank_tts_key != expected:
        raise HTTPException(status_code=401, detail="Invalid TTS API key")


@app.get("/api/health/live")
def health_live() -> dict:
    """Fast liveness — no GPU work."""
    return {"status": "ok", "live": True, "service": "tts"}


@app.get("/api/health")
def health() -> dict:
    ready = parler_ready()
    status = "ready" if ready else ("warming" if parler_available() else "unavailable")
    return {
        "status": status,
        "service": "tts",
        "parler": parler_available(),
        "ready": ready,
        "speaker": default_speaker(),
        "warmup": _warm_stats,
        "runtime": parler_runtime_info(),
        "error": parler_warm_error(),
    }


@app.post("/api/speak-kannada")
async def speak_kannada(body: SpeakBody, _: None = Depends(_require_key)) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")
    if not parler_available():
        raise HTTPException(
            status_code=503,
            detail="Parler TTS not available on this machine",
        )
    if not parler_ready():
        raise HTTPException(
            status_code=503,
            detail="Parler is still warming up — retry in a few seconds",
        )

    speaker = (body.speaker or "").strip() or None
    started = time.perf_counter()
    resolved_speaker = speaker or default_speaker()
    if not body.bypass_cache:
        cached_audio = get_cached_b64(text, speaker=resolved_speaker)
        if cached_audio:
            total_s = round(time.perf_counter() - started, 3)
            return {
                "text": text,
                "audio_b64": cached_audio,
                "speaker": resolved_speaker,
                "engine": "indic-parler-tts",
                "cached": True,
                "timing": {
                    "total_s": total_s,
                    "api_queue_wait_s": 0.0,
                    "cache_hit": True,
                },
            }
    queue_timeout = max(
        0.1,
        float(os.environ.get("BANK_TTS_QUEUE_TIMEOUT", "5")),
    )
    try:
        await asyncio.wait_for(_synth_semaphore.acquire(), timeout=queue_timeout)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=429,
            detail="TTS is busy; retry this request shortly",
        ) from exc
    queue_wait_s = time.perf_counter() - started
    try:
        try:
            audio_b64, cached = await asyncio.to_thread(
                _synth_b64,
                text,
                resolved_speaker,
                bypass_cache=body.bypass_cache,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"TTS failed: {exc}") from exc
    finally:
        _synth_semaphore.release()

    if not audio_b64:
        raise HTTPException(status_code=500, detail="TTS returned empty audio")
    total_s = round(time.perf_counter() - started, 3)
    runtime = parler_runtime_info()
    timing = {
        "total_s": total_s,
        "api_queue_wait_s": round(queue_wait_s, 3),
        "cache_hit": cached,
    }
    if not cached and runtime.get("last_metrics"):
        timing.update(runtime["last_metrics"])
    print(
        f"[tts-server] speaker={resolved_speaker} chars={len(text)} "
        f"cache_hit={int(cached)} total_s={total_s}",
        file=sys.stderr,
        flush=True,
    )
    return {
        "text": text,
        "audio_b64": audio_b64,
        "speaker": resolved_speaker,
        "engine": "indic-parler-tts",
        "cached": cached,
        "timing": timing,
    }
