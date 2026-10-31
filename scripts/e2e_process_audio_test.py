"""E2E: existing Kannada wav -> pipeline oneshot + /api/process-audio."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

os.environ.setdefault("BANK_TTS_ENGINE", "auto")
os.environ.setdefault("BANK_TTS_ALLOW_MMS", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from backend.pipeline_bridge import _extract_json_payload, stop_worker  # noqa: E402

API = os.environ.get("BANK_API", "http://127.0.0.1:8000")
WAV = os.path.abspath(
    os.environ.get(
        "BANK_E2E_WAV",
        os.path.join("data", "stt_test_audio", "clip_001.wav"),
    )
)


def post_audio(path: str) -> dict:
    with open(path, "rb") as f:
        raw = f.read()
    boundary = "----WebKitFormBoundaryE2E"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="audio"; filename="ask.wav"\r\n',
            b"Content-Type: audio/wav\r\n\r\n",
            raw,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    req = urllib.request.Request(
        f"{API}/api/process-audio",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


def main() -> None:
    if not os.path.isfile(WAV):
        raise SystemExit(f"missing wav: {WAV}")

    stop_worker()
    print("=== oneshot ===")
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, "run_pipeline_subprocess.py", WAV],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "BANK_PIPELINE_KEEP_LOADED": "0"},
    )
    if proc.returncode != 0 or not (proc.stdout or "").strip():
        err_tail = (proc.stderr or "")[-1500:]
        print("oneshot_rc", proc.returncode)
        print("oneshot_stderr_tail", err_tail)
        raise SystemExit("oneshot failed (empty/invalid stdout)")
    data = _extract_json_payload(proc.stdout)
    print("elapsed", round(time.time() - t0, 1), "rc", proc.returncode)
    print("error", data.get("error"))
    print("en", (data.get("english_text") or "")[:120])
    print("intent", data.get("intent"), "route", data.get("route"))
    print("resp", (data.get("response_text") or "")[:140])
    print("audio_len", len(data.get("audio_b64") or ""))
    print("stages", data.get("stage_times"), "total", data.get("total_time_s"))

    print("=== api ===")
    t1 = time.time()
    try:
        api = post_audio(WAV)
    except Exception as exc:
        print("API_FAIL", type(exc).__name__, exc)
        if hasattr(exc, "read"):
            print(exc.read()[:500])
        raise SystemExit(1)
    print("api_elapsed", round(time.time() - t1, 1))
    print("error", api.get("error"))
    print("intent", api.get("intent"), "route", api.get("route"))
    print("resp", (api.get("response_text") or "")[:140])
    print("audio_len", len(api.get("audio_b64") or ""))
    print("stages", api.get("stage_times"), "total", api.get("total_time_s"))
    ok = (
        not api.get("error")
        and bool(api.get("intent"))
        and bool(api.get("response_text"))
        and bool(api.get("audio_b64"))
    )
    print("E2E_MODEL_REPLY", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
