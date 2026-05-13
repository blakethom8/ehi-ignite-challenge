import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { api } from "../../api/client";
import { useAccessContext, type AccessMode } from "../../context/AccessContext";
import type { AgentSettings } from "../../context/ChatContext";
import { migrateLegacyKey, storageNamespace } from "../../storage";
import type {
  ProviderAssistantCitation,
  ProviderAssistantResponse,
  ProviderAssistantTurn,
  TraceDetail,
  WorkflowArtifact,
  WorkflowId,
} from "../../types";
import type { Citation, WorkbenchTab } from "./data";

export type LiveToolCall = {
  id: string;
  tool: string;
  input_summary: string;
  status: "running" | "done" | "error";
  output_summary?: string;
  duration_ms?: number;
  error?: string | null;
};

const LEGACY_STORAGE_PREFIX = "atlas:caspian:assistant";

type CaspianCitation = ProviderAssistantCitation & {
  id: string;
};

export type CaspianAssistantMessage =
  | {
      id: string;
      role: "user";
      content: string;
      createdAt: string;
    }
  | {
      id: string;
      role: "assistant";
      content: string;
      confidence: "high" | "medium" | "low";
      engine: string;
      citations: CaspianCitation[];
      followUps: string[];
      trace: TraceDetail | null;
      createdAt: string;
      workflowId?: WorkflowId;
      workflowTabId?: string;
      filesCreated?: string[];
    };

export type CaspianInspectorData = {
  citations: Record<string, Citation>;
  traceByCitationId: Record<string, TraceDetail | null>;
  latestTrace: TraceDetail | null;
  contextItems: Array<{ label: string; value: string }>;
};

type ChatResponse = Awaited<ReturnType<typeof api.chatProviderAssistant>>;

function messageId(prefix: "u" | "a"): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/** Identity key (user id, demo alias, guest run id) used to scope storage to the current principal. */
function identityKeyFor(
  mode: AccessMode,
  userId: string | null,
  activeDemoPatientId: string | null,
  activePatientId: string | null,
  activeGuestRunId: string | null,
): string | null {
  switch (mode) {
    case "authenticated":
      return userId ?? "anon";
    case "demo":
      // Prefer the explicit demo alias if present; otherwise fall back to the
      // active patient id (which is also a demo alias today).
      return activeDemoPatientId ?? activePatientId ?? "anon";
    case "guest":
      return activeGuestRunId ?? "anon";
    case "anonymous":
    default:
      return null;
  }
}

function modeNamespacedStorageKey(
  mode: AccessMode,
  identity: string | null,
  patientId: string | null,
  sessionId: string | null,
): string | null {
  if (!patientId || !sessionId) return null;
  return storageNamespace(mode, identity, `caspian:assistant:${patientId}:${sessionId}`);
}

function legacyStorageKey(patientId: string | null, sessionId: string | null): string | null {
  if (!patientId || !sessionId) return null;
  return `${LEGACY_STORAGE_PREFIX}:${patientId}:${sessionId}`;
}

function readMessages(key: string | null, fallbackKey?: string | null): CaspianAssistantMessage[] {
  const candidateKeys = [key, fallbackKey].filter((value): value is string => Boolean(value));
  if (candidateKeys.length === 0) return [];
  for (const candidateKey of candidateKeys) {
    try {
      const raw = window.localStorage.getItem(candidateKey);
      if (!raw) continue;
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? (parsed as CaspianAssistantMessage[]) : [];
    } catch {
      continue;
    }
  }
  if (!key) return [];
  return [];
}

function countCitations(messages: CaspianAssistantMessage[]): number {
  return messages.reduce(
    (total, message) => total + (message.role === "assistant" ? message.citations.length : 0),
    0,
  );
}

function buildAssistantMessage(
  data: ChatResponse,
  existingMessages: CaspianAssistantMessage[],
): Extract<CaspianAssistantMessage, { role: "assistant" }> {
  const start = countCitations(existingMessages) + 1;
  const citations = data.citations.map((citation, index) => ({
    ...citation,
    id: `e_${start + index}`,
  }));
  return {
    id: messageId("a"),
    role: "assistant",
    content: data.answer,
    confidence: data.confidence,
    engine: data.engine,
    citations,
    followUps: data.follow_ups,
    trace: data.trace,
    createdAt: new Date().toISOString(),
    filesCreated: data.files_created && data.files_created.length > 0 ? data.files_created : undefined,
  };
}

export function buildCaspianInspectorData(
  messages: CaspianAssistantMessage[],
  patientId: string | null,
  sessionId: string | null,
): CaspianInspectorData {
  const citations: Record<string, Citation> = {};
  const traceByCitationId: Record<string, TraceDetail | null> = {};
  let latestTrace: TraceDetail | null = null;
  let latestEngine = "—";

  for (const message of messages) {
    if (message.role !== "assistant") continue;
    latestTrace = message.trace;
    latestEngine = message.engine;
    for (const citation of message.citations) {
      citations[citation.id] = {
        id: citation.id,
        type: normalizeResourceType(citation.source_type),
        title: citation.label,
        snippet: citation.detail,
        source: normalizeResourceRef(citation.source_type, citation.resource_id),
        sourceType: normalizeResourceType(citation.source_type),
        sourceId: normalizeResourceId(citation.resource_id),
        encounter: citation.event_date ? `Observed ${citation.event_date}` : "—",
        author: normalizeResourceType(citation.source_type),
        date: citation.event_date ?? "—",
        related: message.citations
          .filter((candidate) => candidate.id !== citation.id)
          .slice(0, 3)
          .map((candidate) => ({
            id: candidate.id,
            text: candidate.label,
          })),
      };
      traceByCitationId[citation.id] = message.trace;
    }
  }

  return {
    citations,
    traceByCitationId,
    latestTrace,
    contextItems: [
      { label: "Patient", value: patientId ?? "No patient selected" },
      { label: "Session", value: sessionId ?? "—" },
      { label: "Messages", value: String(messages.length) },
      { label: "Latest engine", value: latestEngine },
    ],
  };
}

function normalizeResourceRef(sourceType: string, resourceId: string): string {
  const normalizedType = normalizeResourceType(sourceType);
  const trimmed = resourceId.trim();
  if (!trimmed) return normalizedType;
  if (trimmed.includes("/")) return trimmed;
  return `${normalizedType}/${trimmed}`;
}

function normalizeResourceId(resourceId: string): string {
  const trimmed = resourceId.trim();
  if (!trimmed) return trimmed;
  if (!trimmed.includes("/")) return trimmed;
  return trimmed.split("/").pop() ?? trimmed;
}

function normalizeResourceType(sourceType: string): string {
  const trimmed = sourceType.trim();
  if (!trimmed) return trimmed;
  const normalized = trimmed.toLowerCase();
  const known: Record<string, string> = {
    condition: "Condition",
    observation: "Observation",
    medicationstatement: "MedicationStatement",
    medicationrequest: "MedicationRequest",
    servicerequest: "ServiceRequest",
    documentreference: "DocumentReference",
    diagnosticreport: "DiagnosticReport",
    encounter: "Encounter",
    procedure: "Procedure",
    immunization: "Immunization",
    patient: "Patient",
    allergyintolerance: "AllergyIntolerance",
  };
  return known[normalized] ?? trimmed;
}

// ---------------------------------------------------------------------------
// Workflow runs — these produce workbench artifacts, not chat replies.
// ---------------------------------------------------------------------------

export type CaspianWorkflowState = {
  // Tabs to seed into the workbench (one per completed workflow run).
  tabs: WorkbenchTab[];
  // Canvas state keyed by tabId; each entry is a WorkflowArtifact.
  canvas: Record<string, WorkflowArtifact>;
  // Id of the most recently completed run's tab. Increments on every run
  // so the parent can `openTab` + open the workbench pane via an effect.
  latestTabId: string | null;
  isPending: boolean;
  pendingWorkflowId: WorkflowId | null;
  error: Error | null;
};

const WORKFLOW_LABELS: Record<WorkflowId, string> = {
  preop_review_v1: "Pre-op clearance briefing",
  medication_safety_v1: "Medication safety audit",
  longitudinal_synthesis_v1: "Longitudinal synthesis",
};

function workflowTabFromArtifact(artifact: WorkflowArtifact): WorkbenchTab {
  return {
    id: artifact.artifact_id,
    label: WORKFLOW_LABELS[artifact.workflow_id] ?? artifact.workflow_title,
    icon: "FileText",
    kind: "workflow-artifact",
    renderer: "workflow.artifact",
    dirty: false,
  };
}

export type CaspianAssistantSessionOptions = {
  /** Called whenever a chat turn or workflow run reports files written. */
  onFilesChanged?: () => void;
  /** Caspian-scoped agent settings (mode/model/maxTokens) to send with each chat turn. */
  agentSettings?: AgentSettings;
};

export function useCaspianAssistantSession(
  patientId: string | null,
  sessionId: string | null,
  options: CaspianAssistantSessionOptions = {},
) {
  // Capture the latest agent settings in a ref so the mutation closure always
  // reads the current values without re-creating the mutation on every change.
  const agentSettingsRef = useRef<AgentSettings | undefined>(options.agentSettings);
  useEffect(() => {
    agentSettingsRef.current = options.agentSettings;
  }, [options.agentSettings]);
  const { mode, user, activeDemoPatient, activePatientId, activeGuestRunId } = useAccessContext();
  const identity = identityKeyFor(
    mode,
    user?.id ?? null,
    activeDemoPatient?.id ?? null,
    activePatientId,
    activeGuestRunId,
  );
  const key = useMemo(
    () => modeNamespacedStorageKey(mode, identity, patientId, sessionId),
    [mode, identity, patientId, sessionId],
  );
  const legacyKey = useMemo(
    () => legacyStorageKey(patientId, sessionId),
    [patientId, sessionId],
  );
  // One-shot migration of the legacy unscoped storage key into the current
  // mode-namespaced key. Idempotent: subsequent renders no-op because the
  // legacy key has been removed.
  const migratedKeyRef = useRef<string | null>(null);
  const [messages, setMessages] = useState<CaspianAssistantMessage[]>(() => readMessages(key, legacyKey));
  const [liveToolCalls, setLiveToolCalls] = useState<LiveToolCall[]>([]);
  const [pendingStatus, setPendingStatus] = useState<string | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const [workflow, setWorkflow] = useState<CaspianWorkflowState>(() => ({
    tabs: [],
    canvas: {},
    latestTabId: null,
    isPending: false,
    pendingWorkflowId: null,
    error: null,
  }));

  useEffect(() => {
    setMessages(readMessages(key, legacyKey));
    setLiveToolCalls([]);
    setPendingStatus(null);
    if (streamAbortRef.current) {
      streamAbortRef.current.abort();
      streamAbortRef.current = null;
    }
    setWorkflow({
      tabs: [],
      canvas: {},
      latestTabId: null,
      isPending: false,
      pendingWorkflowId: null,
      error: null,
    });
  }, [key, legacyKey]);

  useEffect(() => {
    if (!key || migratedKeyRef.current === key) return;
    if (legacyKey) migrateLegacyKey(legacyKey, key);
    migratedKeyRef.current = key;
  }, [key, legacyKey]);

  useEffect(() => {
    if (!key) return;
    try {
      window.localStorage.setItem(key, JSON.stringify(messages));
    } catch {
      // Best-effort persistence only.
    }
  }, [key, messages]);

  const mutation = useMutation({
    mutationFn: async (payload: { question: string; history: ProviderAssistantTurn[] }) => {
      if (!patientId) {
        throw new Error("Select a patient before using Caspian.");
      }
      const agentSettings = agentSettingsRef.current;
      const controller = new AbortController();
      streamAbortRef.current = controller;
      setLiveToolCalls([]);
      setPendingStatus("Starting Caspian harness…");

      // Wrap in object refs so flow analysis doesn't narrow the closure-mutated
      // values to `null` at the outer scope.
      const finalRef: { value: ProviderAssistantResponse | null } = { value: null };
      const errorRef: { value: { message: string; status?: number } | null } = { value: null };

      await api.chatProviderAssistantStream(
        {
          patient_id: patientId,
          question: payload.question,
          history: payload.history,
          stance: "opinionated",
          mode: agentSettings?.mode || undefined,
          model: agentSettings?.model || undefined,
          max_tokens: agentSettings?.maxTokens || undefined,
        },
        {
          onEvent: (event) => {
            switch (event.type) {
              case "status":
                setPendingStatus(event.message);
                break;
              case "tool_start":
                setPendingStatus(null);
                setLiveToolCalls((prev) => [
                  ...prev,
                  {
                    id: event.id,
                    tool: event.tool,
                    input_summary: event.input_summary,
                    status: "running",
                  },
                ]);
                break;
              case "tool_end":
                setLiveToolCalls((prev) =>
                  prev.map((call) =>
                    call.id === event.id
                      ? {
                          ...call,
                          status: event.error ? "error" : "done",
                          output_summary: event.output_summary,
                          duration_ms: event.duration_ms,
                          error: event.error,
                        }
                      : call,
                  ),
                );
                break;
              case "done":
                setPendingStatus(null);
                finalRef.value = event.response;
                break;
              case "error":
                setPendingStatus(null);
                errorRef.value = { message: event.message, status: event.status };
                break;
              case "stream_closed":
                break;
            }
          },
        },
        controller.signal,
      );

      if (errorRef.value) {
        throw new Error(errorRef.value.message);
      }
      if (!finalRef.value) {
        throw new Error("Stream ended without a response.");
      }
      return finalRef.value;
    },
    onSuccess: (data) => {
      streamAbortRef.current = null;
      setLiveToolCalls([]);
      setPendingStatus(null);
      setMessages((current) => [...current, buildAssistantMessage(data, current)]);
      if (data.files_created && data.files_created.length > 0) {
        options.onFilesChanged?.();
      }
    },
    onError: () => {
      streamAbortRef.current = null;
      setPendingStatus(null);
      // Leave liveToolCalls in place — the inspector can show what ran before the failure.
    },
  });

  const submitQuestion = useCallback((question: string) => {
    const trimmed = question.trim();
    if (!trimmed || mutation.isPending || !patientId || !sessionId) return;

    const history: ProviderAssistantTurn[] = messages.map((message) => ({
      role: message.role,
      content: message.content,
    }));

    setMessages((current) => [
      ...current,
      {
        id: messageId("u"),
        role: "user",
        content: trimmed,
        createdAt: new Date().toISOString(),
      },
    ]);

    mutation.mutate({ question: trimmed, history });
  }, [messages, mutation, patientId, sessionId]);

  const resetConversation = useCallback(() => {
    if (streamAbortRef.current) {
      streamAbortRef.current.abort();
      streamAbortRef.current = null;
    }
    setMessages([]);
    setLiveToolCalls([]);
    setPendingStatus(null);
    setWorkflow({
      tabs: [],
      canvas: {},
      latestTabId: null,
      isPending: false,
      pendingWorkflowId: null,
      error: null,
    });
    mutation.reset();
    if (!key) return;
    try {
      window.localStorage.removeItem(key);
    } catch {
      // noop
    }
  }, [key, mutation]);

  const workflowMutation = useMutation({
    mutationFn: async (workflowId: WorkflowId) => {
      if (!patientId) throw new Error("Select a patient before running a workflow.");
      return api.runCaspianWorkflow({ patient_id: patientId, workflow_id: workflowId });
    },
    onMutate: (workflowId: WorkflowId) => {
      setWorkflow((prev) => ({
        ...prev,
        isPending: true,
        pendingWorkflowId: workflowId,
        error: null,
      }));
    },
    onError: (err: Error) => {
      setWorkflow((prev) => ({
        ...prev,
        isPending: false,
        pendingWorkflowId: null,
        error: err,
      }));
    },
    onSuccess: (data) => {
      const artifact = data.artifact;
      const newTab = workflowTabFromArtifact(artifact);
      setWorkflow((prev) => ({
        tabs: [...prev.tabs.filter((t) => t.id !== newTab.id), newTab],
        canvas: { ...prev.canvas, [newTab.id]: artifact },
        latestTabId: newTab.id,
        isPending: false,
        pendingWorkflowId: null,
        error: null,
      }));
      setMessages((current) => {
        const start = countCitations(current) + 1;
        const citations = data.citations.map((citation, index) => ({
          ...citation,
          id: `e_${start + index}`,
        }));
        const message: Extract<CaspianAssistantMessage, { role: "assistant" }> = {
          id: messageId("a"),
          role: "assistant",
          content: artifact.chat_narration,
          confidence: "high",
          engine: "workflow",
          citations,
          followUps: [],
          trace: data.trace,
          createdAt: new Date().toISOString(),
          workflowId: artifact.workflow_id,
          workflowTabId: newTab.id,
        };
        return [...current, message];
      });
    },
  });

  const runWorkflow = useCallback(
    (workflowId: WorkflowId) => {
      if (workflowMutation.isPending) return;
      workflowMutation.mutate(workflowId);
    },
    [workflowMutation],
  );

  const acknowledgeLatestWorkflow = useCallback(() => {
    setWorkflow((prev) => (prev.latestTabId ? { ...prev, latestTabId: null } : prev));
  }, []);

  const inspector = useMemo(
    () => buildCaspianInspectorData(messages, patientId, sessionId),
    [messages, patientId, sessionId],
  );

  return {
    messages,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
    submitQuestion,
    resetConversation,
    inspector,
    workflow,
    runWorkflow,
    acknowledgeLatestWorkflow,
    liveToolCalls,
    pendingStatus,
  };
}

// Re-export so callers can iterate workflow buttons in the same module.
export const CASPIAN_WORKFLOW_IDS: WorkflowId[] = [
  "preop_review_v1",
  "medication_safety_v1",
  "longitudinal_synthesis_v1",
];

export const CASPIAN_WORKFLOW_LABEL: Record<WorkflowId, string> = WORKFLOW_LABELS;

// Re-export the icon mapping the SessionsPane uses today. Other UI surfaces
// can pull a sensible default lucide icon for each workflow id.
export const CASPIAN_WORKFLOW_ICON_DEFAULT = Activity;
