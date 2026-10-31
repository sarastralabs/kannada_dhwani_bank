/**
 * Energy-based voice activity detection — pure logic, no browser APIs.
 *
 * Feed it one microphone RMS level per tick; it tells the recorder when speech
 * started, when the turn ended, or when nobody spoke. Kept separate from the
 * recorder hook so it can be tested with recorded level sequences.
 *
 *  - Noise floor: measured over the first ~0.6 s of a fresh microphone (a low
 *    percentile, so the gaps between words reveal the background even if the
 *    customer talks at once — the audio is still recorded), then followed slowly
 *    while the customer is silent and carried over to the next turn.
 *  - Start / sustain thresholds sit above that floor (hysteresis), so a steady fan
 *    hum in a noisy room no longer counts as speech.
 *  - A turn only counts if it contains enough voiced audio; a cough, click or
 *    chair noise followed by silence is a false start and listening continues.
 */

export interface VadConfig {
  /** Silence after speech before the turn ends (ms). */
  silenceMs: number;
  /** Minimum time from speech start before the turn may end (ms). */
  minSpeechMs: number;
  /** Minimum voiced (above-threshold) audio for a real utterance (ms). */
  minVoicedMs: number;
  /** Give up when nobody starts speaking within this time (ms). */
  maxWaitMs: number;
  /** Hard cap on one utterance (ms). */
  maxUtteranceMs: number;
  /** Lowest start threshold (RMS) — keeps quiet laptop mics usable. */
  speechThreshold: number;
  /** Noise calibration window on a fresh microphone (ms). */
  calibrationMs: number;
}

export const VAD_DEFAULTS: VadConfig = {
  // 1.5 s gives enough time to finish a Kannada sentence.
  silenceMs: 1500,
  minSpeechMs: 400,
  minVoicedMs: 250,
  maxWaitMs: 25000,
  maxUtteranceMs: 18000,
  // Quiet laptop mics read ~0.005 RMS while speaking.
  speechThreshold: 0.004,
  calibrationMs: 600,
};

export type VadEvent = "none" | "speech_start" | "false_start" | "end" | "timeout";

/** Below this noise floor the original quiet-mic thresholds apply unchanged. */
const QUIET_ROOM_NOISE = 0.005;
const QUIET_START_CAP = 0.006;
const LOUD_START_CAP = 0.03;
/** How fast the floor follows the room while silent (per tick). */
const NOISE_FOLLOW = 0.02;

export function vadThresholds(
  noise: number,
  minStart: number = VAD_DEFAULTS.speechThreshold,
): { start: number; sustain: number } {
  let start: number;
  if (noise <= QUIET_ROOM_NOISE) {
    // Quiet room: same behaviour that already works on the main kiosk.
    start = Math.min(Math.max(minStart, noise * 1.2), QUIET_START_CAP);
  } else {
    // Noisy room (fan, traffic): start clearly above the background.
    start = Math.min(Math.max(QUIET_START_CAP, noise * 1.6), LOUD_START_CAP);
  }
  // Sustain needs clearly audible speech, but never so high that normal speech
  // (≈0.05–0.1 RMS) is mistaken for silence.
  const sustain = Math.min(start * 2.5, Math.max(start * 1.5, 0.04));
  return { start, sustain };
}

function percentile(values: number[], p: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
}

export class VadDetector {
  private readonly cfg: VadConfig;
  private noiseFloor: number | null;
  private calibration: number[] = [];
  private startedAt: number | null = null;
  private lastTick: number | null = null;
  private speaking = false;
  private speechStartedAt = 0;
  private lastLoudAt = 0;
  private voicedMs = 0;
  private levelSum = 0;
  private levelCount = 0;

  /** ``knownNoise`` — floor learned on an earlier turn with the same microphone. */
  constructor(cfg: Partial<VadConfig> = {}, knownNoise: number | null = null) {
    this.cfg = { ...VAD_DEFAULTS, ...cfg };
    this.noiseFloor = knownNoise;
  }

  /** Current noise floor (null while still calibrating a fresh microphone). */
  get noise(): number | null {
    return this.noiseFloor;
  }

  get isSpeaking(): boolean {
    return this.speaking;
  }

  thresholds(): { start: number; sustain: number } {
    return vadThresholds(this.noiseFloor ?? 0, this.cfg.speechThreshold);
  }

  /** Process one level sample taken at ``now`` (ms). */
  feed(level: number, now: number): VadEvent {
    if (this.startedAt === null) this.startedAt = now;
    const dt = this.lastTick === null ? 0 : Math.max(0, now - this.lastTick);
    this.lastTick = now;

    // Fresh microphone: measure the room first. Speech in this window is still
    // recorded; detection simply starts once the floor is known.
    if (this.noiseFloor === null) {
      this.calibration.push(level);
      if (now - this.startedAt < this.cfg.calibrationMs) return "none";
      this.noiseFloor = percentile(this.calibration, 0.2);
    }

    const { start, sustain } = this.thresholds();

    if (!this.speaking) {
      if (level >= start) {
        this.speaking = true;
        this.speechStartedAt = now;
        this.lastLoudAt = now;
        this.voicedMs = 0;
        this.levelSum = 0;
        this.levelCount = 0;
        return "speech_start";
      }
      // Follow slow changes in the room from silent frames.
      this.noiseFloor += (level - this.noiseFloor) * NOISE_FOLLOW;
      return now - this.startedAt > this.cfg.maxWaitMs ? "timeout" : "none";
    }

    this.levelSum += level;
    this.levelCount += 1;
    // Only clearly audible frames count as voice — background between the start
    // and sustain thresholds does not.
    if (level >= sustain) {
      this.voicedMs += dt;
      this.lastLoudAt = now;
    }
    const speechMs = now - this.speechStartedAt;
    const silenceMs = now - this.lastLoudAt;

    if (speechMs >= this.cfg.maxUtteranceMs) return "end";
    if (speechMs >= this.cfg.minSpeechMs && silenceMs >= this.cfg.silenceMs) {
      if (this.voicedMs < this.cfg.minVoicedMs) {
        // A short noise, or the room got louder — not speech. Lift the floor to
        // what was just heard so the same background does not restart a turn.
        const meanLevel = this.levelCount ? this.levelSum / this.levelCount : level;
        this.noiseFloor = Math.max(this.noiseFloor ?? 0, meanLevel);
        this.speaking = false;
        return now - this.startedAt > this.cfg.maxWaitMs ? "timeout" : "false_start";
      }
      return "end";
    }
    return "none";
  }

  /** Diagnostics for console logs. */
  snapshot(now: number): { speechMs: number; silenceMs: number; voicedMs: number } {
    return {
      speechMs: this.speaking ? now - this.speechStartedAt : 0,
      silenceMs: this.speaking ? now - this.lastLoudAt : 0,
      voicedMs: this.voicedMs,
    };
  }
}
