import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import Root from "./Root";
import "@fontsource/anek-kannada/kannada-500.css";
import "@fontsource/anek-kannada/kannada-600.css";
import "@fontsource/anek-kannada/kannada-700.css";
import "@fontsource/anek-kannada/kannada-800.css";
import "@fontsource/noto-sans-kannada/kannada-400.css";
import "@fontsource/noto-sans-kannada/kannada-500.css";
import "@fontsource/noto-sans-kannada/kannada-600.css";
import "@fontsource/noto-sans-kannada/kannada-700.css";
import "@fontsource/noto-sans-kannada/latin-400.css";
import "@fontsource/noto-sans-kannada/latin-700.css";
import "@fontsource/sora/latin-400.css";
import "@fontsource/sora/latin-500.css";
import "@fontsource/sora/latin-600.css";
import "@fontsource/sora/latin-700.css";
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
