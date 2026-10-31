"""
test_pipeline.py
================
End-to-end test of the Kannada Voice Banking Assistant pipeline.

Runs the full pipeline on all 11 test clips and saves:
  - data/tts_output/<clip>_response.wav   (Kannada voice response)
  - data/tts_output/pipeline_results.txt  (full log of every stage)

Usage
-----
    python test_pipeline.py

No frontend needed. Results are printed to the terminal and saved to files.

What each column means
----------------------
  Clip    : the audio file name
  Intent  : what the user wants (check_balance, apply_loan, etc.)
  Route   : informational (answered directly) or transactional (needs form)
  Audio   : duration of the Kannada voice response saved to disk
"""

import os
import sys
import time

# Force offline mode -- no network calls needed after initial setup
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import soundfile as sf
from backend.pipeline import run_pipeline

DATA_DIR   = "data/stt_test_audio"
OUTPUT_DIR = "data/tts_output"
LOG_FILE   = os.path.join(OUTPUT_DIR, "pipeline_results.txt")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# The 11 test clips
CLIPS = [
    "clip_001.wav",
    "clip_002.wav",
    "clip_003.wav",
    "clip_004.wav",
    "clip_006.wav",
    "clip_007.wav",
    "clip_011.wav",
    "clip_012.wav",
    "clip_013.wav",
    "clip_014.wav",
    "clip_015.wav",
]

sep = "=" * 70
print(sep)
print("  Kannada Voice Banking Assistant -- Pipeline Test")
print("  Running all 11 clips through: STT -> Translation -> NLU -> Router -> TTS")
print(sep)
print()

results = []

with open(LOG_FILE, "w", encoding="utf-8") as log:
    log.write("Pipeline Test Results\n")
    log.write(sep + "\n\n")

    for clip in CLIPS:
        wav_path = os.path.join(DATA_DIR, clip)
        if not os.path.exists(wav_path):
            print("  SKIP " + clip + " (audio file missing)")
            continue

        print("Processing: " + clip + " ...")
        t0 = time.perf_counter()

        result = run_pipeline(wav_path)
        elapsed = round(time.perf_counter() - t0, 1)

        # Save audio
        audio_info = "no audio"
        if result.audio is not None and result.error is None:
            out_path = os.path.join(OUTPUT_DIR, clip.replace(".wav", "_response.wav"))
            sf.write(out_path, result.audio[0], result.audio[1])
            dur = round(len(result.audio[0]) / result.audio[1], 1)
            audio_info = str(dur) + "s -> " + out_path

        # Print result
        if result.error:
            print("  ERROR: " + result.error)
            log.write(clip + " -- ERROR: " + result.error + "\n\n")
        else:
            safe = result.response_text.encode("ascii", errors="replace").decode("ascii")
            print("  Intent   : " + result.intent + " (conf=" + str(round(result.confidence, 2)) + ", route=" + result.route + ")")
            print("  English  : " + result.english_text[:70])
            print("  Response : " + safe[:70] + ("..." if len(safe) > 70 else ""))
            print("  Audio    : " + audio_info)
            print("  Timing   : " + str(result.stage_times) + " total=" + str(result.total_time_s) + "s")

            log.write(clip + "\n")
            log.write("  Kannada  : " + result.kannada_text + "\n")
            log.write("  English  : " + result.english_text + "\n")
            log.write("  Intent   : " + result.intent + " (" + str(round(result.confidence*100)) + "% conf, " + result.route + ")\n")
            log.write("  Response : " + result.response_text + "\n")
            log.write("  Audio    : " + audio_info + "\n")
            log.write("  Timing   : " + str(result.stage_times) + "\n\n")

            results.append({
                "clip": clip,
                "intent": result.intent,
                "route": result.route,
                "audio": audio_info,
            })

        print()

# Summary table
print(sep)
print("  SUMMARY")
print(sep)
print("  {:<16} {:<25} {:<15} {}".format("Clip", "Intent", "Route", "Audio"))
print("  " + "-" * 65)
for r in results:
    print("  {:<16} {:<25} {:<15} {}".format(
        r["clip"], r["intent"], r["route"],
        r["audio"].split("->")[0].strip() if "->" in r["audio"] else r["audio"]
    ))
print(sep)
print()
print("  Full log saved to: " + os.path.abspath(LOG_FILE))
print("  Audio files in  : " + os.path.abspath(OUTPUT_DIR))
print()
print("  To listen to a response, open any .wav file from:")
print("  " + os.path.abspath(OUTPUT_DIR))
