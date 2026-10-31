import { describe, expect, it } from "vitest";
import { VAD_DEFAULTS, VadDetector, vadThresholds, type VadEvent } from "./vadDetector";

const TICK = 20;

/** Speech-like level: loud syllables with short gaps between words. */
function speech(t: number, loud = 0.07): number {
  return t % 300 < 240 ? loud : loud * 0.25;
}

/** Feed `level(t)` every tick for `durationMs`; return events with their times. */
function run(
  level: (t: number) => number,
  durationMs: number,
  knownNoise: number | null = null,
  stopOnEnd = true,
): { event: VadEvent; t: number }[] {
  const vad = new VadDetector({}, knownNoise);
  const events: { event: VadEvent; t: number }[] = [];
  for (let t = 0; t <= durationMs; t += TICK) {
    const event = vad.feed(level(t), t);
    if (event !== "none") {
      events.push({ event, t });
      if (stopOnEnd && (event === "end" || event === "timeout")) break;
    }
  }
  return events;
}

const kinds = (events: { event: VadEvent }[]) => events.map((e) => e.event);

describe("vadThresholds", () => {
  it("keeps the original quiet-mic thresholds in a quiet room", () => {
    expect(vadThresholds(0.002)).toEqual({ start: 0.004, sustain: 0.01 });
    expect(vadThresholds(0.0045).start).toBeCloseTo(0.0054);
    expect(vadThresholds(0.005).start).toBeLessThanOrEqual(0.006);
  });

  it("puts the start threshold clearly above loud background noise", () => {
    const { start, sustain } = vadThresholds(0.012);
    expect(start).toBeGreaterThan(0.012);
    expect(sustain).toBeGreaterThan(start);
    // Normal speech (≈0.05–0.1) must still count as voice.
    expect(sustain).toBeLessThanOrEqual(0.04);
  });
});

describe("VadDetector", () => {
  it("quiet room: detects a sentence and ends after the trailing silence", () => {
    const events = run((t) => (t >= 1000 && t < 3000 ? speech(t) : 0.002), 10000);
    expect(kinds(events)).toEqual(["speech_start", "end"]);
    expect(events[0].t).toBe(1000);
    // Ends ~1.5 s after the last loud syllable.
    expect(events[1].t).toBeGreaterThanOrEqual(4400);
    expect(events[1].t).toBeLessThanOrEqual(4600);
  });

  it("a cough is a false start, then the real sentence is still captured", () => {
    const level = (t: number) => {
      if (t >= 1000 && t < 1120) return 0.08; // cough
      if (t >= 4000 && t < 6000) return speech(t);
      return 0.002;
    };
    const events = run(level, 15000);
    expect(kinds(events)).toEqual(["speech_start", "false_start", "speech_start", "end"]);
    expect(events[2].t).toBe(4000);
  });

  it("noisy room: a steady fan does not start a turn, speech does", () => {
    const fan = 0.012;
    const events = run((t) => (t >= 3000 && t < 5000 ? speech(t, 0.08) : fan), 15000);
    expect(kinds(events)).toEqual(["speech_start", "end"]);
    expect(events[0].t).toBe(3000);
    expect(events[1].t).toBeLessThan(8000); // ended — not stuck at maxUtteranceMs
  });

  it("customer talking immediately: speech during calibration is not lost or mistaken for noise", () => {
    const events = run((t) => (t < 2500 ? speech(t) : 0.002), 10000);
    expect(kinds(events)).toEqual(["speech_start", "end"]);
    // Detection starts right after the 0.6 s calibration (audio is recorded throughout).
    expect(events[0].t).toBeLessThanOrEqual(VAD_DEFAULTS.calibrationMs + TICK);
    expect(events[1].t).toBeLessThan(4500);
  });

  it("reuses the noise floor from the previous turn — no calibration delay", () => {
    const events = run((t) => (t >= 100 && t < 1500 ? speech(t) : 0.002), 8000, 0.002);
    expect(events[0]).toEqual({ event: "speech_start", t: 100 });
  });

  it("nobody speaks: times out after maxWaitMs", () => {
    const events = run(() => 0.002, 30000);
    expect(kinds(events)).toEqual(["timeout"]);
    expect(events[0].t).toBeGreaterThan(VAD_DEFAULTS.maxWaitMs);
  });

  it("background that suddenly rises is learned, not sent as a turn", () => {
    // Quiet start, then a louder hum between the start and sustain thresholds.
    const events = run((t) => (t < 2000 ? 0.002 : 0.008), 20000);
    expect(kinds(events)).not.toContain("end");
    expect(kinds(events)).toContain("false_start");
    // After learning the hum, a real sentence is still detected.
    const later = run(
      (t) => (t >= 1000 && t < 3000 ? speech(t, 0.08) : 0.008),
      12000,
      0.008,
    );
    expect(kinds(later)).toEqual(["speech_start", "end"]);
  });

  it("quiet speaker on a quiet mic still counts (original behaviour kept)", () => {
    const events = run((t) => (t >= 1000 && t < 3000 ? speech(t, 0.02) : 0.002), 10000);
    expect(kinds(events)).toEqual(["speech_start", "end"]);
  });

  it("caps a never-ending utterance at maxUtteranceMs", () => {
    const events = run((t) => (t >= 1000 ? 0.07 : 0.002), 30000);
    expect(kinds(events)).toEqual(["speech_start", "end"]);
    expect(events[1].t - events[0].t).toBeGreaterThanOrEqual(VAD_DEFAULTS.maxUtteranceMs);
  });
});
