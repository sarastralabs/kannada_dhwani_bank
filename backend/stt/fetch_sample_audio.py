"""
One-time helper: generates minimal synthetic .wav files so you can
smoke-test the STT pipeline (model loads, transcribe() runs, returns text)
without needing a network connection or real recordings.

HOW IT WORKS
------------
Writes 3 short .wav files containing Kannada text-to-speech audio generated
via gTTS (Google Text-to-Speech), which only needs internet for the TTS call
itself.  Falls back to silent .wav files if gTTS is unavailable, which is
still enough to verify the module loads and handles audio without crashing.

IMPORTANT — DO NOT USE THESE FOR BENCHMARK NUMBERS
---------------------------------------------------
Synthetic/TTS audio is artificially clean and will produce unrealistically
low WER/CER.  These files are ONLY for confirming the end-to-end pipeline
runs (imports work, model loads, transcribe() returns a string).

For your actual WER/CER results, record real human speech of the 15 banking
phrases in transcripts.json.

Run with:
    pip install gtts        # one-time, only needed for this helper
    python backend/stt/fetch_sample_audio.py
"""

from __future__ import annotations

import io
import os
import struct
import wave

import numpy as np

OUTPUT_DIR = "data/stt_test_audio"
SAMPLE_RATE = 16_000   # Whisper's expected sample rate

# Three short Kannada banking phrases for smoke-testing
SMOKE_TEST_PHRASES = [
    ("sample_smoke_01.wav", "ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟಿದೆ"),
    ("sample_smoke_02.wav", "ಹಣ ವರ್ಗಾಯಿಸಲು ಸಹಾಯ ಮಾಡಿ"),
    ("sample_smoke_03.wav", "ಸಾಲ ಅರ್ಜಿ ಹೇಗೆ ಮಾಡಬೇಕು"),
]

os.makedirs(OUTPUT_DIR, exist_ok=True)


def _write_silent_wav(path: str, duration_s: float = 3.0) -> None:
    """Write a .wav file containing silence (all zeros).  No dependencies."""
    num_samples = int(SAMPLE_RATE * duration_s)
    audio = np.zeros(num_samples, dtype=np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)      # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())


def _write_gtts_wav(path: str, text: str, lang: str = "kn") -> bool:
    """
    Generate a .wav file from text using gTTS.
    Returns True on success, False if gTTS is unavailable or the call fails.
    """
    try:
        from gtts import gTTS          # noqa: PLC0415
        import pydub                   # noqa: PLC0415  (needed for mp3→wav)
        from pydub import AudioSegment # noqa: PLC0415

        mp3_buf = io.BytesIO()
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.write_to_fp(mp3_buf)
        mp3_buf.seek(0)

        audio_seg = AudioSegment.from_mp3(mp3_buf)
        audio_seg = audio_seg.set_frame_rate(SAMPLE_RATE).set_channels(1)
        audio_seg.export(path, format="wav")
        return True

    except ImportError:
        return False
    except Exception as exc:
        print(f"  [gTTS error] {exc} — falling back to silent wav")
        return False


def main() -> None:
    # Try gTTS first; fall back to silent wav if not installed
    try:
        import gtts as _gtts_check  # noqa: F401
        use_gtts = True
        print("gTTS found — generating Kannada TTS audio for smoke-test clips.")
    except ImportError:
        use_gtts = False
        print("gTTS not installed — writing silent .wav files.")
        print("(Install with: pip install gtts pydub  — then re-run for real TTS audio)")
        print("Silent files are still sufficient to verify the pipeline loads correctly.\n")

    saved = 0
    for filename, phrase in SMOKE_TEST_PHRASES:
        out_path = os.path.join(OUTPUT_DIR, filename)

        success = False
        if use_gtts:
            success = _write_gtts_wav(out_path, phrase)

        if not success:
            _write_silent_wav(out_path)
            label = "silent (fallback)"
        else:
            label = "TTS audio"

        print(f"  Saved [{label}]: {out_path}")
        print(f"  Phrase: {phrase}")
        saved += 1

    print(f"\nDone. {saved} smoke-test clips saved to {OUTPUT_DIR}/")
    print()
    print("Next steps:")
    print("  1. Run the STT module on one of these clips to confirm it works:")
    print("       python -c \"from backend.stt import transcribe; print(transcribe('data/stt_test_audio/sample_smoke_01.wav'))\"")
    print("  2. Record real human Kannada speech for the 15 banking phrases")
    print("     (see data/stt_test_audio/transcripts.json) before running benchmark.py")


if __name__ == "__main__":
    main()
