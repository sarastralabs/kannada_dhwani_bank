import { useEffect, useState } from "react";
import {
  downloadAdminCsv,
  fetchSystemStatus,
  fetchUsageStats,
  type SystemStatus,
  type UsageStats,
} from "../../api/client";
import { Badge, Card, Empty, ErrorNote, Icon } from "./shared";

const STAGE_LABEL: Record<string, { en: string; kn: string }> = {
  stt: { en: "Listening", kn: "ಕೇಳುವುದು" },
  translation: { en: "Understanding", kn: "ಅರ್ಥಮಾಡಿಕೊಳ್ಳುವುದು" },
  tts: { en: "Speaking", kn: "ಮಾತನಾಡುವುದು" },
};

function capTone(l: SystemStatus["limits"]): "green" | "amber" | "red" | "slate" {
  if (!l.enabled || l.daily_cap <= 0) return "slate";
  const used = l.daily_used / l.daily_cap;
  return used >= 1 ? "red" : used >= 0.8 ? "amber" : "green";
}

/** Is each stage loaded, and which engine answers it? Replaces guessing from "please say again". */
export function SystemStatusCard({ apiOnline }: { apiOnline: boolean | null }) {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (apiOnline === false) return;
    let alive = true;
    const load = () =>
      fetchSystemStatus()
        .then((s) => {
          if (!alive) return;
          setStatus(s);
          setError(null);
        })
        .catch((e: unknown) => {
          if (alive) setError(e instanceof Error ? e.message : "Could not load status");
        });
    void load();
    const timer = window.setInterval(load, 15000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [apiOnline]);

  // With every stage on Sarvam there is no local model to load, so "not loaded" is normal.
  const allCloud = status ? Object.values(status.stages).every((st) => st.provider === "sarvam") : false;
  const pipelineOk = status ? status.pipeline_ready || allCloud : false;
  const healthy = status ? pipelineOk && status.recent.healthy && status.database.ok : null;

  return (
    <Card
      title="System health"
      titleKn="ವ್ಯವಸ್ಥೆಯ ಸ್ಥಿತಿ"
      actions={
        healthy === null ? null : <Badge tone={healthy ? "green" : "red"}>{healthy ? "All good" : "Needs attention"}</Badge>
      }
    >
      {error && <ErrorNote message={error} />}
      {!status && !error && <p className="ac-muted">Checking…</p>}
      {status && (
        <ul className="ac-health">
          <li>
            <span>Voice pipeline</span>
            <Badge tone={pipelineOk ? "green" : "amber"}>
              {status.pipeline_ready ? "Loaded" : allCloud ? "Cloud — no local models" : "Loads on first request"}
            </Badge>
          </li>
          {Object.entries(status.stages).map(([key, st]) => (
            <li key={key}>
              <span>
                {STAGE_LABEL[key]?.en ?? key} <small className="kn">{STAGE_LABEL[key]?.kn}</small>
              </span>
              <Badge tone={st.last_ok === false ? "red" : st.provider === "sarvam" ? "violet" : "slate"}>
                {st.provider === "sarvam" ? (st.using_local_now ? "Sarvam → local" : "Sarvam AI") : "Open-source"}
              </Badge>
            </li>
          ))}
          <li>
            <span>
              Voice calls today <small className="kn">ಇಂದಿನ ಧ್ವನಿ ಕರೆಗಳು</small>
            </span>
            <Badge tone={capTone(status.limits)}>
              {status.limits.daily_cap > 0 ? `${status.limits.daily_used} / ${status.limits.daily_cap}` : `${status.limits.daily_used} (no cap)`}
            </Badge>
          </li>
          <li>
            <span>Database</span>
            <Badge tone={status.database.ok ? "green" : "red"}>
              {status.database.kind === "mongodb" ? "MongoDB" : "SQLite"}
              {status.database.ok ? "" : " — offline"}
            </Badge>
          </li>
        </ul>
      )}
      {status?.default_admin_password && (
        <ErrorNote message="The admin password is still the default (bank@123). Set BANK_ADMIN_PASS before anyone else can reach this console." />
      )}
      {status && status.limits.blocked_recent > 0 && (
        <ErrorNote
          message={`${status.limits.blocked_recent} request(s) were blocked by the rate limit in the last 15 min. If customers are affected, raise BANK_RATE_PER_MIN or BANK_DAILY_CAP.`}
        />
      )}
      {status && status.recent.service_failures > 0 && (
        <ErrorNote
          message={`${status.recent.service_failures} service failure(s) in the last ${Math.round(status.recent.window_s / 60)} min${
            status.recent.last_error ? `: ${status.recent.last_error.message}` : ""
          }. Customers are told to try again while this lasts.`}
        />
      )}
    </Card>
  );
}

/** Requests per day for the last two weeks — plain SVG, no chart library. */
export function ActivityChart() {
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUsageStats(14)
      .then(setStats)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Could not load stats"));
  }, []);

  const days = stats?.days ?? [];
  const max = Math.max(1, ...days.map((d) => d.count));
  const total = days.reduce((n, d) => n + d.count, 0);

  return (
    <Card title="Requests — last 14 days" titleKn="ಕಳೆದ ೧೪ ದಿನಗಳು">
      {error && <ErrorNote message={error} />}
      {stats && total === 0 && <Empty icon="📈" title="No requests in this period" />}
      {stats && total > 0 && (
        <figure className="ac-chart">
          <svg viewBox={`0 0 ${days.length * 24} 110`} role="img" aria-label={`${total} requests over ${days.length} days`}>
            {days.map((d, i) => {
              const h = Math.round((d.count / max) * 80);
              return (
                <g key={d.date}>
                  <title>{`${d.date}: ${d.count}`}</title>
                  <rect
                    className="ac-chart-bar"
                    x={i * 24 + 4}
                    y={90 - h}
                    width={16}
                    height={Math.max(h, d.count ? 2 : 0)}
                    rx={4}
                  />
                  {d.count > 0 && (
                    <text className="ac-chart-val" x={i * 24 + 12} y={85 - h} textAnchor="middle">
                      {d.count}
                    </text>
                  )}
                  <text className="ac-chart-tick" x={i * 24 + 12} y={106} textAnchor="middle">
                    {d.date.slice(8)}
                  </text>
                </g>
              );
            })}
          </svg>
          <figcaption className="ac-muted">
            {total} requests · avg response {stats.avg_response_s ?? "—"}s
          </figcaption>
        </figure>
      )}
    </Card>
  );
}

export function ExportButton({ kind, label = "Export CSV" }: { kind: "history" | "submissions"; label?: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <>
      <button
        type="button"
        className="ac-btn ac-btn--outline ac-btn--sm"
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setErr(null);
          downloadAdminCsv(kind)
            .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Export failed"))
            .finally(() => setBusy(false));
        }}
      >
        <Icon name="external" size={16} /> {busy ? "Exporting…" : label}
      </button>
      {err && <span className="ac-error">{err}</span>}
    </>
  );
}
