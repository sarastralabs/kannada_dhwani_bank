"""Cloud-only hosts (Render) have no torch: the whole request path must still work.

Runs in a fresh interpreter with torch & friends made un-importable, so a stray
top-level import anywhere on the path fails here instead of on the live site.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCRIPT = textwrap.dedent(
    """
    import os, sys, struct, wave, tempfile
    sys.path.insert(0, {root!r})
    for name in ("torch", "transformers", "faster_whisper", "ctranslate2", "sklearn",
                 "IndicTransToolkit", "sentencepiece", "seaborn", "sounddevice", "matplotlib", "jiwer"):
        sys.modules[name] = None
    tmp = tempfile.mkdtemp()
    os.environ.update(
        BANK_CLOUD_PROVIDER="sarvam", BANK_CLOUD_FALLBACK_LOCAL="0", BANK_NLU_ENGINE="keyword",
        BANK_TTS_ALLOW_MMS="0", SARVAM_API_KEY="test-key-123456",
        BANK_RUNTIME_SETTINGS_FILE=os.path.join(tmp, "rs.json"),
        BANK_CLOUD_STATUS_FILE=os.path.join(tmp, "cs.json"),
        BANK_TTS_CACHE_DIR=os.path.join(tmp, "cache"),
    )
    os.environ.pop("MONGODB_URI", None)

    import numpy as np
    from backend.cloud import sarvam
    sarvam.transcribe = lambda key, wav, language="kn": "ನನ್ನ ಖಾತೆ ಬಾಕಿ ಎಷ್ಟಿದೆ"
    sarvam.translate = lambda key, text, src_lang, tgt_lang: (
        "How much is my account balance?" if tgt_lang.startswith("eng") else "ನಿಮ್ಮ ಖಾತೆ ಬಾಕಿ ಐದು ಸಾವಿರ ರೂಪಾಯಿ")
    sarvam.synthesise = lambda key, text, voice=None: (np.full(4800, 0.1, dtype="float32"), 24000)

    # 1) the HTTP route the kiosk uses for every spoken line
    from fastapi.testclient import TestClient
    import api.main
    with TestClient(api.main.app) as client:
        res = client.post("/api/speak-kannada", json={{"text": "ನಮಸ್ಕಾರ, ನಿಮಗೆ ಏನು ಸಹಾಯ ಬೇಕು?"}})
        assert res.status_code == 200, (res.status_code, res.text[:200])
        assert len(res.json()["audio_b64"]) > 100

    # 2) the full pipeline with spoken output
    wav = os.path.join(tmp, "in.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * np.sin(i / 20))) for i in range(16000)))
    from backend.pipeline import run_pipeline
    r = run_pipeline(wav, synthesise_audio=True)
    assert r.error is None, r.error
    assert r.intent == "check_balance", r.intent
    assert r.audio is not None, "pipeline produced no voice"
    assert sys.modules.get("torch") is None
    print("CLOUD_ONLY_OK")
    """
).format(root=ROOT)


def test_request_path_works_without_torch():
    proc = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        cwd=ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert "CLOUD_ONLY_OK" in proc.stdout, proc.stdout[-800:] + "\n" + proc.stderr[-1500:]
