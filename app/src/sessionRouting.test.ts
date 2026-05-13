import { describe, expect, it } from "vitest";
import {
  resolveInvalidPatientRedirect,
  resolveModulePath,
  resolveSessionHomePath,
  resolveSessionWorkspaceHubPath,
} from "./sessionRouting";

describe("sessionRouting", () => {
  it("routes anonymous users to the public home", () => {
    expect(resolveSessionHomePath("anonymous", null)).toBe("/");
    expect(resolveSessionWorkspaceHubPath("anonymous", null)).toBe("/");
  });

  it("routes authenticated users without an active patient to file intake", () => {
    expect(resolveSessionHomePath("authenticated", null)).toBe("/patient-record/sources");
    expect(resolveSessionWorkspaceHubPath("authenticated", null)).toBe("/patient-record/sources");
    expect(resolveModulePath("patient-record", "authenticated", null)).toBe("/patient-record/sources");
    expect(resolveModulePath("fhir-charts", "authenticated", null)).toBe("/patient-record/sources");
    expect(resolveModulePath("caspian", "authenticated", null)).toBe("/patient-record/sources");
  });

  it("routes authenticated users with an active patient back into the workspace", () => {
    expect(resolveSessionHomePath("authenticated", "patient-123")).toBe("/patient-record?patient=patient-123");
    expect(resolveSessionWorkspaceHubPath("authenticated", "patient-123")).toBe("/records-pool?patient=patient-123");
  });

  it("routes demo users back into their demo chart context", () => {
    expect(resolveSessionHomePath("demo", "demo-high-risk")).toBe("/patient-record?patient=demo-high-risk");
    expect(resolveSessionWorkspaceHubPath("demo", "demo-high-risk")).toBe("/records-pool?patient=demo-high-risk");
    expect(resolveSessionHomePath("demo", null)).toBe("/demo");
  });

  it("routes invalid patient state back to the right recovery screen", () => {
    expect(resolveInvalidPatientRedirect("authenticated")).toBe("/patient-record/sources");
    expect(resolveInvalidPatientRedirect("demo")).toBe("/demo");
    expect(resolveInvalidPatientRedirect("guest")).toBe("/guest-harmonization");
    expect(resolveInvalidPatientRedirect("anonymous")).toBe("/");
  });
});
