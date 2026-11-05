import { describe, expect, it } from "vitest";
import { routeFor } from "./router";
import { withAgentPath } from "./utils/apiBase";

describe("routes", () => {
  it.each(["/", "", "/index.html", "/anything", "/agentx", "/about"])("%s is the landing page", (p) => {
    expect(routeFor(p)).toBe("landing");
  });

  it.each(["/agent", "/agent/", "/agent/session"])("%s is the agent", (p) => {
    expect(routeFor(p)).toBe("agent");
  });
});

describe("agent address for the admin console", () => {
  it("adds /agent to a bare address and leaves a full one alone", () => {
    expect(withAgentPath("https://dhwani.sarastralabs.com")).toBe("https://dhwani.sarastralabs.com/agent");
    expect(withAgentPath("https://dhwani.sarastralabs.com/")).toBe("https://dhwani.sarastralabs.com/agent");
    expect(withAgentPath("https://dhwani.sarastralabs.com/agent")).toBe("https://dhwani.sarastralabs.com/agent");
    expect(withAgentPath("http://localhost:5173")).toBe("http://localhost:5173/agent");
  });
});
