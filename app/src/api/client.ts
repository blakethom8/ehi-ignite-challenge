import axios from "axios";
import type { PatientListItem, PatientOverview, TimelineResponse, EncounterDetail, KeyLabsResponse, CorpusStats, SafetyResponse, ImmunizationResponse, ConditionAcuityResponse } from "../types";

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

  /** Immunization history — all vaccines with dates */
  getImmunizations: (patientId: string): Promise<ImmunizationResponse> =>
    http.get<ImmunizationResponse>(`/patients/${patientId}/immunizations`).then((r) => r.data),

  /** Condition acuity — active conditions ranked by surgical risk */
  getConditionAcuity: (patientId: string): Promise<ConditionAcuityResponse> =>
    http.get<ConditionAcuityResponse>(`/patients/${patientId}/condition-acuity`).then((r) => r.data),
};
