import { useCallback, useEffect, useMemo, useState } from "react";
import {
  clearFormSubmissions,
  decideApplication,
  fetchForm,
  fetchFormSubmissions,
  type ApplicationDecision,
  type BankForm,
  type FormSubmissionItem,
} from "../../api/client";
import { displayFieldValue } from "../../utils/formSummary";
import { startVisibilityAwarePoll } from "../../utils/polling";
import { Badge, Card, ClearAllButton, Empty, ErrorNote, Icon, Loading, relativeDay, dateTime } from "./shared";
import { ExportButton } from "./Insights";

function who(values: Record<string, string>): string {
  return (
    values.full_name?.trim() ||
    values.remitter_name?.trim() ||
    values.applicant_name?.trim() ||
    values.name?.trim() ||
    ""
  );
}

const STATUS: Record<string, { label: string; tone: "amber" | "green" | "red" | "violet" | "slate" }> = {
  submitted: { label: "Needs review", tone: "amber" },
  approved: { label: "Approved", tone: "green" },
  rejected: { label: "Rejected", tone: "red" },
  needs_info: { label: "Info requested", tone: "violet" },
};

function StatusBadge({ status }: { status?: string }) {
  const s = STATUS[status || "submitted"] ?? { label: status || "—", tone: "slate" as const };
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

/** Approve / reject / ask for information, with the message the customer will see. */
function DecisionPanel({ item, onDone }: { item: FormSubmissionItem; onDone: (next: FormSubmissionItem) => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const decided = item.status === "approved" || item.status === "rejected";
  const d: ApplicationDecision | null | undefined = item.decision;

  const act = async (action: ApplicationDecision["action"]) => {
    setBusy(true);
    setError(null);
    try {
      onDone(await decideApplication(item.id, action, note));
      setNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the decision");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="ac-decision no-print" aria-label="Decision">
      {d && (
        <div className={`ac-decision-done ac-decision-done--${item.status}`}>
          <strong>
            {STATUS[item.status || ""]?.label ?? item.status} by {d.by}
          </strong>
          <span className="ac-sub"> · {dateTime(d.at)}</span>
          {d.result?.account_number && (
            <p className="ac-decision-account">
              Account opened: <code>{d.result.account_number}</code> ({d.result.account_type}
              {d.result.existing_customer ? ", added to an existing customer" : ""})
            </p>
          )}
          {d.note && <p className="ac-sub">Message to customer: {d.note}</p>}
        </div>
      )}
      {!decided && (
        <>
          <label className="ac-decision-label" htmlFor="decision-note">
            Message to the customer <span className="ac-muted">(required to reject or ask for information)</span>
          </label>
          <textarea
            id="decision-note"
            className="ac-decision-note"
            rows={2}
            maxLength={500}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. Please bring your ID proof to the branch"
          />
          {error && <ErrorNote message={error} />}
          <div className="ac-decision-actions">
            <button type="button" className="ac-btn ac-btn--gold" disabled={busy} onClick={() => void act("approve")}>
              {item.form_id === "open_account" ? "Approve and open account" : "Approve"}
            </button>
            <button type="button" className="ac-btn ac-btn--outline" disabled={busy} onClick={() => void act("needs_info")}>
              Ask for information
            </button>
            <button type="button" className="ac-btn ac-btn--danger" disabled={busy} onClick={() => void act("reject")}>
              Reject
            </button>
          </div>
        </>
      )}
    </section>
  );
}

export function Forms({ apiOnline }: { apiOnline: boolean | null }) {
  const [items, setItems] = useState<FormSubmissionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formFilter, setFormFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<FormSubmissionItem | null>(null);
  const [schemas, setSchemas] = useState<Record<string, BankForm>>({});
  const [notice, setNotice] = useState<string | null>(null);

  const clearAll = async () => {
    try {
      const n = await clearFormSubmissions();
      setSelected(null);
      setItems([]);
      setError(null);
      setNotice(`Deleted ${n} form submission${n === 1 ? "" : "s"}`);
      window.setTimeout(() => setNotice(null), 3200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not clear form submissions");
    }
  };

  const refresh = useCallback(async () => {
    if (apiOnline === false) return;
    try {
      const next = await fetchFormSubmissions(200);
      next.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
      setItems(next);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load submissions");
    } finally {
      setLoading(false);
    }
  }, [apiOnline]);

  useEffect(() => {
    void refresh();
    return startVisibilityAwarePoll(() => refresh(), 30000, 90000);
  }, [refresh]);

  // Field labels come from the form definition — load it once per form type.
  useEffect(() => {
    const id = selected?.form_id;
    if (!id || schemas[id]) return;
    fetchForm(id)
      .then((f) => setSchemas((prev) => ({ ...prev, [id]: f })))
      .catch(() => undefined);
  }, [selected, schemas]);

  const formTypes = useMemo(() => {
    const m = new Map<string, string>();
    for (const i of items) m.set(i.form_id, i.title_en || i.form_id);
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [items]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((i) => {
      if (formFilter && i.form_id !== formFilter) return false;
      if (statusFilter && (i.status || "submitted") !== statusFilter) return false;
      if (q && !`${i.title_en} ${i.title_kn} ${Object.values(i.values).join(" ")}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [items, formFilter, statusFilter, query]);

  const waiting = items.filter((i) => (i.status || "submitted") === "submitted").length;

  const applyDecision = (next: FormSubmissionItem) => {
    setItems((prev) => prev.map((i) => (i.id === next.id ? next : i)));
    setSelected(next);
  };

  const schema = selected ? schemas[selected.form_id] : undefined;
  const fields = selected
    ? schema
      ? schema.fields.map((f) => ({ id: f.id, label: f.label_en, labelKn: f.label_kn, type: f.type }))
      : Object.keys(selected.values).map((id) => ({ id, label: id.replace(/_/g, " "), labelKn: "", type: "text" }))
    : [];

  return (
    <div className="ac-page">
      <div className="ac-toolbar">
        <div className="ac-toolbar-left">
          <select className="ac-select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Status">
            <option value="">All statuses</option>
            <option value="submitted">Needs review ({waiting})</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="needs_info">Info requested</option>
          </select>
          <select className="ac-select" value={formFilter} onChange={(e) => setFormFilter(e.target.value)} aria-label="Form type">
            <option value="">All forms ({items.length})</option>
            {formTypes.map(([id, title]) => (
              <option key={id} value={id}>
                {title} ({items.filter((i) => i.form_id === id).length})
              </option>
            ))}
          </select>
        </div>
        <div className="ac-toolbar-right">
          <ExportButton kind="submissions" />
          <label className="ac-search">
            <Icon name="search" size={16} />
            <input type="search" placeholder="Search name, account…" value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          <button type="button" className="ac-btn ac-btn--outline ac-btn--sm" onClick={() => void refresh()} title="Refresh">
            <Icon name="refresh" size={16} />
          </button>
          <ClearAllButton what="form submissions" count={items.length} onClear={clearAll} />
        </div>
      </div>

      {error && <ErrorNote message={error} />}
      {notice && <p className="ac-toast">{notice}</p>}

      <div className={`ac-split ${selected ? "has-detail" : ""}`}>
        <Card flush className="ac-split-list">
          {loading ? (
            <Loading />
          ) : shown.length === 0 ? (
            <Empty
              icon="📄"
              title={items.length ? "No submissions match" : "No form submissions yet"}
              hint={items.length ? "Try another form type or clear the search." : "Forms customers complete by voice appear here."}
            />
          ) : (
            <table className="ac-table">
              <thead>
                <tr>
                  <th>Application</th>
                  <th>Customer</th>
                  <th>Status</th>
                  <th>Submitted</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((i) => (
                  <tr
                    key={i.id}
                    className={selected?.id === i.id ? "is-selected" : ""}
                    onClick={() => setSelected(selected?.id === i.id ? null : i)}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === "Enter" && setSelected(i)}
                  >
                    <td>
                      <strong>{i.title_en}</strong>
                      <div className="ac-sub">
                        {i.ref ? <code>{i.ref}</code> : null} <span className="kn">{i.title_kn}</span>
                      </div>
                    </td>
                    <td>{who(i.values) || <span className="ac-muted">—</span>}</td>
                    <td>
                      <StatusBadge status={i.status} />
                    </td>
                    <td className="ac-nowrap">{relativeDay(i.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {selected && (
          <Card
            className="ac-split-detail ac-printable"
            title={selected.title_en}
            titleKn={selected.title_kn}
            actions={
              <>
                <button type="button" className="ac-btn ac-btn--outline ac-btn--sm no-print" onClick={() => window.print()}>
                  <Icon name="print" size={16} /> Print
                </button>
                <button type="button" className="ac-icon-btn no-print" onClick={() => setSelected(null)} aria-label="Close detail">
                  <Icon name="close" size={18} />
                </button>
              </>
            }
          >
            <p className="ac-detail-meta">
              {selected.ref && <code>{selected.ref}</code>} Submitted {dateTime(selected.created_at)}{" "}
              <StatusBadge status={selected.status} />
            </p>
            <DecisionPanel key={selected.id + (selected.status ?? "")} item={selected} onDone={applyDecision} />
            <dl className="ac-fields">
              {fields.map((f) => {
                const raw = selected.values[f.id] ?? "";
                return (
                  <div key={f.id}>
                    <dt>
                      {f.label}
                      {f.labelKn && <span className="kn"> · {f.labelKn}</span>}
                    </dt>
                    <dd>{raw.trim() ? displayFieldValue(f.id, f.type, raw) : <span className="ac-muted">—</span>}</dd>
                  </div>
                );
              })}
            </dl>
            <p className="ac-print-note">Sample branch slip from the voice kiosk — not an official bank document.</p>
          </Card>
        )}
      </div>
    </div>
  );
}
