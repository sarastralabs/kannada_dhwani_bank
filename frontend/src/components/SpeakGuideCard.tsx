import { useState } from "react";

// Accounts whose last 4 digits are unique — saying those 4 gets the balance directly.
// (Full list of 25 incl. shared endings: docs/WHAT_TO_SPEAK.md §5.)
const DEMO_ACCOUNTS = [
  { number: "1234567890", name: "ರಾಮೇಶ್", balance: "₹45,230.50" },
  { number: "9876543210", name: "ಅನಿತಾ", balance: "₹12,500.00" },
  { number: "2222333344", name: "ಲಕ್ಷ್ಮಿ", balance: "₹67,890.25" },
  { number: "3456789012", name: "ವಿಜಯ್", balance: "₹8,750.00" },
  { number: "4567890123", name: "ಕವಿತಾ", balance: "₹1,25,000.00" },
  { number: "6789012345", name: "ಮೋಹನ್", balance: "₹32,400.75" },
];

interface SpeakGuideCardProps {
  compact?: boolean;
}

function preferGuideOpen(compact: boolean): boolean {
  if (compact) return false;
  if (typeof window === "undefined") return true;
  return window.matchMedia("(min-width: 720px) and (min-height: 700px)").matches;
}

/**
 * How to talk to the kiosk agent — shown before/during conversation. Kannada only.
 */
export function SpeakGuideCard({ compact = false }: SpeakGuideCardProps) {
  const [open, setOpen] = useState(() => preferGuideOpen(compact));

  return (
    <section
      className={`speak-guide ${compact ? "speak-guide--compact" : ""}`}
      aria-label="ಹೇಗೆ ಮಾತನಾಡುವುದು"
    >
      <button
        type="button"
        className="speak-guide-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="speak-guide-title kn">ಹೇಗೆ ಮಾತನಾಡುವುದು</span>
        <span className="speak-guide-chevron" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
      </button>

      {open && (
        <div className="speak-guide-body">
          <ol className="speak-guide-steps">
            <li>
              <strong>ಕಾಯಿರಿ</strong>
              <span>
                ಮೇಲಿನ ಪೆಟ್ಟಿಗೆ ಹಸಿರು ಬಣ್ಣದಲ್ಲಿ “ಈಗ ಮಾತನಾಡಿ” ಎಂದು ತೋರಿಸಿದಾಗ ಮಾತ್ರ ಮಾತನಾಡಿ. “ಸ್ವಲ್ಪ
                ಕಾಯಿರಿ” ಅಥವಾ “ಕೇಳಿರಿ” ಎಂದು ಇರುವಾಗ ಮಾತನಾಡಬೇಡಿ.
              </span>
            </li>
            <li>
              <strong>ಕನ್ನಡದಲ್ಲಿ ಸ್ಪಷ್ಟವಾಗಿ</strong>
              <span>ಒಮ್ಮೆಗೆ ಒಂದೇ ಚಿಕ್ಕ ವಿನಂತಿ ಹೇಳಿ. ಖಾತೆ ಸಂಖ್ಯೆಯ ಅಂಕಿಗಳ ನಡುವೆ ಸ್ವಲ್ಪ ನಿಲ್ಲಿಸಿ.</span>
            </li>
            <li>
              <strong>ಖಾತೆ ಬ್ಯಾಲೆನ್ಸ್</strong>
              <span>
                “ಖಾತೆ ಬ್ಯಾಲೆನ್ಸ್” ಎಂದು ಹೇಳಿ, ನಂತರ ಖಾತೆ ಸಂಖ್ಯೆಯ <em>ಕೊನೆಯ ನಾಲ್ಕು</em> ಅಂಕಿಗಳನ್ನು
                ಹೇಳಿ (ಉದಾ: ಏಳು ಎಂಟು ಒಂಬತ್ತು ಸೊನ್ನೆ). ಕೇಳಿದರೆ ಕೊನೆಯ ಆರು ಅಂಕಿಗಳನ್ನು ಹೇಳಿ.
              </span>
            </li>
            <li>
              <strong>ಅರ್ಜಿ</strong>
              <span>
                ಪ್ರತಿ ಪ್ರಶ್ನೆಗೆ ಉತ್ತರಿಸಿ. ಸರಿ ಇದ್ದರೆ “ಹೌದು” ಎನ್ನಿ; ತಪ್ಪಿದ್ದರೆ ಸರಿಯಾದ ಉತ್ತರವನ್ನು ಮತ್ತೆ ಹೇಳಿ
                ಅಥವಾ “ಇಲ್ಲ” ಎನ್ನಿ.
              </span>
            </li>
            <li>
              <strong>ಮುಗಿಸು</strong>
              <span>ಕೆಲಸ ಮುಗಿದ ಮೇಲೆ “ಮುಗಿಸು” ಎಂದು ಹೇಳಿ.</span>
            </li>
          </ol>

          <div className="speak-guide-examples">
            <p className="speak-guide-examples-title">ಉದಾಹರಣೆಗೆ ಹೀಗೆ ಹೇಳಿ</p>
            <ul>
              <li>“ನನ್ನ ಖಾತೆ ಬ್ಯಾಲೆನ್ಸ್ ಹೇಳಿ”</li>
              <li>“ಸೇವಿಂಗ್ಸ್ ಅಕೌಂಟ್ ತೆರೆಯುವುದು ಹೇಗೆ”</li>
              <li>“ಚೆಕ್‌ಬುಕ್ ಅರ್ಜಿ”</li>
            </ul>
          </div>

          <div className="speak-guide-accounts">
            <p className="speak-guide-examples-title">ಪ್ರಯೋಗದ ಖಾತೆಗಳು (ಕೊನೆಯ ನಾಲ್ಕು ಅಂಕಿಗಳನ್ನು ಹೇಳಿ)</p>
            <ul className="speak-guide-account-list">
              {DEMO_ACCOUNTS.map((a) => (
                <li key={a.number}>
                  <code>
                    {a.number.slice(0, -4)}
                    <strong>{a.number.slice(-4)}</strong>
                  </code>
                  <span>{a.name}</span>
                  <span className="speak-guide-bal">{a.balance}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}
