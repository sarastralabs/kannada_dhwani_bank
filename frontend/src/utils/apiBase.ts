/**
 * API base URL for fetch calls.
 * Default "" = same origin (/api/* via Vite dev proxy) — works on PC and phone over LAN.
 * Override with VITE_API_BASE in .env.local if calling the API directly.
 */
export function getApiBase(): string {
  const env = import.meta.env.VITE_API_BASE as string | undefined;
  if (env !== undefined && env.trim() !== "") {
    return env.replace(/\/$/, "");
  }
  return "";
}

/** Known Cloudflare host → agent lobby (admin “open lobby” links). */
const CLOUDFLARE_AGENT_URL: Record<string, string> = {
  "admin.sarastralabs.com": "https://agent.sarastralabs.com",
};

/** Agent lobby URL for admin "open lobby" links — http on localhost, same protocol elsewhere. */
export function getLobbyUrl(): string {
  const env = import.meta.env.VITE_AGENT_URL as string | undefined;
  if (env?.trim()) {
    return env.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    const mapped = CLOUDFLARE_AGENT_URL[host];
    if (mapped) return mapped;
    // localhost / 127.0.0.1: mic works on http, so use http for local dev
    if (host === "localhost" || host === "127.0.0.1") {
      return `http://${host}:5173`;
    }
    return `${window.location.protocol}//${host}:5173`;
  }
  return "http://127.0.0.1:5173";
}
