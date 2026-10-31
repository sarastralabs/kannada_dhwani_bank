import { useCallback, useEffect, useMemo, useState } from "react";
import {
  base64ToAudioUrl,
  clearHistory,
  fetchAdminHistory,
  fetchAdminHistoryItem,
  type HistoryItem,
} from "../../api/client";
import { startVisibilityAwarePoll } from "../../utils/polling";
import {
  Badge,
  Card,
  ClearAllButton,
  ConfidenceBar,
  Empty,
  ErrorNote,
  Icon,
  IntentBadge,
  intentLabel,
  Loading,
  needsAttention,
  relativeDay,
  seconds,
} from "./shared";
import { ExportButton } from "./Insights";

type Filter = "all" | "attention" | "forms" | "answers";

const FILTERS: Array<{ id: Filter; label: string }> = [
  { id: "all", label: "All" },
  { id: "attention", label: "Needs attention" },
  { id: "forms", label: "Forms opened" },
  { id: "answers", label: "Answered" },
];

const STAGES: Array<{ key: string; label: string }> = [
  { key: "stt", label: "Speech → text" },
  { key: "translation", label: "Translate" },
  { key: "nlu_router", label: "Understand" },
  { key: "response_translation", label: "Reply text" },
  { key: "tts", label: "Voice" },
];

function TimingBar({ item }: { item: HistoryItem }) {
  const parts = STAGES.map((s) => ({ ...s, v: Number(item.stage_times?.[s.key] ?? 0) })).filter((p) => p.v > 0.005);
  const total = parts.reduce((a, p) => a + p.v, 0);
  if (!total) return <p className="ac-muted">No timing recorded.</p>;
  return (
    <div className="ac-timing">
      <div className="ac-timing-bar">
        {parts.map((p, i) => (
          <span key={p.key} className={`ac-timing-seg ac-timing-seg--${i}`} style={{ flexGrow: p.v }} title={`${p.label}: ${p.v.toFixed(2)} s`} />
        ))}
      </div>
      <ul className="ac-timing-legend">
        {parts.map((p, i) => (
          <li key={p.key}>
            <span className={`ac-timing-swatch ac-timing-seg--${i}`} />
            {p.label} <strong>{p.v.toFixed(2)} s</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Conversations({ apiOnline }: { apiOnline: boolean | null }) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [intent, setIntent] = useState("");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<HistoryItem | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const clearAll = async () => {
    try {
      const n = await clearHistory();
      setSelectedId(null);
      setItems([]);
      setError(null);
      setNotice(`Deleted ${n} conversation${n === 1 ? "" : "s"} and their recordings`);
      window.setTimeout(() => setNotice(null), 3200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not clear conversations");
    }
  };

  const refresh = useCallback(async () => {
    if (apiOnline === false) return;
    try {
      setItems(await fetchAdminHistory(200));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load conversations");
    } finally {
      setLoading(false);
    }
  }, [apiOnline]);

  useEffect(() => {
    void refresh();
    return startVisibilityAwarePoll(() => refresh(), 20000, 60000);
  }, [refresh]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setDetail(items.find((i) => String(i.id) === selectedId) ?? null);
    fetchAdminHistoryItem(selectedId)
      .then((full) => !cancelled && setDetail(full))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // Only refetch when the selection changes, not on every poll.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  useEffect(() => {
    if (!detail?.audio_b64) {
      setAudioUrl(null);
      return;
    }
    const url = base64ToAudioUrl(detail.audio_b64);
    setAudioUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [detail]);

  const intents = useMemo(() => [...new Set(items.map((i) => i.intent).filter(Boolean))].sort(), [items]);
  const counts = useMemo(
    () => ({
      all: items.length,
      attention: items.filter(needsAttention).length,
      forms: items.filter((i) => i.route === "transactional").length,
      answers: items.filter((i) => i.route === "informational" && i.intent !== "clarification").length,
    }),
    [items],
  );

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((i) => {
      if (filter === "attention" && !needsAttention(i)) return false;
      if (filter === "forms" && i.route !== "transactional") return false;
      if (filter === "answers" && (i.route !== "informational" || i.intent === "clarification")) return false;
      if (intent && i.intent !== intent) return false;
      if (q && !`${i.kannada_text} ${i.english_text} ${i.response_text}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [items, filter, intent, query]);

  return (
    <div className="ac-page">
      <div className="ac-toolbar">
        <div className="ac-chips" role="tablist" aria-label="Filter">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={filter === f.id}
              className={`ac-chip ${filter === f.id ? "is-active" : ""} ${f.id === "attention" && counts.attention ? "ac-chip--warn" : ""}`}
              onClick={() => setFilter(f.id)}
            >
              {f.label} <span className="ac-chip-count">{counts[f.id]}</span>
            </button>
          ))}
        </div>
        <div className="ac-toolbar-right">
          <ExportButton kind="history" />
          <select className="ac-select" value={intent} onChange={(e) => setIntent(e.target.value)} aria-label="Request type">
            <option value="">All request types</option>
            {intents.map((i) => (
              <option key={i} value={i}>
                {intentLabel(i).en}
              </option>
            ))}
          </select>
          <label className="ac-search">
            <Icon name="search" size={16} />
            <input
              type="search"
              placeholder="Search what was said…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <button type="button" className="ac-btn ac-btn--outline ac-btn--sm" onClick={() => void refresh()} title="Refresh">
            <Icon name="refresh" size={16} />
          </button>
          <ClearAllButton what="conversations and their recordings" count={items.length} onClear={clearAll} />
        </div>
      </div>

      {error && <ErrorNote message={error} />}
      {notice && <p className="ac-toast">{notice}</p>}

      <div className={`ac-split ${detail ? "has-detail" : ""}`}>
        <Card flush className="ac-split-list">
          {loading ? (
            <Loading />
          ) : shown.length === 0 ? (
            <Empty
              icon="💬"
              title={items.length ? "Nothing matches these filters" : "No conversations yet"}
              hint={items.length ? "Try another filter or clear the search." : "Requests spoken at the kiosk appear here."}
            />
          ) : (
            <ul className="ac-turns">
              {shown.map((i) => (
                <li key={String(i.id)}>
                  <button
                    type="button"
                    className={`ac-turn ${selectedId === String(i.id) ? "is-selected" : ""} ${needsAttention(i) ? "is-attention" : ""}`}
                    onClick={() => setSelectedId(selectedId === String(i.id) ? null : String(i.id))}
                  >
                    <span className="ac-turn-time">{relativeDay(i.created_at)}</span>
                    <span className="ac-turn-said kn">{i.kannada_text || "—"}</span>
                    <span className="ac-turn-en">{i.english_text || "—"}</span>
                    <span className="ac-turn-meta">
                      <IntentBadge intent={i.intent} />
                      <ConfidenceBar value={i.intent === "form_select" ? null : i.confidence} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {!loading && shown.length > 0 && (
            <p className="ac-list-foot">
              Showing {shown.length} of {items.length} most recent
            </p>
          )}
        </Card>

        {detail && (
          <Card
            className="ac-split-detail"
            title="Turn detail"
            titleKn={relativeDay(detail.created_at)}
            actions={
              <button type="button" className="ac-icon-btn" onClick={() => setSelectedId(null)} aria-label="Close detail">
                <Icon name="close" size={18} />
              </button>
            }
          >
            <dl className="ac-detail">
              <div>
                <dt>Customer said</dt>
                <dd className="kn ac-detail-said">{detail.kannada_text || "—"}</dd>
                <dd className="ac-muted">{detail.english_text}</dd>
              </div>
              <div className="ac-detail-row">
                <div>
                  <dt>Understood as</dt>
                  <dd>
                    <IntentBadge intent={detail.intent} />
                  </dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>
                    <ConfidenceBar value={detail.intent === "form_select" ? null : detail.confidence} />
                  </dd>
                </div>
                <div>
                  <dt>Action</dt>
                  <dd>
                    <Badge tone={detail.route === "transactional" ? "green" : "slate"}>
                      {detail.route === "transactional" ? "Opened a form" : "Spoke an answer"}
                    </Badge>
                  </dd>
                </div>
              </div>
              {needsAttention(detail) && (
                <div className="ac-detail-note">
                  {detail.intent === "clarification"
                    ? "The assistant was not sure and asked the customer to say it again."
                    : "Low confidence — check that the right service was chosen."}
                </div>
              )}
              <div>
                <dt>Assistant replied</dt>
                <dd>{detail.response_text || "—"}</dd>
              </div>
              <div>
                <dt>Time taken · {seconds(detail.total_time_s)}</dt>
                <dd>
                  <TimingBar item={detail} />
                </dd>
              </div>
              {audioUrl && (
                <div>
                  <dt>Reply audio</dt>
                  <dd>
                    <audio controls src={audioUrl} className="ac-audio">
                      <track kind="captions" />
                    </audio>
                  </dd>
                </div>
              )}
            </dl>
          </Card>
        )}
      </div>
    </div>
  );
}
