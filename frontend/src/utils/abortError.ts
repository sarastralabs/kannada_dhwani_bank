/** Request exceeded fetchWithTimeout budget (not intentional cleanup). */
export class FetchTimeoutError extends Error {
  constructor(timeoutMs: number) {
    super(`Request timed out after ${Math.round(timeoutMs / 1000)}s`);
    this.name = "FetchTimeoutError";
  }
}

export function isTimeoutError(err: unknown): boolean {
  if (err instanceof FetchTimeoutError) return true;
  if (err instanceof DOMException && err.name === "TimeoutError") return true;
  if (err instanceof Error) {
    if (err.name === "TimeoutError") return true;
    if (err.message.toLowerCase().includes("timed out")) return true;
  }
  return false;
}

/** True when a fetch/play/listen was cancelled intentionally (React cleanup, new turn, etc.). */
export function isAbortError(err: unknown): boolean {
  if (isTimeoutError(err)) return false;
  if (err instanceof DOMException && err.name === "AbortError") return true;
  if (err instanceof Error) {
    if (err.name === "AbortError") return true;
    const msg = err.message.toLowerCase();
    if (msg.includes("abort") || msg.includes("aborted")) return true;
  }
  return false;
}

export function userFacingFetchError(err: unknown): string {
  if (isTimeoutError(err)) {
    return "ಸೇವೆ ನಿಧಾನವಾಗಿದೆ — ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ";
  }
  if (isAbortError(err)) return "";
  return "ಸಮಸ್ಯೆ ಆಯಿತು. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ.";
}
