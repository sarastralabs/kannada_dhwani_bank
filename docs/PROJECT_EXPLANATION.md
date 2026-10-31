# Kannada Voice Banking Assistant — Project Explanation

**Purpose of this document:** Explain the system flow, which models are used and why, where they come from, and how training data was prepared — for demos, viva, or team walkthroughs.

---

## 1. What the project is

This is an **informational Kannada voice banking assistant**.

- The user **speaks in Kannada**.
- The system returns a **spoken Kannada reply** that explains **how** to do a banking task (ATM, branch, forms, rates).
- It does **not** connect to a real bank, fetch live balances, or show personal account data.

**One-line summary:**  
Speak Kannada → understand the banking intent → reply with how-to guidance in Kannada voice.

---

## 2. End-to-end flow

```
User speaks Kannada
        │
        ▼
┌───────────────────────────────┐
│ 1. STT (Speech-to-Text)       │  Kannada audio → Kannada text
│    Whisper VAANI + faster-whisper
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│ 2. Translation (KN → EN)      │  Kannada text → English text
│    IndicTrans2                │
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│ 3. NLU (Intent classification)│  English text → intent label
│    Fine-tuned DistilBERT      │
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│ 4. Decision Router            │  Intent → English reply text
│    Rules + bank_info.json     │
└───────────────────────────────┘
        │
        ▼
┌───────────────────────────────┐
│ 5. TTS (Text-to-Speech)       │  English reply → Kannada speech
│    IndicTrans2 EN→KN + MMS-TTS│
└───────────────────────────────┘
        │
        ▼
User hears Kannada answer
```

### Why this order?

| Choice | Reason |
|--------|--------|
| STT first | User input is voice; we need text to process |
| Translate to English before NLU | Intent classification and banking reply templates are easier and more reliable in English |
| Rule-based router (not an LLM) | Replies stay safe, predictable, and clearly informational |
| Translate back + TTS | User experience stays fully in Kannada |

### Example walkthrough

| Step | Example |
|------|---------|
| User says | Something like “ಬ್ಯಾಂಕ್ ಬ್ಯಾಲೆನ್ಸ್ ಅನ್ನು ಪರಿಶೀಲಿಸುವುದು ಹೇಗೆ” (how to check bank balance) |
| STT | Kannada transcript |
| KN→EN | English: “How to check bank balance?” |
| NLU | Intent: `check_balance` |
| Router | English guidance: use ATM / branch / SMS — **not** an actual balance |
| EN→KN + TTS | Spoken Kannada reply |

---

## 3. Application layers (around the ML pipeline)

| Layer | Technology | Role |
|-------|------------|------|
| Frontend | React (Vite) | Home, Assist, Forms (voice fill + print), History |
| Backend API | FastAPI + uvicorn | Accept audio, run pipeline, return text + audio |
| History | SQLite | Store past queries and reply audio for replay |
| ML pipeline | Python modules under `backend/` | STT → Translation → NLU → Router → TTS |

The UI sends audio to the API; the API runs the pipeline and returns the transcript, intent, guidance text, and Kannada audio.

---

## 4. Models used — summary table

| Stage | Model / component | Source | Trained by us? |
|-------|-------------------|--------|----------------|
| STT | `ARTPARK-IISc/whisper-medium-vaani-kannada` (converted to CTranslate2) | HuggingFace | **No** — download + convert only |
| Translation KN→EN | `ai4bharat/indictrans2-indic-en-dist-200M` | HuggingFace (gated) | **No** |
| NLU | `distilbert-base-uncased` → fine-tuned checkpoint | HuggingFace base; our fine-tune | **Yes** |
| Router | Static rules + `data/bank_info.json` | Project file | N/A (not ML) |
| Translation EN→KN | `ai4bharat/indictrans2-en-indic-dist-200M` | HuggingFace (gated) | **No** |
| TTS | `facebook/mms-tts-kan` | HuggingFace (public) | **No** |

**Important talking point:** Only the **NLU DistilBERT** model is trained in this project. Speech and translation models are pretrained and downloaded.

---

## 5. Models in detail

### 5.1 Speech-to-Text (STT)

| Item | Detail |
|------|--------|
| **Model** | Whisper Medium fine-tuned for Kannada |
| **HuggingFace ID** | [`ARTPARK-IISc/whisper-medium-vaani-kannada`](https://huggingface.co/ARTPARK-IISc/whisper-medium-vaani-kannada) |
| **Runtime** | [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) with CTranslate2 **int8** |
| **Local path** | `models/whisper-medium-vaani-ct2/` |
| **Why this model** | Plain `openai/whisper-medium` is multilingual but weaker on Kannada. The VAANI fine-tune was trained on conversational Kannada speech (ARTPARK / IISc), so it fits a Kannada banking demo better. |
| **What we did** | Downloaded from HuggingFace and converted with `python backend/stt/convert_models.py --model specialized`. We did **not** retrain Whisper. |
| **Optional baseline** | `openai/whisper-medium` converted the same way — useful for comparison (WER benchmarks), not required for the live app. |

**Upstream data (VAANI):** The STT model’s Kannada quality comes from the **VAANI** dataset used by ARTPARK-IISc. That training was done by the model authors, not by us.

---

### 5.2 Translation (Kannada ↔ English)

| Direction | HuggingFace ID | Role in pipeline |
|-----------|----------------|------------------|
| KN → EN | [`ai4bharat/indictrans2-indic-en-dist-200M`](https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M) | STT output → English for NLU |
| EN → KN | [`ai4bharat/indictrans2-en-indic-dist-200M`](https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M) | Router reply → Kannada for TTS |

| Item | Detail |
|------|--------|
| **Family** | IndicTrans2 (AI4Bharat), distilled **200M** parameter models |
| **Why** | Strong Indic–English quality; distilled size is practical for a student demo on CPU/GPU |
| **Auth** | **Gated** — accept license on HuggingFace + login with a Read token |
| **What we did** | Accept terms, authenticate, download once into HF cache; then run offline |
| **Training by us?** | No |

Toolkit used around these models: `IndicTransToolkit` + HuggingFace `transformers`.

---

### 5.3 NLU — Intent classification (the model we trained)

| Item | Detail |
|------|--------|
| **Base model** | [`distilbert-base-uncased`](https://huggingface.co/distilbert-base-uncased) |
| **Task** | Sequence classification into **7 banking intents** |
| **Train script** | `python backend/nlu/train.py` |
| **Saved checkpoint** | `models/nlu-distilbert/` |
| **Why DistilBERT** | Small, fast, good enough for short intent labels; no need for a large LLM for this task |
| **Baseline** | Keyword classifier (no training) — for comparison in evaluation |

#### Supported intents

1. `open_account`
2. `check_balance`
3. `apply_loan`
4. `deposit_money`
5. `withdraw_money`
6. `account_info_query`
7. `interest_rate_query`

#### Training data — where it came from

| Item | Detail |
|------|--------|
| **File** | `data/nlu_training_data.json` |
| **Size** | ~301 labeled English sentences |
| **Balance** | Roughly 42–49 examples per intent |
| **Source** | **Custom dataset created for this project** — not scraped from a live bank API or customer corpus |
| **Language of labels** | English (because NLU runs **after** KN→EN translation) |
| **Design choice** | Mix of natural English *and* slightly formal / translation-like phrasing (as IndicTrans2 might produce), so the classifier matches real pipeline text |

**Example entries (illustrative):**

```json
{ "text": "I want to open a savings account", "intent": "open_account" }
{ "text": "How do I check my account balance", "intent": "check_balance" }
```

#### How training works

1. Load `data/nlu_training_data.json`
2. Stratified split: ~70% train / 15% validation / 15% test (`seed=42`)
3. Fine-tune DistilBERT with a standard classification head (`num_labels=7`)
4. Save best checkpoint to `models/nlu-distilbert/`
5. Optionally evaluate vs keyword baseline (`backend/nlu/evaluate.py`)

**Talking point:** “We collected / authored ~300 banking query sentences, labeled them with seven intents, and fine-tuned DistilBERT. That is the only model training done in this project.”

---

### 5.4 Decision Router (not a neural model)

| Item | Detail |
|------|--------|
| **Logic** | Pure Python rules based on predicted intent |
| **Knowledge file** | `data/bank_info.json` |
| **Contents** | Interest-rate wording, account procedures (name change, ATM block, etc.), check-balance disclaimer |
| **Why not an LLM** | Controlled, explainable answers; no invented personal balances; clear “informational demo” boundary |

**Example content idea in `bank_info.json`:** savings and FD rates as spoken-friendly text, steps for common procedures, and an explicit note that real-time balance is not available in this demonstration.

---

### 5.5 Text-to-Speech (TTS)

| Item | Detail |
|------|--------|
| **Model** | [`facebook/mms-tts-kan`](https://huggingface.co/facebook/mms-tts-kan) |
| **Type** | MMS-TTS (VITS) for Kannada |
| **Size** | ~36 MB |
| **Auth** | Public — no gated license |
| **Pipeline step** | English router reply → EN→KN (IndicTrans2) → Kannada waveform |
| **Why** | Lightweight Kannada voice synthesis that runs offline after one download |
| **Training by us?** | No |

---

## 6. What we downloaded vs what we trained

```
DOWNLOADED (pretrained)
├── Whisper VAANI Kannada          (STT)
├── IndicTrans2 KN→EN              (translation)
├── IndicTrans2 EN→KN              (translation)
├── DistilBERT base (uncased)      (starting point for NLU)
└── MMS-TTS Kannada                (TTS)

TRAINED BY US
└── DistilBERT fine-tuned on our 7-intent banking dataset
    Data: data/nlu_training_data.json
    Output: models/nlu-distilbert/

PROJECT KNOWLEDGE (hand-written, not ML)
└── data/bank_info.json            (router replies)
```

---

## 7. Data sources — quick reference

| Data / model | Origin | Role |
|--------------|--------|------|
| VAANI (behind STT checkpoint) | ARTPARK-IISc / VAANI Kannada speech research | Improves Kannada STT; we use their published HF model |
| IndicTrans2 | AI4Bharat (HuggingFace, gated) | Kannada ↔ English translation |
| NLU sentences | **Our project** — `nlu_training_data.json` | Fine-tune DistilBERT intents |
| Bank reply text | **Our project** — `bank_info.json` | Router answers |
| DistilBERT base | HuggingFace | Starting weights for NLU |
| MMS-TTS Kan | Meta / Facebook (HuggingFace) | Kannada speech output |

---

## 8. Scope and limitations (say this clearly)

1. **Informational only** — explains *how* to do banking tasks; does not show real balances or personal data.
2. **No core banking integration** — no live CBS / account APIs.
3. **Offline after setup** — models are cached locally; internet is needed mainly for first-time download and gated-model auth.
4. **TTS quality** — intelligible Kannada, synthetic/robotic tone typical of compact VITS models; acceptable for a pipeline demo.
5. **NLU domain** — trained on ~300 English banking phrases for seven intents; out-of-domain speech may fall to a weak or wrong intent.

---

## 9. Suggested 60-second oral explanation

> We built a Kannada voice banking assistant with a five-stage pipeline. Spoken Kannada is converted to text using a Whisper model fine-tuned on the VAANI Kannada dataset by ARTPARK-IISc, which we download from HuggingFace and run with faster-whisper. That text is translated to English with AI4Bharat IndicTrans2. We fine-tuned DistilBERT on about three hundred banking sentences that we created for seven intents. A rule-based router picks a safe how-to reply from our bank info JSON — we never fetch live account data. The reply is translated back to Kannada and spoken with Facebook’s MMS-TTS Kannada model. So only the intent classifier is trained by us; the speech and translation models are pretrained HuggingFace models.

---

## 10. File map (for navigation)

| Path | What it is |
|------|------------|
| `backend/stt/` | Speech-to-text |
| `backend/translation/` | IndicTrans2 wrappers |
| `backend/nlu/` | Intent classification + training |
| `backend/decision_router/` | Intent → reply |
| `backend/tts/` | Kannada speech synthesis |
| `data/nlu_training_data.json` | NLU training / eval data |
| `data/bank_info.json` | Banking reply content |
| `models/whisper-medium-vaani-ct2/` | Converted STT model |
| `models/nlu-distilbert/` | Fine-tuned NLU checkpoint |
| `api/` | FastAPI server |
| `frontend/` | React UI |

---

## 11. Diagram (for slides / reports)

```mermaid
flowchart LR
  A[Kannada audio] --> B[STT: Whisper VAANI]
  B --> C[KN→EN: IndicTrans2]
  C --> D[NLU: DistilBERT]
  D --> E[Router: bank_info.json]
  E --> F[EN→KN: IndicTrans2]
  F --> G[TTS: MMS-TTS Kannada]
  G --> H[Kannada audio reply]
```

---

*Document version: project explanation for demos and reviews. For install steps, see the root `README.md`.*
