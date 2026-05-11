import { describe, expect, it } from "vitest";
import { buildGroundTruthReviewPath } from "./routing";

describe("legacy route redirects", () => {
  it("preserves the ground-truth review run id when redirecting", () => {
    expect(buildGroundTruthReviewPath("run-123")).toBe("/learn/ground-truth-review/run-123");
  });

  it("falls back to the collection route when no run id is present", () => {
    expect(buildGroundTruthReviewPath()).toBe("/learn/ground-truth-review");
  });
});
