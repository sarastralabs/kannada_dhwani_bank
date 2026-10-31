import { useCallback, useEffect, useState } from "react";
import { fetchCustomerDetail, recordLoanRepayment, type CustomerDetail as Detail } from "../../api/client";
import { Badge, Card, Empty, ErrorNote, Icon, Loading, dateTime, money } from "./shared";

const KIND: Record<string, { label: string; tone: "green" | "red" | "blue" | "violet" | "amber" | "slate" }> = {
  deposit: { label: "Deposit", tone: "green" },
  withdrawal: { label: "Withdrawal", tone: "red" },
  transfer_in: { label: "Transfer in", tone: "green" },
  transfer_out: { label: "Transfer out", tone: "red" },
  loan_disbursal: { label: "Loan paid in", tone: "blue" },
  fd_open: { label: "Fixed deposit", tone: "violet" },
  reversal: { label: "Reversal", tone: "amber" },
};

const STATUS: Record<string, string> = {
  submitted: "Needs review",
  approved: "Approved",
  rejected: "Rejected",
  needs_info: "Info requested",
};

/** One customer in full. Staff can record a loan payment received at the counter. */
export function CustomerDetail({ customerId, onClose, onChanged }: { customerId: string; onClose: () => void; onChanged: () => void }) {
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pay, setPay] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await fetchCustomerDetail(customerId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this customer");
    }
  }, [customerId]);

  useEffect(() => {
    setData(null);
    setNotice(null);
    void load();
  }, [load]);

  const repay = async (loanId: string) => {
    const amount = Number(pay[loanId]);
    if (!amount || amount <= 0) return;
    setBusy(loanId);
    setError(null);
    try {
      const r = await recordLoanRepayment(loanId, amount);
      setPay((p) => ({ ...p, [loanId]: "" }));
      setNotice(r.closed ? "Payment recorded — the loan is fully repaid." : `Payment recorded. ${money(r.outstanding_after)} still due.`);
      await load();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record the payment");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card
      className="ac-split-detail"
      title={data ? <span className="kn">{data.customer.full_name_kn || data.customer.full_name}</span> : "Customer"}
      titleKn={data?.customer.mobile ? `Mobile ••••••${data.customer.mobile.slice(-4)}` : undefined}
      actions={
        <button type="button" className="ac-icon-btn" onClick={onClose} aria-label="Close customer">
          <Icon name="close" size={18} />
        </button>
      }
    >
      {error && <ErrorNote message={error} />}
      {notice && <p className="ac-toast">{notice}</p>}
      {!data && !error && <Loading />}
      {data && (
        <div className="ac-custdetail">
          <section>
            <h3>Accounts</h3>
            {data.accounts.map((a) => (
              <div key={a.account_number} className="ac-custrow">
                <code>{a.account_number}</code>
                <Badge tone={a.account_type === "Current" ? "violet" : "blue"}>{a.account_type}</Badge>
                <strong>{money(a.balance_inr)}</strong>
              </div>
            ))}
          </section>

          <section>
            <h3>Loans</h3>
            {data.loans.length === 0 && <p className="ac-muted">No loans.</p>}
            {data.loans.map((l) => (
              <div key={l.id} className="ac-loan">
                <div className="ac-custrow">
                  <strong>{l.loan_type}</strong>
                  <Badge tone={l.status === "active" ? "amber" : "green"}>{l.status}</Badge>
                  <span>{money(l.outstanding_inr)} due of {money(l.principal_inr)}</span>
                </div>
                {l.emi_inr ? (
                  <p className="ac-sub">
                    EMI {money(l.emi_inr)} · {l.annual_rate_pct}% · {l.tenure_months} months
                  </p>
                ) : null}
                {l.status === "active" && (
                  <div className="ac-pay">
                    <input
                      type="number"
                      min="0"
                      placeholder="Payment received (₹)"
                      aria-label="Payment received"
                      value={pay[l.id] ?? ""}
                      onChange={(e) => setPay((p) => ({ ...p, [l.id]: e.target.value }))}
                    />
                    <button type="button" className="ac-btn ac-btn--gold ac-btn--sm" disabled={busy === l.id || !Number(pay[l.id])} onClick={() => void repay(l.id)}>
                      Record payment
                    </button>
                  </div>
                )}
              </div>
            ))}
          </section>

          {data.deposits.length > 0 && (
            <section>
              <h3>Fixed deposits</h3>
              {data.deposits.map((d) => (
                <div key={d.id} className="ac-custrow">
                  <strong>{money(d.principal_inr)}</strong>
                  <span className="ac-sub">
                    {d.annual_rate_pct}% · {d.tenure_months} months
                  </span>
                  <span>
                    matures {d.matures_on} at {money(d.maturity_inr)}
                  </span>
                </div>
              ))}
            </section>
          )}

          <section>
            <h3>Recent activity</h3>
            {data.transactions.length === 0 ? (
              <Empty icon="🧾" title="No movements yet" />
            ) : (
              <table className="ac-table ac-table--tight">
                <tbody>
                  {data.transactions.map((t) => {
                    const k = KIND[t.kind] ?? { label: t.kind, tone: "slate" as const };
                    const out = t.kind === "withdrawal" || t.kind === "transfer_out" || t.kind === "fd_open";
                    return (
                      <tr key={t.id}>
                        <td>
                          <Badge tone={k.tone}>{k.label}</Badge>
                          <div className="ac-sub">{dateTime(t.at)}</div>
                        </td>
                        <td className="ac-num">
                          <strong>
                            {out ? "−" : "+"}
                            {money(t.amount)}
                          </strong>
                          <div className="ac-sub">balance {money(t.balance_after)}</div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </section>

          {data.applications.length > 0 && (
            <section>
              <h3>Applications</h3>
              {data.applications.map((a) => (
                <div key={a.ref} className="ac-custrow">
                  <code>{a.ref}</code>
                  <span>{a.title_en}</span>
                  <Badge tone={a.status === "approved" ? "green" : a.status === "rejected" ? "red" : "amber"}>{STATUS[a.status] ?? a.status}</Badge>
                </div>
              ))}
            </section>
          )}
        </div>
      )}
    </Card>
  );
}
