"""
Shared JSON file for settings staff change from the admin console.

The API process and the pipeline worker subprocess both read it, so a change
saved in the admin console reaches the worker without a restart. Writes merge
into the existing content (never replace it) and are atomic.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lock = threading.RLock()
_cache: dict[str, Any] = {}
_cache_stamp: tuple[float, int] | None = None


def settings_path() -> str:
    return os.environ.get(
        "BANK_RUNTIME_SETTINGS_FILE",
        os.path.join(_PROJECT_ROOT, "data", "runtime_settings.json"),
    )


def _stamp(path: str) -> tuple[float, int] | None:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime, st.st_size)


def read_all() -> dict[str, Any]:
    """Current settings (re-read only when the file changed on disk)."""
    global _cache, _cache_stamp
    path = settings_path()
    with _lock:
        stamp = _stamp(path)
        if stamp is not None and stamp == _cache_stamp:
            return dict(_cache)
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
            data = payload if isinstance(payload, dict) else {}
        except (OSError, ValueError):
            data = {}
        _cache = data
        _cache_stamp = stamp
        return dict(data)


def update(changes: dict[str, Any]) -> dict[str, Any]:
    """Merge top-level keys into the settings file and return the new content."""
    global _cache, _cache_stamp
    path = settings_path()
    with _lock:
        _cache_stamp = None  # force a fresh read so another process's write is kept
        data = read_all()
        data.update(changes)
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        temporary = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=1)
        os.replace(temporary, path)
        _cache = dict(data)
        _cache_stamp = _stamp(path)
        return dict(data)
