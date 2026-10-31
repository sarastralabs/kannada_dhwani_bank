import { useCallback, useRef, useState } from "react";
import { getSharedAudioContext } from "../utils/playAudio";
import { VAD_DEFAULTS, VadDetector, type VadConfig } from "../utils/vadDetector";

export type VadListenState =
  | "idle"
  | "listening"
  | "speech"
  | "processing_local"
  | "error";

export interface VadListenOptions {
  /** Silence after speech before cutting the turn (ms). */
  silenceMs?: number;
  /** Minimum speech duration to accept (ms). */
  minSpeechMs?: number;
  /** Minimum clearly-voiced audio for a real utterance (ms). */
  minVoicedMs?: number;
  /** Max wait for user to start speaking (ms). */
  maxWaitMs?: number;
  /** Max utterance length (ms). */
  maxUtteranceMs?: number;
  /** Lowest RMS start threshold (quiet mics). */
  speechThreshold?: number;
  /** Fired once the recorder is really capturing — safe to tell the customer to speak. */
  onMicReady?: () => void;
}

/** Detection loop period. A timer (not requestAnimationFrame) keeps running in a background tab. */
const TICK_MS = 20;
/** Mic-level meter refresh for the UI — re-rendering every tick wastes CPU on CPU-only kiosks. */
const LEVEL_UI_MS = 80;
/** Show "speak now" even if the recorder's start event is late. */
const MIC_READY_FALLBACK_MS = 400;

const MIC_CONSTRAINTS: MediaTrackConstraints = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
};

const VAD_DEBUG = (() => {
  try {
    return window.localStorage.getItem("vadDebug") === "1";
  } catch {
    return false;
  }
})();

function pickMimeType(): string | undefined {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type));
}

function rmsFromAnalyser(analyser: AnalyserNode, buf: Uint8Array): number {
  analyser.getByteTimeDomainData(buf);
  let sum = 0;
  for (let i = 0; i < buf.length; i++) {
    const v = (buf[i] - 128) / 128;
    sum += v * v;
  }
  return Math.sqrt(sum / buf.length);
}

interface MicGraph {
  stream: MediaStream;
  ctx: AudioContext;
  source: MediaStreamAudioSourceNode;
  analyser: AnalyserNode;
  buf: Uint8Array;
}

function isLive(stream: MediaStream | null): stream is MediaStream {
  return !!stream && stream.getAudioTracks().some((t) => t.readyState === "live");
}

/** A microphone request that was superseded by releaseMic() — not a real error. */
function isCancelled(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

/** Shown on the customer screen — Kannada only; the real error is logged for staff. */
function micErrorMessage(err: unknown): string {
  console.warn("[VAD] microphone error:", err);
  if (err instanceof DOMException && err.name === "NotAllowedError") {
    return "ಮೈಕ್ರೊಫೋನ್ ಬಳಸಲು ಅನುಮತಿ ಇಲ್ಲ. ದಯವಿಟ್ಟು ಸಿಬ್ಬಂದಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ.";
  }
  return "ಮೈಕ್ರೊಫೋನ್ ಕೆಲಸ ಮಾಡುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಸಿಬ್ಬಂದಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ.";
}

/**
 * Hands-free turn recorder: wait for speech → record until silence → return the clip.
 *
 * The microphone stays open across turns (opening it again each turn clipped the
 * customer's first word while the device and auto-gain warmed up); only
 * ``abort()`` / ``releaseMic()`` close it. Detection logic lives in VadDetector.
 */
export function useVadRecorder() {
  const [state, setState] = useState<VadListenState>("idle");
  const [micLevel, setMicLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const graphRef = useRef<MicGraph | null>(null);
  /** Noise floor learned on this microphone — carried to the next turn. */
  const noiseRef = useRef<number | null>(null);
  /** In-flight getUserMedia — concurrent callers share it instead of opening a second mic. */
  const pendingStreamRef = useRef<Promise<MediaStream> | null>(null);
  /** Bumped on every release; a request that resolves after a release is closed again. */
  const micGenRef = useRef(0);

  const disconnectGraph = useCallback(() => {
    const graph = graphRef.current;
    graphRef.current = null;
    if (!graph) return;
    try {
      graph.source.disconnect();
      graph.analyser.disconnect();
    } catch {
      // already disconnected
    }
  }, []);

  const releaseMic = useCallback(() => {
    micGenRef.current += 1;
    pendingStreamRef.current = null;
    disconnectGraph();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    noiseRef.current = null;
  }, [disconnectGraph]);

  /** Stop the turn in progress but keep the microphone open. */
  const cancelListen = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    cleanupRef.current?.();
    cleanupRef.current = null;
    setState("idle");
  }, []);

  /** End listening and close the microphone (session over / service offline). */
  const abort = useCallback(() => {
    cancelListen();
    releaseMic();
  }, [cancelListen, releaseMic]);

  const ensureStream = useCallback((): Promise<MediaStream> => {
    if (isLive(streamRef.current)) return Promise.resolve(streamRef.current);
    if (pendingStreamRef.current) return pendingStreamRef.current;
    releaseMic(); // drop a dead stream and its audio graph
    const gen = micGenRef.current;
    const request = navigator.mediaDevices
      .getUserMedia({ audio: MIC_CONSTRAINTS })
      .then((stream) => {
        if (micGenRef.current !== gen) {
          // Released while the browser was opening it (session ended, React
          // StrictMode re-mount): close it instead of leaving the mic on.
          stream.getTracks().forEach((t) => t.stop());
          throw new DOMException("Microphone request cancelled", "AbortError");
        }
        streamRef.current = stream;
        return stream;
      })
      .finally(() => {
        if (pendingStreamRef.current === request) pendingStreamRef.current = null;
      });
    pendingStreamRef.current = request;
    return request;
  }, [releaseMic]);

  const ensureGraph = useCallback(
    async (stream: MediaStream): Promise<MicGraph> => {
      const ctx = await getSharedAudioContext();
      if (!ctx) {
        throw new Error("Audio not available — tap the screen once, then try again.");
      }
      const current = graphRef.current;
      if (current && current.stream === stream && current.ctx === ctx) return current;
      disconnectGraph();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      const graph = { stream, ctx, source, analyser, buf: new Uint8Array(analyser.fftSize) };
      graphRef.current = graph;
      return graph;
    },
    [disconnectGraph],
  );

  /** Request mic once so the browser prompt appears before hands-free listening. */
  const warmupMic = useCallback(async (): Promise<boolean> => {
    setError(null);
    try {
      await ensureStream();
      return true;
    } catch (err) {
      if (isCancelled(err)) return false;
      setError(micErrorMessage(err));
      setState("error");
      return false;
    }
  }, [ensureStream]);

  const listenOnce = useCallback(
    async (opts: VadListenOptions = {}): Promise<Blob | null> => {
      const { onMicReady, ...overrides } = opts;
      const cfg: VadConfig = { ...VAD_DEFAULTS, ...overrides };
      cancelListen();
      setError(null);

      const ac = new AbortController();
      abortRef.current = ac;

      let recorder: MediaRecorder | null = null;
      let timer: number | null = null;
      let readyTimer: number | null = null;
      /** Settles the pending turn — cancelling must never leave the caller waiting. */
      let settle: ((blob: Blob | null) => void) | null = null;

      const cleanup = () => {
        settle?.(null);
        settle = null;
        if (timer !== null) window.clearTimeout(timer);
        if (readyTimer !== null) window.clearTimeout(readyTimer);
        timer = readyTimer = null;
        try {
          if (recorder && recorder.state !== "inactive") recorder.stop();
        } catch {
          // ignore
        }
        setMicLevel(0);
        cleanupRef.current = null;
      };
      cleanupRef.current = cleanup;

      try {
        const stream = await ensureStream();
        const graph = await ensureGraph(stream);
        if (ac.signal.aborted) {
          cleanup();
          return null;
        }

        const chunks: Blob[] = [];
        const mimeType = pickMimeType();
        recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data);
        };

        // Tell the customer to speak only once audio is really being captured.
        let announced = false;
        const announce = () => {
          if (announced || ac.signal.aborted) return;
          announced = true;
          setState("listening");
          onMicReady?.();
        };
        recorder.onstart = announce;
        readyTimer = window.setTimeout(announce, MIC_READY_FALLBACK_MS);
        recorder.start(200);

        const detector = new VadDetector(cfg, noiseRef.current);
        let lastUiAt = 0;
        let lastLogAt = 0;

        const blob = await new Promise<Blob | null>((resolvePromise) => {
          const resolve = (value: Blob | null) => {
            settle = null;
            resolvePromise(value);
          };
          settle = resolve;
          const finish = (keep: boolean) => {
            const rec = recorder;
            if (rec && rec.state !== "inactive") {
              rec.onstop = () => {
                const out = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
                resolve(keep && out.size > 0 ? out : null);
              };
              rec.stop();
            } else {
              resolve(null);
            }
          };

          const tick = () => {
            timer = null;
            if (ac.signal.aborted) {
              resolve(null);
              return;
            }
            const now = performance.now();
            const level = rmsFromAnalyser(graph.analyser, graph.buf);
            if (now - lastUiAt >= LEVEL_UI_MS) {
              lastUiAt = now;
              setMicLevel(level);
            }

            const event = detector.feed(level, now);
            if (event === "speech_start") {
              const t = detector.thresholds();
              console.log(
                `[VAD] speech started level=${level.toFixed(5)} noise=${(detector.noise ?? 0).toFixed(5)} ` +
                  `start=${t.start.toFixed(5)} sustain=${t.sustain.toFixed(5)}`,
              );
              setState("speech");
            } else if (event === "false_start") {
              console.log(`[VAD] false start (not enough voice) — noise now ${(detector.noise ?? 0).toFixed(5)}`);
              setState("listening");
            } else if (event === "timeout") {
              console.log("[VAD] no speech before maxWaitMs");
              noiseRef.current = detector.noise;
              finish(false);
              return;
            } else if (event === "end") {
              const snap = detector.snapshot(now);
              console.log(
                `[VAD] done speechMs=${snap.speechMs.toFixed(0)} voicedMs=${snap.voicedMs.toFixed(0)} ` +
                  `silenceMs=${snap.silenceMs.toFixed(0)}`,
              );
              noiseRef.current = detector.noise;
              setState("processing_local");
              finish(true);
              return;
            }
            if (VAD_DEBUG && detector.isSpeaking && now - lastLogAt >= 500) {
              lastLogAt = now;
              const snap = detector.snapshot(now);
              console.log(
                `[VAD] speaking speechMs=${snap.speechMs.toFixed(0)} voicedMs=${snap.voicedMs.toFixed(0)} ` +
                  `silenceMs=${snap.silenceMs.toFixed(0)} level=${level.toFixed(5)}`,
              );
            }
            timer = window.setTimeout(tick, TICK_MS);
          };
          timer = window.setTimeout(tick, TICK_MS);
        });

        cleanup();
        setState("idle");
        return ac.signal.aborted ? null : blob;
      } catch (err) {
        cleanup();
        if (ac.signal.aborted || isCancelled(err)) {
          setState("idle");
          return null;
        }
        releaseMic();
        setError(micErrorMessage(err));
        setState("error");
        return null;
      } finally {
        if (abortRef.current === ac) abortRef.current = null;
      }
    },
    [cancelListen, ensureStream, ensureGraph, releaseMic],
  );

  return { state, error, micLevel, listenOnce, abort, releaseMic, warmupMic };
}
