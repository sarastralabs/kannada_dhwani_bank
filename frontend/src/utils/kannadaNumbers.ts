/**
 * Convert spoken Kannada number words into Arabic digits.
 *
 * Supports:
 * - Digit-by-digit (account numbers): "ಒಂದು ನಾಲ್ಕು ಸೊನ್ನೆ" → "140"
 * - Full values (amount): "ನಾಲ್ಕು ಸಾವಿರದ ಇನ್ನೂರು" → "4200"
 */

const ONES: Record<string, number> = {
  // Kannada script
  ಸೊನ್ನೆ: 0,
  ಶೂನ್ಯ: 0,
  ಜೀರೋ: 0,
  ಜಿರೋ: 0,
  ಒಂದು: 1,
  ಒನ್ನೆ: 1,
  ಒಂದ್: 1,
  ಎರಡು: 2,
  ಎರಡ್: 2,
  ಮೂರು: 3,
  ನಾಲ್ಕು: 4,
  ನಾಲಕು: 4,
  ನಾಲ್ಕ: 4,
  ಐದು: 5,
  ಆರು: 6,
  ಏಳು: 7,
  ಎಳು: 7,
  ಎಂಟು: 8,
  ಒಂಬತ್ತು: 9,
  ಒಂಭತ್ತು: 9,
  ಒಂಬತು: 9,
  ಒಂಭತು: 9,
  // Romanized / English (STT often outputs Latin instead of Kannada script)
  sonne: 0,
  shunya: 0,
  zero: 0,
  ondu: 1,
  one: 1,
  eradu: 2,
  yeradu: 2,
  two: 2,
  mooru: 3,
  muru: 3,
  three: 3,
  nalku: 4,
  naalku: 4,
  naku: 4,
  four: 4,
  aidu: 5,
  aydu: 5,
  five: 5,
  aaru: 6,
  aru: 6,
  six: 6,
  elu: 7,
  yelu: 7,
  seven: 7,
  entu: 8,
  yentu: 8,
  eight: 8,
  ombattu: 9,
  ombhattu: 9,
  nine: 9,
};

const TEENS: Record<string, number> = {
  ಹತ್ತು: 10,
  ಹತ್ತ: 10,
  ಹನ್ನೊಂದು: 11,
  ಹನ್ನೊಂದ್: 11,
  ಹನ್ನೆರಡು: 12,
  ಹದಿಮೂರು: 13,
  ಹದಿನಾಲ್ಕು: 14,
  ಹದಿನೈದು: 15,
  ಹದಿನಾರು: 16,
  ಹದಿನೇಳು: 17,
  ಹದಿನೆಂಟು: 18,
  ಹತ್ತೊಂಬತ್ತು: 19,
  ಹತ್ತೊಂಭತ್ತು: 19,
  hattu: 10,
  ten: 10,
  hannpondu: 11,
  hanneradu: 12,
};

const TENS: Record<string, number> = {
  ಇಪ್ಪತ್ತು: 20,
  ಇಪ್ಪತ್ತ: 20,
  ಇಪ್ಪತು: 20,
  ಮೂವತ್ತು: 30,
  ಮೂವತ್ತ: 30,
  ಮೂವತು: 30,
  ನಲವತ್ತು: 40,
  ನಲವತ್ತ: 40,
  ನಲವತು: 40,
  ನಾಲ್ವತ್ತು: 40,
  ಐವತ್ತು: 50,
  ಐವತ್ತ: 50,
  ಐವತು: 50,
  ಅರವತ್ತು: 60,
  ಅರವತ್ತ: 60,
  ಅರವತು: 60,
  ಎಪ್ಪತ್ತು: 70,
  ಎಪ್ಪತ್ತ: 70,
  ಎಪ್ಪತು: 70,
  ಎಂಬತ್ತು: 80,
  ಎಂಬತ್ತ: 80,
  ಎಂಬತು: 80,
  ತೊಂಬತ್ತು: 90,
  ತೊಂಬತ್ತ: 90,
  ತೊಂಬತು: 90,
  ippattu: 20,
  ippatta: 20,
  twenty: 20,
  moovattu: 30,
  muvattu: 30,
  thirty: 30,
  nalavattu: 40,
  forty: 40,
  aivattu: 50,
  fifty: 50,
  aravattu: 60,
  sixty: 60,
  eppattu: 70,
  seventy: 70,
  embattu: 80,
  eighty: 80,
  tombattu: 90,
  ninety: 90,
};

const HUNDREDS: Record<string, number> = {
  ನೂರು: 100,
  ನೂರ: 100,
  ಇನ್ನೂರು: 200,
  ಇನ್ನೂರ: 200,
  ಮುನ್ನೂರು: 300,
  ಮುನ್ನೂರ: 300,
  ನಾನೂರು: 400,
  ನಾನೂರ: 400,
  ಐನೂರು: 500,
  ಐನೂರ: 500,
  ಅರುನೂರು: 600,
  ಅರುನೂರ: 600,
  ಏಳುನೂರು: 700,
  ಏಳನೂರು: 700,
  ಎಂಟುನೂರು: 800,
  ಎಂಟನೂರು: 800,
  ಒಂಬತ್ತುನೂರು: 900,
  ಒಂಭತ್ತುನೂರು: 900,
  nooru: 100,
  nuru: 100,
  hundred: 100,
  innooru: 200,
  munnooru: 300,
  nanooru: 400,
  ainooru: 500,
};

const SCALE: Record<string, number> = {
  ಸಾವಿರ: 1000,
  ಸಾವಿರದ: 1000,
  ಸಾವಿರದು: 1000,
  ಸಾವಿರಗಳು: 1000,
  ಲಕ್ಷ: 100_000,
  ಲಕ್ಷದ: 100_000,
  saavir: 1000,
  saavira: 1000,
  savira: 1000,
  thousand: 1000,
  laksha: 100_000,
  lakh: 100_000,
};

const SKIP_TOKENS = new Set([
  "ಮತ್ತು",
  "ಆಗಿದೆ",
  "ಆಗಿ",
  "ಇನ್ನೂ",
  "ರೂ",
  "ರೂಪಾಯಿ",
  "ರುಪಾಯಿ",
  "ರೂಪಾಯಿಗಳು",
  "ಮಾತ್ರ",
  "ಅಂಕೆ",
  "ಸಂಖ್ಯೆ",
  "ದಯವಿಟ್ಟು",
  "ಆಣೆ",
  "mattu",
  "and",
  "rupees",
  "rupee",
  "rs",
  "only",
]);

function cleanToken(tok: string): string {
  return tok
    .replace(/^[\s"'“”‘’(]+/, "")
    .replace(/[\s"'“”‘’).,;:!?|/\\-]+$/g, "")
    .trim();
}

function normalizeToken(tok: string): string {
  const cleaned = cleanToken(tok);
  // Latin tokens → lowercase for romanized lookup; Kannada stays as-is
  if (/^[a-zA-Z0-9]+$/.test(cleaned)) return cleaned.toLowerCase();
  return cleaned;
}

function tokenizeKannada(text: string): string[] {
  return text
    .replace(/[.,|/\\-]+/g, " ")
    .split(/\s+/)
    .map(normalizeToken)
    .filter(Boolean);
}

function extractLiteralDigits(text: string): string {
  const kannadaDigits = "೦೧೨೩೪೫೬೭೮೯";
  let out = "";
  for (const ch of text) {
    const k = kannadaDigits.indexOf(ch);
    if (k >= 0) out += String(k);
    else if (/\d/.test(ch)) out += ch;
  }
  return out;
}

/** Match a ones-digit word; also accept if token starts with it (STT glue). */
function matchOnes(tok: string): number | null {
  if (ONES[tok] !== undefined) return ONES[tok];
  // Longest-prefix match for glued speech like "ಒಂದುನಾಲ್ಕು" handled elsewhere
  for (const [word, val] of Object.entries(ONES)) {
    if (tok === word) return val;
  }
  return null;
}

/**
 * Split a glued Kannada digit string into ones-words greedily (longest match).
 */
function splitGluedOnes(text: string): string[] | null {
  const compact = text.replace(/\s+/g, "").toLowerCase();
  // Prefer longer Kannada-script keys first, then romanized
  const words = Object.keys(ONES).sort((a, b) => b.length - a.length);
  const parts: string[] = [];
  let i = 0;
  while (i < compact.length) {
    let hit: string | null = null;
    for (const w of words) {
      if (compact.startsWith(w, i)) {
        hit = w;
        break;
      }
    }
    if (!hit) return null;
    parts.push(hit);
    i += hit.length;
  }
  return parts.length ? parts : null;
}

/**
 * Account-style: each ones-word becomes one digit, in order.
 * Unknown filler words are skipped; if no digits found, returns null.
 */
export function kannadaWordsToDigitString(text: string): string | null {
  let tokens = tokenizeKannada(text);
  if (!tokens.length) return null;

  // If whitespace tokenization failed (one big glued token), try split
  if (tokens.length === 1 && matchOnes(tokens[0]) === null) {
    const glued = splitGluedOnes(tokens[0]);
    if (glued) tokens = glued;
  }

  const digits: string[] = [];
  let unknown = 0;
  for (const tok of tokens) {
    if (SKIP_TOKENS.has(tok)) continue;
    const ones = matchOnes(tok);
    if (ones !== null) {
      digits.push(String(ones));
      continue;
    }
    // Try glued chunk inside a longer token
    const glued = splitGluedOnes(tok);
    if (glued && glued.length > 1) {
      for (const g of glued) digits.push(String(ONES[g]));
      continue;
    }
    unknown += 1;
  }

  if (!digits.length) return null;
  // If mostly unknown junk, don't trust the result
  if (unknown > digits.length) return null;
  return digits.join("");
}

export function parseKannadaNumberWords(text: string): number | null {
  const tokens = tokenizeKannada(text);
  if (!tokens.length) return null;

  let total = 0;
  let current = 0;
  let sawNumber = false;

  for (const tok of tokens) {
    if (SKIP_TOKENS.has(tok)) continue;

    if (SCALE[tok] !== undefined) {
      const scale = SCALE[tok];
      if (current === 0) current = 1;
      total += current * scale;
      current = 0;
      sawNumber = true;
      continue;
    }

    if (
      (tok === "ನೂರು" ||
        tok === "ನೂರ" ||
        tok === "nooru" ||
        tok === "nuru" ||
        tok === "hundred") &&
      current > 0 &&
      current < 10
    ) {
      current = current * 100;
      sawNumber = true;
      continue;
    }

    if (HUNDREDS[tok] !== undefined) {
      current += HUNDREDS[tok];
      sawNumber = true;
      continue;
    }

    if (TEENS[tok] !== undefined) {
      current += TEENS[tok];
      sawNumber = true;
      continue;
    }

    if (TENS[tok] !== undefined) {
      current += TENS[tok];
      sawNumber = true;
      continue;
    }

    if (ONES[tok] !== undefined) {
      current += ONES[tok];
      sawNumber = true;
      continue;
    }

    // Soft-fail: ignore one unknown token instead of aborting the whole parse
    // (STT often appends stray words). Only abort if we never saw a number.
    continue;
  }

  if (!sawNumber) return null;
  return total + current;
}

const KN_DIGIT_MAP: Record<string, string> = {
  "೦": "0", "೧": "1", "೨": "2", "೩": "3", "೪": "4", "೫": "5", "೬": "6", "೭": "7", "೮": "8", "೯": "9",
};

/** Scale of a word after a figure, or 0 when it is not one. */
function scaleOf(word: string): number {
  const w = word.toLowerCase();
  if (/^(crore|ಕೋಟಿ)/.test(w)) return 10_000_000;
  if (/^million/.test(w)) return 1_000_000;
  if (/^(lakh|lac|laksha|ಲಕ್ಷ)/.test(w)) return 100_000;
  if (/^(thousand|saav|sav|ಸಾವಿರ|ಸಾವ್ರ)/.test(w)) return 1000;
  if (/^(hundred|ನೂರ)/.test(w)) return 100;
  return 0;
}

/**
 * A figure followed by a scale word — "10 ಲಕ್ಷ" → 1000000, "2.5 lakh" → 250000,
 * "2 ಲಕ್ಷ 50 ಸಾವಿರ" → 250000 (mirrors backend/forms/extract.py `amount_with_scales`).
 */
export function amountWithScales(raw: string): string | null {
  const text = raw.replace(/[೦-೯]/g, (d) => KN_DIGIT_MAP[d]).replace(/(\d),(?=\d)/g, "$1");
  const re = /(\d+(?:\.\d+)?)\s*([A-Za-z]+|[ಀ-೿]+)/g;
  let total = 0;
  let found = false;
  let smallest = Infinity;
  let lastEnd = 0;
  for (const m of text.matchAll(re)) {
    const scale = scaleOf(m[2]);
    if (!scale) continue;
    total += parseFloat(m[1]) * scale;
    smallest = Math.min(smallest, scale);
    lastEnd = (m.index ?? 0) + m[0].length;
    found = true;
  }
  if (!found) return null;
  const tail = text.slice(lastEnd).match(/^\s*(?:and\s+|ಮತ್ತು\s+)?(\d+)\b/);
  if (tail && Number(tail[1]) < smallest) total += Number(tail[1]);
  return String(Math.round(total));
}

export function normalizeSpokenNumber(
  raw: string,
  mode: "digits" | "amount" | "date",
): string {
  const text = raw.trim();
  if (!text) return "";

  // A date the backend already parsed ("21/06/2005") must keep its separators —
  // reducing it to "21062005" made /api/forms/submit reject the whole form.
  if (mode === "date") {
    const dmy = text.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\.?$/);
    if (dmy) return `${dmy[1].padStart(2, "0")}/${dmy[2].padStart(2, "0")}/${dmy[3]}`;
  }

  if (mode === "amount") {
    const scaled = amountWithScales(text);
    if (scaled) return scaled;
  }

  const literal = extractLiteralDigits(text);
  const compactLen = text.replace(/\s/g, "").length;
  // Prefer literal digits only when they dominate the utterance
  if (literal && literal.length >= Math.max(2, Math.ceil(compactLen * 0.6))) {
    return literal;
  }

  if (mode === "digits") {
    const byDigit = kannadaWordsToDigitString(text);
    if (byDigit) return byDigit;
    const n = parseKannadaNumberWords(text);
    if (n !== null) return String(n);
    return literal || text;
  }

  // Amount: try quantity parse first, then digit-by-digit
  const n = parseKannadaNumberWords(text);
  if (n !== null) return String(n);

  const byDigit = kannadaWordsToDigitString(text);
  if (byDigit) return byDigit;

  return literal || text;
}
