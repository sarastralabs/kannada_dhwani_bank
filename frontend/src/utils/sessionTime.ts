/** Target length of one customer visit. Past it the timer keeps counting the extra time. */
export const SESSION_TARGET_S = 180;

/** 75 → "1:15", 3725 → "62:05". */
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Seconds a kiosk session lasted (or has lasted so far, while still open). */
export function sessionSeconds(
  session: { started_at: string; ended_at: string | null },
  nowMs = Date.now(),
): number | null {
  const start = Date.parse(session.started_at);
  if (Number.isNaN(start)) return null;
  const end = session.ended_at ? Date.parse(session.ended_at) : nowMs;
  if (Number.isNaN(end)) return null;
  return Math.max(0, Math.round((end - start) / 1000));
}
