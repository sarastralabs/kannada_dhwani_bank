import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  beginKioskSession,
  endKioskSession,
  fetchGreetingCatalog,
  fetchKioskGreetAudio,
  fetchKioskStatusLite,
  reportKioskPresence,
  setKioskPhase,
  type KioskStatus,
} from "../api/client";

import { startVisibilityAwarePoll } from "../utils/polling";

import {
  greetingForNowFallback,
  pickRandomFromCatalog,
  slotForHour,
  type Greeting,
  type GreetingCatalogSlot,
} from "../utils/greetings";

import { preloadBrowserVoices, unlockAudio } from "../utils/playAudio";
import { SESSION_TARGET_S, formatDuration } from "../utils/sessionTime";

import {
  HandsFreeConversation,
  type ConversationGreeting,
  type HandsFreeTurn,
} from "./HandsFreeConversation";

import { LobbyBot, type MascotMood } from "./LobbyBot";
import { SpeakGuideCard } from "./SpeakGuideCard";

/** Customer-facing messages — never ports, URLs or technical errors on this screen. */
const SERVICE_DOWN_KN = "ಸೇವೆ ತಾತ್ಕಾಲಿಕವಾಗಿ ಲಭ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ಸಿಬ್ಬಂದಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ.";

interface AgentLobbyProps {
  apiOnline: boolean | null;
}

/** Warm Parler greeting WAV on disk for the next customer (fire-and-forget). */
function warmGreetingCache(greet: Greeting): void {
  if (greet.variant === undefined) return;
  void fetchKioskGreetAudio({
    slot: greet.slot,
    variant: greet.variant,
    random: false,
    generate: true,
  }).catch(() => undefined);
}

/** Pick greeting locally — no network wait. */
function pickGreetingNow(catalog: GreetingCatalogSlot[] | null): Greeting {
  if (catalog?.length) return pickRandomFromCatalog(catalog);
  return greetingForNowFallback();
}

/** End a leftover session so the next customer starts fresh. */
async function ensureIdleForNewCustomer(phase: string): Promise<KioskStatus | null> {
  if (phase !== "conversation" && phase !== "greeting") return null;
  return endKioskSession("New customer — session reset");
}

export function AgentLobby({ apiOnline }: AgentLobbyProps) {
  const [status, setStatus] = useState<KioskStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  /** Greeting for the current customer — spoken as the conversation's first line. */
  const [sessionGreeting, setSessionGreeting] = useState<ConversationGreeting | null>(null);
  /** When this customer's session started (for the on-screen timer). */
  const [sessionStartMs, setSessionStartMs] = useState<number | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [activeGreet, setActiveGreet] = useState<Greeting>(() => greetingForNowFallback());
  const [greetCatalog, setGreetCatalog] = useState<GreetingCatalogSlot[] | null>(null);
  const [convoMood, setConvoMood] = useState<MascotMood>("listening");
  /** Brief happy / confused reaction that overrides the turn-based mood. */
  const [reaction, setReaction] = useState<MascotMood | null>(null);
  const reactionTimer = useRef<number | null>(null);
  const react = (m: "happy" | "confused") => {
    if (reactionTimer.current) window.clearTimeout(reactionTimer.current);
    setReaction(m);
    reactionTimer.current = window.setTimeout(() => setReaction(null), 3500);
  };

  const greetingStarted = useRef(false);
  /** True while the session on screen was started here (not a stale one to reset). */
  const ownSession = useRef(false);
  const statusRef = useRef(status);
  const statusFailures = useRef(0);
  const hasLoadedStatus = useRef(false);
  const statusGraceUntil = useRef(Date.now() + 60_000);
  statusRef.current = status;

  const mapTurnToMood = (turn: HandsFreeTurn): MascotMood => {
    switch (turn) {
      case "listening":
      case "form_confirm":
        return "listening";
      case "thinking":
      case "preparing":
      case "form_prompt":
        return "thinking";
      case "speaking":
        return "speaking";
      default:
        return "ready";
    }
  };

  useEffect(() => {
    preloadBrowserVoices();
    const unlock = () => {
      void unlockAudio();
    };
    window.addEventListener("pointerdown", unlock, { once: true });
    window.addEventListener("keydown", unlock, { once: true });

    void fetchGreetingCatalog()
      .then((data) => {
        setGreetCatalog(data.greetings);
        setActiveGreet((prev) => {
          const slot = slotForHour(new Date().getHours());
          if (prev.slot === slot) return prev;
          return greetingForNowFallback();
        });
      })
      .catch(() => undefined);

    return () => {
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
    };
  }, []);

  useEffect(() => {
    const tick = () => {
      const slot = slotForHour(new Date().getHours());
      const meta = greetCatalog?.find((g) => g.slot === slot);
      setActiveGreet((prev) => ({
        ...prev,
        slot,
        title_kn: meta?.title_kn ?? greetingForNowFallback().title_kn,
        title_en: meta?.title_en ?? greetingForNowFallback().title_en,
        hours: meta?.hours ?? greetingForNowFallback().hours,
      }));
    };
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, [greetCatalog]);

  const refresh = useCallback(async () => {
    try {
      const s = await fetchKioskStatusLite();
      setStatus((prev) => {
        // Keep greeting UI mid-speech, but never revert once server reached conversation
        if (
          greetingStarted.current &&
          prev?.phase === "greeting" &&
          s.phase !== "conversation"
        ) {
          return { ...s, phase: "greeting", person_present: true, sessions: prev?.sessions ?? [] };
        }
        if (s.phase === "conversation") {
          greetingStarted.current = false;
        }
        return { ...s, sessions: prev?.sessions ?? [] };
      });
      hasLoadedStatus.current = true;
      statusFailures.current = 0;
      setError(null);
      return s;
    } catch (err) {
      if (!hasLoadedStatus.current && Date.now() < statusGraceUntil.current) return null;
      statusFailures.current += 1;
      if (statusFailures.current >= 3) {
        setError(err instanceof Error ? err.message : "Lobby status failed");
      }
      return null;
    }
  }, []);

  useEffect(() => {
    void refresh();
    return startVisibilityAwarePoll(() => {
      void refresh();
    }, 4000, 20000);
  }, [refresh]);

  const statusLoading = status === null;
  const running = status?.running ?? false;
  const phase = status?.phase ?? "stopped";
  const inSession = phase === "greeting" || phase === "conversation";

  const goToConversation = useCallback(async () => {
    try {
      const next = await setKioskPhase("conversation");
      greetingStarted.current = false;
      setStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start conversation");
      throw err;
    }
  }, []);

  /** New customer: pick the greeting and go straight to the conversation screen. */
  const startConversation = useCallback(async () => {
    const greet = pickGreetingNow(greetCatalog);
    setActiveGreet(greet);
    setSessionGreeting({ line_kn: greet.line_kn, slot: greet.slot, variant: greet.variant });
    warmGreetingCache(greet);
    setSessionStartMs(Date.now());
    await goToConversation();
  }, [greetCatalog, goToConversation]);

  // A session left open by a closed tab, a refresh or another device — reset it so
  // this screen starts fresh. Never touches the session this screen started itself.
  useEffect(() => {
    if (!running || greetingStarted.current || ownSession.current) return;
    if (phase !== "conversation" && phase !== "greeting") return;
    const t = window.setTimeout(() => {
      if (greetingStarted.current || ownSession.current) return;
      void endKioskSession("Reset for next customer").then((s) => {
        setStatus(s);
        greetingStarted.current = false;
      });
    }, 2500);
    return () => window.clearTimeout(t);
  }, [running, phase]);

  useEffect(() => {
    if (!running) greetingStarted.current = false;
    if (phase === "idle" || phase === "stopped") {
      greetingStarted.current = false;
      ownSession.current = false;
    }
  }, [running, phase]);

  const handleManualStart = async () => {
    try {
      await unlockAudio();

      let phaseNow = statusRef.current?.phase ?? "idle";
      if (phaseNow === "conversation" || phaseNow === "greeting") {
        const reset = await ensureIdleForNewCustomer(phaseNow);
        if (reset) {
          setStatus(reset);
          phaseNow = reset.phase;
        }
      }

      greetingStarted.current = true;
      ownSession.current = true;
      await reportKioskPresence(true);
      const next = await beginKioskSession();
      setStatus(next);
      await startConversation();
    } catch (err) {
      greetingStarted.current = false;
      ownSession.current = false;
      setError(err instanceof Error ? err.message : "Could not start session");
    }
  };

  const handleEnd = async (note = "Ended on agent screen") => {
    try {
      ownSession.current = false;
      window.speechSynthesis?.cancel();
      const s = await endKioskSession(note);
      setStatus(s);
      greetingStarted.current = false;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not end session");
    }
  };

  // Session timer: target 3 minutes; past that it keeps counting the extra time.
  useEffect(() => {
    if (!inSession) {
      setSessionStartMs(null);
      return;
    }
    setSessionStartMs((prev) => prev ?? Date.now());
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [inSession]);
  const elapsedS = sessionStartMs ? Math.max(0, Math.floor((nowMs - sessionStartMs) / 1000)) : 0;
  const overtime = elapsedS > SESSION_TARGET_S;

  // Staff still see the real error in the browser console.
  useEffect(() => {
    if (error) console.warn("[lobby]", error);
  }, [error]);

  const slotLabel = useMemo(() => {
    const map = {
      morning: "ಬೆಳಗ್ಗೆ",
      afternoon: "ಮಧ್ಯಾಹ್ನ",
      evening: "ಸಂಜೆ",
      night: "ರಾತ್ರಿ",
    } as const;
    return map[activeGreet.slot];
  }, [activeGreet.slot]);

  if (statusLoading) {
    return (
      <div className="lobby-shell lobby-waiting lobby-phase-idle lobby-v2">
        <div className="lobby-ambient" aria-hidden>
          <span className="lobby-ambient-orb lobby-ambient-orb--1" />
          <span className="lobby-ambient-orb lobby-ambient-orb--2" />
        </div>
        <div className="lobby-waiting-stage">
          <div className="lobby-waiting-bot-wrap">
            <LobbyBot mood="waiting" />
          </div>
          <div className="lobby-waiting-card lobby-loading-card">
            <div className="lobby-brand-lockup">
              <span className="lobby-brand-mark kn" aria-hidden>
                ಕ
              </span>
              <p className="lobby-brand kn">ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್</p>
            </div>
            <div className="spinner" role="status" aria-label="ಮಾಹಿತಿ ಪಡೆಯಲಾಗುತ್ತಿದೆ" />
            <h1 className="kn">ಮಾಹಿತಿ ಪಡೆಯಲಾಗುತ್ತಿದೆ…</h1>
          </div>
        </div>
      </div>
    );
  }

  if (!running) {
    return (
      <div className="lobby-shell lobby-waiting lobby-phase-idle lobby-v2">
        <div className="lobby-ambient" aria-hidden>
          <span className="lobby-ambient-orb lobby-ambient-orb--1" />
          <span className="lobby-ambient-orb lobby-ambient-orb--2" />
        </div>
        <div className="lobby-waiting-stage">
          <div className="lobby-waiting-bot-wrap">
            <span className="lobby-pulse-ring" aria-hidden />
            <LobbyBot mood="waiting" />
          </div>
          <div className="lobby-waiting-card">
            <div className="lobby-brand-lockup">
              <span className="lobby-brand-mark kn" aria-hidden>
                ಕ
              </span>
              <p className="lobby-brand kn">ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್</p>
            </div>
            <h1 className="kn">ಕೌಂಟರ್ ಮುಚ್ಚಿದೆ</h1>
            <p className="lobby-waiting-kn kn">
              ದಯವಿಟ್ಟು ಸಿಬ್ಬಂದಿಯವರು ಈ ಕೌಂಟರ್ ತೆರೆಯುವವರೆಗೆ ಕಾಯಿರಿ.
            </p>
            {(apiOnline === false || error) && <p className="api-warning">{SERVICE_DOWN_KN}</p>}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`lobby-shell lobby-fit lobby-v2 lobby-phase-${inSession ? "conversation" : phase} slot-${activeGreet.slot}`}>
      <div className="lobby-ambient" aria-hidden>
        <span className="lobby-ambient-orb lobby-ambient-orb--1" />
        <span className="lobby-ambient-orb lobby-ambient-orb--2" />
      </div>
      <header className="lobby-top">
        <div className="lobby-brand-lockup">
          <span className="lobby-brand-mark kn" aria-hidden>
            ಕ
          </span>
          <div>
            <p className="lobby-brand kn">ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್</p>
            <p className="lobby-phase">{inSession ? "ಕೈ ಬಳಸದೆ ಮಾತನಾಡಿ" : "ಸಿದ್ಧ · ಗ್ರಾಹಕರಿಗಾಗಿ ಕಾಯುತ್ತಿದೆ"}</p>
          </div>
        </div>
        <div className="lobby-top-actions">
          {inSession ? (
            <span
              className={`lobby-chip lobby-timer${overtime ? " is-over" : ""}`}
              title={`ಗುರಿ ${formatDuration(SESSION_TARGET_S)} ನಿಮಿಷ`}
            >
              ⏱ {formatDuration(elapsedS)}
              {overtime
                ? ` · +${formatDuration(elapsedS - SESSION_TARGET_S)}`
                : ` / ${formatDuration(SESSION_TARGET_S)}`}
            </span>
          ) : (
            <span className="lobby-chip">{slotLabel}</span>
          )}
          {inSession && (
            <button type="button" className="danger-btn lobby-end-btn" onClick={() => void handleEnd()}>
              ಮುಗಿಸಿ
            </button>
          )}
        </div>
      </header>

      {(error || apiOnline === false) && (
        <div className="lobby-alert" role="status">
          <p className="lobby-alert-text">{SERVICE_DOWN_KN}</p>
        </div>
      )}

      <div className={`lobby-body lobby-body-${inSession ? "conversation" : phase}`}>
        {!inSession && (
          <>
            <main className="lobby-stage lobby-stage-idle">
              <div className="lobby-hero-bot">
                <span className="lobby-pulse-ring" aria-hidden />
                <LobbyBot mood="ready" className="lobby-bot-hero" />
              </div>
              <div className="lobby-invite">
                <p className="lobby-invite-kicker">{slotLabel}</p>
                <h1>{activeGreet.title_kn}</h1>
                <p className="lobby-invite-kn">ಪ್ರಾರಂಭಿಸಲು ಕೆಳಗಿನ ಬಟನ್ ಒತ್ತಿ</p>
                <button type="button" className="lobby-cta" onClick={() => void handleManualStart()}>
                  ಪ್ರಾರಂಭಿಸಿ
                </button>
                {/* Collapsed: opened by default it pushed the robot off-screen on 1080p. */}
                <SpeakGuideCard compact />
              </div>
            </main>
          </>
        )}

        {inSession && (
          <div className="convo">
            <HandsFreeConversation
              active={phase === "conversation"}
              apiOnline={apiOnline}
              greeting={sessionGreeting}
              kioskSessionId={status?.current_session_id ?? null}
              onRequestEnd={(reason) => void handleEnd(reason)}
              onTurnChange={(turn) => setConvoMood(mapTurnToMood(turn))}
              onOutcome={react}
              presence={
                <div className="convo-presence">
                  <LobbyBot mood={reaction ?? convoMood} className="convo-bot" />
                </div>
              }
            />
          </div>
        )}
      </div>
    </div>
  );
}
