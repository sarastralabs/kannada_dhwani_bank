# Voice Form UX Plan — Read-back, Animations & Responsive Layout

**Status:** Mostly implemented (agent lobby + admin) — see §17 checklist  
**Last updated:** 2026-09-02  
**Scope:** Agent lobby (`HandsFreeConversation`) — voice-only banking forms, no on-screen number pad

---

## 1. Executive summary

Customers interact **only by voice** (Kannada). The screen is a **visual companion**: it shows what was understood, what the agent is doing, and a readable summary before print — never a typing surface.

This plan combines:

1. **Form read-back** — after filling, Suresh (Parler) speaks a full Kannada summary of captured fields (today only balance inquiry does this).
2. **Live UI feedback** — animations and data cards while listening, processing, speaking, and confirming.
3. **Responsive layout** — one design system that fits **laptop/kiosk** (primary) and **phone** (demo / staff testing) without debug clutter.

**Recommended build order:** read-back backend → speak + summary panel → live context cards → digit-slot animations → whole-form confirm.

---

## 2. Problem statement (today)

| Form | After last field | Screen |
|------|------------------|--------|
| **Balance inquiry** | Speaks full result (*ಖಾತೆ ಸಂಖ್ಯೆ… ಲಭ್ಯ ಬಾಕಿ…*) | Hint text only |
| **All other forms** | Generic *ಅರ್ಜಿ ಸಿದ್ಧ. ಪ್ರಿಂಟ್ ಮಾಡಬಹುದು…* only | Print preview; no voice recap of name/account/amount |
| **During fill** | Field prompts spoken | Small “Heard / Form value” debug-style block |
| **Processing** | Silent wait | “Processing” text + mascot thinking |

**Gaps:** no trust layer for numbers, no synced summary, UI feels like a dev panel on small screens, long forms give no progress sense.

---

## 3. Design principles

### Voice-first

- Microphone is the only input. No keypad, no keyboard, no tap-to-edit digits.
- Retry = speak again; reject = *ಇಲ್ಲ* / *ಮತ್ತೆ ಹೇಳಿ*.
- Screen **confirms** understanding; it does not **collect** input.

### Banking kiosk UX (research-backed)

| Principle | Application |
|-----------|-------------|
| **One focal task** | One big card: current question OR current summary line |
| **Large Kannada type** | Min 18px body, 24px+ for captured values; `Noto Sans Kannada` / `Anek Kannada` (already loaded) |
| **High contrast** | Dark lobby shell + light content cards (existing palette) |
| **Calm motion** | 250–400ms transitions; no flashy loops except mascot idle |
| **Privacy** | Mask account numbers on screen (`•••• •••• 7890`); speak full digits in audio only if needed |
| **Accessibility** | `aria-live="polite"` on status; respect `prefers-reduced-motion` |
| **No debug on customer UI** | Hide “English:”, raw STT, intent confidence — staff/admin only |

### References (patterns, not code)

- **ATM / branch kiosk:** step indicator + large prompt + confirmation screen before receipt.
- **Voice assistants (Alexa/Google):** subtitle line + listening animation; no form fields.
- **Mobile banking:** card-based summaries, not tables.

---

## 4. Target devices & breakpoints

### Primary — laptop / kiosk (landscape)

| Profile | Typical viewport | Role |
|---------|------------------|------|
| **Kiosk laptop** | 1366×768 – 1920×1080 | College lab counter, main demo |
| **Dev laptop** | 1280×800+ | Local testing |

**Layout:** horizontal split — mascot left (or top-center), context card right (or below mascot). Use full viewport height (`lobby-fit` already uses flex column).

### Secondary — phone (portrait)

| Profile | Typical viewport | Role |
|---------|------------------|------|
| **Staff phone** | 390×844 (iPhone), 360×800 (Android) | Same Wi‑Fi demo per `DEMO_AND_INTERACTION_GUIDE.md` |

**Layout:** single column stack — compact mascot → status strip → one scrollable context card. Mini camera corner (existing `lobby-camera-mini`). **No horizontal split** below 640px.

### Breakpoints (proposed)

| Token | Width | Layout |
|-------|-------|--------|
| `kiosk` | ≥ 1024px | Two-column: hero mascot + wide context panel |
| `tablet` | 768px – 1023px | Mascot centered above card; max content width 640px |
| `phone` | &lt; 768px | Full-width card; mascot `lobby-bot-compact`; hide secondary English hints on narrow |
| `short` | max-height 700px | Reduce mascot size 20%; tighten vertical gaps |

**Existing CSS:** `@media (max-width: 720px)` adjusts presence grid; `handsfree-panel` max-width 720px. New components should use `clamp()` and `min(92vw, 640px)` instead of fixed pixels.

### Safe areas

- Phone: `env(safe-area-inset-*)` on header and bottom status.
- Kiosk: keep **End** button ≥ 44×44px touch target top-right.

---

## 5. Information architecture (conversation phase)

```
┌─────────────────────────────────────────────────────────────────┐
│ Header: brand · phase chip · End                                 │
├──────────────────────────────┬──────────────────────────────────┤
│ ZONE A — Agent               │ ZONE B — Live context (NEW)        │
│ • LobbyBot / AgentMascot     │ • Pipeline progress (thinking)     │
│ • Mood: listen/think/speak   │ • Current field + digit slots    │
│ • EQ / rings animation       │ • Filled chips / summary lines     │
│ [mini camera]                │ • Subtitle (speaking)              │
├──────────────────────────────┴──────────────────────────────────┤
│ ZONE C — Status strip (simplified HandsFree status)              │
│ ಕೇಳುತ್ತಿದ್ದೇನೆ… · mic meter · single hint line                  │
└─────────────────────────────────────────────────────────────────┘
```

**Remove from customer view (move to admin/debug):**

- `Heard:` / `English:` dual lines
- `intent-badge` / `route-badge` in assist mode (optional small chip only)
- `handsfree-footer` technical text

---

## 6. State machine → UI mapping

Maps to existing `HandsFreeTurn` in `HandsFreeConversation.tsx` and `MascotMood` in `AgentLobby.tsx`.

| Turn | Mascot | Zone B content | Zone C (status) | Animation |
|------|--------|----------------|-----------------|-----------|
| `idle` | `ready` | Welcome hint | ಸಿದ್ಧ | Idle sway |
| `listening` | `listening` | Empty slots / “…” | ಕೇಳುತ್ತಿದ್ದೇನೆ… + mic meter | Rings + EQ bars |
| `thinking` | `thinking` | Pipeline steps (§7) | ಯೋಚಿಸುತ್ತಿದ್ದೇನೆ… | Antenna pulse, step glow |
| `speaking` | `speaking` | **Subtitle** (Kannada line) | ಉತ್ತರಿಸುತ್ತಿದ್ದೇನೆ… | Mouth open, wave glow |
| `form_prompt` | `speaking` | Field label + empty value | ಪ್ರಶ್ನೆ… | Prompt card slide-in |
| `form_confirm` | `listening` | **Large value card** (masked if digits) | ದೃಢೀಕರಿಸಿ… | Value pop-in |
| `form_preview` | `ready` | Summary list + print sheet | ಅರ್ಜಿ ಸಿದ್ಧ | Checkmark sweep |

---

## 7. Processing animation (“thinking”)

### General assist (`process-audio`)

Customer-facing pipeline strip (not technical labels):

```
[🎤 ಕೇಳಿದೆ] → [🧠 ಅರ್ಥಮಾಡಿಕೊಂಡೆ] → [💬 ಉತ್ತರ] → [🔊 ಹೇಳುತ್ತೇನೆ]
```

- Advance using `stage_times` from API when present (`stt`, `nlu_router`, `tts`).
- Fallback: timed progression so UI never freezes &gt; 3s on one step.
- Active step: soft gold border + subtle shimmer (reuse `--think` token).

### Form field fill (`fillFormFieldAudio`)

```
[🎤] → [🔢 ಸಂಖ್ಯೆ] or [📝 ಪಠ್ಯ] → [✓]
```

Pick icon by `field.type`: `digits` | `amount` | `text` | `date`.

---

## 8. Voice-only form capture (no keypad)

### Digit / account fields

1. Show **N empty slots** (e.g. 10 circles for account; variable for amount).
2. On STT result, fill slots left-to-right with `slot-pop` animation (scale 0→1, brief green flash).
3. Display **masked preview** under slots: `•••• •••• 7890`.
4. If length &lt; 8 for account: slots **pulse amber**; agent asks again.
5. **Confirm step:** large centered value; listen for ಸರಿ / ಇಲ್ಲ; shake on reject, check on accept.

### Amount fields

- Show `₹ ______` with digits filling as parsed.
- Subtitle amount in words when speaking (*ಐದು ಸಾವಿರ ರೂಪಾಯಿ*) — built in summary layer.

### Name fields

- Keep **skip voice confirm** (already implemented) — names loop on “ಸರಿ”.
- Show name chip in “Filled so far” row with checkmark.

### “Filled so far” row

Horizontal scroll chips on phone; wrapped row on laptop:

```
[✓ ಹೆಸರು: ರಾಮೇಶ್] [✓ ಖಾತೆ: ••7890] [○ ಮೊತ್ತ: —]
```

---

## 9. Form read-back summary (voice)

### Goal

When all fields are filled (non–balance-inquiry forms), Suresh speaks a **clear Kannada summary**, then optional whole-form confirm, then print preview.

**Balance inquiry:** unchanged — uses `fetchDemoBalance` → `message_kn`.

### Example (cash withdrawal)

> ನಿಮ್ಮ ಅರ್ಜಿ ಸಿದ್ಧ. ಖಾತೆದಾರರ ಹೆಸರು ರಾಮೇಶ್ ಕುಮಾರ್. ಖಾತೆ ಸಂಖ್ಯೆ ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು ಐದು ಆರು ಏಳು ಎಂಟು ಒಂಬತ್ತು ಸೊನ್ನೆ. ಹಿಂಪಡೆಯುವ ಮೊತ್ತ ಐದು ಸಾವಿರ ರೂಪಾಯಿ. ದಿನಾಂಕ ಇಂದು. ಪ್ರಿಂಟ್ ಮಾಡಬಹುದು.

### Step 1 — Backend: `backend/forms/summary_kn.py`

**Input:** form definition (`data/forms.json`) + `values: dict[str, str]`  
**Output:** `{ "summary_kn": str, "lines": [{ "field_id", "label_kn", "display_kn", "speak_kn" }] }`

| Field type | Display (screen) | Speak (TTS) |
|------------|------------------|-------------|
| `text` / name | As captured | As captured |
| `digits` / account | Masked `••••7890` | Digit-by-digit Kannada words |
| `amount` | `₹ 5,000.00` | Kannada amount words + ರೂಪಾಯಿ |
| `date` | `DD/MM/YYYY` | ಇಂದು or spoken date |
| empty optional | Omit | Omit |

**Helpers:**

- Reverse digit map from `backend/forms/kannada_digits.py` (digits → ಒಂದು, ಎರಡು, …).
- Amount words: share logic with `frontend/src/utils/kannadaNumbers.ts` or port to Python for one source of truth.

**API (recommended):**

```
POST /api/forms/{form_id}/summary
Body: { "values": { "account_number": "1234567890", ... } }
Response: { "summary_kn", "lines", "confirm_prompt_kn" }
```

Keeps TTS text consistent between speak and display.

### Step 2 — Frontend: speak summary

In `HandsFreeConversation.tsx`, when `fieldIndex >= fields.length` and form ≠ `balance_inquiry`:

```
1. POST summary API
2. setSummaryLines(lines)          // Zone B
3. await playKannada(summary_kn)   // remote Parler
4. (optional) whole-form confirm   // §10
5. setTurn("form_preview")
6. submitFormSubmission + continueAssist()
```

Replace generic-only `playKannada(FORM_READY_KN)` for recap; may still append short closing phrase from `FORM_READY_KN` if summary omits it.

### Step 3 — Screen + voice sync (Zone B)

While TTS plays:

- Show **summary card** with one line per field.
- **Highlight active line** (bold + left border); others dimmed 60% opacity.
- Phase 1: highlight all lines together (no karaoke).
- Phase 2 (optional): advance highlight on timer proportional to line length.

### Step 4 — TTS quality rules

| Type | Rule |
|------|------|
| Account | Always digit-by-digit Kannada for TTS |
| Amount | Natural Kannada (*ಮೂರು ಸಾವಿರ ರೂಪಾಯಿ*) |
| Long forms | Cap spoken summary at ~30s; prioritize required fields; say *ಇತರ ವಿವರಗಳು ಅರ್ಜಿಯಲ್ಲಿ ಇವೆ* for rest |

### Step 5 — Whole-form confirm (recommended)

After summary TTS:

1. Agent: *ಎಲ್ಲಾ ಸರಿಯೇ? ಹೌದು ಎಂದರೆ ಮುಗಿಸಿ, ಇಲ್ಲ ಎಂದರೆ ಮತ್ತೆ ಹೇಳಿ.* (`FORM_WHOLE_CONFIRM_KN` in `lobby_phrases.py`)
2. **ಹೌದು / ಸರಿ** → preview + submit
3. **ಇಲ್ಲ / ತಪ್ಪು** → ask which field, or restart from field index 0

Reuse `isAffirmCommand` / `isRejectCommand` from `voiceCommands.ts`.

---

## 10. End-to-end flow (target)

```
Last field confirmed
    ↓
Build Kannada summary (API)
    ↓
Show summary lines on screen
    ↓
Agent reads full summary (Parler / Suresh)
    ↓
"ಎಲ್ಲಾ ಸರಿಯೇ? ಹೌದು ಅಥವಾ ಇಲ್ಲ."
    ↓
ಹೌದು → form_preview → print → submit → "ಬೇರೆ ಸಹಾಯ?"
ಇಲ್ಲ  → re-ask field or restart form
```

**Balance path (unchanged):**

```
Account captured → fetchDemoBalance → speak message_kn → show balance card → continueAssist
```

---

## 11. Responsive wireframes

### Laptop / kiosk (≥ 1024px, landscape)

```
┌────────────────────────────────────────────────────────────┐
│ ಕನ್ನಡ ವಾಯ್ಸ್ ಬ್ಯಾಂಕಿಂಗ್          [ರಾತ್ರಿ]  [End]          │
├──────────────────┬─────────────────────────────────────────┤
│                  │  ┌─────────────────────────────────┐  │
│    [Mascot]      │  │ ಖಾತೆ ಸಂಖ್ಯೆ                      │  │
│    listening     │  │ ○ ○ ○ ○ ● ● ○ ○ ○ ○              │  │
│    + rings       │  │ •••• •••• 56__                   │  │
│                  │  └─────────────────────────────────┘  │
│                  │  Filled: [✓ ಹೆಸರು] [✓ ಖಾತೆ]          │
│                  │  ─────────────────────────────────   │
│                  │  Subtitle: ದಯವಿಟ್ಟು ಮೊತ್ತ ಹೇಳಿ...     │
├──────────────────┴─────────────────────────────────────────┤
│ ● ಕೇಳುತ್ತಿದ್ದೇನೆ…  ████████░░ mic                         │
└────────────────────────────────────────────────────────────┘
                                    [cam 112×84]
```

- Context card: `min(48vw, 520px)` wide, scroll if summary &gt; 4 lines.
- Mascot: existing `lobby-bot-convo` (~168px SVG).

### Phone (&lt; 768px, portrait)

```
┌─────────────────────┐
│ Brand        [End]  │
├─────────────────────┤
│      [Mascot]       │  compact, ~120px
│   ● ಕೇಳುತ್ತಿದ್ದೇನೆ  │
├─────────────────────┤
│ ┌─────────────────┐ │
│ │ Field card      │ │  92vw, max 400px
│ │ slots / summary │ │
│ └─────────────────┘ │
│ [✓ ಹೆಸರು][✓ ಖಾತೆ]  │  horizontal scroll chips
├─────────────────────┤
│ ████████░░ mic      │
└─────────────────────┘
              [cam]
```

- Single column; no side-by-side.
- Hide duplicate English status line; keep one Kannada + optional smaller EN.
- Form print preview: full-width sheet; print button sticky bottom.

### Short viewport (height &lt; 700px)

- Shrink mascot 20%.
- Collapse “Filled so far” to icon-only chips with tooltip.
- Pipeline strip: icons only, no labels.

---

## 12. Component plan (new / changed)

| Component | Responsibility |
|-----------|----------------|
| `LiveContextCard.tsx` | Zone B wrapper; switches by `turn` + `mode` |
| `PipelineProgress.tsx` | Thinking strip for assist + form fill |
| `FormDigitSlots.tsx` | Slot UI for `digits` / `amount` |
| `FormFilledChips.tsx` | Horizontal “filled so far” |
| `AgentSubtitle.tsx` | Speaking line with fade-in |
| `FormSummaryPanel.tsx` | Read-back lines + active highlight |
| `FormConfirmCard.tsx` | Large value for field confirm |

| File | Change |
|------|--------|
| `backend/forms/summary_kn.py` | **New** — summary builder |
| `backend/lobby_phrases.py` | Add `FORM_WHOLE_CONFIRM_KN` |
| `api/routes/forms.py` | `POST /forms/{id}/summary` |
| `frontend/src/utils/formSummary.ts` | Client types + API call |
| `HandsFreeConversation.tsx` | Wire turns, summary, confirm |
| `AgentLobby.tsx` | Pass layout class by breakpoint; optional context slot |
| `index.css` | Tokens, animations, responsive grids |
| `tests/test_form_summary.py` | Unit tests |

**No TTS box changes** — uses existing `/api/speak-kannada` → `tts.sarastralabs.com`.

---

## 13. Animation catalog (CSS)

| Name | Duration | When |
|------|----------|------|
| `slot-pop` | 280ms | Digit captured |
| `card-slide-in` | 320ms | New field / summary line |
| `value-shake` | 400ms | Confirm rejected |
| `check-draw` | 350ms | Confirm accepted |
| `pipeline-tick` | 600ms loop | Active processing step |
| `subtitle-fade` | 300ms | New agent line |
| `summary-line-active` | 200ms | Read-back highlight switch |
| `lobby-ring` | existing | Listening / speaking |

All respect `@media (prefers-reduced-motion: reduce) { animation: none }`.

---

## 14. Content & copy (Kannada)

| Key | Text |
|-----|------|
| `FORM_WHOLE_CONFIRM_KN` | ಎಲ್ಲಾ ಸರಿಯೇ? ಹೌದು ಎಂದರೆ ಮುಗಿಸಿ, ಇಲ್ಲ ಎಂದರೆ ಮತ್ತೆ ಹೇಳಿ. |
| Summary opener | ನಿಮ್ಮ ಅರ್ಜಿ ಸಿದ್ಧ. |
| Summary closer | ಪ್ರಿಂಟ್ ಮಾಡಬಹುದು. |
| Slot incomplete | ಖಾತೆ ಸಂಖ್ಯೆ ಸಂಪೂರ್ಣವಾಗಿಲ್ಲ — ಮತ್ತೆ ಹೇಳಿ. |
| Pipeline STT | ನಿಮ್ಮ ಮಾತು ಕೇಳಿದೆ |
| Pipeline NLU | ಅರ್ಥಮಾಡಿಕೊಂಡೆ |
| Pipeline TTS | ಉತ್ತರ ಹೇಳುತ್ತೇನೆ |

---

## 15. Demo test data

### Demo accounts (`data/demo_accounts.json`)

| Account | Holder | Balance |
|---------|--------|---------|
| 1234567890 | ರಾಮೇಶ್ ಕುಮಾರ್ | ₹45,230.50 |
| 9876543210 | ಅನಿತಾ ರಾವ್ | ₹12,500.00 |
| 1111222233 | ಸುರೇಶ್ ಗೌಡ | ₹89,340.75 |

### Kannada test phrases

**Start balance:** ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟು? / ಬಾಕಿ ತಿಳಿಸಿ  

**Account (digit-by-digit):** ಒಂದು ಎರಡು ಮೂರು ನಾಲ್ಕು ಐದು ಆರು ಏಳು ಎಂಟು ಒಂಬತ್ತು ಸೊನ್ನೆ  

**Withdraw:** ನಗದು ಹಿಂಪಡೆಯಬೇಕು  

**Confirm:** ಸರಿ / ಹೌದು · Reject: ಇಲ್ಲ / ಮತ್ತೆ ಹೇಳಿ  

---

## 16. Implementation phases & effort

| Phase | Deliverable | Estimate |
|-------|-------------|----------|
| **A** | `summary_kn.py` + API + tests | 0.5 day |
| **B** | Speak summary + `FormSummaryPanel` | 0.5 day |
| **C** | Whole-form confirm loop | 0.5 day |
| **D** | `LiveContextCard` + pipeline strip + subtitle | 1 day |
| **E** | Digit slots + filled chips + responsive CSS | 1 day |
| **F** | Polish, reduced motion, phone QA | 0.5 day |

**Total:** ~3.5–4 days for full plan; **A+B+D (summary + basic live UI)** ~1.5 days for first demo milestone.

---

## 17. Test checklist

- [ ] Balance inquiry still speaks `message_kn` only (no regression)
- [x] Balance inquiry speaks full result and shows on-screen balance card
- [x] Non-balance forms: voice summary + confirm before print
- [x] Cash withdrawal summary includes name, masked account, amount, date
- [x] Summary displays on laptop and phone without horizontal scroll overflow
- [x] Whole-form confirm: ಸರಿ → print; ಇಲ್ಲ → retry
- [ ] Long loan form summary under ~30s TTS or truncated with disclaimer
- [x] `prefers-reduced-motion` disables slot animations
- [x] No debug “English:” / raw STT line on customer-facing build
- [x] Account masked on screen; full digits only in audio if required
- [x] Print sheet includes form disclaimer text
- [x] Lobby loading state (no “closed” flash before status loads)
- [x] Admin form submissions viewer

---

## 18. Out of scope (explicit)

- On-screen number pad or keyboard entry
- Tap-to-edit individual digits
- Customer-facing intent confidence scores
- Separate mobile app — responsive web only

---

## 19. Related docs

- [DEMO_AND_INTERACTION_GUIDE.md](./DEMO_AND_INTERACTION_GUIDE.md) — startup & demo flow
- [DEPLOYMENT.md](./DEPLOYMENT.md) — kiosk + TTS split deploy
- `frontend/src/components/AgentMascot.tsx` — existing mood animations
- `frontend/src/components/HandsFreeConversation.tsx` — turn state machine

---

## 20. Decision log

| Decision | Rationale |
|----------|-----------|
| Voice-only, no keypad | User requirement; screen builds trust |
| Summary via backend API | One Kannada string for TTS + UI |
| Mask account on screen | Privacy at public kiosk |
| Laptop-first, phone-second | Primary demo is counter laptop; phone for Wi‑Fi testing |
| Phase summary highlight without karaoke v1 | Faster ship; timer sync later |

---

*Implementation tracked in §17. Remaining polish: pipeline stage_times, two-column kiosk layout, karaoke summary sync.*
