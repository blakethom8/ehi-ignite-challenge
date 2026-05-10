/**
 * Atlas trust-boundary types — frontend stub.
 *
 * The frontend redesign distinguishes Caspian (first-party / private
 * patient boundary) from plugins (installable / consented external).
 * Today the only encoding of that distinction in code is the single
 * `Workspace.family` field — enough for visual fidelity, not enough
 * to enforce trust.
 *
 * This file declares the contract the runtime should honor when the
 * backend wires real plugin execution. None of these types are
 * referenced by current components; they exist so future code has
 * something to import against, and so the architecture document
 * (`docs/architecture/AGENTIC-HARNESS.md`) has a concrete TS mirror.
 *
 * Backend mirror lives in `api/trust/models.py` (does not exist yet).
 *
 * STATUS: type-only scaffold. No runtime behavior. No verification.
 */

import type { WorkspaceId } from "./types";

// ============================================================
// Plugin identity
// ============================================================

/** A plugin id is the same shape as a marketplace WorkspaceId. */
export type PluginId = Exclude<WorkspaceId, "caspian">;

export type VendorIdentity = {
  /** Stable id for the publishing vendor. */
  id: string;
  /** Display name shown in the package home + boundary chip. */
  name: string;
  /** Public key fingerprint; manifest signatures verify against this. */
  keyFingerprint: string;
};

// ============================================================
// Plugin manifest — what a vendor publishes
// ============================================================

export type Permission =
  | { kind: "read-anchor"; scope: AnchorScopeField[] }
  | { kind: "call-external"; connector: ConnectorId }
  | { kind: "send-outbound"; channel: OutboundChannelId };

export type Connector = {
  id: ConnectorId;
  label: string;
  endpointPattern: string;
};

export type ConnectorId = string;
export type OutboundChannelId = string;
export type ExportKind = "markdown" | "json" | "shareable-bundle";
export type ModelPresetId =
  | "clinical-high"
  | "clinical-balanced"
  | "marketplace-act"
  | "draft";

export type PluginManifest = {
  id: PluginId;
  version: string; // semver
  vendor: VendorIdentity;
  /** Detached signature over the rest of the manifest. */
  signature: string;
  permissions: Permission[];
  connectors: Connector[];
  exports: ExportKind[];
  /** True if the plugin can produce outbound boundary crossings. */
  requiresConsent: boolean;
  modelPreset?: ModelPresetId;
};

// ============================================================
// Anchor package — what a plugin actually receives
// ============================================================

export type AnchorScopeField =
  | "demographics.age-band"
  | "demographics.sex"
  | "demographics.geography"
  | "diagnoses.active"
  | "diagnoses.history"
  | "medications.active"
  | "medications.history"
  | "allergies"
  | "biomarkers"
  | "labs.recent"
  | "encounters.recent"
  | "performance-status";

export type RedactionPreset =
  | "de-id-v1"
  | "de-id-v2"
  | "de-id-v3"
  | "research-grade"
  | "minimal";

export type AnchorScope = AnchorScopeField[];

/**
 * The patient-anchor handle a plugin receives at run time. The plugin
 * never reads the raw chart — it reads the AnchorPackage. Atlas
 * compiles this server-side and signs it; the plugin can't widen scope.
 */
export type AnchorPackage = {
  pluginId: PluginId;
  patientId: string;
  scope: AnchorScope;
  redactions: RedactionPreset;
  /** Detached signature over (pluginId, patientId, scope, redactions, issuedAt, expiresAt). */
  signature: string;
  issuedAt: string; // ISO 8601
  expiresAt: string; // ISO 8601 — anchor packages expire
};

// ============================================================
// Provenance — what gets recorded for every outbound action
// ============================================================

export type OutboundActionKind =
  | "send-packet"
  | "register-patient"
  | "submit-application"
  | "schedule-followup"
  | "post-update";

export type UserIdentity = {
  id: string;
  name: string;
  role: "clinician" | "attending" | "coordinator" | "admin";
};

/**
 * Append-only audit row written every time a plugin crosses the
 * consented external boundary. The provenance log is what makes
 * "consented external" meaningful — without it, the boundary pill is
 * theatre.
 */
export type ProvenanceRecord = {
  runId: string;
  pluginId: PluginId;
  pluginVersion: string;
  vendor: VendorIdentity;
  action: OutboundActionKind;
  approver: UserIdentity;
  redactionPreset: RedactionPreset;
  /** What was sent (artifact id), if applicable. */
  artifactId?: string;
  ts: string; // ISO 8601
};

// ============================================================
// Approval shapes (Caspian vs Plugin diverge here)
// ============================================================

/**
 * Clinical-state approval — Caspian's approval shape. Reversible,
 * recorded in the clinical audit log, not provenance.
 */
export type CaspianApprovalRequest = {
  kind: "clinical";
  runId: string;
  description: string;
  /** What clinical state changes if approved. */
  effect: string;
  /** Approver role required. */
  approverRole: UserIdentity["role"];
};

/**
 * Outbound-boundary approval — plugin's approval shape. Each outbound
 * action is gated; per-run consent must be granted before per-action
 * approvals fire.
 */
export type PluginApprovalRequest = {
  kind: "outbound";
  runId: string;
  pluginId: PluginId;
  action: OutboundActionKind;
  description: string;
  /** Snapshot of what would be sent. Approver reviews this verbatim. */
  payloadPreview: string;
  redactionPreset: RedactionPreset;
  approverRole: UserIdentity["role"];
};

export type ApprovalRequest = CaspianApprovalRequest | PluginApprovalRequest;
