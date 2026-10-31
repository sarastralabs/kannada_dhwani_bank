import { useEffect, useState } from "react";
import { fetchAdminConversationFlow, type ConversationFlowData } from "../../api/client";
import { Badge, Card, ErrorNote, IntentBadge, Loading } from "./shared";

const COMMAND_LABELS: Record<string, { en: string; kn: string }> = {
  confirm: { en: "Yes / correct", kn: "ಹೌದು" },
  reject: { en: "No / say again", kn: "ಇಲ್ಲ" },
  skip: { en: "Skip optional", kn: "ಬಿಟ್ಟುಬಿಡಿ" },
  end: { en: "Finish", kn: "ಮುಗಿಸು" },
};

export function Guide({ apiOnline }: { apiOnline: boolean | null }) {
  const [flow, setFlow] = useState<ConversationFlowData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    if (apiOnline === false) return;
    fetchAdminConversationFlow()
      .then(setFlow)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load the guide"));
  }, [apiOnline]);

  if (error) return <ErrorNote message={error} />;
  if (!flow) return <Loading label="Loading guide…" />;

  return (
    <div className="ac-page">
      {flow.notes.length > 0 && (
        <aside className="ac-tips" aria-label="Tips for staff">
          <h2>Good to know</h2>
          <ul>
            {flow.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </aside>
      )}

      <Card title="A customer visit, step by step" titleKn="ಗ್ರಾಹಕರ ಭೇಟಿ — ಹಂತ ಹಂತವಾಗಿ">
        <ol className="ac-timeline">
          {flow.phases.map((p, i) => (
            <li key={p.id}>
              <span className="ac-timeline-num">{i + 1}</span>
              <div>
                <h3>{p.title}</h3>
                <p>{p.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </Card>

      <Card title="What customers can ask" titleKn="ಗ್ರಾಹಕರು ಕೇಳಬಹುದಾದವು" flush>
        <ul className="ac-intents">
          {flow.intents.map((row) => {
            const isOpen = open === row.intent;
            const hasForm = Boolean(row.form_id);
            return (
              <li key={row.intent} className={isOpen ? "is-open" : ""}>
                <button type="button" className="ac-intent-row" onClick={() => setOpen(isOpen ? null : row.intent)} aria-expanded={isOpen}>
                  <IntentBadge intent={row.intent} />
                  <span className="ac-intent-dest">
                    {hasForm ? (
                      <>
                        Opens <strong>{row.form_title_en}</strong>
                        <span className="kn ac-sub"> · {row.form_title_kn}</span>
                      </>
                    ) : (
                      "Speaks an answer"
                    )}
                  </span>
                  <span className="ac-intent-examples kn">{row.example_phrases.slice(0, 2).join(" · ")}</span>
                  {hasForm && (
                    <span className="ac-intent-toggle">
                      {isOpen ? "Hide" : `${row.fields.length} question${row.fields.length === 1 ? "" : "s"}`}
                    </span>
                  )}
                </button>
                {isOpen && hasForm && (
                  <ol className="ac-questions">
                    {row.fields.map((f) => (
                      <li key={f.id}>
                        <strong>{f.label_en}</strong>
                        <span className="kn ac-sub"> · {f.label_kn}</span>
                        {f.prompt_kn ? <p className="kn">“{f.prompt_kn}”</p> : <p className="ac-muted">Filled automatically</p>}
                        {!f.required && <Badge tone="slate">optional</Badge>}
                      </li>
                    ))}
                  </ol>
                )}
              </li>
            );
          })}
        </ul>
      </Card>

      <div className="ac-grid ac-grid--2">
        <Card title="Words that work anytime" titleKn="ಯಾವಾಗ ಬೇಕಾದರೂ ಬಳಸಬಹುದಾದ ಪದಗಳು">
          <dl className="ac-commands">
            {Object.entries(flow.voice_commands).map(([key, words]) => (
              <div key={key}>
                <dt>
                  {COMMAND_LABELS[key]?.en ?? key}
                  {COMMAND_LABELS[key] && <span className="kn ac-sub"> · {COMMAND_LABELS[key].kn}</span>}
                </dt>
                <dd>
                  {words.map((w) => (
                    <span key={w} className="ac-word kn">
                      {w}
                    </span>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card title="Form menu" titleKn="ಅರ್ಜಿ ಪಟ್ಟಿ">
          <p className="ac-lead">When a customer asks for “a form”, they pick by number or name.</p>
          <ol className="ac-menu">
            {flow.form_menu.map((m) => (
              <li key={m.id}>
                <span className="ac-menu-num">{m.index}</span>
                <span>
                  {m.title_en}
                  <span className="kn ac-sub"> · {m.title_kn}</span>
                </span>
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </div>
  );
}
