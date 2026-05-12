// API response types — mirrors api/models.py

export type AuthMode = "anonymous" | "demo" | "authenticated" | "guest";

// Server-declared capability surface. Returned by GET /api/auth/capabilities.
// Mirrors api/core/access_policy.Capabilities exactly.
export interface Capabilities {
  mode: AuthMode;
  can_use_caspian: boolean;
  can_edit_caspian_user_files: boolean;
  can_write_caspian_notes: boolean;
  can_run_workflows: boolean;
  can_use_aggregation_uploads: boolean;
  can_use_aggregation_profiles: boolean;
  can_use_harmonize: boolean;
  can_use_guest_harmonization: boolean;
  can_use_assistant_tools_write: boolean;
  show_caspian_seed_files: boolean;
  persistence_scope: "none" | "browser-ephemeral" | "browser-persistent" | "server-persistent";
}

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: "consumer" | "clinician" | "attending" | "coordinator" | "admin";
}

export interface DemoPatientOption {
  id: string;
  name: string;
  description: string;
  short_journey?: string;
  metadata?: {
    care_setting?: string;
    clinical_focus?: string;
    complexity?: string;
    tags?: string[];
  };
}

export interface AuthSessionResponse {
  mode: AuthMode;
  user: AuthUser | null;
  active_patient_id: string | null;
  active_patient_name: string | null;
  active_demo_patient?: DemoPatientOption | null;
  expires_at: string | null;
  available_demo_patients: DemoPatientOption[];
}

export type AuthRole = AuthUser["role"];
export type AuthAccountStatus = "active" | "disabled";

export interface AdminUserSummary {
  id: string;
  email: string;
  display_name: string;
  role: AuthRole;
  status: AuthAccountStatus;
  created_at: string;
  last_login_at: string | null;
  workspace_count: number;
  storage_bytes: number;
}

export interface AdminWorkspaceSummary {
  id: string;
  display_name: string;
  created_at: string;
  updated_at: string;
  source_count: number;
  storage_bytes: number;
}

export interface AdminUserDetail extends AdminUserSummary {
  workspaces: AdminWorkspaceSummary[];
}

export interface AdminAuditEvent {
  id: string;
  created_at: string;
  session_id: string | null;
  user_id: string | null;
  mode: string | null;
  patient_id: string | null;
  event_type: string;
  payload: Record<string, unknown>;
}

export interface AdminAuditListResponse {
  events: AdminAuditEvent[];
}

export interface AdminSessionSummary {
  id: string;
  mode: string;
  user_id: string | null;
  user_email: string | null;
  user_display_name: string | null;
  active_patient_id: string | null;
  active_patient_name: string | null;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  user_agent: string | null;
}

export interface AdminPatchUserPayload {
  role?: AuthRole;
  status?: AuthAccountStatus;
}

export interface AdminActionResponse {
  ok: boolean;
}

export interface PatientListItem {
  id: string;
  name: string;
  age_years: number;
  gender: string;
  complexity_tier: string;
  complexity_score: number;
  total_resources: number;
  encounter_count: number;
  active_condition_count: number;
  active_med_count: number;
  workspace_type?: "synthea" | "upload" | "profile" | "demo";
  source_count?: number;
  prepared_source_count?: number;
}

export interface AggregationProfile {
  id: string;
  display_name: string;
  created_at: string;
  updated_at: string;
  notes: string;
  storage_mode: string;
}

export interface AggregationCreateProfilePayload {
  display_name?: string;
  notes?: string;
}

export interface AggregationUpdateProfilePayload {
  display_name: string;
  notes?: string;
}

export interface AggregationCreateProfileResponse {
  profile: AggregationProfile;
  storage_posture: string;
}

export interface CanonicalSourceSummary {
  id: string;
  label: string;
  kind: string;
  status: string;
  status_label: string;
  total_resources: number;
}

export interface CanonicalPatientSummary {
  patient_id: string;
  patient_name: string;
  workspace_id: string;
  source_count: number;
  prepared_source_count: number;
  needs_preparation_count: number;
  total_resources: number;
  canonical_observation_count: number;
  canonical_condition_count: number;
  canonical_medication_count: number;
  canonical_allergy_count: number;
  canonical_immunization_count: number;
  encounter_count: number;
  review_item_count: number;
  date_start: string | null;
  date_end: string | null;
  storage_mode: string;
  storage_description: string;
  sources: CanonicalSourceSummary[];
  fallback_modes: string[];
}

export interface ConditionRow {
  condition_id: string;
  display: string;
  clinical_status: string;
  is_active: boolean;
  onset_dt: string | null;
  abatement_dt: string | null;
}

export interface MedRow {
  med_id: string;
  display: string;
  status: string;
  authored_on: string | null;
  is_active: boolean;
}

export interface ResourceTypeCount {
  resource_type: string;
  count: number;
  category: "Clinical" | "Billing" | "Administrative";
}

export interface EncounterTypeSummary {
  encounter_type: string;
  count: number;
}

export interface CareTeamSummaryItem {
  name: string;
  specialty?: string;
  organizations: string[];
  encounter_count: number;
  latest_encounter_dt: string | null;
  class_breakdown: Record<string, number>;
}

export interface SiteOfServiceSummaryItem {
  name: string;
  specialty?: string;
  provider_count: number;
  encounter_count: number;
  latest_encounter_dt: string | null;
  class_breakdown: Record<string, number>;
}

export interface PatientOverview {
  id: string;
  name: string;
  age_years: number;
  gender: string;
  birth_date: string | null;
  is_deceased: boolean;
  race: string;
  ethnicity: string;
  city: string;
  state: string;
  language: string;
  marital_status: string;
  daly: number | null;
  qaly: number | null;
  earliest_encounter_dt: string | null;
  latest_encounter_dt: string | null;
  years_of_history: number;
  total_resources: number;
  clinical_resource_count: number;
  billing_resource_count: number;
  billing_pct: number;
  resource_type_counts: ResourceTypeCount[];
  complexity_score: number;
  complexity_tier: string;
  active_condition_count: number;
  resolved_condition_count: number;
  conditions: ConditionRow[];
  active_med_count: number;
  total_med_count: number;
  medications: MedRow[];
  unique_loinc_count: number;
  obs_category_breakdown: Record<string, number>;
  encounter_count: number;
  encounter_class_breakdown: Record<string, number>;
  encounter_type_breakdown: EncounterTypeSummary[];
  avg_resources_per_encounter: number;
  care_team: CareTeamSummaryItem[];
  sites_of_service: SiteOfServiceSummaryItem[];
  allergy_count: number;
  allergy_labels: string[];
  immunization_count: number;
  unique_vaccines: string[];
  parse_warning_count: number;
}

export interface EncounterEvent {
  encounter_id: string;
  class_code: string;
  encounter_type: string;
  reason_display: string;
  start: string | null;
  end: string | null;
  provider_org: string;
  practitioner_name: string;
  specialty: string;
  source_category: string;
  provenance_label: string;
  linked_observation_count: number;
  linked_condition_count: number;
  linked_procedure_count: number;
  linked_medication_count: number;
  linked_clinical_note_count: number;
}

export interface TimelineResponse {
  patient_id: string;
  name: string;
  encounters: EncounterEvent[];
  year_counts: Record<string, number>;
}

export interface ObservationDetail {
  obs_id: string;
  category: string;
  display: string;
  loinc_code: string;
  effective_dt: string | null;
  value_type: string;
  value_quantity: number | null;
  value_unit: string;
  value_concept_display: string | null;
}

export interface ConditionDetail {
  condition_id: string;
  display: string;
  clinical_status: string;
  is_active: boolean;
  onset_dt: string | null;
}

export interface ProcedureDetail {
  procedure_id: string;
  display: string;
  status: string;
  performed_start: string | null;
  reason_display: string;
}

export interface ProcedureItem {
  procedure_id: string;
  display: string;
  status: string;
  performed_start: string | null;
  performed_end: string | null;
  reason_display: string;
  body_site: string;
}

export interface ProceduresResponse {
  patient_id: string;
  name: string;
  total_count: number;
  procedures: ProcedureItem[];
}

export interface MedicationDetail {
  med_id: string;
  display: string;
  status: string;
  authored_on: string | null;
  dosage_text: string;
  reason_display: string;
}

export interface EncounterDetail {
  encounter_id: string;
  class_code: string;
  encounter_type: string;
  reason_display: string;
  start: string | null;
  end: string | null;
  duration_hours: number | null;
  provider_org: string;
  practitioner_name: string;
  specialty: string;
  source_category: string;
  provenance_label: string;
  observations: ObservationDetail[];
  conditions: ConditionDetail[];
  procedures: ProcedureDetail[];
  medications: MedicationDetail[];
  diagnostic_report_count: number;
  imaging_study_count: number;
  clinical_notes: ClinicalNoteItem[];
}

export interface LabHistoryPoint {
  effective_dt: string | null;
  value: number;
  abnormality: "low" | "high" | "normal" | "unknown";
  alert_severity: "critical" | "warning" | null;
}

export interface LabValue {
  loinc_code: string;
  display: string;
  value: number | null;
  unit: string;
  effective_dt: string | null;
  trend: "up" | "down" | "stable" | null;
  is_abnormal: boolean | null;
  abnormality: "low" | "high" | "normal" | "unknown";
  alert_severity: "critical" | "warning" | null;
  reference_low: number | null;
  reference_high: number | null;
  reference_unit: string;
  reference_range_label: string;
  history: LabHistoryPoint[];
}

export interface LabAlertFlag {
  lab_name: string;
  loinc_code: string;
  value: number;
  unit: string;
  severity: "critical" | "warning";
  direction: "high" | "low" | "trending_up" | "trending_down";
  message: string;
  days_ago: number;
}

export interface TimelineEvent {
  loinc_code: string;
  display_name: string;
  value: number;
  unit: string;
  date: string;                  // "YYYY-MM-DD"
  change_direction: "up" | "down" | "stable";
}

export interface TimelineMonth {
  month: string;                 // "2026-03"
  label: string;                 // "Mar 2026"
  events: TimelineEvent[];
}

export interface KeyLabsResponse {
  patient_id: string;
  panels: Record<string, LabValue[]>;
  alert_flags: LabAlertFlag[];
  timeline_events: TimelineMonth[];
}

export interface SafetyMedication {
  med_id: string;
  display: string;
  status: string;
  authored_on: string | null;
  is_active: boolean;
}

export interface SafetyFlag {
  class_key: string;
  label: string;
  severity: "critical" | "warning" | "info";
  surgical_note: string;
  status: "ACTIVE" | "HISTORICAL" | "NONE";
  medications: SafetyMedication[];
  protocol_note?: string | null;
}

export interface SafetyResponse {
  patient_id: string;
  name: string;
  flags: SafetyFlag[];
  active_flag_count: number;
  historical_flag_count: number;
}

export interface SurgicalRiskComponent {
  key: string;
  label: string;
  score: number;
  max_score: number;
  status: "CLEARED" | "REVIEW" | "FLAGGED";
  rationale: string;
  evidence: string[];
}

export interface SurgicalRiskResponse {
  patient_id: string;
  name: string;
  score: number;
  max_score: number;
  tier: "LOW" | "MODERATE" | "HIGH";
  disposition: "CLEARED" | "REVIEW" | "HOLD";
  rule_version: string;
  components: SurgicalRiskComponent[];
  methodology_notes: string[];
}

export interface ImmunizationItem {
  imm_id: string;
  display: string;
  cvx_code: string;
  status: string;
  occurrence_dt: string | null;
}

export interface ImmunizationResponse {
  patient_id: string;
  name: string;
  total_count: number;
  immunizations: ImmunizationItem[];
  unique_vaccines: string[];
}

export interface CorpusStats {
  total_patients: number;
  gender_breakdown: Record<string, number>;
  complexity_tier_breakdown: Record<string, number>;
  avg_age: number;
  avg_encounter_count: number;
  avg_active_condition_count: number;
  avg_active_med_count: number;
  total_encounters: number;
  total_resources: number;
}

export interface RankedConditionItem {
  condition_id: string;
  display: string;
  clinical_status: string;
  onset_dt: string | null;
  risk_category: string;
  risk_rank: number;
  risk_label: string;
  is_active: boolean;
}

export interface ConditionAcuityResponse {
  patient_id: string;
  name: string;
  active_count: number;
  resolved_count: number;
  ranked_active: RankedConditionItem[];
  ranked_resolved: RankedConditionItem[];
}

export interface PatientRiskSummary {
  id: string;
  name: string;
  complexity_tier: string;
  has_critical_flag: boolean;
  active_critical_classes: string[];
}

export interface ObservationDistribution {
  loinc_code: string;
  display_name: string;
  unit: string;
  count: number;
  patient_count: number;
  min: number;
  max: number;
  mean: number;
  median: number;
  p10: number;
  p25: number;
  p75: number;
  p90: number;
  histogram: number[];
  bucket_labels: string[];
}

export interface ObservationDistributionsResponse {
  distributions: ObservationDistribution[];
  total_loinc_codes_found: number;
  loinc_codes_shown: number;
}

export interface InteractionResult {
  drug_a: string;
  drug_a_label: string;
  drug_b: string;
  drug_b_label: string;
  severity: "contraindicated" | "major" | "moderate";
  mechanism: string;
  clinical_effect: string;
  management: string;
  drug_a_meds: string[];
  drug_b_meds: string[];
}

export interface InteractionResponse {
  patient_id: string;
  active_class_keys: string[];
  interactions: InteractionResult[];
  contraindicated_count: number;
  major_count: number;
  moderate_count: number;
  has_interactions: boolean;
}

export interface FieldCoverageItem {
  field_path: string;
  resource_type: string;
  present_count: number;
  total_count: number;
  coverage_pct: number;
  coverage_label: "Always" | "Usually" | "Sometimes" | "Rarely";
}

export interface FieldCoverageResponse {
  total_patients: number;
  fields: FieldCoverageItem[];
}

export interface AllergySubstanceEntry {
  substance: string;
  count: number;
  criticality: string;
}

export interface AllergyCriticalityBreakdown {
  criticality_counts: Record<string, number>;
  category_counts: Record<string, number>;
  total_allergy_records: number;
  patients_with_allergies: number;
  patients_with_high_criticality: number;
  top_substances: AllergySubstanceEntry[];
}

export interface ProviderAssistantTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ProviderAssistantCitation {
  source_type: string;
  resource_id: string;
  label: string;
  detail: string;
  event_date: string | null;
}

// ---------------------------------------------------------------------------
// Care Journey (multi-lane Gantt timeline)
// ---------------------------------------------------------------------------

export interface MedicationEpisodeItem {
  episode_id: string;
  display: string;
  drug_class: string | null;
  status: string;
  is_active: boolean;
  start_date: string | null;
  end_date: string | null;
  duration_days: number | null;
  request_count: number;
  reason: string | null;
}

export interface ConditionEpisodeItem {
  condition_id: string;
  display: string;
  clinical_status: string;
  onset_date: string | null;
  end_date: string | null;
  is_active: boolean;
}

export interface EncounterMarker {
  encounter_id: string;
  class_code: string;
  type_text: string;
  start: string | null;
  reason_display: string;
  diagnoses: string[];
}

export interface ClinicalNoteItem {
  note_id: string;
  source_id: string;
  source_label: string;
  resource_type: string;
  resource_id: string;
  note_index: number;
  date: string | null;
  author: string;
  organization: string;
  document_type: string;
  category: string;
  encounter_id: string | null;
  linked_encounter_id: string | null;
  linked_encounter_type: string;
  linked_encounter_start: string | null;
  provider: string;
  site: string;
  section_title: string;
  attachment_content_type: string;
  preview: string;
  text: string;
}

export interface ClinicalNotesResponse {
  patient_id: string;
  name: string;
  total_count: number;
  notes: ClinicalNoteItem[];
}

export interface ProcedureMarker {
  procedure_id: string;
  display: string;
  start: string | null;
  end: string | null;
  reason_display: string;
}

export interface DiagnosticReportItem {
  report_id: string;
  display: string;
  category: string;
  date: string | null;
  result_count: number;
  has_presented_form: boolean;
  note_preview: string;
}

export interface CareJourneyResponse {
  patient_id: string;
  name: string;
  earliest_date: string | null;
  latest_date: string | null;
  medication_episodes: MedicationEpisodeItem[];
  conditions: ConditionEpisodeItem[];
  encounters: EncounterMarker[];
  procedures: ProcedureMarker[];
  diagnostic_reports: DiagnosticReportItem[];
  clinical_notes: ClinicalNoteItem[];
  drug_classes_present: string[];
}

export interface ProviderAssistantRequest {
  patient_id: string;
  question: string;
  history?: ProviderAssistantTurn[];
  context_packages?: ProviderAssistantContextPackage[];
  stance?: "opinionated" | "balanced";
  model?: string;
  mode?: string;
  max_tokens?: number;
}

/**
 * Live streaming events emitted by POST /assistant/chat/stream as the agent runs.
 * `tool_start`/`tool_end` arrive in real time per tool call; `done` carries the
 * full ProviderAssistantResponse; `error` is terminal. `stream_closed` is the
 * end-of-stream sentinel.
 */
export type AssistantStreamEvent =
  | {
      type: "tool_start";
      id: string;
      tool: string;
      input_summary: string;
    }
  | {
      type: "tool_end";
      id: string;
      tool: string;
      output_summary: string;
      duration_ms: number;
      error: string | null;
    }
  | { type: "done"; response: ProviderAssistantResponse }
  | { type: "error"; status?: number; message: string }
  | { type: "stream_closed" };

export interface AssistantStreamCallbacks {
  onEvent: (event: AssistantStreamEvent) => void;
}

export interface ProviderAssistantContextPackage {
  id: string;
  title: string;
  type: string;
  summary: string;
  instructions: string;
}

export interface AssistantModeOption {
  id: string;
  label: string;
  description: string;
}

export interface AssistantModelOption {
  id: string;
  label: string;
  description: string;
  speed: "fast" | "medium" | "slow";
}

export interface AssistantSettings {
  current: {
    mode: string;
    model: string;
    max_tokens: number;
  };
  client_overrides_enabled: boolean;
  max_tokens_limit: number;
  available_modes: AssistantModeOption[];
  available_models: AssistantModelOption[];
}

export interface ToolCallDetail {
  tool_name: string;
  input_summary: string;
  output_summary: string;
  duration_ms: number | null;
  error: string | null;
}

export interface TraceDetail {
  trace_id: string;
  duration_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  total_cost_usd: number | null;
  tool_calls: ToolCallDetail[];
  system_prompt_preview: string;
  retrieved_facts: string[];
  // Transparency metadata
  model_used: string | null;
  mode_used: string | null;
  max_tokens_used: number | null;
  context_token_estimate: number | null;
  history_turns_sent: number | null;
}

export interface ProviderAssistantResponse {
  patient_id: string;
  answer: string;
  confidence: "high" | "medium" | "low";
  stance: "opinionated" | "balanced";
  engine: "deterministic" | "anthropic-agent-sdk" | "deterministic-fallback" | string;
  citations: ProviderAssistantCitation[];
  follow_ups: string[];
  trace: TraceDetail | null;
  /** Relative workspace paths the agent wrote on this turn (slice 3+4). */
  files_created: string[];
}

// ---------------------------------------------------------------------------
// Caspian workflow runs — prepared review packets that produce a structured
// artifact rendered in the workbench (not just a chat reply).
// ---------------------------------------------------------------------------

export type WorkflowId =
  | "preop_review_v1"
  | "medication_safety_v1"
  | "longitudinal_synthesis_v1";

export type WorkflowBannerStatus =
  | "clear"
  | "review"
  | "hold"
  | "critical"
  | "stable"
  | "evolving"
  | "deteriorating";

export interface WorkflowBanner {
  status: WorkflowBannerStatus;
  label: string;
  headline: string;
  action_label: string | null;
}

export interface WorkflowFactCell {
  label: string;
  value: string;
  tone: "default" | "tier" | "caution";
}

export interface WorkflowTableSection {
  kind: "table";
  title: string;
  columns: string[];
  rows: string[][];
  empty_note?: string | null;
}

export interface WorkflowNarrativeSection {
  kind: "narrative";
  title: string;
  body: string;
}

export type WorkflowSection = WorkflowTableSection | WorkflowNarrativeSection;

export interface WorkflowArtifact {
  workflow_id: WorkflowId;
  workflow_title: string;
  workflow_type: string;
  artifact_id: string;
  generated_at: string;
  banner: WorkflowBanner;
  fact_rail: WorkflowFactCell[];
  sections: WorkflowSection[];
  chat_narration: string;
  /** Relative workspace path where the artifact was persisted (slice 1+2). */
  file_path: string | null;
}

export interface WorkflowRunRequest {
  patient_id: string;
  workflow_id: WorkflowId;
}

export interface WorkflowRunResponse {
  patient_id: string;
  artifact: WorkflowArtifact;
  citations: ProviderAssistantCitation[];
  trace: TraceDetail | null;
}

// ---------------------------------------------------------------------------
// Caspian file workspace — per-patient on-disk working directory.
// ---------------------------------------------------------------------------

export type CaspianFileGroupNode = {
  type: "group";
  label: string;
};

export type CaspianFileFolderNode = {
  type: "folder";
  name: string;
  expanded?: boolean;
  children: CaspianFileTreeNode[];
};

/**
 * File-kind taxonomy — mirrors api/core/caspian_workspace._kind_for_path.
 *
 *  - `system`    — read-only system-context tree (system prompt + chart
 *                  context + workflow packets)
 *  - `user`      — clinician-authored files (notes/, user-instructions.md)
 *  - `generated` — workflow-run artifacts, always read-only to users
 *  - `demo-seed` — virtual sample files only present in demo sessions
 */
export type CaspianFileKind = "system" | "user" | "generated" | "demo-seed";

export type CaspianFileFileNode = {
  type: "file";
  name: string;
  id: string; // path relative to workspace root
  ext: string;
  icon: string;
  dirty?: boolean;
  editable: boolean;
  kind?: CaspianFileKind;
};

export type CaspianFileRefNode = {
  type: "ref";
  id: string;
  label: string;
  sub: string;
};

export type CaspianFileTreeNode =
  | CaspianFileGroupNode
  | CaspianFileFolderNode
  | CaspianFileFileNode
  | CaspianFileRefNode;

export interface CaspianFileListResponse {
  workspace_key: string;
  tree: CaspianFileTreeNode[];
  capabilities?: Capabilities | null;
}

export interface CaspianFileReadResponse {
  path: string;
  content: string;
  mtime: string | null;
  editable: boolean;
  /** Content format — drives the renderer (markdown formatter, JSON pretty-print, monospaced text). */
  kind: "markdown" | "json" | "text";
  /** File-kind taxonomy — drives the provenance pill in WorkspaceFileRenderer. */
  file_kind?: CaspianFileKind;
}

export interface SaveAsNoteRequest {
  patient_id: string;
  source_path: string;
}

export interface CaspianFileWriteRequest {
  patient_id: string;
  path: string;
  content: string;
}

export interface CaspianFileWriteResponse {
  path: string;
  bytes: number;
  mtime: string;
}

// ---------------------------------------------------------------------------
// Patient Context guided intake
// ---------------------------------------------------------------------------

export type PatientContextSourceMode = "synthetic" | "private_blake_cedars" | "selected_patient";
export type PatientContextGapCategory =
  | "missing_sources"
  | "medication_reality"
  | "timeline_gap"
  | "uncertain_fact"
  | "qualitative_context";

export interface PatientContextGapCard {
  id: string;
  category: PatientContextGapCategory;
  title: string;
  prompt: string;
  why_it_matters: string;
  status: "open" | "answered" | "skipped";
  priority: number;
  evidence: string[];
}

export interface PatientContextTurn {
  id: string;
  role: "patient" | "assistant";
  content: string;
  created_at: string;
  linked_gap_id: string | null;
}

export interface PatientContextFact {
  id: string;
  source: "patient-reported";
  linked_gap_id: string | null;
  statement: string;
  summary: string;
  confidence: "high" | "medium" | "low";
  created_at: string;
}

export interface PatientContextExportStatus {
  generated: boolean;
  files: string[];
  generated_at: string | null;
}

export interface PatientContextSessionResponse {
  session_id: string;
  patient_id: string;
  patient_label: string;
  source_mode: PatientContextSourceMode;
  source_posture: string;
  gap_cards: PatientContextGapCard[];
  turns: PatientContextTurn[];
  facts: PatientContextFact[];
  export_status: PatientContextExportStatus;
}

export interface PatientContextTurnResponse extends PatientContextSessionResponse {
  assistant_message: PatientContextTurn;
}

export interface PatientContextExportResponse {
  session_id: string;
  generated_at: string;
  files: string[];
  preview: string;
}

export interface PatientContextStatus {
  private_blake_cedars_available: boolean;
  storage: string;
}

// ---------------------------------------------------------------------------
// Data Aggregator workflow
// ---------------------------------------------------------------------------

export interface AggregationUploadedFile {
  file_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
  status: "uploaded" | "needs_processing" | "unsupported";
  data_type: string;
  source_name: string;
  date_range: string;
  contains: string[];
  description: string;
  context_notes: string;
  extraction_confidence: "high" | "medium" | "low" | "unknown";
  storage_path: string;
  parse_status: "stored" | "ready_to_extract" | "extracted" | "structured" | "unsupported";
  next_step: string;
  derived_artifacts: string[];
}

export interface AggregationPreparedPreviewItem {
  resource_type: string;
  label: string;
  value: string;
  date: string;
  status: string;
}

export interface AggregationPreparedPreviewResponse {
  patient_id: string;
  file_id: string;
  file_name: string;
  parse_status: AggregationUploadedFile["parse_status"];
  output_type: string;
  total_resources: number;
  resource_counts: Record<string, number>;
  artifact_paths: string[];
  date_start: string;
  date_end: string;
  json_preview: Record<string, unknown> | null;
  preview_items: AggregationPreparedPreviewItem[];
  message: string;
}

export interface AggregationSourceCard {
  id: string;
  name: string;
  category:
    | "synthetic_fhir"
    | "private_ehi"
    | "portal"
    | "file_upload"
    | "lab"
    | "pharmacy"
    | "payer"
    | "wearable"
    | "planned_adapter";
  mode: "available" | "missing" | "planned" | "uploaded" | "private";
  status_label: string;
  record_count: number;
  last_updated: string | null;
  confidence: "high" | "medium" | "low" | "not_started";
  posture: string;
  next_action: string;
  help_title: string;
  help_body: string;
  evidence: string[];
}

export interface AggregationEnvironmentResponse {
  patient_id: string;
  patient_label: string;
  environment_label: string;
  source_posture: string;
  private_blake_cedars_available: boolean;
  synthetic_resource_counts: Record<string, number>;
  uploaded_files: AggregationUploadedFile[];
  source_cards: AggregationSourceCard[];
  guidance: string[];
}

export interface AggregationCleaningIssue {
  id: string;
  category:
    | "source_gap"
    | "medication_reality"
    | "timeline_gap"
    | "duplicate_candidate"
    | "uncoded_file"
    | "provenance_gap"
    | "patient_context";
  severity: "high" | "medium" | "low";
  status: "open" | "ready_for_review" | "planned" | "resolved";
  title: string;
  body: string;
  recommended_action: string;
  source_ids: string[];
  evidence: string[];
  help_title: string;
  help_body: string;
}

export interface AggregationCleaningQueueResponse {
  patient_id: string;
  patient_label: string;
  issue_counts: Record<string, number>;
  issues: AggregationCleaningIssue[];
  guidance: string[];
}

export interface AggregationReadinessItem {
  id: string;
  label: string;
  status: "ready" | "needs_review" | "missing" | "planned";
  score: number;
  body: string;
  next_action: string;
}

export interface AggregationReadinessResponse {
  patient_id: string;
  patient_label: string;
  readiness_score: number;
  posture: string;
  checklist: AggregationReadinessItem[];
  blockers: string[];
  export_targets: string[];
}

export interface AggregationUploadResponse {
  file: AggregationUploadedFile;
  storage_posture: string;
  source_card: AggregationSourceCard;
}

export interface AggregationUploadPayload {
  file: File;
  data_type: string;
  source_name: string;
  date_range: string;
  contains: string[];
  description: string;
  context_notes: string;
}

export interface AggregationDeleteResponse {
  deleted: boolean;
  file_id: string;
}

// ---------------------------------------------------------------------------
// Guest harmonization
// ---------------------------------------------------------------------------

export interface GuestHarmonizationUploadedFile {
  file_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
  storage_path: string;
  status: "uploaded";
}

export interface GuestHarmonizationOutput {
  output_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  storage_path: string;
}

export type GuestHarmonizationAudience =
  | "patient-summary"
  | "clinician-handoff"
  | "second-opinion"
  | "preop-review";

export interface GuestHarmonizationRunResponse {
  run_id: string;
  mode: "guest";
  created_at: string;
  expires_at: string;
  uploaded_files: GuestHarmonizationUploadedFile[];
  outputs: GuestHarmonizationOutput[];
  status: "ready" | "processing" | "completed" | "expired" | "failed";
  disclosure: string;
  patient_voice?: string | null;
  audience?: GuestHarmonizationAudience | "" | null;
}

export interface GuestHarmonizationContextRequest {
  patient_voice?: string | null;
  audience?: GuestHarmonizationAudience | "" | null;
}

export interface GuestHarmonizationDeleteResponse {
  deleted: boolean;
  run_id: string;
}

export interface GuestHarmonizationOutputPackage {
  schema_version: "atlas.harmonized_record.v1";
  created_at: string;
  source_files: Array<Record<string, unknown>>;
  patient: Record<string, unknown>;
  facts: Array<Record<string, unknown>>;
  provenance: Array<Record<string, unknown>>;
  quality_issues: Array<Record<string, unknown>>;
}

// Patient classifications

export interface ClassificationBestExample {
  patient_id: string;
  name: string;
  age: number;
  complexity_tier: string;
  total_resources: number;
  n_active_conditions: number;
  n_active_medications: number;
  drug_classes: string[];
  risky_combos: string[];
}

export interface ClassificationCategory {
  count: number;
  best_example: ClassificationBestExample;
  patient_ids: string[];
}

export interface ClassificationsResponse {
  categories: Record<string, ClassificationCategory>;
  population_stats: {
    total_patients: number;
    tier_distribution: Record<string, number>;
    age_distribution: Record<string, number>;
    med_count_distribution: Record<string, number>;
  };
}

// ---------------------------------------------------------------------------
// Harmonize endpoints — cross-source merge with FHIR Provenance
// ---------------------------------------------------------------------------

export interface HarmonizeCollection {
  id: string;
  name: string;
  description: string;
  source_count: number;
}

export interface HarmonizeCollectionsResponse {
  collections: HarmonizeCollection[];
}

export interface HarmonizeSource {
  id: string;
  label: string;
  kind: "fhir-pull" | "extracted-pdf" | string;
  available: boolean;
  document_reference: string | null;
  resource_counts: Record<string, number>;
  total_resources: number;
  status: "structured" | "unparsed_structured" | "pending_extraction" | "extracted" | "empty_extraction" | "identity_mismatch" | "missing";
  status_label: string;
}

export interface HarmonizeSourceManifestResponse {
  collection_id: string;
  sources: HarmonizeSource[];
}

export interface HarmonizeObservationSource {
  source_label: string;
  source_observation_ref: string;
  value: number | null;
  unit: string | null;
  raw_value: number | null;
  raw_unit: string | null;
  effective_date: string | null;
  document_reference: string | null;
  reference_low?: number | null;
  reference_high?: number | null;
  reference_unit?: string | null;
}

export interface HarmonizeLatestObservation {
  value: number | null;
  unit: string | null;
  source_label: string;
  effective_date: string | null;
}

export interface HarmonizeMergedObservation {
  merged_ref: string | null;
  canonical_name: string;
  loinc_code: string | null;
  canonical_unit: string | null;
  source_count: number;
  measurement_count: number;
  has_conflict: boolean;
  latest: HarmonizeLatestObservation | null;
  sources: HarmonizeObservationSource[];
}

export interface HarmonizeObservationsResponse {
  collection_id: string;
  total: number;
  cross_source: number;
  merged: HarmonizeMergedObservation[];
}

export interface HarmonizeConditionSource {
  source_label: string;
  source_condition_ref: string;
  display: string;
  snomed: string | null;
  icd10: string | null;
  icd9: string | null;
  clinical_status: string | null;
  onset_date: string | null;
  document_reference: string | null;
}

export interface HarmonizeMergedCondition {
  merged_ref: string | null;
  canonical_name: string;
  snomed: string | null;
  icd10: string | null;
  icd9: string | null;
  is_active: boolean;
  source_count: number;
  occurrence_count: number;
  sources: HarmonizeConditionSource[];
}

export interface HarmonizeConditionsResponse {
  collection_id: string;
  total: number;
  cross_source: number;
  merged: HarmonizeMergedCondition[];
}

export interface HarmonizeMedicationSource {
  source_label: string;
  source_request_ref: string;
  display: string;
  rxnorm_codes: string[];
  status: string | null;
  authored_on: string | null;
  document_reference: string | null;
}

export interface HarmonizeMergedMedication {
  merged_ref: string | null;
  canonical_name: string;
  rxnorm_codes: string[];
  is_active: boolean;
  source_count: number;
  occurrence_count: number;
  sources: HarmonizeMedicationSource[];
}

export interface HarmonizeMedicationsResponse {
  collection_id: string;
  total: number;
  cross_source: number;
  merged: HarmonizeMergedMedication[];
}

export interface HarmonizeContributionTotals {
  observations: number;
  conditions: number;
  medications: number;
  allergies: number;
  immunizations: number;
  encounters: number;
  procedures: number;
  diagnostic_reports: number;
  clinical_notes: number;
  all: number;
}

export interface HarmonizeClinicalNote {
  source_id: string;
  source_label: string;
  resource_type: string;
  resource_id: string;
  note_index: number;
  encounter_id?: string | null;
  date: string | null;
  author?: string | null;
  organization?: string | null;
  document_type?: string | null;
  category?: string | null;
  time?: string | null;
  section_title?: string | null;
  attachment_content_type?: string | null;
  text: string;
}

export interface HarmonizeClinicalArtifact {
  source_id: string;
  source_label: string;
  id: string;
  status: string;
  display: string;
  type: string;
  reason: string;
  category: string;
  class_code: string;
  period_start: string | null;
  period_end: string | null;
  performed_start: string | null;
  performed_end: string | null;
  effective_date: string | null;
  encounter_id: string | null;
  provider: string;
  site: string;
  service_provider: string;
  performer_labels: string[];
  performer_organization_labels: string[];
  performer_practitioner_labels: string[];
  specialty_labels: string[];
  result_refs: string[];
  has_presented_form: boolean;
  note_preview: string;
}

export interface HarmonizeSourceDiffSourceTotals {
  unique: HarmonizeContributionTotals;
  shared: HarmonizeContributionTotals;
}

export interface HarmonizeSourceDiffUniqueFacts {
  observations: HarmonizeMergedObservation[];
  conditions: HarmonizeMergedCondition[];
  medications: HarmonizeMergedMedication[];
  allergies: HarmonizeMergedAllergy[];
  immunizations: HarmonizeMergedImmunization[];
}

export interface HarmonizeSourceDiffSource {
  id: string;
  label: string;
  kind: string;
  document_reference: string | null;
  totals: HarmonizeSourceDiffSourceTotals;
  unique_facts: HarmonizeSourceDiffUniqueFacts;
}

export interface HarmonizeSourceDiffResponse {
  collection_id: string;
  sources: HarmonizeSourceDiffSource[];
}

export interface HarmonizeContributionsResponse {
  collection_id: string;
  document_reference: string;
  label: string | null;
  kind: string | null;
  observations: HarmonizeMergedObservation[];
  conditions: HarmonizeMergedCondition[];
  medications: HarmonizeMergedMedication[];
  allergies: HarmonizeMergedAllergy[];
  immunizations: HarmonizeMergedImmunization[];
  encounters: HarmonizeClinicalArtifact[];
  procedures: HarmonizeClinicalArtifact[];
  diagnostic_reports: HarmonizeClinicalArtifact[];
  clinical_notes: HarmonizeClinicalNote[];
  totals: HarmonizeContributionTotals;
}

export interface HarmonizeAllergySource {
  source_label: string;
  source_allergy_ref: string;
  display: string;
  snomed: string | null;
  rxnorm: string | null;
  criticality: string | null;
  clinical_status: string | null;
  recorded_date: string | null;
  document_reference: string | null;
}

export interface HarmonizeMergedAllergy {
  merged_ref: string | null;
  canonical_name: string;
  snomed: string | null;
  rxnorm: string | null;
  is_active: boolean;
  highest_criticality: string | null;
  source_count: number;
  occurrence_count: number;
  sources: HarmonizeAllergySource[];
}

export interface HarmonizeAllergiesResponse {
  collection_id: string;
  total: number;
  cross_source: number;
  merged: HarmonizeMergedAllergy[];
}

export interface HarmonizeImmunizationSource {
  source_label: string;
  source_immunization_ref: string;
  display: string;
  cvx: string | null;
  ndc: string | null;
  occurrence_date: string | null;
  status: string | null;
  document_reference: string | null;
}

export interface HarmonizeMergedImmunization {
  merged_ref: string | null;
  canonical_name: string;
  cvx: string | null;
  ndc: string | null;
  occurrence_date: string | null;
  source_count: number;
  occurrence_count: number;
  sources: HarmonizeImmunizationSource[];
}

export interface HarmonizeImmunizationsResponse {
  collection_id: string;
  total: number;
  cross_source: number;
  merged: HarmonizeMergedImmunization[];
}

export interface HarmonizeExtractItem {
  source_id: string;
  label: string;
  extracted_path: string;
  cache_hit: boolean;
  entry_count: number;
  elapsed_seconds: number;
}

export interface HarmonizeExtractJobEvent {
  event_id: string;
  event_type:
    | "job_queued"
    | "file_queued"
    | "job_started"
    | "file_started"
    | "file_completed"
    | "job_completed"
    | "job_failed";
  created_at: string;
  stage: string;
  message: string;
  source_id: string | null;
  source_label: string | null;
  page_start: number | null;
  page_end: number | null;
  page_count: number | null;
  processed_pages: number;
  total_pages: number | null;
  processed_files: number;
  total_files: number;
  progress_basis: "lifecycle" | "metadata" | "reported" | "estimated";
  is_estimate: boolean;
}

export interface HarmonizeExtractResponse {
  collection_id: string;
  extracted: HarmonizeExtractItem[];
}

export interface HarmonizeExtractJobResponse {
  job_id: string;
  collection_id: string;
  status: "pending" | "running" | "complete" | "failed";
  results: HarmonizeExtractItem[];
  error: string | null;
  started_at: string;
  completed_at: string | null;
  progress_percent: number;
  stage: string;
  detail: string | null;
  total_files: number;
  processed_files: number;
  total_pages: number | null;
  processed_pages: number;
  estimated_processed_pages?: number;
  current_source_label: string | null;
  estimated_seconds: number | null;
  progress_mode: "reported" | "estimated" | "lifecycle";
  events: HarmonizeExtractJobEvent[];
}

export interface HarmonizeRunFactCounts {
  observations: number;
  conditions: number;
  medications: number;
  allergies: number;
  immunizations: number;
  procedures: number;
  diagnostic_reports: number;
  clinical_documents: number;
  clinical_notes: number;
}

export interface HarmonizeRunSummary {
  source_count: number;
  prepared_source_count: number;
  needs_preparation_count: number;
  candidate_counts: HarmonizeRunFactCounts;
  cross_source_counts: HarmonizeRunFactCounts;
  total_candidate_facts: number;
  cross_source_facts: number;
  conflict_count: number;
  review_item_count: number;
  publishable: boolean;
}

export interface HarmonizeRunSource {
  id: string;
  label: string;
  kind: string;
  document_reference: string | null;
  path: string;
  exists: boolean;
  size_bytes: number | null;
  modified_at: string | null;
  sha256: string | null;
  status: string;
  status_label: string;
  total_resources: number;
  resource_counts: Record<string, number>;
}

export interface HarmonizeRunReviewItem {
  id: string;
  category: string;
  severity: "low" | "medium" | "high";
  title: string;
  body: string;
  source_id: string | null;
  resource_type: string | null;
  merged_ref: string | null;
  resolved: boolean;
  decision: string | null;
  decision_notes: string;
  selected_source_ref: string | null;
  resolved_at: string | null;
}

export interface HarmonizeReviewEvent {
  event_id: string;
  event_type: "review_decision";
  collection_id: string | null;
  run_id: string | null;
  item_id: string;
  category: string | null;
  severity: string | null;
  source_id: string | null;
  resource_type: string | null;
  merged_ref: string | null;
  decision: string;
  notes: string;
  selected_source_ref: string | null;
  resolved: boolean;
  resolved_at: string | null;
  created_at: string;
  actor: string;
  previous_decision: string | null;
  previous_resolved: boolean;
  previous_selected_source_ref: string | null;
}

export interface HarmonizeReviewDecisionSummary {
  event_count: number;
  resolved_item_count: number;
  open_item_count: number;
  latest_event_at: string | null;
  decisions: Record<string, number>;
}

export interface HarmonizeReviewDecisionPayload {
  item_id: string;
  decision:
    | "accepted"
    | "dismissed"
    | "source_fixed"
    | "overridden"
    | "kept_separate"
    | "deferred";
  notes?: string;
  selected_source_ref?: string | null;
}

export interface HarmonizeRunResponse {
  run_id: string;
  collection_id: string;
  collection_name: string;
  status: "complete" | "failed";
  rule_version: string;
  started_at: string;
  completed_at: string;
  duration_seconds: number;
  sources: HarmonizeRunSource[];
  summary: HarmonizeRunSummary;
  review_items: HarmonizeRunReviewItem[];
  review_events: HarmonizeReviewEvent[];
  review_decision_summary: HarmonizeReviewDecisionSummary;
  artifact_path: string;
}

export interface HarmonizeRunStateResponse {
  collection_id: string;
  latest_run: HarmonizeRunResponse | null;
}

export interface PublishedChartChangeSummary {
  previous_snapshot_id: string | null;
  previous_run_id: string | null;
  fact_delta: number;
  source_delta: number;
  review_item_delta: number;
  candidate_count_delta: HarmonizeRunFactCounts;
  headline: string;
}

export interface PublishedChartSnapshot {
  snapshot_id: string;
  collection_id: string;
  run_id: string;
  collection_name: string;
  published_at: string;
  run_completed_at: string;
  rule_version: string;
  artifact_path: string;
  summary: HarmonizeRunSummary;
  source_count: number;
  candidate_fact_count: number;
  review_item_count: number;
  review_decision_summary: HarmonizeReviewDecisionSummary;
  activated_at: string | null;
  activated_from_snapshot_id: string | null;
  change_summary: PublishedChartChangeSummary;
  is_active: boolean;
}

export interface PublishedChartStateResponse {
  collection_id: string;
  active_snapshot: PublishedChartSnapshot | null;
  snapshots: PublishedChartSnapshot[];
}

export interface HarmonizeCanonicalSelectionLatest {
  value?: number | string | null;
  unit?: string | null;
  source_label?: string | null;
  effective_date?: string | null;
}

export interface HarmonizeCanonicalSelection {
  applied?: boolean;
  decision?: string | null;
  review_item_id?: string | null;
  resolved_at?: string | null;
  notes?: string | null;
  selected_source_ref?: string | null;
  selected_source_label?: string | null;
  selected_latest?: HarmonizeCanonicalSelectionLatest | null;
  previous_latest?: HarmonizeCanonicalSelectionLatest | null;
  warning?: string | null;
  retains_all_source_values?: boolean;
}

export interface HarmonizeProvenanceResponse {
  collection_id: string;
  merged_ref: string;
  canonical_selection?: HarmonizeCanonicalSelection | null;
  // FHIR Provenance dict — shape stable but free-form on the wire
  provenance: {
    resourceType: string;
    target: { reference: string }[];
    recorded: string;
    activity: { coding: { system: string; code: string; display: string }[] };
    agent: { type: { coding: { code: string; display: string }[] }; who: { display: string } }[];
    entity: {
      role: string;
      what: { reference: string };
      extension: { url: string; valueString: string }[];
    }[];
  };
}

export interface PipelineRunSummary {
  run_id: string;
  pipeline_name: string;
  architecture: string | null;
  lab_root: string;
  status: string;
  pdf_path: string;
  pdf_label: string;
  pdf_sha256: string | null;
  artifact_dir: string;
  source_pdf_artifact: string | null;
  bundle_artifact: string | null;
  eval_artifact: string | null;
  bundle_shape_artifact: string | null;
  ground_truth_artifact: string | null;
  ground_truth_path: string | null;
  has_ground_truth: boolean;
  trace_count: number;
  artifact_urls: Record<string, string>;
  started_at: string | null;
  finished_at: string | null;
  latency_ms: number;
  cost_usd: number;
  total_entries: number;
  weighted_f1: number | null;
  loinc_resolution_rate: number | null;
  patient_link_rate: number | null;
  encounter_link_rate: number | null;
  resource_counts: Record<string, number>;
  error: string | null;
}

export interface PipelineLeaderboardRow {
  name: string;
  architecture: string;
  description: string;
  primary_backends: string[];
  estimated_cost_per_pdf_usd: number | null;
  run_count: number;
  success_count: number;
  failure_count: number;
  success_rate: number | null;
  last_run_at: string | null;
  last_status: string | null;
  last_run_id: string | null;
  avg_latency_ms: number | null;
  avg_cost_usd: number | null;
  avg_entries: number | null;
  best_weighted_f1: number | null;
  latest_weighted_f1: number | null;
  best_clinical_qa_score: number | null;
  latest_clinical_qa_score: number | null;
  latest_eval_run_id: string | null;
  latest_loinc_resolution_rate: number | null;
  latest_patient_link_rate: number | null;
  latest_encounter_link_rate: number | null;
  tested_pdf_count: number;
  recent_runs: PipelineRunSummary[];
}

export interface PipelineSuiteSummary {
  suite_run_id: string;
  suite_name: string;
  root: string;
  cell_count: number;
  succeeded: number;
  failed: number;
  created_at: string | null;
  report_path: string | null;
}

export interface PipelineQuestionEvaluationSummary {
  question_id: string;
  title: string;
  safety_critical: boolean;
  abstained: boolean;
  score: number;
  correctness: number;
  evidence_citation_quality: number;
  hallucination_avoidance: number;
  abstention_quality: number;
  clinical_usefulness: number;
  citation_count: number;
  unsupported_claim_count: number;
  answer_model: string | null;
  answer_latency_ms: number;
  tool_call_count: number;
  missing_required_evidence_types: string[];
}

export interface PipelineEvaluationSummary {
  eval_run_id: string;
  suite_id: string;
  suite_name: string;
  suite_version: string;
  status: string;
  created_at: string;
  finished_at: string | null;
  pipeline_run_id: string;
  pipeline_name: string;
  lab_root: string;
  pdf_label: string;
  artifact_dir: string;
  artifact_urls: Record<string, string>;
  question_count: number;
  safety_critical_count: number;
  overall_score: number | null;
  mean_correctness: number | null;
  mean_evidence_citation_quality: number | null;
  mean_hallucination_avoidance: number | null;
  mean_abstention_quality: number | null;
  unsupported_claim_rate: number | null;
  abstention_rate: number | null;
  latency_ms: number;
  cost_usd: number;
  bundle_stats: Record<string, unknown>;
  question_results: PipelineQuestionEvaluationSummary[];
}

export interface PipelineQuestionEvaluationDetail {
  question_id: string;
  title: string;
  clinical_question: string;
  expected_answer: string | null;
  grading_rubric: string | null;
  required_evidence_types: string[];
  ideal_citations: string[];
  expected_supporting_facts: string[];
  safety_critical: boolean;
  abstention_allowed: boolean;
  answer: string | null;
  abstained: boolean;
  citations: string[];
  claims: string[];
  answer_model: string | null;
  prompt_template_id: string | null;
  harness_name: string | null;
  response_format_version: string | null;
  answer_latency_ms: number;
  tool_call_count: number;
  tool_calls: Record<string, unknown>[];
  cost_usd: number;
  score: number | null;
  correctness: number | null;
  completeness: number | null;
  evidence_citation_quality: number | null;
  cited_fact_support: number | null;
  hallucination_avoidance: number | null;
  abstention_quality: number | null;
  clinical_usefulness: number | null;
  unsupported_claims: string[];
  missing_required_evidence_types: string[];
  grader: string | null;
  grader_rationale: string | null;
  cited_evidence: Record<string, unknown>[];
  available_evidence_count: number;
  artifact_urls: Record<string, string>;
}

export interface PipelineEvaluationDetail {
  summary: PipelineEvaluationSummary;
  context_builder: string | null;
  question_runner: string | null;
  answer_grader: string | null;
  bundle_stats: Record<string, unknown>;
  prompt_contract: Record<string, unknown>;
  run_instructions: Record<string, unknown>;
  questions: PipelineQuestionEvaluationDetail[];
}

export interface PipelineTestCriterion {
  key: string;
  label: string;
  target: string;
  measurement: string;
  why_it_matters: string;
}

export interface PipelineTestPdfSummary {
  pdf_sha256: string | null;
  pdf_label: string;
  original_path: string;
  run_count: number;
  pipeline_count: number;
  pipelines: string[];
  latest_run_at: string | null;
  has_ground_truth: boolean;
  ground_truth_path: string | null;
}

export interface PipelineGoldStandardSummary {
  pipeline_name: string;
  label: string;
  definition: string;
  measurement: string;
  current_run_count: number;
  latest_run_at: string | null;
  artifact_policy: string;
}

export interface PipelineGroundTruthPdfSummary {
  pdf_sha_prefix: string;
  pdf_sha256: string;
  pdf_label: string;
  pdf_path: string;
  latest_version: number;
  created_at: string | null;
  reviewer: string | null;
  source_run_id: string | null;
  resource_counts: Record<string, number>;
  total_entries: number;
  ground_truth_path: string;
}

export interface PipelineGroundTruthSummary {
  definition: string;
  what_it_is_not: string;
  storage_policy: string;
  comparison_policy: string;
  creation_workflow: string[];
  pdf_count: number;
  versions: PipelineGroundTruthPdfSummary[];
}

export interface PipelineLabLeaderboardResponse {
  generated_at: string;
  lab_roots: string[];
  pipelines: PipelineLeaderboardRow[];
  recent_runs: PipelineRunSummary[];
  evaluations: PipelineEvaluationSummary[];
  suites: PipelineSuiteSummary[];
  test_criteria: PipelineTestCriterion[];
  test_pdfs: PipelineTestPdfSummary[];
  gold_standard: PipelineGoldStandardSummary;
  ground_truth: PipelineGroundTruthSummary;
  totals: {
    registered_pipelines: number;
    pipelines_with_runs: number;
    run_count: number;
    success_count: number;
    failure_count: number;
    eval_run_count: number;
    suite_count: number;
  };
}

export type GroundTruthReviewStatus = "draft" | "published";
export type GroundTruthReviewFactStatus =
  | "accepted"
  | "rejected"
  | "edited"
  | "missing"
  | "uncertain"
  | "needs_follow_up"
  | "duplicate"
  | "unsupported";
export type GroundTruthReviewReasonCode =
  | "wrong_value"
  | "wrong_code"
  | "wrong_date"
  | "wrong_unit"
  | "wrong_status"
  | "wrong_linkage"
  | "unsupported_by_pdf"
  | "missing_from_output";
export type GroundTruthReviewAnnotationType =
  | "supports_fact"
  | "contradicts_fact"
  | "missing_fact"
  | "extraction_error"
  | "uncertain";

export interface GroundTruthReviewBBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface GroundTruthReviewPdfAnnotation {
  annotation_id: string;
  page_number: number;
  bbox: GroundTruthReviewBBox;
  annotation_type: GroundTruthReviewAnnotationType;
  linked_resource_ref: string | null;
  note: string;
  created_at: string;
  updated_at: string;
}

export interface GroundTruthReviewFactDecision {
  decision_id: string;
  resource_ref: string;
  resource_type: string;
  resource_id: string | null;
  status: GroundTruthReviewFactStatus;
  reason_codes: GroundTruthReviewReasonCode[];
  original_resource: Record<string, unknown> | null;
  edited_resource: Record<string, unknown> | null;
  reviewer_note: string;
  linked_annotation_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface GroundTruthReviewSession {
  review_id: string;
  run_id: string;
  pdf_sha256: string;
  source_pdf_path: string;
  candidate_bundle_path: string;
  reviewer: string;
  status: GroundTruthReviewStatus;
  created_at: string;
  updated_at: string;
  published_ground_truth_version: number | null;
  decisions: GroundTruthReviewFactDecision[];
  annotations: GroundTruthReviewPdfAnnotation[];
  notes: string;
}

export interface GroundTruthReviewProgress {
  total_facts: number;
  reviewed_facts: number;
  accepted_facts: number;
  rejected_facts: number;
  edited_facts: number;
  uncertain_facts: number;
  missing_facts: number;
  needs_review: number;
}

export interface GroundTruthReviewRunSummary {
  run_id: string;
  pipeline_name: string;
  status: string;
  pdf_label: string;
  pdf_sha256: string | null;
  started_at: string | null;
  finished_at: string | null;
  total_entries: number;
  resource_counts: Record<string, number>;
  has_source_pdf: boolean;
  has_bundle: boolean;
  review_status: GroundTruthReviewStatus | "not_started";
  reviewed_facts: number;
  published_ground_truth_version: number | null;
  existing_ground_truth_versions: number[];
}

export interface GroundTruthReviewFactSummary {
  resource_ref: string;
  resource_type: string;
  resource_id: string | null;
  display: string;
  codes: string[];
  value: string | null;
  date: string | null;
  status: string | null;
  patient_ref: string | null;
  encounter_ref: string | null;
  source_locator: string | null;
  original_resource: Record<string, unknown>;
}

export interface GroundTruthReviewRunDetail {
  run: GroundTruthReviewRunSummary;
  manifest: Record<string, unknown>;
  facts: GroundTruthReviewFactSummary[];
  facts_by_type: Record<string, GroundTruthReviewFactSummary[]>;
  review: GroundTruthReviewSession;
  progress: GroundTruthReviewProgress;
  artifact_urls: Record<string, string>;
}

export interface GroundTruthReviewPublishResponse {
  run_id: string;
  pdf_sha256: string;
  version: number;
  ground_truth_path: string;
  kept_resource_count: number;
  rejected_resource_count: number;
  missing_fact_count: number;
  review: GroundTruthReviewSession;
}

export interface GroundTruthReviewPdfPage {
  page_number: number;
  width: number;
  height: number;
  image_url: string;
}

export interface GroundTruthReviewPdfPagesResponse {
  run_id: string;
  page_count: number;
  scale: number;
  pages: GroundTruthReviewPdfPage[];
}

export interface GroundTruthReviewPdfTextMatch {
  page_number: number;
  bbox: GroundTruthReviewBBox;
  text: string;
  score: number;
  confidence: "high" | "medium" | "low" | string;
  matched_terms: string[];
  strategy: string;
}

export interface GroundTruthReviewFactLocationResponse {
  run_id: string;
  resource_ref: string;
  query: string;
  locator_version: string;
  matches: GroundTruthReviewPdfTextMatch[];
}

export interface GroundTruthVersionSummary {
  version: number;
  created_at: string | null;
  reviewer: string | null;
  source_run_id: string | null;
  notes: string;
  total_entries: number;
  resource_counts: Record<string, number>;
  ground_truth_path: string;
}

export interface CcdaLabProcessorOption {
  id: string;
  label: string;
  input_kinds: Array<"ccda" | "pdf">;
  backend: string;
  available: boolean;
  description: string;
}

export interface CcdaLabProcessorsResponse {
  options: CcdaLabProcessorOption[];
  microsoft_configured: boolean;
  microsoft_status: {
    configured: boolean;
    reachable: boolean;
    mode: "api" | "cli" | "none";
    endpoint: string | null;
    detail: string;
  };
  upload_limit_bytes: number;
}

export interface CcdaLabResourceSample {
  resource_type: string;
  id: string | null;
  display: string;
  status: string;
  date: string;
  value: string;
}

export interface CcdaLabSourceSection {
  title: string;
  code: string | null;
  entry_count: number;
  expected_resource_types: string[];
  emitted_matching_resources: number;
}

export interface CcdaLabSourceSummary {
  document_title: string;
  patient_display: string;
  section_count: number;
  entry_count: number;
  sections: CcdaLabSourceSection[];
}

export interface CcdaLabCoverageSummary {
  source_section_count: number;
  source_entry_count: number;
  mappable_section_count: number;
  mapped_section_count: number;
  emitted_resource_count: number;
  emitted_clinical_resource_count: number;
}

export interface CcdaLabConversionResponse {
  filename: string;
  content_type: string | null;
  input_kind: "ccda" | "pdf";
  processor_id: string;
  processor_label: string;
  backend_used: "microsoft" | "fallback" | "pdf-pipeline";
  latency_ms: number;
  total_entries: number;
  resource_counts: Record<string, number>;
  coverage: CcdaLabCoverageSummary;
  source_summary: CcdaLabSourceSummary | null;
  bundle_shape: Record<string, unknown>;
  samples: CcdaLabResourceSample[];
  warnings: string[];
  bundle: Record<string, unknown>;
}

// T8c — Patient Context augmentation read shapes.
// See docs/architecture/LLM-CONTEXT-AUGMENTATION-PLAN.md §3 + §T8.
export interface PatientVoiceSummaryDTO {
  summary: string;
  citations: string[];
}

export interface EpisodeBriefDTO {
  episode_id: string;
  type: string;
  period_start: string;
  period_end: string | null;
  one_liner: string;
}

export interface HarmonizationCaveatDTO {
  fact_path: string;
  verdict: string;
  confidence: "high" | "medium" | "low" | string;
  rationale: string;
  dissenting_sources: string[];
}

export interface PatientContextAugmentationResponse {
  patient_voice: PatientVoiceSummaryDTO | null;
  episode_briefs: EpisodeBriefDTO[];
  caveats: HarmonizationCaveatDTO[];
}

// Minimal FHIR Composition shape — the narrative endpoint returns the
// raw FHIR resource. The UI mostly reads `section[].title` +
// `section[].text.div`.
export interface FhirCompositionSection {
  title: string;
  text?: { status: string; div: string };
}

export interface FhirComposition {
  resourceType: "Composition";
  id: string;
  status: string;
  date?: string;
  section?: FhirCompositionSection[];
  relatesTo?: Array<{ code: string; targetReference?: { reference: string } }>;
}
