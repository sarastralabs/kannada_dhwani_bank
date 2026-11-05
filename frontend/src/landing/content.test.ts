import { describe, expect, it } from "vitest";
import * as C from "./content";
import { kannadaDigits, rateLabel } from "./content";

/** Every string anywhere inside the exported content. */
function strings(value: unknown, out: string[] = []): string[] {
  if (typeof value === "string") out.push(value);
  else if (Array.isArray(value)) value.forEach((v) => strings(v, out));
  else if (value && typeof value === "object") Object.values(value).forEach((v) => strings(v, out));
  return out;
}

const KANNADA = /[\u0C80-\u0CFF]/;
// Words that are allowed to stay in English: the company name, and icon characters have no letters at all.
const ALLOWED_LATIN = /Sarastra Labs/;

describe("landing content is Kannada", () => {
  const all = strings(Object.fromEntries(Object.entries(C).filter(([, v]) => typeof v !== "function")));

  it("has real content", () => {
    expect(all.length).toBeGreaterThan(80);
  });

  it("has no English left in any visible sentence", () => {
    const offenders = all.filter((s) => {
      const letters = s.replace(ALLOWED_LATIN, "").replace(/[^A-Za-z]/g, "");
      return letters.length > 0 && !/^(mascot|listening|thinking|speaking|happy|greeting|savings_account|fixed_deposit_\dyr|home_loan|personal_loan|education_loan|car_loan|services|how|rates|faq)$/.test(s) && !/^(savings|fixed|home|personal|education|car)/.test(s) && !/^[a-z_0-9]+$/.test(s);
    });
    expect(offenders).toEqual([]);
  });

  it("every card, step, question and answer is written in Kannada", () => {
    for (const s of [
      ...C.SERVICES.cards.flatMap((c) => [c.title, c.say, c.note]),
      ...C.HOW.steps.flatMap((s) => [s.title, s.text]),
      ...C.JOURNEY.steps.flatMap((s) => [s.title, s.text]),
      ...C.SAFETY.items.flatMap((s) => [s.title, s.text]),
      ...C.FAQ.items.flatMap((f) => [f.q, f.a]),
      ...C.RATES.groups.flatMap((g) => [g.title, ...g.rows.map((r) => r.label)]),
    ]) {
      expect(KANNADA.test(s), s).toBe(true);
    }
  });

  it("covers every rate the backend sends", () => {
    const keys = C.RATES.groups.flatMap((g) => g.rows.map((r) => r.key));
    expect(keys.sort()).toEqual(
      ["car_loan", "education_loan", "fixed_deposit_1yr", "fixed_deposit_3yr", "fixed_deposit_5yr", "home_loan", "personal_loan", "savings_account"].sort(),
    );
  });
});

describe("Kannada numbers", () => {
  it("turns digits into Kannada digits", () => {
    expect(kannadaDigits(2026)).toBe("೨೦೨೬");
    expect(kannadaDigits("3.5")).toBe("೩.೫");
  });

  it("writes a rate the way people say it", () => {
    expect(rateLabel(3.5)).toBe("ಶೇ. ೩.೫");
    expect(rateLabel(11)).toBe("ಶೇ. ೧೧");
    expect(rateLabel(7.25)).toBe("ಶೇ. ೭.೨೫");
  });
});
