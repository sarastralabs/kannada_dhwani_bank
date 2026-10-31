# Translation Module — Kannada ↔ English

Translates Kannada text (STT output) to English for NLU processing, and
English response text to Kannada for TTS output.  
Uses IndicTrans2 distilled 200M models via HuggingFace `transformers`.  
Runs fully offline on CPU after the one-time model download.

---

## ⚠️ Required: HuggingFace Authentication (do this first)

Both IndicTrans2 models are **gated** on HuggingFace — they require you to
accept the model licence terms and authenticate before downloading.

**If you skip this step**, you will see a `GatedRepoError` when the module
tries to load a model for the first time, even with a valid internet
connection.

### Step 1 — Accept the licence terms (one-time, per model)

Open each model page in a browser while logged into your HuggingFace account
and click **"Agree and access repository"**:

- [ai4bharat/indictrans2-indic-en-dist-200M](https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M)
  *(Kannada → English)*
- [ai4bharat/indictrans2-en-indic-dist-200M](https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M)
  *(English → Kannada)*

### Step 2 — Create a HuggingFace access token

Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
and create a token of type **Read** (not *Fine-grained*).

Replace `<YOUR_TOKEN>` below with the real value — it starts with `hf_` and is about 37
characters. Storing the placeholder text yields a token that exists but fails with `401`.

### Step 3 — Log in on your machine

```bash
pip install huggingface_hub   # already in requirements.txt
hf auth login                 # `huggingface-cli login` on huggingface_hub < 1.0
# Paste your token when prompted
```

Or set the environment variable directly (useful for CI / shared machines):

```bash
# Windows
set HF_TOKEN=<YOUR_TOKEN>

# Linux / macOS
export HF_TOKEN=<YOUR_TOKEN>
```

Confirm it worked before continuing — this should print your username:

```bash
python -c "from huggingface_hub import whoami; print(whoami()['name'])"
```

### Step 4 — Verify access before running the module

```bash
python -c "
from huggingface_hub import model_info
for m in ['ai4bharat/indictrans2-indic-en-dist-200M',
          'ai4bharat/indictrans2-en-indic-dist-200M']:
    info = model_info(m)
    print(f'OK: {m}')
"
```

Both lines should print `OK:`. If you still see `GatedRepoError`, the licence
terms have not been accepted on the HuggingFace website for that model.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

**Windows only** — IndicTransToolkit requires a special flag due to its
Cython build step:

```bash
pip install IndicTransToolkit --no-build-isolation
```

Verified working: Windows 11, Python 3.12.

### 2. Authenticate with HuggingFace

See the [Required: HuggingFace Authentication](#️-required-huggingface-authentication-do-this-first)
section above.

### 3. First use — model download (requires internet, one-time only)

Models are downloaded automatically on the first `translate()` call and
cached to disk (`%USERPROFILE%\.cache\huggingface\hub` on Windows,
`~/.cache/huggingface/hub` on Linux).  
All subsequent calls load from disk — no internet access needed after this.

```python
from backend.translation import translate_kn_to_en

# First call: downloads ~800 MB model (Kannada → English)
text = translate_kn_to_en("ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟಿದೆ")
print(text)  # "What is my account balance?"
```

### 4. Use in pipeline

```python
from backend.translation import translate_kn_to_en, translate_en_to_kn

# STT output → NLU input
en_query = translate_kn_to_en("ಸಾಲ ಅರ್ಜಿ ಹೇಗೆ ಮಾಡಬೇಕು")
# "How do I apply for a loan?"

# Banking response → TTS input
kn_response = translate_en_to_kn("Your loan application has been submitted.")
# Kannada text
```

### 5. Run the benchmark

```bash
python backend/translation/benchmark.py
```

Outputs `translation_benchmark_results.csv` with BLEU and chrF2++ scores.

---

## File Layout

```
backend/translation/
├── __init__.py       Public API: translate(), translate_kn_to_en(), translate_en_to_kn()
├── translator.py     IndicTranslator class (HuggingFace + IndicProcessor wrapper)
├── exceptions.py     TranslationInputError definition
├── utils.py          Language code validation, text normalisation
└── benchmark.py      BLEU/chrF2++ benchmark harness

data/translation_test/
└── reference_translations.json    11 manually-written English reference translations
```

---

## Models

| Direction | HuggingFace ID | Size | Use |
|-----------|---------------|------|-----|
| Kannada → English | `ai4bharat/indictrans2-indic-en-dist-200M` | ~200M | STT output → NLU |
| English → Kannada | `ai4bharat/indictrans2-en-indic-dist-200M` | ~200M | Response → TTS |

Both are the **distilled 200M** variants — not the 1.1B full models.  
Memory usage: ~800 MB per model (float32 on CPU), ~400 MB (float16 on GPU).  
Both models are loaded only if both directions are used; a pipeline using
only Kannada→English loads one model.

---

## API Reference

### `translate_kn_to_en(text) → str`

Translate Kannada text to English. Use this in the NLU module.

### `translate_en_to_kn(text) → str`

Translate English text to Kannada. Use this in the TTS module.

### `translate(text, src_lang="kan_Knda", tgt_lang="eng_Latn") → str`

Generic translation function. Prefer the named wrappers above for
downstream modules to avoid language code typos.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `text` | required | Source text string |
| `src_lang` | `"kan_Knda"` | IndicTrans2 source language code |
| `tgt_lang` | `"eng_Latn"` | IndicTrans2 target language code |

**Returns:** Translated string, or `""` for empty/whitespace input.  
**Raises:** `TranslationInputError` for unsupported directions or non-string input.

---

## Expected BLEU / chrF2++ Ranges — Sanity Check

Run `benchmark.py` after model download to confirm the module is working.

> Assumes: **11 banking phrase pairs** (clips 001–004, 006–007, 011–015),
> single reference per sentence, `num_beams=5`, CPU or GPU inference.
> Clips 005, 008, 009, 010 were removed when the test set was finalised.

| Metric | Actual result | Notes |
|--------|--------------|-------|
| Corpus BLEU | **16.30** | Single-reference BLEU on short sentences is always lower than multi-reference benchmarks. BLEU 0 on clip_012 ("Enable Internet Banking" vs "Please activate internet banking") drags the corpus number down despite being a correct translation. |
| Corpus chrF2++ | **48.28** | Character-level metric; more forgiving of valid paraphrases. Lead with this in your report. |
| Avg inference time | **1.0 s/phrase** on GPU | At `num_beams=5`. First call includes model load (~9 s); subsequent calls are ~0.2 s each. |

**Note on BLEU scores for your report:**  
BLEU penalises valid paraphrases. "What is the balance in my account?" vs the
reference "What is my account balance?" scores poorly despite being a correct
translation. Always accompany BLEU with chrF2++ and a qualitative review of
a few output samples. See the IndicTrans2 paper for published benchmarks on
Kannada↔English (reported at corpus level with multiple references).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `GatedRepoError` | HF auth not set up | Complete the [Authentication](#️-required-huggingface-authentication-do-this-first) steps above |
| `AttributeError: 'NoneType' object has no attribute 'shape'` during `generate()` | IndicTrans2's `_reorder_cache()` uses the legacy tuple cache format, which is incompatible with `transformers >=4.38`'s `DynamicCache` beam search default. | The fix is already applied in `translator.py`: `use_cache=False` is passed to `model.generate()`, bypassing `_reorder_cache` entirely. If you see this error, ensure you are using the `translator.py` from this repo and not an older cached version. Do NOT downgrade `transformers` — it would violate IndicTransToolkit's `>=4.51` requirement. |
| `OSError: Can't load tokenizer` | Model files corrupted or partially downloaded | Delete `~/.cache/huggingface/hub/models--ai4bharat--indictrans2*` and re-run |
| `ModuleNotFoundError: IndicTransToolkit` | Package not installed | `pip install IndicTransToolkit --no-build-isolation` (Windows) or `pip install indictranstoolkit` (Linux) |
| Output is garbled/empty | Wrong model loaded for direction | Confirm `MODEL_IDS` in `__init__.py` — indic-en for Kannada→English, en-indic for English→Kannada |
| `TranslationInputError: Unsupported direction` | Wrong language codes passed | Use `translate_kn_to_en()` / `translate_en_to_kn()` instead of `translate()` with manual codes |
| BLEU = 0 | All outputs empty | Usually means model loaded but IndicProcessor preprocessing failed — check `IndicTransToolkit` version (`>=1.1`) |
