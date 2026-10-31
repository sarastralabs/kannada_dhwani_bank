export type AdminView = "overview" | "conversations" | "forms" | "customers" | "settings" | "guide";

export const VIEWS: Array<{ id: AdminView; en: string; kn: string; icon: string; hash: string }> = [
  { id: "overview", en: "Overview", kn: "ಅವಲೋಕನ", icon: "overview", hash: "" },
  { id: "conversations", en: "Conversations", kn: "ಸಂಭಾಷಣೆಗಳು", icon: "conversations", hash: "#conversations" },
  { id: "forms", en: "Form submissions", kn: "ಅರ್ಜಿಗಳು", icon: "forms", hash: "#forms" },
  { id: "customers", en: "Customers", kn: "ಗ್ರಾಹಕರು", icon: "customers", hash: "#customers" },
  { id: "settings", en: "Settings", kn: "ಸೆಟ್ಟಿಂಗ್‌ಗಳು", icon: "settings", hash: "#settings" },
  { id: "guide", en: "How it works", kn: "ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ", icon: "guide", hash: "#guide" },
];

/** Old links (#speech-history, #conversation-flow, #form-submissions) keep working. */
export function viewFromHash(hash: string): AdminView {
  const h = hash.replace(/^#/, "").toLowerCase();
  if (h.startsWith("conversation-flow") || h.startsWith("flow") || h.startsWith("guide")) return "guide";
  if (h.startsWith("conversations") || h.startsWith("speech")) return "conversations";
  if (h.startsWith("form")) return "forms";
  if (h.startsWith("customers")) return "customers";
  if (h.startsWith("settings")) return "settings";
  return "overview";
}
