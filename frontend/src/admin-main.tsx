import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AdminApp } from "./AdminApp";
import "./index.css";
import "./admin.css";
import "./admin-console.css";
import "./theme.css";
import "./mascot.css";
import "./admin-theme.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AdminApp />
  </StrictMode>,
);
