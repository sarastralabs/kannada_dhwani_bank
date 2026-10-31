# Backend on Render (free) — cloud-only

Speech, translation and voice come from **Sarvam AI**; intents use the built-in
keyword classifier. No torch and no model files, so the image runs in ~70 MB of RAM
(tested in Docker with a 512 MB limit).

## 1. Create the service
Render → **New** → **Blueprint** → pick `sarastralabs/kannada_dhwani_bank`.
It reads `render.yaml` (Dockerfile.cloud, free plan, health check `/health`).

## 2. Enter the secrets (Render asks for the `sync: false` ones)
| Variable | Value |
|---|---|
| `BANK_ADMIN_PASS` | a strong staff-console password |
| `SARVAM_API_KEY` | your Sarvam key |
| `MONGODB_URI` | Atlas string, password URL-encoded (`@` → `%40`) |

Everything else (`BANK_CLOUD_PROVIDER=sarvam`, `BANK_NLU_ENGINE=keyword`, CORS for
`dhwani.sarastralabs.com` / `admin-dhwani.sarastralabs.com`, …) is already in `render.yaml`.

## 3. Atlas network access
Atlas → Security → Network Access → allow `0.0.0.0/0` (Render's IPs change).
Use a strong database password.

## 4. Connect the frontends
Copy the service URL (`https://dhwani-api.onrender.com`). In both Cloudflare apps set the
build variable `VITE_API_BASE` to it (no trailing slash), then **Retry deployment**.

## 5. Check
* `GET <url>/health` → `{"status":"ok"}`
* Admin console → Overview → **System health**: Listening / Understanding / Speaking show
  *Sarvam AI*, database shows *MongoDB*.

## Things to know
* The free plan sleeps after ~15 min idle; the first request then takes about a minute.
  Wake it before a demo, or ping `/health` with a free uptime monitor.
* There is no local fallback on this host: if Sarvam credits run out, customers hear
  "please try again" and System health shows the cause.
* Intent accuracy is keyword-based (Kannada + English keywords). For DistilBERT use the full
  `Dockerfile` on a host with ≥2 GB RAM and upload `models/nlu-distilbert`.
* The staff console's "Speech engines" toggles save to a file that is wiped on every Render
  restart; the env defaults above are what persist.
