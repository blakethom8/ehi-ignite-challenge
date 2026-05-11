export function buildGroundTruthReviewPath(runId?: string): string {
  return runId
    ? `/learn/ground-truth-review/${encodeURIComponent(runId)}`
    : "/learn/ground-truth-review";
}
