"""Kiosk -> TTS box: a 429 "busy" answer is retried, not turned into silence."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class _Box(BaseHTTPRequestHandler):
    busy_left = 0
    calls = 0

    def do_POST(self) -> None:  # noqa: N802
        type(self).calls += 1
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if type(self).busy_left > 0:
            type(self).busy_left -= 1
            body, code = {"detail": "TTS is busy; retry this request shortly"}, 429
        else:
            body, code = {"audio_b64": "UklGRg==", "timing": {"cache_hit": False}}, 200
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args) -> None:
        pass


@pytest.fixture()
def box(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Box)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("BANK_TTS_REMOTE_URL", f"http://127.0.0.1:{server.server_port}")
    _Box.calls = 0
    yield _Box
    server.shutdown()


def test_busy_is_retried_until_free(box, monkeypatch) -> None:
    from backend.tts import remote_bridge

    monkeypatch.setattr(remote_bridge.time, "sleep", lambda s: None)
    box.busy_left = 2
    out = remote_bridge._request("POST", "/api/speak-kannada", {"text": "ಹೌದು"})
    assert out["audio_b64"] == "UklGRg=="
    assert box.calls == 3


def test_busy_gives_up_after_wait_budget(box, monkeypatch) -> None:
    from backend.tts import remote_bridge

    monkeypatch.setenv("BANK_TTS_BUSY_WAIT_S", "0")
    box.busy_left = 99
    with pytest.raises(RuntimeError, match="429"):
        remote_bridge._request("POST", "/api/speak-kannada", {"text": "ಹೌದು"})
    assert box.calls == 1
