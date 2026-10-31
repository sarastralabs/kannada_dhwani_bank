import { useEffect, useRef, useState } from "react";
import { checkHealth } from "./api/client";
import { AgentLobby } from "./components/AgentLobby";
import { startVisibilityAwarePoll } from "./utils/polling";

/**
 * Lobby Agent frontend only (port 5173).
 * Admin console runs separately on port 5174.
 */
export default function App() {
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const failStreak = useRef(0);
  const hasConnected = useRef(false);
  const startupGraceUntil = useRef(Date.now() + 60_000);

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    const applyHealth = (ok: boolean) => {
      if (ok) {
        hasConnected.current = true;
        failStreak.current = 0;
        setApiOnline(true);
        return;
      }
      if (!hasConnected.current && Date.now() < startupGraceUntil.current) return;
      failStreak.current += 1;
      if (failStreak.current >= 3) {
        setApiOnline(false);
      }
    };

    const probe = () => {
      checkHealth().then((ok) => {
        if (cancelled) return;
        applyHealth(ok);
        if (!ok && attempts < 10) {
          attempts += 1;
          window.setTimeout(probe, 1500);
        }
      });
    };
    probe();

    const stop = startVisibilityAwarePoll(() => {
      checkHealth().then((ok) => {
        if (!cancelled) applyHealth(ok);
      });
    }, 10000, 30000);

    return () => {
      cancelled = true;
      stop();
    };
  }, []);

  return <AgentLobby apiOnline={apiOnline} />;
}
