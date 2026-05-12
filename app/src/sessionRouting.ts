import type { AuthMode } from "./types";

function withPatientContext(path: string, patientId: string | null): string {
  if (!patientId || path === "/") return path;
  const url = new URL(path, "http://atlas.local");
  url.searchParams.set("patient", patientId);
  return `${url.pathname}${url.search}`;
}

export function resolveSessionHomePath(mode: AuthMode, activePatientId: string | null): string {
  if (activePatientId) {
    return withPatientContext("/patient-record", activePatientId);
  }
  if (mode === "authenticated") {
    return "/patient-record/sources";
  }
  if (mode === "demo") {
    return "/demo";
  }
  return "/";
}

export function resolveSessionWorkspaceHubPath(mode: AuthMode, activePatientId: string | null): string {
  if (mode === "anonymous") {
    return "/";
  }
  if (activePatientId) {
    return withPatientContext("/records-pool", activePatientId);
  }
  if (mode === "authenticated") {
    return "/patient-record/sources";
  }
  return "/demo";
}

export function resolveAccountPath(mode: AuthMode, hasUser: boolean): string {
  return mode === "authenticated" && hasUser ? "/account/settings" : "/account";
}
