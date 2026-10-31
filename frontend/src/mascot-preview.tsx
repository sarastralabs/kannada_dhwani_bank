/**
 * Dev-only page: http://localhost:5173/mascot-preview.html?mood=speaking
 * Shows the mascot in any mood; window.mouth(level) feeds it a voice level (0..1) by hand.
 * Not part of the production build (vite.config.ts only builds index.html).
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import "./agent.css";
import "./conversation.css";
import "./theme.css";
import "./mascot.css";
import { AgentMascot, type MascotMood } from "./components/AgentMascot";
import { publishMouthLevel } from "./utils/lipsync";

const params = new URLSearchParams(window.location.search);
const mood = (params.get("mood") ?? "speaking") as MascotMood;
(window as unknown as { mouth: (n: number) => void }).mouth = publishMouthLevel;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <div className="lobby-shell" style={{ display: "grid", placeItems: "center", minHeight: "100dvh" }}>
      <AgentMascot mood={mood} className="lobby-bot-hero" />
    </div>
  </StrictMode>,
);
