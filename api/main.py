"""
FastAPI server for the Kannada Voice Banking Assistant.

Usage:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import os

# Load .env from project root BEFORE any backend imports
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=True)

from backend.quiet_torch import install_quiet_triton_stderr

install_quiet_triton_stderr()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.cors_config import cors_middleware_kwargs
from api.ratelimit import RateLimitMiddleware

from backend.cuda_runtime import ensure_compatible_cudnn

ensure_compatible_cudnn()

from api.history import init_db
from api.routes import admin, balance, forms, history, insights, kiosk, landing, pipeline

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
# TTS: auto tries Parler (natural Kannada) then MMS (offline fallback).
_tts = os.environ.get("BANK_TTS_ENGINE", "mms").strip().lower()
os.environ["BANK_TTS_ENGINE"] = _tts
os.environ.setdefault("BANK_TTS_ALLOW_MMS", "1")
os.environ.setdefault("BANK_TTS_SPEAKER", "Suresh")

app = FastAPI(title="Kannada Voice Banking API", version="1.0.0")

app.add_middleware(RateLimitMiddleware)
app.add_middleware(CORSMiddleware, **cors_middleware_kwargs())  # added last = outermost, so 429s carry CORS headers


@app.exception_handler(Exception)
async def _unhandled_exception(_request: Request, exc: Exception) -> JSONResponse:
    """Consistent JSON for unexpected server errors."""
    import sys

    print(f"[api] unhandled: {exc}", file=sys.stderr)
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "detail": "Internal server error"},
    )

app.include_router(pipeline.router, prefix="/api")
app.include_router(balance.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(landing.router, prefix="/api")
app.include_router(forms.router, prefix="/api")
app.include_router(kiosk.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(insights.router, prefix="/api")


def autostart_kiosk() -> bool:
    """Open the lobby on boot when BANK_KIOSK_AUTOSTART=1.

    Kiosk state lives in memory, so every restart (or Render waking from sleep) would
    otherwise leave the customer screen on "counter closed" until staff press Open lobby.
    """
    if os.environ.get("BANK_KIOSK_AUTOSTART", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    from api import kiosk_state

    kiosk_state.start_kiosk()
    print("[startup] kiosk lobby opened (BANK_KIOSK_AUTOSTART)", flush=True)
    return True


@app.on_event("startup")
def _startup() -> None:
    init_db()
    autostart_kiosk()
    try:
        from backend.db.customers import init_customer_db, seed_from_demo, store_mode

        mode = init_customer_db()
        if mode == "sqlite":
            seeded = seed_from_demo(force=False)
            print(f"[startup] customer store=sqlite seed={seeded}", flush=True)
        else:
            print(f"[startup] customer store={mode}", flush=True)
    except Exception as exc:
        import sys

        print(f"[startup] customer store init skipped: {exc}", file=sys.stderr)

    from backend.pipeline_bridge import warm_pipeline, worker_enabled

    warm_on_start = os.environ.get("BANK_PIPELINE_WARM_ON_START", "1").strip().lower()
    if worker_enabled() and warm_on_start not in {"0", "false", "off", "no"}:
        try:
            result = warm_pipeline()
            print(
                f"[startup] pipeline ready model={result.get('model')} "
                f"stages={result.get('stage_times')}"
            )
        except Exception as exc:
            import sys

            print(f"[startup] pipeline pre-warm failed: {exc}", file=sys.stderr)

    # Keep remote TTS "hot" from the kiosk side: pull common phrases into local cache
    # so first customer replies do not wait on a cold remote synthesis.
    try:
        import threading

        from backend.tts.remote_bridge import remote_tts_configured

        if remote_tts_configured():

            def _warm_remote_phrases() -> None:
                try:
                    from backend.tts.warmup import warm_via_remote_phrases

                    warm = warm_via_remote_phrases()
                    print(f"[startup] remote TTS phrase cache: {warm}", flush=True)
                except Exception as warm_exc:
                    import sys

                    print(
                        f"[startup] remote TTS phrase warm skipped: {warm_exc}",
                        file=sys.stderr,
                        flush=True,
                    )

            threading.Thread(
                target=_warm_remote_phrases,
                name="tts-phrase-warm",
                daemon=True,
            ).start()
            print("[startup] remote TTS phrase warm started in background", flush=True)
    except Exception as exc:
        import sys

        print(f"[startup] remote TTS warm hook failed: {exc}", file=sys.stderr)
@app.on_event("shutdown")
def _shutdown() -> None:
    try:
        from backend.pipeline_bridge import stop_worker

        stop_worker()
    except Exception:
        pass
    try:
        from backend.tts.parler_bridge import stop_worker as stop_parler

        stop_parler()
    except Exception:
        pass


@app.get("/health")
def health_root() -> dict:
    """Plain liveness probe for hosts (Render, Fly, uptime monitors)."""
    return {"status": "ok"}


@app.get("/api/health/live")
def health_live() -> dict:
    """Fast liveness probe — no TTS/STT checks (used by frontend online indicator)."""
    return {"status": "ok", "live": True}


@app.get("/api/health")
def health() -> dict:
    from backend.db.store import mongo_enabled, ping_mongo
    from backend.tts import parler_status

    mongo = "disabled"
    if mongo_enabled():
        mongo = "connected" if ping_mongo() else "error"

    tts_info = {}
    try:
        tts_info = parler_status()
    except Exception as exc:
        tts_info = {"error": str(exc), "ready": False}
    pipeline_worker = os.environ.get("BANK_PIPELINE_WORKER", "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }

    status = "ok"
    remote = tts_info.get("remote") or {}
    if remote.get("configured"):
        if not remote.get("healthy"):
            status = "degraded"
        elif not tts_info.get("ready"):
            status = "warming"

    return {
        "status": status,
        "mongodb": mongo,
        "pipeline_worker": pipeline_worker,
        "tts": tts_info,
    }
