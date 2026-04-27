import axios from "axios";
import type {
  PatientListItem,
  PatientOverview,
  TimelineResponse,
  EncounterDetail,
  KeyLabsResponse,
  CorpusStats,
  SafetyResponse,
  SurgicalRiskResponse,
  ImmunizationResponse,
  ConditionAcuityResponse,
  PatientRiskSummary,
  ObservationDistributionsResponse,
  InteractionResponse,
  FieldCoverageResponse,
  AllergyCriticalityBreakdown,
  ProviderAssistantRequest,
  ProviderAssistantResponse,
  CareJourneyResponse,
  ClassificationsResponse,
  AssistantSettings,
} from "../types";

const http = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export const api = {
  /** Lightweight patient list — names only, no bundle loading */
  listPatients: (): Promise<PatientListItem[]> =>
    http.get<PatientListItem[]>("/patients").then((r) => r.data),

  /** Full patient overview — loads and parses the FHIR bundle */
  getOverview: (patientId: string): Promise<PatientOverview> =>
    http.get<PatientOverview>(`/patients/${patientId}/overview`).then((r) => r.data),

  /** Encounter timeline */
  getTimeline: (patientId: string): Promise<TimelineResponse> =>
    http.get<TimelineResponse>(`/patients/${patientId}/timeline`).then((r) => r.data),

  /** Single encounter detail for preview pane */
  getEncounterDetail: (patientId: string, encounterId: string): Promise<EncounterDetail> =>
    http.get<EncounterDetail>(`/patients/${patientId}/encounters/${encounterId}`).then((r) => r.data),

  /** Raw FHIR Encounter resource JSON from the bundle */
  getRawEncounter: (patientId: string, encounterId: string): Promise<Record<string, unknown>> =>
    http.get<Record<string, unknown>>(`/patients/${patientId}/encounters/${encounterId}/raw`).then((r) => r.data),

  /** Key lab panels for the safety overview */
  getKeyLabs: (patientId: string): Promise<KeyLabsResponse> =>
    http.get<KeyLabsResponse>(`/patients/${patientId}/key-labs`).then((r) => r.data),

  /** Corpus-level aggregate statistics across all 1,180 patients */
  getCorpusStats: (): Promise<CorpusStats> =>
    http.get<CorpusStats>('/corpus/stats').then((r) => r.data),

  /** Pre-op safety flags — drug class risk classification */
  getSafety: (patientId: string): Promise<SafetyResponse> =>
    http.get<SafetyResponse>(`/patients/${patientId}/safety`).then((r) => r.data),

  /** Deterministic pre-op surgical risk score */
  getSurgicalRisk: (patientId: string): Promise<SurgicalRiskResponse> =>
    http.get<SurgicalRiskResponse>(`/patients/${patientId}/surgical-risk`).then((r) => r.data),

  /** Immunization history — all vaccines with dates */
  getImmunizations: (patientId: string): Promise<ImmunizationResponse> =>
    http.get<ImmunizationResponse>(`/patients/${patientId}/immunizations`).then((r) => r.data),

  /** Condition acuity — active conditions ranked by surgical risk */
  getConditionAcuity: (patientId: string): Promise<ConditionAcuityResponse> =>
    http.get<ConditionAcuityResponse>(`/patients/${patientId}/condition-acuity`).then((r) => r.data),

  /** Risk summary for all patients — complexity tier + critical safety flags */
  getRiskSummary: (): Promise<PatientRiskSummary[]> =>
    http.get<{ patients: PatientRiskSummary[] }>("/patients/risk-summary").then((r) => r.data.patients),

  /** Population-level LOINC observation distributions across all 1,180 patients */
  getObservationDistributions: (): Promise<ObservationDistributionsResponse> =>
    http.get<ObservationDistributionsResponse>("/corpus/observation-distributions").then((r) => r.data),

  /** Drug-drug interaction checker — flags known interactions between active medications */
  getInteractions: (patientId: string): Promise<InteractionResponse> =>
    http.get<InteractionResponse>(`/patients/${patientId}/interactions`).then((r) => r.data),

  /** Field coverage profiler across the full corpus */
  getFieldCoverage: (): Promise<FieldCoverageResponse> =>
    http.get<FieldCoverageResponse>("/corpus/field-coverage").then((r) => r.data),

  /** Allergy criticality + category breakdown across the full corpus */
  getAllergyCriticalityBreakdown: (): Promise<AllergyCriticalityBreakdown> =>
    http.get<AllergyCriticalityBreakdown>("/corpus/allergies/criticality-breakdown").then((r) => r.data),

  /** Care journey — medication episodes, conditions, encounters for Gantt timeline */
  getCareJourney: (patientId: string): Promise<CareJourneyResponse> =>
    http.get<CareJourneyResponse>(`/patients/${patientId}/care-journey`).then((r) => r.data),

  /** Provider-facing chart Q&A */
  chatProviderAssistant: (payload: ProviderAssistantRequest): Promise<ProviderAssistantResponse> =>
    http.post<ProviderAssistantResponse>("/assistant/chat", payload).then((r) => r.data),

  /** Assistant settings — available modes, models, current config */
  getAssistantSettings: (): Promise<AssistantSettings> =>
    http.get<AssistantSettings>("/assistant/settings").then((r) => r.data),

  /** Patient classification categories */
  getClassifications: (): Promise<ClassificationsResponse> =>
    http.get<ClassificationsResponse>("/classifications").then((r) => r.data),

  /** Raw FHIR bundle JSON for a patient */
  getRawFhir: (patientId: string): Promise<Record<string, unknown>> =>
    http.get<Record<string, unknown>>(`/patients/${patientId}/fhir`).then((r) => r.data),
};
