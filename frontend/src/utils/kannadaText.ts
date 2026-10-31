/**
 * Rough Kannada → English (Latin) transliteration for form fields like names.
 * Not linguistic ISO-perfect — good enough for printable bank-style forms.
 */

const VOWEL_SIGNS: Record<string, string> = {
  "ಾ": "a",
  "ಿ": "i",
  "ೀ": "i",
  "ು": "u",
  "ೂ": "u",
  "ೃ": "ru",
  "ೆ": "e",
  "ೇ": "e",
  "ೈ": "ai",
  "ೊ": "o",
  "ೋ": "o",
  "ೌ": "au",
};

const INDEPENDENT_VOWELS: Record<string, string> = {
  ಅ: "a",
  ಆ: "aa",
  ಇ: "i",
  ಈ: "i",
  ಉ: "u",
  ಊ: "u",
  ಋ: "ru",
  ಎ: "e",
  ಏ: "e",
  ಐ: "ai",
  ಒ: "o",
  ಓ: "o",
  ಔ: "au",
};

const CONSONANTS: Record<string, string> = {
  ಕ: "k",
  ಖ: "kh",
  ಗ: "g",
  ಘ: "gh",
  ಙ: "ng",
  ಚ: "ch",
  ಛ: "chh",
  ಜ: "j",
  ಝ: "jh",
  ಞ: "ny",
  ಟ: "t",
  ಠ: "th",
  ಡ: "d",
  ಢ: "dh",
  ಣ: "n",
  ತ: "t",
  ಥ: "th",
  ದ: "d",
  ಧ: "dh",
  ನ: "n",
  ಪ: "p",
  ಫ: "ph",
  ಬ: "b",
  ಭ: "bh",
  ಮ: "m",
  ಯ: "y",
  ರ: "r",
  ಱ: "r",
  ಲ: "l",
  ವ: "v",
  ಶ: "sh",
  ಷ: "sh",
  ಸ: "s",
  ಹ: "h",
  ಳ: "l",
  ಝ಼: "zh",
  ಕ್ಷ: "ksh",
  ಜ್ಞ: "gy",
};

const VIRAMA = "್";
/** ಂ is "m" before these (ಸಂಪತ್ → Sampat) and "n" elsewhere (ಬಂಟ್ವಾಳ → Bantwala). */
const LABIALS = new Set(["ಪ", "ಫ", "ಬ", "ಭ", "ಮ"]);
const ANUSVARA = "ಂ";
const VISARGA = "ಃ";

function hasKannada(text: string): boolean {
  return /[\u0C80-\u0CFF]/.test(text);
}

/**
 * Transliterate Kannada script to Latin. Leaves already-Latin text unchanged.
 */
export function transliterateKannadaToEnglish(raw: string): string {
  const text = raw.trim();
  if (!text) return "";
  if (!hasKannada(text)) return text;

  let out = "";
  let i = 0;
  const chars = [...text];

  while (i < chars.length) {
    const ch = chars[i];

    if (/\s/.test(ch)) {
      out += " ";
      i += 1;
      continue;
    }

    if (INDEPENDENT_VOWELS[ch]) {
      out += INDEPENDENT_VOWELS[ch];
      i += 1;
      continue;
    }

    if (CONSONANTS[ch]) {
      let base = CONSONANTS[ch];
      i += 1;
      // Consonant cluster with virama
      while (i < chars.length && chars[i] === VIRAMA && i + 1 < chars.length && CONSONANTS[chars[i + 1]]) {
        // ವ joined to a consonant sounds "w" (ಅಶ್ವಿನ್ → Ashwin, ಸ್ವಾಮಿ → Swami).
        base += chars[i + 1] === "ವ" ? "w" : CONSONANTS[chars[i + 1]];
        i += 2;
      }
      if (i < chars.length && chars[i] === VIRAMA) {
        // Final virama — no inherent vowel
        out += base;
        i += 1;
      } else if (i < chars.length && VOWEL_SIGNS[chars[i]]) {
        out += base + VOWEL_SIGNS[chars[i]];
        i += 1;
      } else {
        out += base + "a";
      }
      continue;
    }

    if (ch === ANUSVARA) {
      out += LABIALS.has(chars[i + 1] ?? "") ? "m" : "n";
      i += 1;
      continue;
    }
    if (ch === VISARGA) {
      out += "h";
      i += 1;
      continue;
    }

    // Pass through Latin / digits / punctuation
    out += ch;
    i += 1;
  }

  // Title-case words for form look: "nishaan" → "Nishaan"
  return out
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

/** Map common deposit-mode answers to English. */
export function normalizeDepositMode(raw: string): string {
  const t = raw.trim().toLowerCase().replace(/\s+/g, "");
  if (!t) return raw.trim();
  if (t.includes("ನಗದು") || t.includes("cash") || t.includes("nagadu")) return "Cash";
  if (t.includes("ಚೆಕ್") || t.includes("ಚೆಕ್ಕು") || t.includes("cheque") || t.includes("check")) {
    return "Cheque";
  }
  if (hasKannada(raw)) return transliterateKannadaToEnglish(raw);
  return raw.trim();
}
