import { useEffect, useState } from "react";

/**
 * Two screens share one app:
 *   /        landing page (what the assistant is, what to say, the big "ಏಜೆಂಟ್" button)
 *   /agent   the voice kiosk
 *
 * Cloudflare serves the app for every path, so deep links like /agent just work. Moving between
 * them uses the History API (no page reload), which keeps the tap that started it as the
 * "user gesture" browsers require before they allow sound and the microphone.
 */
export type Route = "landing" | "agent";

export const AGENT_PATH = "/agent";

export function routeFor(pathname: string): Route {
  const path = pathname.replace(/\/+$/, "");
  return path === AGENT_PATH || path.startsWith(`${AGENT_PATH}/`) ? "agent" : "landing";
}

export function navigate(path: string): void {
  if (window.location.pathname !== path) window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => routeFor(window.location.pathname));
  useEffect(() => {
    const sync = () => setRoute(routeFor(window.location.pathname));
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  return route;
}
