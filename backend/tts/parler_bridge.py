"""
Bridge to AI4Bharat Indic Parler-TTS via an isolated .venv-parler worker.

Main project stays on transformers>=4.51 (IndicTrans2). Parler needs 4.46.x,
so synthesis runs in a long-lived subprocess started from .venv-parler.
"""

from __future__ import annotations

import base64
from collections import deque
import io
import json
import os
import queue
import subprocess
import sys
import threading
import time
from typing import Any

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKER_SCRIPT = os.path.join(PROJECT_ROOT, "run_parler_tts_worker.py")
DEFAULT_VENV_PY = os.path.join(PROJECT_ROOT, ".venv-parler", "Scripts", "python.exe")
DEFAULT_VENV_PY_UNIX = os.path.join(PROJECT_ROOT, ".venv-parler", "bin", "python")

_lock = threading.Lock()
_proc: subprocess.Popen[str] | None = None
_ready = False
_warmed = False
_warm_error: str | None = None
_worker_info: dict[str, Any] = {}
_last_metrics: dict[str, Any] = {}
_stderr_tail: deque[str] = deque(maxlen=60)


def _terminate_process(proc: subprocess.Popen[str] | None) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    except Exception:
        pass
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        try:
            if stream is not None:
                stream.close()
        except Exception:
            pass


def _readline_with_timeout(stream, timeout_s: float) -> str:
    """Read a worker response without allowing a dead GPU process to hang forever."""
    result: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)

    def _read() -> None:
        try:
            result.put(stream.readline())
        except BaseException as exc:
            result.put(exc)

    threading.Thread(target=_read, daemon=True, name="parler-worker-read").start()
    try:
        value = result.get(timeout=max(1.0, timeout_s))
    except queue.Empty as exc:
        raise TimeoutError(f"Parler worker timed out after {timeout_s:.0f}s") from exc
    if isinstance(value, BaseException):
        raise value
    return value


def _parler_python() -> str | None:
    override = os.environ.get("BANK_PARLER_PYTHON", "").strip()
    if override and os.path.isfile(override):
        return override
    if os.path.isfile(DEFAULT_VENV_PY):
        return DEFAULT_VENV_PY
    if os.path.isfile(DEFAULT_VENV_PY_UNIX):
        return DEFAULT_VENV_PY_UNIX
    return None


def _parler_model_cached() -> bool:
    """True only when indic-parler weights are present locally (no network fetch)."""
    model_id = os.environ.get("BANK_PARLER_MODEL", "ai4bharat/indic-parler-tts")
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        from huggingface_hub import try_to_load_from_cache

        for filename in ("config.json", "model.safetensors"):
            if try_to_load_from_cache(model_id, filename, cache_dir=HF_HUB_CACHE) is None:
                return False
        return True
    except Exception:
        # No hub / offline — assume unavailable rather than hang on download
        return False


def parler_available() -> bool:
    """True when isolated Parler venv exists and engine is not forced to mms."""
    engine = os.environ.get("BANK_TTS_ENGINE", "auto").strip().lower()
    if engine in {"mms", "mms-tts", "off"}:
        return False
    if engine not in {"parler", "indic-parler", "auto"}:
        return False
    if _parler_python() is None or not os.path.isfile(WORKER_SCRIPT):
        return False

    # Dedicated TTS box (engine=parler): venv present is enough — worker loads model.
    if engine in {"parler", "indic-parler"}:
        return True

    if not _parler_model_cached():
        return False

    if engine in {"auto"}:
        free_mb = _cuda_free_mb()
        # 8GB laptops often have <4.5GB free after Whisper — allow Parler more often.
        min_free = int(os.environ.get("BANK_PARLER_MIN_FREE_MB", "2800"))
        if free_mb is not None and free_mb < min_free:
            return False
    return True


def _cuda_free_mb() -> int | None:
    """Free VRAM in MiB on device 0, or None if unavailable."""
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        free, _total = torch.cuda.mem_get_info(0)
        return int(free // (1024 * 1024))
    except Exception:
        return None


def default_speaker() -> str:
    try:
        from api.app_settings import get_tts_speaker

        return get_tts_speaker()
    except Exception:
        pass
    sp = os.environ.get("BANK_TTS_SPEAKER", "Suresh").strip()
    if sp.lower() == "anu":
        return "Anu"
    return "Suresh"


def parler_ready() -> bool:
    """True after Parler worker is loaded and a warmup synth succeeded."""
    return _warmed and _ready


def parler_warm_error() -> str | None:
    return _warm_error


def parler_runtime_info() -> dict[str, Any]:
    """Return non-secret worker details and the latest synthesis timings."""
    return {
        **_worker_info,
        "ready": parler_ready(),
        "last_metrics": dict(_last_metrics),
    }


def ensure_parler_ready(*, run_synth_ping: bool = True) -> bool:
    """
    Block until the Parler worker subprocess has loaded the model into GPU.
    Optionally run one short synthesis so the first customer request is fast.
    """
    global _warmed, _warm_error

    if not parler_available():
        _warm_error = "Parler not available (venv, model cache, or GPU)"
        return False

    if _warmed and _ready:
        return True

    with _lock:
        if _warmed and _ready:
            return True
        try:
            _start_worker_locked()
            if run_synth_ping:
                sp = default_speaker()
                resp = _request({"cmd": "synth", "text": "ಸರಿ", "speaker": sp}, _hold_lock=True)
                if not resp.get("ok"):
                    raise RuntimeError(resp.get("error") or "warmup synth failed")
            _warmed = run_synth_ping
            _warm_error = None
            return True
        except Exception as exc:
            _warmed = False
            _warm_error = str(exc)
            return False


def _start_worker_locked() -> None:
    global _proc, _ready, _warmed, _worker_info
    if _proc is not None and _proc.poll() is None and _ready:
        return

    py = _parler_python()
    if not py:
        raise RuntimeError(
            "Parler venv not found. Run: .\\scripts\\setup_parler_venv.ps1"
        )

    env = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
    }
    # Parler worker must read HF cache even when the API runs offline-first.
    for key in ("HF_HUB_OFFLINE", "HF_DATASETS_OFFLINE", "TRANSFORMERS_OFFLINE"):
        env.pop(key, None)
    env.setdefault("TRANSFORMERS_OFFLINE", "0")
    proc = subprocess.Popen(
        [py, WORKER_SCRIPT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
        bufsize=1,
    )
    _proc = proc
    _stderr_tail.clear()
    assert proc.stdout is not None

    def _drain_stderr(worker: subprocess.Popen[str] = proc) -> None:
        assert worker.stderr is not None
        for line in worker.stderr:
            line = line.rstrip()
            if line:
                _stderr_tail.append(line)
                print(line, file=sys.stderr, flush=True)

    threading.Thread(target=_drain_stderr, daemon=True, name="parler-worker-stderr").start()

    # First stdout line should be ready handshake (after model load in worker).
    start_timeout = float(os.environ.get("BANK_PARLER_START_TIMEOUT", "180"))
    try:
        line = _readline_with_timeout(proc.stdout, start_timeout)
    except TimeoutError:
        _proc = None
        _ready = False
        _warmed = False
        _terminate_process(proc)
        raise
    if not line:
        _proc = None
        _ready = False
        _warmed = False
        _terminate_process(proc)
        raise RuntimeError(
            f"Parler worker failed to start: {' | '.join(_stderr_tail)[-500:]}"
        )
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        _proc = None
        _ready = False
        _warmed = False
        _terminate_process(proc)
        raise RuntimeError(f"Parler worker bad handshake: {line[:200]}") from exc
    if not payload.get("ok"):
        _proc = None
        _ready = False
        _warmed = False
        _terminate_process(proc)
        raise RuntimeError(payload.get("error") or "Parler worker not ready")
    _worker_info = {
        key: payload.get(key)
        for key in (
            "device",
            "device_name",
            "dtype",
            "model",
            "cuda_version",
            "free_vram_mb",
            "total_vram_mb",
        )
        if payload.get(key) is not None
    }
    _ready = True


def _request(payload: dict[str, Any], timeout_s: float = 300.0, *, _hold_lock: bool = False) -> dict[str, Any]:
    global _proc, _ready, _last_metrics
    queued_at = time.perf_counter()

    def _do_request() -> dict[str, Any]:
        global _proc, _ready, _warmed, _last_metrics
        queue_wait_s = time.perf_counter() - queued_at
        _start_worker_locked()
        assert _proc is not None and _proc.stdin and _proc.stdout
        try:
            _proc.stdin.write(json.dumps(payload) + "\n")
            _proc.stdin.flush()
        except BrokenPipeError:
            broken_proc = _proc
            _proc = None
            _ready = False
            _terminate_process(broken_proc)
            _start_worker_locked()
            assert _proc is not None and _proc.stdin and _proc.stdout
            _proc.stdin.write(json.dumps(payload) + "\n")
            _proc.stdin.flush()

        try:
            line = _readline_with_timeout(_proc.stdout, timeout_s)
        except TimeoutError:
            timed_out_proc = _proc
            _proc = None
            _ready = False
            _warmed = False
            _terminate_process(timed_out_proc)
            raise
        if not line:
            dead_proc = _proc
            _proc = None
            _ready = False
            _terminate_process(dead_proc)
            raise RuntimeError(
                f"Parler worker died: {' | '.join(_stderr_tail)[-800:]}"
            )
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            bad_proc = _proc
            _proc = None
            _ready = False
            _warmed = False
            _terminate_process(bad_proc)
            raise RuntimeError(f"Parler worker returned bad JSON: {line[:200]}") from exc
        metrics = response.get("metrics")
        if isinstance(metrics, dict):
            metrics["queue_wait_s"] = round(queue_wait_s, 3)
            response["metrics"] = metrics
            _last_metrics = dict(metrics)
        return response

    if _hold_lock:
        return _do_request()
    with _lock:
        return _do_request()


def stop_worker() -> None:
    global _proc, _ready, _warmed, _worker_info, _last_metrics
    with _lock:
        if _proc is None:
            return
        proc = _proc
        try:
            if proc.stdin and proc.poll() is None:
                proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                proc.stdin.flush()
                proc.wait(timeout=10)
        except Exception:
            pass
        _terminate_process(proc)
        _proc = None
        _ready = False
        _warmed = False
        _worker_info = {}
        _last_metrics = {}


def synthesise_kannada_parler(
    kannada_text: str,
    speaker: str | None = None,
) -> tuple[np.ndarray, int]:
    """
    Synthesise Kannada speech with Indic Parler-TTS (Suresh/Anu).
    Raises on failure — caller should fall back to MMS.
    """
    if not kannada_text or not kannada_text.strip():
        raise ValueError("empty text")
    sp = speaker or default_speaker()
    resp = _request({"cmd": "synth", "text": kannada_text.strip(), "speaker": sp})
    if not resp.get("ok") or not resp.get("audio_b64"):
        raise RuntimeError(resp.get("error") or "Parler synth failed")

    raw = base64.b64decode(resp["audio_b64"])
    import soundfile as sf

    audio, sr = sf.read(io.BytesIO(raw), dtype="float32")
    if getattr(audio, "ndim", 1) > 1:
        audio = audio.mean(axis=1)
    return np.asarray(audio, dtype=np.float32), int(sr or resp.get("sr") or 22050)
