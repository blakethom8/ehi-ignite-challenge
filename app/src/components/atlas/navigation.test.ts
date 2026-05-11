import { describe, expect, it } from "vitest";
import { deriveActiveModule, hrefForModule } from "./navigation";

describe("atlas module navigation", () => {
  it("classifies legacy aliases under their current top-level module", () => {
    expect(deriveActiveModule("/records-pool")).toBe("home");
    expect(deriveActiveModule("/aggregate/context")).toBe("patient-record");
    expect(deriveActiveModule("/explorer/assistant")).toBe("fhir-charts");
    expect(deriveActiveModule("/marketplace")).toBe("workspaces");
    expect(deriveActiveModule("/ground-truth-review/demo-run")).toBe("learn");
  });

  it("resolves canonical module hrefs", () => {
    expect(hrefForModule("home")).toBe("/");
    expect(hrefForModule("patient-record")).toBe("/patient-record");
    expect(hrefForModule("fhir-charts")).toBe("/fhir-charts");
    expect(hrefForModule("caspian")).toBe("/caspian");
    expect(hrefForModule("workspaces")).toBe("/workspaces");
    expect(hrefForModule("learn")).toBe("/learn");
  });
});
