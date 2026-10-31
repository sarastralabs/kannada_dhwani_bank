"""Pipeline health bookkeeping — tells "not understood" apart from "service broken"."""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from typing import Any

# Failure text that means infrastructure, not "the customer said something odd".
_SERVICE_PATTERNS = re.compile(
    r"huggingface|couldn't connect|offline mode|not found in|no such file|"
    r"out of memory|cuda|cannot load|failed to load|model|worker|connection|"
    r"timed out|timeout|oserror|importerror|modulenotfound|not ready|unavailable",
    re.IGNORECASE,
)

_lock = threading.Lock()
_events: deque[tuple[float, bool, str]] = deque(maxlen=200)
_last_error: dict[str, Any] | None = None


def classify_error(message: str | None) -> str:
    """Return "service_unavailable" for infrastructure faults, else "not_understood"."""
    if message and _SERVICE_PATTERNS.search(message):
        return "service_unavailable"
    return "not_understood"


def record(ok: bool, error: str | None = None) -> None:
    """Remember one pipeline outcome (only genuine service faults count as failures)."""
    global _last_error
    failed = (not ok) and classify_error(error) == "service_unavailable"
    with _lock:
        _events.append((time.time(), not failed, (error or "")[:300]))
        if failed:
            _last_error = {"at": time.time(), "message": (error or "")[:300]}


def snapshot(window_s: int = 900) -> dict[str, Any]:
    cutoff = time.time() - window_s
    with _lock:
        recent = [e for e in _events if e[0] >= cutoff]
        failures = [e for e in recent if not e[1]]
        last = dict(_last_error) if _last_error else None
    return {
        "window_s": window_s,
        "requests": len(recent),
        "service_failures": len(failures),
        "last_error": last,
        "healthy": not failures or (recent and recent[-1][1]),
    }


def reset() -> None:
    global _last_error
    with _lock:
        _events.clear()
        _last_error = None
