import { useCallback, useEffect, useRef, useState } from "react";
import { CHAT } from "./content";
import { Icon } from "./Icons";

const reduced = () =>
  typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * A phone showing a sample conversation. It plays once when scrolled into view: the customer's
 * lines appear, the assistant "types" for a moment, then answers. Everything is shown at once
 * for people who asked their device to reduce motion.
 */
export function ChatPreview() {
  const total = CHAT.messages.length;
  const [shown, setShown] = useState(0);
  const [typing, setTyping] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const started = useRef(false);
  const timers = useRef<number[]>([]);

  const clear = () => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  };

  const play = useCallback(() => {
    clear();
    if (reduced()) {
      setShown(total);
      setTyping(false);
      return;
    }
    setShown(0);
    setTyping(false);
    let at = 350;
    CHAT.messages.forEach((m, i) => {
      if (m.who === "agent") {
        timers.current.push(window.setTimeout(() => setTyping(true), at));
        at += 1100;
      } else {
        at += 500;
      }
      timers.current.push(
        window.setTimeout(() => {
          setTyping(false);
          setShown(i + 1);
        }, at),
      );
      at += 650;
    });
  }, [total]);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setShown(total);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true;
          play();
        }
      },
      { threshold: 0.35 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      clear();
    };
  }, [play, total]);

  // Keep the newest message in view inside the phone, without scrolling the page itself.
  const bodyRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const body = bodyRef.current;
    if (body) body.scrollTop = body.scrollHeight;
  }, [shown, typing]);

  const done = shown >= total;

  return (
    <div className="lp-phone" ref={rootRef}>
      <div className="lp-phone-frame">
        <div className="lp-phone-top" aria-hidden>
          <img src="/mascot/greeting.png" alt="" width={36} height={36} />
          <strong>{CHAT.agent}</strong>
          <span className="lp-phone-live" />
        </div>
        <div className="lp-phone-body" ref={bodyRef} role="log" aria-live="polite" aria-label={CHAT.title}>
          {CHAT.messages.slice(0, shown).map((m, i) => (
            <div key={i} className={`lp-msg lp-msg--${m.who}`}>
              <span className="lp-msg-who">{m.who === "agent" ? CHAT.agent : CHAT.you}</span>
              <p>{m.text}</p>
            </div>
          ))}
          {typing && (
            <div className="lp-msg lp-msg--agent lp-msg--typing" aria-label={CHAT.typing}>
              <span className="lp-msg-who">{CHAT.agent}</span>
              <p aria-hidden>
                <i />
                <i />
                <i />
              </p>
            </div>
          )}
        </div>
      </div>
      <div className="lp-phone-foot">
        <span>{CHAT.sample}</span>
        {done && (
          <button type="button" className="lp-link-btn" onClick={play}>
            <Icon name="replay" size={16} /> {CHAT.replay}
          </button>
        )}
      </div>
    </div>
  );
}
