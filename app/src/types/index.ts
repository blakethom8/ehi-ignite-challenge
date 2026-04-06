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

export interface KeyLabsResponse {
  patient_id: string;
  panels: Record<string, LabValue[]>;
  alert_flags: LabAlertFlag[];
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
