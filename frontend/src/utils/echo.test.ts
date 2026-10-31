import { describe, expect, it } from "vitest";
import { isEcho } from "./echo";

const SPOKEN = [
  "ಖಾತೆ ಸಂಬಂಧಿತ ಪ್ರಶ್ನೆಗಳಿಗಾಗಿ ದಯವಿಟ್ಟು ಮಾನ್ಯವಾದ ಫೋಟೋ ಗುರುತಿನ ದಾಖಲೆಯೊಂದಿಗೆ ನಿಮ್ಮ ಹತ್ತಿರದ ಶಾಖೆಗೆ ಭೇಟಿ ನೀಡಿ",
];

describe("echo guard", () => {
  it("catches the assistant's own reply heard back, even truncated or slightly mis-heard", () => {
    expect(isEcho("ಆತೆ ಸಂಬಂಧಿತ ಪ್ರಶ್ನೆಗಳಿಗಾಗಿ ದಯವಿಟ್ಟು ಮಾನ್ಯವಾದ ಫೋಟೋ ಗುರುತಿನ ದಾ", SPOKEN)).toBe(true);
  });

  it.each([
    "ನನ್ನ ಖಾತೆ ಬಾಕಿ ಎಷ್ಟಿದೆ",
    "ಬ್ಯಾಂಕ್ ಖಾತೆ ತೆರೆಯಬೇಕು",
    "ಹೌದು",
    "ರಾಮಕೃಷ್ಣ",
    "ನನ್ನ ಹೆಸರು ರಾಮಕೃಷ್ಣ ಹೆಗಡೆ",
  ])("does not treat %s as echo", (text) => {
    expect(isEcho(text, SPOKEN)).toBe(false);
  });

  it("handles empty input", () => {
    expect(isEcho("", SPOKEN)).toBe(false);
    expect(isEcho(null, SPOKEN)).toBe(false);
    expect(isEcho("ಖಾತೆ ಸಂಬಂಧಿತ ಪ್ರಶ್ನೆಗಳಿಗಾಗಿ ದಯವಿಟ್ಟು ಮಾನ್ಯವಾದ ಫೋಟೋ", [])).toBe(false);
  });
});
