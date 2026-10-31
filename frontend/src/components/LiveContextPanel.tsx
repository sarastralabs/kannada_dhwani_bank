import { displayFieldValue } from "../utils/formSummary";

interface FormDigitSlotsProps {
  value: string;
  maxSlots?: number;
  label?: string;
  /**
   * The customer gives only the end of the number (balance: last 4 or 6 digits).
   * Digits fill the last boxes and the boxes before them show "*".
   */
  lastDigits?: boolean;
}

export function FormDigitSlots({ value, maxSlots = 10, label, lastDigits = false }: FormDigitSlotsProps) {
  const digits = (value || "").replace(/\D/g, "").split("");
  const slots = Math.max(maxSlots, digits.length);
  const hidden = lastDigits ? slots - digits.length : 0;

  return (
    <div className="live-digit-slots" aria-label={label || "ಖಾತೆ ಸಂಖ್ಯೆ"}>
      <div className="live-digit-row">
        {Array.from({ length: slots }, (_, i) => {
          if (i < hidden) {
            return (
              <span key={i} className="live-digit-slot is-masked" aria-hidden>
                *
              </span>
            );
          }
          const d = i - hidden;
          const filled = d < digits.length;
          return (
            <span
              key={i}
              className={`live-digit-slot${filled ? " is-filled" : ""}`}
              aria-hidden
            >
              {filled ? digits[d] : ""}
            </span>
          );
        })}
      </div>
      {value && (
        <p className="live-digit-mask">
          {hidden > 0 ? "*".repeat(hidden) + digits.join("") : displayFieldValue("account_number", "digits", value)}
        </p>
      )}
    </div>
  );
}

export interface BalanceResultView {
  found: boolean;
  account_number: string;
  balance_inr?: number;
  holder_name_kn?: string;
  message_kn: string;
  message_en: string;
}

interface BalanceResultCardProps {
  result: BalanceResultView;
}

export function BalanceResultCard({ result }: BalanceResultCardProps) {
  const maskedAcct = displayFieldValue("account_number", "digits", result.account_number);
  const balanceText =
    result.found && result.balance_inr !== undefined
      ? `₹ ${result.balance_inr.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`
      : null;

  return (
    <section className="balance-result-card panel" aria-live="polite">
      <h3 className="balance-result-title">ಖಾತೆಯ ಶಿಲ್ಕು</h3>
      {result.found ? (
        <>
          {result.holder_name_kn && (
            <p className="balance-result-name kn">{result.holder_name_kn}</p>
          )}
          <p className="balance-result-acct">
            <span className="balance-result-label">ಖಾತೆ</span> {maskedAcct}
          </p>
          {balanceText && <p className="balance-result-amount">{balanceText}</p>}
        </>
      ) : null}
      <p className="balance-result-msg kn">{result.message_kn}</p>
    </section>
  );
}

interface LiveValueCardProps {
  label: string;
  value: string;
  fieldType?: string;
  fieldId?: string;
  /** Only the last digits are asked for (balance inquiry) — right-align them behind "*". */
  lastDigits?: boolean;
}

export function LiveValueCard({
  label,
  value,
  fieldType = "text",
  fieldId = "",
  lastDigits = false,
}: LiveValueCardProps) {
  if (!value) return null;
  const display = displayFieldValue(fieldId, fieldType, value);
  const showSlots = fieldType === "digits" && value.replace(/\D/g, "").length > 0;

  return (
    <div className="live-value-card">
      <p className="live-value-label">{label}</p>
      {showSlots ? (
        <FormDigitSlots value={value} label={label} lastDigits={lastDigits} />
      ) : (
        <p className="live-value-text">{display}</p>
      )}
    </div>
  );
}
