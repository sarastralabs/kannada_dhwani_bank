/**
 * Echo guard: on a kiosk the microphone can pick up the assistant's own voice, which then
 * gets treated as a new customer request ("For related questions, please visit your nearest
 * branch…" answered with yet another reply). Compare what was heard with what was just spoken.
 */

function bigrams(text: string): Set<string> {
  const letters = text.normalize("NFC").replace(/[^\p{L}\p{M}\p{N}]+/gu, "");
  const out = new Set<string>();
  for (let i = 0; i < letters.length - 1; i++) out.add(letters.slice(i, i + 2));
  return out;
}

/** True when `heard` is mostly made of text the assistant just said (long enough to be sure). */
export function isEcho(heard: string | null | undefined, spoken: readonly string[], minLetters = 18, threshold = 0.7): boolean {
  if (!heard) return false;
  const h = bigrams(heard);
  if (h.size < minLetters) return false; // short phrases ("ಹೌದು", names) are never treated as echo
  for (const line of spoken) {
    const s = bigrams(line);
    let shared = 0;
    for (const g of h) if (s.has(g)) shared++;
    if (shared / h.size >= threshold) return true;
  }
  return false;
}
