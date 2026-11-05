import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import Root from "./Root";
import "./index.css";
import "./agent.css";
import "./conversation.css";
import "./theme.css";
import "./mascot.css";
import "./kiosk-theme.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
