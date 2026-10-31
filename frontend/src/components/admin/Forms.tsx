import { useCallback, useEffect, useMemo, useState } from "react";
import {
  clearFormSubmissions,
  fetchForm,
  fetchFormSubmissions,
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

export function Forms({ apiOnline }: { apiOnline: boolean | null }) {
  const [items, setItems] = useState<FormSubmissionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formFilter, setFormFilter] = useState("");
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
      if (q && !`${i.title_en} ${i.title_kn} ${Object.values(i.values).join(" ")}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [items, formFilter, query]);

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
                  <th>Form</th>
                  <th>Customer</th>
                  <th>Account</th>
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
                      <div className="ac-sub kn">{i.title_kn}</div>
                    </td>
                    <td>{who(i.values) || <span className="ac-muted">—</span>}</td>
                    <td>
                      {i.values.account_number ? (
                        <code>{displayFieldValue("account_number", "digits", i.values.account_number)}</code>
                      ) : (
                        <span className="ac-muted">—</span>
                      )}
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
              Submitted {dateTime(selected.created_at)}
              {selected.status && <Badge tone="blue">{selected.status}</Badge>}
            </p>
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
