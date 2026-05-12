/**
 * Atlas trust-boundary types — frontend contract.
 *
 * The frontend redesign distinguishes Caspian (first-party / private
 * patient boundary) from plugins (installable / consented external).
 *
 * This file is the canonical TS mirror of the runtime contract. The
 * backend mirror lives in `api/trust/models.py`. The full design
 * intent is documented in `docs/product-specs/PLUGIN-RUNTIME.md` and
 * `docs/architecture/AGENTIC-HARNESS.md`.
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

export type ConnectorAuth = "none" | "vendor-token" | "user-delegated";

export type Connector = {
  id: ConnectorId;
  label: string;
  endpointPattern: string;
  auth: ConnectorAuth;
};

export type ConnectorId = string;
export type OutboundChannelId = string;
export type ExportKind = "markdown" | "json" | "shareable-bundle";

export type ModelPresetId =
  | "clinical-high"
  | "clinical-balanced"
  | "marketplace-act"
  | "draft";

export type TrustPosture = {
  posture: "consented-external" | "internal-cohort";
  boundaryLabel: string;
  requiresPerRunConsent: boolean;
};

export type AnchorSpec = {
  scope: AnchorScopeField[];
  redactionPreset: RedactionPreset;
  ttlSeconds: number;
};

export type PluginToolDecl = {
  id: string;
  label: string;
  category:
    | "clinical-trial"
    | "patient"
    | "external"
    | "outbound"
    | "artifact"
    | "transparency";
  permission: "read-anchor" | "call-external" | "send-outbound";
};

export type WorkflowDecl = {
  id: string;
  title: string;
  description: string;
  tags: string[];
  needs: string[];
  produces: string[];
};

export type WorkbenchKind =
  | "trial-board"
  | "candidate-detail"
  | "eligibility-form"
  | "barriers-list"
  | "pa-form"
  | "manufacturer-program-matcher"
  | "specialty-picker"
  | "referral-packet"
  | "network-status-board"
  | "packet-outline"
  | "anticoag-note"
  | "preop-brief"
  | "summary-json"
  | "diff"
  | "manifest-json"
  | "workflow-artifact"
  | "workspace-file";

export type WorkbenchRenderer =
  | "trial.board"
  | "trial.detail"
  | "form.eligibility"
  | "list.barriers"
  | "form.pa"
  | "matcher.manufacturer"
  | "picker.specialty"
  | "packet.referral"
  | "board.network-status"
  | "markdown.doc"
  | "json.viewer"
  | "diff.unified"
  | "workflow.artifact"
  | "workspace.file";

export type WorkbenchTabSpec = {
  id: string;
  label: string;
  kind: WorkbenchKind;
  renderer: WorkbenchRenderer;
};

export type PluginFileSeed = {
  group: string;
  name: string;
  icon: string;
  dirty?: boolean;
};

export type PluginUISpec = {
  homeSections: Array<
    | "hero"
    | "permissions-ledger"
    | "workflows"
    | "recent-runs"
    | "about"
    | "tasks"
    | "calendar"
  >;
  workbenchTabs: WorkbenchTabSpec[];
  files: PluginFileSeed[];
  agent: {
    avatarInitials: string;
    avatarColor: string; // CSS var ok
    modelPreset: ModelPresetId;
  };
};

export type PluginManifest = {
  schemaVersion: string;
  id: PluginId;
  version: string; // semver
  vendor: VendorIdentity;
  displayName: string;
  subtitle: string;
  description: string;
  icon: string;
  color: string;
  trust: TrustPosture;
  anchor: AnchorSpec;
  connectors: Connector[];
  permissions: Permission[];
  workflows: WorkflowDecl[];
  tools: PluginToolDecl[];
  ui: PluginUISpec;
  exports: ExportKind[];
  /** Detached signature over the canonical JSON of the manifest minus this field. */
  signature: string;
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
  schemaVersion: string;
  pluginId: PluginId;
  pluginVersion: string;
  patientId: string;
  runId: string;
  issuedAt: string; // ISO 8601
  expiresAt: string; // ISO 8601
  redactionPreset: RedactionPreset;
  scope: AnchorScope;
  data: Record<string, unknown>;
  signature: string;
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
  role: "consumer" | "clinician" | "attending" | "coordinator" | "admin";
};

/**
 * Append-only audit row written every time a plugin crosses the
 * consented external boundary.
 */
export type ProvenanceRecord = {
  id: string;
  runId: string;
  pluginId: PluginId;
  pluginVersion: string;
  vendor: VendorIdentity;
  action: OutboundActionKind;
  approver: UserIdentity;
  redactionPreset: RedactionPreset;
  artifactId?: string;
  endpoint: string;
  responseStatus: number;
  responseSummary: string;
  ts: string; // ISO 8601
  signature: string;
};

// ============================================================
// Approval shapes (Caspian vs Plugin diverge here)
// ============================================================

export type CaspianApprovalRequest = {
  kind: "clinical";
  runId: string;
  description: string;
  effect: string;
  approverRole: UserIdentity["role"];
};

export type PluginApprovalRequest = {
  kind: "outbound";
  runId: string;
  approvalId: string;
  pluginId: PluginId;
  action: OutboundActionKind;
  description: string;
  /** Snapshot of what would be sent. Approver reviews this verbatim. */
  payloadPreview: string;
  destination: string;
  redactionPreset: RedactionPreset;
  approverRole: UserIdentity["role"];
};

export type ApprovalRequest = CaspianApprovalRequest | PluginApprovalRequest;

// ============================================================
// Consent token (returned by /api/plugins/runs/{id}/consent)
// ============================================================

export type ConsentToken = {
  pluginId: PluginId;
  runId: string;
  scope: AnchorScopeField[];
  issuedAt: string;
  expiresAt: string;
  approverId: string;
  signature: string;
};

// ============================================================
// Run state machine (frontend view)
// ============================================================

export type RunState =
  | "awaiting-consent"
  | "running"
  | "waiting"
  | "complete"
  | "failed"
  | "revoked";

export type ActiveRun = {
  id: string;
  pluginId: PluginId;
  state: RunState;
  step?: string;
  elapsed?: string;
  consentToken?: string;
  anchorPackage?: AnchorPackage;
};
