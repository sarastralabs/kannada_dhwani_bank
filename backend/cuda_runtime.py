"""
Ensure a single compatible cuDNN is visible before CTranslate2 / torch CUDA work.

faster-whisper (CTranslate2) ships a stub ``cudnn64_9.dll`` next to
``ctranslate2.dll``. On Windows that directory wins DLL search order, so CT2
loads its incomplete cuDNN and then fails with:

    Could not load symbol cudnnGetLibConfig. Error code 127

PyTorch ships the full cuDNN 9 suite under ``torch/lib``. Prefer that suite:
prepend it to PATH, register it via ``add_dll_directory``, and move CT2's
bundled stub aside (once) so Windows resolves torch's loader + ops DLLs.
"""
from __future__ import annotations

import os
from pathlib import Path

_DONE = False


def ensure_compatible_cudnn() -> None:
    """Idempotent; safe to call from every pipeline entrypoint."""
    global _DONE
    if _DONE:
        return
    _DONE = True

    try:
        import torch
    except Exception:
        return

    torch_lib = Path(torch.__file__).resolve().parent / "lib"
    if not torch_lib.is_dir():
        return

    torch_lib_s = str(torch_lib)
    path = os.environ.get("PATH", "")
    if not path.startswith(torch_lib_s):
        os.environ["PATH"] = torch_lib_s + os.pathsep + path
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(torch_lib_s)
        except OSError:
            pass

    try:
        import importlib.util

        spec = importlib.util.find_spec("ctranslate2")
        if not spec or not spec.origin:
            return
        ct2_dir = Path(spec.origin).resolve().parent
        bundled = ct2_dir / "cudnn64_9.dll"
        backup = ct2_dir / "cudnn64_9.dll.bak_torch_conflict"
        if bundled.is_file() and not backup.exists():
            bundled.rename(backup)
    except OSError:
        # Another process may hold the DLL; PATH/add_dll_directory still helps
        # when the stub is already renamed.
        pass
