"""
Regression: a chatty worker must not freeze the bridge.

The worker writes logs to stderr on every request. If the API never drains that
pipe, the OS buffer fills, the worker blocks on its next write, and every
/api/process-audio call hangs forever behind the bridge lock.
"""
from __future__ import annotations

import textwrap
import threading
from pathlib import Path

import pytest

FAKE_WORKER = textwrap.dedent(
    """
    import json, sys
    print(json.dumps({"ok": True, "ready": True}), flush=True)
    for line in sys.stdin:
        req = json.loads(line)
        if req.get("cmd") == "quit":
            break
        # Far more than any OS pipe buffer (4-64 KB).
        sys.stderr.write("noise " * 40_000 + "\\n")
        sys.stderr.flush()
        print(json.dumps({"ok": True, "n": req.get("n")}), flush=True)
    """
)


def test_worker_stderr_is_drained(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend import pipeline_bridge as bridge

    script = tmp_path / "fake_worker.py"
    script.write_text(FAKE_WORKER, encoding="utf-8")
    monkeypatch.setattr(bridge, "WORKER_SCRIPT", str(script))
    monkeypatch.setattr(bridge, "_proc", None)
    monkeypatch.setattr(bridge, "_ready", False)

    results: list[dict] = []

    def run() -> None:
        for n in range(5):
            results.append(bridge._request({"n": n}))

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout=30)
    try:
        assert not t.is_alive(), "bridge hung — worker stderr is not being drained"
        assert [r.get("n") for r in results] == [0, 1, 2, 3, 4]
        assert "noise" in bridge._stderr_snippet(100)
    finally:
        bridge.stop_worker()
