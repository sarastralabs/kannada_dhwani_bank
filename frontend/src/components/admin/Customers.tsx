import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchAdminCustomers, type AdminBalanceAuditRow, type AdminCustomerRow } from "../../api/client";
import { Badge, Card, Empty, ErrorNote, Icon, Loading, money, relativeDay } from "./shared";

/** backend/balance_lookup.py audit sources -> staff wording. */
function sourceLabel(source: string): string {
  switch (source) {
    case "last4_ambiguous":
      return "Last 4 shared — asked for 6";
    case "last4_not_found":
      return "No account ends in these 4";
    case "length_reject":
      return "Wrong number of digits";
    case "not_found":
      return "No such account";
    default:
      return "Matched in records";
  }
}

export function Customers({ apiOnline }: { apiOnline: boolean | null }) {
  const [rows, setRows] = useState<AdminCustomerRow[]>([]);
  const [audit, setAudit] = useState<AdminBalanceAuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const refresh = useCallback(async () => {
    if (apiOnline === false) return;
    try {
      const data = await fetchAdminCustomers();
      setRows(data.customers);
      setAudit(data.balance_audit);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load customers");
    } finally {
      setLoading(false);
    }
  }, [apiOnline]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const sharedLast4 = useMemo(() => {
    const c = new Map<string, number>();
    for (const r of rows) c.set(r.account_number.slice(-4), (c.get(r.account_number.slice(-4)) ?? 0) + 1);
    return c;
  }, [rows]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) =>
      `${r.holder_name} ${r.holder_name_kn} ${r.account_number} ${r.mobile ?? ""}`.toLowerCase().includes(q),
    );
  }, [rows, query]);

  const totals = useMemo(
    () => ({
      accounts: rows.length,
      deposits: rows.reduce((a, r) => a + Number(r.balance_inr || 0), 0),
      loans: rows.filter((r) => r.loans?.length).length,
      lookups: audit.length,
      found: audit.filter((a) => a.found).length,
    }),
    [rows, audit],
  );

  return (
    <div className="ac-page">
      <div className="ac-kpis ac-kpis--4">
        <article className="ac-kpi">
          <span className="ac-kpi-label">Accounts</span>
          <strong className="ac-kpi-value">{totals.accounts}</strong>
          <span className="ac-kpi-sub">demo customers</span>
        </article>
        <article className="ac-kpi">
          <span className="ac-kpi-label">Total balances</span>
          <strong className="ac-kpi-value ac-kpi-value--sm">{money(totals.deposits)}</strong>
          <span className="ac-kpi-sub">across all accounts</span>
        </article>
        <article className="ac-kpi">
          <span className="ac-kpi-label">With loans</span>
          <strong className="ac-kpi-value">{totals.loans}</strong>
          <span className="ac-kpi-sub">accounts</span>
        </article>
        <article className="ac-kpi">
          <span className="ac-kpi-label">Balance lookups</span>
          <strong className="ac-kpi-value">{totals.lookups}</strong>
          <span className="ac-kpi-sub">{totals.found} found · {totals.lookups - totals.found} not found</span>
        </article>
      </div>

      {error && <ErrorNote message={error} />}

      <Card
        title="Accounts"
        titleKn="ಖಾತೆಗಳು"
        flush
        actions={
          <>
            <label className="ac-search">
              <Icon name="search" size={16} />
              <input type="search" placeholder="Name, account or mobile…" value={query} onChange={(e) => setQuery(e.target.value)} />
            </label>
            <button type="button" className="ac-btn ac-btn--outline ac-btn--sm" onClick={() => void refresh()} title="Refresh">
              <Icon name="refresh" size={16} />
            </button>
          </>
        }
      >
        {loading ? (
          <Loading />
        ) : shown.length === 0 ? (
          <Empty icon="👤" title={rows.length ? "No customer matches" : "No customers"} />
        ) : (
          <table className="ac-table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>Account</th>
                <th>Type</th>
                <th className="ac-num">Balance</th>
                <th>Mobile</th>
                <th>Loans</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => {
                const shared = (sharedLast4.get(r.account_number.slice(-4)) ?? 0) > 1;
                return (
                  <tr key={r.account_number}>
                    <td>
                      <strong className="kn">{r.holder_name_kn || r.holder_name}</strong>
                      <div className="ac-sub">{r.holder_name}</div>
                    </td>
                    <td className="ac-nowrap">
                      <code className="ac-acct">
                        {r.account_number.slice(0, -4)}
                        <b>{r.account_number.slice(-4)}</b>
                      </code>
                      {shared && (
                        <span className="ac-shared" title="Another account ends in the same 4 digits — the kiosk will ask for the last 6">
                          shares last 4
                        </span>
                      )}
                    </td>
                    <td>
                      <Badge tone={r.account_type === "Current" ? "violet" : "blue"}>{r.account_type}</Badge>
                    </td>
                    <td className="ac-num">
                      <strong>{money(r.balance_inr)}</strong>
                    </td>
                    <td className="ac-muted ac-nowrap">{r.mobile || "—"}</td>
                    <td>
                      {r.loans?.length
                        ? r.loans.map((l) => (
                            <div key={l.id} className="ac-sub">
                              {l.loan_type} · {money(l.outstanding_inr)} due
                            </div>
                          ))
                        : <span className="ac-muted">—</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="Balance lookup log" titleKn="ಶಿಲ್ಕು ಪರಿಶೀಲನೆಗಳು" flush>
        {audit.length === 0 ? (
          <Empty icon="🔎" title="No balance lookups yet" hint="Each balance request at the kiosk is logged here." />
        ) : (
          <table className="ac-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Account said</th>
                <th>How</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((a) => (
                <tr key={a.id}>
                  <td className="ac-nowrap">{relativeDay(a.created_at)}</td>
                  <td>
                    <code>{a.account_number}</code>
                  </td>
                  <td className="ac-muted">{sourceLabel(a.source)}</td>
                  <td>
                    <Badge tone={a.found ? "green" : "amber"}>{a.found ? "Found" : "Not found"}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
