# STT Module — Kannada Speech-to-Text

Converts spoken Kannada `.wav` audio to Kannada text.  
Runs fully offline on CPU using `faster-whisper` (CTranslate2 int8 quantization).

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

For the CPU-only client deployment machine, install the lightweight PyTorch build
instead of the default CUDA-enabled one:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### 2. Convert models — one-time setup

See the full [Model Conversion](#model-conversion) section below.

### 3. Transcribe audio

```python
from backend.stt import transcribe

text = transcribe("data/stt_test_audio/clip_001.wav")
print(text)  # ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟಿದೆ
```

### 4. Run the benchmark

See the full [Benchmarking](#benchmarking) section below.

---

## File Layout

```
backend/stt/
├── __init__.py          Public API: transcribe()
├── transcriber.py       KannadaTranscriber class (faster-whisper wrapper)
├── exceptions.py        STTInputError definition
├── utils.py             Audio validation helpers
├── convert_models.py    One-time HF → CTranslate2 conversion CLI
└── benchmark.py         WER/CER benchmark harness

data/stt_test_audio/
├── clip_001.wav … clip_015.wav    Test audio clips (human-recorded)
└── transcripts.json               Ground-truth Kannada transcripts (11 clips)

models/
├── whisper-medium-ct2/            Converted baseline model (gitignored)
├── whisper-medium-vaani-ct2/      Converted VAANI rollback model (gitignored)
└── whisper-kannada-medium-ct2/     Converted Vasista production model (gitignored)
```

---

## Models

| Key | HuggingFace ID | Purpose |
|-----|----------------|---------|
| `baseline` | `openai/whisper-medium` | Generic multilingual Whisper — not Kannada-tuned; benchmark lower bound |
| `specialized` | `ARTPARK-IISc/whisper-medium-vaani-kannada` | Previous production model, retained for rollback |
| `vasista-medium` | `vasista22/whisper-kannada-medium` | Kannada-fine-tuned production default |

Set `BANK_STT_MODEL=vasista-medium` for the default model, or
`BANK_STT_MODEL=specialized` to roll back without changing code.

---

## Model Conversion

`convert_models.py` is a **one-time setup script**. It downloads the selected Whisper
checkpoints from HuggingFace and converts them to CTranslate2 int8 format for
fast offline CPU inference. After this step the `models/` directory is
self-contained and no internet access is ever needed again.

### Prerequisites

- Internet connection (this step only)
- `ctranslate2` installed — the Python package is sufficient; no CLI tool needs
  to be on PATH (the script uses `ctranslate2.converters.TransformersConverter`
  directly, which works regardless of PATH configuration on Windows or Linux)
- ~6 GB free disk space during conversion (int8 output is ~400 MB per model;
  the raw HuggingFace checkpoints are ~1.5 GB each and can be deleted afterwards)

### Commands

```bash
# Recommended: convert both models in one shot
python backend/stt/convert_models.py --model all

# Convert only the baseline (openai/whisper-medium)
python backend/stt/convert_models.py --model baseline

# Convert only the Kannada-specialized model
python backend/stt/convert_models.py --model specialized

# Convert the default Vasista Kannada model
python backend/stt/convert_models.py --model vasista-medium
```

### What the script does

1. Calls `ct2-transformers-converter --model <hf_id> --output_dir <path> --quantization int8 --force`
2. Verifies that `model.bin`, `config.json`, and `vocabulary.json` are present
   in the output directory
3. Prints the size of `model.bin` as a quick sanity check

### Expected output (healthy conversion)

```
============================================================
  Converting: baseline
  Source    : openai/whisper-medium
  Purpose   : Generic multilingual Whisper (not Kannada-tuned) — benchmark baseline
  Output    : models/whisper-medium-ct2
============================================================
  Downloading from HuggingFace and converting to CTranslate2 int8 ...
  (This may take several minutes on first run — model is ~1.5 GB)

[OK] 'baseline' converted successfully.
     model.bin size: 388.4 MB
     Location: models/whisper-medium-ct2

============================================================
  Converting: specialized
  ...
[OK] 'specialized' converted successfully.
     model.bin size: 392.1 MB
     Location: models/whisper-medium-vaani-ct2
```

**Healthy `model.bin` size range: 370–420 MB.**  
If the file is smaller than 300 MB the conversion likely truncated; delete
the output directory and re-run with `--model all`.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: ctranslate2` | ctranslate2 not installed | `pip install ctranslate2` |
| `OSError: [Errno 28] No space left` | Insufficient disk during conversion | Free at least 6 GB and retry |
| `model.bin` < 300 MB | Conversion interrupted | Delete output dir, re-run |
| `KeyError: 'encoder'` from faster-whisper at runtime | Wrong converter used (OpusMTConverter instead of TransformersConverter) | Delete output dir, re-run with the correct script |
| HuggingFace 401 / 403 error for specialized model | Model requires accepting terms | Visit the HF model page, accept the licence, then re-run |
| `RuntimeError: Output directory already exists` | `force=True` not taking effect | Delete the output directory manually and retry |

---

## Benchmarking

`benchmark.py` runs both models over the held-out test set, computes WER and
CER for each, and saves a comparison CSV.

### Prerequisites

- Both models converted (see above)
- `data/stt_test_audio/` populated with **11 `.wav` clips** and `transcripts.json`
  (clips: 001–004, 006–007, 011–015 — the finalised test set)
- **Audio must be real human-recorded Kannada speech** — see the note on
  synthetic audio below

### Commands

```bash
# Full benchmark — both models, default paths
python backend/stt/benchmark.py

# Benchmark a single model
python backend/stt/benchmark.py --models specialized
python backend/stt/benchmark.py --models baseline

# Custom data directory and output path
python backend/stt/benchmark.py \
    --data-dir data/stt_test_audio \
    --output results/benchmark_results.csv

# Test production-latency mode (beam_size=1) vs accuracy mode (beam_size=5)
python backend/stt/benchmark.py --beam-size 1
python backend/stt/benchmark.py --beam-size 5
```

### What the benchmark does

1. Loads `transcripts.json` (ground-truth reference texts)
2. For each model, runs `transcribe()` on every `.wav` clip with `beam_size=5`
   (accuracy-focused; production uses `beam_size=1`)
3. Prints each clip's reference vs hypothesis to stdout as it runs
4. Computes WER and CER across all clips using `jiwer`
5. Saves a CSV and prints a formatted summary table

### Output CSV schema

```
benchmark_results.csv
```

| Column | Type | Description |
|--------|------|-------------|
| `model_name` | string | `baseline` or `specialized` |
| `wer_percent` | float | Word Error Rate × 100. Lower is better. |
| `cer_percent` | float | Character Error Rate × 100. Lower is better. |
| `avg_inference_time_s` | float | Mean seconds per clip (wall clock) |
| `num_clips` | int | Number of clips successfully transcribed |
| `total_time_s` | float | Total inference time across all clips |
| `beam_size` | int | Beam width used for this run |

### Example CSV output

```csv
model_name,wer_percent,cer_percent,avg_inference_time_s,num_clips,total_time_s,beam_size
baseline,111.11,87.55,6.24,11,68.62,5
specialized,50.00,20.60,0.71,11,7.81,5
```

> Test set: **11 banking phrases** (clips 001–004, 006–007, 011–015).
> Clips 005, 008, 009, 010 were removed when the test set was finalised at 11 clips.

### Example stdout table

```
======================================================================
  BENCHMARK RESULTS
======================================================================
| model_name   |   wer_percent |   cer_percent |   avg_inference_time_s |   num_clips |   total_time_s |   beam_size |
|--------------|---------------|---------------|------------------------|-------------|----------------|-------------|
| baseline     |         72.40 |         48.30 |                   6.21 |          15 |          93.15 |           5 |
| specialized  |         38.50 |         22.80 |                   6.35 |          15 |          95.25 |           5 |
======================================================================

  Results saved to: benchmark_results.csv
```

---

## Expected WER/CER Ranges — Sanity Check

Use these ranges to decide whether your converted models are working correctly
before writing up your results. Numbers outside these ranges are a signal to
investigate, not necessarily a project failure.

> All ranges below assume: real human-recorded Kannada audio, 15–20 clips of
> 5–15 seconds each, banking-domain phrases, `beam_size=5`.

### Baseline — `openai/whisper-medium` (not Kannada-tuned)

| Metric | Expected range | What it means |
|--------|---------------|---------------|
| WER | **55–85%** | Whisper-medium was not trained specifically on Kannada. It knows the script but makes many word-level substitutions on conversational/domain speech. A WER above 85% likely means the model loaded incorrectly (wrong language forced, or wrong model file). A WER below 45% on real rural speech is suspiciously good — check your audio quality. |
| CER | **35–60%** | Character-level errors are fewer than word-level because the model often gets partial words right. Below 30% CER on the baseline with real rural audio would be unusual. |
| Avg inference time | **4–10 s/clip** on CPU | At `beam_size=5` with `whisper-medium` int8. If you see >15 s/clip consistently, check that `compute_type="int8"` is being applied (not float32). |

### Specialized — `ARTPARK-IISc/whisper-medium-vaani-kannada`

| Metric | Expected range | What it means |
|--------|---------------|---------------|
| WER | **25–55%** | Fine-tuned on the VAANI dataset which covers conversational Kannada across Karnataka dialects. Meaningful improvement over baseline expected. If WER is above 70%, the model may have loaded as the wrong variant — verify `model.bin` size matches the baseline (~390 MB). |
| CER | **12–35%** | CER improvement over baseline is usually proportionally larger than WER improvement because the fine-tuning improves character-level accuracy first. |
| Avg inference time | **4–10 s/clip** on CPU | Should be similar to baseline — same architecture, same quantization. A large discrepancy (>3 s difference) is worth investigating. |

### Relative improvement (the core project claim)

The project claim is that the specialized model is meaningfully better than the
generic baseline for Kannada banking speech. **Actual benchmark results on the
11-clip test set (beam_size=5):**

| Model | WER% | CER% | Avg time/clip |
|-------|------|------|---------------|
| baseline (whisper-medium) | 111.11 | 87.55 | 6.24 s |
| specialized (vaani-kannada) | **50.00** | **20.60** | 0.71 s |

WER reduction: **61 percentage points**. CER reduction: **67 percentage points**.
Both metrics confirm the specialized model is dramatically better for Kannada
banking speech — validating the project hypothesis.

If you see less than 10 pp improvement on WER, consider these explanations
before concluding the fine-tuning didn't help:

1. **Audio quality** — if your clips are very clean and clearly spoken, the
   baseline model will perform better than it would on genuinely rural/noisy
   speech. The gap widens on harder audio.
2. **Clip length** — very short clips (<3 s) give Whisper less context to work
   with. The VAANI fine-tuning helps most on natural, continuous speech.
3. **Dialect** — the VAANI dataset covers many Karnataka dialects but is
   weighted toward certain regions. If your speakers use a dialect not well-
   represented in VAANI, the improvement will be smaller.

### Red flags — investigate before reporting

| Observation | What to check |
|-------------|--------------|
| Both models produce identical outputs | Model cache collision — confirm `MODEL_PATHS` in `__init__.py` point to different directories |
| Either model outputs only English text | `language="kn"` is not being passed — check `transcriber.py` |
| WER > 100% on either model | `jiwer` can exceed 100% when the hypothesis is much longer than the reference. Usually means VAD is off and silence is generating hallucinated text. Try `vad_filter=True` (already the default). |
| `avg_inference_time_s` < 0.5 s | The model may be returning immediately without real inference — check that the audio files are not all being detected as silent |
| CER > WER | Not expected for Kannada. If this happens, check that `jiwer.cer()` is being called correctly (not called with swapped argument order). |

---

## API Reference

### `transcribe(audio_path, model=None, beam_size=1) → str`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `audio_path` | required | Path to `.wav` file (16 kHz mono recommended) |
| `model` | `None` | Uses `BANK_STT_MODEL`; explicit options are `"baseline"`, `"specialized"`, or `"vasista-medium"` |
| `beam_size` | `1` | `1` = greedy/fast (≤10 s on CPU); `5` = beam search/accurate |

**Returns:** Kannada text string, or `""` for silent clips.  
**Raises:** `STTInputError` for missing/corrupt/unsupported files.  
**Raises:** `FileNotFoundError` if the model directory has not been created yet.

---

## Important Notes for the Phase-2 Report

- **Real audio is mandatory for final benchmark numbers.** gTTS/espeak-ng
  synthetic speech is unrealistically clean. WER on synthetic audio can be
  10–30 percentage points lower than on real speech, making results non-comparable
  to published benchmarks.
- **Report both beam_size=1 and beam_size=5 results.** The speed/accuracy
  tradeoff is a legitimate additional finding for your report methodology section.
  Run `benchmark.py --beam-size 1` and `benchmark.py --beam-size 5` and include
  both rows in your results table.
- **CPU-only simulation.** Before writing up deployment results, run:
  ```bash
  # Windows
  set CUDA_VISIBLE_DEVICES=
  python backend/stt/benchmark.py --models specialized --beam-size 1
  ```
  and confirm inference time stays under 10 seconds per clip (the AC-1.1 target).
- **CER is your primary metric for Kannada.** Lead with CER in your report; WER is
  secondary. Cite this reason: Kannada's conjunct characters (ಒತ್ತಕ್ಷರ) mean a
  single character error makes the whole word wrong under WER, which overstates
  the error rate on a per-character basis.
