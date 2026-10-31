# Free deployment — Cloudflare Pages + a backend host

Two static frontends (kiosk and staff console) plus one API.

## 1. Frontends → Cloudflare Pages (free)

Create **two** Pages projects from the same GitHub repo. Root directory: `frontend`.

| Project | Build command | Output dir | Environment variables |
|---|---|---|---|
| kiosk | `npm run build:agent` | `dist` | `VITE_API_BASE` |
| admin | `npm run build:admin` | `dist-admin` | `VITE_API_BASE`, `VITE_AGENT_URL` |

`VITE_API_BASE` is the backend origin (see `frontend/.env.production.example`).
Pages cannot proxy `/api` to another host, so the browser calls the API directly and
the backend must allow the Pages origins (step 3).

## 2. Backend

* **Render (free):** New → Blueprint → pick this repo (`render.yaml`). Set the secrets
  marked `sync: false` in the dashboard. Free instances sleep after ~15 min idle (first
  request takes ~1 min) and have ~512 MB RAM.
* **Hugging Face Space (free CPU, ~16 GB RAM):** create a Docker Space, push this repo
  (the `Dockerfile` serves on `$PORT`; set the Space port to 8000 or `PORT=7860`).

### Models are not in git
`models/` is gitignored. Whisper CT2 weights come from `backend/stt/convert_models.py`;
the NLU model from `backend/nlu/train.py`; IndicTrans2 is **gated** on Hugging Face
(request access, then download with a token on a machine with internet).
On Render's 512 MB tier, local torch models will not fit — run Sarvam for STT,
translation and TTS in the admin console (Settings → Speech engines). The intent
model still needs torch, so use the Hugging Face Space route or swap NLU for the
keyword classifier before relying on Render.

## 3. Required environment variables

| Variable | Purpose |
|---|---|
| `BANK_ADMIN_PASS` | Staff console password (default `bank@123` is public — change it) |
| `BANK_CORS_ORIGINS` | Comma-separated Pages URLs, e.g. `https://dhwani-kiosk.pages.dev,https://dhwani-admin.pages.dev` |
| `SARVAM_API_KEY` | Cloud speech (optional) |
| `MONGODB_URI`, `MONGODB_DB_NAME` | Persistent storage; without it SQLite/JSONL files reset on every redeploy |

## 4. Check it works

* `GET <backend>/health` → `{"status":"ok"}`
* Open the admin console → Overview → **System health** shows each engine and the database.
* Browsers only allow the microphone over HTTPS (Pages provides it) or on `localhost`.
