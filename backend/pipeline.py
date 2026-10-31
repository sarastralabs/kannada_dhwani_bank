"""
backend/pipeline.py

Sequential pipeline: Kannada audio -> Kannada + English text + spoken Kannada response.

Memory management
-----------------
By default each model is loaded, used, then unloaded (low peak RAM).

Set BANK_PIPELINE_KEEP_LOADED=1 (used by the warm pipeline worker) to keep
models resident across turns — much lower latency after the first request.

Pipeline stages:
    1. STT        load -> transcribe -> UNLOAD
    2. Translation load -> translate_kn_to_en -> UNLOAD
    3. NLU + Router  load -> classify + route (kept together, both lightweight once loaded)
                            -> UNLOAD NLU
    4. TTS        load -> synthesise(response_text) -> UNLOAD
                  Router returns English response_text; pipeline.py passes it to
                  synthesise() as-is. MMS-TTS (facebook/mms-tts-kan) is Kannada-only,
                  so translation does NOT happen in this file — it happens inside
                  synthesise() (backend/tts/speaker.py):
                      Router (English response_text)
                          -> synthesise()
                              split sentences
                              -> translate_en_to_kn() per sentence
                              -> MMS-TTS
                              -> audio

Each stage's model is guaranteed gone before the next stage loads.
The router has no model, so it costs nothing.

Usage
-----
    from backend.pipeline import run_pipeline

    result = run_pipeline("data/stt_test_audio/clip_001.wav")
    print(result.intent)             # "check_balance"
    print(result.response_text)      # "Real-time balance lookup..."
    # result.audio is a (numpy_array, sample_rate) tuple
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from backend.dialog_context import DialogContext, parse_dialog_context


@dataclass
class PipelineResult:
    """Structured result from one full pipeline run."""
    audio_path:     str = ""
    kannada_text:   str = ""       # STT output
    english_text:   str = ""       # Translation output
    intent:         str = ""       # NLU output
    confidence:     float = 0.0    # NLU confidence
    route:          str = ""       # "informational" or "transactional"
    response_text:  str = ""       # Decision Router output (English)
    required_fields: list = field(default_factory=list)  # transactional only
    form_id:        str = ""       # voice-fill form id when transactional
    form_menu:      list = field(default_factory=list)  # form picker items
    response_text_kn: str = ""     # Kannada TTS when set (skips En→Kn in TTS)
    prefill:        dict = field(default_factory=dict)  # form field prefill hints
    clarify_candidates: list = field(default_factory=list)
    audio:          Optional[tuple[np.ndarray, int]] = None  # TTS output
    audio_output_path: str = ""     # Where the generated wave file was written, if any
    stage_times:    dict = field(default_factory=dict)
    total_time_s:   float = 0.0
    error:          Optional[str] = None


def _write_audio_to_disk(audio: Optional[tuple[np.ndarray, int]], output_path: str) -> str:
    """Write a numpy audio tuple to disk as a .wav file and return the saved path."""
    if audio is None:
        return ""

    audio_array, sample_rate = audio
    abs_output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)

    import soundfile as sf  # noqa: PLC0415

    sf.write(abs_output_path, audio_array, sample_rate)
    return abs_output_path


def _extract_account_hint(kannada: str, english: str) -> str:
    from backend.forms.kannada_digits import extract_digits_from_kannada

    for text in (english, kannada):
        digits = extract_digits_from_kannada(text)
        if len(digits) >= 8:
            return digits
    return ""


def run_pipeline(
    audio_path: str,
    output_dir: str | None = None,
    output_name: str | None = None,
    context: DialogContext | dict[str, Any] | None = None,
    *,
    synthesise_audio: bool = True,
) -> PipelineResult:
    """
    Run the complete voice banking pipeline on a single .wav file.

    Each stage explicitly unloads its model before the next stage begins,
    keeping peak memory at single-model level.

    Parameters
    ----------
    audio_path:
        Path to a .wav audio file containing Kannada speech.

    Returns
    -------
    PipelineResult
        All intermediate and final outputs. Check result.error for failures.
        ``response_text`` is English (from the Decision Router).
        ``audio`` is Kannada speech: ``synthesise()`` translates En→Kn
        internally (split sentences → ``translate_en_to_kn()`` → MMS-TTS)
        before returning the waveform.
    """
    result = PipelineResult(audio_path=audio_path)
    ctx = (
        context
        if isinstance(context, DialogContext)
        else parse_dialog_context(context if isinstance(context, dict) else None)
    )
    default_output_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "tts_output")
    )
    output_dir = output_dir or default_output_dir
    t_total = time.perf_counter()
    keep_loaded = os.environ.get("BANK_PIPELINE_KEEP_LOADED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    def _maybe_unload(fn, *args) -> None:
        if keep_loaded:
            return
        try:
            fn(*args)
        except Exception:
            pass

    # ── Stage 1: STT ─────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    _unload_stt = None
    try:
        from backend.stt import transcribe, unload_model as _unload_stt
        result.kannada_text = transcribe(audio_path, beam_size=3)
    except Exception as exc:
        result.error = "STT failed: " + str(exc)
        result.total_time_s = round(time.perf_counter() - t_total, 2)
        return result
    finally:
        if _unload_stt is not None:
            _maybe_unload(_unload_stt)
    result.stage_times["stt"] = round(time.perf_counter() - t0, 2)

    if not result.kannada_text.strip():
        result.error = "STT returned empty (silent audio)"
        result.total_time_s = round(time.perf_counter() - t_total, 2)
        return result

    # ── Stage 2: Translation (Kannada -> English) ─────────────────────────────
    t0 = time.perf_counter()
    _unload_trans = None
    try:
        from backend.translation import translate_kn_to_en, unload_model as _unload_trans
        result.english_text = translate_kn_to_en(result.kannada_text)
    except Exception as exc:
        result.error = "Translation failed: " + str(exc)
        result.total_time_s = round(time.perf_counter() - t_total, 2)
        return result
    finally:
        if _unload_trans is not None:
            _maybe_unload(_unload_trans, "kn_to_en")
    result.stage_times["translation"] = round(time.perf_counter() - t0, 2)

    if not result.english_text.strip():
        result.error = "Translation returned empty"
        result.total_time_s = round(time.perf_counter() - t_total, 2)
        return result

    # ── Stage 3: NLU + Router (or form menu) ─────────────────────────────────
    t0 = time.perf_counter()
    _unload_nlu = None
    try:
        from backend.forms.form_menu import (
            build_form_menu_payload,
            is_form_menu_request,
            match_form_from_speech,
            match_form_in_menu,
            opening_line_for_form,
        )
        from backend.nlu import unload_model as _unload_nlu
        from backend.nlu.clarification import build_clarification, resolve_clarified_intent
        from backend.nlu.follow_up import resolve_follow_up
        from backend.nlu.resolve import classify_with_hints, top_intents_for_clarification
        from backend.decision_router import route
        from backend.forms import form_id_for_intent

        routed = False
        max_clarify = int(os.environ.get("BANK_NLU_MAX_CLARIFY", "3"))

        # User answering a prior "Did you mean X or Y?" prompt
        if (
            not routed
            and ctx.mode == "assist"
            and ctx.pending_intents
            and ctx.last_intent in {"clarification", "account_info_query"}
        ):
            picked = resolve_clarified_intent(
                ctx.pending_intents, result.kannada_text, result.english_text
            )
            if picked:
                intent, conf = picked
                routing = route(intent, result.english_text, result.kannada_text)
                result.intent = intent
                result.confidence = conf
                result.route = routing["route"]
                result.response_text = routing["response_text"]
                result.response_text_kn = routing.get("response_text_kn", "")
                result.required_fields = list(routing.get("required_fields") or [])
                result.form_id = form_id_for_intent(intent) or ""
                result.form_menu = []
                result.clarify_candidates = []
                if result.form_id and intent == "check_balance":
                    result.response_text = (
                        "Opening balance inquiry. I will ask for your account number next."
                    )
                    result.response_text_kn = (
                        "ಖಾತೆಯ ಶಿಲ್ಕು ಪರಿಶೀಲನೆಯನ್ನು ಪ್ರಾರಂಭಿಸುತ್ತೇನೆ."
                    )
                    acct = _extract_account_hint(result.kannada_text, result.english_text)
                    if acct:
                        result.prefill = {"account_number": acct}
                routed = True

        # Follow-up when prior turn set context (e.g. "what about FD?" after rates)
        if ctx.mode == "assist" and ctx.last_intent and not routed:
            follow = resolve_follow_up(ctx.last_intent, result.kannada_text, result.english_text)
            if follow and follow.get("type") == "form" and follow.get("form_id"):
                fid = str(follow["form_id"])
                kn_open, en_open = opening_line_for_form(fid)
                result.intent = "form_select"
                result.route = "transactional"
                result.form_id = fid
                result.response_text = en_open
                result.response_text_kn = kn_open
                result.confidence = 0.85
                routed = True
            elif follow and follow.get("type") == "interest_product":
                product = str(follow.get("product") or "")
                routing = route("interest_rate_query", f"interest rate for {product}", result.kannada_text)
                result.intent = "interest_rate_query"
                result.confidence = 0.8
                result.route = routing["route"]
                result.response_text = routing["response_text"]
                result.response_text_kn = routing.get("response_text_kn", "")
                result.required_fields = list(routing.get("required_fields") or [])
                routed = True

        # Form menu pick — match only against the spoken menu list
        if not routed and ctx.mode == "form_select" and ctx.menu_form_ids:
            picked = match_form_in_menu(
                result.kannada_text, result.english_text, ctx.menu_form_ids
            )
            if picked:
                kn_open, en_open = opening_line_for_form(picked)
                result.intent = "form_select"
                result.route = "transactional"
                result.form_id = picked
                result.response_text = en_open
                result.response_text_kn = kn_open
                result.confidence = 0.9
                routed = True
            else:
                result.intent = "form_select"
                result.route = "informational"
                result.response_text = (
                    "I could not identify that form. "
                    "Please say the menu number or form name again."
                )
                result.response_text_kn = (
                    "ಅರ್ಜಿಯನ್ನು ಗುರುತಿಸಲಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಅರ್ಜಿಯ ಸಂಖ್ಯೆ ಅಥವಾ ಹೆಸರನ್ನು ಮತ್ತೆ ಹೇಳಿ."
                )
                result.confidence = 0.0
                routed = True

        direct_form = None if routed else match_form_from_speech(
            result.kannada_text, result.english_text
        )
        if not routed and direct_form:
            kn_open, en_open = opening_line_for_form(direct_form)
            result.intent = "form_select"
            result.route = "transactional"
            result.form_id = direct_form
            result.response_text = en_open
            result.response_text_kn = kn_open
            result.required_fields = []
            result.form_menu = []
        elif not routed and is_form_menu_request(result.kannada_text, result.english_text):
            menu = build_form_menu_payload()
            result.intent = "form_menu"
            result.route = "form_menu"
            result.response_text = menu["speech_en"]
            result.response_text_kn = menu["speech_kn"]
            result.form_menu = menu["forms"]
            result.required_fields = []
            result.form_id = ""
        elif not routed:
            result.intent, result.confidence, _source = classify_with_hints(
                result.kannada_text, result.english_text
            )
            min_conf = float(os.environ.get("BANK_NLU_MIN_CONF", "0.35"))
            if result.confidence < min_conf:
                top2 = top_intents_for_clarification(result.english_text, k=2)
                attempt = ctx.clarify_attempts if ctx.last_intent == "clarification" else 0
                if attempt >= max_clarify:
                    en_clarify = (
                        "I am having trouble understanding. "
                        "Please visit the counter or try one service at a time — "
                        "balance, open account, loan, deposit, or withdraw."
                    )
                    kn_clarify = (
                        "ನೀವು ಹೇಳಿದ್ದು ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲು ತೊಂದರೆಯಾಗುತ್ತಿದೆ. "
                        "ದಯವಿಟ್ಟು ಸಿಬ್ಬಂದಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ ಅಥವಾ ಒಂದು ಸೇವೆಯನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ಹೇಳಿ — "
                        "ಖಾತೆಯ ಶಿಲ್ಕು, ಖಾತೆ ತೆರೆಯುವುದು, ಸಾಲ, ಠೇವಣಿ, ಅಥವಾ ಹಣ ಹಿಂಪಡೆಯುವುದು."
                    )
                    result.intent = "clarification"
                    result.route = "informational"
                    result.response_text = en_clarify
                    result.response_text_kn = kn_clarify
                    result.clarify_candidates = []
                else:
                    en_clarify, kn_clarify = build_clarification(top2, attempt=attempt)
                    result.intent = "clarification"
                    result.route = "informational"
                    result.response_text = en_clarify
                    result.response_text_kn = kn_clarify
                    result.clarify_candidates = [t[0] for t in top2[:2]]
                result.required_fields = []
                result.form_id = ""
                result.form_menu = []
            else:
                routing = route(result.intent, result.english_text, result.kannada_text)
                result.route = routing["route"]
                result.response_text = routing["response_text"]
                result.response_text_kn = routing.get("response_text_kn", "")
                result.required_fields = list(routing.get("required_fields") or [])
                result.form_id = form_id_for_intent(result.intent) or ""
                result.form_menu = []
                result.clarify_candidates = []
                if result.form_id and result.intent == "check_balance":
                    result.response_text = (
                        "Opening balance inquiry. I will ask for your account number next."
                    )
                    result.response_text_kn = (
                        "ಖಾತೆಯ ಶಿಲ್ಕು ಪರಿಶೀಲನೆಯನ್ನು ಪ್ರಾರಂಭಿಸುತ್ತೇನೆ."
                    )
                    acct = _extract_account_hint(result.kannada_text, result.english_text)
                    if acct:
                        result.prefill = {"account_number": acct}
    except Exception as exc:
        result.error = "NLU/Router failed: " + str(exc)
        result.total_time_s = round(time.perf_counter() - t_total, 2)
        return result
    finally:
        if _unload_nlu is not None:
            _maybe_unload(_unload_nlu, "finetuned")
    result.stage_times["nlu_router"] = round(time.perf_counter() - t0, 2)

    # Interactive HTTP requests fetch TTS separately so semantic results reach
    # the UI immediately and the STT worker is not held by remote synthesis.
    if not synthesise_audio:
        if not result.response_text_kn.strip() and result.response_text.strip():
            t0 = time.perf_counter()
            _unload_response_translation = None
            try:
                from backend.translation import (
                    translate_en_to_kn,
                    unload_model as _unload_response_translation,
                )

                result.response_text_kn = translate_en_to_kn(result.response_text)
            except Exception:
                # Routing remains successful even if response localization fails.
                result.response_text_kn = ""
            finally:
                if _unload_response_translation is not None:
                    _maybe_unload(_unload_response_translation, "en_to_kn")
            result.stage_times["response_translation"] = round(
                time.perf_counter() - t0,
                2,
            )
        result.stage_times["tts"] = 0.0
        result.total_time_s = round(time.perf_counter() - t_total, 2)
        return result

    # ── Stage 4: TTS ──────────────────────────────────────────────────────────
    # Natural Kannada = Indic Parler. Free Whisper/NLU VRAM before Parler worker.
    t0 = time.perf_counter()
    _unload_tts = None
    try:
        engine = os.environ.get("BANK_TTS_ENGINE", "parler").strip().lower()
        if engine in {"parler", "indic-parler", "auto"}:
            from backend.tts.remote_bridge import remote_tts_configured

            if not remote_tts_configured():
                try:
                    from backend.stt import unload_model as _u_stt
                    from backend.nlu import unload_model as _u_nlu
                    from backend.translation import unload_model as _u_tr
                    import gc
                    import torch

                    _u_stt("all")
                    _u_nlu("all")
                    _u_tr("all")
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass

        from backend.tts import synthesise, synthesise_kannada, unload_model as _unload_tts
        if result.response_text_kn.strip():
            result.audio = synthesise_kannada(result.response_text_kn)
        else:
            result.audio = synthesise(result.response_text)
        if result.audio is None:
            result.error = "TTS returned empty audio"
    except Exception as exc:
        result.error = "TTS failed: " + str(exc)
        # Non-fatal — return result without audio rather than crashing
        result.total_time_s = round(time.perf_counter() - t_total, 2)
        return result
    finally:
        if _unload_tts is not None:
            _maybe_unload(_unload_tts)
    result.stage_times["tts"] = round(time.perf_counter() - t0, 2)

    if result.audio is not None:
        stem = output_name or os.path.splitext(os.path.basename(audio_path))[0]
        output_path = os.path.join(output_dir, f"{stem}.wav")
        result.audio_output_path = _write_audio_to_disk(result.audio, output_path)

    result.total_time_s = round(time.perf_counter() - t_total, 2)
    return result


if __name__ == "__main__":
    import gc
    import os
    import sys
    # Ensure project root is on path when running as: python backend/pipeline.py
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import soundfile as sf
    import torch

    def gpu_mem():
        if torch.cuda.is_available():
            used = round(torch.cuda.memory_allocated() / 1024**3, 2)
            res  = round(torch.cuda.memory_reserved()  / 1024**3, 2)
            return "GPU used=" + str(used) + "GB reserved=" + str(res) + "GB"
        return "CPU-only"

    clips = [
        "data/stt_test_audio/clip_001.wav",   # check_balance
        "data/stt_test_audio/clip_003.wav",   # apply_loan
        "data/stt_test_audio/clip_004.wav",   # open_account
        "data/stt_test_audio/clip_007.wav",   # account_info_query
    ]

    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "tts_output"))
    os.makedirs(output_dir, exist_ok=True)
    print("Full pipeline.py multi-run test")
    print("Confirms memory stays flat across repeated calls")
    print("=" * 65)
    print("Start: " + gpu_mem())
    print()

    for i, clip_path in enumerate(clips, 1):
        clip_name = os.path.basename(clip_path)
        print("Run " + str(i) + "/4: " + clip_name)

        result = run_pipeline(clip_path, output_dir=output_dir, output_name=f"pipeline_run{i}")

        if result.error:
            print("  ERROR: " + result.error)
        else:
            safe_resp = result.response_text.encode('ascii', errors='replace').decode('ascii')
            audio_dur = (round(len(result.audio[0]) / result.audio[1], 1)
                         if result.audio else 0)
            if result.audio_output_path:
                out = result.audio_output_path
            else:
                out = ""
            print("  intent=" + result.intent +
                  " conf=" + str(round(result.confidence, 2)) +
                  " route=" + result.route)
            print("  response=" + safe_resp[:65] +
                  ("..." if len(safe_resp) > 65 else ""))
            print("  audio=" + str(audio_dur) + "s  total=" +
                  str(result.total_time_s) + "s  " + str(result.stage_times) +
                  ("  saved=" + out if out else ""))

        print("  mem after run: " + gpu_mem())
        print()

    print("=" * 65)
    print("All 4 runs complete. No crash. Exit 0.")
