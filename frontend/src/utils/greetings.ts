export type GreetSlot = "morning" | "afternoon" | "evening" | "night";

export interface GreetLine {
  line_kn: string;
  line_en: string;
}

export interface Greeting {
  slot: GreetSlot;
  title_kn: string;
  title_en: string;
  line_kn: string;
  line_en: string;
  hours: string;
  variant?: number;
  variant_count?: number;
  alt_titles_kn?: string[];
}

export interface GreetingCatalogSlot {
  slot: GreetSlot;
  title_kn: string;
  title_en: string;
  hours: string;
  alt_titles_kn: string[];
  lines: GreetLine[];
  variant_count: number;
}

import { getApiBase } from "./apiBase";

const API_BASE = getApiBase();

/** Local system clock → greeting slot (customer lobby). */
export function slotForHour(hour: number): GreetSlot {
  if (hour >= 5 && hour <= 11) return "morning";
  if (hour >= 12 && hour <= 15) return "afternoon";
  if (hour >= 16 && hour <= 19) return "evening";
  return "night";
}

/** Fetch catalog + one random line for current hour from API. */
export async function fetchGreetingPick(hour = new Date().getHours()): Promise<Greeting> {
  const res = await fetch(`${API_BASE}/api/kiosk/greetings?hour=${hour}&random=true`);
  if (!res.ok) throw new Error("Failed to load greetings");
  const data = await res.json();
  return data.current as Greeting;
}

/** Pick random line client-side when catalog already loaded. */
export function pickRandomFromCatalog(
  catalog: GreetingCatalogSlot[],
  hour = new Date().getHours(),
): Greeting {
  const slot = slotForHour(hour);
  const entry = catalog.find((g) => g.slot === slot) ?? catalog[0];
  if (!entry?.lines?.length) {
    return {
      slot,
      title_kn: entry?.title_kn ?? "ನಮಸ್ಕಾರ",
      title_en: entry?.title_en ?? "Namaskara",
      hours: entry?.hours ?? "",
      line_kn: "ನಮಸ್ಕಾರ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
      line_en: "Namaskara. How may I help you?",
    };
  }
  const variant = Math.floor(Math.random() * entry.lines.length);
  const line = entry.lines[variant];
  return {
    slot,
    title_kn: entry.title_kn,
    title_en: entry.title_en,
    hours: entry.hours,
    alt_titles_kn: entry.alt_titles_kn,
    variant,
    variant_count: entry.variant_count,
    line_kn: line.line_kn,
    line_en: line.line_en,
  };
}

/** Fallback when API offline — minimal single line per slot. */
export function greetingForNowFallback(date = new Date()): Greeting {
  const slot = slotForHour(date.getHours());
  const fallbacks: Record<GreetSlot, Greeting> = {
    morning: {
      slot: "morning",
      title_kn: "ಶುಭೋದಯ",
      title_en: "Good morning",
      hours: "05:00–11:59",
      line_kn:
        "ಶುಭೋದಯ. ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್ ಸೇವೆಗೆ ಸುಸ್ವಾಗತ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
      line_en: "Good morning. Welcome. How may I help you?",
    },
    afternoon: {
      slot: "afternoon",
      title_kn: "ಶುಭ ಮಧ್ಯಾಹ್ನ",
      title_en: "Good afternoon",
      hours: "12:00–15:59",
      line_kn:
        "ಶುಭ ಮಧ್ಯಾಹ್ನ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
      line_en: "Good afternoon. How may I help you?",
    },
    evening: {
      slot: "evening",
      title_kn: "ಶುಭ ಸಂಜೆ",
      title_en: "Good evening",
      hours: "16:00–19:59",
      line_kn: "ಶುಭ ಸಂಜೆ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
      line_en: "Good evening. How may I help you?",
    },
    night: {
      slot: "night",
      title_kn: "ನಮಸ್ಕಾರ",
      title_en: "Namaskara",
      hours: "20:00–04:59",
      line_kn: "ನಮಸ್ಕಾರ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
      line_en: "Namaskara. How may I help you?",
    },
  };
  return fallbacks[slot];
}
