import axios from "axios";
import type {
  AuthSessionResponse,
  Capabilities,
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
  ClinicalNotesResponse,
  AssistantStreamCallbacks,
  AssistantStreamEvent,
  ProviderAssistantRequest,
  ProviderAssistantResponse,
  WorkflowRunRequest,
  WorkflowRunResponse,
  CaspianFileListResponse,
  CaspianFileReadResponse,
  CaspianFileWriteRequest,
  CaspianFileWriteResponse,
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
  HarmonizeReviewDecisionPayload,
  HarmonizeRunResponse,
  HarmonizeRunStateResponse,
  HarmonizeSourceManifestResponse,
  PublishedChartStateResponse,
  AggregationEnvironmentResponse,
  AggregationCreateProfilePayload,
  AggregationCreateProfileResponse,
  AggregationPreparedPreviewResponse,
  AggregationReadinessResponse,
  AggregationUpdateProfilePayload,
  AggregationUploadPayload,
  AggregationUploadResponse,
  AdminActionResponse,
  AdminAuditListResponse,
  AdminPatchUserPayload,
  AdminSessionSummary,
  AdminUserDetail,
  AdminUserSummary,
  CanonicalPatientSummary,
  GuestHarmonizationContextRequest,
  GuestHarmonizationDeleteResponse,
  GuestHarmonizationOutputPackage,
  GuestHarmonizationRunResponse,
  GroundTruthReviewFactLocationResponse,
  GroundTruthReviewPublishResponse,
  GroundTruthReviewPdfPagesResponse,
  GroundTruthReviewRunDetail,
  GroundTruthReviewRunSummary,
  GroundTruthReviewSession,
  GroundTruthVersionSummary,
  CcdaLabConversionResponse,
  CcdaLabProcessorsResponse,
  PipelineEvaluationDetail,
  PipelineLabLeaderboardResponse,
  PatientContextAugmentationResponse,
  FhirComposition,
} from "../types";
import {
  getMockAggregationCleaningQueue,
  getMockAggregationReadiness,
  getMockAggregationSources,
  getMockAggregationUploadJson,
  getMockAggregationUploadPreview,
  getMockCanonicalSummary,
  getMockHarmonizeCollections,
  getMockHarmonizeWorkspace,
  getMockLatestHarmonizationRun,
  getMockOverview,
  getMockPatientContextStatus,
  getMockPublishedChart,
  mockPatients,
} from "./mockData";

const http = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

const useMockData = import.meta.env.VITE_USE_MOCK_DATA === "true";

async function getOrMock<T>(request: Promise<T>, fallback: T): Promise<T> {
  if (useMockData) return fallback;
  return request;
}

async function getOrDemoFallback<T>(
  request: Promise<T>,
  fallbackFactory: () => T,
  entityId?: string | null,
): Promise<T> {
  if (useMockData) return fallbackFactory();
  try {
    return await request;
  } catch (error) {
    if (axios.isAxiosError(error) && entityId?.startsWith("demo-")) {
      const status = error.response?.status;
      if (status === 401 || status === 403 || status === 404 || status === 500) {
        return fallbackFactory();
      }
    }
    throw error;
  }
}

export const api = {
  getAuthSession: (): Promise<AuthSessionResponse> =>
    http.get<AuthSessionResponse>("/auth/session").then((r) => r.data),

  /**
   * Server-declared capability surface for the current session (anonymous,
   * demo, authenticated, or guest). Always returns 200 with the appropriate
   * mode's policy. Frontend should not re-derive capabilities locally.
   */
  getCapabilities: (): Promise<Capabilities> =>
    http.get<Capabilities>("/auth/capabilities").then((r) => r.data),

  login: (email: string, password: string): Promise<AuthSessionResponse> =>
    http.post<AuthSessionResponse>("/auth/login", { email, password }).then((r) => r.data),

  signup: (email: string, password: string, displayName: string): Promise<AuthSessionResponse> =>
    http
      .post<AuthSessionResponse>("/auth/signup", { email, password, display_name: displayName })
      .then((r) => r.data),

  logout: (): Promise<AuthSessionResponse> =>
    http.post<AuthSessionResponse>("/auth/logout").then((r) => r.data),

  enterDemo: (patientId: string): Promise<AuthSessionResponse> =>
    http.post<AuthSessionResponse>("/auth/demo", { patient_id: patientId }).then((r) => r.data),

  exitDemo: (): Promise<AuthSessionResponse> =>
    http.post<AuthSessionResponse>("/auth/demo/exit").then((r) => r.data),

  selectActivePatient: (patientId: string | null): Promise<AuthSessionResponse> =>
    http.post<AuthSessionResponse>("/auth/select-patient", { patient_id: patientId }).then((r) => r.data),

  /** Lightweight patient list — names only, no bundle loading */
  listPatients: (): Promise<PatientListItem[]> =>
    getOrMock(http.get<PatientListItem[]>("/patients").then((r) => r.data), mockPatients),

  /** Full patient overview — loads and parses the FHIR bundle */
  getOverview: (patientId: string): Promise<PatientOverview> =>
    getOrMock(
      http.get<PatientOverview>(`/patients/${patientId}/overview`).then((r) => r.data),
      getMockOverview(patientId),
    ),

  /** Canonical patient workspace summary — source-agnostic read facade */
  getCanonicalSummary: (patientId: string): Promise<CanonicalPatientSummary> =>
    getOrMock(
      http.get<CanonicalPatientSummary>(`/canonical/${patientId}/summary`).then((r) => r.data),
      getMockCanonicalSummary(patientId),
    ),

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

  /** Clinical notes from the active published chart snapshot */
  getClinicalNotes: (patientId: string): Promise<ClinicalNotesResponse> =>
    http.get<ClinicalNotesResponse>(`/patients/${patientId}/clinical-notes`).then((r) => r.data),

  /** Provider-facing chart Q&A */
  chatProviderAssistant: (payload: ProviderAssistantRequest): Promise<ProviderAssistantResponse> =>
    http.post<ProviderAssistantResponse>("/assistant/chat", payload).then((r) => r.data),

  /**
   * Streaming variant of /assistant/chat. Emits tool_start / tool_end events as
   * each agent tool runs, then a `done` event with the full response. Aborts
   * cleanly if the AbortSignal fires.
   */
  chatProviderAssistantStream: async (
    payload: ProviderAssistantRequest,
    callbacks: AssistantStreamCallbacks,
    signal?: AbortSignal,
  ): Promise<void> => {
    const response = await fetch("/api/assistant/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(payload),
      signal,
    });
    if (!response.ok || !response.body) {
      throw new Error(
        `Chat stream failed (${response.status}). ${
          response.statusText ?? ""
        }`.trim(),
      );
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      // SSE frames are separated by a blank line. Each frame contains one or
      // more `data: ...` lines; we only emit `data:` payloads.
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let frameEnd = buffer.indexOf("\n\n");
        while (frameEnd !== -1) {
          const frame = buffer.slice(0, frameEnd);
          buffer = buffer.slice(frameEnd + 2);
          frameEnd = buffer.indexOf("\n\n");
          const dataLines = frame
            .split("\n")
            .filter((line) => line.startsWith("data:"))
            .map((line) => line.slice(5).trimStart());
          if (dataLines.length === 0) continue;
          const json = dataLines.join("\n");
          try {
            const event = JSON.parse(json) as AssistantStreamEvent;
            callbacks.onEvent(event);
          } catch {
            // Malformed frame — skip silently; transport keepalives etc.
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  /** Run a prepared Caspian workflow packet and get back a structured artifact for the workbench. */
  runCaspianWorkflow: (payload: WorkflowRunRequest): Promise<WorkflowRunResponse> =>
    http.post<WorkflowRunResponse>("/caspian/workflows/run", payload).then((r) => r.data),

  /** List the Caspian file workspace tree for (session, patient). */
  listCaspianFiles: (patientId: string): Promise<CaspianFileListResponse> =>
    http
      .get<CaspianFileListResponse>("/caspian/files/list", { params: { patient_id: patientId } })
      .then((r) => r.data),

  /** Read a single Caspian workspace file by relative path. */
  readCaspianFile: (patientId: string, path: string): Promise<CaspianFileReadResponse> =>
    http
      .get<CaspianFileReadResponse>("/caspian/files/read", { params: { patient_id: patientId, path } })
      .then((r) => r.data),

  /** Write (overwrite) a Caspian workspace file. */
  writeCaspianFile: (payload: CaspianFileWriteRequest): Promise<CaspianFileWriteResponse> =>
    http.put<CaspianFileWriteResponse>("/caspian/files/write", payload).then((r) => r.data),

  /**
   * Copy a generated workflow-run artifact into the user's notes/ folder.
   * Authenticated sessions only — the backend 403s for demo/guest. Filename
   * collisions in notes/ are resolved with a -2 / -3 / … suffix on the stem.
   */
  saveCaspianFileAsNote: (patientId: string, sourcePath: string): Promise<CaspianFileWriteResponse> =>
    http
      .post<CaspianFileWriteResponse>("/caspian/files/save-as-note", {
        patient_id: patientId,
        source_path: sourcePath,
      })
      .then((r) => r.data),

  /** Patient-facing guided context intake */
  getPatientContextStatus: (): Promise<PatientContextStatus> =>
    getOrMock(
      http.get<PatientContextStatus>("/patient-context/status").then((r) => r.data),
      getMockPatientContextStatus(),
    ),

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

  updateAggregationProfile: (patientId: string, payload: AggregationUpdateProfilePayload): Promise<AggregationCreateProfileResponse> =>
    http.patch<AggregationCreateProfileResponse>(`/aggregation/profiles/${patientId}`, payload).then((r) => r.data),

  deleteAggregationProfile: (patientId: string): Promise<AggregationDeleteResponse> =>
    http.delete<AggregationDeleteResponse>(`/aggregation/profiles/${patientId}`).then((r) => r.data),

  getAggregationSources: (patientId: string): Promise<AggregationEnvironmentResponse> =>
    getOrDemoFallback(
      http.get<AggregationEnvironmentResponse>(`/aggregation/sources/${patientId}`).then((r) => r.data),
      () => getMockAggregationSources(patientId),
      patientId,
    ),

  getAggregationCleaningQueue: (patientId: string): Promise<AggregationCleaningQueueResponse> =>
    getOrDemoFallback(
      http.get<AggregationCleaningQueueResponse>(`/aggregation/cleaning-queue/${patientId}`).then((r) => r.data),
      () => getMockAggregationCleaningQueue(patientId),
      patientId,
    ),

  getAggregationReadiness: (patientId: string): Promise<AggregationReadinessResponse> =>
    getOrDemoFallback(
      http.get<AggregationReadinessResponse>(`/aggregation/readiness/${patientId}`).then((r) => r.data),
      () => getMockAggregationReadiness(patientId),
      patientId,
    ),

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

  /** Guest temporary harmonization */
  createGuestHarmonizationRun: (): Promise<GuestHarmonizationRunResponse> =>
    http.post<GuestHarmonizationRunResponse>("/guest-harmonization/runs").then((r) => r.data),

  getGuestHarmonizationRun: (runId: string): Promise<GuestHarmonizationRunResponse> =>
    http.get<GuestHarmonizationRunResponse>(`/guest-harmonization/runs/${encodeURIComponent(runId)}`).then((r) => r.data),

  uploadGuestHarmonizationFile: (runId: string, file: File): Promise<GuestHarmonizationRunResponse> => {
    const form = new FormData();
    form.append("file", file);
    return http.post<GuestHarmonizationRunResponse>(
      `/guest-harmonization/runs/${encodeURIComponent(runId)}/uploads`,
      form,
      { headers: { "Content-Type": "multipart/form-data" } },
    ).then((r) => r.data);
  },

  processGuestHarmonizationRun: (runId: string): Promise<GuestHarmonizationRunResponse> =>
    http.post<GuestHarmonizationRunResponse>(`/guest-harmonization/runs/${encodeURIComponent(runId)}/process`).then((r) => r.data),

  getGuestHarmonizationOutput: (runId: string): Promise<GuestHarmonizationOutputPackage> =>
    http.get<GuestHarmonizationOutputPackage>(`/guest-harmonization/runs/${encodeURIComponent(runId)}/output`).then((r) => r.data),

  exportGuestHarmonizationBundle: (runId: string): Promise<Blob> =>
    http
      .get<Blob>(`/guest-harmonization/runs/${encodeURIComponent(runId)}/export-workspace`, {
        responseType: "blob",
      })
      .then((r) => r.data),

  setGuestHarmonizationContext: (
    runId: string,
    payload: GuestHarmonizationContextRequest,
  ): Promise<GuestHarmonizationRunResponse> =>
    http
      .post<GuestHarmonizationRunResponse>(
        `/guest-harmonization/runs/${encodeURIComponent(runId)}/context`,
        payload,
      )
      .then((r) => r.data),

  deleteGuestHarmonizationRun: (runId: string): Promise<GuestHarmonizationDeleteResponse> =>
    http.delete<GuestHarmonizationDeleteResponse>(`/guest-harmonization/runs/${encodeURIComponent(runId)}`).then((r) => r.data),

  getAggregationUploadPreview: (patientId: string, fileId: string): Promise<AggregationPreparedPreviewResponse> =>
    getOrDemoFallback(
      http
        .get<AggregationPreparedPreviewResponse>(`/aggregation/uploads/${patientId}/${fileId}/preview`)
        .then((r) => r.data),
      () => getMockAggregationUploadPreview(patientId, fileId),
      patientId,
    ),

  getAggregationUploadJson: (patientId: string, fileId: string): Promise<Record<string, unknown>> =>
    getOrDemoFallback(
      http
        .get<Record<string, unknown>>(`/aggregation/uploads/${patientId}/${fileId}/prepared-json`)
        .then((r) => r.data),
      () => getMockAggregationUploadJson(patientId, fileId),
      patientId,
    ),

  /** Assistant settings — available modes, models, current config */
  getAssistantSettings: (): Promise<AssistantSettings> =>
    http.get<AssistantSettings>("/assistant/settings").then((r) => r.data),

  /** Patient classification categories */
  getClassifications: (): Promise<ClassificationsResponse> =>
    http.get<ClassificationsResponse>("/classifications").then((r) => r.data),

  /** Raw FHIR bundle JSON for a patient */
  getRawFhir: (patientId: string): Promise<Record<string, unknown>> =>
    http.get<Record<string, unknown>>(`/patients/${patientId}/fhir`).then((r) => r.data),

  /** PDF/FHIR pipeline experiment leaderboard */
  getPipelineLabLeaderboard: (): Promise<PipelineLabLeaderboardResponse> =>
    http.get<PipelineLabLeaderboardResponse>("/pipeline-lab/leaderboard").then((r) => r.data),

  getPipelineLabEvaluationDetail: (evalRunId: string): Promise<PipelineEvaluationDetail> =>
    http.get<PipelineEvaluationDetail>(`/pipeline-lab/evaluations/${encodeURIComponent(evalRunId)}`).then((r) => r.data),

  /** Internal C-CDA/PDF -> FHIR playground */
  getCcdaLabProcessors: (): Promise<CcdaLabProcessorsResponse> =>
    http.get<CcdaLabProcessorsResponse>("/internal/ccda-lab/processors").then((r) => r.data),

  convertCcdaLabDocument: (
    file: File,
    processorId: string,
    skipCache = false,
  ): Promise<CcdaLabConversionResponse> => {
    const form = new FormData();
    form.append("file", file);
    form.append("processor_id", processorId);
    form.append("skip_cache", String(skipCache));
    return http
      .post<CcdaLabConversionResponse>("/internal/ccda-lab/convert", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  /** Human review workspace for candidate reference bundles */
  listGroundTruthReviewRuns: (): Promise<GroundTruthReviewRunSummary[]> =>
    http.get<GroundTruthReviewRunSummary[]>("/ground-truth-review/runs").then((r) => r.data),

  getGroundTruthReviewRun: (runId: string): Promise<GroundTruthReviewRunDetail> =>
    http
      .get<GroundTruthReviewRunDetail>(`/ground-truth-review/runs/${encodeURIComponent(runId)}`)
      .then((r) => r.data),

  getGroundTruthReviewPdfPages: (runId: string): Promise<GroundTruthReviewPdfPagesResponse> =>
    http
      .get<GroundTruthReviewPdfPagesResponse>(`/ground-truth-review/runs/${encodeURIComponent(runId)}/pdf/pages`)
      .then((r) => r.data),

  locateGroundTruthReviewFact: (runId: string, resourceRef: string): Promise<GroundTruthReviewFactLocationResponse> =>
    http
      .get<GroundTruthReviewFactLocationResponse>(`/ground-truth-review/runs/${encodeURIComponent(runId)}/locate-fact`, {
        params: { resource_ref: resourceRef },
      })
      .then((r) => r.data),

  saveGroundTruthReview: (runId: string, review: GroundTruthReviewSession): Promise<GroundTruthReviewSession> =>
    http
      .put<GroundTruthReviewSession>(`/ground-truth-review/runs/${encodeURIComponent(runId)}/review`, review)
      .then((r) => r.data),

  publishGroundTruthReview: (
    runId: string,
    payload: { reviewer?: string; notes?: string } = {},
  ): Promise<GroundTruthReviewPublishResponse> =>
    http
      .post<GroundTruthReviewPublishResponse>(`/ground-truth-review/runs/${encodeURIComponent(runId)}/publish`, payload)
      .then((r) => r.data),

  listReviewedReferenceVersions: (pdfSha: string): Promise<GroundTruthVersionSummary[]> =>
    http
      .get<GroundTruthVersionSummary[]>(`/ground-truth-review/ground-truth/${encodeURIComponent(pdfSha)}`)
      .then((r) => r.data),

  // -------------------------------------------------------------------------
  // Harmonize — cross-source merge with FHIR Provenance
  // -------------------------------------------------------------------------

  getHarmonizeCollections: (): Promise<HarmonizeCollectionsResponse> =>
    getOrMock(
      http.get<HarmonizeCollectionsResponse>("/harmonize/collections").then((r) => r.data),
      getMockHarmonizeCollections(),
    ),

  getHarmonizeWorkspace: (patientId: string): Promise<HarmonizeCollection> =>
    getOrMock(
      http
        .get<HarmonizeCollection>(`/harmonize/workspaces/${encodeURIComponent(patientId)}`)
        .then((r) => r.data),
      getMockHarmonizeWorkspace(patientId),
    ),

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

  runHarmonization: (collectionId: string): Promise<HarmonizeRunResponse> =>
    http
      .post<HarmonizeRunResponse>(`/harmonize/${collectionId}/runs`)
      .then((r) => r.data),

  getLatestHarmonizationRun: (collectionId: string): Promise<HarmonizeRunStateResponse> =>
    getOrDemoFallback(
      http
        .get<HarmonizeRunStateResponse>(`/harmonize/${collectionId}/runs/latest`)
        .then((r) => r.data),
      () => getMockLatestHarmonizationRun(collectionId),
      collectionId,
    ),

  resolveHarmonizationReviewItem: (
    collectionId: string,
    runId: string,
    payload: HarmonizeReviewDecisionPayload,
  ): Promise<HarmonizeRunResponse> =>
    http
      .post<HarmonizeRunResponse>(`/harmonize/${collectionId}/runs/${runId}/review-items/resolve`, payload)
      .then((r) => r.data),

  getPublishedChart: (collectionId: string): Promise<PublishedChartStateResponse> =>
    getOrDemoFallback(
      http
        .get<PublishedChartStateResponse>(`/harmonize/${collectionId}/published`)
        .then((r) => r.data),
      () => getMockPublishedChart(collectionId),
      collectionId,
    ),

  publishHarmonizationRun: (collectionId: string, runId: string): Promise<PublishedChartStateResponse> =>
    http
      .post<PublishedChartStateResponse>(`/harmonize/${collectionId}/runs/${runId}/publish`)
      .then((r) => r.data),

  activatePublishedSnapshot: (collectionId: string, snapshotId: string): Promise<PublishedChartStateResponse> =>
    http
      .post<PublishedChartStateResponse>(`/harmonize/${collectionId}/published/${snapshotId}/activate`)
      .then((r) => r.data),

  unpublishActiveChart: (collectionId: string): Promise<PublishedChartStateResponse> =>
    http
      .delete<PublishedChartStateResponse>(`/harmonize/${collectionId}/published/active`)
      .then((r) => r.data),

  // -------------------------------------------------------------------------
  // Admin — user, session, and activity management
  // -------------------------------------------------------------------------

  adminListUsers: (): Promise<AdminUserSummary[]> =>
    http.get<AdminUserSummary[]>("/admin/users").then((r) => r.data),

  adminGetUser: (userId: string): Promise<AdminUserDetail> =>
    http
      .get<AdminUserDetail>(`/admin/users/${encodeURIComponent(userId)}`)
      .then((r) => r.data),

  adminGetUserActivity: (userId: string, limit = 100): Promise<AdminAuditListResponse> =>
    http
      .get<AdminAuditListResponse>(
        `/admin/users/${encodeURIComponent(userId)}/activity`,
        { params: { limit } },
      )
      .then((r) => r.data),

  adminPatchUser: (
    userId: string,
    payload: AdminPatchUserPayload,
  ): Promise<AdminUserDetail> =>
    http
      .patch<AdminUserDetail>(`/admin/users/${encodeURIComponent(userId)}`, payload)
      .then((r) => r.data),

  adminDeleteUser: (userId: string): Promise<AdminActionResponse> =>
    http
      .delete<AdminActionResponse>(`/admin/users/${encodeURIComponent(userId)}`)
      .then((r) => r.data),

  adminListSessions: (): Promise<AdminSessionSummary[]> =>
    http.get<AdminSessionSummary[]>("/admin/sessions").then((r) => r.data),

  adminRevokeSession: (sessionId: string): Promise<AdminActionResponse> =>
    http
      .delete<AdminActionResponse>(`/admin/sessions/${encodeURIComponent(sessionId)}`)
      .then((r) => r.data),

  // -------------------------------------------------------------------------
  // Self-service account
  // -------------------------------------------------------------------------

  updateAccountProfile: (displayName: string): Promise<AuthSessionResponse> =>
    http
      .patch<AuthSessionResponse>("/auth/me", { display_name: displayName })
      .then((r) => r.data),

  changeAccountPassword: (
    currentPassword: string,
    newPassword: string,
  ): Promise<AdminActionResponse> =>
    http
      .post<AdminActionResponse>("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      })
      .then((r) => r.data),

  deleteAccount: (): Promise<AuthSessionResponse> =>
    http.delete<AuthSessionResponse>("/auth/me").then((r) => r.data),
  // T8c — LLM-augmented context panels on the merged-record page.
  // See docs/architecture/LLM-CONTEXT-AUGMENTATION-PLAN.md §T8.
  getPatientContextAugmentation: (
    patientId: string,
  ): Promise<PatientContextAugmentationResponse> =>
    http
      .get<PatientContextAugmentationResponse>(
        `/patient-context/${encodeURIComponent(patientId)}/augmentation`,
      )
      .then((r) => r.data),

  getPatientContextNarrative: (
    patientId: string,
    episodeSlug: string,
  ): Promise<FhirComposition> =>
    http
      .get<FhirComposition>(
        `/patient-context/${encodeURIComponent(patientId)}/narratives/${encodeURIComponent(episodeSlug)}`,
      )
      .then((r) => r.data),

  getNarrativeHistory: (
    patientId: string,
    episodeSlug: string,
  ): Promise<{
    patient_id: string;
    episode_slug: string;
    versions: Array<{
      timestamp: string;
      composition_id: string | null;
      replaces_id: string | null;
      archived_path: string;
    }>;
  }> =>
    http
      .get(
        `/patient-context/${encodeURIComponent(patientId)}/narratives/${encodeURIComponent(episodeSlug)}/history`,
      )
      .then((r) => r.data),

  getArchivedNarrative: (
    patientId: string,
    episodeSlug: string,
    timestamp: string,
  ): Promise<FhirComposition> =>
    http
      .get<FhirComposition>(
        `/patient-context/${encodeURIComponent(patientId)}/narratives/${encodeURIComponent(episodeSlug)}/history/${encodeURIComponent(timestamp)}`,
      )
      .then((r) => r.data),

  getSnapshotDiff: (
    collectionId: string,
    snapshotId: string,
    against?: string,
  ): Promise<{
    snapshot_a: { snapshot_id: string; run_id: string; published_at: string | null };
    snapshot_b: { snapshot_id: string; run_id: string; published_at: string | null };
    categories: Record<
      string,
      {
        added: Array<{ merged_ref: string; label: string; value: string }>;
        removed: Array<{ merged_ref: string; label: string; value: string }>;
        changed: Array<{ merged_ref: string; label: string; before: string; after: string }>;
      }
    >;
    totals: { added: number; removed: number; changed: number };
  }> =>
    http
      .get(
        `/harmonize/${encodeURIComponent(collectionId)}/snapshots/${encodeURIComponent(snapshotId)}/diff${
          against ? `?against=${encodeURIComponent(against)}` : ""
        }`,
      )
      .then((r) => r.data),
};
