import type { AuthMode } from "./types";
import { withPatientContext } from "./routing";

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
  if (mode === "guest") {
    return "/guest-harmonization";
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

export function resolveModulePath(
  moduleId: "home" | "patient-record" | "fhir-charts" | "caspian" | "workspaces" | "learn",
  mode: AuthMode,
  activePatientId: string | null,
): string {
  if (moduleId === "home") {
    return resolveSessionHomePath(mode, activePatientId);
  }
  if (activePatientId) {
    const basePath = moduleId === "patient-record"
      ? "/patient-record"
      : moduleId === "fhir-charts"
      ? "/fhir-charts"
      : moduleId === "caspian"
      ? "/caspian"
      : "/workspaces";
    return withPatientContext(basePath, activePatientId);
  }
  if (mode === "authenticated" && moduleId !== "workspaces") {
    return "/patient-record/sources";
  }
  if (moduleId === "patient-record") return "/patient-record";
  if (moduleId === "fhir-charts") return "/fhir-charts";
  if (moduleId === "caspian") return "/caspian";
  if (moduleId === "learn") return "/learn";
  return "/workspaces";
}

export function resolveInvalidPatientRedirect(mode: AuthMode): string {
  if (mode === "authenticated") return "/patient-record/sources";
  if (mode === "demo") return "/demo";
  if (mode === "guest") return "/guest-harmonization";
  return "/";
}
