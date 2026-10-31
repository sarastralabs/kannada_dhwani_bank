/** Mask account number for on-screen display. */
export function maskAccountDisplay(raw: string): string {
  const digits = (raw || "").replace(/\D/g, "");
  if (digits.length <= 4) return digits || "—";
  return "•".repeat(digits.length - 4) + digits.slice(-4);
}

/** Format field value for customer-facing display (not debug). */
export function displayFieldValue(
  fieldId: string,
  fieldType: string,
  value: string,
): string {
  const v = (value || "").trim();
  if (!v) return "—";
  if (
    fieldType === "digits" ||
    fieldId.includes("account") ||
    fieldId === "mobile_number" ||
    fieldId === "old_mobile" ||
    fieldId === "new_mobile"
  ) {
    if (v.replace(/\D/g, "").length >= 8) {
      return maskAccountDisplay(v);
    }
  }
  if (fieldType === "amount" || fieldId.includes("amount") || fieldId === "income") {
    const n = parseFloat(v.replace(/[^\d.]/g, ""));
    if (!Number.isNaN(n)) return `₹ ${n.toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;
  }
  return v;
}

/** Kannada wording for fixed English choices (mirrors backend/forms/summary_kn.py). */
const CHOICE_KN: Record<string, string> = {
  savings: "ಉಳಿತಾಯ ಖಾತೆ",
  "savings account": "ಉಳಿತಾಯ ಖಾತೆ",
  current: "ಚಾಲ್ತಿ ಖಾತೆ",
  "current account": "ಚಾಲ್ತಿ ಖಾತೆ",
  salary: "ವೇತನ ಖಾತೆ",
  "fixed deposit": "ಸ್ಥಿರ ಠೇವಣಿ",
  "home loan": "ಗೃಹ ಸಾಲ",
  "personal loan": "ವೈಯಕ್ತಿಕ ಸಾಲ",
  "education loan": "ಶಿಕ್ಷಣ ಸಾಲ",
  "car loan": "ವಾಹನ ಸಾಲ",
  "gold loan": "ಚಿನ್ನದ ಸಾಲ",
  cash: "ನಗದು",
  cheque: "ಚೆಕ್",
  "demand draft": "ಡಿಮ್ಯಾಂಡ್ ಡ್ರಾಫ್ಟ್",
  "atm / debit card": "ಎಟಿಎಂ / ಡೆಬಿಟ್ ಕಾರ್ಡ್",
  "credit card": "ಕ್ರೆಡಿಟ್ ಕಾರ್ಡ್",
  monthly: "ಮಾಸಿಕ",
  quarterly: "ತ್ರೈಮಾಸಿಕ",
  "on maturity": "ಅವಧಿ ಪೂರ್ಣಗೊಂಡಾಗ",
  "cumulative / on maturity": "ಸಂಚಿತವಾಗಿ / ಅವಧಿ ಪೂರ್ಣಗೊಂಡಾಗ",
  "1 year": "ಒಂದು ವರ್ಷ",
  "2 years": "ಎರಡು ವರ್ಷ",
  "3 years": "ಮೂರು ವರ್ಷ",
  "5 years": "ಐದು ವರ್ಷ",
  "6 months": "ಆರು ತಿಂಗಳು",
  "12 months": "ಹನ್ನೆರಡು ತಿಂಗಳು",
};

const KANNADA_LETTERS = /[ಀ-೿]/;

/**
 * What the customer sees for a filled field — in Kannada letters.
 * Numbers, amounts and dates stay as figures. Names / addresses use the Kannada the
 * customer spoke (the saved value stays in English letters for the bank).
 */
export function kannadaDisplayValue(
  fieldId: string,
  fieldType: string,
  value: string,
  spokenKn?: string,
): string {
  const v = (value || "").trim();
  if (!v) return "—";
  if (fieldType === "digits" || fieldType === "amount" || fieldType === "date") {
    return displayFieldValue(fieldId, fieldType, v);
  }
  if (KANNADA_LETTERS.test(v)) return v;
  const choice = CHOICE_KN[v.toLowerCase()];
  if (choice) return choice;
  // Codes (IFSC "SBIN0001234", PAN "ABCDE1234F") are shown as parsed, not as heard.
  if (/\d/.test(v) && !/\s/.test(v)) return v;
  const kn = (spokenKn || "").replace(/�/g, "").trim();
  if (kn && KANNADA_LETTERS.test(kn)) return kn;
  return displayFieldValue(fieldId, fieldType, v);
}

const SMALL_KN = [
  "ಸೊನ್ನೆ", "ಒಂದು", "ಎರಡು", "ಮೂರು", "ನಾಲ್ಕು", "ಐದು", "ಆರು", "ಏಳು", "ಎಂಟು", "ಒಂಬತ್ತು",
  "ಹತ್ತು", "ಹನ್ನೊಂದು", "ಹನ್ನೆರಡು", "ಹದಿಮೂರು", "ಹದಿನಾಲ್ಕು", "ಹದಿನೈದು", "ಹದಿನಾರು", "ಹದಿನೇಳು",
  "ಹದಿನೆಂಟು", "ಹತ್ತೊಂಬತ್ತು",
];
const TENS_KN: Record<number, [string, string]> = {
  2: ["ಇಪ್ಪತ್ತು", "ಇಪ್ಪತ್ತ"],
  3: ["ಮೂವತ್ತು", "ಮೂವತ್ತ"],
  4: ["ನಲವತ್ತು", "ನಲವತ್ತ"],
  5: ["ಐವತ್ತು", "ಐವತ್ತ"],
  6: ["ಅರವತ್ತು", "ಅರವತ್ತ"],
  7: ["ಎಪ್ಪತ್ತು", "ಎಪ್ಪತ್ತ"],
  8: ["ಎಂಬತ್ತು", "ಎಂಬತ್ತ"],
  9: ["ತೊಂಬತ್ತು", "ತೊಂಬತ್ತ"],
};
const ONES_SUFFIX_KN = ["", "ೊಂದು", "ೆರಡು", "ಮೂರು", "ನಾಲ್ಕು", "ೈದು", "ಾರು", "ೇಳು", "ೆಂಟು", "ೊಂಬತ್ತು"];

/** Kannada number words up to 99,999 (mirrors backend/forms/summary_kn.py `_int_kn`). */
function intKn(n: number): string {
  if (n <= 0) return SMALL_KN[0];
  if (n < 20) return SMALL_KN[n];
  if (n < 100) {
    const [full, stem] = TENS_KN[Math.floor(n / 10)];
    return n % 10 === 0 ? full : stem + ONES_SUFFIX_KN[n % 10];
  }
  if (n < 1000) {
    const rest = n % 100;
    const base = n < 200 ? "ನೂರು" : `${intKn(Math.floor(n / 100))} ನೂರು`;
    return rest === 0 ? base : `${base.slice(0, -1)} ${intKn(rest)}`;
  }
  if (n < 100000) {
    const rest = n % 1000;
    const base = `${intKn(Math.floor(n / 1000))} ಸಾವಿರ`;
    return rest === 0 ? base : `${base} ${intKn(rest)}`;
  }
  return String(n);
}

/** "5000" → "ಐದು ಸಾವಿರ ರೂಪಾಯಿ" — for reading an amount back (TTS misreads bare figures). */
export function amountSpeakKn(value: string): string {
  const amount = parseFloat((value || "").replace(/[^\d.]/g, ""));
  if (Number.isNaN(amount)) return (value || "").trim();
  const whole = Math.floor(amount);
  if (whole >= 10000000) return `${whole} ರೂಪಾಯಿ`;
  if (whole >= 100000) {
    const lakhs = Math.floor(whole / 100000);
    const rest = whole % 100000;
    return rest === 0
      ? `${intKn(lakhs)} ಲಕ್ಷ ರೂಪಾಯಿ`
      : `${intKn(lakhs)} ಲಕ್ಷ ${intKn(rest)} ರೂಪಾಯಿ`;
  }
  return `${intKn(whole)} ರೂಪಾಯಿ`;
}
