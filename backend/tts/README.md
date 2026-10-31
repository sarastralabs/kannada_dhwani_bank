# TTS Module -- Kannada Text-to-Speech

Converts the Decision Router's English `response_text` to spoken Kannada audio.
Internally uses `translate_en_to_kn()` (existing Translation module) then synthesises
speech with Facebook's MMS-TTS VITS model.

Model: `facebook/mms-tts-kan` -- 36 MB, public (no auth), fully offline, CC-BY-NC 4.0

---

## Pipeline integration (`backend/pipeline.py`)

`run_pipeline()` passes the Decision Router's English `response_text` directly to
`synthesise()`. **English is never sent to MMS-TTS.** Translation happens inside
the TTS module before synthesis:

```
Router (English response_text)
    -> synthesise()                    # called from pipeline.py Stage 4
        split sentences
        -> translate_en_to_kn()        # per sentence, Translation module
        -> MMS-TTS (facebook/mms-tts-kan)
        -> audio
```

Reading `pipeline.py` alone can look like English goes straight to a Kannada-only
model; the call chain is `pipeline.synthesise()` → `speaker.synthesise()` →
`translate_en_to_kn()` → `_synthesise_kannada()`.

---

## Quick Start

```python
from backend.tts import synthesise

audio, sr = synthesise(
    "The interest rate for savings account is 3 point 5 percent per annum.",
    output_path="data/tts_output/response.wav",
)
# audio: float32 NumPy array, sr: 16000
```

Play back with any audio player (VLC, Windows Media Player, Audacity):
```
data/tts_output/response.wav
```

---

## No Setup Required

Unlike IndicTrans2 and Whisper, this model:
- Is **not gated** on HuggingFace -- no auth, no terms acceptance
- Has **no new dependencies** -- `VitsModel` is already in `transformers 4.57.6`
- Downloads **36 MB** in seconds on first use, fully offline afterwards

---

## API

### `synthesise(english_text, output_path=None, play=False) -> tuple[ndarray, int] | None`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `english_text` | required | English text (router's response_text) |
| `output_path` | None | Save .wav to this path if given |
| `play` | False | Play via sounddevice (optional, skips if not installed) |
| `voice_description` | None | Accepted for API compatibility; ignored by MMS-TTS |

Returns `(audio_array, sample_rate)` or `None` for empty input.

---

## Performance (measured on dev machine, CUDA GPU)

| Step | Time |
|------|------|
| translate_en_to_kn() | ~14-15s (model first load) / ~0.2s (cached) |
| KannadaSpeaker init (model load) | ~2s (from cache) |
| synthesis (~10s Kannada speech) | ~1.65s on GPU |
| Total (all models cached) | ~2s end-to-end |

Sample rate: 16000 Hz. Typical output: 8-15 seconds of audio per banking response.

---

## Voice Quality

**Preferred:** AI4Bharat **Indic Parler-TTS** with named Kannada speakers
**Suresh** (default) or **Anu** — natural, bank-friendly voice.

Runs in an **isolated** `.venv-parler` (transformers 4.46.1) so the main app
can keep transformers ≥4.51 for IndicTrans2. A long-lived worker process
(`run_parler_tts_worker.py`) is started on first synth.

```powershell
.\scripts\setup_parler_venv.ps1
# optional:
# $env:BANK_TTS_SPEAKER = "Anu"      # or Suresh
# $env:BANK_TTS_ENGINE  = "parler"   # auto | parler | mms
# $env:BANK_PARLER_DTYPE = "fp16"    # fp16 on GPU (~half VRAM); fp32 | auto
```

On CUDA the worker loads **`ai4bharat/indic-parler-tts` in FP16** by default
(`BANK_PARLER_DTYPE=auto` → fp16 on GPU, fp32 on CPU). Same model weights,
lower VRAM and faster inference vs full FP32.

**Fallback:** `facebook/mms-tts-kan` (robotic but offline / no extra setup).

---

## Known Quality Fixes (both implemented in speaker.py / __init__.py)

### Fix 1 -- Sentence splitting

**Problem:** VITS models produce degraded output and apparent truncation when
given multi-sentence input as a single string. The first sentence sounds fine but
the second is clipped or muffled.

**Root cause:** VITS models are trained on short, single-utterance samples and
their duration predictor degrades on long sequences. Feeding a 200-character
two-sentence string produces less natural prosody than two separate 100-character
inference calls.

**Fix:** `synthesise()` splits English input on sentence boundaries (`. ! ?`)
before translation, translates and synthesises each sentence independently,
then concatenates the audio arrays with a 0.4-second silence gap between them.
This is the standard practical approach for VITS inference on longer texts.

### Fix 2 -- ASCII digit normalisation

**Problem:** IndicTrans2 (`translate_en_to_kn`) sometimes preserves ASCII digits
inside its Kannada output. For example, "3 point 5 percent per annum" translates
to a Kannada string containing the raw characters "3" and "5" rather than spelling
them out in Kannada script. VitsModel tokenises these as mixed-script tokens and
produces audible artefacts (stuttering, clicks) around digit positions.

**Verified by inspection:** The Kannada output for "3 point 5 percent" was
confirmed to contain ASCII digit characters (`digits_replaced: True` in tests).

**Fix:** `_normalise_digits()` in `speaker.py` replaces ASCII digits 0-9 with
their Kannada word equivalents (e.g. "3" -> "ಮೂರು", "5" -> "ಐದು") before passing
text to the tokenizer. This is applied per-sentence inside `_synthesise_kannada()`.
Tested and confirmed on:
- Two-sentence numeric input (interest rate response): 14.61s clean output
- Two-sentence non-numeric input (account info procedure): 20.21s clean output

---

## Files

```
backend/tts/
├── __init__.py      Public API: synthesise()
└── speaker.py       KannadaSpeaker class (VitsModel wrapper)

data/tts_output/     .wav files from synthesise(output_path=...)  [gitignored]
```

---

## Design Decision History -- Indic Parler-TTS (restored via isolated venv)

The original design specified `ai4bharat/indic-parler-tts` (Parler-TTS, ~0.9B params)
as the TTS model due to its higher Kannada voice quality (NSS 88.17) and named
Kannada voices (Suresh, Anu, Chetan, Vidya).

### Blocker -- transformers conflict (still true in the *main* env)

`parler-tts` requires `transformers<4.50` for `generate()`, while IndicTransToolkit
needs `transformers>=4.51`. They cannot share one Python environment.

### Current solution (2026)

Install Parler in **`.venv-parler`** and call it through `backend/tts/parler_bridge.py`
(persistent worker). Main env keeps MMS as fallback. See `scripts/setup_parler_venv.ps1`.

---

### Why MMS remains as fallback
- No gating, works without the second venv
- `VitsModel` is native in transformers 4.57+
- 36 MB vs ~2 GB
- Voice quality lower; use only when Parler is not set up
