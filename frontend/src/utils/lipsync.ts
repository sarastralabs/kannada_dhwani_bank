/**
 * Lip-sync: turn the audio that is playing into a mouth shape.
 *
 * The voice arrives as a base64 WAV, so its loudness over time is computed directly from the
 * samples (no AudioContext graph needed — works the same in every browser, even before the
 * page has been tapped). While the audio plays, the player publishes a smoothed level
 * (0..1); the mascot listens and picks one of four mouth frames.
 */

export interface Envelope {
  /** Seconds covered by each entry of `levels`. */
  hop: number;
  /** Loudness per hop, normalised so ordinary speech peaks near 1. */
  levels: Float32Array;
}

/** Closed, small, medium, wide. */
export const MOUTH_FRAMES = 4;

export function levelToFrame(level: number): number {
  if (level < 0.12) return 0;
  if (level < 0.34) return 1;
  if (level < 0.64) return 2;
  return 3;
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** Loudness envelope of a PCM16 / float32 WAV, or null if it cannot be read. */
export function wavEnvelope(b64: string, hop = 0.04): Envelope | null {
  try {
    const bytes = base64ToBytes(b64);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    if (bytes.length < 44 || view.getUint32(0, false) !== 0x52494646 /* RIFF */) return null;

    let format = 1;
    let channels = 1;
    let rate = 0;
    let bits = 16;
    let dataStart = -1;
    let dataLen = 0;
    for (let pos = 12; pos + 8 <= bytes.length; ) {
      const id = view.getUint32(pos, false);
      const size = view.getUint32(pos + 4, true);
      if (id === 0x666d7420 /* "fmt " */) {
        format = view.getUint16(pos + 8, true);
        channels = view.getUint16(pos + 10, true);
        rate = view.getUint32(pos + 12, true);
        bits = view.getUint16(pos + 22, true);
      } else if (id === 0x64617461 /* "data" */) {
        dataStart = pos + 8;
        dataLen = Math.min(size, bytes.length - dataStart);
        break;
      }
      pos += 8 + size + (size % 2);
    }
    if (dataStart < 0 || rate <= 0 || channels < 1) return null;
    const isFloat = format === 3 && bits === 32;
    if (!isFloat && !(format === 1 && bits === 16)) return null;

    const bytesPerSample = bits / 8;
    const frames = Math.floor(dataLen / (bytesPerSample * channels));
    const win = Math.max(1, Math.round(rate * hop));
    const count = Math.ceil(frames / win);
    const rms = new Float32Array(count);
    for (let w = 0; w < count; w++) {
      const from = w * win;
      const to = Math.min(frames, from + win);
      let sum = 0;
      for (let f = from; f < to; f++) {
        const at = dataStart + f * channels * bytesPerSample; // first channel is enough
        const v = isFloat ? view.getFloat32(at, true) : view.getInt16(at, true) / 32768;
        sum += v * v;
      }
      rms[w] = Math.sqrt(sum / Math.max(1, to - from));
    }
    // Normalise by a high percentile so quiet and loud voices both move the mouth fully.
    const sorted = Array.from(rms).sort((a, b) => a - b);
    const ref = sorted[Math.floor(sorted.length * 0.95)] || sorted[sorted.length - 1] || 1;
    const levels = new Float32Array(count);
    for (let i = 0; i < count; i++) levels[i] = ref > 1e-4 ? Math.min(1, Math.sqrt(rms[i] / ref)) : 0;
    return { hop, levels };
  } catch {
    return null;
  }
}

/** Fast attack, slow release — a mouth snaps open but relaxes smoothly. */
export function smoothLevel(previous: number, raw: number, release = 0.72): number {
  return Math.max(raw, previous * release);
}

// ── Tiny publish/subscribe channel: audio player → mascot ────────────────

type Listener = (level: number) => void;
const listeners = new Set<Listener>();
let lastPublishAt = 0;

export function onMouthLevel(fn: Listener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function publishMouthLevel(level: number): void {
  lastPublishAt = typeof performance !== "undefined" ? performance.now() : Date.now();
  listeners.forEach((fn) => fn(level));
}

/** True while real audio is driving the mouth (otherwise the mascot falls back to a talking loop). */
export function mouthRecentlyDriven(maxAgeMs = 400): boolean {
  const now = typeof performance !== "undefined" ? performance.now() : Date.now();
  return now - lastPublishAt < maxAgeMs;
}
