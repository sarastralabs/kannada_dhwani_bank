"""
backend/tts/__init__.py

Public API for the TTS (Text-to-Speech) module.

Preferred engine: AI4Bharat Indic Parler-TTS (Suresh / Anu) via isolated
.venv-parler worker. Falls back to facebook/mms-tts-kan if Parler is unavailable.
"""

from __future__ import annotations

import os
import threading
import warnings

import numpy as np
import soundfile as sf

from backend.tts.speaker import KannadaSpeaker, _DEFAULT_MODEL_ID

__all__ = ["synthesise", "synthesise_kannada", "unload_model", "parler_status"]

_speaker: KannadaSpeaker | None = None
_tts_lock = threading.Lock()


def _mms_device() -> str | None:
    """API-process MMS on CPU when warm pipeline worker owns the GPU."""
    forced = os.environ.get("BANK_TTS_DEVICE", "").strip().lower()
    if forced in {"cpu", "cuda"}:
        return forced
    try:
        from backend.pipeline_bridge import worker_enabled

        if worker_enabled():
            return "cpu"
    except Exception:
        pass
    return None


def parler_status(*, fast: bool = False) -> dict:
    from backend.tts.parler_bridge import default_speaker, parler_available, parler_ready, _parler_python
    from backend.tts.remote_bridge import remote_tts_configured, remote_tts_status

    remote = remote_tts_status(fast=fast)
    if remote.get("configured"):
        return {
            "available": True,
            "remote": remote,
            "ready": bool(remote.get("ready")),
            "local_parler": False,
            "local_ready": False,
            "python": None,
            "speaker": default_speaker(),
            "engine_env": os.environ.get("BANK_TTS_ENGINE", "auto"),
        }

    return {
        "available": parler_available(),
        "remote": remote,
        "ready": parler_ready(),
        "local_parler": parler_available(),
        "local_ready": parler_ready(),
        "python": _parler_python(),
        "speaker": default_speaker(),
        "engine_env": os.environ.get("BANK_TTS_ENGINE", "auto"),
    }


def _play_audio(audio: np.ndarray, sr: int) -> None:
    try:
        import sounddevice as sd

        sd.play(audio, sr)
        sd.wait()
    except ImportError:
        warnings.warn(
            "sounddevice not installed -- playback skipped. pip install sounddevice",
            stacklevel=3,
        )
    except Exception as exc:
        warnings.warn("Playback failed: " + str(exc), stacklevel=3)


def _save_audio(audio: np.ndarray, sr: int, output_path: str) -> None:
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    sf.write(output_path, audio, sr)


def cloud_tts_profile(*, backup: bool = False) -> str | None:
    """Cache profile for Sarvam voice output, or None when the local voice is in use.

    ``backup=True``: the open-source voice server is down — use Sarvam if a working key
    exists, whatever Speaking is set to (None when Sarvam cannot be used either).
    """
    from backend import cloud

    if backup:
        if not cloud.api_key() or cloud.blocked_reason("tts") is not None:
            return None
    elif not cloud.cloud_selected("tts"):
        return None
    elif not cloud.use_cloud("tts"):
        if cloud.fallback_allowed():
            return None
        raise cloud.unavailable_error("voice")
    from backend.cloud.sarvam import TTS_MODEL_DEFAULT

    model = os.environ.get("SARVAM_TTS_MODEL", "").strip() or TTS_MODEL_DEFAULT
    return f"sarvam|{model}|{cloud.get_config()['sarvam_voice']}"


def synthesise_kannada_cloud(
    kannada_text: str, *, backup: bool = False
) -> tuple[np.ndarray, int] | None:
    """Sarvam voice for prepared Kannada text, or None to use the local voice."""
    from backend import cloud

    if cloud_tts_profile(backup=backup) is None:
        return None
    from backend.cloud import sarvam

    voice = cloud.get_config()["sarvam_voice"]
    try:
        return cloud.call_cloud(
            "tts",
            lambda key: sarvam.synthesise(key, kannada_text, voice=voice),
        )
    except Exception:
        if backup or cloud.fallback_allowed():
            return None
        raise


def synthesise_kannada(
    kannada_text: str,
    output_path: str | None = None,
    play: bool = False,
    voice_description: str | None = None,
    speaker: str | None = None,
) -> tuple[np.ndarray, int] | None:
    """
    Synthesise from Kannada text.

    Prefer Indic Parler-TTS (Suresh/Anu). MMS only when BANK_TTS_ENGINE=mms/auto
    fallback is allowed — never silently replace Parler when engine=parler.
    """
    if not kannada_text or not kannada_text.strip():
        return None

    from backend.tts.speaker import prepare_kannada_for_tts

    # Parler must also receive digit words — raw "1234567890" is misread.
    kannada_text = prepare_kannada_for_tts(kannada_text)

    cloud_result = synthesise_kannada_cloud(kannada_text)
    if cloud_result is not None:
        if output_path:
            _save_audio(cloud_result[0], cloud_result[1], output_path)
        if play:
            _play_audio(cloud_result[0], cloud_result[1])
        return cloud_result

    selected_speaker = speaker
    if not selected_speaker and voice_description:
        v = voice_description.strip().lower()
        if "anu" in v:
            selected_speaker = "Anu"
        elif "suresh" in v:
            selected_speaker = "Suresh"
    if not selected_speaker:
        try:
            from api.app_settings import get_tts_speaker

            selected_speaker = get_tts_speaker()
        except Exception:
            selected_speaker = os.environ.get("BANK_TTS_SPEAKER", "Suresh")
    if selected_speaker:
        selected_speaker = (
            "Anu" if selected_speaker.strip().lower() == "anu" else "Suresh"
        )

    from backend.tts.parler_bridge import parler_available, synthesise_kannada_parler
    from backend.tts.remote_bridge import remote_tts_configured, synthesise_kannada_remote

    engine = os.environ.get("BANK_TTS_ENGINE", "auto").strip().lower()
    force_parler = engine in {"parler", "indic-parler", "remote"}
    allow_mms = os.environ.get("BANK_TTS_ALLOW_MMS", "1").strip().lower() in {
        "1", "true", "yes", "on",
    }
    allow_mms = allow_mms or engine in {"mms", "mms-tts", "auto", "off", ""}

    # Remote Parler on a second GPU — no local VRAM used on this machine.
    if remote_tts_configured() and engine in {"parler", "indic-parler", "auto", "remote"}:
        try:
            audio, sr = synthesise_kannada_remote(
                kannada_text,
                speaker=selected_speaker,
            )
            if output_path:
                _save_audio(audio, sr, output_path)
            if play:
                _play_audio(audio, sr)
            return audio, sr
        except Exception as exc:
            raise RuntimeError(
                f"Remote Parler TTS failed: {exc}. "
                "Check BANK_TTS_REMOTE_URL, BANK_TTS_REMOTE_KEY, and tts.sarastralabs.com health."
            ) from exc

    if force_parler or parler_available():
        try:
            audio, sr = synthesise_kannada_parler(
                kannada_text,
                speaker=selected_speaker,
            )
            if output_path:
                _save_audio(audio, sr, output_path)
            if play:
                _play_audio(audio, sr)
            return audio, sr
        except Exception as exc:
            if force_parler:
                raise RuntimeError(
                    f"Natural Kannada voice (Parler) failed: {exc}. "
                    "Do not use MMS — fix Parler/GPU, then retry."
                ) from exc
            warnings.warn(
                f"Parler-TTS failed ({exc}); falling back to MMS-TTS",
                stacklevel=2,
            )

    if not allow_mms or force_parler:
        raise RuntimeError(
            "Parler-TTS is required for natural Kannada (BANK_TTS_ENGINE=parler) "
            "but is not available. Check .venv-parler and GPU memory."
        )

    global _speaker
    with _tts_lock:
        if _speaker is None:
            _speaker = KannadaSpeaker(_DEFAULT_MODEL_ID, device=_mms_device())
        return _speaker.synthesise_kannada(
            kannada_text,
            output_path=output_path,
            play=play,
        )


def synthesise(
    english_text: str,
    output_path: str | None = None,
    play: bool = False,
    voice_description: str | None = None,
) -> tuple[np.ndarray, int] | None:
    """
    Translate English → Kannada, then synthesise with Parler (natural Kannada).
    """
    if not english_text or not english_text.strip():
        return None

    from backend.translation import translate_en_to_kn, unload_model as unload_translation
    import gc
    import re

    parts = re.split(r"(?<=[.!?])\s+", english_text.strip())
    sentences = [p.strip() for p in parts if p.strip()] or [english_text.strip()]

    # Translate first (IndicTrans on GPU), then free VRAM for Parler worker.
    kannada_lines: list[str] = []
    for sentence in sentences:
        kannada = translate_en_to_kn(sentence)
        if kannada and kannada.strip():
            kannada_lines.append(kannada.strip())

    engine = os.environ.get("BANK_TTS_ENGINE", "parler").strip().lower()
    from backend.tts.remote_bridge import remote_tts_configured

    if engine in {"parler", "indic-parler", "auto"} and not remote_tts_configured():
        try:
            unload_translation("all")
        except Exception:
            pass
        try:
            import torch

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    audio_parts: list[np.ndarray] = []
    sr_out = 22050
    silence = None

    for kannada in kannada_lines:
        result = synthesise_kannada(
            kannada,
            play=False,
            voice_description=voice_description,
        )
        if result is None:
            continue
        audio, sr_out = result
        if silence is None:
            silence = np.zeros(int(0.35 * sr_out), dtype=np.float32)
        audio_parts.append(audio)
        if len(kannada_lines) > 1:
            audio_parts.append(silence)

    if not audio_parts:
        return None
    if len(kannada_lines) > 1 and audio_parts:
        audio_parts = audio_parts[:-1]

    audio = np.concatenate(audio_parts)
    if output_path:
        _save_audio(audio, sr_out, output_path)
    if play:
        _play_audio(audio, sr_out)
    return audio, sr_out


def unload_model() -> None:
    """Release MMS speaker + stop Parler worker."""
    import gc

    import torch

    from backend.tts.parler_bridge import stop_worker

    global _speaker
    _speaker = None
    stop_worker()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
