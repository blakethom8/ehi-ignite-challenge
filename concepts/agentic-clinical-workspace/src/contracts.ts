export type WorkspaceSurfaceRole =
  | "chat"
  | "canvas"
  | "inspector"
  | "management"
  | "source"
  | "artifact";

export type WorkspaceSurfaceMobileMode = "hide" | "drawer" | "stack";

export type WorkspaceSurfaceDefinition = {
  id: string;
  title: string;
  role: WorkspaceSurfaceRole;
  defaultOpen: boolean;
  defaultWidth: number;
  minWidth: number;
  canCollapse: boolean;
  canFullscreen: boolean;
  mobileMode: WorkspaceSurfaceMobileMode;
};

export type WorkspaceDefinition = {
  id: string;
  title: string;
  description: string;
  primarySkill: string;
  defaultSurfaces: WorkspaceSurfaceDefinition[];
  tools: WorkspaceToolDefinition[];
  sourceGroups: WorkspaceSourceGroup[];
};

export type WorkspaceToolPermission = "read" | "write" | "external" | "approval-required";

export type WorkspaceToolDefinition = {
  id: string;
  label: string;
  category: "patient" | "clinical-trial" | "pursuit" | "artifact" | "transparency";
  permission: WorkspaceToolPermission;
  description: string;
};

export type WorkspaceSourceGroup = {
  id: string;
  label: string;
  description: string;
  sources: WorkspaceSource[];
};

export type WorkspaceSource = {
  id: string;
  label: string;
  kind: "api" | "database" | "url" | "file" | "manual";
  location: string;
  permission: WorkspaceToolPermission;
};

export type WorkspaceSession = {
  id: string;
  workspaceId: string;
  patientId?: string;
  status: "idle" | "running" | "blocked" | "failed" | "complete";
  activeSkill: string;
  createdAt: string;
  updatedAt: string;
};

export type WorkspaceEvent =
  | AssistantMessageEvent
  | UserMessageEvent
  | ToolCallEvent
  | ToolResultEvent
  | CanvasObjectEvent
  | ArtifactEvent
  | CheckpointEvent
  | ApprovalRequestEvent;

export type WorkspaceEventBase = {
  id: string;
  sessionId: string;
  createdAt: string;
};

export type AssistantMessageEvent = WorkspaceEventBase & {
  type: "assistant.message";
  content: string;
};

export type UserMessageEvent = WorkspaceEventBase & {
  type: "user.message";
  content: string;
};

export type ToolCallEvent = WorkspaceEventBase & {
  type: "tool.call";
  toolId: string;
  args: Record<string, unknown>;
};

export type ToolResultEvent = WorkspaceEventBase & {
  type: "tool.result";
  toolId: string;
  ok: boolean;
  summary: string;
  resultRef?: string;
};

export type CanvasObjectEvent = WorkspaceEventBase & {
  type: "canvas.object.updated";
  objectKind: string;
  objectId: string;
  patch: Record<string, unknown>;
};

export type ArtifactEvent = WorkspaceEventBase & {
  type: "artifact.created" | "artifact.updated";
  artifactId: string;
  label: string;
};

export type CheckpointEvent = WorkspaceEventBase & {
  type: "checkpoint.created";
  label: string;
};

export type ApprovalRequestEvent = WorkspaceEventBase & {
  type: "approval.requested";
  label: string;
  reason: string;
  requestedAction: Record<string, unknown>;
};

export type TrialCandidate = {
  id: string;
  nctId: string;
  title: string;
  status: string;
  phase?: string;
  conditions: string[];
  interventions: string[];
  enrollment?: number;
  operationalBurden: "low" | "medium" | "high" | "unknown";
  matchScore?: number;
  inclusionMatches: string[];
  exclusionRisks: string[];
  sourceSnapshotIds: string[];
};

export type TrialPursuitStatus =
  | "interested"
  | "reviewing"
  | "packet"
  | "contacted"
  | "submitted"
  | "follow-up"
  | "closed";

export type TrialPursuit = {
  id: string;
  patientId: string;
  candidateId: string;
  status: TrialPursuitStatus;
  owner?: string;
  tasks: PursuitTask[];
  notes: PursuitNote[];
  updatedAt: string;
};

export type PursuitTask = {
  id: string;
  title: string;
  status: "open" | "done";
  dueAt?: string;
};

export type PursuitNote = {
  id: string;
  body: string;
  createdAt: string;
};
