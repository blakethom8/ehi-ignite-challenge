/**
 * Plugin runtime HTTP client.
 *
 * Mirror of api/plugins/routers/plugins.py. Frontend never re-derives
 * trust state — every call lands at a verified backend endpoint that
 * enforces consent + scope + provenance writes.
 */

import axios, { AxiosError } from "axios";
import type {
  AnchorPackage,
  ConsentToken,
  PluginApprovalRequest,
  PluginManifest,
  ProvenanceRecord,
  RunState,
  UserIdentity,
} from "../components/atlas/trust";

const http = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export type RunEvent = {
  id: string;
  runId: string;
  ts: string;
  kind: string;
  payload: Record<string, unknown>;
};

export type PluginRun = {
  id: string;
  pluginId: PluginManifest["id"];
  pluginVersion: string;
  patientId: string;
  state: RunState;
  workflowId: string | null;
  title: string | null;
  startedBy: UserIdentity;
  startedAt: string;
  completedAt: string | null;
  anchor: AnchorPackage | null;
  canvas: Record<string, unknown>;
};

export type PluginApprovalRow = {
  id: string;
  runId: string;
  pluginId: string;
  status: "pending" | "approved" | "denied" | "voided";
  action: PluginApprovalRequest["action"];
  description: string;
  payloadPreview: string;
  destination: string;
  redactionPreset: PluginApprovalRequest["redactionPreset"];
  approverRole: UserIdentity["role"];
  toolId: string;
  toolPayload: Record<string, unknown>;
  createdAt: string;
  resolvedAt: string | null;
  resolvedBy: string | null;
};

export type PluginRuntimeErrorCode =
  | "OutOfScope"
  | "UndeclaredConnector"
  | "ConsentRequired"
  | "ConsentExpired"
  | "ConsentError"
  | "ApprovalRequired"
  | "AnchorExpired"
  | "AnchorError"
  | "PermissionDenied"
  | "UnknownTool"
  | "PluginManifestError"
  | "RuntimeError"
  | "NotFound"
  | "NotInstalled";

export class PluginRuntimeError extends Error {
  code: PluginRuntimeErrorCode;
  status: number;

  constructor(code: PluginRuntimeErrorCode, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

function unwrap<T>(p: Promise<{ data: T }>): Promise<T> {
  return p.then((r) => r.data).catch((e: AxiosError) => {
    const detail = (e.response?.data as { detail?: { error?: string; message?: string } } | undefined)?.detail;
    if (detail?.error) {
      throw new PluginRuntimeError(
        detail.error as PluginRuntimeErrorCode,
        detail.message ?? e.message,
        e.response?.status ?? 500,
      );
    }
    throw e;
  });
}

export const pluginsApi = {
  listInstalled: (): Promise<PluginManifest[]> =>
    unwrap(http.get<PluginManifest[]>("/plugins/installed")),

  getManifest: (pluginId: string): Promise<PluginManifest> =>
    unwrap(http.get<PluginManifest>(`/plugins/${pluginId}/manifest`)),

  listRuns: (pluginId: string): Promise<PluginRun[]> =>
    unwrap(http.get<PluginRun[]>(`/plugins/${pluginId}/runs`)),

  listPluginProvenance: (pluginId: string): Promise<ProvenanceRecord[]> =>
    unwrap(http.get<ProvenanceRecord[]>(`/plugins/${pluginId}/provenance`)),

  startRun: (body: {
    pluginId: string;
    patientId?: string;
    workflowId?: string;
    title?: string;
    user?: UserIdentity;
  }): Promise<PluginRun> => unwrap(http.post<PluginRun>("/plugins/runs", body)),

  getRun: (runId: string): Promise<PluginRun> =>
    unwrap(http.get<PluginRun>(`/plugins/runs/${runId}`)),

  grantConsent: (runId: string, user?: UserIdentity): Promise<{ runId: string; consentToken: ConsentToken }> =>
    unwrap(http.post(`/plugins/runs/${runId}/consent`, { user })),

  revokeConsent: (runId: string, user?: UserIdentity): Promise<{ runId: string; state: RunState }> =>
    unwrap(http.post(`/plugins/runs/${runId}/revoke-consent`, { user })),

  callTool: (runId: string, toolId: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> =>
    unwrap(http.post(`/plugins/runs/${runId}/tool/${toolId}`, { payload })),

  requestApproval: (
    runId: string,
    body: {
      toolId: string;
      toolPayload: Record<string, unknown>;
      action: PluginApprovalRequest["action"];
      description: string;
      payloadPreview: string;
      destination: string;
      approverRole?: UserIdentity["role"];
    },
  ): Promise<PluginApprovalRequest> =>
    unwrap(http.post<PluginApprovalRequest>(`/plugins/runs/${runId}/approvals`, body)),

  listApprovals: (runId: string): Promise<PluginApprovalRow[]> =>
    unwrap(http.get<PluginApprovalRow[]>(`/plugins/runs/${runId}/approvals`)),

  approveOutbound: (runId: string, approvalId: string, user?: UserIdentity): Promise<{
    approval: string;
    result: Record<string, unknown>;
    provenance: string;
  }> =>
    unwrap(http.post(`/plugins/runs/${runId}/approvals/${approvalId}/approve`, { user })),

  denyOutbound: (runId: string, approvalId: string, user?: UserIdentity): Promise<{ approvalId: string; status: string }> =>
    unwrap(http.post(`/plugins/runs/${runId}/approvals/${approvalId}/deny`, { user })),

  listEvents: (runId: string): Promise<RunEvent[]> =>
    unwrap(http.get<RunEvent[]>(`/plugins/runs/${runId}/events`)),

  listRunProvenance: (runId: string): Promise<ProvenanceRecord[]> =>
    unwrap(http.get<ProvenanceRecord[]>(`/plugins/runs/${runId}/provenance`)),
};
