import { useCallback, useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { fetchLanding, type LandingData } from "../api/client";
import { AgentMascot } from "../components/AgentMascot";
import { AGENT_PATH, navigate } from "../router";
import { unlockAudio } from "../utils/playAudio";
import {
  AGENT_BUTTON,
  AGENT_BUTTON_LONG,
  BRAND,
  FAQ,
  FINAL,
  FOOTER,
  HELPER,
  HERO,
  HOW,
  JOURNEY,
  NAV,
  PAGE_TITLE,
  RATES,
  SAFETY,
  SERVICES,
  kannadaDigits,
  rateLabel,
} from "./content";
import "./landing.css";

type Rates = NonNullable<LandingData["rates"]>;

/** A real link to /agent (so "open in new tab" works) that opens the agent without reloading. */
function AgentLink({ className, children, onGo }: { className: string; children: ReactNode; onGo?: () => void }) {
  const go = (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; // let the browser handle those
    e.preventDefault();
    onGo?.();
    void unlockAudio(); // this tap is the gesture browsers need before they allow sound
    navigate(AGENT_PATH);
    window.scrollTo(0, 0);
  };
  return (
    <a className={className} href={AGENT_PATH} onClick={go}>
      {children}
    </a>
  );
}

/** Interest rates: asks the backend, which may be waking up (free hosting), so it retries a few times. */
function useRates(): { rates: Rates | null; state: "loading" | "ready" | "error"; retry: () => void } {
  const [rates, setRates] = useState<Rates | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let alive = true;
    let timer = 0;
    setState("loading");
    const tryOnce = (n: number) => {
      fetchLanding()
        .then((d) => {
          if (!alive) return;
          if (d.rates && Object.keys(d.rates).length) {
            setRates(d.rates);
            setState("ready");
          } else {
            setState("error");
          }
        })
        .catch(() => {
          if (!alive) return;
          if (n < 3) timer = window.setTimeout(() => tryOnce(n + 1), 4000);
          else setState("error");
        });
    };
    tryOnce(0);
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [attempt]);

  return { rates, state, retry: () => setAttempt((a) => a + 1) };
}

export default function Landing() {
  const heroRef = useRef<HTMLElement | null>(null);
  const [helperOpen, setHelperOpen] = useState(false);
  const [helperDismissed, setHelperDismissed] = useState(false);
  const { rates, state, retry } = useRates();

  // Landing-only page chrome: Kannada title, smooth anchor scrolling.
  useEffect(() => {
    const previous = document.title;
    document.title = PAGE_TITLE;
    document.documentElement.classList.add("lp-active");
    return () => {
      document.title = previous;
      document.documentElement.classList.remove("lp-active");
    };
  }, []);

  // The small floating helper appears once the big hero mascot has scrolled away.
  useEffect(() => {
    const el = heroRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([entry]) => setHelperOpen(!entry.isIntersecting), { threshold: 0.15 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const scrollTo = useCallback((id: string) => (e: MouseEvent) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return (
    <div className="lp" lang="kn">
      <header className="lp-header">
        <a className="lp-brand" href="/" aria-label={BRAND}>
          <span className="lp-brand-mark" aria-hidden>
            ಕ
          </span>
          <span className="lp-brand-name">{BRAND}</span>
        </a>
        <nav className="lp-nav" aria-label="ಪುಟದ ವಿಭಾಗಗಳು">
          {NAV.map((n) => (
            <a key={n.id} href={`#${n.id}`} onClick={scrollTo(n.id)}>
              {n.label}
            </a>
          ))}
        </nav>
        <AgentLink className="lp-btn lp-btn--saffron lp-btn--sm">{AGENT_BUTTON}</AgentLink>
      </header>

      <main>
        {/* Hero */}
        <section className="lp-hero" ref={heroRef} aria-labelledby="lp-hero-title">
          <div className="lp-hero-text">
            <p className="lp-kicker">{HERO.kicker}</p>
            <h1 id="lp-hero-title">{HERO.title}</h1>
            <p className="lp-lead">{HERO.lead}</p>
            <div className="lp-cta-row">
              <AgentLink className="lp-btn lp-btn--saffron lp-btn--lg">
                <span aria-hidden>🎙️</span> {AGENT_BUTTON_LONG}
              </AgentLink>
              <a className="lp-btn lp-btn--ghost lp-btn--lg" href="#how" onClick={scrollTo("how")}>
                {HERO.secondary}
              </a>
            </div>
            <ul className="lp-chips">
              {HERO.chips.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
            <p className="lp-demo">{HERO.demo}</p>
          </div>
          <div className="lp-hero-art">
            <AgentLink className="lp-hero-mascot-link">
              <AgentMascot mood="greeting" className="lp-hero-mascot" />
            </AgentLink>
          </div>
        </section>

        {/* What you can do */}
        <section className="lp-section" id="services" aria-labelledby="lp-services-title">
          <div className="lp-wrap">
            <h2 id="lp-services-title">{SERVICES.title}</h2>
            <p className="lp-section-lead">{SERVICES.lead}</p>
            <ul className="lp-cards">
              {SERVICES.cards.map((c) => (
                <li key={c.title} className="lp-card">
                  <span className="lp-card-icon" aria-hidden>
                    {c.icon}
                  </span>
                  <h3>{c.title}</h3>
                  <p className="lp-say">
                    <span>{SERVICES.say}</span>
                    “{c.say}”
                  </p>
                  <p className="lp-card-note">{c.note}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* How it works */}
        <section className="lp-section lp-section--tint" id="how" aria-labelledby="lp-how-title">
          <div className="lp-wrap">
            <h2 id="lp-how-title">{HOW.title}</h2>
            <ol className="lp-steps">
              {HOW.steps.map((s, i) => (
                <li key={s.title} className="lp-step">
                  <img className={`lp-pose lp-pose--${s.pose}`} src={`/mascot/${s.pose}.png`} alt="" width={180} height={180} loading="lazy" />
                  <span className="lp-step-no" aria-hidden>
                    {kannadaDigits(i + 1)}
                  </span>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </li>
              ))}
            </ol>
            <div className="lp-tips">
              <h3>{HOW.tipsTitle}</h3>
              <ul>
                {HOW.tips.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* Application journey */}
        <section className="lp-section" id="journey" aria-labelledby="lp-journey-title">
          <div className="lp-wrap">
            <h2 id="lp-journey-title">{JOURNEY.title}</h2>
            <p className="lp-section-lead">{JOURNEY.lead}</p>
            <ol className="lp-journey">
              {JOURNEY.steps.map((s, i) => (
                <li key={s.title}>
                  <span className="lp-journey-no" aria-hidden>
                    {kannadaDigits(i + 1)}
                  </span>
                  <div>
                    <h3>{s.title}</h3>
                    <p>{s.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Interest rates */}
        <section className="lp-section lp-section--tint" id="rates" aria-labelledby="lp-rates-title">
          <div className="lp-wrap">
            <h2 id="lp-rates-title">{RATES.title}</h2>
            <p className="lp-section-lead">{RATES.lead}</p>
            {state === "ready" && rates ? (
              <div className="lp-rate-grid">
                {RATES.groups.map((g) => (
                  <div key={g.title} className="lp-rate-card">
                    <h3>{g.title}</h3>
                    <dl>
                      {g.rows.map((r) =>
                        rates[r.key] ? (
                          <div key={r.key}>
                            <dt>{r.label}</dt>
                            <dd>
                              <strong>{rateLabel(rates[r.key].percent)}</strong>
                              {rates[r.key].floating && <small>{RATES.floating}</small>}
                            </dd>
                          </div>
                        ) : null,
                      )}
                    </dl>
                  </div>
                ))}
              </div>
            ) : state === "loading" ? (
              <p className="lp-rate-status" role="status">
                {RATES.loading}
              </p>
            ) : (
              <p className="lp-rate-status" role="alert">
                {RATES.error}{" "}
                <button type="button" className="lp-link-btn" onClick={retry}>
                  {RATES.retry}
                </button>
              </p>
            )}
            <p className="lp-fineprint">{RATES.note}</p>
          </div>
        </section>

        {/* Safety */}
        <section className="lp-section" id="safety" aria-labelledby="lp-safety-title">
          <div className="lp-wrap">
            <h2 id="lp-safety-title">{SAFETY.title}</h2>
            <ul className="lp-safety">
              {SAFETY.items.map((s) => (
                <li key={s.title}>
                  <span className="lp-card-icon" aria-hidden>
                    {s.icon}
                  </span>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* FAQ */}
        <section className="lp-section lp-section--tint" id="faq" aria-labelledby="lp-faq-title">
          <div className="lp-wrap lp-wrap--narrow">
            <h2 id="lp-faq-title">{FAQ.title}</h2>
            <div className="lp-faq">
              {FAQ.items.map((f) => (
                <details key={f.q}>
                  <summary>{f.q}</summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Final call */}
        <section className="lp-final" aria-labelledby="lp-final-title">
          <img className="lp-pose lp-pose--happy" src="/mascot/happy.png" alt="" width={220} height={220} loading="lazy" />
          <h2 id="lp-final-title">{FINAL.title}</h2>
          <p>{FINAL.lead}</p>
          <AgentLink className="lp-btn lp-btn--saffron lp-btn--lg">
            <span aria-hidden>🎙️</span> {AGENT_BUTTON_LONG}
          </AgentLink>
        </section>
      </main>

      <footer className="lp-footer">
        <p>{FOOTER.line}</p>
        <p className="lp-fineprint">{FOOTER.demo}</p>
      </footer>

      {/* Floating helper: appears after the hero, one tap opens the agent. */}
      {helperOpen && !helperDismissed && (
        <div className="lp-helper" role="complementary">
          <AgentLink className="lp-helper-main">
            <img src="/mascot/greeting.png" alt="" width={72} height={72} />
            <span>{HELPER.bubble}</span>
          </AgentLink>
          <button type="button" className="lp-helper-close" aria-label={HELPER.close} onClick={() => setHelperDismissed(true)}>
            ×
          </button>
        </div>
      )}
    </div>
  );
}
