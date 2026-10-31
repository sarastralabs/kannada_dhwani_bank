"""
Optional cloud speech providers (Sarvam AI) alongside the local open-source models.

Staff choose per stage in the admin console — speech-to-text, translation and
voice — between ``local`` (Whisper / IndicTrans2 / Parler, the default) and
``sarvam``. One Sarvam API key serves all three.

Settings live in ``data/runtime_settings.json`` (gitignored) under ``"cloud"``;
``SARVAM_API_KEY`` in ``.env`` is used when no key was saved from the console.
The pipeline worker re-reads the file when it changes, so no restart is needed.

When a cloud call fails the stage falls back to the local model (unless staff
turned that off) and the error is recorded in ``data/cloud_status.json`` so the
console can say "credits used up — paste a new key". After a key or credit
error the cloud is skipped until the key is replaced; after a network or rate
limit error it is retried after ``BANK_CLOUD_RETRY_S`` seconds (default 30).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from backend import runtime_settings
from backend.cloud.sarvam import TTS_VOICE_DEFAULT, TTS_VOICES, CloudError

__all__ = [
    "STAGES",
    "CloudError",
    "get_config",
    "save_config",
    "public_config",
    "api_key",
    "stage_provider",
    "use_cloud",
    "call_cloud",
    "record_ok",
    "record_error",
]

T = TypeVar("T")

STAGES = ("stt", "translation", "tts")
PROVIDERS = ("local", "sarvam")
_BLOCKING_KINDS = frozenset({"auth", "quota"})

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_status_lock = threading.RLock()
_last_write: dict[str, float] = {}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def _raw() -> dict[str, Any]:
    cloud = runtime_settings.read_all().get("cloud")
    return cloud if isinstance(cloud, dict) else {}


def api_key() -> str:
    saved = str(_raw().get("sarvam_api_key") or "").strip()
    return saved or os.environ.get("SARVAM_API_KEY", "").strip()


def _key_source() -> str:
    if str(_raw().get("sarvam_api_key") or "").strip():
        return "settings"
    if os.environ.get("SARVAM_API_KEY", "").strip():
        return "env"
    return "none"


def key_fingerprint(key: str | None = None) -> str:
    key = api_key() if key is None else key
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12] if key else ""


def get_config() -> dict[str, Any]:
    raw = _raw()
    config: dict[str, Any] = {}
    for stage in STAGES:
        value = str(raw.get(stage) or "local").strip().lower()
        config[stage] = value if value in PROVIDERS else "local"
    voice = str(raw.get("sarvam_voice") or TTS_VOICE_DEFAULT).strip().lower()
    config["sarvam_voice"] = voice if voice in TTS_VOICES else TTS_VOICE_DEFAULT
    config["fallback_local"] = raw.get("fallback_local", True) is not False
    return config


def save_config(changes: dict[str, Any]) -> dict[str, Any]:
    """Validate and merge admin changes. ``sarvam_api_key=""`` removes the saved key."""
    raw = dict(_raw())
    for stage in STAGES:
        if stage in changes and changes[stage] is not None:
            value = str(changes[stage]).strip().lower()
            if value not in PROVIDERS:
                raise ValueError(f"Unknown provider {value!r} for {stage}. Choose local or sarvam.")
            raw[stage] = value
    if changes.get("sarvam_voice") is not None:
        voice = str(changes["sarvam_voice"]).strip().lower()
        if voice not in TTS_VOICES:
            raise ValueError(f"Unknown Sarvam voice {voice!r}.")
        raw["sarvam_voice"] = voice
    if changes.get("fallback_local") is not None:
        raw["fallback_local"] = bool(changes["fallback_local"])
    if changes.get("sarvam_api_key") is not None:
        key = str(changes["sarvam_api_key"]).strip()
        if key and (len(key) < 8 or any(c.isspace() for c in key)):
            raise ValueError("That does not look like a Sarvam API key.")
        if key:
            raw["sarvam_api_key"] = key
        else:
            raw.pop("sarvam_api_key", None)
    runtime_settings.update({"cloud": raw})
    return get_config()


def stage_provider(stage: str) -> str:
    return get_config().get(stage, "local")


# ---------------------------------------------------------------------------
# Status (shared between the API process and the pipeline worker)
# ---------------------------------------------------------------------------
def _status_path() -> str:
    return os.environ.get(
        "BANK_CLOUD_STATUS_FILE",
        os.path.join(_PROJECT_ROOT, "data", "cloud_status.json"),
    )


def read_status() -> dict[str, Any]:
    try:
        with open(_status_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_stage(stage: str, entry: dict[str, Any]) -> None:
    path = _status_path()
    with _status_lock:
        data = read_status()
        data[stage] = entry
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        temporary = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=1)
            os.replace(temporary, path)
        except OSError:
            pass
        _last_write[stage] = time.monotonic()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_ok(stage: str, elapsed_ms: int) -> None:
    previous = read_status().get(stage) or {}
    # Successes only need writing when something changed or once a minute.
    if previous.get("ok") and time.monotonic() - _last_write.get(stage, 0.0) < 60:
        return
    _write_stage(
        stage,
        {
            "ok": True,
            "at": _now_iso(),
            "ms": elapsed_ms,
            "key_fp": key_fingerprint(),
            "kind": None,
            "message": None,
        },
    )


def record_error(stage: str, exc: Exception) -> None:
    kind = exc.kind if isinstance(exc, CloudError) else "server"
    _write_stage(
        stage,
        {
            "ok": False,
            "at": _now_iso(),
            "epoch": time.time(),
            "key_fp": key_fingerprint(),
            "kind": kind,
            "message": str(exc)[:300],
        },
    )
    print(f"[cloud] {stage} sarvam failed kind={kind}: {exc}", file=sys.stderr, flush=True)


def _retry_after_s() -> float:
    try:
        return max(0.0, float(os.environ.get("BANK_CLOUD_RETRY_S", "30")))
    except ValueError:
        return 30.0


def blocked_reason(stage: str) -> str | None:
    """Why the cloud is being skipped for this stage right now (None = usable)."""
    entry = read_status().get(stage) or {}
    if entry.get("ok") is not False:
        return None
    if entry.get("key_fp") != key_fingerprint():
        return None  # the key was replaced since the error — try again
    if entry.get("kind") in _BLOCKING_KINDS:
        return str(entry.get("message") or entry.get("kind"))
    if time.time() - float(entry.get("epoch") or 0) < _retry_after_s():
        return str(entry.get("message") or entry.get("kind"))
    return None


def use_cloud(stage: str) -> bool:
    """True when this stage is set to Sarvam, a key exists and it is not blocked."""
    if stage_provider(stage) != "sarvam":
        return False
    if not api_key():
        return False
    return blocked_reason(stage) is None


def cloud_selected(stage: str) -> bool:
    return stage_provider(stage) == "sarvam"


def call_cloud(stage: str, func: Callable[[str], T]) -> T:
    """Run ``func(api_key)`` and record the outcome. Re-raises on failure."""
    started = time.perf_counter()
    try:
        result = func(api_key())
    except Exception as exc:
        record_error(stage, exc)
        raise
    record_ok(stage, round((time.perf_counter() - started) * 1000))
    return result


def fallback_allowed() -> bool:
    return bool(get_config().get("fallback_local", True))


def unavailable_error(stage: str) -> CloudError:
    """Raised when Sarvam is selected, cannot be used, and local fallback is off."""
    if not api_key():
        return CloudError("auth", f"Sarvam is selected for {stage} but no API key is set")
    reason = blocked_reason(stage) or "unavailable"
    return CloudError("quota", f"Sarvam {stage} is unavailable: {reason}")


def open_source_voice_online() -> bool:
    """Can the open-source voice speak right now? (Remote voice server answering, or none configured.)"""
    from backend.tts.remote_bridge import remote_tts_configured, remote_tts_healthy

    if not remote_tts_configured():
        return True  # the voice runs on this PC
    return remote_tts_healthy(timeout_s=4.0)


# ---------------------------------------------------------------------------
# Admin view (never exposes the key itself)
# ---------------------------------------------------------------------------
def public_config() -> dict[str, Any]:
    config = get_config()
    key = api_key()
    status = read_status()
    fp = key_fingerprint(key)
    stages: dict[str, Any] = {}
    for stage in STAGES:
        entry = status.get(stage) or {}
        current_key = entry.get("key_fp") == fp
        stages[stage] = {
            "provider": config[stage],
            "ok": entry.get("ok") if current_key else None,
            "at": entry.get("at") if current_key else None,
            "ms": entry.get("ms") if current_key else None,
            "error_kind": entry.get("kind") if current_key else None,
            "error": entry.get("message") if current_key else None,
            "using_local_now": config[stage] == "sarvam" and not use_cloud(stage),
        }
    return {
        "provider_name": "Sarvam AI",
        "stages": stages,
        "sarvam_voice": config["sarvam_voice"],
        "voices": list(TTS_VOICES),
        "fallback_local": config["fallback_local"],
        "key_set": bool(key),
        "key_hint": f"…{key[-4:]}" if len(key) >= 8 else ("set" if key else ""),
        "key_source": _key_source(),
        # Speaking can be switched to the open-source voice only while its server is up.
        "open_source_voice_online": open_source_voice_online(),
    }
