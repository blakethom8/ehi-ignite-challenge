import { describe, expect, it } from "vitest";
import { buildGroundTruthReviewPath, supportsPatientContext, withPatientContext } from "./routing";

describe("legacy route redirects", () => {
  it("preserves the ground-truth review run id when redirecting", () => {
    expect(buildGroundTruthReviewPath("run-123")).toBe("/learn/ground-truth-review/run-123");
  });

  it("falls back to the collection route when no run id is present", () => {
    expect(buildGroundTruthReviewPath()).toBe("/learn/ground-truth-review");
  });

  it("only carries patient context for patient-scoped session modes", () => {
    expect(supportsPatientContext("authenticated")).toBe(true);
    expect(supportsPatientContext("demo")).toBe(true);
    expect(supportsPatientContext("guest")).toBe(false);
    expect(withPatientContext("/workspaces/trial-finder", "demo-123", { mode: "guest" })).toBe("/workspaces/trial-finder");
    expect(withPatientContext("/workspaces/trial-finder#summary", "demo-123", { mode: "demo" })).toBe("/workspaces/trial-finder?patient=demo-123#summary");
  });
});
