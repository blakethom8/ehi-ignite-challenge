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
