import { useCallback, useEffect, useRef, useState, type CSSProperties, type MouseEvent, type ReactNode } from "react";
import "@fontsource/baloo-tamma-2/kannada-600.css";
import "@fontsource/baloo-tamma-2/kannada-700.css";
import "@fontsource/baloo-tamma-2/kannada-800.css";
import "@fontsource/baloo-tamma-2/latin-700.css";
import "@fontsource/baloo-tamma-2/latin-800.css";
import { fetchLanding, type LandingData } from "../api/client";
import { AgentMascot } from "../components/AgentMascot";
import { AGENT_PATH, navigate } from "../router";
import { unlockAudio } from "../utils/playAudio";
import { ChatPreview } from "./ChatPreview";
import {
  AGENT_BUTTON,
  AGENT_BUTTON_LONG,
  BRAND,
  CHAT,
  CONTROLS,
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
  STATS,
  kannadaDigits,
  rateLabel,
} from "./content";
import { useReveal, useTextSize } from "./hooks";
import { Icon } from "./Icons";
import "./landing.css";

type Rates = NonNullable<LandingData["rates"]>;

const stagger = (i: number): CSSProperties => ({ ["--i" as string]: i });

/** A real link to /agent (so "open in new tab" works) that opens the agent without reloading. */
function AgentLink({ className, children, label }: { className: string; children: ReactNode; label?: string }) {
  const go = (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; // let the browser handle those
    e.preventDefault();
    void unlockAudio(); // this tap is the gesture browsers need before they allow sound
    navigate(AGENT_PATH);
    window.scrollTo(0, 0);
  };
  return (
    <a className={className} href={AGENT_PATH} onClick={go} aria-label={label}>
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
  const [menuOpen, setMenuOpen] = useState(false);
  const [mood, setMood] = useState<"greeting" | "listening">("greeting");
  const { rates, state, retry } = useRates();
  const { level, cycle } = useTextSize();
  useReveal(state);

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

  // The floating helper / bottom bar appears once the hero has scrolled away.
  useEffect(() => {
    const el = heroRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([entry]) => setHelperOpen(!entry.isIntersecting), { threshold: 0.1 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const scrollTo = useCallback(
    (id: string) => (e: MouseEvent) => {
      e.preventDefault();
      setMenuOpen(false);
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    [],
  );

  return (
    <div className="lp" lang="kn">
      <header className="lp-header">
        <a className="lp-brand" href="/" aria-label={BRAND}>
          <span className="lp-brand-mark" aria-hidden>
            ಕ
          </span>
          <span className="lp-brand-name">{BRAND}</span>
        </a>
        <nav className="lp-nav" aria-label={CONTROLS.sections}>
          {NAV.map((n) => (
            <a key={n.id} href={`#${n.id}`} onClick={scrollTo(n.id)}>
              {n.label}
            </a>
          ))}
        </nav>
        <button type="button" className="lp-size-btn lp-size-btn--header" data-level={level} onClick={cycle} aria-label={CONTROLS.textSizeHint} title={CONTROLS.textSizeHint}>
          <span aria-hidden>ಅ</span>
        </button>
        <AgentLink className="lp-btn lp-btn--saffron lp-btn--sm">{AGENT_BUTTON}</AgentLink>
        <button
          type="button"
          className="lp-menu-btn"
          aria-expanded={menuOpen}
          aria-controls="lp-menu"
          aria-label={menuOpen ? CONTROLS.menuClose : CONTROLS.menuOpen}
          onClick={() => setMenuOpen((o) => !o)}
        >
          <Icon name={menuOpen ? "close" : "menu"} size={24} />
        </button>
        {menuOpen && (
          <div id="lp-menu" className="lp-menu">
            {NAV.map((n) => (
              <a key={n.id} href={`#${n.id}`} onClick={scrollTo(n.id)}>
                {n.label}
              </a>
            ))}
            <button type="button" className="lp-menu-size" onClick={cycle} data-level={level}>
              <span aria-hidden>ಅ</span> {CONTROLS.textSize}
            </button>
          </div>
        )}
      </header>

      <main>
        {/* Hero */}
        <section className="lp-hero" ref={heroRef} aria-labelledby="lp-hero-title">
          <div className="lp-hero-inner">
            <div className="lp-hero-text">
              <p className="lp-kicker">{HERO.kicker}</p>
              <h1 id="lp-hero-title">
                {HERO.titleLead} <span className="lp-mark">{HERO.titleMark}</span>
              </h1>
              <p className="lp-lead">{HERO.lead}</p>
              <div className="lp-cta-row">
                <AgentLink className="lp-btn lp-btn--saffron lp-btn--lg">
                  <Icon name="mic" size={22} /> {AGENT_BUTTON_LONG}
                </AgentLink>
                <a className="lp-btn lp-btn--ghost lp-btn--lg" href="#how" onClick={scrollTo("how")}>
                  {HERO.secondary}
                </a>
              </div>
              <p className="lp-demo">{HERO.demo}</p>
            </div>
            <div className="lp-hero-art">
              <div
                className="lp-hero-stage"
                onMouseEnter={() => setMood("listening")}
                onMouseLeave={() => setMood("greeting")}
                onFocus={() => setMood("listening")}
                onBlur={() => setMood("greeting")}
              >
                <span className="lp-glow" aria-hidden />
                <span className="lp-spark lp-spark--a" aria-hidden />
                <span className="lp-spark lp-spark--b" aria-hidden />
                <span className="lp-spark lp-spark--c" aria-hidden />
                <p className="lp-bubble">{HERO.bubble}</p>
                <AgentLink className="lp-hero-mascot-link" label={HERO.mascotAlt}>
                  <AgentMascot mood={mood} className="lp-hero-mascot" />
                </AgentLink>
              </div>
            </div>
          </div>
          <svg className="lp-wave" viewBox="0 0 1440 70" preserveAspectRatio="none" aria-hidden>
            <path d="M0 38 C 200 82 420 0 700 34 C 980 68 1200 8 1440 42 L1440 70 L0 70 Z" />
          </svg>
        </section>

        {/* Stats strip */}
        <ul className="lp-stats lp-wrap">
          {STATS.map((s, i) => (
            <li key={s.label} className="lp-reveal" style={stagger(i)}>
              <Icon name={s.icon} size={26} />
              <strong>{s.value}</strong>
              <span>{s.label}</span>
            </li>
          ))}
        </ul>

        {/* A conversation */}
        <section className="lp-section" id="chat" aria-labelledby="lp-chat-title">
          <div className="lp-wrap lp-chat">
            <div className="lp-chat-text lp-reveal">
              <h2 id="lp-chat-title">{CHAT.title}</h2>
              <p className="lp-section-lead">{CHAT.lead}</p>
              <ul className="lp-checks">
                {CHAT.points.map((p) => (
                  <li key={p}>
                    <Icon name="check" size={20} />
                    {p}
                  </li>
                ))}
              </ul>
              <AgentLink className="lp-btn lp-btn--saffron lp-btn--lg">
                <Icon name="mic" size={22} /> {AGENT_BUTTON_LONG}
              </AgentLink>
            </div>
            <div className="lp-chat-phone lp-reveal" style={stagger(1)}>
              <ChatPreview />
            </div>
          </div>
        </section>

        {/* What you can do */}
        <section className="lp-section lp-section--tint" id="services" aria-labelledby="lp-services-title">
          <div className="lp-wrap">
            <h2 id="lp-services-title" className="lp-reveal">
              {SERVICES.title}
            </h2>
            <p className="lp-section-lead lp-reveal">{SERVICES.lead}</p>
            <ul className="lp-cards">
              {SERVICES.cards.map((c, i) => (
                <li key={c.title} className="lp-card lp-reveal" style={stagger(i % 4)}>
                  <span className="lp-card-icon" aria-hidden>
                    <Icon name={c.icon} size={26} />
                  </span>
                  <div className="lp-card-body">
                    <h3>{c.title}</h3>
                    <p className="lp-say">
                      <span>{SERVICES.say}</span>
                      “{c.say}”
                    </p>
                    <p className="lp-card-note">{c.note}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* How it works */}
        <section className="lp-section" id="how" aria-labelledby="lp-how-title">
          <div className="lp-wrap">
            <h2 id="lp-how-title" className="lp-reveal">
              {HOW.title}
            </h2>
            <ol className="lp-steps">
              {HOW.steps.map((s, i) => (
                <li key={s.title} className="lp-step lp-reveal" style={stagger(i)}>
                  <img className={`lp-pose lp-pose--${s.pose}`} src={`/mascot/${s.pose}.png`} alt="" width={180} height={180} loading="lazy" />
                  <span className="lp-step-no" aria-hidden>
                    {kannadaDigits(i + 1)}
                  </span>
                  <div className="lp-step-body">
                    <h3>{s.title}</h3>
                    <p>{s.text}</p>
                  </div>
                </li>
              ))}
            </ol>
            <div className="lp-tips lp-reveal">
              <h3>{HOW.tipsTitle}</h3>
              <ul>
                {HOW.tips.map((t) => (
                  <li key={t}>
                    <Icon name="check" size={18} />
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* Application journey */}
        <section className="lp-section lp-section--tint" id="journey" aria-labelledby="lp-journey-title">
          <div className="lp-wrap">
            <h2 id="lp-journey-title" className="lp-reveal">
              {JOURNEY.title}
            </h2>
            <p className="lp-section-lead lp-reveal">{JOURNEY.lead}</p>
            <ol className="lp-journey">
              {JOURNEY.steps.map((s, i) => (
                <li key={s.title} className="lp-reveal" style={stagger(i)}>
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
        <section className="lp-section" id="rates" aria-labelledby="lp-rates-title">
          <div className="lp-wrap">
            <h2 id="lp-rates-title" className="lp-reveal">
              {RATES.title}
            </h2>
            <p className="lp-section-lead lp-reveal">{RATES.lead}</p>
            {state === "ready" && rates ? (
              <div className="lp-rate-grid">
                {RATES.groups.map((g, gi) => (
                  <div key={g.title} className="lp-rate-card lp-reveal" style={stagger(gi)}>
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
        <section className="lp-section lp-section--tint" id="safety" aria-labelledby="lp-safety-title">
          <div className="lp-wrap">
            <h2 id="lp-safety-title" className="lp-reveal">
              {SAFETY.title}
            </h2>
            <ul className="lp-safety">
              {SAFETY.items.map((s, i) => (
                <li key={s.title} className="lp-reveal" style={stagger(i)}>
                  <span className="lp-card-icon" aria-hidden>
                    <Icon name={s.icon} size={26} />
                  </span>
                  <div>
                    <h3>{s.title}</h3>
                    <p>{s.text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* FAQ */}
        <section className="lp-section" id="faq" aria-labelledby="lp-faq-title">
          <div className="lp-wrap lp-wrap--narrow">
            <h2 id="lp-faq-title" className="lp-reveal">
              {FAQ.title}
            </h2>
            <div className="lp-faq">
              {FAQ.items.map((f, i) => (
                <details key={f.q} className="lp-reveal" style={stagger(i % 3)}>
                  <summary>
                    <span>{f.q}</span>
                    <Icon name="plus" size={20} />
                  </summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Final call */}
        <section className="lp-final" aria-labelledby="lp-final-title">
          <svg className="lp-wave lp-wave--top" viewBox="0 0 1440 70" preserveAspectRatio="none" aria-hidden>
            <path d="M0 0 L1440 0 L1440 36 C 1200 70 980 6 700 36 C 420 66 200 4 0 40 Z" />
          </svg>
          <div className="lp-final-inner lp-reveal">
            <img className="lp-pose lp-pose--happy" src="/mascot/happy.png" alt="" width={220} height={220} loading="lazy" />
            <h2 id="lp-final-title">{FINAL.title}</h2>
            <p>{FINAL.lead}</p>
            <AgentLink className="lp-btn lp-btn--saffron lp-btn--lg">
              <Icon name="mic" size={22} /> {AGENT_BUTTON_LONG}
            </AgentLink>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <p>{FOOTER.line}</p>
        <p className="lp-fineprint">{FOOTER.demo}</p>
      </footer>

      {/* Floating helper (desktop) / bottom bar (phones): appears after the hero, one tap opens the agent. */}
      {helperOpen && !helperDismissed && (
        <div className="lp-helper" role="complementary">
          <AgentLink className="lp-helper-main">
            <img src="/mascot/greeting.png" alt="" width={72} height={72} />
            <span className="lp-helper-text">{HELPER.bubble}</span>
            <span className="lp-helper-bar">{AGENT_BUTTON_LONG}</span>
            <Icon name="mic" size={22} />
          </AgentLink>
          <button type="button" className="lp-helper-close" aria-label={HELPER.close} onClick={() => setHelperDismissed(true)}>
            <Icon name="close" size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
