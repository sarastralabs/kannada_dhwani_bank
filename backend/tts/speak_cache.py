"""Single-flight Kannada TTS cache with privacy-safe static disk persistence."""

from __future__ import annotations

import base64
import hashlib
import io
import os
import sys
import threading
import time
from typing import Callable

_CACHE: dict[str, str] = {}
_CACHE_LOCK = threading.RLock()
_KEY_LOCKS = tuple(threading.Lock() for _ in range(64))


def _disk_cache_dir() -> str:
    configured = os.environ.get("BANK_TTS_DISK_CACHE_DIR", "").strip()
    if configured:
        return os.path.abspath(configured)
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return os.path.join(project_root, "data", "tts_cache")


def _max_cache_entries() -> int:
    try:
        return max(32, int(os.environ.get("BANK_TTS_CACHE_MAX", "160")))
    except ValueError:
        return 160


def _cache_key(text: str, speaker: str | None = None, profile: str | None = None) -> str:
    version = os.environ.get("BANK_TTS_CACHE_VERSION", "v1").strip()
    if profile:
        # Cloud voices (e.g. "sarvam|bulbul:v3|shubh") never share clips with Parler.
        payload = f"{version}\0{profile}\0{(text or '').strip()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    sp = (speaker or os.environ.get("BANK_TTS_SPEAKER", "")).strip()
    engine = os.environ.get("BANK_TTS_ENGINE", "auto").strip().lower()
    model = os.environ.get("BANK_PARLER_MODEL", "ai4bharat/indic-parler-tts").strip()
    settings = "|".join(
        (
            os.environ.get("BANK_PARLER_DTYPE", "fp16").strip(),
            os.environ.get("BANK_PARLER_DO_SAMPLE", "1").strip(),
            os.environ.get("BANK_PARLER_TEMPERATURE", "0.9").strip(),
            os.environ.get("BANK_PARLER_MAX_NEW_TOKENS", "1500").strip(),
            os.environ.get("BANK_PARLER_MIN_NEW_TOKENS", "280").strip(),
            os.environ.get("BANK_PARLER_TOKENS_PER_CHAR", "40").strip(),
            os.environ.get("BANK_TTS_SPEAKER_REVISION", "v1").strip(),
            os.environ.get("BANK_TTS_TRIM_REVISION", "v1").strip(),
        )
    )
    payload = f"{version}\0{engine}\0{model}\0{settings}\0{sp}\0{(text or '').strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _wav_too_short(raw: bytes, min_s: float = 0.12) -> bool:
    """
    True for empty / near-silent-length clips. Parler occasionally ends a phrase
    immediately (1-sample WAV); caching that would make the phrase silent forever.
    """
    if len(raw) < 44 or raw[:4] != b"RIFF":
        return True
    try:
        import soundfile as sf

        info = sf.info(io.BytesIO(raw))
        return info.frames < info.samplerate * min_s
    except Exception:
        return True


def get_cached_b64(
    text: str,
    *,
    speaker: str | None = None,
    profile: str | None = None,
) -> str | None:
    if not text or not text.strip():
        return None
    key = _cache_key(text, speaker, profile)
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
    if hit:
        return hit

    path = os.path.join(_disk_cache_dir(), f"{key}.wav")
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        if _wav_too_short(raw):
            return None
        hit = base64.b64encode(raw).decode("ascii")
        with _CACHE_LOCK:
            _CACHE[key] = hit
        return hit
    except OSError:
        return None


def put_cached_b64(
    text: str,
    audio_b64: str,
    *,
    speaker: str | None = None,
    persist: bool = False,
    profile: str | None = None,
) -> None:
    if not text.strip() or not audio_b64:
        return
    try:
        raw = base64.b64decode(audio_b64, validate=True)
    except ValueError:
        return
    if _wav_too_short(raw):
        print(
            f"[tts-cache] not caching empty/too-short audio for {len(text)}-char text",
            file=sys.stderr,
            flush=True,
        )
        return
    key = _cache_key(text, speaker, profile)
    max_entries = _max_cache_entries()
    with _CACHE_LOCK:
        if key not in _CACHE and len(_CACHE) >= max_entries:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = audio_b64

    # Only static prompts opt in. Dynamic account/name/balance speech must not
    # be retained on disk.
    if not persist:
        return
    try:
        cache_dir = _disk_cache_dir()
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"{key}.wav")
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "wb") as handle:
            handle.write(raw)
        os.replace(tmp, path)
    except (OSError, ValueError):
        return


def _key_lock(key: str) -> threading.Lock:
    return _KEY_LOCKS[int(key[:8], 16) % len(_KEY_LOCKS)]


class _RemoteVoiceFailed(Exception):
    """The open-source voice server did not answer — try the Sarvam backup outside the lock."""


def _cloud_to_b64(
    text: str, *, persist: bool, bypass_cache: bool, backup: bool = False
) -> str | None:
    """Sarvam voice (cached under its own profile), or None to use the local voice."""
    from backend.tts import cloud_tts_profile, synthesise_kannada_cloud

    profile = cloud_tts_profile(backup=backup)
    if profile is None:
        return None
    if not bypass_cache:
        hit = get_cached_b64(text, profile=profile)
        if hit:
            print("[tts] cloud cache_hit=1", file=sys.stderr, flush=True)
            return hit
    key = _cache_key(text, profile=profile)
    with _key_lock(key):
        if not bypass_cache:
            hit = get_cached_b64(text, profile=profile)
            if hit:
                return hit
        started = time.perf_counter()
        result = synthesise_kannada_cloud(text, backup=backup)
        if result is None:
            return None  # Sarvam failed — caller falls back to the local voice
        audio, sr = result
        from backend.tts.audio_util import trim_trailing_silence

        audio = trim_trailing_silence(audio, sr)
        import soundfile as sf

        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        put_cached_b64(text, b64, persist=persist, profile=profile)
        print(
            f"[tts] sarvam synthesis_ms={round((time.perf_counter() - started) * 1000)}",
            file=sys.stderr,
            flush=True,
        )
        return b64


def kannada_to_b64(
    text: str,
    *,
    speaker: str | None = None,
    free_vram: Callable[[], None] | None = None,
    persist: bool = False,
    bypass_cache: bool = False,
) -> str:
    """Synthesise Kannada text with memory cache and optional static disk cache."""
    text = (text or "").strip()
    if not text:
        return ""

    from backend.tts.remote_bridge import remote_tts_configured, remote_tts_healthy
    from backend.tts.speaker import prepare_kannada_for_tts

    # Normalize before cache lookup so "1234…" and spoken Kannada share one clip.
    text = prepare_kannada_for_tts(text)

    engine = os.environ.get("BANK_TTS_ENGINE", "mms").strip().lower()
    from backend.tts.parler_bridge import parler_available

    use_parler = engine in {"parler", "indic-parler"} or (
        engine == "auto" and parler_available()
    )

    if not speaker:
        try:
            from api.app_settings import get_tts_speaker

            speaker = get_tts_speaker()
        except Exception:
            speaker = os.environ.get("BANK_TTS_SPEAKER", "Suresh")
    speaker = "Anu" if str(speaker).strip().lower() == "anu" else "Suresh"

    cloud_b64 = _cloud_to_b64(text, persist=persist, bypass_cache=bypass_cache)
    if cloud_b64:
        return cloud_b64

    if not bypass_cache:
        hit = get_cached_b64(
            text,
            speaker=speaker if (use_parler or remote_tts_configured()) else None,
        )
        if hit:
            print("[tts] cache_hit=1", file=sys.stderr, flush=True)
            return hit

    uses_remote = remote_tts_configured() and engine in {"parler", "indic-parler", "auto", "remote"}

    def _sarvam_backup(reason: str) -> str | None:
        b64 = _cloud_to_b64(text, persist=persist, bypass_cache=bypass_cache, backup=True)
        if b64:
            print(f"[tts] voice server {reason} — Sarvam voice used", file=sys.stderr, flush=True)
        return b64

    # Voice server down → speak with Sarvam (if a key works) instead of failing.
    if uses_remote and not remote_tts_healthy(timeout_s=4.0):
        b64 = _sarvam_backup("offline")
        if b64:
            return b64

    try:
        return _synthesise_locked(
            text,
            speaker=speaker,
            use_parler=use_parler,
            uses_remote=uses_remote,
            free_vram=free_vram,
            persist=persist,
            bypass_cache=bypass_cache,
        )
    except _RemoteVoiceFailed as failed:
        b64 = _sarvam_backup("failed")
        if b64:
            return b64
        raise failed.__cause__ or failed


def _synthesise_locked(
    text: str,
    *,
    speaker: str,
    use_parler: bool,
    uses_remote: bool,
    free_vram: Callable[[], None] | None,
    persist: bool,
    bypass_cache: bool,
) -> str:
    from backend.tts.remote_bridge import fetch_kannada_b64_remote, remote_tts_configured

    key = _cache_key(
        text,
        speaker=speaker if (use_parler or remote_tts_configured()) else None,
    )
    started = time.perf_counter()
    with _key_lock(key):
        # Concurrent prompt warm-up requests share one synthesis.
        if not bypass_cache:
            hit = get_cached_b64(
                text,
                speaker=speaker if (use_parler or remote_tts_configured()) else None,
            )
            if hit:
                return hit

        # Split deploy: kiosk must use remote GPU box — never load local Parler here.
        if uses_remote:
            print(
                f"[tts] remote speak → {os.environ.get('BANK_TTS_REMOTE_URL', '').rstrip('/')} "
                f"speaker={speaker}",
                file=sys.stderr,
                flush=True,
            )
            try:
                b64 = fetch_kannada_b64_remote(text, speaker=speaker)
                if not b64:
                    raise RuntimeError(
                        "Remote TTS returned empty audio. Check the configured TTS health endpoint."
                    )
            except Exception as exc:
                raise _RemoteVoiceFailed(str(exc)) from exc
            put_cached_b64(text, b64, speaker=speaker, persist=persist)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            print(
                f"[tts] cache_hit=0 synthesis_ms={elapsed_ms} persist={int(persist)}",
                file=sys.stderr,
                flush=True,
            )
            return b64

        if use_parler and free_vram is not None:
            free_vram()

        from backend.tts import synthesise_kannada

        result = synthesise_kannada(text, speaker=speaker)
        if result is None:
            return ""

        audio, sr = result
        from backend.tts.audio_util import trim_trailing_silence

        audio = trim_trailing_silence(audio, sr)
        buf = io.BytesIO()
        import soundfile as sf

        sf.write(buf, audio, sr, format="WAV")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        put_cached_b64(
            text,
            b64,
            speaker=speaker if use_parler else None,
            persist=persist,
        )
        return b64


def prewarm_phrases(
    phrases: tuple[str, ...] | list[str],
    *,
    speaker: str,
    free_vram: Callable[[], None] | None = None,
) -> int:
    """Pre-synthesise common phrases; returns count cached."""
    n = 0
    for phrase in phrases:
        if not phrase or not phrase.strip():
            continue
        if get_cached_b64(phrase, speaker=speaker):
            n += 1
            continue
        if kannada_to_b64(
            phrase,
            speaker=speaker,
            free_vram=free_vram,
            persist=True,
        ):
            n += 1
    return n
