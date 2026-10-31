"""Suppress known-harmless Torch/Triton import noise on Windows."""

from __future__ import annotations

import os
import sys


def disable_torch_compile_env() -> None:
    os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
    os.environ.setdefault("TORCH_COMPILE_DISABLE", "1")
    os.environ.setdefault("BANK_PARLER_COMPILE", "0")


class QuietTritonStderr:
    """Filter stderr lines that only report missing Triton (common on Windows)."""

    def __init__(self, real):
        self._real = real

    def write(self, data: str) -> int:
        text = data or ""
        if "No module named 'triton'" in text or 'No module named "triton"' in text:
            return len(text)
        stripped = text.strip().lower()
        if stripped.startswith("import error:") and "triton" in stripped:
            return len(text)
        return self._real.write(data)

    def flush(self) -> None:
        self._real.flush()

    def fileno(self):
        return self._real.fileno()

    def isatty(self) -> bool:
        return bool(getattr(self._real, "isatty", lambda: False)())

    def __getattr__(self, name: str):
        return getattr(self._real, name)


_INSTALLED = False


def install_quiet_triton_stderr() -> None:
    global _INSTALLED
    disable_torch_compile_env()
    if _INSTALLED:
        return
    if isinstance(sys.stderr, QuietTritonStderr):
        _INSTALLED = True
        return
    sys.stderr = QuietTritonStderr(sys.stderr)
    _INSTALLED = True
