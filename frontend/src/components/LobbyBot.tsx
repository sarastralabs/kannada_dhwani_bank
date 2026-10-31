import { AgentMascot, type MascotMood } from "./AgentMascot";

interface LobbyBotProps {
  mood?: MascotMood;
  className?: string;
}

export function LobbyBot({ mood = "waiting", className = "" }: LobbyBotProps) {
  return <AgentMascot mood={mood} className={className} />;
}

export type { MascotMood };
