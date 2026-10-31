import { FormEvent, useEffect, useState } from "react";
import { adminLogin } from "../api/client";
import { setAdminSession } from "../auth/adminSession";

interface AdminLoginProps {
  apiOnline: boolean | null;
  onSuccess: (username: string) => void;
}

export function AdminLogin({ apiOnline, onSuccess }: AdminLoginProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [focused, setFocused] = useState<string | null>(null);

  useEffect(() => {
    const t = window.setTimeout(() => setMounted(true), 60);
    return () => window.clearTimeout(t);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await adminLogin(username.trim(), password);
      setAdminSession(result.token, result.username);
      onSuccess(result.username);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`adm-login-scene${mounted ? " is-ready" : ""}`}>
      <section className="adm-login-showcase" aria-hidden>
        <div className="adm-login-showcase-bg" aria-hidden>
          <span className="adm-login-orb adm-login-orb--1" />
          <span className="adm-login-orb adm-login-orb--2" />
        </div>
        <div className="adm-login-showcase-inner">
          <div className="adm-login-lottie-ring">
            <span className="adm-login-ring adm-login-ring--1" />
            <span className="adm-login-ring adm-login-ring--2" />
            <img className="adm-login-mascot" src="/mascot/greeting.png" alt="Dhwani, the voice assistant" draggable={false} />
          </div>

          <h1 className="kn adm-login-title">ಕನ್ನಡ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್</h1>
          <p className="adm-login-tagline">Staff console · voice-first counter</p>

          <ul className="adm-login-perks">
            <li>
              <span className="adm-login-perk-icon">🎙</span>
              Hands-free Kannada
            </li>
            <li>
              <span className="adm-login-perk-icon">📡</span>
              Live lobby control
            </li>
            <li>
              <span className="adm-login-perk-icon">🔊</span>
              Suresh & Anu voices
            </li>
          </ul>
        </div>
      </section>

      <section className="adm-login-panel">
        <div className="adm-login-panel-inner">
          <header className="adm-login-head">
            <span className="adm-login-badge kn">ಕ</span>
            <div>
              <h2>Staff sign in</h2>
              <p className="kn">ಸಿಬ್ಬಂದಿ ಪ್ರವೇಶ</p>
            </div>
          </header>

          <form className="adm-login-form" onSubmit={(e) => void handleSubmit(e)}>
            {apiOnline === false && (
              <div className="adm-alert adm-alert--warn adm-login-alert" role="alert">
                Service unavailable — start the backend and try again.
              </div>
            )}
            {error && (
              <div className="adm-alert adm-alert--error adm-login-alert" role="alert">
                {error}
              </div>
            )}

            <label
              className={`adm-login-field${focused === "user" ? " is-focused" : ""}`}
              htmlFor="admin-user"
            >
              <span className="adm-login-field-label">Staff ID</span>
              <span className="adm-login-input-wrap">
                <span className="adm-login-input-icon" aria-hidden>
                  👤
                </span>
                <input
                  id="admin-user"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  onFocus={() => setFocused("user")}
                  onBlur={() => setFocused(null)}
                  autoComplete="username"
                  placeholder="Enter staff ID"
                  required
                />
              </span>
            </label>

            <label
              className={`adm-login-field${focused === "pass" ? " is-focused" : ""}`}
              htmlFor="admin-pass"
            >
              <span className="adm-login-field-label">Password</span>
              <span className="adm-login-input-wrap">
                <span className="adm-login-input-icon" aria-hidden>
                  🔒
                </span>
                <input
                  id="admin-pass"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onFocus={() => setFocused("pass")}
                  onBlur={() => setFocused(null)}
                  autoComplete="current-password"
                  placeholder="Enter password"
                  required
                />
              </span>
            </label>

            <button
              type="submit"
              className={`adm-login-submit${busy ? " is-loading" : ""}`}
              disabled={busy || apiOnline === false}
            >
              <span className="adm-login-submit-text">
                {busy ? "Signing in…" : "Sign in"}
              </span>
              {busy && <span className="adm-login-spinner" aria-hidden />}
            </button>
          </form>

          <footer className="adm-login-status">
            <span
              className={`adm-conn adm-conn--inline ${apiOnline ? "is-on" : apiOnline === false ? "is-off" : ""}`}
            >
              <span className="adm-conn-dot" aria-hidden />
              {apiOnline ? "Service online" : apiOnline === false ? "Service offline" : "Connecting…"}
            </span>
          </footer>
        </div>
      </section>
    </div>
  );
}
