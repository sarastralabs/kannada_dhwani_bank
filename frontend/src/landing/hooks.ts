import { useCallback, useEffect, useState } from "react";

const prefersReducedMotion = () =>
  typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Fade sections in as they scroll into view (everything is simply shown when motion is reduced). */
export function useReveal(key?: unknown): void {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>(".lp-reveal:not(.is-in)"));
    if (prefersReducedMotion() || typeof IntersectionObserver === "undefined") {
      els.forEach((el) => el.classList.add("is-in"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -6% 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [key]);
}

/** Text size for people who find the type small: 100%, 112.5%, 125% of the browser's own size. */
export const TEXT_SIZES = [100, 112.5, 125] as const;
const STORAGE_KEY = "dhwani.landing.textSize";

export function useTextSize(): { level: number; cycle: () => void } {
  const [level, setLevel] = useState(() => {
    try {
      const saved = Number(window.localStorage.getItem(STORAGE_KEY));
      return Number.isInteger(saved) && saved >= 0 && saved < TEXT_SIZES.length ? saved : 0;
    } catch {
      return 0;
    }
  });

  useEffect(() => {
    document.documentElement.style.fontSize = `${TEXT_SIZES[level]}%`;
    try {
      window.localStorage.setItem(STORAGE_KEY, String(level));
    } catch {
      /* storage can be blocked — the size still applies for this visit */
    }
    return () => {
      document.documentElement.style.fontSize = ""; // the kiosk keeps its own sizes
    };
  }, [level]);

  const cycle = useCallback(() => setLevel((l) => (l + 1) % TEXT_SIZES.length), []);
  return { level, cycle };
}
