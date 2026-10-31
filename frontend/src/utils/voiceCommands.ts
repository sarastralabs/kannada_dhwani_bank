/** Long Kannada vowels → short, so "ಮುಗೀಸು" matches "ಮುಗಿಸು" (STT varies vowel length). */
const KN_VOWEL_FOLD: Record<string, string> = {
  "ೀ": "ಿ",
  "ೂ": "ು",
  "ೇ": "ೆ",
  "ೋ": "ೊ",
  ಈ: "ಇ",
  ಊ: "ಉ",
  ಏ: "ಎ",
  ಓ: "ಒ",
};

/**
 * Normalize spoken text for whole-word command matching.
 * Kannada vowel signs (\p{M}) are kept — dropping them made different words look
 * alike ("ಸರಿತಾ" matched "ಸರಿ" = yes, "ಇಲ್ಲಿ" matched "ಇಲ್ಲ" = no).
 */
function norm(text: string): string {
  return text
    .toLowerCase()
    .replace(/[ೀೂೇೋಈಊಏಓ]/g, (ch) => KN_VOWEL_FOLD[ch] ?? ch)
    .replace(/[^\p{L}\p{M}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const END_PHRASES = [
  "ಮುಗಿಸು",
  "ಮುಗಿದು",
  "ಮುಗಿಸಿ",
  "ಮುಗಿಯಿತು",
  "ನಿಲ್ಲಿಸು",
  "ನಿಲ್ಲಿಸಿ",
  "bye",
  "goodbye",
  "good bye",
  "stop",
  "end",
  "finish",
  "thank you bye",
];

// Whole words only — list the forms customers actually say.
const AFFIRM_PHRASES = [
  "ಸರಿ",
  "ಸರಿಯೇ",
  "ಸರಿಯಾಗಿದೆ",
  "ಸರಿಯಾಗಿ ಇದೆ",
  "ಸರಿಯಿದೆ",
  "ಸರಿ ಇದೆ",
  "ಹೌದು",
  "ಹೌದ್",
  "ಹೌದಪ್ಪ",
  "ಓಕೆ",
  "ಓಕೇ",
  "ಒಪ್ಪಿದೆ",
  "ದೃಢೀಕರಿಸಿ",
  "yes",
  "yeah",
  "yep",
  "ok",
  "okay",
  "correct",
  "confirm",
  "right",
];

const REJECT_PHRASES = [
  "ಮತ್ತೆ",
  "ಮರುಹೇಳಿ",
  "ತಪ್ಪು",
  "ತಪ್ಪಾಗಿದೆ",
  "ಇಲ್ಲ",
  "ಅಲ್ಲ",
  "no",
  "wrong",
  "again",
  "re record",
  "rerecord",
  "repeat",
];

const SKIP_PHRASES = [
  "ಬಿಟ್ಟುಬಿಡಿ",
  "ಬಿಟ್ಟುಬಿಡು",
  "skip",
  "none",
  "n a",
  "leave it",
  "no need",
];

function includesPhrase(haystack: string, phrase: string): boolean {
  const p = norm(phrase);
  if (!p) return false;
  const escaped = p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?:^|\\s)${escaped}(?:\\s|$)`, "u").test(haystack);
}

function includesAny(haystack: string, phrases: string[]): boolean {
  return phrases.some((p) => includesPhrase(haystack, p));
}

export function isEndSessionCommand(...parts: string[]): boolean {
  const t = norm(parts.filter(Boolean).join(" "));
  if (!t) return false;
  return includesAny(t, END_PHRASES);
}

export function isAffirmCommand(...parts: string[]): boolean {
  const t = norm(parts.filter(Boolean).join(" "));
  if (!t) return false;
  return includesAny(t, AFFIRM_PHRASES);
}

export function isRejectCommand(...parts: string[]): boolean {
  const t = norm(parts.filter(Boolean).join(" "));
  if (!t) return false;
  return includesAny(t, REJECT_PHRASES);
}

export function isSkipCommand(...parts: string[]): boolean {
  const t = norm(parts.filter(Boolean).join(" "));
  if (!t) return false;
  return includesAny(t, SKIP_PHRASES);
}
