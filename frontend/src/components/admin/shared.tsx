import { useState, type ReactNode } from "react";
import type { HistoryItem } from "../../api/client";

/* ── Formatting ─────────────────────────────────────────────────────────── */

export function money(n: number): string {
  return `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function timeOnly(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  } catch {
    return iso;
  }
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

/** "Today 2:05 PM" / "Yesterday 6:10 PM" / "Oct 3, 6:10 PM" */
export function relativeDay(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = new Date();
  const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const t = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  if (sameDay(d, now)) return `Today ${t}`;
  if (sameDay(d, yesterday)) return `Yesterday ${t}`;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function isToday(iso: string | null | undefined): boolean {
  return Boolean(iso) && new Date(iso as string).toDateString() === new Date().toDateString();
}

export function seconds(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${n < 10 ? n.toFixed(1) : Math.round(n)} s`;
}

/* ── Intents ────────────────────────────────────────────────────────────── */

export const INTENT_LABELS: Record<string, { en: string; kn: string; tone: Tone }> = {
  check_balance: { en: "Balance", kn: "ಶಿಲ್ಕು", tone: "blue" },
  open_account: { en: "Open account", kn: "ಹೊಸ ಖಾತೆ", tone: "green" },
  form_select: { en: "Open form", kn: "ಅರ್ಜಿ", tone: "green" },
  apply_loan: { en: "Loan", kn: "ಸಾಲ", tone: "violet" },
  deposit_money: { en: "Deposit", kn: "ಠೇವಣಿ", tone: "teal" },
  withdraw_money: { en: "Withdraw", kn: "ಹಿಂಪಡೆ", tone: "teal" },
  interest_rate_query: { en: "Interest / repay", kn: "ಬಡ್ಡಿ", tone: "gold" },
  account_info_query: { en: "Account help", kn: "ಖಾತೆ ಮಾಹಿತಿ", tone: "slate" },
  clarification: { en: "Asked to repeat", kn: "ಮತ್ತೆ ಕೇಳಿತು", tone: "amber" },
};

export function intentLabel(intent: string | null | undefined): { en: string; kn: string; tone: Tone } {
  if (!intent) return { en: "—", kn: "", tone: "slate" };
  return INTENT_LABELS[intent] ?? { en: intent.replace(/_/g, " "), kn: "", tone: "slate" };
}

/**
 * A turn staff should look at: the assistant had to ask again, or was unsure.
 * form_select is rule-routed (confidence 0 by design) — not a problem.
 */
export function needsAttention(item: HistoryItem): boolean {
  if (item.intent === "clarification") return true;
  if (item.intent === "form_select") return false;
  return typeof item.confidence === "number" && item.confidence < 0.5;
}

/* ── UI atoms ───────────────────────────────────────────────────────────── */

export type Tone = "blue" | "green" | "violet" | "teal" | "gold" | "slate" | "amber" | "red";

export function Badge({ tone = "slate", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`ac-badge ac-badge--${tone}`}>{children}</span>;
}

export function IntentBadge({ intent }: { intent: string | null | undefined }) {
  const l = intentLabel(intent);
  return (
    <Badge tone={l.tone}>
      {l.en}
      {l.kn && <span className="kn ac-badge-kn"> · {l.kn}</span>}
    </Badge>
  );
}

export function ConfidenceBar({ value }: { value: number | null | undefined }) {
  if (typeof value !== "number") return <span className="ac-muted">—</span>;
  const pct = Math.round(value * 100);
  const tone = pct >= 70 ? "good" : pct >= 50 ? "ok" : "low";
  return (
    <span className={`ac-conf ac-conf--${tone}`} title={`Confidence ${pct}%`}>
      <span className="ac-conf-track">
        <span className="ac-conf-fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="ac-conf-num">{pct}%</span>
    </span>
  );
}

export function Card({
  title,
  titleKn,
  actions,
  children,
  className = "",
  flush = false,
}: {
  title?: ReactNode;
  titleKn?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <section className={`ac-card ${className}`}>
      {(title || actions) && (
        <header className="ac-card-head">
          <div>
            {title && <h2 className="ac-card-title">{title}</h2>}
            {titleKn && <p className="ac-card-kn kn">{titleKn}</p>}
          </div>
          {actions && <div className="ac-card-actions">{actions}</div>}
        </header>
      )}
      <div className={flush ? "ac-card-body ac-card-body--flush" : "ac-card-body"}>{children}</div>
    </section>
  );
}

export function Empty({ icon = "○", title, hint }: { icon?: string; title: string; hint?: string }) {
  return (
    <div className="ac-empty">
      <span className="ac-empty-icon" aria-hidden>
        {icon}
      </span>
      <p className="ac-empty-title">{title}</p>
      {hint && <p className="ac-empty-hint">{hint}</p>}
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="ac-loading" role="status">
      <span className="ac-spinner" aria-hidden />
      {label}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p className="ac-error" role="alert">
      {message}
    </p>
  );
}

/* ── Icons (inline, stroke = currentColor) ─────────────────────────────── */

const ICONS: Record<string, string> = {
  overview: "M4 13h6v7H4v-7zm10-9h6v16h-6V4zM4 4h6v5H4V4z",
  conversations: "M4 5h16v10H8l-4 4V5zm4 4h8m-8 3h5",
  forms: "M7 3h10l2 2v16H5V3h2zm2 6h6m-6 4h6m-6 4h4",
  customers: "M12 12a4 4 0 100-8 4 4 0 000 8zm-7 9a7 7 0 0114 0",
  settings: "M12 15a3 3 0 100-6 3 3 0 000 6zm7.4-3a7.4 7.4 0 00-.1-1.3l2-1.6-2-3.4-2.4 1a7.5 7.5 0 00-2.2-1.3L14.4 3h-4l-.4 2.4a7.5 7.5 0 00-2.2 1.3l-2.4-1-2 3.4 2 1.6a7.4 7.4 0 000 2.6l-2 1.6 2 3.4 2.4-1a7.5 7.5 0 002.2 1.3l.4 2.4h4l.4-2.4a7.5 7.5 0 002.2-1.3l2.4 1 2-3.4-2-1.6c.1-.4.1-.9.1-1.3z",
  guide: "M5 4h9a4 4 0 014 4v12H9a4 4 0 01-4-4V4zm4 4h5m-5 4h5",
  external: "M14 4h6v6m0-6l-9 9M10 6H5v13h13v-5",
  logout: "M15 4h4v16h-4M10 16l4-4-4-4m4 4H4",
  refresh: "M20 11a8 8 0 10-2.3 5.7M20 4v7h-7",
  trash: "M4 7h16M9 7V4h6v3m-8 0l1 13h8l1-13M10 11v6m4-6v6",
  search: "M11 18a7 7 0 100-14 7 7 0 000 14zm9 3l-4.3-4.3",
  play: "M8 5v14l11-7L8 5z",
  print: "M7 8V3h10v5M7 17H4v-7h16v7h-3m-10-3h10v7H7v-7z",
  close: "M6 6l12 12M18 6L6 18",
  menu: "M4 7h16M4 12h16M4 17h16",
};

export function Icon({ name, size = 18 }: { name: keyof typeof ICONS | string; size?: number }) {
  return (
    <svg className="ac-icon" width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d={ICONS[name] ?? ""}
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** "Clear all" for test data — asks "Are you sure?" first. Disabled when there is nothing to clear. */
export function ClearAllButton({
  what,
  count,
  onClear,
}: {
  what: string;
  count: number;
  onClear: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const run = async () => {
    if (busy || count === 0) return;
    if (!window.confirm(`Are you sure? This permanently deletes all ${count} ${what}. It cannot be undone.`)) return;
    setBusy(true);
    try {
      await onClear();
    } finally {
      setBusy(false);
    }
  };
  return (
    <button
      type="button"
      className="ac-btn ac-btn--danger ac-btn--sm"
      disabled={busy || count === 0}
      onClick={() => void run()}
      title={`Delete all ${what}`}
    >
      <Icon name="trash" size={16} /> {busy ? "Clearing…" : "Clear all"}
    </button>
  );
}
