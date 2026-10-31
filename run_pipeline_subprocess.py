"""
Thin wrapper: run_pipeline on a single wav file and print JSON result.
Called by the API as a subprocess so pipeline crashes don't kill the server.
Usage: python run_pipeline_subprocess.py <wav_path>
"""
import base64
import json
import os
import sys
import tempfile

# Force fully offline mode -- no network calls to huggingface.co
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Keep stdout JSON-only (torch/triton may print noise)
_REAL_STDOUT = sys.stdout
sys.stdout = sys.stderr

from backend.cuda_runtime import ensure_compatible_cudnn  # noqa: E402

ensure_compatible_cudnn()

from backend.pipeline import run_pipeline  # noqa: E402
import soundfile as sf  # noqa: E402

wav_path = sys.argv[1]
context: dict = {}
if len(sys.argv) > 2 and sys.argv[2].strip():
    try:
        context = json.loads(sys.argv[2])
    except json.JSONDecodeError:
        context = {}
include_audio = len(sys.argv) <= 3 or sys.argv[3].strip().lower() not in {
    "0",
    "false",
    "off",
    "no",
}

result = run_pipeline(
    wav_path,
    context=context or None,
    synthesise_audio=include_audio,
)

audio_b64 = ""
if result.audio is not None:
    buf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    buf.close()
    sf.write(buf.name, result.audio[0], result.audio[1])
    with open(buf.name, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode()
    try:
        os.unlink(buf.name)
    except OSError:
        pass

output = {
    "kannada_text": result.kannada_text,
    "english_text": result.english_text,
    "intent": result.intent,
    "confidence": result.confidence,
    "route": result.route,
    "response_text": result.response_text,
    "required_fields": result.required_fields,
    "form_id": result.form_id,
    "form_menu": result.form_menu,
    "response_text_kn": result.response_text_kn,
    "prefill": result.prefill,
    "clarify_candidates": result.clarify_candidates,
    "audio_b64": audio_b64,
    "stage_times": result.stage_times,
    "total_time_s": result.total_time_s,
    "error": result.error,
}
_REAL_STDOUT.write(json.dumps(output) + "\n")
_REAL_STDOUT.flush()
