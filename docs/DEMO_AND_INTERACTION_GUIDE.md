# Kannada Voice Banking — Demo & Interaction Guide

Hands-free Kannada voice kiosk for banking queries, forms, and demo balance lookup.

---

## 1. Start the system (before demo)

Open **three** terminals:

### Terminal 1 — API (required)

```powershell
cd c:\Sarastra\voice-based-assistant
py -3.12 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Wait **~60 seconds** after startup for pipeline worker + TTS pre-warm.

Verify:

```powershell
py -3.12 scripts/production_smoke_test.py
```

All checks should pass.

> Run **only one** API on port 8000. Multiple instances cause GPU errors.

### Terminal 2 & 3 — Frontend

```powershell
cd c:\Sarastra\voice-based-assistant\frontend
npm run dev:agent    # Agent lobby  → https://localhost:5173
npm run dev:admin    # Admin panel  → https://localhost:5174
```

Or both at once:

```powershell
cd c:\Sarastra\voice-based-assistant\frontend
.\scripts\dev-all.ps1
```

### Phone on same Wi‑Fi

Use the IP shown by `dev-all.ps1`, e.g.:

- Agent: `https://192.168.x.x:5173`
- Admin: `https://192.168.x.x:5174`

Accept the browser certificate warning once. Allow **camera** and **microphone**.

---

## 2. Admin — open the counter

1. Open **Admin** → `https://localhost:5174`
2. Login:
   - **Username:** `admin`
   - **Password:** `bank@123`
3. Click **Start counter** (or equivalent kiosk start control)

The **Agent** screen (`https://localhost:5173`) will show “Waiting for customer”.

---

## 3. Customer flow (Agent lobby)

| Step | What happens | What you do |
|------|----------------|-------------|
| 1 | Counter is open | Admin starts kiosk |
| 2 | Stand in camera frame | Presence detected |
| 3 | Time-based Kannada greeting | Text shows first, then voice — **wait** |
| 4 | Preparing → green **Listening** | Speak only when Listening is green |
| 5 | You ask your need | Speak clearly in Kannada |
| 6 | Bot answers or opens a form | Follow voice prompts |
| 7 | Confirm each field | Say **ಹೌದು** / **ಸರಿ** or **ಮತ್ತೆ ಹೇಳಿ** |
| 8 | End session | Say **ಮುಗಿಸು** or tap **End** |

On-screen help: **ಹೇಗೆ ಮಾತನಾಡುವುದು · How to speak** (same tips as [WHAT_TO_SPEAK.md](./WHAT_TO_SPEAK.md)).

**Tips**

- Tap the screen once if audio does not play (browser unlock).
- Speak **after** the bot finishes speaking (avoid echo).
- Wait for the mic indicator before speaking.
- During forms, absence auto-end is paused until the form completes.

---

## 4. What to speak — voice intents (7 types)

These are recognized by the AI pipeline when you speak in **Kannada**:

| Intent | Say this (Kannada) | English meaning | What bot does |
|--------|-------------------|-----------------|---------------|
| **Balance** | `ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟಿದೆ` | What is my account balance? | Opens balance form → asks account number |
| **Open account** | `ಹೊಸ ಖಾತೆ ತೆರೆಯಬೇಕು` | I want to open a new account | Opens account opening form |
| **Loan** | `ಸಾಲಕ್ಕೆ ಅರ್ಜಿ ಸಲ್ಲಿಸಬೇಕು` | I want to apply for a loan | Opens loan application form |
| **Deposit** | `ನಗದು ಠೇವಣಿ ಮಾಡಬೇಕು` | I want to deposit money | Opens deposit slip form |
| **Withdraw** | `ಹಣ ಹಿಂಪಡೆಯಬೇಕು` | I want to withdraw money | Opens withdrawal slip form |
| **Interest rates** | `ಬಡ್ಡಿ ದರ ಎಷ್ಟು` | What are the interest rates? | Speaks current rates (informational) |
| **Account info** | `ಖಾತೆ ಮಾಹಿತಿ ಬೇಕು` | I need account information | Speaks general procedures (informational) |

**Alternative phrases (also work well)**

- Balance: `ಬ್ಯಾಲೆನ್ಸ್ ತಿಳಿಸಿ`, `ಖಾತೆಯಲ್ಲಿ ಎಷ್ಟು ಹಣ ಇದೆ`
- Loan: `ಲೋನ್ ಬೇಕು`, `ಸಾಲ ಅರ್ಜಿ`
- Open account: `ಖಾತೆ ತೆರೆಯಲು ಬಯಸುತ್ತೇನೆ`

---

## 5. Balance inquiry — full demo script

Best demo path (~1–2 minutes):

1. Admin → **Start counter**
2. Customer steps into camera → hears greeting
3. Customer says:

   ```
   ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟಿದೆ
   ```

4. Bot asks for account number. Customer says **all 10 digits** clearly:

   ```
   one two three four five six seven eight nine zero
   ```

   Or Kannada digits one-by-one (include final **ಸೊನ್ನೆ** / zero).

5. Bot confirms. Customer says:

   ```
   ಹೌದು
   ```

6. Bot speaks balance in Kannada, e.g. ₹**45,230.50** for account `1234567890`.

### Demo accounts (only these work — 10 digits)

| Account number | Name | Balance (₹) | Type |
|----------------|------|-------------|------|
| `1234567890` | Ramesh Kumar | 45,230.50 | Savings |
| `9876543210` | Anita Rao | 12,500.00 | Savings |
| `1111222233` | Suresh Gowda | 89,340.75 | Current |
| `2222333344` | Lakshmi Devi | 67,890.25 | Savings |
| `5555666677` | Prakash Shetty | 15,250.00 | Savings |
| `8888999900` | Meena Patil | 2,40,075.50 | Current |

Any other number → “account not found” message in Kannada. Full speak guide: [WHAT_TO_SPEAK.md](./WHAT_TO_SPEAK.md).

---

## 6. Form filling — confirm commands

During any form field:

| You want | Say (Kannada) | Say (English) |
|----------|---------------|---------------|
| Confirm value | `ಸರಿ`, `ಹೌದು` | yes, ok, correct |
| Re-record | `ಮತ್ತೆ ಹೇಳಿ`, `ತಪ್ಪು` | again, wrong, no |
| Skip optional field | `ಬಿಟ್ಟುಬಿಡಿ` | skip, none |
| End session | `ಮುಗಿಸು`, `ನಿಲ್ಲಿಸು` | stop, end, goodbye |

After all fields → form preview → **Print / Save PDF** on screen.

---

## 7. Informational queries (no form)

### Interest rates

Say:

```
ಬಡ್ಡಿ ದರ ಎಷ್ಟು
```

Bot reads savings, FD, home loan, personal loan rates.

### General account help

Say:

```
ATM ಕಾರ್ಡ್ ಬ್ಲಾಕ್ ಮಾಡಬೇಕು
```

or

```
ಖಾತೆ ಮಾಹಿತಿ ಬೇಕು
```

Bot gives general procedure text (demo — not real banking).

---

## 8. Troubleshooting during demo

| Problem | Fix |
|---------|-----|
| No voice / robotic browser voice | Restart API; wait 60s; check smoke test |
| “Service offline” on agent | Start API on port 8000 |
| Mic not working | Allow microphone; tap screen once |
| Bot opens wrong form | Speak clearly; reduce background noise |
| Confirm loop on `ಸರಿ` | Speak louder; say `ಹೌದು` or `yes` |
| Slow first response | Normal (~10–20s cold); faster after first turn |
| Phone cannot connect | Same Wi‑Fi; use `https://` not `http://` |

---

## 9. End-to-end test checklist

- [ ] API smoke test — ALL PASS
- [ ] Admin login works
- [ ] Start counter → agent shows waiting
- [ ] Camera detects presence → greeting plays
- [ ] Balance query → account → confirm → Kannada balance spoken
- [ ] Say `ಮುಗಿಸು` → session ends
- [ ] Admin can stop counter

---

## 10. Quick reference — URLs & credentials

| Item | Value |
|------|--------|
| API | `http://127.0.0.1:8000` |
| Agent (lobby) | `https://localhost:5173` |
| Admin | `https://localhost:5174` |
| Admin user | `admin` |
| Admin password | `bank@123` |
| Demo account | `1234567890` |

---

## 11. Git push (Sarastra Labs org)

Repo: `https://github.com/sarastralabs/bank_assistant.git`

```powershell
# Switch GitHub CLI to Sarastra Labs account
gh auth switch -u sarastralabs
gh auth status

cd c:\Sarastra\voice-based-assistant

# Do NOT commit .env (secrets)
git add -A
git reset HEAD .env

git status
git commit -m "Production fixes: smooth voice flow, balance inquiry, TTS stability"
git push origin main
```

If push asks for credentials, `gh auth switch` should route HTTPS git through the Sarastra Labs token.

---

## 12. Verify on another PC (deployment troubleshooting)

Your PC works but another machine does not — **compare checks side by side**.

### On BOTH machines (working + problem PC)

**1. API must be running first**, then:

```powershell
cd c:\Sarastra\voice-based-assistant
py -3.12 scripts/deployment_check.py --full > deploy-check.txt
```

Open `deploy-check.txt` and compare. Every `[FAIL]` on the bad PC is a clue.

**2. Full automated suite:**

```powershell
cd c:\Sarastra\voice-based-assistant\frontend\scripts
.\deployment_verify.ps1 -Full
```

**3. Quick smoke only:**

```powershell
py -3.12 scripts/production_smoke_test.py
```

### Most common differences between machines

| Symptom on other PC | Cause | Fix |
|---------------------|--------|-----|
| `speak-kannada 500` | Old API code or missing `import os` | Pull latest git; restart API |
| `STT failed` / CUDA OOM | Missing models or 2 APIs on GPU | Copy `models/` folder; one API only |
| `models/... missing` | Large files not in git | Copy `models/` from working PC OR run convert + train |
| Agent "offline" | API not on `0.0.0.0:8000` | `--host 0.0.0.0 --port 8000` |
| Phone cannot open URL | Firewall | Allow 5173, 5174, 8000 private |
| Robotic / no voice | TTS 500 | `BANK_TTS_ENGINE=mms` in `.env`; restart API |
| Wrong intent | Old code or no NLU model | Copy `models/nlu-distilbert/` |

### Copy from working PC to deployment PC

These are **not fully in git** (too large):

```
models/whisper-medium-vaani-ct2/
models/nlu-distilbert/
```

Zip and copy, or regenerate on the new machine (see README).

### Checklist before demo on any machine

- [ ] `deployment_check.py --full` → ALL PASS
- [ ] `production_smoke_test.py` → ALL PASS  
- [ ] Only **one** API on port 8000
- [ ] Admin login works
- [ ] Phone opens `https://<wifi-ip>:5173`

---

## 13. Fresh install on a new PC (`setup.bat`)

```powershell
cd c:\Sarastra\voice-based-assistant
setup.bat
```

The setup wizard will:

1. Create `.venv` and install all Python + npm libraries  
2. **Open HuggingFace links** in your browser (optional)  
3. Ask you to accept **2 licenses** and **paste your token** (`hf_...`)  
4. Download all ML models automatically  
5. Run verification  

### HuggingFace steps (setup asks you interactively)

| Step | What to do |
|------|------------|
| A | Log in at https://huggingface.co/login |
| B | Accept license: indictrans2-indic-en-dist-200M |
| C | Accept license: indictrans2-en-indic-dist-200M |
| D | Create Read token at https://huggingface.co/settings/tokens |
| E | Paste token in setup when prompted → downloads start |

| Command | When |
|---------|------|
| `setup.bat` | First time on new PC |
| `setup.bat --fresh` | Broken venv — delete and reinstall |
| `setup.bat --skip-models` | Libs only; copy `models/` from working PC |

After setup, run the 3 terminals from section 1.

---

## 14. Student access — 3 deployment modes

All three work without students using your company domain.

### Mode A — Same Wi‑Fi + IP (college lab, fastest)

Students open on the **same network** as the demo PC:

```
https://192.168.x.x:5173   (agent)
https://192.168.x.x:5174   (admin)
```

- No ngrok, no domain
- Accept browser certificate warning once
- Firewall: allow ports **5173, 5174, 8000** on Private network
- **Note:** Some college Wi‑Fi blocks phone→laptop (client isolation) — use Mode B if that happens

### Mode B — ngrok (students on any network)

Tunnel the frontend only (API proxied through Vite):

```powershell
ngrok http https://localhost:5173
```

Share the ngrok URL, e.g. `https://abc123.ngrok-free.app`

- No domain needed
- CORS allows `*.ngrok-free.app` and `*.ngrok.io` automatically
- Mic/camera work (real HTTPS)

Optional — remote TTS box via ngrok:

```env
BANK_TTS_REMOTE_URL=https://xyz.ngrok-free.app
```

### Mode C — Cloudflare tunnel + domain (production)

Use Sarastra subdomains: **`tts.sarastralabs.com`** (TTS GPU), **`agent.sarastralabs.com`** (customer UI), **`admin.sarastralabs.com`** (staff UI).

**Full step-by-step:** [CLOUDFLARE_TUNNEL.md](./CLOUDFLARE_TUNNEL.md)

```env
BANK_TTS_REMOTE_URL=https://tts.sarastralabs.com
BANK_TTS_REMOTE_KEY=your-shared-secret
BANK_CORS_ORIGINS=https://agent.sarastralabs.com,https://admin.sarastralabs.com
```

### Split GPU architecture (recommended for speed)

| Machine | Role | Command |
|---------|------|---------|
| **Kiosk PC** | STT + NLU + API + frontend | `uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| **TTS GPU PC** | Parler Suresh only | `.\scripts\run_tts_server.ps1` |

Kiosk `.env`:

```env
BANK_TTS_REMOTE_URL=https://tts.sarastralabs.com
BANK_TTS_REMOTE_KEY=shared-secret
BANK_TTS_ENGINE=auto
```

See [CLOUDFLARE_TUNNEL.md](./CLOUDFLARE_TUNNEL.md) for tunnel setup on the TTS GPU machine.

Check health (includes TTS status):

```powershell
curl http://127.0.0.1:8000/api/health
```

---
