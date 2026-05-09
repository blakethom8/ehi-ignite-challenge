/**
 * TypeScript shapes for the /api/skills surface.
 *
 * Mirror of `api/routers/skills.py` Pydantic models. Keep in sync; the
 * frontend treats these as authoritative for component prop types.
 */

export type SkillAudience = "clinician" | "patient" | "regulatory";
export type SkillShape = "dashboard" | "brief-workspace" | "conversational";

export type RunStatus =
  | "created"
  | "running"
  | "escalated"
  | "validated"
  | "finished"
  | "failed";

export interface SkillSummary {
  name: string;
  version: string;
  audience: SkillAudience;
  shape: SkillShape;
  description: string;
  required_tools: string[];
  optional_tools: string[];
  context_packages: string[];
  is_live_eligible: boolean;
}

export interface EscalationManifestEntry {
  condition: string;
  description: string;
  action: "stop_and_ask" | "stop_and_summarize" | "stop_and_revise";
  prompt: string;
}

export interface SkillDetail extends SkillSummary {
  body: string;
  escalation: EscalationManifestEntry[];
  output_schema: Record<string, unknown>;
  workspace_template: string | null;
}

export interface PendingEscalation {
  approval_id: string;
  condition: string;
  prompt: string;
  context: Record<string, unknown>;
  raised_at: string;
}

export interface RunStateResponse {
  run_id: string;
  skill_name: string;
  patient_id: string;
  status: RunStatus;
  brief: Record<string, unknown>;
  pending_escalations: PendingEscalation[];
  failure_reason: string | null;
}

export interface Citation {
  citation_id: string;
  claim: string;
  source_kind:
    | "fhir_resource"
    | "external_url"
    | "clinician_input"
    | "agent_inference";
  source_ref: string | null;
  evidence_tier: "T1" | "T2" | "T3" | "T4";
  access_timestamp: string;
}

export interface WorkspaceResponse {
  run_id: string;
  markdown: string;
  citations: Citation[];
}

export interface TranscriptEvent {
  at: string;
  kind: string;
  [key: string]: unknown;
}

export interface TranscriptResponse {
  run_id: string;
  events: TranscriptEvent[];
}

export type CanvasNodeKind =
  | "criteria"
  | "anchor"
  | "candidate_trial"
  | "selected_trial"
  | "packet_task"
  | "summary"
  | "artifact";

export interface CanvasNode {
  node_id: string;
  kind: CanvasNodeKind | string;
  title: string;
  status: string;
  summary: string;
  data: Record<string, unknown>;
  selected: boolean;
  created_at: string;
  updated_at: string;
}

export interface CanvasResponse {
  run_id: string;
  version: number;
  updated_at: string;
  nodes: CanvasNode[];
}

export interface RunMessage {
  message_id: string;
  actor: "clinician" | "patient" | "system";
  message: string;
  canvas_ref: Record<string, unknown> | null;
  consumed: boolean;
  consumed_at: string | null;
  created_at: string;
}

export interface RunMessageRequest {
  actor?: "clinician" | "patient" | "system";
  message: string;
  canvas_ref?: Record<string, unknown> | null;
}

export interface RunMessagesResponse {
  run_id: string;
  messages: RunMessage[];
}

export interface RunListItem {
  run_id: string;
  skill_name: string;
  patient_id: string;
  status: RunStatus;
  started_at: string | null;
  finished_at: string | null;
}

export interface PatientMemoryResponse {
  patient_id: string;
  pinned: string;
  context_packages: Record<string, string>;
  notes: Array<Record<string, unknown>>;
}

export type TrialPursuitStatus =
  | "interested"
  | "reviewing"
  | "packet"
  | "contacted"
  | "submitted"
  | "follow_up"
  | "closed";

export interface TrialPursuitTask {
  task_id: string;
  title: string;
  status: "pending" | "done" | string;
  due_at: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface TrialPursuitEvent {
  event_id: string;
  kind: string;
  note: string;
  actor: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface TrialPursuit {
  pursuit_id: string;
  patient_id: string;
  nct_id: string;
  title: string;
  status: TrialPursuitStatus;
  sponsor: string | null;
  trial_status: string | null;
  source_url: string | null;
  source_kind: string;
  source_updated_at: string | null;
  fit_score: number | null;
  next_step: string;
  notes: string;
  tags: string[];
  created_from_run_id: string | null;
  created_from_canvas_node_id: string | null;
  evidence_snapshot: Record<string, unknown>;
  tasks: TrialPursuitTask[];
  events: TrialPursuitEvent[];
  created_at: string;
  updated_at: string;
}

export interface TrialPursuitListResponse {
  patient_id: string;
  pursuits: TrialPursuit[];
}

export interface TrialPursuitUpsertRequest {
  nct_id: string;
  title: string;
  status?: TrialPursuitStatus;
  sponsor?: string | null;
  trial_status?: string | null;
  source_url?: string | null;
  source_kind?: string;
  source_updated_at?: string | null;
  fit_score?: number | null;
  next_step?: string | null;
  notes?: string | null;
  tags?: string[];
  created_from_run_id?: string | null;
  created_from_canvas_node_id?: string | null;
  evidence_snapshot?: Record<string, unknown>;
  actor?: string;
}

export type SaveDestination = "run" | "patient" | "package";

export interface SavePinnedFact {
  text: string;
  citation_id?: string;
  evidence_tier?: string;
}

export interface SaveRequest {
  destination: SaveDestination;
  actor?: string;
  edits_markdown?: string;
  facts?: SavePinnedFact[];
  package_name?: string;
  package_content?: string;
}

export interface RunStartResponse {
  run_id: string;
  skill_name: string;
  patient_id: string;
  status: RunStatus;
}

export interface InspectorFile {
  path: string;
  kind: string;
  size_bytes: number;
  content: string | null;
}

export interface InspectorTool {
  alias: string;
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  kind: string;
  permission: string;
  declared: boolean;
  available: boolean;
}

export interface RunInspectorResponse {
  run: Record<string, unknown>;
  skill: Record<string, unknown>;
  instructions: {
    skill_md: string;
    workspace_template: string | null;
    output_schema: Record<string, unknown>;
    escalation: Array<Record<string, unknown>>;
    assembled_prompt: string;
    files: InspectorFile[];
  };
  context: {
    brief: Record<string, unknown>;
    patient_memory: {
      pinned: string;
      context_packages: Record<string, string>;
      notes: Array<Record<string, unknown>>;
    };
    messages: RunMessage[];
    canvas: CanvasResponse;
    citations: Citation[];
  };
  tools: InspectorTool[];
  permissions: Record<string, unknown>;
  transcript: {
    events: TranscriptEvent[];
    summary: Record<string, unknown>;
  };
  artifacts: {
    workspace_markdown: string;
    canvas: CanvasResponse;
    output: Record<string, unknown> | null;
    citations: Citation[];
    files: InspectorFile[];
  };
}
