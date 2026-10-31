# Kannada Voice Banking Assistant — Complete Project Guide

> Written for juniors, internees, and anyone picking up this project for the first time.
> Read top to bottom once. After that, use it as a reference.

---

## Table of Contents

1. [What Is This Project?](#1-what-is-this-project)
2. [Problem It Solves](#2-problem-it-solves)
3. [How It Works — Big Picture](#3-how-it-works--big-picture)
4. [Full Pipeline — Step by Step](#4-full-pipeline--step-by-step)
5. [Project Folder Structure](#5-project-folder-structure)
6. [Each Module Explained](#6-each-module-explained)
   - [Module 1 — STT (Speech to Text)](#module-1--stt-speech-to-text)
   - [Module 2 — Translation](#module-2--translation)
   - [Module 3 — NLU (Intent Classification)](#module-3--nlu-intent-classification)
   - [Module 4 — Decision Router](#module-4--decision-router)
   - [Module 5 — TTS (Text to Speech)](#module-5--tts-text-to-speech)
7. [The 7 Banking Intents](#7-the-7-banking-intents)
8. [The API Layer](#8-the-api-layer)
9. [The Frontend](#9-the-frontend)
10. [The Database](#10-the-database)
11. [ML Models Used](#11-ml-models-used)
12. [Environment Variables (.env)](#12-environment-variables-env)
13. [Setting Up on a New PC](#13-setting-up-on-a-new-pc)
14. [Running the Project Every Day](#14-running-the-project-every-day)
15. [Demo Accounts](#15-demo-accounts)
16. [Common Errors and Fixes](#16-common-errors-and-fixes)
17. [Benchmark Results](#17-benchmark-results)
18. [Architecture Decisions and Tradeoffs](#18-architecture-decisions-and-tradeoffs)
19. [Future Improvements](#19-future-improvements)

---

## 1. What Is This Project?

This is a **voice-based banking assistant for Kannada speakers**. A customer walks up to a kiosk, speaks in Kannada, and the system understands what they want and responds back in spoken Kannada — no typing, no English required.

It is a **final-year engineering project** in the AI/ML domain. It demonstrates an end-to-end pipeline of five chained AI/ML models working together in real time.

---

## 2. Problem It Solves

Rural bank customers in Karnataka often:
- Cannot read or type in English
- Are not comfortable with touchscreen menus
- Have to wait for a bank employee for even simple queries like checking balance or interest rates

This kiosk lets them simply **speak in Kannada** and get an instant voice response.

---

## 3. How It Works — Big Picture

```
Customer speaks Kannada into microphone
              ↓
      [STT] Whisper model
      Kannada audio → Kannada text
              ↓
   [Translation] IndicTrans2 model
      Kannada text → English text
              ↓
      [NLU] DistilBERT model
      English text → Intent label
      e.g. "check_balance"
              ↓
   [Decision Router] Python logic
      Intent → Response text (English)
      + determines if it needs a form
              ↓
      [TTS] MMS-TTS model
      English response → Kannada speech
      (internally translates EN→KN first)
              ↓
Customer hears Kannada voice response
```

Every stage runs one after another (sequential). Each model loads, does its job, and unloads before the next one starts — this keeps RAM usage manageable.

---

## 4. Full Pipeline — Step by Step

The main file is `backend/pipeline.py`. The function `run_pipeline(audio_path)` runs all 5 stages.

### Stage 1 — STT
- Takes a `.wav` audio file
- Runs it through **faster-whisper** (a fast CTranslate2 version of Whisper)
- Returns Kannada text (e.g. `"ನನ್ನ ಖಾತೆಯ ಶಿಲ್ಕು ಎಷ್ಟಿದೆ"`)

### Stage 2 — Translation
- Takes the Kannada text
- Runs it through **IndicTrans2** (ai4bharat model)
- Returns English text (e.g. `"What is my account balance"`)

### Stage 3 — NLU
- Takes the English text
- Runs it through a **fine-tuned DistilBERT** classifier
- Returns an intent label + confidence score (e.g. `"check_balance"`, `0.97`)
- Also handles: low confidence → asks for clarification, follow-up questions, form menu requests

### Stage 4 — Decision Router
- Pure Python, no ML
- Takes the intent label
- Looks up `data/bank_info.json` for informational queries
- Returns a structured English response + whether a form is needed

### Stage 5 — TTS
- Takes the English response text
- First translates it to Kannada sentence by sentence (IndicTrans2 EN→KN)
- Then runs through **Facebook MMS-TTS** (mms-tts-kan) to produce audio
- Returns a numpy audio array that gets streamed to the frontend

---

## 5. Project Folder Structure

```
voice-based-assistant/
│
├── backend/                    # All AI/ML logic
│   ├── pipeline.py             # Main pipeline orchestrator
│   ├── pipeline_bridge.py      # Worker thread that keeps pipeline warm
│   ├── stt/                    # Module 1: Speech-to-Text
│   ├── translation/            # Module 2: Kannada ↔ English translation
│   ├── nlu/                    # Module 3: Intent classification
│   ├── decision_router/        # Module 4: Routing logic
│   ├── tts/                    # Module 5: Text-to-Speech
│   ├── forms/                  # Form templates + entity extraction
│   ├── db/                     # Customer database (SQLite / MongoDB)
│   ├── balance_lookup.py       # Real account balance lookup
│   └── admin_flow.py           # Admin-specific flows
│
├── api/                        # FastAPI web server
│   ├── main.py                 # App entry point, startup, health
│   ├── routes/                 # URL route handlers
│   │   ├── pipeline.py         # POST /api/pipeline — main voice endpoint
│   │   ├── kiosk.py            # Kiosk session management
│   │   ├── forms.py            # Form submission endpoints
│   │   ├── balance.py          # Balance lookup endpoint
│   │   ├── history.py          # Conversation history
│   │   ├── admin.py            # Admin login, controls
│   │   └── landing.py          # Landing/health page
│   ├── kiosk_state.py          # Session state per kiosk
│   ├── admin_auth.py           # Admin username/password check
│   ├── audio.py                # Audio file utilities
│   └── app_settings.py         # Reads and validates .env settings
│
├── frontend/                   # React + TypeScript UI
│   ├── src/App.tsx             # Customer-facing kiosk UI
│   ├── src/AdminApp.tsx        # Admin dashboard
│   └── src/components/         # Reusable UI components
│
├── data/
│   ├── nlu_training_data.json  # 301 labeled Kannada/English sentences
│   ├── bank_info.json          # Bank rates, procedures, responses
│   ├── forms.json              # Form field templates
│   └── stt_test_audio/         # Test audio clips + transcripts
│
├── models/
│   ├── whisper-kannada-medium-ct2/   # STT model (CTranslate2 int8 format)
│   └── nlu-distilbert/               # Fine-tuned DistilBERT checkpoint
│
├── scripts/
│   ├── setup_new_pc.ps1        # Full automated setup script
│   ├── constraints.txt         # Pip version pins
│   ├── deployment_check.py     # Checks all services are running
│   └── production_smoke_test.py # End-to-end test before demo
│
├── docs/                       # Documentation
├── .env                        # Your local config (never commit secrets)
├── .env.example                # Template for .env
├── requirements.txt            # Python packages
└── README.md                   # Quick start
```

---

## 6. Each Module Explained

### Module 1 — STT (Speech to Text)

**Location:** `backend/stt/`

**What it does:** Converts a `.wav` audio file of spoken Kannada into a Kannada text string.

**Model used:** `vasista22/whisper-kannada-medium` — a Whisper Medium model fine-tuned specifically on Kannada speech. It is converted to CTranslate2 int8 format (stored in `models/whisper-kannada-medium-ct2/`) for faster inference.

**Key files:**
- `transcriber.py` — `KannadaTranscriber` class, wraps faster-whisper
- `__init__.py` — exposes `transcribe(audio_path)` and `unload_model()`
- `convert_models.py` — one-time script to download from HuggingFace and convert to CTranslate2

**How to use it standalone:**
```python
from backend.stt import transcribe
text = transcribe("data/stt_test_audio/clip_001.wav")
print(text)  # ನನ್ನ ಖಾತೆಯ ಶಿಲ್ಕು ಎಷ್ಟಿದೆ
```

---

### Module 2 — Translation

**Location:** `backend/translation/`

**What it does:** Translates between Kannada and English in both directions.
- KN → EN: used after STT (Kannada text → English for NLU)
- EN → KN: used inside TTS (English response → Kannada before MMS-TTS)

**Model used:** `ai4bharat/indictrans2-indic-en-dist-200M` (KN→EN) and `ai4bharat/indictrans2-en-indic-dist-200M` (EN→KN). These are gated models — you must accept their license on HuggingFace.

**Key files:**
- `translator.py` — `IndicTranslator` class
- `__init__.py` — exposes `translate_kn_to_en()`, `translate_en_to_kn()`, `unload_model()`

**Important:** These are ~900MB models each. They are loaded and unloaded per request to save RAM unless `BANK_PIPELINE_KEEP_LOADED=1`.

---

### Module 3 — NLU (Intent Classification)

**Location:** `backend/nlu/`

**What it does:** Takes the English translation of what the user said and classifies it into one of 7 banking intent categories.

**Two classifiers exist:**
1. **Keyword baseline** (`keyword_classifier.py`) — simple rule-based, no ML, ~60% accuracy
2. **DistilBERT fine-tuned** (`distilbert_classifier.py`) — ML model trained on 301 labeled examples, ~97% accuracy

In production, both run. If DistilBERT confidence is below threshold (default 0.35), it asks the user to clarify.

**Training:**
```powershell
.\.venv\Scripts\python.exe backend\nlu\train.py
```
Takes ~3 minutes on CPU. Saves the model to `models/nlu-distilbert/`.

**Key files:**
- `intents.py` — single source of truth for all 7 intent labels
- `train.py` — fine-tuning script (run once)
- `distilbert_classifier.py` — inference using saved checkpoint
- `keyword_classifier.py` — fallback rule-based classifier
- `clarification.py` — builds "Did you mean X or Y?" prompts
- `follow_up.py` — handles follow-up questions in the same conversation

---

### Module 4 — Decision Router

**Location:** `backend/decision_router/`

**What it does:** Takes an intent label and decides:
- **Informational** → looks up `data/bank_info.json` and returns a text answer
- **Transactional** → returns a list of fields the system needs to collect (opens a form)

**No ML here** — pure Python dictionary lookups. Fast and deterministic.

**Informational intents** (answered from bank_info.json):
- `interest_rate_query` → reads all rates from bank_info.json
- `account_info_query` → reads procedure text (ATM block, PIN change, etc.)

**Transactional intents** (need form collection):
- `check_balance` → needs `account_number`
- `open_account` → needs `full_name`, `date_of_birth`, `address`, `account_type`
- `apply_loan` → needs `full_name`, `loan_type`, `loan_amount`, `income`
- `deposit_money` → needs `account_number`, `amount`
- `withdraw_money` → needs `account_number`, `amount`

---

### Module 5 — TTS (Text to Speech)

**Location:** `backend/tts/`

**What it does:** Converts an English response text into spoken Kannada audio.

**Two TTS engines:**
1. **Remote TTS** (default when configured) — calls `https://tts.sarastralabs.com` which runs Parler-TTS on a GPU box. Produces more natural speech. Requires `BANK_TTS_REMOTE_KEY` in `.env`.
2. **MMS-TTS** (local fallback) — uses `facebook/mms-tts-kan` locally. Smaller model, less natural but works offline.

**Flow inside TTS:**
```
English response text
    → split into sentences
    → translate_en_to_kn() each sentence (IndicTrans2)
    → MMS-TTS each Kannada sentence
    → concatenate audio chunks
    → return numpy array
```

**Config in .env:**
```
BANK_TTS_ENGINE=auto          # auto = try remote first, fall back to MMS
BANK_TTS_ENGINE=mms           # always use local MMS
BANK_TTS_REMOTE_URL=https://tts.sarastralabs.com
BANK_TTS_REMOTE_KEY=your_key_here
BANK_TTS_SPEAKER=Suresh       # voice name for Parler
```

---

## 7. The 7 Banking Intents

These are defined in `backend/nlu/intents.py` and are the single source of truth.

| Intent | Example phrase | Route | What happens |
|--------|---------------|-------|--------------|
| `check_balance` | "What is my account balance" | Transactional | Asks for account number, looks up balance in DB |
| `open_account` | "I want to open a new account" | Transactional | Collects name, DOB, address, account type |
| `apply_loan` | "I need a home loan" | Transactional | Collects name, loan type, amount, income |
| `deposit_money` | "I want to deposit money" | Transactional | Collects account number, amount |
| `withdraw_money` | "I want to withdraw cash" | Transactional | Collects account number, amount |
| `account_info_query` | "How do I block my ATM card" | Informational | Reads procedure from bank_info.json |
| `interest_rate_query` | "What is the FD interest rate" | Informational | Reads all rates from bank_info.json |

---

## 8. The API Layer

**Location:** `api/`

The API is a **FastAPI** web server running on port 8000. The frontend talks to it via HTTP.

### Key endpoints

| Method | URL | What it does |
|--------|-----|--------------|
| GET | `/api/health` | Check if API + TTS are healthy |
| POST | `/api/pipeline` | Main endpoint — send audio, get response |
| POST | `/api/kiosk/start` | Start a kiosk session |
| POST | `/api/kiosk/stop` | End a kiosk session |
| GET | `/api/balance/{account}` | Look up account balance |
| POST | `/api/forms/submit` | Submit a filled form |
| GET | `/api/history` | Get conversation history |
| POST | `/api/admin/login` | Admin login |

### How the pipeline endpoint works (`/api/pipeline`)
1. Receives an audio file (WAV) from the frontend
2. Calls `run_pipeline(audio_path)` from `backend/pipeline.py`
3. Returns a JSON response with:
   - `kannada_text` — what the user said (STT output)
   - `english_text` — translation
   - `intent` — classified intent
   - `response_text` — English response
   - `audio_base64` — Kannada voice response as base64 WAV
   - `form_id` — if a form needs to be opened
   - `stage_times` — how long each stage took

### Startup sequence
When you run `uvicorn api.main:app`:
1. Loads `.env`
2. Initialises SQLite customer database (seeds 6 demo accounts)
3. Warms the pipeline (loads all models once so first request is fast)
4. Warms TTS cache (pre-generates common phrases)
5. Starts accepting requests

---

## 9. The Frontend

**Location:** `frontend/`

Built with **React + TypeScript + Vite**.

### Two UIs

**1. Agent UI (port 5173)** — `src/App.tsx`
- The kiosk screen the customer sees
- Shows "Tap to speak" button
- Records audio from microphone
- Sends to API, plays back Kannada audio response
- Shows transcript of what was said and what the system responded
- Opens forms when a transactional intent is detected

**2. Admin UI (port 5174)** — `src/AdminApp.tsx`
- Login: `admin` / `bank@123`
- Shows live session state
- Can start/stop kiosk
- Shows conversation history
- Shows API health status

### How to start frontend
```powershell
cd frontend
npm install       # first time only
.\scripts\dev-all.ps1   # starts both UIs
```

---

## 10. The Database

**Location:** `backend/db/`

Two modes — the system auto-detects which to use:

**SQLite (default)** — `backend/db/customers.py`
- Local file-based database
- Auto-created on first run
- Seeded with 6 demo accounts at startup
- No setup needed

**MongoDB (optional)** — if `MONGO_URI` is set in `.env`
- Used for production/multi-kiosk deployments
- Stores customers, accounts, transaction history

### Demo accounts (seeded automatically)
All 6 demo customers have accounts in the SQLite DB. Account numbers are 10-digit numbers. The balance lookup works against this DB — when a customer says their account number during `check_balance`, it queries this.

---

## 11. ML Models Used

| Model | Purpose | Size | Where stored |
|-------|---------|------|-------------|
| `vasista22/whisper-kannada-medium` | STT — Kannada speech → text | ~740 MB (int8) | `models/whisper-kannada-medium-ct2/` |
| `ai4bharat/indictrans2-indic-en-dist-200M` | Translation KN→EN | ~913 MB | HuggingFace cache |
| `ai4bharat/indictrans2-en-indic-dist-200M` | Translation EN→KN | ~1.1 GB | HuggingFace cache |
| `distilbert-base-uncased` (fine-tuned) | NLU intent classification | ~268 MB | `models/nlu-distilbert/` |
| `facebook/mms-tts-kan` | TTS — Kannada speech synthesis | ~36 MB | HuggingFace cache |

**Why these models?**
- **Whisper** — best open-source STT, vaani-kannada fine-tune dramatically improves Kannada accuracy (WER drops from 111% to 50%)
- **IndicTrans2** — best open translation model for Indian languages, built specifically for Indic scripts
- **DistilBERT** — small, fast, accurate for classification; fine-tuning on 301 examples gives 97.8% accuracy
- **MMS-TTS** — only reliable open-source Kannada TTS model available, works fully offline

---

## 12. Environment Variables (.env)

The `.env` file in the project root controls all runtime behaviour. Copy `.env.example` to `.env` and fill in values.

| Variable | Default | What it does |
|----------|---------|--------------|
| `BANK_TTS_ENGINE` | `auto` | `auto` = remote then MMS fallback; `mms` = always local |
| `BANK_TTS_REMOTE_URL` | — | URL of remote Parler TTS server |
| `BANK_TTS_REMOTE_KEY` | — | API key for remote TTS |
| `BANK_TTS_SPEAKER` | `Suresh` | Voice name for Parler TTS |
| `BANK_TTS_ALLOW_MMS` | `1` | Allow local MMS fallback |
| `BANK_ADMIN_USER` | `admin` | Admin panel username |
| `BANK_ADMIN_PASS` | `bank@123` | Admin panel password |
| `BANK_PIPELINE_KEEP_LOADED` | `1` | Keep models in RAM between requests (faster) |
| `BANK_PIPELINE_WORKER` | `1` | Use background worker thread for pipeline |
| `TRANSFORMERS_OFFLINE` | `1` | Prevent HuggingFace from checking internet |
| `HF_HUB_OFFLINE` | `1` | Same — use cached models only |
| `MONGO_URI` | — | MongoDB connection string (optional) |
| `BANK_NLU_MIN_CONF` | `0.35` | Below this confidence, ask for clarification |

---

## 13. Setting Up on a New PC

### Requirements
- Windows 10 or 11
- Python 3.12 (download from python.org — tick "Add to PATH")
- Node.js 18+ (download from nodejs.org)
- Microsoft C++ Build Tools (for IndicTransToolkit compilation)
- 16 GB RAM minimum
- Good internet for first-time model downloads (~4 GB total)

### One-command setup
```powershell
cd C:\your-project-folder\bank_assistant
powershell -ExecutionPolicy Bypass -File scripts\setup_new_pc.ps1 -HfToken hf_yourtoken
```

This automatically:
1. Checks Python and Node.js
2. Creates `.venv` virtual environment
3. Installs all Python packages from `requirements.txt`
4. Saves your HuggingFace token
5. Downloads and converts all ML models
6. Runs `npm install` for frontend
7. Verifies everything is working

### HuggingFace setup (required for translation models)
The IndicTrans2 models are "gated" — you must:
1. Create a free account at https://huggingface.co
2. Go to https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M → click **"Agree and access repository"**
3. Go to https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M → click **"Agree and access repository"**
4. Go to https://huggingface.co/settings/tokens → create a **Read** token
5. Pass it as `-HfToken hf_yourtoken` to the setup script

### After setup — fix .env placeholders
Check for placeholder values and replace them:
```powershell
# Set the TTS API key
(Get-Content .env) -replace 'CHANGE_ME-must-match-tts-box', 'actual_key_here' | Set-Content .env

# Set the admin password
(Get-Content .env) -replace 'CHANGE_ME-strong-password', 'bank@123' | Set-Content .env
```

---

## 14. Running the Project Every Day

Open **2 terminals** and run one command in each:

**Terminal 1 — API server:**
```powershell
cd C:\your-project\bank_assistant
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```
Wait ~60 seconds for all models to load. You'll see:
```
[startup] pipeline ready model=vasista-medium stages={...}
INFO: Application startup complete.
```

**Terminal 2 — Frontend:**
```powershell
cd C:\your-project\bank_assistant\frontend
.\scripts\dev-all.ps1
```

**Open in browser:**
- Kiosk (customer view): `https://localhost:5173`
- Admin panel: `https://localhost:5174` → login: `admin` / `bank@123`
- From phone on same Wi-Fi: `https://<pc-ip-address>:5173`

---

## 15. Demo Accounts

Six accounts are pre-seeded in the SQLite database automatically on first startup.

To check what accounts exist:
```powershell
.\.venv\Scripts\python.exe -c "from backend.db.customers import list_customers; [print(c) for c in list_customers()]"
```

For `check_balance` demo: the customer speaks their account number in Kannada (or English), the system extracts the digits, and looks up the balance in the local DB.

---

## 16. Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `ImportError: cannot import name 'PreTrainedTokenizerBase'` | `transformers` v5 installed | Run `pip install "transformers>=4.51,<5"` |
| `403 GatedRepoError` for IndicTrans2 | HF account hasn't accepted the license | Log into HF as the token owner, go to both model pages, click "Agree and access repository" |
| `Invalid TTS API key` | `BANK_TTS_REMOTE_KEY` is placeholder in `.env` | Replace `CHANGE_ME-must-match-tts-box` with the real key |
| `CHANGE_ME-strong-password` admin login fails | Admin password not set | Replace in `.env` with `bank@123` or chosen password |
| `WinError 10048` port already in use | Another uvicorn is running | Close the old terminal or run `netstat -ano | findstr :8000` to find and kill it |
| `'vite' is not recognized` | `npm install` not run | Run `npm install` in the `frontend/` folder |
| Script parse errors with `â€"` characters | File encoding corruption | Re-save the script as UTF-8 without BOM |
| Pipeline fails silently | Models not downloaded | Re-run setup script or check `models/` folder exists |
| `customers: 0` in startup log | DB already exists, skip seed | Normal — means customers were already seeded before |

---

## 17. Benchmark Results

These numbers are from the evaluation scripts in `backend/stt/benchmark.py`, `backend/nlu/evaluate.py`, etc.

### STT (11 test clips)
| Model | WER% | CER% |
|-------|------|------|
| openai/whisper-medium (generic) | 111.11% | 87.55% |
| vasista22/whisper-kannada-medium | **50.00%** | **20.60%** |

The Kannada-fine-tuned model makes about half as many word errors.

### NLU (46 test sentences, stratified split)
| Model | Accuracy | Macro F1 |
|-------|----------|----------|
| Keyword baseline | 60.9% | 0.619 |
| Fine-tuned DistilBERT | **97.8%** | **0.979** |

The DistilBERT model is dramatically more accurate. The keyword baseline is kept as a fallback.

### Translation (BLEU/chrF2++)
| Metric | Score |
|--------|-------|
| Corpus BLEU | 16.30 |
| Corpus chrF2++ | **48.28** |

chrF2++ is the better metric for Kannada (handles script-level character n-grams). 48.28 is strong for a 200M parameter model on a low-resource language.

---

## 18. Architecture Decisions and Tradeoffs

**Why sequential pipeline instead of parallel?**
The four large models together would require ~3 GB VRAM or ~6 GB RAM simultaneously. Sequential load-unload keeps peak usage at single-model level. Latency is ~8-15 seconds per request on CPU, ~3-5 seconds on GPU.

**Why DistilBERT for NLU instead of a larger LLM?**
DistilBERT is 66M parameters — loads in under a second. An LLM would take 30+ seconds to load per request. For 7 intents with 301 training examples, DistilBERT reaches 97.8% accuracy — more than sufficient.

**Why translate to English first instead of doing NLU in Kannada?**
There is no Kannada-specific NLU/intent model available. IndicTrans2 translation quality is high enough that the English NLU model works well. This avoids needing Kannada training data for NLU.

**Why MMS-TTS for voice output?**
`facebook/mms-tts-kan` is the only reliable open-source Kannada TTS model. The Parler-TTS remote server produces more natural speech but requires a GPU box and API key. MMS-TTS is the offline fallback.

**Why SQLite by default?**
Zero setup. Works immediately on any machine. MongoDB is available for multi-kiosk production deployments where a shared customer database is needed.

---

## 19. Future Improvements

Things not yet implemented but identified as future work:

1. **Entity extraction (NER)** — currently forms collect fields one-by-one via voice prompts. A spaCy NER model could extract account numbers, names, amounts directly from speech in one turn.

2. **Better Kannada STT** — WER of 50% means 1 in 2 words is wrong. A larger Whisper model fine-tuned on more Kannada data would help significantly.

3. **Multi-turn dialogue** — the current system handles one intent per turn. A proper dialogue manager would handle multi-turn conversations ("actually, I meant withdraw not deposit").

4. **On-device deployment** — currently needs a PC. Running on a Raspberry Pi or Jetson Nano would enable cheaper kiosk hardware.

5. **More intents** — the 7 intents cover common queries. Adding mini-statement, cheque request, FD booking etc. would make it more complete.

6. **Noise robustness** — the STT model struggles with background noise typical of a busy bank branch. Noise cancellation as a pre-processing step would help.

---

## Quick Reference Card

```
Start API:
  .\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000

Start Frontend:
  cd frontend && .\scripts\dev-all.ps1

Kiosk URL:     https://localhost:5173
Admin URL:     https://localhost:5174
Admin login:   admin / bank@123

Re-train NLU:
  .\.venv\Scripts\python.exe backend\nlu\train.py

Run smoke test:
  .\.venv\Scripts\python.exe scripts\production_smoke_test.py

Check which HF account is logged in:
  .\.venv\Scripts\python.exe -c "from huggingface_hub import whoami; print(whoami()['name'])"

Switch HF account:
  .\.venv\Scripts\python.exe -c "from huggingface_hub import login; login(token='hf_...')"
```

---

*Last updated: September 2026. For questions, refer to `docs/DEMO_AND_INTERACTION_GUIDE.md` for demo scripts and `docs/WHAT_TO_SPEAK.md` for Kannada phrases to test with.*
