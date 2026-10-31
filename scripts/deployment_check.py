"""
Deployment verification — run on ANY machine before demo.

Checks files, models, Python deps, ports, and (if API is up) live endpoints.
Compare output between your working PC and the problem deployment.

    py -3.12 scripts/deployment_check.py
    py -3.12 scripts/deployment_check.py --api http://127.0.0.1:8000
    py -3.12 scripts/deployment_check.py --full   # includes slow pipeline test
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

_STT_DIRS = {
    "vasista-medium": "models/whisper-kannada-medium-ct2",
    "specialized": "models/whisper-medium-vaani-ct2",
    "baseline": "models/whisper-medium-ct2",
}
_STT_MODEL = os.environ.get("BANK_STT_MODEL", "vasista-medium").strip() or "vasista-medium"
_STT_DIR = _STT_DIRS.get(_STT_MODEL, _STT_DIRS["vasista-medium"])

# ── Required on-disk assets (git may not include large models) ───────────────
REQUIRED_PATHS: list[tuple[str, str, str]] = [
    ("STT (Kannada)", f"{_STT_DIR}/model.bin", f"Run: py -3.12 backend/stt/convert_models.py --model {_STT_MODEL}"),
    ("STT config", f"{_STT_DIR}/config.json", "Same as above"),
    ("NLU model", "models/nlu-distilbert/config.json", "Run: py -3.12 backend/nlu/train.py"),
    ("Demo accounts", "data/demo_accounts.json", "Should exist in repo"),
    ("Forms", "data/forms.json", "Should exist in repo"),
    ("Test audio", "data/stt_test_audio/clip_001.wav", "Optional but needed for pipeline test"),
    ("Env file", ".env", "Copy from .env.example and set BANK_TTS_ENGINE=mms"),
]

OPTIONAL_PATHS: list[tuple[str, str]] = [
    ("Parler venv", ".venv-parler/Scripts/python.exe"),
    ("Frontend deps", "frontend/node_modules/vite/package.json"),
]


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def _file_ok(rel: str, min_bytes: int = 1) -> tuple[bool, str]:
    path = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.isfile(path):
        return False, "missing"
    size = os.path.getsize(path)
    if size < min_bytes:
        return False, f"too small ({size} B)"
    if rel.endswith("model.bin") and size < 300_000_000:
        return False, f"suspicious size ({size // (1024*1024)} MB, expect ~370–420 MB)"
    return True, f"OK ({size // 1024} KB)" if size < 10_000_000 else f"OK ({size // (1024*1024)} MB)"


def _user_agent() -> str:
    """Same UA as the kiosk: Cloudflare rejects urllib's default with 403."""
    ua = os.environ.get("BANK_TTS_REMOTE_USER_AGENT", "").strip()
    env_path = os.path.join(ROOT, ".env")
    if not ua and os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as f:
            for ln in f:
                if ln.startswith("BANK_TTS_REMOTE_USER_AGENT="):
                    ua = ln.split("=", 1)[1].strip().strip('"')
    return ua or "SarastraBankAssistant/1.0"


def _get(url: str, timeout: float = 10) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify deployment on this machine")
    parser.add_argument("--api", default=os.environ.get("BANK_API", "http://127.0.0.1:8000"))
    # Default: BANK_TTS_URL, else the kiosk's BANK_TTS_REMOTE_URL from .env, else local :8001.
    parser.add_argument("--tts", default=None)
    parser.add_argument("--full", action="store_true", help="Run slow API pipeline test")
    args = parser.parse_args()
    api = args.api.rstrip("/")
    tts = (args.tts or os.environ.get("BANK_TTS_URL", "")).rstrip("/")
    failed: list[str] = []
    warns: list[str] = []

    def check(name: str, ok: bool, detail: str = "", *, warn: bool = False) -> None:
        if ok:
            mark = "PASS"
        elif warn:
            mark = "WARN"
        else:
            mark = "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
        if not ok and not warn:
            failed.append(name)
        elif not ok and warn:
            warns.append(name)

    print("\n=== Deployment check ===")
    print(f"  Machine : {os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', '?'))}")
    print(f"  Root    : {ROOT}")
    print(f"  Python  : {sys.version.split()[0]}")
    print(f"  API URL : {api}")
    print(f"  TTS URL : {tts}\n")

    # ── Python version ───────────────────────────────────────────────────────
    print("Runtime:")
    v = sys.version_info
    check("Python 3.12+", v.major == 3 and v.minor >= 12, f"{v.major}.{v.minor}.{v.micro}")

    try:
        import torch  # noqa: F401

        cuda = torch.cuda.is_available()
        if cuda:
            name = torch.cuda.get_device_name(0)
            mem = torch.cuda.get_device_properties(0).total_memory // (1024**2)
            check("CUDA GPU", True, f"{name}, {mem} MB VRAM")
            if mem < 6000:
                warns.append("low_vram")
                print("  [WARN] GPU < 6 GB — use BANK_TTS_ENGINE=mms, expect slower first turn")
        else:
            check("CUDA GPU", False, "not available — pipeline will use CPU (very slow)", warn=True)
    except ImportError:
        check("PyTorch", False, "not installed — pip install -r requirements.txt")

    # ── Files & models ───────────────────────────────────────────────────────
    print("\nRequired files:")
    for label, rel, fix in REQUIRED_PATHS:
        ok, detail = _file_ok(rel)
        check(label, ok, detail if ok else f"{detail}. Fix: {fix}")

    print("\nOptional:")
    for label, rel in OPTIONAL_PATHS:
        ok, detail = _file_ok(rel)
        check(label, ok, detail if ok else "not found (OK if not using Parler/frontend yet)", warn=not ok)

    greet_dir = os.path.join(ROOT, "data", "greetings")
    greet_wavs = [
        f for f in os.listdir(greet_dir) if f.endswith(".wav")
    ] if os.path.isdir(greet_dir) else []
    greet_ok = len(greet_wavs) >= 4
    check(
        "Greeting audio cache",
        greet_ok,
        f"{len(greet_wavs)} WAV(s) in data/greetings/"
        if greet_ok
        else "missing — run: py -3.12 scripts/warm_greetings.py --first-only",
        warn=not greet_ok,
    )

    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(ROOT, ".env"))
        from backend.db.store import mongo_enabled, ping_mongo

        if mongo_enabled():
            check("MongoDB Atlas", ping_mongo(), "connected" if ping_mongo() else "connection failed")
        else:
            check("MongoDB Atlas", False, "MONGODB_URI not set (optional)", warn=True)
    except Exception as exc:
        check("MongoDB Atlas", False, str(exc), warn=True)

    # ── .env keys (values hidden) ────────────────────────────────────────────
    print("\nEnvironment (.env):")
    env_path = os.path.join(ROOT, ".env")
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
        keys = {ln.split("=", 1)[0].strip() for ln in lines if "=" in ln}
        for key in ("BANK_TTS_ENGINE", "BANK_PIPELINE_WORKER", "BANK_TTS_ALLOW_MMS", "BANK_TTS_REMOTE_URL"):
            check(f".env {key}", key in keys, "set" if key in keys else "missing — add to .env", warn=key not in keys)
        remote_url = next((ln.split("=", 1)[1].strip() for ln in lines if ln.startswith("BANK_TTS_REMOTE_URL=")), "")
        if remote_url:
            print(f"  [INFO] Remote TTS: {remote_url} — start TTS box before API")
            if not tts:
                tts = remote_url.rstrip("/")
        # Separate name: this used to overwrite the TTS URL with the engine name,
        # so the live check always probed "auto/api/health".
        tts_engine = next((ln.split("=", 1)[1].strip() for ln in lines if ln.startswith("BANK_TTS_ENGINE=")), "")
        if tts_engine and tts_engine.lower() == "parler":
            print("  [WARN] BANK_TTS_ENGINE=parler needs .venv-parler + HF model; use mms for stable demo")
    else:
        check(".env file", False, "copy .env.example → .env")

    # ── Ports ────────────────────────────────────────────────────────────────
    print("\nPorts (is something listening?):")
    for port, label in [(8000, "API"), (8001, "TTS"), (5173, "Agent UI"), (5174, "Admin UI")]:
        open_ = _port_open("127.0.0.1", port)
        check(f"Port {port} ({label})", open_, "listening" if open_ else "not open — start service", warn=port == 8001 and not open_)

    # ── Live TTS (if up) ─────────────────────────────────────────────────────
    print("\nLive TTS:")
    tts = tts or "http://127.0.0.1:8001"
    print(f"  [INFO] Checking TTS at {tts}")
    tts_up = False
    try:
        th = _get(f"{tts}/api/health", timeout=8)
        tts_up = th.get("ready") is True or th.get("status") in {"ready", "ok"}
        detail = f"status={th.get('status')} ready={th.get('ready')}"
        check("GET TTS /api/health", th.get("parler") or th.get("service") == "tts", detail)
        check("TTS ready (Parler warmed)", th.get("ready") is True or th.get("status") == "ready",
              "warming — wait for [tts-server] Ready log", warn=not tts_up)
    except Exception as exc:
        check("GET TTS /api/health", False, str(exc), warn=True)
        print("  Start TTS first: powershell -ExecutionPolicy Bypass -File .\\scripts\\run_tts_server.ps1")

    # ── Live API (if up) ─────────────────────────────────────────────────────
    print("\nLive API:")
    api_up = False
    try:
        h = _get(f"{api}/api/health", timeout=12)
        api_up = h.get("status") in {"ok", "warming", "degraded"}
        check("GET /api/health", api_up, f"status={h.get('status')}")
        remote = (h.get("tts") or {}).get("remote") or {}
        if remote.get("configured"):
            check(
                "Remote TTS reachable",
                remote.get("healthy"),
                f"ready={remote.get('ready')} url={remote.get('url')}",
                warn=not remote.get("ready"),
            )
    except Exception as exc:
        check("GET /api/health", False, str(exc))
        print("\n  Start API on target machine:")
        print("    cd", ROOT)
        print("    py -3.12 -m uvicorn api.main:app --host 0.0.0.0 --port 8000")
        print("  Wait 60s, then re-run this script.\n")

    if api_up:
        try:
            s = _get(f"{api}/api/kiosk/status", timeout=5)
            check("GET /api/kiosk/status", "running" in s)
        except Exception as exc:
            check("GET /api/kiosk/status", False, str(exc))

        try:
            speak = _get(f"{api}/api/health")  # already ok
            del speak
            body = json.dumps({"text": "ಪರೀಕ್ಷೆ"}).encode()
            req = urllib.request.Request(
                f"{api}/api/speak-kannada",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read())
            b64 = data.get("audio_b64") or ""
            check("POST /api/speak-kannada", len(b64) > 500, f"{len(b64)} bytes b64")
        except Exception as exc:
            detail = str(exc)
            if isinstance(exc, urllib.error.HTTPError):
                detail = exc.read().decode()[:180]
            check("POST /api/speak-kannada", False, detail)

        if args.full:
            wav = os.path.join(ROOT, "data", "stt_test_audio", "clip_001.wav")
            if os.path.isfile(wav):
                try:
                    with open(wav, "rb") as wf:
                        audio_bytes = wf.read()
                    boundary = "----DeployCheck"
                    body = (
                        f"--{boundary}\r\n"
                        'Content-Disposition: form-data; name="audio"; filename="clip_001.wav"\r\n'
                        "Content-Type: audio/wav\r\n\r\n"
                    ).encode() + audio_bytes + f"\r\n--{boundary}--\r\n".encode()
                    req = urllib.request.Request(
                        f"{api}/api/process-audio",
                        data=body,
                        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=180) as resp:
                        data = json.loads(resp.read())
                    check(
                        "POST /api/process-audio (balance intent)",
                        not data.get("error") and data.get("intent") == "check_balance",
                        data.get("error") or f"intent={data.get('intent')}",
                    )
                except Exception as exc:
                    detail = str(exc)
                    if isinstance(exc, urllib.error.HTTPError):
                        detail = exc.read().decode()[:180]
                    check("POST /api/process-audio", False, detail)
            else:
                print("  [SKIP] full pipeline — no clip_001.wav")

    # ── Compare hint ─────────────────────────────────────────────────────────
    print("\n--- If this machine FAILs but your PC PASSes ---")
    print("  1. Missing models/ folder — copy from working PC or run convert_models.py + train.py")
    print("  2. Old API still running — only ONE uvicorn on port 8000")
    print("  3. .env different — set BANK_TTS_ENGINE=mms on both")
    print("  4. GPU OOM — close other apps; use 4GB-safe mms + single API")
    print("  5. Frontend without API — phone shows offline; start API with --host 0.0.0.0")
    print("  6. Firewall — allow 8000, 5173, 5174 on Private network")
    print("\n  Save this output and compare:")
    print("    py -3.12 scripts/deployment_check.py --full > deploy-check.txt")

    print(f"\n=== {'ALL PASS' if not failed else f'{len(failed)} FAILURE(S)'} ===")
    if warns:
        print(f"  ({len(warns)} warning(s))")
    for f in failed:
        print(f"  - {f}")
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
