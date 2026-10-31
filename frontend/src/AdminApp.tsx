import { useEffect, useState } from "react";
import { adminLogout, checkHealth, fetchAdminMe, fetchKioskStatusLite, type KioskStatusLite } from "./api/client";
import { clearAdminSession, getAdminUsername, isAdminLoggedIn } from "./auth/adminSession";
import { AdminLogin } from "./components/AdminLogin";
import { Conversations } from "./components/admin/Conversations";
import { Customers } from "./components/admin/Customers";
import { Forms } from "./components/admin/Forms";
import { Guide } from "./components/admin/Guide";
import { Overview } from "./components/admin/Overview";
import { Settings } from "./components/admin/Settings";
import { Icon } from "./components/admin/shared";
import { VIEWS, viewFromHash, type AdminView } from "./components/admin/views";
import { getLobbyUrl } from "./utils/apiBase";
import { startVisibilityAwarePoll } from "./utils/polling";

function lobbyPill(s: KioskStatusLite | null): { text: string; tone: string } {
  if (!s) return { text: "Lobby …", tone: "off" };
  if (!s.running) return { text: "Lobby closed", tone: "off" };
  if (s.phase === "conversation" || s.phase === "greeting") return { text: "Customer at counter", tone: "busy" };
  return { text: "Lobby open", tone: "live" };
}

/** Staff console — overview, conversations, forms, customers, settings, guide. */
export function AdminApp() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [adminAuthed, setAdminAuthed] = useState(() => isAdminLoggedIn());
  const [adminChecking, setAdminChecking] = useState(() => isAdminLoggedIn());
  const [view, setView] = useState<AdminView>(() => viewFromHash(window.location.hash));
  const [navOpen, setNavOpen] = useState(false);
  const [lobby, setLobby] = useState<KioskStatusLite | null>(null);
  const username = getAdminUsername() ?? "Staff";

  // Service health (fast liveness probe).
  useEffect(() => {
    let cancelled = false;
    let failures = 0;
    let everOk = false;
    const graceUntil = Date.now() + 60_000;
    const record = (ok: boolean) => {
      if (cancelled) return;
      if (ok) {
        everOk = true;
        failures = 0;
        setConnected(true);
        return;
      }
      if (!everOk && Date.now() < graceUntil) return;
      failures += 1;
      if (failures >= 3) setConnected(false);
    };
    void checkHealth().then(record);
    const stop = startVisibilityAwarePoll(() => checkHealth().then(record), 10000, 30000);
    return () => {
      cancelled = true;
      stop();
    };
  }, []);

  // Validate a stored session once (it ends when the API restarts).
  useEffect(() => {
    if (!isAdminLoggedIn()) return;
    let cancelled = false;
    fetchAdminMe().then((me) => {
      if (cancelled) return;
      if (!me) {
        clearAdminSession();
        setAdminAuthed(false);
      }
      setAdminChecking(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Lobby state for the top bar on every page.
  useEffect(() => {
    if (!adminAuthed) return;
    const load = () => fetchKioskStatusLite().then(setLobby).catch(() => undefined);
    void load();
    return startVisibilityAwarePoll(load, 8000, 30000);
  }, [adminAuthed]);

  useEffect(() => {
    const onHash = () => setView(viewFromHash(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = (next: AdminView) => {
    const hash = VIEWS.find((v) => v.id === next)?.hash ?? "";
    if (hash) window.location.hash = hash;
    else if (window.location.hash) history.replaceState(null, "", window.location.pathname + window.location.search);
    setView(next);
    setNavOpen(false);
    window.scrollTo({ top: 0 });
  };

  const signOut = async () => {
    await adminLogout();
    setAdminAuthed(false);
  };

  const openLobby = () => window.open(getLobbyUrl(), "_blank", "noopener,noreferrer");

  if (adminChecking) {
    return (
      <div className="ac-gate">
        <span className="ac-spinner" aria-hidden />
        <p>Verifying session…</p>
      </div>
    );
  }

  if (!adminAuthed) {
    return <AdminLogin apiOnline={connected} onSuccess={() => setAdminAuthed(true)} />;
  }

  const meta = VIEWS.find((v) => v.id === view) ?? VIEWS[0];
  const pill = lobbyPill(lobby);

  return (
    <div className={`ac-shell ${navOpen ? "nav-open" : ""}`}>
      <aside className="ac-sidebar" aria-label="Navigation">
        <div className="ac-brand">
          <span className="ac-brand-logo" aria-hidden>
            <img src="/mascot/greeting.png" alt="" draggable={false} />
          </span>
          <div>
            <strong className="kn">ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್</strong>
            <span>Staff console</span>
          </div>
        </div>

        <nav className="ac-nav">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              type="button"
              className={`ac-nav-item ${view === v.id ? "is-active" : ""}`}
              aria-current={view === v.id ? "page" : undefined}
              onClick={() => go(v.id)}
            >
              <Icon name={v.icon} size={20} />
              <span>
                <span className="ac-nav-en">{v.en}</span>
                <span className="ac-nav-kn kn">{v.kn}</span>
              </span>
            </button>
          ))}
        </nav>

        <div className="ac-sidebar-foot">
          <p className={`ac-conn ${connected ? "is-on" : connected === false ? "is-off" : ""}`}>
            <span className="ac-conn-dot" aria-hidden />
            {connected ? "Service online" : connected === false ? "Service offline" : "Connecting…"}
          </p>
          <div className="ac-user">
            <span className="ac-user-avatar" aria-hidden>
              {username.charAt(0).toUpperCase()}
            </span>
            <span className="ac-user-name">{username}</span>
            <button type="button" className="ac-icon-btn ac-icon-btn--dark" onClick={() => void signOut()} title="Sign out" aria-label="Sign out">
              <Icon name="logout" size={18} />
            </button>
          </div>
        </div>
      </aside>
      {navOpen && <button type="button" className="ac-scrim" aria-label="Close menu" onClick={() => setNavOpen(false)} />}

      <div className="ac-body">
        <header className="ac-topbar">
          <button type="button" className="ac-icon-btn ac-menu-btn" onClick={() => setNavOpen(true)} aria-label="Open menu">
            <Icon name="menu" size={22} />
          </button>
          <div className="ac-topbar-titles">
            <h1>{meta.en}</h1>
            <p className="kn">{meta.kn}</p>
          </div>
          <div className="ac-topbar-actions">
            <button type="button" className={`ac-pill ac-pill--${pill.tone}`} onClick={() => go("overview")} title="Lobby status">
              <span className="ac-pill-dot" aria-hidden />
              {pill.text}
            </button>
            <button type="button" className="ac-btn ac-btn--outline ac-btn--sm ac-hide-sm" onClick={openLobby}>
              <Icon name="external" size={16} /> Customer screen
            </button>
          </div>
        </header>

        {connected === false && (
          <div className="ac-banner" role="alert">
            Cannot reach the kiosk service. Check that the API is running on the kiosk PC.
          </div>
        )}

        <main className="ac-main">
          {view === "overview" && <Overview apiOnline={connected} onNavigate={go} onOpenLobby={openLobby} />}
          {view === "conversations" && <Conversations apiOnline={connected} />}
          {view === "forms" && <Forms apiOnline={connected} />}
          {view === "customers" && <Customers apiOnline={connected} />}
          {view === "settings" && <Settings apiOnline={connected} username={username} onSignOut={() => void signOut()} />}
          {view === "guide" && <Guide apiOnline={connected} />}
        </main>
      </div>
    </div>
  );
}
