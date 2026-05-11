import type {
  AggregationEnvironmentResponse,
  AggregationPreparedPreviewResponse,
  AggregationSourceCard,
  AggregationUploadedFile,
  CanonicalPatientSummary,
  HarmonizeCollection,
  HarmonizeRunStateResponse,
  PatientContextStatus,
  PatientListItem,
  PatientOverview,
  PublishedChartStateResponse,
  ResourceTypeCount,
} from "../types";

/*
 * Frontend mock data boundary
 *
 * We keep this file intentionally small and explicit so the design/build loop can
 * continue when FastAPI is not running. The API client may use these records only
 * for UI shell work; integration checks should still run against the real
 * Synthea-backed FastAPI endpoints before we commit or demo behavior that depends
 * on patient data.
 */
export const mockPatients: PatientListItem[] = [
  {
    id: "demo-high-risk",
    name: "Demo Patient - Surgical Review",
    age_years: 67,
    gender: "female",
    complexity_tier: "complex",
    complexity_score: 82,
    total_resources: 4812,
    encounter_count: 44,
    active_condition_count: 9,
    active_med_count: 11,
    workspace_type: "demo",
    source_count: 3,
    prepared_source_count: 1,
  },
  {
    id: "demo-trial-match",
    name: "Demo Patient - Trial Match",
    age_years: 54,
    gender: "male",
    complexity_tier: "moderate",
    complexity_score: 61,
    total_resources: 3180,
    encounter_count: 28,
    active_condition_count: 6,
    active_med_count: 7,
    workspace_type: "demo",
    source_count: 2,
    prepared_source_count: 0,
  },
  {
    id: "demo-med-access",
    name: "Demo Patient - Medication Access",
    age_years: 72,
    gender: "female",
    complexity_tier: "highly_complex",
    complexity_score: 91,
    total_resources: 5364,
    encounter_count: 51,
    active_condition_count: 12,
    active_med_count: 15,
    workspace_type: "demo",
    source_count: 4,
    prepared_source_count: 2,
  },
];

const mockPatientById = new Map(mockPatients.map((patient) => [patient.id, patient]));

const mockBundleContextByPatientId: Record<string, { label: string; updated_at: string }> = {
  "demo-high-risk": { label: "Blake EHI", updated_at: "2026-10-05" },
  "demo-trial-match": { label: "Atlas Trial Match", updated_at: "2026-09-18" },
  "demo-med-access": { label: "Medication Access Review", updated_at: "2026-10-02" },
};

function mockPatient(patientId: string): PatientListItem {
  return mockPatientById.get(patientId) ?? mockPatients[0];
}

function mockWorkspaceCollectionId(patientId: string): string {
  const safe = patientId
    .replace(/[^A-Za-z0-9_.-]+/g, "-")
    .replace(/^[.-]+|[.-]+$/g, "")
    .slice(0, 120) || "patient";
  return `upload-${safe}`;
}

function mockUploadedFiles(patientId: string): AggregationUploadedFile[] {
  const patient = mockPatient(patientId);
  const bundle = mockBundleContextByPatientId[patient.id] ?? {
    label: patient.name,
    updated_at: "2026-10-05",
  };

  return [
    {
      file_id: `${patient.id}-portal-export`,
      file_name: `${bundle.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-portal-export.json`,
      content_type: "application/json",
      size_bytes: 1_842_331,
      uploaded_at: `${bundle.updated_at}T09:24:00Z`,
      status: "uploaded",
      data_type: "FHIR JSON export",
      source_name: "Cedars patient portal",
      date_range: "2019-2026",
      contains: ["Medications", "Conditions or diagnoses", "Labs and observations"],
      description: "Primary portal export used as the prepared baseline for this selected data space.",
      context_notes: "Includes longitudinal history plus the pre-op packet handoff context.",
      extraction_confidence: "high",
      storage_path: `/demo/${patient.id}/portal-export.json`,
      parse_status: "structured",
      next_step: "Ready for harmonization",
      derived_artifacts: ["prepared-json", "resource-preview"],
    },
    {
      file_id: `${patient.id}-outside-consult`,
      file_name: "outside-consult-note.pdf",
      content_type: "application/pdf",
      size_bytes: 684_120,
      uploaded_at: `${bundle.updated_at}T10:02:00Z`,
      status: "needs_processing",
      data_type: "PDF report",
      source_name: "Outside specialty consult",
      date_range: "October 2026",
      contains: ["Visit notes or summaries", "Conditions or diagnoses"],
      description: "External consult letter staged for extraction and review.",
      context_notes: "Narrative-only attachment; not yet folded into canonical facts.",
      extraction_confidence: "medium",
      storage_path: `/demo/${patient.id}/outside-consult-note.pdf`,
      parse_status: "ready_to_extract",
      next_step: "Run PDF extraction",
      derived_artifacts: [],
    },
  ];
}

export function getMockOverview(patientId: string): PatientOverview {
  const patient = mockPatient(patientId);
  const resourceTypeCounts: ResourceTypeCount[] = [
    { resource_type: "Observation", count: Math.round(patient.total_resources * 0.32), category: "Clinical" },
    { resource_type: "Condition", count: Math.round(patient.total_resources * 0.14), category: "Clinical" },
    { resource_type: "MedicationRequest", count: Math.round(patient.total_resources * 0.1), category: "Clinical" },
    { resource_type: "Encounter", count: patient.encounter_count, category: "Clinical" },
    { resource_type: "Claim", count: Math.round(patient.total_resources * 0.08), category: "Billing" },
  ];

  return {
    id: patient.id,
    name: patient.name,
    age_years: patient.age_years,
    gender: patient.gender,
    birth_date: patient.id === "demo-trial-match" ? "1971-08-16" : "1958-02-03",
    is_deceased: false,
    race: patient.id === "demo-trial-match" ? "White" : "Asian",
    ethnicity: "Not Hispanic or Latino",
    city: "Los Angeles",
    state: "CA",
    language: "English",
    marital_status: "Married",
    daly: null,
    qaly: null,
    earliest_encounter_dt: "2016-04-12",
    latest_encounter_dt: "2026-04-28",
    years_of_history: 10,
    total_resources: patient.total_resources,
    clinical_resource_count: Math.round(patient.total_resources * 0.74),
    billing_resource_count: Math.round(patient.total_resources * 0.18),
    billing_pct: 18,
    resource_type_counts: resourceTypeCounts,
    complexity_score: patient.complexity_score,
    complexity_tier: patient.complexity_tier,
    active_condition_count: patient.active_condition_count,
    resolved_condition_count: Math.max(2, patient.active_condition_count - 3),
    conditions: [],
    active_med_count: patient.active_med_count,
    total_med_count: patient.active_med_count + 4,
    medications: [],
    unique_loinc_count: 23,
    obs_category_breakdown: {
      laboratory: 46,
      vital_signs: 18,
      survey: 7,
    },
    encounter_count: patient.encounter_count,
    encounter_class_breakdown: {
      ambulatory: Math.max(12, patient.encounter_count - 10),
      inpatient: 4,
      emergency: 2,
    },
    encounter_type_breakdown: [
      { encounter_type: "Office Visit", count: Math.max(10, patient.encounter_count - 12) },
      { encounter_type: "Inpatient", count: 4 },
      { encounter_type: "Emergency", count: 2 },
    ],
    avg_resources_per_encounter: Math.round(patient.total_resources / patient.encounter_count),
    care_team: [],
    sites_of_service: [],
    allergy_count: 3,
    allergy_labels: ["Penicillin", "Latex", "Shellfish"],
    immunization_count: 16,
    unique_vaccines: ["COVID-19", "Influenza", "Pneumococcal"],
    parse_warning_count: 0,
  };
}

export function getMockCanonicalSummary(patientId: string): CanonicalPatientSummary {
  const patient = mockPatient(patientId);
  const sourceCount = patient.source_count ?? 3;
  const preparedSourceCount = patient.prepared_source_count ?? 1;

  return {
    patient_id: patient.id,
    patient_name: patient.name,
    workspace_id: mockWorkspaceCollectionId(patient.id),
    source_count: sourceCount,
    prepared_source_count: preparedSourceCount,
    needs_preparation_count: Math.max(sourceCount - preparedSourceCount, 0),
    total_resources: Math.round(patient.total_resources * 0.66),
    canonical_observation_count: 78,
    canonical_condition_count: patient.active_condition_count + 4,
    canonical_medication_count: patient.active_med_count + 2,
    canonical_allergy_count: 3,
    canonical_immunization_count: 16,
    encounter_count: patient.encounter_count,
    review_item_count: preparedSourceCount < sourceCount ? 2 : 0,
    date_start: "2016-04-12",
    date_end: "2026-04-28",
    storage_mode: "frontend_mock",
    storage_description: "Frontend preview fixture while FastAPI aggregation endpoints are unavailable.",
    sources: [
      {
        id: "src_portal",
        label: "Portal export bundle",
        kind: "portal",
        status: "structured",
        status_label: "Structured",
        total_resources: 2140,
      },
      {
        id: "src_pdf",
        label: "Outside consult PDF",
        kind: "file_upload",
        status: "ready_to_extract",
        status_label: "Needs preparation",
        total_resources: 0,
      },
      {
        id: "src_lab",
        label: "Lab history CSV",
        kind: "lab",
        status: "stored",
        status_label: "Staged",
        total_resources: 0,
      },
    ].slice(0, sourceCount),
    fallback_modes: ["frontend_mock"],
  };
}

export function getMockAggregationSources(patientId: string): AggregationEnvironmentResponse {
  const patient = mockPatient(patientId);
  const uploadedFiles = mockUploadedFiles(patientId);
  const sourceCards: AggregationSourceCard[] = [
    {
      id: "synthea-fhir",
      name: "Synthea FHIR baseline bundle",
      category: "synthetic_fhir",
      mode: "available",
      status_label: "Available",
      record_count: patient.total_resources,
      last_updated: "2026-10-05T08:45:00Z",
      confidence: "high",
      posture: "Structured public demo dataset",
      next_action: "Open as the chart baseline.",
      help_title: "Prepared baseline bundle",
      help_body: "This source anchors the selected patient workspace and gives the chart a clear, inspectable baseline before additional uploads are merged.",
      evidence: ["Demographics", "Encounter history", "Medication timeline"],
    },
    {
      id: "portal-export",
      name: "Portal export bundle",
      category: "portal",
      mode: "available",
      status_label: "Ready to stage",
      record_count: 2140,
      last_updated: "2026-05-09T16:10:00Z",
      confidence: "high",
      posture: "Structured FHIR-aligned export",
      next_action: "Attach as the baseline chart source.",
      help_title: "Best starting point",
      help_body: "This prepared export anchors the workspace and gives downstream modules a stable baseline.",
      evidence: ["Demographics", "Medication list", "Encounter history"],
    },
    {
      id: "outside-pdf",
      name: "Outside consult PDF",
      category: "file_upload",
      mode: "uploaded",
      status_label: "Needs extraction",
      record_count: 1,
      last_updated: "2026-05-09T16:22:00Z",
      confidence: "medium",
      posture: "Unstructured clinical document",
      next_action: "Run extraction and review the prepared preview.",
      help_title: "Prepare document",
      help_body: "This page should remain usable in preview even before the backend extraction service is running.",
      evidence: ["Pre-op consult note"],
    },
    {
      id: "lab-csv",
      name: "Lab history CSV",
      category: "lab",
      mode: "uploaded",
      status_label: "Staged",
      record_count: 48,
      last_updated: "2026-05-08T09:02:00Z",
      confidence: "medium",
      posture: "Tabular import awaiting mapping",
      next_action: "Confirm date range and map the columns.",
      help_title: "Structured but not canonical",
      help_body: "CSV uploads can preview here before they are folded into the harmonized record.",
      evidence: ["CBC trend", "INR history"],
    },
  ];

  return {
    patient_id: patient.id,
    patient_label: patient.name,
    environment_label: "Prepared demo workspace",
    source_posture: "Frontend preview fixture for the Patient Record pipeline.",
    private_blake_cedars_available: false,
    synthetic_resource_counts: {
      Observation: 128,
      Condition: 24,
      MedicationRequest: 18,
      Encounter: patient.encounter_count,
      DocumentReference: 5,
    },
    uploaded_files: uploadedFiles,
    source_cards: sourceCards.slice(0, 4),
    guidance: [
      "Start with the portal export or another broad source before adding PDFs.",
      "Use Source Intake to stage uploads even when the backend is offline in preview mode.",
      "Harmonized Record should stay empty until a prepared source is available.",
    ],
  };
}

export function getMockPatientContextStatus(): PatientContextStatus {
  return {
    private_blake_cedars_available: false,
    storage: "frontend_mock",
  };
}

export function getMockAggregationUploadPreview(
  patientId: string,
  fileId: string,
): AggregationPreparedPreviewResponse {
  const patient = mockPatient(patientId);
  if (fileId.endsWith("portal-export")) {
    return {
      patient_id: patient.id,
      file_id: fileId,
      file_name: "portal-export.json",
      parse_status: "structured",
      output_type: "FHIR bundle",
      total_resources: 2140,
      resource_counts: {
        Observation: 812,
        Condition: 204,
        MedicationRequest: 166,
        Encounter: 74,
        DocumentReference: 23,
      },
      artifact_paths: ["/demo/prepared/portal-export.json"],
      date_start: "2019-01-11",
      date_end: "2026-10-05",
      json_preview: {
        resourceType: "Bundle",
        type: "collection",
        entry: [{ resource: { resourceType: "Patient", id: patient.id } }],
      },
      preview_items: [
        { resource_type: "Condition", label: "Atrial fibrillation", value: "active", date: "2023-06-14", status: "confirmed" },
        { resource_type: "MedicationRequest", label: "Apixaban 5 mg BID", value: "active", date: "2026-04-02", status: "active" },
        { resource_type: "Observation", label: "INR", value: "1.2", date: "2026-10-02", status: "final" },
      ],
      message: "Prepared portal export preview",
    };
  }

  return {
    patient_id: patient.id,
    file_id: fileId,
    file_name: "outside-consult-note.pdf",
    parse_status: "ready_to_extract",
    output_type: "pending_extraction",
    total_resources: 0,
    resource_counts: {},
    artifact_paths: [],
    date_start: "",
    date_end: "",
    json_preview: null,
    preview_items: [],
    message: "Run extraction to generate structured preview rows for this PDF.",
  };
}

export function getMockAggregationUploadJson(
  patientId: string,
  fileId: string,
): Record<string, unknown> {
  return getMockAggregationUploadPreview(patientId, fileId).json_preview ?? {
    resourceType: "Bundle",
    type: "collection",
    entry: [],
  };
}

export function getMockBundleContext(patientId: string): { label: string; updated_at: string } | null {
  return mockBundleContextByPatientId[patientId] ?? null;
}

export function getMockHarmonizeCollections(): { collections: HarmonizeCollection[] } {
  return { collections: [] };
}

export function getMockHarmonizeWorkspace(patientId: string): HarmonizeCollection {
  const patient = mockPatient(patientId);
  return {
    id: mockWorkspaceCollectionId(patient.id),
    name: `${patient.name} workspace`,
    description:
      "Prepared preview workspace without upload-backed harmonized sources yet. Add documents in Source Intake to create a patient-specific harmonized record.",
    source_count: 0,
  };
}

export function getMockLatestHarmonizationRun(collectionId: string): HarmonizeRunStateResponse {
  return {
    collection_id: collectionId,
    latest_run: null,
  };
}

export function getMockPublishedChart(collectionId: string): PublishedChartStateResponse {
  return {
    collection_id: collectionId,
    active_snapshot: null,
    snapshots: [],
  };
}
