/**
 * Live plugin-run state hook.
 *
 * Drives the workspace UI from the backend runtime. Polls events +
 * approvals + run status every 2s. Mutation methods (grant consent,
 * call tool, request/approve approval) invalidate the queries so the
 * UI reflects the runtime within a tick.
 *
 * Canvas state is derived by folding `tool.result` events into a
 * `{ [toolId]: result }` map. The WorkbenchPane and renderers project
 * straight off that map — no business logic on the frontend, per
 * HARNESS-SURFACES §8.
 */

import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useMemo } from "react";
import {
  pluginsApi,
  type PluginApprovalRow,
  type PluginRun,
  type RunEvent,
} from "../../api/plugins";
import type { PluginApprovalRequest, UserIdentity } from "./trust";

const POLL_MS = 2_000;

export type PluginRunStateBundle = {
  run: PluginRun | undefined;
  events: RunEvent[];
  approvals: PluginApprovalRow[];
  canvas: Record<string, unknown>;
  pendingApproval: PluginApprovalRow | undefined;
  isLoading: boolean;
  grantConsent: (user?: UserIdentity) => Promise<unknown>;
  revokeConsent: (user?: UserIdentity) => Promise<unknown>;
  callTool: (toolId: string, payload: Record<string, unknown>) => Promise<Record<string, unknown>>;
  requestApproval: (body: {
    toolId: string;
    toolPayload: Record<string, unknown>;
    action: PluginApprovalRequest["action"];
    description: string;
    payloadPreview: string;
    destination: string;
    approverRole?: UserIdentity["role"];
  }) => Promise<PluginApprovalRequest>;
  approve: (approvalId: string, user?: UserIdentity) => Promise<unknown>;
  deny: (approvalId: string, user?: UserIdentity) => Promise<unknown>;
};

function buildCanvas(events: RunEvent[]): Record<string, unknown> {
  const canvas: Record<string, unknown> = {};
  for (const e of events) {
    if (e.kind === "tool.result") {
      const payload = e.payload as { toolId?: string; result?: Record<string, unknown> };
      if (payload.toolId && payload.result) {
        canvas[payload.toolId] = payload.result;
      }
    }
  }
  return canvas;
}

export function usePluginRun(runId: string | null): PluginRunStateBundle {
  const qc = useQueryClient();
  const enabled = Boolean(runId);

  const runQuery = useQuery<PluginRun>({
    queryKey: ["plugins", "run", runId],
    queryFn: () => pluginsApi.getRun(runId as string),
    enabled,
    refetchInterval: POLL_MS,
  });

  const eventsQuery = useQuery<RunEvent[]>({
    queryKey: ["plugins", "run", runId, "events"],
    queryFn: () => pluginsApi.listEvents(runId as string),
    enabled,
    refetchInterval: POLL_MS,
  });

  const approvalsQuery = useQuery<PluginApprovalRow[]>({
    queryKey: ["plugins", "run", runId, "approvals"],
    queryFn: () => pluginsApi.listApprovals(runId as string),
    enabled,
    refetchInterval: POLL_MS,
  });

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["plugins", "run", runId] });

  const grantConsent = useMutation({
    mutationFn: (user?: UserIdentity) => pluginsApi.grantConsent(runId as string, user),
    onSuccess: invalidate,
  });

  const revokeConsent = useMutation({
    mutationFn: (user?: UserIdentity) => pluginsApi.revokeConsent(runId as string, user),
    onSuccess: invalidate,
  });

  const callTool = useMutation({
    mutationFn: ({ toolId, payload }: { toolId: string; payload: Record<string, unknown> }) =>
      pluginsApi.callTool(runId as string, toolId, payload),
    onSuccess: invalidate,
  });

  const requestApproval = useMutation({
    mutationFn: (body: Parameters<typeof pluginsApi.requestApproval>[1]) =>
      pluginsApi.requestApproval(runId as string, body),
    onSuccess: invalidate,
  });

  const approve = useMutation({
    mutationFn: ({ approvalId, user }: { approvalId: string; user?: UserIdentity }) =>
      pluginsApi.approveOutbound(runId as string, approvalId, user),
    onSuccess: invalidate,
  });

  const deny = useMutation({
    mutationFn: ({ approvalId, user }: { approvalId: string; user?: UserIdentity }) =>
      pluginsApi.denyOutbound(runId as string, approvalId, user),
    onSuccess: invalidate,
  });

  const events = eventsQuery.data ?? [];
  const approvals = approvalsQuery.data ?? [];
  const canvas = useMemo(() => buildCanvas(events), [events]);
  const pendingApproval = approvals.find((a) => a.status === "pending");

  return {
    run: runQuery.data,
    events,
    approvals,
    canvas,
    pendingApproval,
    isLoading: runQuery.isLoading || eventsQuery.isLoading,
    grantConsent: (user) => grantConsent.mutateAsync(user),
    revokeConsent: (user) => revokeConsent.mutateAsync(user),
    callTool: (toolId, payload) => callTool.mutateAsync({ toolId, payload }),
    requestApproval: (body) => requestApproval.mutateAsync(body),
    approve: (approvalId, user) => approve.mutateAsync({ approvalId, user }),
    deny: (approvalId, user) => deny.mutateAsync({ approvalId, user }),
  };
}
