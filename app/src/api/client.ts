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
  ProceduresResponse,
  ProviderAssistantRequest,
  ProviderAssistantResponse,
  CareJourneyResponse,
  ClassificationsResponse,
  AssistantSettings,
  PatientContextExportResponse,
  PatientContextSessionResponse,
  PatientContextSourceMode,
  PatientContextStatus,
  PatientContextTurnResponse,
  AggregationCleaningQueueResponse,
  AggregationDeleteResponse,
  HarmonizeCollection,
  HarmonizeAllergiesResponse,
  HarmonizeCollectionsResponse,
  HarmonizeConditionsResponse,
  HarmonizeContributionsResponse,
  HarmonizeExtractJobResponse,
  HarmonizeSourceDiffResponse,
  HarmonizeImmunizationsResponse,
  HarmonizeMedicationsResponse,
  HarmonizeObservationsResponse,
  HarmonizeProvenanceResponse,
  HarmonizeSourceManifestResponse,
  AggregationEnvironmentResponse,
  AggregationCreateProfilePayload,
  AggregationCreateProfileResponse,
  AggregationPreparedPreviewResponse,
  AggregationReadinessResponse,
  AggregationUploadPayload,
  AggregationUploadResponse,
  CanonicalPatientSummary,
} from "../types";
import { mockPatients } from "./mockData";

const http = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

const useMockData = import.meta.env.VITE_USE_MOCK_DATA === "true";

async function getOrMock<T>(request: Promise<T>, fallback: T): Promise<T> {
  if (useMockData) return fallback;
  try {
    return await request;
  } catch (error) {
    if (import.meta.env.DEV) {
      console.warn("API unavailable; using frontend mock data for this request.", error);
      return fallback;
    }
    throw error;
  }
}

export const api = {
  /** Lightweight patient list — names only, no bundle loading */
  listPatients: (): Promise<PatientListItem[]> =>
    getOrMock(http.get<PatientListItem[]>("/patients").then((r) => r.data), mockPatients),

  /** Full patient overview — loads and parses the FHIR bundle */
  getOverview: (patientId: string): Promise<PatientOverview> =>
    http.get<PatientOverview>(`/patients/${patientId}/overview`).then((r) => r.data),

  /** Canonical patient workspace summary — source-agnostic read facade */
  getCanonicalSummary: (patientId: string): Promise<CanonicalPatientSummary> =>
    http.get<CanonicalPatientSummary>(`/canonical/${patientId}/summary`).then((r) => r.data),

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

  /** Procedure history */
  getProcedures: (patientId: string): Promise<ProceduresResponse> =>
    http.get<ProceduresResponse>(`/patients/${patientId}/procedures`).then((r) => r.data),

  /** Provider-facing chart Q&A */
  chatProviderAssistant: (payload: ProviderAssistantRequest): Promise<ProviderAssistantResponse> =>
    http.post<ProviderAssistantResponse>("/assistant/chat", payload).then((r) => r.data),

  /** Patient-facing guided context intake */
  getPatientContextStatus: (): Promise<PatientContextStatus> =>
    http.get<PatientContextStatus>("/patient-context/status").then((r) => r.data),

  createPatientContextSession: (
    patientId: string,
    sourceMode: PatientContextSourceMode = "selected_patient",
  ): Promise<PatientContextSessionResponse> =>
    http.post<PatientContextSessionResponse>("/patient-context/sessions", {
      patient_id: patientId,
      source_mode: sourceMode,
    }).then((r) => r.data),

  sendPatientContextTurn: (
    sessionId: string,
    message: string,
    selectedGapId?: string | null,
  ): Promise<PatientContextTurnResponse> =>
    http.post<PatientContextTurnResponse>(`/patient-context/sessions/${sessionId}/turn`, {
      message,
      selected_gap_id: selectedGapId || undefined,
    }).then((r) => r.data),

  exportPatientContext: (sessionId: string): Promise<PatientContextExportResponse> =>
    http.post<PatientContextExportResponse>(`/patient-context/sessions/${sessionId}/export`).then((r) => r.data),

  /** Data Aggregator workflow */
  createAggregationProfile: (payload: AggregationCreateProfilePayload = {}): Promise<AggregationCreateProfileResponse> =>
    http.post<AggregationCreateProfileResponse>("/aggregation/profiles", payload).then((r) => r.data),

  getAggregationSources: (patientId: string): Promise<AggregationEnvironmentResponse> =>
    http.get<AggregationEnvironmentResponse>(`/aggregation/sources/${patientId}`).then((r) => r.data),

  getAggregationCleaningQueue: (patientId: string): Promise<AggregationCleaningQueueResponse> =>
    http.get<AggregationCleaningQueueResponse>(`/aggregation/cleaning-queue/${patientId}`).then((r) => r.data),

  getAggregationReadiness: (patientId: string): Promise<AggregationReadinessResponse> =>
    http.get<AggregationReadinessResponse>(`/aggregation/readiness/${patientId}`).then((r) => r.data),

  uploadAggregationFile: (patientId: string, payload: AggregationUploadPayload): Promise<AggregationUploadResponse> => {
    const form = new FormData();
    form.append("file", payload.file);
    form.append("data_type", payload.data_type);
    form.append("source_name", payload.source_name);
    form.append("date_range", payload.date_range);
    form.append("contains", JSON.stringify(payload.contains));
    form.append("description", payload.description);
    form.append("context_notes", payload.context_notes);
    return http.post<AggregationUploadResponse>(`/aggregation/uploads/${patientId}`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },

  deleteAggregationFile: (patientId: string, fileId: string): Promise<AggregationDeleteResponse> =>
    http.delete<AggregationDeleteResponse>(`/aggregation/uploads/${patientId}/${fileId}`).then((r) => r.data),

  getAggregationUploadPreview: (patientId: string, fileId: string): Promise<AggregationPreparedPreviewResponse> =>
    http
      .get<AggregationPreparedPreviewResponse>(`/aggregation/uploads/${patientId}/${fileId}/preview`)
      .then((r) => r.data),

  getAggregationUploadJson: (patientId: string, fileId: string): Promise<Record<string, unknown>> =>
    http
      .get<Record<string, unknown>>(`/aggregation/uploads/${patientId}/${fileId}/prepared-json`)
      .then((r) => r.data),

  /** Assistant settings — available modes, models, current config */
  getAssistantSettings: (): Promise<AssistantSettings> =>
    http.get<AssistantSettings>("/assistant/settings").then((r) => r.data),

  /** Patient classification categories */
  getClassifications: (): Promise<ClassificationsResponse> =>
    http.get<ClassificationsResponse>("/classifications").then((r) => r.data),

  /** Raw FHIR bundle JSON for a patient */
  getRawFhir: (patientId: string): Promise<Record<string, unknown>> =>
    http.get<Record<string, unknown>>(`/patients/${patientId}/fhir`).then((r) => r.data),

  // -------------------------------------------------------------------------
  // Harmonize — cross-source merge with FHIR Provenance
  // -------------------------------------------------------------------------

  getHarmonizeCollections: (): Promise<HarmonizeCollectionsResponse> =>
    http.get<HarmonizeCollectionsResponse>("/harmonize/collections").then((r) => r.data),

  getHarmonizeWorkspace: (patientId: string): Promise<HarmonizeCollection> =>
    http
      .get<HarmonizeCollection>(`/harmonize/workspaces/${encodeURIComponent(patientId)}`)
      .then((r) => r.data),

  getHarmonizeSources: (collectionId: string): Promise<HarmonizeSourceManifestResponse> =>
    http
      .get<HarmonizeSourceManifestResponse>(`/harmonize/${collectionId}/sources`)
      .then((r) => r.data),

  getHarmonizeObservations: (
    collectionId: string,
    crossSourceOnly = false,
  ): Promise<HarmonizeObservationsResponse> =>
    http
      .get<HarmonizeObservationsResponse>(`/harmonize/${collectionId}/observations`, {
        params: { cross_source_only: crossSourceOnly },
      })
      .then((r) => r.data),

  getHarmonizeConditions: (
    collectionId: string,
    crossSourceOnly = false,
  ): Promise<HarmonizeConditionsResponse> =>
    http
      .get<HarmonizeConditionsResponse>(`/harmonize/${collectionId}/conditions`, {
        params: { cross_source_only: crossSourceOnly },
      })
      .then((r) => r.data),

  getHarmonizeMedications: (
    collectionId: string,
    crossSourceOnly = false,
  ): Promise<HarmonizeMedicationsResponse> =>
    http
      .get<HarmonizeMedicationsResponse>(`/harmonize/${collectionId}/medications`, {
        params: { cross_source_only: crossSourceOnly },
      })
      .then((r) => r.data),

  getHarmonizeAllergies: (
    collectionId: string,
    crossSourceOnly = false,
  ): Promise<HarmonizeAllergiesResponse> =>
    http
      .get<HarmonizeAllergiesResponse>(`/harmonize/${collectionId}/allergies`, {
        params: { cross_source_only: crossSourceOnly },
      })
      .then((r) => r.data),

  getHarmonizeImmunizations: (
    collectionId: string,
    crossSourceOnly = false,
  ): Promise<HarmonizeImmunizationsResponse> =>
    http
      .get<HarmonizeImmunizationsResponse>(`/harmonize/${collectionId}/immunizations`, {
        params: { cross_source_only: crossSourceOnly },
      })
      .then((r) => r.data),

  getHarmonizeProvenance: (
    collectionId: string,
    mergedRef: string,
  ): Promise<HarmonizeProvenanceResponse> =>
    http
      .get<HarmonizeProvenanceResponse>(
        `/harmonize/${collectionId}/provenance/${encodeURIComponent(mergedRef)}`,
      )
      .then((r) => r.data),

  getHarmonizeContributions: (
    collectionId: string,
    documentReference: string,
  ): Promise<HarmonizeContributionsResponse> =>
    http
      .get<HarmonizeContributionsResponse>(
        `/harmonize/${collectionId}/contributions/${encodeURIComponent(documentReference)}`,
      )
      .then((r) => r.data),

  getHarmonizeSourceDiff: (
    collectionId: string,
  ): Promise<HarmonizeSourceDiffResponse> =>
    http
      .get<HarmonizeSourceDiffResponse>(`/harmonize/${collectionId}/source-diff`)
      .then((r) => r.data),

  /**
   * Start a background extraction job. Returns immediately with job_id;
   * poll `getHarmonizeExtractJob(jobId)` until status is complete/failed.
   */
  extractHarmonizeCollection: (collectionId: string): Promise<HarmonizeExtractJobResponse> =>
    http
      .post<HarmonizeExtractJobResponse>(`/harmonize/${collectionId}/extract`)
      .then((r) => r.data),

  getHarmonizeExtractJob: (jobId: string): Promise<HarmonizeExtractJobResponse> =>
    http
      .get<HarmonizeExtractJobResponse>(`/harmonize/extract-jobs/${jobId}`)
      .then((r) => r.data),

  getLatestHarmonizeExtractJob: (collectionId: string): Promise<HarmonizeExtractJobResponse> =>
    http
      .get<HarmonizeExtractJobResponse>(`/harmonize/${collectionId}/extract-job`)
      .then((r) => r.data),
};
