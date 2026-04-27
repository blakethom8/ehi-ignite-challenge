// API response types — mirrors api/models.py

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
  linked_observation_count: number;
  linked_condition_count: number;
  linked_procedure_count: number;
  linked_medication_count: number;
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
  observations: ObservationDetail[];
  conditions: ConditionDetail[];
  procedures: ProcedureDetail[];
  medications: MedicationDetail[];
  diagnostic_report_count: number;
  imaging_study_count: number;
}

export interface LabHistoryPoint {
  effective_dt: string | null;
  value: number;
}

export interface LabValue {
  loinc_code: string;
  display: string;
  value: number | null;
  unit: string;
  effective_dt: string | null;
  trend: "up" | "down" | "stable" | null;
  is_abnormal: boolean | null;
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
  drug_classes_present: string[];
}

export interface ProviderAssistantRequest {
  patient_id: string;
  question: string;
  history?: ProviderAssistantTurn[];
  stance?: "opinionated" | "balanced";
  model?: string;
  mode?: string;
  max_tokens?: number;
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
