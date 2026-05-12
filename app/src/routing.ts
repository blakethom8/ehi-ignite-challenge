export function buildGroundTruthReviewPath(runId?: string): string {
  return runId
    ? `/learn/ground-truth-review/${encodeURIComponent(runId)}`
    : "/learn/ground-truth-review";
}

export function buildDemoSelectionPath(patientId?: string | null, next?: string | null): string {
  const params = new URLSearchParams();
  if (patientId) {
    params.set("patient", patientId);
  }
  if (next) {
    params.set("next", next);
  }
  const search = params.toString();
  return search ? `/demo?${search}` : "/demo";
}

export function withPatientContext(path: string, patientId: string | null): string {
  if (!patientId) return path;
  const url = new URL(path, "http://atlas.local");
  url.searchParams.set("patient", patientId);
  return `${url.pathname}${url.search}${url.hash}`;
}

export function resolveDemoDestination(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) {
    return "/patient-record";
  }
  return next;
}
