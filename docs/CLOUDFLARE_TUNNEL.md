# Cloudflare Tunnel — Kannada Voice Banking

Expose the voice banking stack on [Sarastra Labs](https://www.sarastralabs.com/) subdomains without opening router ports.

| Hostname | Machine | Local service |
|----------|---------|---------------|
| `tts.sarastralabs.com` | **8 GB GPU (TTS box)** | Parler TTS API → `127.0.0.1:8001` |
| `agent.sarastralabs.com` | **Kiosk PC** (optional) | Agent UI → `https://127.0.0.1:5173` |
| `admin.sarastralabs.com` | **Kiosk PC** (optional) | Admin UI → `https://127.0.0.1:5174` |

For a **college lab on same Wi‑Fi**, students use kiosk IP — TTS can still use `tts.sarastralabs.com` or LAN (see §2.2).

---

## 8 GB TTS machine — run these commands

Use this checklist on the **GPU box where Parler runs only**.

### One-time setup (first deploy)

```powershell
cd <repo-root>   # git clone https://github.com/sarastralabs/bank_assistant.git
powershell -ExecutionPolicy Bypass -File .\scripts\setup_tts_box.ps1
# Edit .env — set BANK_TTS_REMOTE_KEY (same as kiosk)
# Accept HF license: https://huggingface.co/ai4bharat/indic-parler-tts

# Cloudflare (once)
cloudflared tunnel login
cloudflared tunnel create bank-tts
cloudflared tunnel route dns bank-tts tts.sarastralabs.com
```

Create `%USERPROFILE%\.cloudflared\config-tts.yml`:

```yaml
tunnel: bank-tts
credentials-file: C:\Users\<YOU>\.cloudflared\<TUNNEL-UUID>.json

ingress:
  - hostname: tts.sarastralabs.com
    service: http://127.0.0.1:8001
  - service: http_status:404
```

### Every time you start the TTS box (2 terminals)

**Terminal 1 — Parler TTS server**

```powershell
cd <repo-root>
powershell -ExecutionPolicy Bypass -File .\scripts\run_tts_server.ps1
```

Wait until you see: `[tts-server] Ready — speaker=… phrases=… elapsed=…s`

**Full guide:** [docs/DEPLOYMENT.md](./DEPLOYMENT.md)

**Terminal 2 — Cloudflare tunnel**

```powershell
cloudflared tunnel --config %USERPROFILE%\.cloudflared\config-tts.yml run bank-tts
```

### Verify TTS box is healthy

```powershell
# Local
curl http://127.0.0.1:8001/api/health

# Public (after tunnel is running)
curl https://tts.sarastralabs.com/api/health
```

Expected: `"status": "ready"`, `"ready": true`, `"service": "tts"`, `"parler": true`

---

## TTS box `.env` (copy from `.env.tts.example`)

```env
BANK_TTS_ENGINE=parler
BANK_TTS_SPEAKER=Suresh
BANK_PIPELINE_WORKER=0
BANK_TTS_ALLOW_MMS=0
TRANSFORMERS_OFFLINE=1
HF_HUB_OFFLINE=1
HF_DATASETS_OFFLINE=1
BANK_TTS_REMOTE_KEY=<same-secret-as-kiosk>
```

**Important:** `BANK_TTS_REMOTE_KEY` must be **identical** on kiosk and TTS box.

---

## Kiosk PC `.env` (already set in repo root `.env`)

```env
BANK_TTS_ENGINE=auto
BANK_TTS_REMOTE_URL=https://tts.sarastralabs.com
BANK_TTS_REMOTE_KEY=<same-secret-as-kiosk>
BANK_TTS_REMOTE_TIMEOUT=90
BANK_TTS_REMOTE_RETRIES=2
BANK_PIPELINE_KEEP_LOADED=1
BANK_PIPELINE_WORKER=1
```

After TTS box + tunnel are up, restart kiosk API:

```powershell
cd <repo-root>
py -3.12 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Verify kiosk sees remote TTS:

```powershell
curl http://127.0.0.1:8000/api/health
```

Look for: `"tts": { "remote": { "healthy": true, "ready": true, "url": "https://tts.sarastralabs.com" } }`

---

## Prerequisites

1. Domain **sarastralabs.com** on Cloudflare (DNS managed by Cloudflare).
2. [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) on TTS box (and kiosk if using `agent.sarastralabs.com`).
3. HF access accepted for `ai4bharat/indic-parler-tts` on TTS box.

---

## Part 1 — TTS tunnel details (`tts.sarastralabs.com`)

### DNS route (one-time)

```powershell
cloudflared tunnel route dns bank-tts tts.sarastralabs.com
```

Creates CNAME `tts.sarastralabs.com` → `<tunnel-id>.cfargotunnel.com`.

---

## Part 2 — Kiosk PC (main API + frontend)

STT, translation, NLU run here. TTS calls go to `https://tts.sarastralabs.com`.

### Start kiosk (3 terminals)

**Start TTS box first** (see §8 GB TTS machine). Then on kiosk:

```powershell
# Terminal 1 — API (waits for remote TTS ready)
cd <repo-root>
powershell -ExecutionPolicy Bypass -File .\scripts\start-kiosk-api.ps1

# Terminal 2 — Frontend
cd <repo-root>\frontend
.\scripts\dev-all.ps1
```

Students on same Wi‑Fi: `https://<kiosk-ip>:5173`

### Same-LAN TTS (faster, skip Cloudflare for TTS)

If both PCs are on the same network, set on **kiosk** `.env`:

```env
BANK_TTS_REMOTE_URL=http://192.168.x.x:8001
```

TTS box still runs `run_tts_server.ps1` — Cloudflare optional.

---

## Part 3 — Public agent + admin UI (`agent` / `admin.sarastralabs.com`)

When students are **not** on the same Wi‑Fi, expose both Vite dev servers through one tunnel.

**Important:** `cloudflared tunnel login` must use the Cloudflare account that owns **sarastralabs.com** (same account as `tts.sarastralabs.com`). If DNS routes land under `*.aaptor.com`, you are logged into the wrong account.

### Fix “existing certificate” login error

If login says it would overwrite `cert.pem`, back up the old account cert first:

```powershell
Move-Item $env:USERPROFILE\.cloudflared\cert.pem $env:USERPROFILE\.cloudflared\cert-aaptor.pem.bak
cloudflared tunnel login
```

Select **sarastralabs.com** in the browser. Your aaptor.com tunnels keep working with the backed-up cert if needed.

### One-time setup

If `route dns` fails with **Tunnel not found** right after create, wait 10 seconds and use the **UUID** instead of the name:

```powershell
cloudflared tunnel route dns 52aa5e01-4810-47b0-8ab3-90df7e7be61e agent.sarastralabs.com
cloudflared tunnel route dns 52aa5e01-4810-47b0-8ab3-90df7e7be61e admin.sarastralabs.com
```

Replace the UUID with yours from `cloudflared tunnel list`.

Copy [deploy/cloudflare/config-kiosk.yml.example](../deploy/cloudflare/config-kiosk.yml.example) to `%USERPROFILE%\.cloudflared\config-kiosk.yml` and set `credentials-file` to your tunnel JSON.

**Manual DNS (Cloudflare dashboard → sarastralabs.com → DNS):** if `route dns` fails, add CNAME records:

| Name | Target |
|------|--------|
| `agent` | `<TUNNEL-UUID>.cfargotunnel.com` |
| `admin` | `<TUNNEL-UUID>.cfargotunnel.com` |

### Start tunnel (kiosk PC, terminal 3)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-kiosk-tunnel.ps1
```

Or:

```powershell
cloudflared tunnel --config %USERPROFILE%\.cloudflared\config-kiosk.yml run bank-kiosk
```

`%USERPROFILE%\.cloudflared\config-kiosk.yml`:

```yaml
tunnel: bank-kiosk
credentials-file: C:\Users\<YOU>\.cloudflared\<TUNNEL-UUID>.json

ingress:
  - hostname: agent.sarastralabs.com
    service: https://127.0.0.1:5173
    originRequest:
      noTLSVerify: true
  - hostname: admin.sarastralabs.com
    service: https://127.0.0.1:5174
    originRequest:
      noTLSVerify: true
  - service: http_status:404
```

CORS: `*.sarastralabs.com` is already allowed in `api/cors_config.py`. Optional explicit list:

```env
BANK_CORS_ORIGINS=https://agent.sarastralabs.com,https://admin.sarastralabs.com
```

Frontend (admin “open lobby” link): copy [frontend/.env.cloudflare.example](../frontend/.env.cloudflare.example) to `frontend/.env.local`.

---

## Part 4 — Run tunnel as Windows service (optional)

```powershell
cloudflared service install
cloudflared --config %USERPROFILE%\.cloudflared\config-tts.yml tunnel run bank-tts
```

[Cloudflare Windows service docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/configure-tunnels/local-management/as-a-service/windows/)

---

## Quick reference

| Machine | Terminal 1 | Terminal 2 | Terminal 3 |
|---------|------------|------------|------------|
| **8 GB TTS** | `run_tts_server.ps1` | `cloudflared … config-tts.yml` | — |
| **Kiosk** | `start-kiosk-api.ps1` | `dev-all.ps1` | `run-kiosk-tunnel.ps1` (optional) |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `502` on `tts.sarastralabs.com` | Run `run_tts_server.ps1` first on `:8001` |
| `401` on speak-kannada | `BANK_TTS_REMOTE_KEY` mismatch — sync `.env` and `.env.tts.example` |
| `remote.healthy: false` | Tunnel not running or wrong `BANK_TTS_REMOTE_URL` |
| Parler not ready | Run `setup_parler_venv.ps1`; accept HF license |
| Slow replies | Use LAN URL for TTS if both PCs on same Wi‑Fi |

---

## Security

- Rotate `BANK_TTS_REMOTE_KEY` before production — never commit real keys.
- `tts.sarastralabs.com` is server-to-server only (kiosk → TTS).
- Change admin password before exposing `admin.sarastralabs.com`.

---

## Related files

| File | Purpose |
|------|---------|
| [docs/DEPLOYMENT.md](./DEPLOYMENT.md) | **Main deployment guide** — terminals, env profiles, health |
| [.env.kiosk.example](../.env.kiosk.example) | Kiosk PC config |
| [.env.local-pc.example](../.env.local-pc.example) | Single-PC config |
| [.env.tts.example](../.env.tts.example) | Copy to `.env` on 8 GB TTS box |
| [deploy/cloudflare/](../deploy/cloudflare/) | Tunnel YAML templates |
| [scripts/run_tts_server.ps1](../scripts/run_tts_server.ps1) | Start Parler API on `:8001` |
| [scripts/start-kiosk-api.ps1](../scripts/start-kiosk-api.ps1) | Start main API on `:8000` |
| [DEMO_AND_INTERACTION_GUIDE.md](./DEMO_AND_INTERACTION_GUIDE.md) | Demo flow |
