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
import "./kiosk-theme.css";
import { CustomerCard } from "./components/HandsFreeConversation";

const params = new URLSearchParams(window.location.search);
const mood = (params.get("mood") ?? "speaking") as MascotMood;
(window as unknown as { mouth: (n: number) => void }).mouth = publishMouthLevel;

const SAMPLE = {
  found: true,
  name: "ರಾಮಕೃಷ್ಣ ಹೆಗಡೆ",
  message_kn: "",
  accounts: [{ last4: "4438", account_type: "Savings", balance_inr: 60000 }],
  loans: [{ loan_type: "personal", outstanding_inr: 91000, emi_inr: 8884.88 }],
  deposits: [{ principal_inr: 10000, maturity_inr: 10669.5, matures_on: "2027-10-31" }],
  transactions: [
    { kind: "deposit", amount: 50000, balance_after: 50000, at: "", last4: "4438" },
    { kind: "loan_disbursal", amount: 20000, balance_after: 70000, at: "", last4: "4438" },
    { kind: "fd_open", amount: 10000, balance_after: 60000, at: "", last4: "4438" },
  ],
  applications: [
    { ref: "DH-26-000003", title_kn: "ಸಾಲ ಅರ್ಜಿ", status: "approved", status_kn: "ಅನುಮೋದಿಸಲಾಗಿದೆ" },
    { ref: "DH-26-000004", title_kn: "ಚೆಕ್ ಪುಸ್ತಕ", status: "submitted", status_kn: "ಪರಿಶೀಲನೆಯಲ್ಲಿದೆ" },
  ],
};

if (params.get("view") === "customer") {
  createRoot(document.getElementById("root")!).render(
    <div className="lobby-shell" style={{ minHeight: "100dvh", padding: "1rem" }}>
      <div style={{ maxWidth: 640, margin: "0 auto" }}>
        <section className="hf-details-card">
          <h2 className="hf-details-title">ನಿಮ್ಮ ವಿವರಗಳು</h2>
          <CustomerCard info={SAMPLE} />
        </section>
      </div>
    </div>,
  );
} else createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <div className="lobby-shell" style={{ display: "grid", placeItems: "center", minHeight: "100dvh" }}>
      <AgentMascot mood={mood} className="lobby-bot-hero" />
    </div>
  </StrictMode>,
);
