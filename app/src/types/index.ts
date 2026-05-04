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

export interface CareTeamSummaryItem {
  name: string;
  organizations: string[];
  encounter_count: number;
  latest_encounter_dt: string | null;
  class_breakdown: Record<string, number>;
}

export interface SiteOfServiceSummaryItem {
  name: string;
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
  context_packages?: ProviderAssistantContextPackage[];
  stance?: "opinionated" | "balanced";
  model?: string;
  mode?: string;
  max_tokens?: number;
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
  all: number;
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
}

export interface HarmonizeProvenanceResponse {
  collection_id: string;
  merged_ref: string;
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
