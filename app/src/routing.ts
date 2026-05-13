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

export function buildAccountAccessPath(next?: string | null): string {
  if (!next) return "/account";
  const params = new URLSearchParams();
  params.set("next", next);
  return `/account?${params.toString()}`;
}

import type { AuthMode } from "./types";

type PatientContextOptions = {
  mode?: AuthMode | null;
};

export function supportsPatientContext(mode: AuthMode | null | undefined): boolean {
  return mode === "authenticated" || mode === "demo";
}

export function withPatientContext(
  path: string,
  patientId: string | null,
  options?: PatientContextOptions,
): string {
  if (!patientId) return path;
  if (options?.mode && !supportsPatientContext(options.mode)) return path;
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

export function resolveAccountDestination(next: string | null): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/account")) {
    return null;
  }
  return next;
}
