import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  fetchDemoBalance,
  fetchForm,
  fetchKioskGreetAudio,
  fetchSpeakKannada,
  fillFormFieldAudio,
  normalizeFormValue,
  processAudio,
  submitFormSubmission,
  type BankForm,
  type PipelineContext,
  type PipelineResult,
  type FormField,
  type FormFillResult,
} from "../api/client";
import {
  BalanceResultCard,
  LiveValueCard,
  type BalanceResultView,
} from "./LiveContextPanel";
import { SpeakGuideCard } from "./SpeakGuideCard";
import { useVadRecorder, type VadListenOptions } from "../hooks/useVadRecorder";
import { isAbortError, userFacingFetchError } from "../utils/abortError";
import { isEcho } from "../utils/echo";
import { playBase64Wav, speakKannada, unlockAudio } from "../utils/playAudio";
import { ANYTHING_ELSE_KN, ASK_NEED_KN, FORM_CONFIRM_SUFFIX_KN } from "../utils/lobbyPhrases";
import { amountSpeakKn, kannadaDisplayValue } from "../utils/formSummary";
import {
  isAffirmCommand,
  isEndSessionCommand,
  isRejectCommand,
  isSkipCommand,
} from "../utils/voiceCommands";

export type HandsFreeTurn =
  | "idle"
  | "listening"
  | "thinking"
  | "preparing"
  | "speaking"
  | "form_prompt"
  | "form_confirm";

/** Time-of-day greeting spoken as the first line of the conversation. */
export interface ConversationGreeting {
  line_kn: string;
  slot?: string;
  variant?: number;
}

interface HandsFreeConversationProps {
  active: boolean;
  apiOnline: boolean | null;
  /** Spoken first instead of "ನಿಮಗೆ ಏನು ಸಹಾಯ ಬೇಕು?" (it already asks that). */
  greeting?: ConversationGreeting | null;
  /** Robot, shown at the top of the details side. */
  presence?: ReactNode;
  kioskSessionId?: string | null;
  onRequestEnd: (reason: string) => void;
  onTurnChange?: (turn: HandsFreeTurn) => void;
  onFormModeChange?: (inForm: boolean) => void;
  /** Short mascot reaction: a form was saved, or the customer wasn't heard. */
  onOutcome?: (outcome: "happy" | "confused") => void;
}

type Mode = "assist" | "form";

interface FormSession {
  form: BankForm;
  fieldIndex: number;
  values: Record<string, string>;
  /** What the customer sees for each field, in Kannada letters. */
  shown: Record<string, string>;
  promptAudio: Record<string, string>;
  skipFirstFieldPrompt?: boolean;
}

function todayDateString(): string {
  return new Date().toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function autoFilledValues(form: BankForm): Record<string, string> {
  const values: Record<string, string> = {};
  for (const field of form.fields) {
    if (field.auto === "today" || (field.type === "date" && field.id === "date")) {
      values[field.id] = todayDateString();
    }
  }
  return values;
}

function askableFields(form: BankForm) {
  return form.fields.filter((f) => !f.auto && !(f.type === "date" && f.id === "date"));
}

type StatusTone = "listen" | "wait" | "think" | "speak" | "done";

interface StatusView {
  tone: StatusTone;
  kn: string;
}

/**
 * One status for the customer — whose turn it is. Mic state wins over turn so
 * "Listening" never shows alongside "Talking…" / "Got it".
 */
function statusView(turn: HandsFreeTurn, vadState: string): StatusView {
  if (vadState === "processing_local") {
    return { tone: "think", kn: "ಕೇಳಿದೆ ✓" };
  }
  if (turn === "listening" && vadState === "speech") {
    return { tone: "listen", kn: "ಕೇಳುತ್ತಿದ್ದೇನೆ…" };
  }
  switch (turn) {
    case "listening":
      return { tone: "listen", kn: "ಈಗ ಮಾತನಾಡಿ" };
    case "thinking":
      return { tone: "think", kn: "ಯೋಚಿಸುತ್ತಿದ್ದೇನೆ…" };
    case "speaking":
    case "form_prompt":
    case "form_confirm":
      return { tone: "speak", kn: "ಕೇಳಿರಿ…" };
    case "preparing":
    default:
      return { tone: "wait", kn: "ಸ್ವಲ್ಪ ಕಾಯಿರಿ…" };
  }
}

/** Hints that only repeat what the status line or the card already say. */
const REDUNDANT_HINT =
  /^(?:ಕೇಳಿರಿ…|ಧ್ವನಿ ಸಿದ್ಧಪಡಿಸಲಾಗುತ್ತಿದೆ…|ಈಗ ಮಾತನಾಡಿ|ಮೈಕ್ರೊಫೋನ್ ಸಿದ್ಧವಾಗುತ್ತಿದೆ…)$|^ಅರ್ಜಿ:|^ನಿಮಗೆ ಏನು ಸಹಾಯ ಬೇಕು/;

/** Shown for any failure the customer cannot fix — the real error goes to the console. */
const TRY_AGAIN_KN = "ಸಮಸ್ಯೆ ಆಯಿತು. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ.";

function customerError(where: string, err: unknown): string {
  console.warn(`[hands-free] ${where}:`, err);
  return TRY_AGAIN_KN;
}

const TRY_SAYING_KN = ["ಖಾತೆ ಬ್ಯಾಲೆನ್ಸ್", "ಹೊಸ ಖಾತೆ ತೆರೆಯಬೇಕು", "ಸಾಲ ಬೇಕು", "ಬಡ್ಡಿ ದರ ಎಷ್ಟು?"];

/** Let React paint subtitle / status before starting TTS or mic work. */
function waitForUiPaint(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve());
    });
  });
}

const NAME_FIELD_IDS = new Set([
  "full_name",
  "name",
  "applicant_name",
  "beneficiary_name",
  "remitter_name",
  "nominee_name",
]);

/** Said when a request is not understood — asking again is enough. */
const SERVICE_DOWN_KN = "ಸೇವೆ ತಾತ್ಕಾಲಿಕವಾಗಿ ಲಭ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ಸಿಬ್ಬಂದಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ.";
const SAY_AGAIN_KN = "ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ";
/** "I want a form" without saying which — ask once more, with an example. */
const WHICH_FORM_KN = "ಯಾವ ಅರ್ಜಿ ಬೇಕು ಎಂದು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ. ಉದಾಹರಣೆಗೆ, ಹೊಸ ಖಾತೆ ಅಥವಾ ಸಾಲ.";

/** A form that was just sent — stays on the details side until the next form opens. */
interface SubmittedForm {
  form: BankForm;
  values: Record<string, string>;
  shown: Record<string, string>;
  saved: boolean;
}

function formListenOpts(field: FormField): VadListenOptions {
  if (NAME_FIELD_IDS.has(field.id) || field.type === "text") {
    return {
      silenceMs: 1300,
      minSpeechMs: 450,
      maxUtteranceMs: 22000,
      speechThreshold: 0.014,
    };
  }
  if (field.type === "digits" || field.type === "amount") {
    return { silenceMs: 1100, minSpeechMs: 400, maxUtteranceMs: 20000 };
  }
  return {};
}

/** Read-back attempts before the question is asked again. */
const MAX_CONFIRM_ROUNDS = 3;

const DIGIT_KN: Record<string, string> = {
  "0": "ಸೊನ್ನೆ",
  "1": "ಒಂದು",
  "2": "ಎರಡು",
  "3": "ಮೂರು",
  "4": "ನಾಲ್ಕು",
  "5": "ಐದು",
  "6": "ಆರು",
  "7": "ಏಳು",
  "8": "ಎಂಟು",
  "9": "ಒಂಬತ್ತು",
};

/**
 * What the assistant says when reading an answer back — always Kannada:
 * names/addresses in the customer's own Kannada (the backend's spoken_kn — not the
 * English-letter form value), digits as Kannada digit words (TTS misreads "1234567890"),
 * amounts as Kannada words, fixed choices ("Cash") in Kannada.
 */
function readBackText(filled: FormFillResult, field: FormField, value: string): string {
  if (filled.spoken_kn?.trim()) return filled.spoken_kn.trim();
  if (field.type === "digits" && /^\d+$/.test(value)) {
    return value
      .split("")
      .map((ch) => DIGIT_KN[ch] ?? ch)
      .join(" ");
  }
  if (field.type === "amount") return amountSpeakKn(value);
  if (field.type === "text") {
    const shown = kannadaDisplayValue(field.id, field.type, value, filled.kannada_text);
    if (shown !== "—") return shown;
  }
  return value;
}

function resolveFormFieldValue(filled: FormFillResult, field: FormField): string {
  // Names / addresses are kept as spoken — never fall back to the English translation.
  if (filled.spoken_kn?.trim()) {
    return (filled.value || normalizeFormValue(filled.spoken_kn, "text", field.id)).trim();
  }
  let value =
    filled.value ||
    filled.english_text ||
    normalizeFormValue(filled.kannada_text, field.type, field.id);
  if (!value?.trim() && field.type === "digits") {
    value = normalizeFormValue(filled.kannada_text, "digits", field.id);
  }
  if (!value?.trim() && NAME_FIELD_IDS.has(field.id)) {
    value =
      normalizeFormValue(filled.kannada_text, "text", field.id) || filled.kannada_text.trim();
  }
  return value?.trim() ?? "";
}

export function HandsFreeConversation({
  active,
  apiOnline,
  greeting = null,
  presence = null,
  kioskSessionId = null,
  onRequestEnd,
  onTurnChange,
  onFormModeChange,
  onOutcome,
}: HandsFreeConversationProps) {
  const { state: vadState, error: vadError, micLevel, listenOnce, abort, releaseMic, warmupMic } =
    useVadRecorder();

  const [turn, setTurn] = useState<HandsFreeTurn>("idle");
  const [mode, setMode] = useState<Mode>("assist");
  const [lastResult, setLastResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  /** The answer being checked, as the customer sees it (Kannada letters for text). */
  const [draftKn, setDraftKn] = useState("");
  const [formSession, setFormSession] = useState<FormSession | null>(null);
  const [subtitle, setSubtitle] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<SubmittedForm | null>(null);
  const [balanceResult, setBalanceResult] = useState<BalanceResultView | null>(null);
  const [submitWarning, setSubmitWarning] = useState<string | null>(null);
  /** Last thing STT heard from the customer — shown so they can catch mishearings. */
  const [heardRaw, setHeard] = useState<string | null>(null);
  // Whisper sometimes stops mid-character and returns U+FFFD — don't show "�" to customers.
  const heard = heardRaw?.replace(/�/g, "").trim() || null;

  const onEndRef = useRef(onRequestEnd);
  onEndRef.current = onRequestEnd;
  const onTurnRef = useRef(onTurnChange);
  onTurnRef.current = onTurnChange;
  const onFormModeRef = useRef(onFormModeChange);
  onFormModeRef.current = onFormModeChange;
  const onOutcomeRef = useRef(onOutcome);
  onOutcomeRef.current = onOutcome;
  const playAbortRef = useRef<AbortController | null>(null);
  /** Lines the assistant spoke recently, for the echo guard. */
  const spokenRef = useRef<{ text: string; at: number }[]>([]);
  const rememberSpoken = (text?: string | null) => {
    if (!text?.trim()) return;
    const now = Date.now();
    spokenRef.current = [...spokenRef.current.filter((l) => now - l.at < 90_000), { text, at: now }].slice(-4);
  };
  const listenOnceRef = useRef(listenOnce);
  listenOnceRef.current = listenOnce;
  const warmupMicRef = useRef(warmupMic);
  warmupMicRef.current = warmupMic;
  const apiOnlineRef = useRef(apiOnline);
  apiOnlineRef.current = apiOnline;
  // A ref, so a new greeting object never restarts the conversation loop.
  const greetingRef = useRef(greeting);
  greetingRef.current = greeting;
  const kioskSessionRef = useRef(kioskSessionId);
  kioskSessionRef.current = kioskSessionId;
  const dialogRef = useRef<{
    last_intent: string;
    last_route: string;
    pending_intents: string[];
    clarify_attempts: number;
    last_kannada_text: string;
    last_english_text: string;
  }>({
    last_intent: "",
    last_route: "",
    pending_intents: [],
    clarify_attempts: 0,
    last_kannada_text: "",
    last_english_text: "",
  });

  useEffect(() => {
    if (apiOnline === false && active) {
      abort();
      playAbortRef.current?.abort();
      window.speechSynthesis?.cancel();
    }
  }, [apiOnline, active, abort]);

  useEffect(() => {
    if (!active || apiOnlineRef.current === false) {
      abort();
      playAbortRef.current?.abort();
      window.speechSynthesis?.cancel();
      setTurn("idle");
      return;
    }

    let cancelled = false;
    let session: FormSession | null = null;

    const still = () => !cancelled && active;

    const run = async () => {
      for (let i = 0; i < 12 && still() && apiOnlineRef.current === null; i++) {
        await new Promise((r) => window.setTimeout(r, 250));
      }
      if (!still()) return;

      await unlockAudio();
      playAbortRef.current = new AbortController();
      setTurn("preparing");
      setHint("ಮೈಕ್ರೊಫೋನ್ ಸಿದ್ಧವಾಗುತ್ತಿದೆ…");
      const micOk = await warmupMicRef.current();
      // A cancelled run (session ended, StrictMode re-mount) stops quietly — only a
      // live run that really failed to get the mic shows the permission hint.
      if (!still()) return;
      if (!micOk) {
        setError("ಮೈಕ್ರೊಫೋನ್ ಬಳಸಲು ಅನುಮತಿ ನೀಡಿ");
        return;
      }

    let emptyListenCount = 0;

    const pipelineContext = (overrides: Partial<PipelineContext> = {}): PipelineContext => ({
      mode: "assist",
      last_intent: dialogRef.current.last_intent,
      last_route: dialogRef.current.last_route,
      pending_intents: dialogRef.current.pending_intents,
      clarify_attempts: dialogRef.current.clarify_attempts,
      last_kannada_text: dialogRef.current.last_kannada_text,
      last_english_text: dialogRef.current.last_english_text,
      kiosk_session_id: kioskSessionRef.current ?? undefined,
      ...overrides,
    });

    const rememberTurn = (result: PipelineResult) => {
      setHeard(result.kannada_text?.trim() || null);
      if (result.kannada_text) {
        dialogRef.current.last_kannada_text = result.kannada_text;
      }
      if (result.english_text) {
        dialogRef.current.last_english_text = result.english_text;
      }
      if (result.intent === "clarification") {
        dialogRef.current.last_intent = "clarification";
        dialogRef.current.pending_intents = result.clarify_candidates ?? [];
        dialogRef.current.clarify_attempts += 1;
      } else if (result.intent) {
        dialogRef.current.last_intent = result.intent;
        dialogRef.current.pending_intents = [];
        dialogRef.current.clarify_attempts = 0;
      }
      if (result.route) {
        dialogRef.current.last_route = result.route;
      }
    };

    const setSession = (next: FormSession | null) => {
      session = next;
      setFormSession(next);
      onFormModeRef.current?.(next !== null);
    };

    const playKannada = async (
      text: string,
      cachedB64?: string,
      speaker?: "Suresh" | "Anu",
    ) => {
      playAbortRef.current?.abort();
      const ac = new AbortController();
      playAbortRef.current = ac;
      try {
        if (cachedB64) {
          setTurn("speaking");
          await waitForUiPaint();
          await playBase64Wav(cachedB64, ac.signal);
          return;
        }
        setTurn("preparing");
        setHint("ಧ್ವನಿ ಸಿದ್ಧಪಡಿಸಲಾಗುತ್ತಿದೆ…");
        await waitForUiPaint();
        await speakKannada(
          text,
          ac.signal,
          apiOnlineRef.current,
          () => {
            setTurn("speaking");
            setHint("ಕೇಳಿರಿ…");
          },
          speaker,
        );
      } catch (err) {
        if (isAbortError(err)) return;
        throw err;
      }
    };

    const playReply = async (audioB64: string, subtitleText?: string) => {
      playAbortRef.current?.abort();
      const ac = new AbortController();
      playAbortRef.current = ac;
      if (subtitleText) {
        setSubtitle(subtitleText);
        rememberSpoken(subtitleText);
      }
      setTurn("speaking");
      await waitForUiPaint();
      try {
        await playBase64Wav(audioB64, ac.signal);
      } catch (err) {
        if (isAbortError(err)) return;
        throw err;
      }
    };

    const playKannadaLine = async (
      text: string,
      cachedB64?: string,
      speaker?: "Suresh" | "Anu",
    ) => {
      // Show text on UI first, then speak — never speak before the subtitle paints.
      setSubtitle(text);
      rememberSpoken(text);
      await waitForUiPaint();
      await playKannada(text, cachedB64, speaker);
    };

    const listenForSpeech = async (opts: VadListenOptions = {}) => {
      setTurn("preparing");
      // Keep a useful hint ("ಮತ್ತೆ ಹೇಳಿ…") while the mic gets ready; the status box
      // already says "wait" and then turns green.
      setHint((prev) => prev || "ಮೈಕ್ರೊಫೋನ್ ಸಿದ್ಧವಾಗುತ್ತಿದೆ…");
      await waitForUiPaint();
      return listenOnceRef.current({
        ...opts,
        onMicReady: () => {
          setTurn("listening");
          setHint((prev) => (prev && prev !== "ಮೈಕ್ರೊಫೋನ್ ಸಿದ್ಧವಾಗುತ್ತಿದೆ…" ? prev : "ಈಗ ಮಾತನಾಡಿ"));
          opts.onMicReady?.();
        },
      });
    };

    const continueAssist = async () => {
      setSession(null);
      setMode("assist");
      setSubmitWarning(null);
      setHint("ಮತ್ತೊಂದು ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಬಹುದು");
      await playKannadaLine(ANYTHING_ELSE_KN);
    };

    const openFormById = async (
      formId: string,
      opts?: {
        skipFirstFieldPrompt?: boolean;
        prefill?: Record<string, string>;
        detail?: BankForm;
      },
    ) => {
      const detail = opts?.detail ?? (await fetchForm(formId));
      if (!still()) return;
      const values = { ...autoFilledValues(detail), ...(opts?.prefill ?? {}) };
      const shown: Record<string, string> = {};
      let fieldIndex = 0;
      const askFields = askableFields(detail);
      if (opts?.prefill?.account_number && askFields[0]?.id === "account_number") {
        fieldIndex = 1;
      }
      session = {
        form: detail,
        fieldIndex,
        values,
        shown,
        promptAudio: {},
        skipFirstFieldPrompt: opts?.skipFirstFieldPrompt ?? false,
      };
      setSession(session);
      setMode("form");
      setSubmitted(null);
      setLastResult(null);
      setBalanceResult(null);
      setHint(`ಅರ್ಜಿ: ${detail.title_kn}`);
      await runFormLoop();
      if (!still()) return;
      // Balance inquiry already spoke the result and should not reopen assist TTS.
      if (formId === "balance_inquiry") return;
      await continueAssist();
    };

    const runFormLoop = async () => {
      while (still()) {
        if (!session) return;

        const fields = askableFields(session.form);
        if (session.fieldIndex >= fields.length) {
          if (session.form.id === "balance_inquiry") {
            const acct = session.values.account_number?.trim();
            setTurn("thinking");
            try {
              const bal = await fetchDemoBalance(acct || "");
              setBalanceResult(bal);
              setTurn("speaking");
              setHint(bal.message_kn);
              await playKannadaLine(bal.message_kn);
              if (!bal.found) {
                // Ambiguous — multiple accounts share last 4 digits — ask for 6
                const askFor6 = (bal as Record<string, unknown>).ambiguous === true;
                session = {
                  ...session,
                  fieldIndex: 0,
                  values: {
                    ...session.values,
                    account_number: askFor6
                      ? (acct?.slice(-4) ?? "")  // keep what they said so hint shows it
                      : "",
                  },
                  skipFirstFieldPrompt: false,
                };
                setSession(session);
                continue;
              }
            } catch (err) {
              if (isAbortError(err)) return;
              setError(customerError("Balance lookup failed", err));
            }
            setSession(null);
            return;
          }

          // Every answer was already read back and confirmed — send the form now,
          // no second read-back of the whole form and no printed sheet.
          setTurn("thinking");
          setHint("ಅರ್ಜಿಯನ್ನು ಕಳುಹಿಸಲಾಗುತ್ತಿದೆ…");
          setSubtitle(null);
          const done = session;
          let saved = true;
          let confirmText = "ನಿಮ್ಮ ಅರ್ಜಿಯನ್ನು ಸ್ವೀಕರಿಸಲಾಗಿದೆ. ದಯವಿಟ್ಟು ಹತ್ತಿರದ ಶಾಖೆಗೆ ಭೇಟಿ ನೀಡಿ. ಧನ್ಯವಾದಗಳು.";
          try {
            const submitResult = await submitFormSubmission({
              form_id: done.form.id,
              title_kn: done.form.title_kn,
              title_en: done.form.title_en,
              values: done.values,
              kiosk_session_id: kioskSessionRef.current ?? undefined,
            });
            const confirmKn = (submitResult as Record<string, unknown>).confirmation_kn as string | undefined;
            if (confirmKn?.trim()) confirmText = confirmKn;
            setSubmitWarning(null);
          } catch (err) {
            if (isAbortError(err)) return;
            saved = false;
            confirmText = "ಅರ್ಜಿಯನ್ನು ಉಳಿಸಲಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಸಿಬ್ಬಂದಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ.";
            setSubmitWarning("ಅರ್ಜಿಯನ್ನು ಉಳಿಸಲಾಗಲಿಲ್ಲ — ದಯವಿಟ್ಟು ಸಿಬ್ಬಂದಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ");
          }
          if (!still()) return;
          setSubmitted({ form: done.form, values: done.values, shown: done.shown, saved });
          if (saved) onOutcomeRef.current?.("happy");
          setSession(null);
          try {
            await playKannadaLine(confirmText);
          } catch (err) {
            if (isAbortError(err)) return;
            console.warn("[hands-free] Confirmation TTS failed:", err);
          }
          return;
        }

        const field = fields[session.fieldIndex];
        setDraft("");
        setTurn("form_prompt");
        const skipPrompt =
          session.skipFirstFieldPrompt &&
          session.fieldIndex === 0 &&
          field.id === "account_number";
        if (!skipPrompt && field.prompt_kn) {
          let promptAudio = session.promptAudio[field.id];
          if (!promptAudio) {
            setTurn("preparing");
            promptAudio = await fetchSpeakKannada(field.prompt_kn).catch(() => "");
            if (!still()) return;
          }

          const nextField = fields[session.fieldIndex + 1];
          if (
            nextField?.prompt_kn &&
            !session.promptAudio[nextField.id]
          ) {
            const activeFormId = session.form.id;
            void fetchSpeakKannada(nextField.prompt_kn)
              .then((audio) => {
                if (!audio || !still() || session?.form.id !== activeFormId) return;
                setSession({
                  ...session,
                  promptAudio: { ...session.promptAudio, [nextField.id]: audio },
                });
              })
              .catch(() => undefined);
          }

          setSubtitle(field.prompt_kn);
          await playKannada(field.prompt_kn, promptAudio);
        }
        if (!still()) return;

        const blob = await listenForSpeech(formListenOpts(field));
        if (!still()) return;
        if (!blob) {
          setHint("ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಜೋರಾಗಿ ಮತ್ತು ಸ್ಪಷ್ಟವಾಗಿ ಹೇಳಿ");
          continue;
        }

        setTurn("thinking");
        try {
          const ext = blob.type.includes("ogg") ? "ogg" : "webm";
          const filled = await fillFormFieldAudio(blob, field.type, field.id, `field.${ext}`);
          if (!still()) return;
          setHeard(filled.kannada_text?.trim() || null);

          const skipSource = `${filled.kannada_text} ${filled.english_text} ${filled.value}`;
          if (isEndSessionCommand(filled.kannada_text, filled.english_text)) {
            onEndRef.current("Customer ended during form");
            return;
          }

          if (filled.validation_error) {
            setDraft("");
            setError(filled.validation_error);
            setHint("ದಯವಿಟ್ಟು ಸಂಖ್ಯೆಯನ್ನು ಒಂದೊಂದೇ ಅಂಕಿಯಾಗಿ ಮತ್ತೆ ಹೇಳಿ");
            await playKannada(filled.validation_error);
            continue;
          }

          if (!field.required && isSkipCommand(skipSource)) {
            session = {
              ...session,
              fieldIndex: session.fieldIndex + 1,
              values: { ...session.values, [field.id]: "" },
              shown: { ...session.shown, [field.id]: "" },
            };
            setSession(session);
            setError(null);
            continue;
          }

          let value = resolveFormFieldValue(filled, field);
          if (field.required && !value) {
            setError("ನಿಮ್ಮ ಉತ್ತರ ಕೇಳಿಸಲಿಲ್ಲ — ದಯವಿಟ್ಟು ಮತ್ತೆ ಸ್ಪಷ್ಟವಾಗಿ ಹೇಳಿ");
            setHint("ದಯವಿಟ್ಟು ನಿಮ್ಮ ಉತ್ತರವನ್ನು ಮತ್ತೆ ಸ್ಪಷ್ಟವಾಗಿ ಹೇಳಿ");
            continue;
          }
          let spoken = readBackText(filled, field, value);
          let heardKn = filled.spoken_kn?.trim() || filled.kannada_text?.trim() || "";
          setDraft(value);
          setDraftKn(kannadaDisplayValue(field.id, field.type, value, heardKn));

          // Read the answer back. "ಹೌದು" accepts it, "ಇಲ್ಲ" asks the question again, and
          // anything else is the customer saying the correct answer — use it and read
          // that back (the prompt itself says "ತಪ್ಪಿದ್ದರೆ ಮಾಹಿತಿಯನ್ನು ಮತ್ತೆ ಹೇಳಿ").
          let accepted = false;
          for (let round = 0; round < MAX_CONFIRM_ROUNDS && !accepted; round += 1) {
            setTurn("form_confirm");
            await playKannada(spoken ? `${spoken}. ${FORM_CONFIRM_SUFFIX_KN}` : FORM_CONFIRM_SUFFIX_KN);
            if (!still()) return;

            const confirmBlob = await listenForSpeech();
            if (!still()) return;
            if (!confirmBlob) continue;

            setTurn("thinking");
            const confirmExt = confirmBlob.type.includes("ogg") ? "ogg" : "webm";
            const confirmFill = await fillFormFieldAudio(
              confirmBlob,
              "text",
              "confirm",
              `confirm.${confirmExt}`,
            );
            if (!still()) return;
            setHeard(confirmFill.kannada_text?.trim() || null);

            const parts = [confirmFill.kannada_text, confirmFill.english_text, confirmFill.value];
            if (isEndSessionCommand(...parts)) {
              onEndRef.current("Customer ended during confirm");
              return;
            }
            if (isAffirmCommand(...parts)) {
              accepted = true;
              break;
            }
            if (isRejectCommand(...parts)) break; // ask the question again
            if (!parts.join(" ").trim()) continue; // nothing heard — read back again

            // A correction: understand the reply as this field's answer.
            setHint("ಹೊಸ ಉತ್ತರವನ್ನು ಪರಿಶೀಲಿಸುತ್ತಿದ್ದೇನೆ");
            const corrected = await fillFormFieldAudio(
              confirmBlob,
              field.type,
              field.id,
              `correction.${confirmExt}`,
            );
            if (!still()) return;
            setHeard(corrected.kannada_text?.trim() || null);
            if (corrected.validation_error) {
              setError(corrected.validation_error);
              await playKannada(corrected.validation_error);
              continue;
            }
            const correctedValue = resolveFormFieldValue(corrected, field);
            if (!correctedValue) continue;
            value = correctedValue;
            spoken = readBackText(corrected, field, correctedValue);
            heardKn = corrected.spoken_kn?.trim() || corrected.kannada_text?.trim() || "";
            setDraft(value);
            setDraftKn(kannadaDisplayValue(field.id, field.type, value, heardKn));
            setError(null);
            setHint("ಸರಿಯಾಗಿದ್ದರೆ ಹೌದು ಎಂದು ಹೇಳಿ; ತಪ್ಪಿದ್ದರೆ ಮಾಹಿತಿಯನ್ನು ಮತ್ತೆ ಹೇಳಿ");
          }
          if (!accepted) {
            // "ಇಲ್ಲ", or still unsure after a few tries — ask the question again.
            setDraft("");
            setHint("ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ");
            continue;
          }

          const finalValue = normalizeFormValue(value, field.type, field.id) || value;
          if (field.required && !finalValue.trim()) {
            setError("ಈ ಮಾಹಿತಿಯನ್ನು ನೀಡುವುದು ಕಡ್ಡಾಯ");
            continue;
          }

          session = {
            ...session,
            fieldIndex: session.fieldIndex + 1,
            values: { ...session.values, [field.id]: finalValue },
            shown: {
              ...session.shown,
              [field.id]: kannadaDisplayValue(field.id, field.type, finalValue, heardKn),
            },
          };
          setSession(session);
          setDraft("");
          setError(null);
        } catch (err) {
          if (!still()) return;
          if (isAbortError(err)) return;
          setError(customerError("Form fill failed", err));
        }
      }
    };

    const runAssistLoop = async () => {
      setLastResult(null);
      setError(null);
      setSession(null);
      setMode("assist");

      // First line: the time-of-day greeting (it already asks how we can help),
      // straight on this screen — there is no separate greeting page.
      const greet = greetingRef.current;
      setTurn("speaking");
      setHint(null);
      try {
        if (greet?.line_kn) {
          let cached = "";
          if (greet.slot && greet.variant !== undefined) {
            cached = await fetchKioskGreetAudio({
              slot: greet.slot,
              variant: greet.variant,
              hour: new Date().getHours(),
              random: false,
              generate: false,
            })
              .then((d) => (d.cached ? d.audio_b64 : ""))
              .catch(() => "");
            if (!still()) return;
          }
          await playKannadaLine(greet.line_kn, cached || undefined);
        } else {
          await playKannadaLine(ASK_NEED_KN);
        }
      } catch (err) {
        if (isAbortError(err)) return;
        console.warn("[hands-free] Greeting voice failed:", err);
      }
      if (!still()) return;

      while (still()) {
        setMode("assist");
        setError(null);

        const blob = await listenForSpeech();
        if (!still()) return;
        if (!blob) {
          emptyListenCount += 1;
          // Do not speak on every empty listen — that creates listen↔speak loops
          // when the room is quiet or the mic picks up echo.
          if (emptyListenCount === 2) {
            onOutcomeRef.current?.("confused");
            setHint("ಕೇಳಲಿಲ್ಲ — ದಯವಿಟ್ಟು ಸ್ಪಷ್ಟವಾಗಿ ಹೇಳಿ");
          }
          if (emptyListenCount >= 4) {
            setHint("ಕೇಳಲಿಲ್ಲ — ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ");
            onOutcomeRef.current?.("confused");
            await playKannada(SAY_AGAIN_KN);
            emptyListenCount = 0;
          }
          // After 8 empty listens (~3 min of silence) — end session automatically
          if (emptyListenCount >= 8) {
            await playKannada("ಯಾವುದೇ ಪ್ರತಿಕ್ರಿಯೆ ಇಲ್ಲ. ಸೆಷನ್ ಮುಗಿಸಲಾಗುತ್ತಿದೆ. ಧನ್ಯವಾದಗಳು.");
            onEndRef.current("Auto-ended: no speech detected for extended period");
            return;
          }
          continue;
        }
        emptyListenCount = 0;
        setBalanceResult(null);

        setTurn("thinking");
        try {
          const ext = blob.type.includes("ogg") ? "ogg" : "webm";
          // Text only: the reply shows on screen at once and is spoken via
          // /api/speak-kannada, so TTS never holds the single STT/NLU worker.
          const result = await processAudio(
            blob,
            `lobby.${ext}`,
            pipelineContext(),
            { includeAudio: false },
          );
          if (!still()) return;

          // The mic heard the assistant itself — not a customer request, so ignore it.
          if (isEcho(result.kannada_text, spokenRef.current.map((l) => l.text))) {
            console.warn("[hands-free] Ignored echo of the assistant's own voice");
            continue;
          }

          setLastResult(result);
          rememberTurn(result);
          // Clear a stale "service unavailable" notice once a request goes through again.
          if (!result.error) setError((prev) => (prev === SERVICE_DOWN_KN ? null : prev));

          if (result.error) {
            const canProceed = Boolean(result.form_id);
            if (!canProceed) {
              // Not understood — asking again is enough (no technical message on screen).
              console.warn("[hands-free] Request not understood:", result.error);
              if (result.error_code === "service_unavailable") {
                // A model or service is down — say so instead of "please say again".
                setError(SERVICE_DOWN_KN);
                onOutcomeRef.current?.("confused");
              }
              try {
                await playKannadaLine(result.response_text_kn?.trim() || SAY_AGAIN_KN, undefined, result.tts_speaker);
              } catch (playErr) {
                if (isAbortError(playErr)) return;
                console.warn("[hands-free] TTS fallback failed:", playErr);
              }
              continue;
            }
          }

          if (isEndSessionCommand(result.kannada_text, result.english_text)) {
            onEndRef.current("Customer said goodbye");
            return;
          }

          // Not clear which form the customer wants — no menu, just ask again.
          if (result.route === "form_menu") {
            await playKannadaLine(WHICH_FORM_KN);
            continue;
          }

          if (result.route === "transactional" && result.form_id) {
            try {
              const detailPromise = fetchForm(result.form_id).then(
                (detail) => ({ detail, error: null }),
                (error: unknown) => ({ detail: null, error }),
              );
              if (result.audio_b64) {
                try {
                  await playReply(result.audio_b64, result.response_text_kn);
                } catch (speechError) {
                  if (isAbortError(speechError)) return;
                  console.warn("[hands-free] Form opener audio failed:", speechError);
                }
              } else if (result.response_text_kn) {
                try {
                  await playKannadaLine(
                    result.response_text_kn,
                    undefined,
                    result.tts_speaker,
                  );
                } catch (speechError) {
                  if (isAbortError(speechError)) return;
                  console.warn("[hands-free] Form opener TTS failed:", speechError);
                }
              }
              const loaded = await detailPromise;
              if (loaded.error) throw loaded.error;
              const detail = loaded.detail;
              if (!detail) throw new Error("Could not load form");
              if (!still()) return;
              await openFormById(result.form_id, {
                skipFirstFieldPrompt: false,
                prefill: result.prefill,
                detail,
              });
            } catch (err) {
              if (isAbortError(err)) return;
              setError(customerError("Could not open form", err));
            }
            continue;
          }

          if (result.audio_b64) {
            await playReply(result.audio_b64, result.response_text_kn);
          } else if (result.response_text_kn) {
            await playKannadaLine(
              result.response_text_kn,
              undefined,
              result.tts_speaker,
            );
          }
        } catch (err) {
          if (!still()) return;
          if (isAbortError(err)) return;
          if (userFacingFetchError(err)) setError(customerError("Request failed", err));
        }
      }
    };

      await runAssistLoop();
    };

    void run();

    return () => {
      cancelled = true;
      abort();
      releaseMic();
      playAbortRef.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, [active, abort, releaseMic, kioskSessionId]);

  useEffect(() => {
    if (!active) {
      onFormModeRef.current?.(false);
    }
  }, [active]);

  useEffect(() => {
    onTurnRef.current?.(turn);
  }, [turn]);

  const micPct = Math.min(100, Math.round(micLevel * 800));
  const form = formSession?.form ?? null;
  const fieldIndex = formSession?.fieldIndex ?? 0;
  const values = formSession?.values ?? {};
  const askFields = form ? askableFields(form) : [];
  const currentField = askFields[fieldIndex] ?? null;

  const status = statusView(turn, vadState);
  const shownError = error ?? vadError;
  const agentLine = subtitle?.trim() || null;
  const stepTotal = askFields.length;
  const stepNow = Math.min(fieldIndex + 1, stepTotal);
  const progressPct = stepTotal
    ? Math.round((Math.min(fieldIndex, stepTotal) / stepTotal) * 100)
    : 0;
  // In a form the current question is the headline — never repeat it as a second bubble.
  const formAgentLine =
    agentLine && agentLine !== currentField?.prompt_kn && agentLine !== shownError
      ? agentLine
      : null;
  // The balance card already shows its own message.
  const assistText =
    agentLine && agentLine !== balanceResult?.message_kn
      ? agentLine
      : !balanceResult
        ? lastResult?.response_text_kn?.trim() || null
        : null;
  const shownHint =
    hint &&
    !REDUNDANT_HINT.test(hint) &&
    hint !== agentLine &&
    hint !== shownError &&
    hint !== balanceResult?.message_kn
      ? hint
      : null;

  // Details side: the form being filled, else the one just sent.
  const detailsForm = form ?? submitted?.form ?? null;
  const detailsValues = form ? values : (submitted?.values ?? {});
  const detailsShown = form ? formSession?.shown : submitted?.shown;
  const detailsRows = detailsForm
    ? detailsForm.fields.map((f) => {
        const raw = detailsValues[f.id] ?? "";
        const isCurrent = Boolean(form) && f.id === currentField?.id;
        const text =
          isCurrent && draft
            ? draftKn || kannadaDisplayValue(f.id, f.type, draft)
            : detailsShown?.[f.id] || (raw ? kannadaDisplayValue(f.id, f.type, raw) : "");
        return { id: f.id, label: f.label_kn, text, isCurrent, done: Boolean(raw) && !isCurrent };
      })
    : [];

  return (
    <div className={`hf hf-mode-${mode}`}>
      <div className="hf-talk">
        <div className={`hf-status hf-tone-${status.tone}`} aria-live="polite">
          <span className="hf-status-dot" aria-hidden />
          <div className="hf-status-text">
            <p className="hf-status-kn">{status.kn}</p>
          </div>
          {turn === "listening" && (
            <div className="hf-meter" aria-hidden>
              <div className="hf-meter-fill" style={{ width: `${micPct}%` }} />
            </div>
          )}
          {/* Voice orb: swells with the customer's actual voice so they know they are heard. */}
          <span
            className={`hf-orb${turn === "listening" ? " is-live" : ""}`}
            style={{ ["--lvl" as string]: String(Math.min(1, micPct / 60)) }}
            aria-hidden
          />
        </div>
        {form && stepTotal > 0 && (
          <div className="hf-steps" role="progressbar" aria-valuemin={1} aria-valuemax={stepTotal} aria-valuenow={Math.min(fieldIndex + 1, stepTotal)}>
            {askFields.map((f, i) => (
              <span key={f.id} className={`hf-step${i < fieldIndex ? " is-done" : i === fieldIndex ? " is-current" : ""}`} />
            ))}
            <span className="hf-steps-label">
              {Math.min(fieldIndex + 1, stepTotal)} / {stepTotal}
            </span>
          </div>
        )}
        {shownHint && <p className="hf-hint">{shownHint}</p>}

        <section className="hf-card">
          {mode === "form" && form ? (
            <>
              <header className="hf-form-head">
                <div className="hf-form-titles">
                  <h2 className="hf-form-title">{form.title_kn}</h2>
                </div>
                {stepTotal > 0 && (
                  <p className="hf-step">
                    {stepNow} / {stepTotal}
                  </p>
                )}
              </header>
              {stepTotal > 0 && (
                <div className="hf-progress" aria-hidden>
                  <span style={{ width: `${progressPct}%` }} />
                </div>
              )}

              {formAgentLine && <p className="hf-agent-line">{formAgentLine}</p>}

              {currentField && (
                <div className="hf-question">
                  <p className="hf-question-label">{currentField.label_kn}</p>
                  <p className="hf-question-text">
                    {currentField.prompt_kn || currentField.label_kn}
                  </p>
                </div>
              )}

              {currentField && draft && (
                <LiveValueCard
                  label={currentField.label_kn}
                  value={currentField.type === "text" ? draftKn || draft : draft}
                  fieldType={currentField.type}
                  fieldId={currentField.id}
                  lastDigits={form.id === "balance_inquiry" && currentField.id === "account_number"}
                />
              )}

              {shownError && (
                <p className="hf-retry" role="alert">
                  {shownError}
                </p>
              )}
            </>
          ) : (
            <>
              {balanceResult && <BalanceResultCard result={balanceResult} />}
              {assistText ? (
                <p className="hf-agent-text">{assistText}</p>
              ) : (
                !balanceResult && (
                  <div className="hf-welcome">
                    <p className="hf-agent-text">ನಿಮಗೆ ಏನು ಸಹಾಯ ಬೇಕು?</p>
                    <p className="hf-agent-en">ಉದಾಹರಣೆಗೆ ಹೀಗೆ ಹೇಳಿ:</p>
                    <ul className="hf-try">
                      {TRY_SAYING_KN.map((phrase) => (
                        <li key={phrase}>“{phrase}”</li>
                      ))}
                    </ul>
                  </div>
                )
              )}
              {lastResult?.route === "transactional" && lastResult.form_id && (
                <p className="hf-note">ಅರ್ಜಿ ತೆರೆಯಲಾಗುತ್ತಿದೆ…</p>
              )}
              {shownError && (
                <p className="hf-retry" role="alert">
                  {shownError}
                </p>
              )}
            </>
          )}

          {submitWarning && <p className="hf-retry hf-retry--soft">{submitWarning}</p>}
        </section>

        {heard && (
          <p className="hf-heard">
            <span className="hf-heard-label">ನೀವು ಹೇಳಿದ್ದು</span>
            <span className="hf-heard-text">“{heard}”</span>
          </p>
        )}

        <footer className="hf-footer">
          <SpeakGuideCard compact />
          <p className="hf-end-tip">ಮುಗಿಸಲು “ಮುಗಿಸು” ಎಂದು ಹೇಳಿ</p>
        </footer>
      </div>

      <aside className="hf-details" aria-label="ನಿಮ್ಮ ವಿವರಗಳು">
        {presence}
        <section className="hf-details-card">
          <h2 className="hf-details-title">ನಿಮ್ಮ ವಿವರಗಳು</h2>
          {detailsForm ? (
            <>
              <p className="hf-details-form">{detailsForm.title_kn}</p>
              {!form && submitted && (
                <p className={`hf-details-done${submitted.saved ? "" : " is-warn"}`}>
                  {submitted.saved ? "✓ ಅರ್ಜಿಯನ್ನು ಸಲ್ಲಿಸಲಾಗಿದೆ" : "ಅರ್ಜಿಯನ್ನು ಉಳಿಸಲಾಗಲಿಲ್ಲ"}
                </p>
              )}
              <dl className="hf-details-list">
                {detailsRows.map((row) => (
                  <div
                    key={row.id}
                    className={["hf-details-row", row.isCurrent ? "is-current" : "", row.done ? "is-done" : ""]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <dt>{row.label}</dt>
                    <dd>{row.text || "—"}</dd>
                  </div>
                ))}
              </dl>
            </>
          ) : (
            <p className="hf-details-empty">ಅರ್ಜಿ ತೆರೆದಾಗ ನೀವು ನೀಡುವ ವಿವರಗಳು ಇಲ್ಲಿ ಕಾಣುತ್ತವೆ.</p>
          )}
        </section>
      </aside>
    </div>
  );
}
