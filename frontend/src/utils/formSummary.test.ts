import { describe, expect, it } from "vitest";
import { amountSpeakKn, kannadaDisplayValue } from "./formSummary";
import { formatDuration, sessionSeconds } from "./sessionTime";
import { normalizeSpokenNumber } from "./kannadaNumbers";

describe("details shown in Kannada", () => {
  it("names use what the customer said", () => {
    expect(kannadaDisplayValue("full_name", "text", "Ashwin", "ಅಶ್ವಿನ್")).toBe("ಅಶ್ವಿನ್");
  });
  it("fixed choices are translated", () => {
    expect(kannadaDisplayValue("account_type", "text", "Savings", "")).toBe("ಉಳಿತಾಯ ಖಾತೆ");
  });
  it("free text falls back to the Kannada heard", () => {
    expect(kannadaDisplayValue("purpose", "text", "Personal use", "ವೈಯಕ್ತಿಕ ಬಳಕೆ")).toBe("ವೈಯಕ್ತಿಕ ಬಳಕೆ");
  });
  it("numbers stay as figures", () => {
    expect(kannadaDisplayValue("amount", "amount", "5000", "ಐದು ಸಾವಿರ")).toBe("₹ 5,000");
    expect(kannadaDisplayValue("mobile_number", "digits", "9876543210")).toBe("••••••3210");
  });
  it("codes stay as parsed, not as heard", () => {
    expect(kannadaDisplayValue("beneficiary_ifsc", "text", "SBIN0001234", "ಎಸ್ ಬಿ ಐ ಎನ್ ಸೊನ್ನೆ")).toBe("SBIN0001234");
    expect(kannadaDisplayValue("pan", "text", "ABCDE1234F", "ಎ ಬಿ ಸಿ")).toBe("ABCDE1234F");
  });
  it("an address with a house number still shows the Kannada said", () => {
    expect(kannadaDisplayValue("address", "text", "Mane Sankhye 12", "ಮನೆ ಸಂಖ್ಯೆ ೧೨")).toBe("ಮನೆ ಸಂಖ್ಯೆ ೧೨");
  });
  it("empty is a dash", () => {
    expect(kannadaDisplayValue("purpose", "text", "")).toBe("—");
  });
});

describe("session time", () => {
  it("formats minutes and seconds", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(75)).toBe("1:15");
    expect(formatDuration(185)).toBe("3:05");
  });
  it("measures a finished and an open session", () => {
    const started_at = "2026-10-12T10:00:00Z";
    expect(sessionSeconds({ started_at, ended_at: "2026-10-12T10:03:20Z" })).toBe(200);
    expect(sessionSeconds({ started_at, ended_at: null }, Date.parse("2026-10-12T10:01:00Z"))).toBe(60);
  });
});

describe("amounts read back in Kannada", () => {
  it.each([
    ["5000", "ಐದು ಸಾವಿರ ರೂಪಾಯಿ"],
    ["250", "ಎರಡು ನೂರ ಐವತ್ತು ರೂಪಾಯಿ"],
    ["12500", "ಹನ್ನೆರಡು ಸಾವಿರ ಐದು ನೂರು ರೂಪಾಯಿ"],
    ["150000", "ಒಂದು ಲಕ್ಷ ಐವತ್ತು ಸಾವಿರ ರೂಪಾಯಿ"],
    ["45", "ನಲವತ್ತೈದು ರೂಪಾಯಿ"],
  ])("%s → %s", (value, words) => {
    expect(amountSpeakKn(value)).toBe(words);
  });
});

describe("amounts with lakh / thousand after a figure", () => {
  it.each([
    ["10 ಲಕ್ಷ.", "1000000"],
    ["10 ಲಕ್ಷ", "1000000"],
    ["2.5 ಲಕ್ಷ", "250000"],
    ["2 ಲಕ್ಷ 50 ಸಾವಿರ", "250000"],
    ["3 ಲಕ್ಷ 500", "300500"],
    ["5 ಸಾವಿರ", "5000"],
    ["10 lakh", "1000000"],
    ["1 ಕೋಟಿ", "10000000"],
    ["೧೦ ಲಕ್ಷ", "1000000"],
    ["ಹತ್ತು ಲಕ್ಷ", "1000000"],
    ["50,000", "50000"],
    ["1000000", "1000000"],
  ])("%s → %s", (spoken, value) => {
    expect(normalizeSpokenNumber(spoken, "amount")).toBe(value);
  });
});
