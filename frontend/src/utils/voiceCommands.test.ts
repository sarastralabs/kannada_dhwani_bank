import { describe, expect, it } from "vitest";
import { isAffirmCommand, isEndSessionCommand, isRejectCommand, isSkipCommand } from "./voiceCommands";

describe("voice commands — Kannada", () => {
  it.each(["ಹೌದು", "ಹೌದು.", "ಸರಿ", "ಸರಿಯಾಗಿದೆ.", "ಸರಿಯಿದೆ", "ಓಕೆ ಸರ್", "Yes.", "It's Right."])(
    "%s is yes",
    (text) => {
      expect(isAffirmCommand(text)).toBe(true);
    },
  );

  it.each(["ಇಲ್ಲ", "ತಪ್ಪು", "ಮತ್ತೆ ಹೇಳಿ", "ತಪ್ಪಾಗಿದೆ", "No.", "wrong"])("%s is no", (text) => {
    expect(isRejectCommand(text)).toBe(true);
  });

  it.each(["ಮುಗಿಸು", "ಮುಗಿಸಿ", "ಮುಗೀಸು", "ನಿಲ್ಲಿಸಿ", "Finish"])("%s ends the session", (text) => {
    expect(isEndSessionCommand(text)).toBe(true);
  });

  it("skip still works", () => {
    expect(isSkipCommand("ಬಿಟ್ಟುಬಿಡಿ")).toBe(true);
  });

  // Names, places and numbers spoken as a correction must not be read as yes / no.
  // These all matched before, because vowel signs were stripped before comparing.
  it.each(["ಸರಿತಾ", "ಸರಸ್ವತಿ", "ಅಶ್ವಿನ್", "ಬಂಟ್ವಾಳ", "ಇಪ್ಪತ್ತೊಂದು ಆರು"])("%s is not yes", (text) => {
    expect(isAffirmCommand(text)).toBe(false);
  });

  it.each(["ಇಲ್ಲಿ ಬನ್ನಿ", "ಮತ್ತೂರು", "ಅಶ್ವಿನ್", "ಬಂಟ್ವಾಳ"])("%s is not no", (text) => {
    expect(isRejectCommand(text)).toBe(false);
  });
});
