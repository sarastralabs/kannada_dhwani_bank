import { useMemo } from "react";

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
              <img
                key={p}
                className={`mascot-pose${p === pose ? " is-active" : ""}`}
                src={`/mascot/${p}.png`}
                alt=""
                draggable={false}
                decoding="async"
              />
            ))}
          </div>
        </div>

        <p className="agent-mascot-bubble">{label}</p>
      </div>
    </div>
  );
}
