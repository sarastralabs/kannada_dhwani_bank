import { useEffect, useMemo, useState } from "react";
import { levelToFrame, MOUTH_FRAMES, onMouthLevel } from "../utils/lipsync";

export type MascotMood =
  | "waiting"
  | "ready"
  | "greeting"
  | "listening"
  | "thinking"
  | "speaking"
  | "happy"
  | "confused";

const POSES = ["greeting", "listening", "thinking", "speaking", "happy", "confused"] as const;
type Pose = (typeof POSES)[number];

const POSE_FOR_MOOD: Record<MascotMood, Pose> = {
  waiting: "greeting",
  ready: "greeting",
  greeting: "greeting",
  listening: "listening",
  thinking: "thinking",
  speaking: "speaking",
  happy: "happy",
  confused: "confused",
};

/** Poses with open eyes get a blink layer (the happy pose already has them shut). */
const BLINK_POSES: ReadonlySet<Pose> = new Set<Pose>(["greeting", "listening", "thinking", "speaking", "confused"]);
/** Poses whose mouth moves with the voice. */
const TALKING_POSE: Pose = "speaking";
const MOUTHS = Array.from({ length: MOUTH_FRAMES }, (_, i) => i);

interface AgentMascotProps {
  mood?: MascotMood;
  className?: string;
}

/**
 * Dhwani mascot — one illustrated pose per mood, crossfaded, with CSS motion.
 */
export function AgentMascot({ mood = "waiting", className = "" }: AgentMascotProps) {
  const label = useMemo(() => {
    switch (mood) {
      case "greeting":
        return "ನಮಸ್ಕಾರ!";
      case "listening":
        return "ಕೇಳುತ್ತಿದ್ದೇನೆ…";
      case "thinking":
        return "ಯೋಚಿಸುತ್ತಿದ್ದೇನೆ…";
      case "speaking":
        return "ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ…";
      case "ready":
        return "ಸಿದ್ಧ!";
      case "happy":
        return "ಮುಗಿಯಿತು!";
      case "confused":
        return "ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ";
      default:
        return "ಕಾಯುತ್ತಿದ್ದೇನೆ…";
    }
  }, [mood]);

  const pose = POSE_FOR_MOOD[mood];
  const blinking = useBlink();
  const mouth = useMouthFrame(mood === "speaking");

  return (
    <div
      className={`agent-mascot agent-mascot-${mood} ${className}`}
      role="status"
      aria-label={label}
    >
      <div className="agent-mascot-glow" />
      <div className="agent-mascot-rings" aria-hidden>
        <span />
        <span />
        <span />
      </div>
      <div className="agent-mascot-stage">
        <div className="agent-mascot-svg mascot-figure" aria-hidden>
          <span className="mascot-shadow" />
          <div className="mascot-body-group">
            {POSES.map((p) => (
              <div key={p} className={`mascot-pose${p === pose ? " is-active" : ""}`}>
                <img className="mascot-pose-img" src={`/mascot/${p}.png`} alt="" draggable={false} decoding="async" />
                {BLINK_POSES.has(p) && (
                  <img
                    className={`mascot-layer${blinking && p === pose ? " is-on" : ""}`}
                    src={`/mascot/blink-${p}.png`}
                    alt=""
                    draggable={false}
                  />
                )}
                {p === TALKING_POSE &&
                  MOUTHS.map((i) => (
                    <img
                      key={i}
                      className={`mascot-layer${mouth === i ? " is-on" : ""}`}
                      src={`/mascot/mouth-${p}-${i}.png`}
                      alt=""
                      draggable={false}
                    />
                  ))}
              </div>
            ))}
          </div>
        </div>

        <p className="agent-mascot-bubble">{label}</p>
      </div>
    </div>
  );
}

/** Natural blinking: every 2.5–5.5 s, sometimes twice in a row. */
function useBlink(): boolean {
  const [blinking, setBlinking] = useState(false);
  useEffect(() => {
    let timer = 0;
    let alive = true;
    const later = (ms: number, fn: () => void) => {
      timer = window.setTimeout(() => alive && fn(), ms);
    };
    const wait = () => later(2500 + Math.random() * 3000, blink);
    const blink = () => {
      setBlinking(true);
      later(130, () => {
        setBlinking(false);
        if (Math.random() < 0.2) {
          later(150, () => {
            setBlinking(true);
            later(120, () => {
              setBlinking(false);
              wait();
            });
          });
        } else {
          wait();
        }
      });
    };
    wait();
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, []);
  return blinking;
}

/** Mouth shape (0 closed … 3 wide) while the assistant is speaking; -1 = leave the artwork's own mouth. */
function useMouthFrame(speaking: boolean): number {
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    if (!speaking) {
      setFrame(0);
      return;
    }
    return onMouthLevel((level) => {
      const next = levelToFrame(level);
      setFrame((f) => (f === next ? f : next));
    });
  }, [speaking]);
  return speaking ? frame : -1;
}
