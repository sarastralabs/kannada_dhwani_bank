import { getApiBase } from "../utils/apiBase";
import { FetchTimeoutError } from "../utils/abortError";
import { normalizeSpokenNumber } from "../utils/kannadaNumbers";
import { normalizeDepositMode, transliterateKannadaToEnglish } from "../utils/kannadaText";
import type { Greeting, GreetingCatalogSlot } from "../utils/greetings";

export interface PipelineResult {
  kannada_text: string;
  english_text: string;
  intent: string;
  confidence: number;
  route: string;
  response_text: string;
  response_text_kn?: string;
  required_fields?: string[];
  form_id?: string;
  form_menu?: FormMenuItem[];
  prefill?: Record<string, string>;
  clarify_candidates?: string[];
  audio_b64: string;
  stage_times: Record<string, number>;
  total_time_s: number;
  error: string | null;
  /** service_unavailable = a model or service is down; not_understood = the customer was not understood. */
  error_code?: "service_unavailable" | "not_understood";
  history_id?: number | string | null;
  kiosk_session_id?: string;
  tts_speaker?: "Suresh" | "Anu";
}

/** Dialog context so the backend knows what the customer is doing. */
export interface PipelineContext {
  mode?: "assist" | "form_select" | "form";
  form_id?: string;
  field_id?: string;
  last_intent?: string;
  last_route?: string;
  menu_form_ids?: string[];
  pending_intents?: string[];
  clarify_attempts?: number;
  last_kannada_text?: string;
  last_english_text?: string;
  kiosk_session_id?: string;
}

export interface FormMenuItem {
  index: number;
  id: string;
  title_kn: string;
  title_en: string;
  description_kn?: string;
}

export interface HistoryItem {
  id: number | string;
  created_at: string;
  kannada_text: string;
  english_text: string;
  intent: string;
  confidence: number;
  route: string;
  response_text: string;
  has_audio: boolean;
  total_time_s: number | null;
  stage_times: Record<string, number>;
  audio_b64?: string;
}

export interface LandingData {
  product: {
    name: string;
    tagline: string;
    language: string;
    mode: string;
  };
  stats: {
    supported_intents: number;
    history_queries: number;
    pipeline_stages: number;
    typical_latency_s: string;
  };
  intents: Array<{ id: string; label: string; example: string }>;
  interest_rates: Array<{ product: string; rate: string }>;
  pipeline: Array<{ step: number; name: string; detail: string }>;
  recent: Array<{
    id: number;
    intent: string;
    kannada_text: string;
    created_at: string;
  }>;
}

const API_BASE = getApiBase();
const DEFAULT_TIMEOUT_MS = 120_000;

function parseApiErrorBody(body: unknown, fallback: string): string {
  if (body == null || typeof body !== "object") return fallback;
  const rec = body as Record<string, unknown>;
  const detail = rec.detail ?? rec.error;
  if (typeof detail === "string") return detail;
  if (detail != null) return JSON.stringify(detail);
  return fallback;
}

async function parseApiError(res: Response, fallback: string): Promise<string> {
  try {
    const err = await res.json();
    return parseApiErrorBody(err, fallback);
  } catch {
    return fallback;
  }
}

async function fetchWithTimeout(
  url: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<Response> {
  const timeoutMs = init?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const { timeoutMs: _t, signal: outer, ...rest } = init ?? {};
  const ac = new AbortController();
  let timedOut = false;
  // timeoutMs <= 0 → wait until the server responds (no client abort)
  const timer =
    timeoutMs > 0
      ? window.setTimeout(() => {
          timedOut = true;
          ac.abort();
        }, timeoutMs)
      : null;
  const onAbort = () => ac.abort();
  outer?.addEventListener("abort", onAbort);
  try {
    return await fetch(url, { ...rest, signal: ac.signal });
  } catch (err) {
    if (timedOut && !outer?.aborted) {
      throw new FetchTimeoutError(timeoutMs);
    }
    throw err;
  } finally {
    if (timer !== null) window.clearTimeout(timer);
    outer?.removeEventListener("abort", onAbort);
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    // Live probe — must stay fast even while process-audio blocks worker threads.
    const res = await fetchWithTimeout(`${API_BASE}/api/health/live`, { timeoutMs: 5000 });
    if (!res.ok) return false;
    const data = await res.json();
    if (data.live === true || String(data.status ?? "").toLowerCase() === "ok") {
      return true;
    }
    // Fallback for older API builds without /health/live
    const full = await fetchWithTimeout(`${API_BASE}/api/health`, { timeoutMs: 8000 });
    if (!full.ok) return false;
    const detail = await full.json();
    const status = String(detail.status ?? "").toLowerCase();
    return status === "ok" || status === "warming" || status === "degraded";
  } catch {
    return false;
  }
}

export async function processAudio(
  audioBlob: Blob,
  filename = "recording.webm",
  context?: PipelineContext,
  options?: { includeAudio?: boolean; signal?: AbortSignal },
): Promise<PipelineResult> {
  const formData = new FormData();
  formData.append("audio", audioBlob, filename);
  if (context && Object.keys(context).length > 0) {
    formData.append("context", JSON.stringify(context));
  }
  if (context?.kiosk_session_id) {
    formData.append("kiosk_session_id", context.kiosk_session_id);
  }
  if (options?.includeAudio === false) {
    formData.append("include_audio", "false");
  }

  const res = await fetchWithTimeout(`${API_BASE}/api/process-audio`, {
    method: "POST",
    body: formData,
    timeoutMs: 0,          // no client timeout — wait until server responds
    signal: options?.signal,
  });

  if (!res.ok) {
    throw new Error(await parseApiError(res, `Request failed (${res.status})`));
  }

  return res.json();
}

export async function transcribeAudio(
  audioBlob: Blob,
  filename = "recording.webm",
): Promise<{ kannada_text: string; english_text: string; error: string | null }> {
  const formData = new FormData();
  formData.append("audio", audioBlob, filename);

  const res = await fetchWithTimeout(`${API_BASE}/api/transcribe-audio`, {
    method: "POST",
    body: formData,
    timeoutMs: 0,          // no client timeout — wait until server responds
  });

  if (!res.ok) {
    throw new Error(await parseApiError(res, `Transcribe failed (${res.status})`));
  }

  return res.json();
}

export async function fetchLanding(): Promise<LandingData> {
  const res = await fetchWithTimeout(`${API_BASE}/api/landing`, { timeoutMs: 15000 });
  if (!res.ok) throw new Error("Failed to load landing data");
  return res.json();
}

export async function fetchHistory(limit = 50): Promise<HistoryItem[]> {
  const res = await fetchWithTimeout(`${API_BASE}/api/history?limit=${limit}`, { timeoutMs: 15000 });
  if (!res.ok) throw new Error("Failed to load history");
  const data = await res.json();
  return data.items ?? [];
}

export async function fetchHistoryItem(id: number | string): Promise<HistoryItem> {
  const res = await fetchWithTimeout(`${API_BASE}/api/history/${id}`, { timeoutMs: 15000 });
  if (!res.ok) throw new Error("Failed to load history item");
  return res.json();
}

export async function deleteHistoryItem(id: number | string): Promise<void> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/history/${id}`, {
    method: "DELETE",
    headers: adminAuthHeaders(),
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error("Failed to delete history item");
}

/** Admin: delete every conversation and its recording. Returns how many were removed. */
export async function clearHistory(): Promise<number> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/history`, {
    method: "DELETE",
    headers: adminAuthHeaders(),
    timeoutMs: 30000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Could not clear conversations"));
  return Number((await res.json()).deleted ?? 0);
}

/** Admin: delete every saved form submission. Returns how many were removed. */
export async function clearFormSubmissions(): Promise<number> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/forms/submissions`, {
    method: "DELETE",
    headers: adminAuthHeaders(),
    timeoutMs: 30000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Could not clear form submissions"));
  return Number((await res.json()).deleted ?? 0);
}

export function base64ToAudioUrl(audioB64: string): string {
  const binary = atob(audioB64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: "audio/wav" });
  return URL.createObjectURL(blob);
}

export function formatHistoryTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export function formatIntentLabel(intent: string): string {
  return intent.replace(/_/g, " ");
}

export interface FormField {
  id: string;
  label_kn: string;
  label_en: string;
  prompt_kn: string;
  type: "text" | "digits" | "amount" | "date";
  required: boolean;
  /** If set, field is filled automatically and not asked by voice. */
  auto?: "today" | null;
}

export interface FormSummary {
  id: string;
  title_kn: string;
  title_en: string;
  description_kn: string;
  description_en: string;
  field_count: number;
}

export interface FormCatalog {
  disclaimer_kn: string;
  disclaimer_en: string;
  intent_map?: Record<string, string>;
  forms: FormSummary[];
}

export interface BankForm {
  id: string;
  title_kn: string;
  title_en: string;
  description_kn: string;
  description_en: string;
  fields: FormField[];
  disclaimer_kn: string;
  disclaimer_en: string;
}

export async function fetchFormCatalog(): Promise<FormCatalog> {
  const res = await fetchWithTimeout(`${API_BASE}/api/forms`, { timeoutMs: 15000 });
  if (!res.ok) throw new Error("Failed to load forms");
  return res.json();
}

export async function fetchForm(formId: string): Promise<BankForm> {
  const res = await fetchWithTimeout(`${API_BASE}/api/forms/${encodeURIComponent(formId)}`, {
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error("Failed to load form");
  return res.json();
}

export async function submitFormSubmission(payload: {
  form_id: string;
  title_kn: string;
  title_en: string;
  values: Record<string, string>;
  kiosk_session_id?: string;
}): Promise<{
  ok: boolean;
  submission: { id: string };
  /** Number the customer quotes later, e.g. DH-26-000123. */
  application_ref?: string;
  confirmation_kn?: string;
  confirmation_en?: string;
}> {
  const res = await fetchWithTimeout(`${API_BASE}/api/forms/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error("Failed to save form submission");
  return res.json();
}

export interface ApplicationStatusView {
  found: boolean;
  ref?: string;
  title_kn?: string;
  status?: string;
  status_kn?: string;
  account_number?: string;
  /** Sentence for the kiosk to read out. */
  message_kn: string;
}

/** A customer's own application: its number (spoken digits are fine) and the last 4 digits of their mobile. */
export async function fetchApplicationStatus(ref: string, mobileLast4: string): Promise<ApplicationStatusView> {
  const params = new URLSearchParams({ ref: ref.replace(/\s+/g, ""), mobile_last4: mobileLast4.replace(/\D/g, "") });
  const res = await fetchWithTimeout(`${API_BASE}/api/applications/status?${params}`, { timeoutMs: 15000 });
  if (res.status === 404) {
    return { found: false, message_kn: "ಈ ಅರ್ಜಿ ಸಂಖ್ಯೆ ಅಥವಾ ಮೊಬೈಲ್ ಅಂಕಿಗಳು ಹೊಂದಿಕೆಯಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ." };
  }
  if (res.status === 429) {
    return { found: false, message_kn: "ತುಂಬಾ ಪ್ರಯತ್ನಗಳಾಗಿವೆ. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಪ್ರಯತ್ನಿಸಿ." };
  }
  if (!res.ok) throw new Error("Could not check the application");
  return { found: true, ...(await res.json()) };
}

export async function resolveFormChoice(
  kannada_text: string,
  english_text: string,
  menuFormIds?: string[],
): Promise<{ matched: boolean; form_id: string | null; form?: BankForm }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/forms/resolve-choice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      kannada_text,
      english_text,
      menu_form_ids: menuFormIds ?? [],
    }),
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error("Form choice failed");
  return res.json();
}

export interface FormSubmissionItem {
  id: string;
  created_at: string;
  form_id: string;
  title_kn: string;
  title_en: string;
  values: Record<string, string>;
  kiosk_session_id?: string;
  status?: ApplicationStatus | string;
  /** Customer-facing application number, e.g. DH-26-000123. */
  ref?: string;
  decision?: ApplicationDecision | null;
}

export type ApplicationStatus = "submitted" | "approved" | "rejected" | "needs_info";

export interface ApplicationDecision {
  action: "approve" | "reject" | "needs_info";
  by: string;
  at: string;
  /** Message the customer sees. */
  note: string;
  result?: { account_number?: string; account_type?: string; existing_customer?: boolean; summary?: string };
}

/** Loan / fixed-deposit terms staff can set when approving; anything left out uses the default. */
export interface ApprovalTerms {
  amount?: number;
  annual_rate_pct?: number;
  tenure_months?: number;
}

export interface ApplicationPreview {
  ok: boolean;
  problems: string[];
  summary: string;
  details: { amount?: number; annual_rate_pct?: number; tenure_months?: number; emi_inr?: number; maturity_inr?: number } & Record<string, unknown>;
}

export async function previewApplication(id: string): Promise<ApplicationPreview> {
  return adminGetJson<ApplicationPreview>(`/api/admin/applications/${encodeURIComponent(id)}/preview`, "Could not check this application");
}

export async function decideApplication(
  id: string,
  action: ApplicationDecision["action"],
  note = "",
  terms?: ApprovalTerms,
): Promise<FormSubmissionItem> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/applications/${encodeURIComponent(id)}/decision`, {
    method: "POST",
    headers: { ...adminAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ action, note, terms }),
    timeoutMs: 20000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Could not save the decision"));
  return res.json();
}

export async function fetchFormSubmissions(limit = 50): Promise<FormSubmissionItem[]> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/forms/submissions?limit=${limit}`, {
    headers: adminAuthHeaders(),
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error("Failed to load form submissions");
  const data = await res.json();
  return data.items ?? [];
}

export async function fetchDemoBalance(accountNumber: string): Promise<{
  found: boolean;
  account_number: string;
  balance_inr?: number;
  holder_name?: string;
  holder_name_kn?: string;
  message_kn: string;
  message_en: string;
}> {
  const acct = accountNumber.replace(/\D/g, "");
  if (!acct) {
    return {
      found: false,
      account_number: "",
      message_kn: "ದಯವಿಟ್ಟು ಸರಿಯಾದ ಖಾತೆ ಸಂಖ್ಯೆಯನ್ನು ಹೇಳಿ.",
      message_en: "Please provide a valid account number.",
    };
  }
  const res = await fetchWithTimeout(`${API_BASE}/api/balance/${encodeURIComponent(acct)}`, {
    timeoutMs: 30_000,
  });
  if (!res.ok) throw new Error("Balance lookup failed");
  return res.json();
}

export async function fetchFormPromptAudio(formId: string): Promise<Record<string, string>> {
  const cacheKey = `prompt-audio:${formId}`;
  try {
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      const parsed = JSON.parse(cached) as Record<string, string>;
      if (parsed && typeof parsed === "object") return parsed;
    }
  } catch {
    // ignore bad cache
  }

  const res = await fetchWithTimeout(
    `${API_BASE}/api/forms/${encodeURIComponent(formId)}/prompt-audio`,
    { timeoutMs: 0 },     // no client timeout — model loading can take time
  );
  if (!res.ok) throw new Error("Failed to load form prompt audio");
  const data = await res.json();
  if (Array.isArray(data.errors) && data.errors.length > 0) {
    console.warn("[forms] prompt-audio partial failures:", data.errors);
  }
  const audio = (data.audio as Record<string, string>) ?? {};
  try {
    sessionStorage.setItem(cacheKey, JSON.stringify(audio));
  } catch {
    // quota — non-fatal
  }
  return audio;
}

const speakInFlight = new Map<string, Promise<string>>();

function speakCacheKey(text: string, speaker?: string): string {
  return `${speaker ?? ""}\0${text}`;
}

export async function fetchSpeakKannada(
  text: string,
  signal?: AbortSignal,
  speaker?: string,
): Promise<string> {
  const key = speakCacheKey(text, speaker);
  const existing = speakInFlight.get(key);
  if (existing) return existing;

  const request = (async () => {
    const res = await fetchWithTimeout(`${API_BASE}/api/speak-kannada`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, speaker: speaker || undefined }),
      timeoutMs: 0,        // no client timeout — wait for TTS to finish
      signal,
    });
    if (!res.ok) {
      throw new Error(await parseApiError(res, `TTS failed (${res.status})`));
    }
    const data = await res.json();
    return (data.audio_b64 as string) ?? "";
  })();
  if (signal) return request;
  speakInFlight.set(key, request);
  try {
    return await request;
  } finally {
    if (speakInFlight.get(key) === request) {
      speakInFlight.delete(key);
    }
  }
}

export interface VoiceOption {
  id: string;
  label_en: string;
  label_kn: string;
  description_en: string;
  description_kn: string;
}

export async function fetchVoiceSettings(): Promise<{
  speaker: string;
  options: VoiceOption[];
}> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/settings/voice`, {
    headers: adminAuthHeaders(),
    timeoutMs: 10000,
  });
  if (!res.ok) throw new Error("Could not load voice settings");
  return res.json();
}

export async function updateVoiceSpeaker(speaker: string): Promise<string> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/settings/voice`, {
    method: "PUT",
    headers: { ...adminAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ speaker }),
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Could not update voice"));
  const data = await res.json();
  return data.speaker as string;
}

export async function transcribeFormAudio(
  audioBlob: Blob,
  filename = "field.webm",
): Promise<string> {
  const formData = new FormData();
  formData.append("audio", audioBlob, filename);

  const res = await fetchWithTimeout(`${API_BASE}/api/forms/transcribe`, {
    method: "POST",
    body: formData,
    timeoutMs: 0,          // no client timeout
  });

  if (!res.ok) {
    throw new Error(await parseApiError(res, `Transcription failed (${res.status})`));
  }

  const data = await res.json();
  return (data.text ?? "").trim();
}

export interface FormFillResult {
  kannada_text: string;
  english_text: string;
  value: string;
  /** Names / addresses: what was heard, in Kannada — used to read the answer back. */
  spoken_kn?: string;
  error?: string | null;
  validation_error?: string | null;
}

/**
 * Speak Kannada → local STT + IndicTrans2 Kn→En + typed extract → English form value.
 */
export async function fillFormFieldAudio(
  audioBlob: Blob,
  fieldType: FormField["type"],
  fieldId: string,
  filename = "field.webm",
): Promise<FormFillResult> {
  let lastError: Error | null = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    const formData = new FormData();
    formData.append("audio", audioBlob, filename);
    formData.append("field_type", fieldType);
    formData.append("field_id", fieldId);

    try {
      const res = await fetchWithTimeout(`${API_BASE}/api/forms/fill-field`, {
        method: "POST",
        body: formData,
        timeoutMs: 0,      // no client timeout — wait until server responds
      });

      if (!res.ok) {
        const msg = await parseApiError(res, `Form fill failed (${res.status})`);
        const retryable = res.status >= 500 && attempt === 0;
        if (retryable) {
          lastError = new Error(msg);
          await new Promise((r) => window.setTimeout(r, 400));
          continue;
        }
        throw new Error(msg);
      }

      const data = await res.json();
      return {
        kannada_text: (data.kannada_text ?? "").trim(),
        english_text: (data.english_text ?? "").trim(),
        value: (data.value ?? "").trim(),
        spoken_kn: (data.spoken_kn ?? "").trim(),
        error: data.error ?? null,
        validation_error: data.validation_error ?? null,
      };
    } catch (err) {
      if (attempt === 0 && err instanceof Error && !err.message.includes("422")) {
        lastError = err;
        await new Promise((r) => window.setTimeout(r, 400));
        continue;
      }
      throw err;
    }
  }
  throw lastError ?? new Error("Form fill failed");
}

/**
 * Clean / convert STT text for a form field into English-form values.
 * Prefer fillFormFieldAudio (IndicTrans2) for voice; this is a client-side fallback.
 */
export function normalizeFormValue(
  raw: string,
  type: FormField["type"],
  fieldId?: string,
): string {
  const text = raw.trim();
  if (!text) return "";

  if (type === "digits" || type === "amount" || type === "date") {
    return normalizeSpokenNumber(text, type);
  }

  if (fieldId === "deposit_mode") {
    return normalizeDepositMode(text);
  }

  if (fieldId === "full_name" || type === "text") {
    return transliterateKannadaToEnglish(text);
  }

  return text;
}

// ── Kiosk / Admin agent control ─────────────────────────────────────────────

export interface KioskSession {
  id: string;
  started_at: string;
  ended_at: string | null;
  phase: string;
  note: string;
}

export interface KioskStatusLite {
  running: boolean;
  phase: string;
  started_at: string | null;
  stopped_at: string | null;
  current_session_id: string | null;
  person_present: boolean;
  last_event: string;
  updated_at: string;
  demo_mode: boolean;
}

export interface KioskStatus extends KioskStatusLite {
  sessions: KioskSession[];
}

async function kioskPost(
  path: string,
  body?: unknown,
  opts?: { admin?: boolean },
): Promise<KioskStatus> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (opts?.admin) {
    const { adminAuthHeaders } = await import("../auth/adminSession");
    Object.assign(headers, adminAuthHeaders());
  }
  const res = await fetchWithTimeout(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    timeoutMs: 15000,
  });
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Request failed (${res.status})`));
  }
  return res.json();
}

export async function fetchKioskStatusLite(): Promise<KioskStatusLite> {
  const res = await fetchWithTimeout(`${API_BASE}/api/kiosk/status/lite`, { timeoutMs: 8000 });
  if (!res.ok) throw new Error("Failed to load lobby status");
  return res.json();
}

export async function fetchKioskStatus(): Promise<KioskStatus> {
  const res = await fetchWithTimeout(`${API_BASE}/api/kiosk/status`, { timeoutMs: 10000 });
  if (!res.ok) throw new Error("Failed to load lobby status");
  return res.json();
}

export async function startKiosk(): Promise<KioskStatus> {
  return kioskPost("/api/kiosk/start", undefined, { admin: true });
}

export async function stopKiosk(): Promise<KioskStatus> {
  return kioskPost("/api/kiosk/stop", undefined, { admin: true });
}

export async function reportKioskPresence(present: boolean): Promise<KioskStatus> {
  return kioskPost("/api/kiosk/presence", { present });
}

export async function beginKioskSession(): Promise<KioskStatus> {
  return kioskPost("/api/kiosk/session/begin");
}

export async function setKioskPhase(
  phase: "idle" | "greeting" | "conversation",
): Promise<KioskStatus> {
  return kioskPost("/api/kiosk/session/phase", { phase });
}

export async function endKioskSession(note = ""): Promise<KioskStatus> {
  return kioskPost("/api/kiosk/session/end", { note });
}

export async function endKioskSessionAsAdmin(note = "Ended by admin"): Promise<KioskStatus> {
  return kioskPost("/api/kiosk/session/end-admin", { note }, { admin: true });
}

/** Time-based Kannada lobby greeting — random full sentence; prefer cached MMS. */
export async function fetchKioskGreetAudio(opts?: {
  slot?: string;
  hour?: number;
  variant?: number;
  random?: boolean;
  generate?: boolean;
}): Promise<{
  audio_b64: string;
  cached: boolean;
  slot: string;
  variant: number;
  title_kn: string;
  line_kn: string;
  line_en: string;
  title_en: string;
}> {
  const params = new URLSearchParams();
  if (opts?.slot) params.set("slot", opts.slot);
  if (opts?.hour !== undefined) params.set("hour", String(opts.hour));
  if (opts?.variant !== undefined) params.set("variant", String(opts.variant));
  if (opts?.random === false) params.set("random", "false");
  else params.set("random", "true");
  if (opts?.generate) params.set("generate", "true");
  const qs = params.toString();
  const res = await fetchWithTimeout(`${API_BASE}/api/kiosk/greet-audio${qs ? `?${qs}` : ""}`, {
    timeoutMs: 30000,
  });
  if (!res.ok) {
    let detail = "Greeting audio failed";
    try {
      const err = await res.json();
      detail = err.detail ?? detail;
    } catch {
      // keep
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const data = await res.json();
  return {
    audio_b64: (data.audio_b64 ?? "") as string,
    cached: Boolean(data.cached),
    slot: (data.slot ?? "") as string,
    variant: Number(data.variant ?? 0),
    title_kn: (data.title_kn ?? "") as string,
    title_en: (data.title_en ?? "") as string,
    line_kn: (data.line_kn ?? "") as string,
    line_en: (data.line_en ?? "") as string,
  };
}

export async function fetchGreetingCatalog(hour?: number): Promise<{
  current: Greeting;
  greetings: GreetingCatalogSlot[];
}> {
  const h = hour ?? new Date().getHours();
  const res = await fetchWithTimeout(`${API_BASE}/api/kiosk/greetings?hour=${h}&random=true`, {
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error("Failed to load greeting catalog");
  return res.json();
}

export interface AdminLoginResult {
  token: string;
  username: string;
  role: string;
  demo_mode: boolean;
}

export async function adminLogin(username: string, password: string): Promise<AdminLoginResult> {
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
    timeoutMs: 15000,
  });
  if (!res.ok) {
    throw new Error(await parseApiError(res, "Login failed"));
  }
  return res.json();
}

export async function adminLogout(): Promise<void> {
  const { adminAuthHeaders, clearAdminSession } = await import("../auth/adminSession");
  try {
    await fetchWithTimeout(`${API_BASE}/api/admin/logout`, {
      method: "POST",
      headers: adminAuthHeaders(),
      timeoutMs: 10000,
    });
  } finally {
    clearAdminSession();
  }
}

export async function fetchAdminMe(): Promise<{ username: string; role: string } | null> {
  const { adminAuthHeaders, clearAdminSession } = await import("../auth/adminSession");
  const headers = adminAuthHeaders();
  if (!headers.Authorization) return null;
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/me`, { headers, timeoutMs: 10000 });
  if (!res.ok) {
    clearAdminSession();
    return null;
  }
  return res.json();
}

export interface AdminCustomerRow {
  customer_id: string | null;
  holder_name: string;
  holder_name_kn: string;
  mobile?: string | null;
  customer_status: string;
  account_number: string;
  account_type: string;
  account_status: string;
  balance_inr: number;
  balance_updated_at?: string | null;
  source: string;
  loans: Array<{
    id: string;
    loan_type: string;
    principal_inr: number;
    outstanding_inr: number;
    status: string;
  }>;
}

export interface AdminBalanceAuditRow {
  id: number;
  account_number: string;
  customer_id?: string | null;
  found: number;
  source: string;
  kiosk_session_id?: string;
  created_at: string;
}

export async function fetchAdminCustomers(): Promise<{
  store: string;
  customers: AdminCustomerRow[];
  balance_audit: AdminBalanceAuditRow[];
}> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/customers`, {
    headers: adminAuthHeaders(),
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load customers"));
  return res.json();
}

export interface ConversationFlowIntent {
  intent: string;
  route: string;
  form_id?: string | null;
  form_title_en?: string;
  form_title_kn?: string;
  required_entities: string[];
  example_phrases: string[];
  fields: Array<{
    id: string;
    label_kn: string;
    label_en: string;
    prompt_kn: string;
    type: string;
    required: boolean;
  }>;
  next_step: string;
}

export interface ConversationFlowData {
  phases: Array<{ id: string; title: string; detail: string }>;
  intents: ConversationFlowIntent[];
  voice_commands: Record<string, string[]>;
  form_menu: Array<{ index: number; id: string; title_kn: string; title_en: string }>;
  intent_map: Record<string, string>;
  notes: string[];
}

export async function fetchAdminConversationFlow(): Promise<ConversationFlowData> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/conversation-flow`, {
    headers: adminAuthHeaders(),
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load conversation flow"));
  return res.json();
}

export type CloudStage = "stt" | "translation" | "tts";
export type CloudProvider = "local" | "sarvam";

export interface CloudStageStatus {
  provider: CloudProvider;
  ok: boolean | null;
  at: string | null;
  ms: number | null;
  error_kind: string | null;
  error: string | null;
  /** Sarvam is selected but the local model is answering (no key, credits, or outage). */
  using_local_now: boolean;
}

export interface CloudSettings {
  provider_name: string;
  stages: Record<CloudStage, CloudStageStatus>;
  sarvam_voice: string;
  voices: string[];
  fallback_local: boolean;
  key_set: boolean;
  key_hint: string;
  key_source: "settings" | "env" | "none";
  /** Open-source voice server answering — Speaking can only be switched to it then. */
  open_source_voice_online?: boolean;
}

export interface CloudSettingsUpdate {
  stt?: CloudProvider;
  translation?: CloudProvider;
  tts?: CloudProvider;
  sarvam_voice?: string;
  fallback_local?: boolean;
  /** "" removes the saved key. */
  sarvam_api_key?: string;
}

export interface CloudTestResult {
  ok: boolean;
  kind: string | null;
  message: string;
  translation?: string;
  audio_b64?: string;
}

export async function fetchCloudSettings(): Promise<CloudSettings> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/settings/cloud`, {
    headers: adminAuthHeaders(),
    timeoutMs: 10000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Could not load speech engine settings"));
  return res.json();
}

export async function updateCloudSettings(changes: CloudSettingsUpdate): Promise<CloudSettings> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/settings/cloud`, {
    method: "PUT",
    headers: { ...adminAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(changes),
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Could not save speech engine settings"));
  return res.json();
}

/** Translate + speak one phrase with Sarvam. Pass a key to test it before saving. */
export async function testCloudKey(body: { sarvam_api_key?: string; sarvam_voice?: string } = {}): Promise<CloudTestResult> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/settings/cloud/test`, {
    method: "POST",
    headers: { ...adminAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
    timeoutMs: 60000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Key test failed"));
  return res.json();
}

export interface SystemHealth {
  status: string;
  pipeline_worker?: boolean;
  tts?: {
    available?: boolean;
    ready?: boolean;
    speaker?: string;
    engine_env?: string;
    remote?: {
      configured?: boolean;
      url?: string;
      healthy?: boolean;
      ready?: boolean;
      warmup?: { phrases_cached?: number; elapsed_s?: number; error?: string | null } | null;
    };
  };
}

/** Full health (pipeline + TTS box) for the staff dashboard. */
export async function fetchSystemHealth(): Promise<SystemHealth> {
  const res = await fetchWithTimeout(`${API_BASE}/api/health`, { timeoutMs: 12000 });
  if (!res.ok) throw new Error(`Health check failed (${res.status})`);
  return res.json();
}

export async function fetchAdminHistory(limit = 50): Promise<HistoryItem[]> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/history?limit=${limit}`, {
    headers: adminAuthHeaders(),
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load speech history"));
  const data = await res.json();
  return data.items ?? [];
}

export async function fetchAdminHistoryItem(id: number | string): Promise<HistoryItem> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/history/${id}`, {
    headers: adminAuthHeaders(),
    timeoutMs: 20000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load history item"));
  return res.json();
}

// ── Staff insights ────────────────────────────────────────────────────────

export interface SystemStatus {
  pipeline_ready: boolean;
  stages: Record<string, { provider: string; using_local_now: boolean; last_ok: boolean | null; last_error: string | null }>;
  database: { kind: "mongodb" | "sqlite"; ok: boolean };
  cloud_key_set: boolean;
  default_admin_password: boolean;
  limits: { enabled: boolean; daily_used: number; daily_cap: number; per_min: number; blocked_recent: number };
  recent: {
    window_s: number;
    requests: number;
    service_failures: number;
    last_error: { at: number; message: string } | null;
    healthy: boolean;
  };
}

export interface UsageStats {
  days: { date: string; count: number }[];
  intents: { intent: string; count: number }[];
  avg_response_s: number | null;
  sample_size: number;
}

async function adminGetJson<T>(path: string, fallback: string): Promise<T> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}${path}`, { headers: adminAuthHeaders(), timeoutMs: 15000 });
  if (!res.ok) throw new Error(await parseApiError(res, fallback));
  return res.json();
}

export const fetchSystemStatus = () => adminGetJson<SystemStatus>("/api/admin/system", "Failed to load system status");
export const fetchUsageStats = (days = 14) => adminGetJson<UsageStats>(`/api/admin/stats?days=${days}`, "Failed to load stats");

/** Download an admin CSV (needs the auth header, so it cannot be a plain link). */
export async function downloadAdminCsv(kind: "history" | "submissions" | "transactions"): Promise<void> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/export/${kind}.csv`, {
    headers: adminAuthHeaders(),
    timeoutMs: 30000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Export failed"));
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = { history: "conversations.csv", submissions: "form-submissions.csv", transactions: "transactions.csv" }[kind];
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ── Customers, loans and the returning-customer view ─────────────────────

export interface CustomerDetail {
  customer: { id: string; full_name: string; full_name_kn?: string; mobile?: string | null; status: string; created_at: string };
  accounts: { account_number: string; account_type: string; balance_inr: number; status: string }[];
  loans: {
    id: string;
    loan_type: string;
    principal_inr: number;
    outstanding_inr: number;
    annual_rate_pct?: number;
    tenure_months?: number;
    emi_inr?: number;
    status: string;
  }[];
  deposits: { id: string; principal_inr: number; maturity_inr: number; matures_on: string; annual_rate_pct: number; tenure_months: number; status: string }[];
  transactions: { id: string; account_number: string; kind: string; amount: number; balance_after: number; at: string; ref?: string; counterparty?: string }[];
  applications: { ref: string; title_en: string; title_kn: string; status: string; created_at: string }[];
}

export const fetchCustomerDetail = (id: string) =>
  adminGetJson<CustomerDetail>(`/api/admin/customers/${encodeURIComponent(id)}`, "Could not load this customer");

export async function recordLoanRepayment(loanId: string, amount: number): Promise<{ outstanding_after: number; closed: boolean }> {
  const { adminAuthHeaders } = await import("../auth/adminSession");
  const res = await fetchWithTimeout(`${API_BASE}/api/admin/loans/${encodeURIComponent(loanId)}/repayment`, {
    method: "POST",
    headers: { ...adminAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ amount }),
    timeoutMs: 15000,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Could not record the payment"));
  return res.json();
}

export interface CustomerSummaryView {
  found: boolean;
  name?: string;
  accounts?: { last4: string; account_type: string; balance_inr: number }[];
  loans?: { loan_type: string; outstanding_inr: number; emi_inr?: number }[];
  deposits?: { principal_inr: number; maturity_inr: number; matures_on: string }[];
  transactions?: { kind: string; amount: number; balance_after: number; at: string; last4: string }[];
  applications?: { ref: string; title_kn: string; status: string; status_kn: string }[];
  /** Sentence for the kiosk to read out. */
  message_kn: string;
}

/** A returning customer: last 4 digits of an account AND of their registered mobile. */
export async function fetchCustomerSummary(accountLast4: string, mobileLast4: string): Promise<CustomerSummaryView> {
  const params = new URLSearchParams({ account_last4: accountLast4.replace(/\D/g, ""), mobile_last4: mobileLast4.replace(/\D/g, "") });
  const res = await fetchWithTimeout(`${API_BASE}/api/customer/summary?${params}`, { timeoutMs: 15000 });
  if (res.status === 404) {
    return { found: false, message_kn: "ಈ ಅಂಕಿಗಳಿಗೆ ಹೊಂದುವ ಖಾತೆ ಸಿಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ." };
  }
  if (res.status === 429) {
    return { found: false, message_kn: "ತುಂಬಾ ಪ್ರಯತ್ನಗಳಾಗಿವೆ. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಪ್ರಯತ್ನಿಸಿ." };
  }
  if (!res.ok) throw new Error("Could not load your details");
  return { found: true, ...(await res.json()) };
}
