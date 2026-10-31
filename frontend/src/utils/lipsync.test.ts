import { describe, expect, it } from "vitest";
import { levelToFrame, smoothLevel, wavEnvelope } from "./lipsync";

/** A mono PCM16 WAV: 0.2 s of silence, 0.2 s loud tone, 0.2 s silence. */
function wavBase64(): string {
  const rate = 8000;
  const samples = new Int16Array(rate * 0.6);
  for (let i = Math.floor(rate * 0.2); i < Math.floor(rate * 0.4); i++) {
    samples[i] = Math.round(Math.sin(i / 6) * 20000);
  }
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);
  const text = (o: number, s: string) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  text(0, "RIFF");
  v.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, rate, true);
  v.setUint32(28, rate * 2, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  text(36, "data");
  v.setUint32(40, samples.length * 2, true);
  new Int16Array(buf, 44).set(samples);
  let bin = "";
  new Uint8Array(buf).forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}

describe("lip-sync", () => {
  it("finds loud and quiet parts of a WAV", () => {
    const env = wavEnvelope(wavBase64())!;
    expect(env).not.toBeNull();
    expect(env.hop).toBe(0.04);
    const at = (s: number) => env.levels[Math.floor(s / env.hop)];
    expect(at(0.1)).toBeLessThan(0.05); // silence
    expect(at(0.3)).toBeGreaterThan(0.8); // tone
    expect(at(0.5)).toBeLessThan(0.05); // silence again
  });

  it("returns null for data that is not a WAV", () => {
    expect(wavEnvelope(btoa("not a wav file at all, just text........................"))).toBeNull();
    expect(wavEnvelope("")).toBeNull();
  });

  it("maps level to the four mouth shapes", () => {
    expect([0, 0.2, 0.5, 0.9].map(levelToFrame)).toEqual([0, 1, 2, 3]);
  });

  it("opens fast and closes slowly", () => {
    expect(smoothLevel(0, 1)).toBe(1);
    const closing = smoothLevel(1, 0);
    expect(closing).toBeGreaterThan(0.5);
    expect(closing).toBeLessThan(1);
  });
});
