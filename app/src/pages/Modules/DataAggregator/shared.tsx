import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Braces,
  CalendarDays,
  CheckCircle2,
  CircleHelp,
  Download,
  FolderOpen,
  FileSearch,
  FileText,
  FileUp,
  Loader2,
  Layers3,
  Pencil,
  Play,
  Plus,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { api } from "../../../api/client";
import type {
  AggregationEnvironmentResponse,
  AggregationCreateProfilePayload,
  AggregationPreparedPreviewResponse,
  AggregationSourceCard,
  AggregationUpdateProfilePayload,
  AggregationUploadedFile,
  AggregationUploadPayload,
  HarmonizeExtractJobResponse,
  HarmonizeRunResponse,
  PatientListItem,
  PatientOverview,
  PublishedChartStateResponse,
} from "../../../types";

type AggregatorPage = "workspaces" | "sources" | "publish";
type SourceSelection =
  | { type: "baseline"; id: "synthea-fhir" }
  | { type: "upload"; id: string };

const pageCopy: Record<AggregatorPage, { badge: string; title: string; body: string }> = {
  workspaces: {
    badge: "Workspace Library",
    title: "Manage patient workspaces",
    body:
      "Create named demo profiles, open existing workspaces, and remove upload-backed workspaces that should no longer feed downstream chart views.",
  },
  sources: {
    badge: "Source Intake",
    title: "Upload all of your health documents",
    body:
      "Add records from portals, PDFs, labs, pharmacies, wearables, insurance files, screenshots, and anything else that should feed the harmonized record.",
  },
  publish: {
    badge: "Publish Chart",
    title: "Activate the chart for downstream use",
    body:
      "Pin a reviewed harmonization run as the active chart snapshot for FHIR Charts, Clinical Insights, and future clinical workflows.",
  },
};

function HelpButton({ title, body }: { title: string; body: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#dfe4ea] bg-white text-[#667085] hover:border-[#5b76fe] hover:text-[#5b76fe]"
        aria-label={`Help: ${title}`}
      >
        <CircleHelp size={16} />
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-72 rounded-xl border border-[#dfe4ea] bg-white p-4 text-left shadow-lg">
          <p className="text-sm font-semibold text-[#1c1c1e]">{title}</p>
          <p className="mt-1 text-sm leading-6 text-[#667085]">{body}</p>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return (
    <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] px-3 py-2.5">
      <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">{label}</p>
      <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{value}</p>
      <p className="mt-0.5 text-xs leading-5 text-[#667085]">{detail}</p>
    </div>
  );
}

function CompactMetric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return (
    <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] px-3 py-2">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-[#667085]">{label}</p>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-lg font-semibold text-[#1c1c1e]">{value}</span>
        <span className="text-xs text-[#667085]">{detail}</span>
      </div>
    </div>
  );
}

function uploadErrorMessage(error: unknown): string | null {
  if (!error) return null;
  const maybe = error as {
    message?: string;
    response?: {
      status?: number;
      data?: { detail?: string } | string;
    };
  };
  const status = maybe.response?.status;
  if (status === 413) {
    return "This file is too large for the upload gateway. For this prototype, uploads should be 25 MB or smaller.";
  }
  const detail = maybe.response?.data;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object" && "detail" in detail && detail.detail) return detail.detail;
  if (maybe.message) return maybe.message;
  return "The file could not be saved. Please try again.";
}

function PdfPageProgressMap({ job }: { job: HarmonizeExtractJobResponse | null }) {
  const totalPages = job?.total_pages ?? null;
  const visiblePages = totalPages ? Math.min(totalPages, 8) : 4;
  const processedPages = job?.processed_pages ?? 0;
  const isRunning = job?.status === "pending" || job?.status === "running";

  return (
    <div className="rounded-lg border border-[#ead3b9] bg-white px-3 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">Page processing map</p>
        <p className="text-xs text-[#667085]">
          {totalPages ? `${processedPages}/${totalPages} pages complete` : "Counting pages when extraction starts"}
        </p>
      </div>
      <div className="mt-3 grid grid-cols-4 gap-2 sm:grid-cols-8">
        {Array.from({ length: visiblePages }).map((_, index) => {
          const pageNumber = index + 1;
          const isComplete = totalPages ? pageNumber <= processedPages : false;
          const isActive = isRunning && !isComplete && (totalPages ? pageNumber === processedPages + 1 : index === 0);
          return (
            <div
              key={pageNumber}
              className={`flex h-16 flex-col justify-between rounded-md border px-2 py-2 text-[11px] ${
                isComplete
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : isActive
                    ? "border-[#5b76fe] bg-[#f4f6ff] text-[#4157d8]"
                    : "border-[#eef0f4] bg-[#f7f9fc] text-[#667085]"
              }`}
            >
              <span className="font-semibold">{totalPages ? `Page ${pageNumber}` : ["Read", "Extract", "Map", "Validate"][index]}</span>
              <span className={isActive ? "h-1.5 rounded-full bg-[#5b76fe]" : "h-1.5 rounded-full bg-[#dfe4ea]"} />
            </div>
          );
        })}
      </div>
      {totalPages && totalPages > visiblePages && (
        <p className="mt-2 text-xs text-[#667085]">Showing the first {visiblePages} pages; remaining pages continue in the same server job.</p>
      )}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="rounded-2xl bg-white p-8 text-sm text-[#667085] shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      Loading aggregation workspace...
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-red-50 p-5 text-sm leading-6 text-red-700">
      {message}
    </div>
  );
}

const containsOptions = [
  "Labs and observations",
  "Visit notes or summaries",
  "Medications",
  "Conditions or diagnoses",
  "Imaging or procedures",
  "Device or wearable data",
  "Insurance or claims",
  "Not sure",
];

const emptyUploadForm = {
  data_type: "PDF report",
  source_name: "",
  date_range: "",
  contains: [] as string[],
  description: "",
  context_notes: "",
};

function bytesLabel(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

function parseStatusClass(status: AggregationUploadedFile["parse_status"]): string {
  if (status === "structured" || status === "extracted") return "bg-emerald-100 text-emerald-800";
  if (status === "ready_to_extract") return "bg-amber-100 text-amber-800";
  if (status === "unsupported") return "bg-red-50 text-red-700";
  return "bg-slate-100 text-slate-700";
}

function parseStatusLabel(status: AggregationUploadedFile["parse_status"]): string {
  if (status === "structured") return "FHIR ready";
  if (status === "ready_to_extract") return "Ready to extract";
  if (status === "extracted") return "PDF parsed";
  if (status === "unsupported") return "Unsupported";
  return "Stored only";
}

function safeUploadSessionId(value: string): string {
  return value.replace(/[^A-Za-z0-9_.-]+/g, "-").replace(/^[.-]+|[.-]+$/g, "").slice(0, 120) || "patient";
}

function workspaceCollectionId(patientId: string): string {
  return `workspace-${safeUploadSessionId(patientId)}`;
}

const sourceTypeExamples = [
  {
    title: "Portal exports",
    examples: "MyChart, hospital portals, specialist clinics, FHIR JSON, C-CDA documents",
    description: "Best for structured medications, conditions, encounters, allergies, immunizations, and labs.",
  },
  {
    title: "PDF documents",
    examples: "Discharge summaries, visit notes, lab packets, imaging reports, referral letters",
    description: "Best when you have a human-readable record that is not available as a structured export.",
  },
  {
    title: "Medication records",
    examples: "Pharmacy histories, medication lists, prior authorizations, insurance coverage letters",
    description: "Useful for checking what was prescribed, filled, stopped, denied, or difficult to access.",
  },
  {
    title: "Wearables and devices",
    examples: "Apple Health, Whoop, BP cuffs, glucose monitors, sleep and activity exports",
    description: "Used as patient-generated context and trends, not as verified chart facts.",
  },
];

function resourceCountEntries(preview: AggregationPreparedPreviewResponse): [string, number][] {
  return Object.entries(preview.resource_counts ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);
}

function dateLabel(value: string): string {
  if (!value) return "Not found";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return date.toLocaleDateString();
}

function exportJsonFile(fileName: string, data: Record<string, unknown>) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const safeName = fileName.replace(/[^A-Za-z0-9_.-]+/g, "-").replace(/^[.-]+|[.-]+$/g, "") || "prepared-output";
  link.href = url;
  link.download = `${safeName}.prepared.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function baselineResourceEntries(
  overview: PatientOverview | undefined,
  counts: Record<string, number> | null | undefined,
): [string, number][] {
  if (overview?.resource_type_counts.length) {
    return overview.resource_type_counts
      .map((item) => [item.resource_type, item.count] as [string, number])
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);
  }
  return Object.entries(counts ?? {})
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);
}

function baselineSampleRows(overview: PatientOverview | undefined): AggregationPreparedPreviewResponse["preview_items"] {
  if (!overview) return [];
  const conditions = overview.conditions.slice(0, 4).map((condition) => ({
    resource_type: "Condition",
    label: condition.display,
    value: condition.clinical_status,
    date: condition.onset_dt ?? "",
    status: condition.is_active ? "active" : "resolved",
  }));
  const medications = overview.medications.slice(0, 4).map((medication) => ({
    resource_type: "MedicationRequest",
    label: medication.display,
    value: "",
    date: medication.authored_on ?? "",
    status: medication.status,
  }));
  return [...conditions, ...medications].slice(0, 8);
}

function PreparedJsonModal({
  fileName,
  jsonData,
  isLoading,
  error,
  onClose,
}: {
  fileName: string;
  jsonData: Record<string, unknown> | null;
  isLoading: boolean;
  error: Error | null;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#101828]/35 px-4 py-8 backdrop-blur-[2px]">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="prepared-json-title"
        className="w-full max-w-5xl overflow-hidden rounded-xl border border-[#dfe4ea] bg-white shadow-2xl"
      >
        <header className="flex flex-col gap-3 border-b border-[#eef0f5] px-5 py-4 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Prepared output JSON</p>
            <h2 id="prepared-json-title" className="mt-1 truncate text-lg font-semibold text-[#1c1c1e]">
              {fileName}
            </h2>
            <p className="mt-1 text-sm leading-5 text-[#667085]">
              Full prepared JSON for this source. Use export if you want the complete structure outside the workspace.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={() => jsonData && exportJsonFile(fileName, jsonData)}
              disabled={!jsonData}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#5b76fe] px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Download size={15} />
              Export JSON
            </button>
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#dfe4ea] text-[#667085] hover:border-[#5b76fe] hover:text-[#5b76fe]"
              aria-label="Close JSON preview"
            >
              <X size={16} />
            </button>
          </div>
        </header>
        <div className="bg-[#101828]">
          {isLoading ? (
            <div className="flex min-h-[320px] items-center justify-center text-sm text-white/70">
              Loading full JSON...
            </div>
          ) : error ? (
            <div className="m-4 rounded-lg bg-red-50 p-4 text-sm text-red-700">
              Could not load prepared JSON: {error.message}
            </div>
          ) : (
            <pre className="max-h-[70vh] overflow-auto p-4 text-xs leading-5 text-[#f8faff]">
              {JSON.stringify(jsonData ?? {}, null, 2)}
            </pre>
          )}
        </div>
      </section>
    </div>
  );
}

function PreparedPreviewPane({
  patientId,
  baselineSource,
  baselineCounts,
  selectedSource,
  file,
  extractInProgress,
  extractJob,
  extractStatus,
  extractStartedAt,
  extractCompletedAt,
  extractError,
  onRunExtraction,
}: {
  patientId: string;
  baselineSource: AggregationSourceCard | null;
  baselineCounts: Record<string, number> | null | undefined;
  selectedSource: SourceSelection | null;
  file: AggregationUploadedFile | null;
  extractInProgress: boolean;
  extractJob: HarmonizeExtractJobResponse | null;
  extractStatus: string | null;
  extractStartedAt: string | null;
  extractCompletedAt: string | null;
  extractError: string | null;
  onRunExtraction: () => void;
}) {
  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const selectedIsBaseline = selectedSource?.type === "baseline";
  const previewQuery = useQuery({
    queryKey: ["aggregation-upload-preview", patientId, file?.file_id],
    queryFn: () => api.getAggregationUploadPreview(patientId, file!.file_id),
    enabled: Boolean(patientId && file && !selectedIsBaseline),
  });
  const overviewQuery = useQuery({
    queryKey: ["overview", patientId, "source-intake-preview"],
    queryFn: () => api.getOverview(patientId),
    enabled: Boolean(patientId && selectedIsBaseline && baselineSource),
  });
  const rawFhirQuery = useQuery({
    queryKey: ["raw-fhir", patientId, "source-intake-preview"],
    queryFn: () => api.getRawFhir(patientId),
    enabled: Boolean(jsonModalOpen && selectedIsBaseline && patientId),
  });
  const overview = overviewQuery.data;
  const preview = previewQuery.data ?? null;
  const resourceEntries = selectedIsBaseline
    ? baselineResourceEntries(overview, baselineCounts)
    : preview
      ? resourceCountEntries(preview)
      : [];
  const needsPdfExtraction = file?.parse_status === "ready_to_extract";
  const hasPreparedOutput = selectedIsBaseline
    ? Boolean(baselineSource?.record_count)
    : Boolean(preview && preview.total_resources > 0);
  const canRunPdfExtraction = needsPdfExtraction && !extractInProgress;
  const extractionStatusLabel = extractInProgress
    ? extractStatus === "pending"
      ? "Queued"
      : "Processing"
    : extractStatus === "complete"
      ? "Complete"
      : extractStatus === "failed"
        ? "Failed"
        : "Not started";
  const extractionProgress = extractJob?.progress_percent ?? (extractInProgress ? 10 : 0);
  const extractionEstimateDetail = extractJob?.total_pages
    ? `${extractJob.total_pages} page${extractJob.total_pages === 1 ? "" : "s"} detected`
    : "often 30-90s/page";
  const extractionStage = extractJob?.stage ?? (extractInProgress ? "Starting processor" : "Waiting to start");
  const preparedJsonQuery = useQuery({
    queryKey: ["aggregation-upload-json", patientId, file?.file_id],
    queryFn: () => api.getAggregationUploadJson(patientId, file!.file_id),
    enabled: Boolean(jsonModalOpen && patientId && file && hasPreparedOutput && !selectedIsBaseline),
  });

  useEffect(() => {
    setJsonModalOpen(false);
  }, [file?.file_id, selectedSource?.type]);

  const baselineRows = baselineSampleRows(overview);
  const safeBaselineCounts = baselineCounts ?? {};
  const baselineTotal = baselineSource?.record_count ?? Object.values(safeBaselineCounts).reduce((sum, count) => sum + count, 0);

  return (
    <>
    <section className="rounded-lg border border-[#dfe4ea] bg-white">
      <div className="flex flex-col gap-3 border-b border-[#eef0f5] px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Data Parsing</p>
          <h3 className="mt-1 truncate text-base font-semibold text-[#1c1c1e]">
            {selectedIsBaseline ? "Synthea FHIR patient bundle" : file?.file_name ?? "Select a source"}
          </h3>
        </div>
        <div className="flex flex-col gap-2 lg:items-end">
          <p className="max-w-2xl text-sm leading-5 text-[#667085]">
            {selectedSource
              ? "Preview how the selected source was converted into structured data before it feeds the harmonized record."
              : "Choose a source above to inspect parsed output."}
          </p>
          {((selectedIsBaseline && baselineSource) || preview?.json_preview) && (
            <button
              type="button"
              onClick={() => setJsonModalOpen(true)}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-sm font-semibold text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe]"
            >
              <Braces size={15} />
              View JSON
            </button>
          )}
        </div>
      </div>

      {!selectedSource ? (
        <div className="p-4 text-sm text-[#667085]">
          No source selected.
        </div>
      ) : selectedIsBaseline ? (
        <div className="space-y-4 p-4">
          {overviewQuery.isLoading ? (
            <div className="p-2 text-sm text-[#667085]">Loading baseline FHIR preview...</div>
          ) : !baselineSource ? (
            <div className="p-2 text-sm text-red-700">Could not load baseline source.</div>
          ) : (
            <div className="grid gap-3 lg:grid-cols-[360px_1fr]">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">
                    FHIR ready
                  </span>
                  <span className="rounded-full bg-[#f0f3fa] px-2.5 py-1 text-xs font-semibold text-[#667085]">
                    Baseline Synthea Bundle
                  </span>
                </div>
                <p className="text-sm leading-6 text-[#667085]">
                  This is the selected patient's structured Synthea FHIR record. It acts as the baseline chart source; uploaded PDFs and exports are added on top.
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <MetricCard label="Resources" value={baselineTotal} detail="FHIR records" />
                  <MetricCard label="Artifacts" value={1} detail="Patient bundle" />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] px-3 py-2.5">
                    <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#667085]">
                      <CalendarDays size={13} />
                      Start
                    </div>
                    <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">{dateLabel(overview?.earliest_encounter_dt ?? "")}</p>
                  </div>
                  <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] px-3 py-2.5">
                    <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#667085]">
                      <CalendarDays size={13} />
                      End
                    </div>
                    <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">{dateLabel(overview?.latest_encounter_dt ?? "")}</p>
                  </div>
                </div>
              </div>
              <div>
                <div className="rounded-lg border border-[#dfe4ea]">
                  <div className="border-b border-[#eef0f4] px-3 py-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Resource type breakdown</p>
                  </div>
                  <div className="divide-y divide-[#eef0f4]">
                    {resourceEntries.map(([resourceType, count]) => {
                      const percent = baselineTotal ? Math.round((count / baselineTotal) * 100) : 0;
                      return (
                        <div key={resourceType} className="grid grid-cols-[160px_1fr_52px] items-center gap-3 px-3 py-2">
                          <p className="truncate text-sm font-semibold text-[#1c1c1e]">{resourceType}</p>
                          <div className="h-2 overflow-hidden rounded-full bg-[#eef0f5]">
                            <div className="h-full rounded-full bg-[#5b76fe]" style={{ width: `${Math.max(percent, 4)}%` }} />
                          </div>
                          <p className="text-right text-sm font-semibold text-[#555a6a]">{count}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
                <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-[#667085]">Sample baseline rows</p>
                <div className="mt-2 max-h-[360px] divide-y divide-[#eef0f4] overflow-y-auto rounded-lg border border-[#dfe4ea]">
                  {baselineRows.length ? baselineRows.map((item, index) => (
                    <div key={`${item.resource_type}-${item.label}-${index}`} className="p-3">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-semibold leading-5 text-[#1c1c1e]">{item.label}</p>
                        <span className="shrink-0 rounded-full bg-[#f5f6f8] px-2 py-0.5 text-[11px] font-semibold text-[#667085]">
                          {item.resource_type}
                        </span>
                      </div>
                      {(item.value || item.date || item.status) && (
                        <p className="mt-1 text-xs leading-5 text-[#667085]">
                          {[item.value, item.date ? item.date.slice(0, 10) : "", item.status].filter(Boolean).join(" · ")}
                        </p>
                      )}
                    </div>
                  )) : (
                    <p className="p-3 text-sm text-[#667085]">No sample rows available for this bundle.</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      ) : previewQuery.isLoading ? (
        <div className="p-4 text-sm text-[#667085]">Loading prepared output…</div>
      ) : !preview ? (
        <div className="p-4 text-sm text-red-700">Could not load preview.</div>
      ) : (
        <div className="space-y-4 p-4">
          {needsPdfExtraction && (
            <div className="rounded-lg border border-[#f0d7bf] bg-[#fff8f1] p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">PDF processor</p>
                  <h4 className="mt-1 text-base font-semibold text-[#1c1c1e]">Extract candidate FHIR resources from this PDF</h4>
                  <p className="mt-1 max-w-3xl text-sm leading-6 text-[#667085]">
                    This runs the local multipass PDF extraction pipeline, writes a cached extracted bundle next to the source file, and then refreshes this preview.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={onRunExtraction}
                  disabled={!canRunPdfExtraction}
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#5b76fe] px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {extractInProgress ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                  {extractInProgress ? "Running processor" : "Run PDF processor"}
                </button>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-4">
                <CompactMetric label="Status" value={extractionStatusLabel} detail={extractInProgress ? "active job" : "processor"} />
                <CompactMetric label="Estimate" value="Page-based" detail={extractionEstimateDetail} />
                <CompactMetric label="Started" value={extractStartedAt ? dateLabel(extractStartedAt) : "Not yet"} detail="job time" />
                <CompactMetric label="Finished" value={extractCompletedAt ? dateLabel(extractCompletedAt) : "Pending"} detail="job time" />
              </div>
              {(extractInProgress || extractJob) && (
                <div className="mt-3 space-y-3">
                  <div className="rounded-lg border border-[#ead3b9] bg-white px-3 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-[#1c1c1e]">{extractionStage}</p>
                        <p className="mt-1 text-xs leading-5 text-[#667085]">
                          {extractJob?.detail ?? "Runs on the server, so you can leave this page and come back later."}
                        </p>
                      </div>
                      <p className="text-sm font-semibold text-[#5b76fe]">{extractionProgress}%</p>
                    </div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#eef0f5]">
                      <div
                        className="h-full rounded-full bg-[#5b76fe] transition-all duration-500"
                        style={{ width: `${Math.max(5, Math.min(100, extractionProgress))}%` }}
                      />
                    </div>
                  </div>
                  <PdfPageProgressMap job={extractJob} />
                </div>
              )}
              {extractError && (
                <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                  Extraction failed: {extractError}
                </p>
              )}
            </div>
          )}

          {!hasPreparedOutput && needsPdfExtraction ? (
            <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] px-4 py-3">
              <p className="text-sm font-semibold text-[#1c1c1e]">No prepared output yet</p>
              <p className="mt-1 text-sm leading-6 text-[#667085]">
                Run the PDF processor to generate candidate FHIR resources, resource counts, extracted dates, sample rows, and the JSON preview.
              </p>
            </div>
          ) : (
          <div className="grid gap-3 lg:grid-cols-[360px_1fr]">
            <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${parseStatusClass(preview.parse_status)}`}>
                {parseStatusLabel(preview.parse_status)}
              </span>
              <span className="rounded-full bg-[#f0f3fa] px-2.5 py-1 text-xs font-semibold text-[#667085]">
                {preview.output_type}
              </span>
            </div>

            <p className="text-sm leading-6 text-[#667085]">{preview.message}</p>

            <div className="grid grid-cols-2 gap-2">
              <MetricCard
                label="Resources"
                value={preview.total_resources}
                detail="Prepared records"
              />
              <MetricCard
                label="Artifacts"
                value={preview.artifact_paths.length}
                detail="Derived files"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] px-3 py-2.5">
                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <CalendarDays size={13} />
                  Start
                </div>
                <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">{dateLabel(preview.date_start)}</p>
              </div>
              <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] px-3 py-2.5">
                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <CalendarDays size={13} />
                  End
                </div>
                <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">{dateLabel(preview.date_end)}</p>
              </div>
            </div>
          </div>

          <div>
            <div className="rounded-lg border border-[#dfe4ea]">
              <div className="border-b border-[#eef0f4] px-3 py-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Resource type breakdown</p>
              </div>
              {resourceEntries.length > 0 ? (
                <div className="divide-y divide-[#eef0f4]">
                  {resourceEntries.map(([resourceType, count]) => {
                    const percent = preview.total_resources ? Math.round((count / preview.total_resources) * 100) : 0;
                    return (
                      <div key={resourceType} className="grid grid-cols-[140px_1fr_52px] items-center gap-3 px-3 py-2">
                        <p className="truncate text-sm font-semibold text-[#1c1c1e]">{resourceType}</p>
                        <div className="h-2 overflow-hidden rounded-full bg-[#eef0f5]">
                          <div className="h-full rounded-full bg-[#5b76fe]" style={{ width: `${Math.max(percent, 4)}%` }} />
                        </div>
                        <p className="text-right text-sm font-semibold text-[#555a6a]">{count}</p>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="px-3 py-2 text-sm text-[#667085]">No resource types found yet.</p>
              )}
            </div>

            <p className="mt-4 text-xs font-semibold uppercase tracking-wider text-[#667085]">Sample prepared rows</p>
            {preview.preview_items.length === 0 ? (
              <p className="mt-2 rounded-lg bg-[#f7f9fc] p-3 text-sm text-[#667085]">
                This source has not produced structured preview rows yet.
              </p>
            ) : (
              <div className="mt-2 max-h-[360px] divide-y divide-[#eef0f4] overflow-y-auto rounded-lg border border-[#dfe4ea]">
                {preview.preview_items.map((item, index) => (
                  <div key={`${item.resource_type}-${item.label}-${index}`} className="p-3">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-semibold leading-5 text-[#1c1c1e]">{item.label}</p>
                      <span className="shrink-0 rounded-full bg-[#f5f6f8] px-2 py-0.5 text-[11px] font-semibold text-[#667085]">
                        {item.resource_type}
                      </span>
                    </div>
                    {(item.value || item.date || item.status) && (
                      <p className="mt-1 text-xs leading-5 text-[#667085]">
                        {[item.value, item.date ? item.date.slice(0, 10) : "", item.status]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          </div>
          )}

        </div>
      )}
    </section>
    {jsonModalOpen && selectedIsBaseline && baselineSource && (
      <PreparedJsonModal
        fileName={`${baselineSource.name}.json`}
        jsonData={rawFhirQuery.data ?? null}
        isLoading={rawFhirQuery.isLoading}
        error={rawFhirQuery.error as Error | null}
        onClose={() => setJsonModalOpen(false)}
      />
    )}
    {jsonModalOpen && !selectedIsBaseline && preview?.json_preview && file && (
      <PreparedJsonModal
        fileName={file.file_name}
        jsonData={preparedJsonQuery.data ?? preview.json_preview}
        isLoading={preparedJsonQuery.isLoading}
        error={preparedJsonQuery.error as Error | null}
        onClose={() => setJsonModalOpen(false)}
      />
    )}
    </>
  );
}

function UploadDetailModal({
  file,
  form,
  patientLabel,
  isPending,
  errorMessage,
  onClose,
  onFileChange,
  onFormChange,
  onToggleContains,
  onSubmit,
}: {
  file: File | null;
  form: Omit<AggregationUploadPayload, "file">;
  patientLabel: string;
  isPending: boolean;
  errorMessage: string | null;
  onClose: () => void;
  onFileChange: (file: File | null) => void;
  onFormChange: (next: Omit<AggregationUploadPayload, "file">) => void;
  onToggleContains: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const modalInputRef = useRef<HTMLInputElement | null>(null);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#101828]/35 px-4 py-8 backdrop-blur-[2px]">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-5xl overflow-hidden rounded-xl border border-[#dfe4ea] bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-detail-title"
      >
        <header className="flex flex-col gap-3 border-b border-[#eef0f5] px-5 py-4 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Add data source</p>
            <h2 id="upload-detail-title" className="mt-1 text-lg font-semibold text-[#1c1c1e]">
              Tell us what this file contains
            </h2>
            <p className="mt-1 text-sm leading-5 text-[#667085]">
              This source will be staged directly inside {patientLabel}'s Source Intake workspace.
            </p>
            <p className="mt-2 rounded-lg border border-[#f0d7bf] bg-[#fff8f1] px-3 py-2 text-xs leading-5 text-[#8a5a24]">
              Demo storage: uploaded files are stored on this application server for the prototype. Use synthetic or
              test records unless you intentionally want to test this hosted demo environment.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#dfe4ea] text-[#667085] hover:border-[#5b76fe] hover:text-[#5b76fe]"
            aria-label="Close add data source"
          >
            <X size={16} />
          </button>
        </header>

        <div className="grid max-h-[calc(100vh-210px)] gap-4 overflow-y-auto p-5 lg:grid-cols-[1fr_320px]">
          <section>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="text-sm font-semibold text-[#1c1c1e]">
                Data type
                <select value={form.data_type} onChange={(event) => onFormChange({ ...form, data_type: event.target.value })} className="mt-2 w-full rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm">
                  <option>PDF report</option>
                  <option>FHIR JSON export</option>
                  <option>C-CDA / XML document</option>
                  <option>Lab or diagnostic report</option>
                  <option>Medication / pharmacy record</option>
                  <option>Wearable or device export</option>
                  <option>Insurance / payer document</option>
                  <option>Image or screenshot</option>
                  <option>Not sure</option>
                </select>
              </label>
              <label className="text-sm font-semibold text-[#1c1c1e]">
                Source or organization
                <input value={form.source_name} onChange={(event) => onFormChange({ ...form, source_name: event.target.value })} placeholder="Cedars-Sinai, Function Health, Apple Health" className="mt-2 w-full rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm" />
              </label>
              <label className="text-sm font-semibold text-[#1c1c1e]">
                Date range, if known
                <input value={form.date_range} onChange={(event) => onFormChange({ ...form, date_range: event.target.value })} placeholder="2024-2026, April 2026, not sure" className="mt-2 w-full rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm" />
              </label>
              <div>
                <p className="text-sm font-semibold text-[#1c1c1e]">Contains</p>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {containsOptions.map((option) => (
                    <label key={option} className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${form.contains.includes(option) ? "border-[#5b76fe] bg-[#eef1ff] text-[#5b76fe]" : "border-[#e9eaef] text-[#555a6a]"}`}>
                      <input type="checkbox" checked={form.contains.includes(option)} onChange={() => onToggleContains(option)} />
                      {option}
                    </label>
                  ))}
                </div>
              </div>
              <label className="md:col-span-2 text-sm font-semibold text-[#1c1c1e]">
                Description and context
                <textarea value={form.description} onChange={(event) => onFormChange({ ...form, description: event.target.value })} placeholder="What is this file, and what should your care team understand about it?" className="mt-2 min-h-[92px] w-full resize-y rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm" />
              </label>
              <label className="md:col-span-2 text-sm font-semibold text-[#1c1c1e]">
                Anything we should know before processing?
                <textarea value={form.context_notes} onChange={(event) => onFormChange({ ...form, context_notes: event.target.value })} placeholder="Examples: self-ordered labs, supplements at the time, unsure if every page belongs to me." className="mt-2 min-h-[76px] w-full resize-y rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm" />
                <span className="mt-1 block text-xs font-normal text-[#8d92a3]">This becomes document-specific Patient Context, not verified chart truth.</span>
              </label>
            </div>
          </section>

          <aside className="space-y-4">
            <div className="rounded-lg border border-[#dfe4ea] bg-[#f8faff] p-4">
              <div className="flex items-start gap-4 rounded-xl border border-[#dfe4ff] bg-[#fafbff] p-4">
                <div className="flex h-20 w-16 shrink-0 items-center justify-center rounded-lg bg-white text-sm font-bold text-[#5b76fe] shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                  FILE
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-[#1c1c1e]">{file?.name || "No file selected"}</p>
                  <p className="mt-1 text-sm text-[#667085]">{file ? `${bytesLabel(file.size)} · ${file.type || "unknown type"}` : "Choose a file to continue."}</p>
                </div>
              </div>
              <input
                ref={modalInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.json,.ndjson,.xml,.csv,.txt,.jpg,.jpeg,.png,.heic,application/pdf,application/json,text/csv,text/xml"
                onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
              />
              <button type="button" onClick={() => modalInputRef.current?.click()} className="mt-4 w-full rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm font-semibold text-[#555a6a]">
                {file ? "Choose different file" : "Choose file"}
              </button>
            </div>

            <div className="rounded-lg border border-[#f0d7bf] bg-[#fff8f1] p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">Why this matters</p>
              <p className="mt-2 text-sm leading-6 text-[#667085]">
                The platform can store a file immediately, but it needs patient-provided context to understand the type of data, source, and likely extraction confidence.
              </p>
            </div>
          </aside>
        </div>
        <footer className="flex flex-col-reverse gap-2 border-t border-[#eef0f5] bg-[#f8faff] px-5 py-4 sm:flex-row sm:justify-end">
          {errorMessage && (
            <p className="mr-auto rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
              {errorMessage}
            </p>
          )}
          <button type="button" onClick={onClose} className="rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-sm font-semibold text-[#555a6a]">
            Cancel
          </button>
          <button type="submit" disabled={!file || isPending} className="rounded-lg bg-[#5b76fe] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            {isPending ? "Saving..." : "Save to source intake"}
          </button>
        </footer>
      </form>
    </div>
  );
}

function SourceInventoryPage({
  patientId,
  sources,
  refreshAll,
}: {
  patientId: string;
  sources: AggregationEnvironmentResponse;
  refreshAll: () => void;
}) {
  const queryClient = useQueryClient();
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [sourceTypesOpen, setSourceTypesOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedSource, setSelectedSource] = useState<SourceSelection | null>(null);
  const [activeExtractJobId, setActiveExtractJobId] = useState<string | null>(null);
  const lastFinalizedExtractJobRef = useRef<string | null>(null);
  const pendingUploadedSelectionRef = useRef<string | null>(null);
  const [uploadForm, setUploadForm] = useState<Omit<AggregationUploadPayload, "file">>(emptyUploadForm);
  const collectionId = `upload-${safeUploadSessionId(patientId)}`;
  const baselineSource =
    sources.source_cards.find((source) => source.id === "synthea-fhir" && source.mode === "available") ?? null;
  const uploadMutation = useMutation({
    mutationFn: (payload: AggregationUploadPayload) => api.uploadAggregationFile(patientId, payload),
    onSuccess: (response) => {
      setUploadModalOpen(false);
      setSelectedFile(null);
      setUploadForm(emptyUploadForm);
      pendingUploadedSelectionRef.current = response.file.file_id;
      setSelectedSource({ type: "upload", id: response.file.file_id });
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      refreshAll();
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (fileId: string) => api.deleteAggregationFile(patientId, fileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      refreshAll();
    },
  });
  const extractMutation = useMutation({
    mutationFn: () => api.extractHarmonizeCollection(collectionId),
    onSuccess: (job) => {
      setActiveExtractJobId(job.job_id);
      queryClient.invalidateQueries({ queryKey: ["source-intake-extract-job", collectionId, "latest"] });
      refreshAll();
    },
  });
  const extractJobQuery = useQuery({
    queryKey: ["source-intake-extract-job", activeExtractJobId],
    queryFn: () => api.getHarmonizeExtractJob(activeExtractJobId!),
    enabled: Boolean(activeExtractJobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "running" ? 1500 : false;
    },
  });

  const structuredFiles = sources.uploaded_files.filter((file) => file.parse_status === "structured").length;
  const pendingExtraction = sources.uploaded_files.filter((file) => file.parse_status === "ready_to_extract").length;
  const extractedFiles = sources.uploaded_files.filter((file) => file.parse_status === "extracted").length;
  const needsContext = sources.uploaded_files.filter((file) => !file.description || !file.contains.length).length;
  const sourceCount = sources.uploaded_files.length + (baselineSource ? 1 : 0);
  const preparedFiles = structuredFiles + extractedFiles + (baselineSource ? 1 : 0);
  const latestExtractJobQuery = useQuery({
    queryKey: ["source-intake-extract-job", collectionId, "latest"],
    queryFn: () => api.getLatestHarmonizeExtractJob(collectionId),
    enabled: pendingExtraction > 0 || Boolean(activeExtractJobId),
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "running" ? 1500 : false;
    },
  });
  const activeSelection =
    selectedSource ??
    (baselineSource
      ? ({ type: "baseline", id: "synthea-fhir" } as const)
      : sources.uploaded_files[0]
        ? ({ type: "upload", id: sources.uploaded_files[0].file_id } as const)
        : null);
  const activeUpload =
    activeSelection?.type === "upload"
      ? sources.uploaded_files.find((file) => file.file_id === activeSelection.id) ?? null
      : null;
  const activeBaselineSource =
    activeSelection?.type === "baseline" ? baselineSource : null;
  const selectedPreviewFile =
    activeSelection?.type === "upload"
      ? activeUpload
      : null;
  const extractJob = extractJobQuery.data ?? latestExtractJobQuery.data ?? null;
  const extractInProgress =
    extractMutation.isPending ||
    extractJob?.status === "pending" ||
    extractJob?.status === "running";

  useEffect(() => {
    const pendingUploadId = pendingUploadedSelectionRef.current;
    if (pendingUploadId) {
      if (sources.uploaded_files.some((file) => file.file_id === pendingUploadId)) {
        setSelectedSource({ type: "upload", id: pendingUploadId });
        pendingUploadedSelectionRef.current = null;
      }
      return;
    }
    if (selectedSource?.type === "baseline" && baselineSource) return;
    if (selectedSource?.type === "upload" && sources.uploaded_files.some((file) => file.file_id === selectedSource.id)) return;
    if (baselineSource) {
      setSelectedSource({ type: "baseline", id: "synthea-fhir" });
      return;
    }
    if (sources.uploaded_files[0]) {
      setSelectedSource({ type: "upload", id: sources.uploaded_files[0].file_id });
      return;
    }
    setSelectedSource(null);
  }, [baselineSource, selectedSource, sources.uploaded_files]);

  useEffect(() => {
    if (!extractJob || (extractJob.status !== "complete" && extractJob.status !== "failed")) return;
    if (lastFinalizedExtractJobRef.current === extractJob.job_id) return;
    lastFinalizedExtractJobRef.current = extractJob.job_id;
    refreshAll();
    queryClient.invalidateQueries({ queryKey: ["aggregation-upload-preview", patientId] });
    queryClient.invalidateQueries({ queryKey: ["source-intake-extract-job", collectionId, "latest"] });
  }, [collectionId, extractJob, patientId, queryClient, refreshAll]);

  function openUpload(file?: File | null) {
    uploadMutation.reset();
    setSelectedFile(file ?? null);
    setUploadForm(emptyUploadForm);
    setUploadModalOpen(true);
  }

  function toggleContains(value: string) {
    setUploadForm((current) => ({
      ...current,
      contains: current.contains.includes(value)
        ? current.contains.filter((item) => item !== value)
        : [...current.contains, value],
    }));
  }

  function submitUpload(event: FormEvent) {
    event.preventDefault();
    if (!selectedFile) return;
    uploadMutation.reset();
    uploadMutation.mutate({ file: selectedFile, ...uploadForm });
  }

  function deleteFile(file: AggregationUploadedFile) {
    if (!window.confirm(`Remove ${file.file_name} from the local aggregation workspace? This deletes the staged local copy and metadata.`)) return;
    deleteMutation.mutate(file.file_id);
  }

  return (
    <div className="space-y-5">
      {uploadModalOpen && (
        <UploadDetailModal
          file={selectedFile}
          form={uploadForm}
          patientLabel={sources.patient_label}
          isPending={uploadMutation.isPending}
          errorMessage={uploadErrorMessage(uploadMutation.error)}
          onClose={() => setUploadModalOpen(false)}
          onFileChange={setSelectedFile}
          onFormChange={setUploadForm}
          onToggleContains={toggleContains}
          onSubmit={submitUpload}
        />
      )}

      {sourceTypesOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 p-4">
          <div className="mx-auto mt-12 max-w-4xl rounded-2xl bg-white shadow-xl">
            <div className="flex items-start justify-between gap-4 border-b border-[#eef0f5] p-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Types of records</p>
                <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">Examples of files and sources you can add</h2>
              </div>
              <button type="button" onClick={() => setSourceTypesOpen(false)} className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#dfe4ea] text-[#667085]">
                <X size={16} />
              </button>
            </div>
            <div className="grid gap-3 p-5 md:grid-cols-2">
              {sourceTypeExamples.map((item) => (
                <div key={item.title} className="rounded-xl border border-[#e9eaef] p-4">
                  <p className="text-sm font-semibold text-[#1c1c1e]">{item.title}</p>
                  <p className="mt-1 text-sm leading-6 text-[#667085]">{item.description}</p>
                  <p className="mt-3 text-xs font-semibold uppercase tracking-wider text-[#8d92a3]">Examples</p>
                  <p className="mt-1 text-sm leading-5 text-[#555a6a]">{item.examples}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <section className="rounded-lg border border-[#dfe4ea] bg-white px-4 py-2.5">
        <div className="grid gap-3 lg:grid-cols-[minmax(180px,1fr)_minmax(0,620px)] lg:items-center">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Sources</p>
            <h2 className="truncate text-base font-semibold text-[#1c1c1e]">{sources.patient_label}</h2>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <CompactMetric label="Sources" value={sourceCount} detail={`${sources.uploaded_files.length} staged`} />
            <CompactMetric label="Prepared" value={`${preparedFiles}/${sourceCount}`} detail={`${pendingExtraction} need prep`} />
            <CompactMetric label="Needs context" value={needsContext} detail="missing" />
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div className="overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#eef0f5] px-4 py-3">
            <div className="flex items-center gap-2">
              <FileText size={18} className="text-[#5b76fe]" />
              <h2 className="text-base font-semibold text-[#1c1c1e]">Source files</h2>
            </div>
            <button type="button" onClick={() => openUpload()} className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#5b76fe] px-3 py-2 text-sm font-semibold text-white">
              <FileUp size={15} />
              Add file
            </button>
          </div>
          {sourceCount ? (
            <div className="divide-y divide-[#eef0f4]">
              {baselineSource && (
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedSource({ type: "baseline", id: "synthea-fhir" })}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedSource({ type: "baseline", id: "synthea-fhir" });
                    }
                  }}
                  className={`grid w-full gap-3 px-4 py-3 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#5b76fe] lg:grid-cols-[minmax(0,1fr)_210px_180px_96px] lg:items-center ${
                    activeSelection?.type === "baseline" ? "bg-[#eef2ff]" : "hover:bg-[#f7f9fc]"
                  }`}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[#1c1c1e]">Synthea FHIR patient bundle</p>
                    <p className="mt-1 text-xs text-[#8d92a3]">
                      {baselineSource.record_count.toLocaleString()} resources · selected patient baseline
                    </p>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[#555a6a]">FHIR JSON export</p>
                    <p className="mt-1 truncate text-xs text-[#8d92a3]">Synthea public demo data</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">
                      FHIR ready
                    </span>
                    <span className="rounded-full bg-[#eef1ff] px-2.5 py-1 text-xs font-semibold text-[#5b76fe]">
                      baseline
                    </span>
                  </div>
                  <Link
                    to={`/charts?patient=${patientId}`}
                    onClick={(event) => event.stopPropagation()}
                    className="inline-flex items-center justify-center gap-1 rounded-lg border border-[#dfe4ea] px-2.5 py-1.5 text-xs font-semibold text-[#667085] hover:border-[#5b76fe] hover:text-[#5b76fe]"
                  >
                    Open chart
                  </Link>
                </div>
              )}
              {sources.uploaded_files.map((file) => {
                const isSelected = activeSelection?.type === "upload" && activeSelection.id === file.file_id;
                return (
                  <div
                    key={file.file_id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedSource({ type: "upload", id: file.file_id })}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedSource({ type: "upload", id: file.file_id });
                      }
                    }}
                    className={`grid w-full gap-3 px-4 py-3 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#5b76fe] lg:grid-cols-[minmax(0,1fr)_210px_180px_96px] lg:items-center ${
                      isSelected ? "bg-[#eef2ff]" : "hover:bg-[#f7f9fc]"
                    }`}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-[#1c1c1e]">{file.file_name}</p>
                      <p className="mt-1 text-xs text-[#8d92a3]">
                        {bytesLabel(file.size_bytes)} · {file.content_type} · {new Date(file.uploaded_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[#555a6a]">{file.data_type}</p>
                      {file.source_name && <p className="mt-1 truncate text-xs text-[#8d92a3]">{file.source_name}</p>}
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${parseStatusClass(file.parse_status)}`}>
                        {parseStatusLabel(file.parse_status)}
                      </span>
                      {file.parse_status === "ready_to_extract" && (
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedSource({ type: "upload", id: file.file_id });
                            extractMutation.mutate();
                          }}
                          disabled={extractInProgress}
                          className="inline-flex items-center gap-1 rounded-full border border-[#f0d7bf] bg-white px-2.5 py-1 text-xs font-semibold text-[#9a5a16] hover:bg-[#fff8f1] disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {extractInProgress ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
                          Extract PDF
                        </button>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        deleteFile(file);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          event.stopPropagation();
                          deleteFile(file);
                        }
                      }}
                      className="inline-flex items-center justify-center gap-1 rounded-lg border border-[#dfe4ea] px-2.5 py-1.5 text-xs font-semibold text-[#667085] hover:border-red-200 hover:bg-red-50 hover:text-red-700"
                    >
                      <Trash2 size={13} />
                      Remove
                    </button>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-6 text-center">
              <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
                <FileUp size={22} />
              </div>
              <h3 className="mt-3 text-base font-semibold text-[#1c1c1e]">No uploaded files yet</h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#667085]">
                Add PDFs, portal exports, lab reports, CSVs, screenshots, or device files.
              </p>
            </div>
          )}
        </div>
        <PreparedPreviewPane
          patientId={patientId}
          baselineSource={activeBaselineSource}
          baselineCounts={sources.synthetic_resource_counts}
          selectedSource={activeSelection}
          file={selectedPreviewFile}
          extractInProgress={extractInProgress}
          extractJob={extractJob}
          extractStatus={extractJob?.status ?? null}
          extractStartedAt={extractJob?.started_at ?? null}
          extractCompletedAt={extractJob?.completed_at ?? null}
          extractError={extractJob?.error ?? (extractMutation.error ? (extractMutation.error as Error).message : null)}
          onRunExtraction={() => extractMutation.mutate()}
        />
      </section>

      <section className="rounded-lg border border-[#f0d7bf] bg-[#fff8f1] p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">Not sure what to upload?</p>
            <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">See examples of records and source data</h2>
            <p className="mt-1 text-sm leading-6 text-[#667085]">
              Common sources include portal exports, PDFs, lab reports, medication lists, insurance files, and wearable data.
            </p>
          </div>
          <button type="button" onClick={() => setSourceTypesOpen(true)} className="rounded-lg border border-[#f0d7bf] bg-white px-4 py-2 text-sm font-semibold text-[#9a5a16]">
            View examples
          </button>
        </div>
      </section>
    </div>
  );
}

function ReadinessPage({
  sources,
  patientId,
  collectionId,
  latestRun,
  publishedState,
  publishError,
  activateError,
  unpublishError,
  isPublishing,
  activatingSnapshotId,
  isUnpublishing,
  onPublish,
  onActivateSnapshot,
  onUnpublish,
  onDeleteWorkspace,
  isDeleting,
}: {
  sources: AggregationEnvironmentResponse;
  patientId: string;
  collectionId: string;
  latestRun: HarmonizeRunResponse | null;
  publishedState: PublishedChartStateResponse | null;
  publishError: string | null;
  activateError: string | null;
  unpublishError: string | null;
  isPublishing: boolean;
  activatingSnapshotId: string | null;
  isUnpublishing: boolean;
  onPublish: () => void;
  onActivateSnapshot: (snapshotId: string) => void;
  onUnpublish: () => void;
  onDeleteWorkspace: () => void;
  isDeleting: boolean;
}) {
  const uploadedCount = sources.uploaded_files.length;
  const preparedCount = sources.uploaded_files.filter((file) => file.parse_status === "structured" || file.parse_status === "extracted").length;
  const needsPreparationCount = sources.uploaded_files.filter((file) => file.parse_status === "ready_to_extract").length;
  const needsContextCount = sources.uploaded_files.filter((file) => !file.description || !file.contains.length).length;
  const canDeleteWorkspace = patientId.startsWith("workspace-");
  const activeSnapshot = publishedState?.active_snapshot ?? null;
  const snapshots = publishedState?.snapshots ?? [];
  const latestRunIsActive = activeSnapshot?.run_id === latestRun?.run_id;
  const canPublishLatest =
    !!latestRun &&
    latestRun.status === "complete" &&
    latestRun.summary.publishable &&
    !latestRunIsActive;
  const publishBlocker = !latestRun
    ? "Run harmonization before publishing a chart snapshot."
    : latestRun.status !== "complete"
      ? "The latest harmonization run did not complete."
      : latestRun.summary.review_item_count > 0
        ? "Resolve review items in Harmonized Record before publishing."
        : latestRun.summary.total_candidate_facts <= 0
          ? "The latest run has no candidate facts to publish."
          : latestRunIsActive
            ? "The latest run is already the active chart snapshot."
            : "";

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-[#dfe4ea] bg-white p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Workspace</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">{sources.patient_label}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#667085]">
              Publishing pins one harmonization run as the active chart snapshot.
              Downstream modules should read from that active snapshot instead
              of raw uploads or transient previews.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to={`/aggregate/sources?patient=${patientId}`} className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-sm font-semibold text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe]">
              <FileUp size={15} />
              Add sources
            </Link>
            <Link to={`/aggregate/harmonize?patient=${patientId}`} className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-sm font-semibold text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe]">
              <Play size={15} />
              Harmonized Record
            </Link>
            <Link to={`/charts?patient=${patientId}`} className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#5b76fe] px-3 py-2 text-sm font-semibold text-white">
              <Layers3 size={15} />
              Open FHIR Charts
            </Link>
            {canDeleteWorkspace && (
              <button
                type="button"
                onClick={onDeleteWorkspace}
                disabled={isDeleting}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Trash2 size={15} />
                {isDeleting ? "Deleting..." : "Delete workspace"}
              </button>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard label="Active snapshot" value={activeSnapshot ? "Published" : "None"} detail={activeSnapshot ? `Run ${activeSnapshot.run_id.slice(0, 8)}` : "No chart is active."} />
        <MetricCard label="Latest run" value={latestRun ? "Complete" : "Not run"} detail={latestRun ? `${latestRun.summary.total_candidate_facts} candidate facts.` : "Run harmonization first."} />
        <MetricCard label="Review items" value={latestRun?.summary.review_item_count ?? "—"} detail="Must be resolved before publish." />
        <MetricCard label="Sources" value={uploadedCount} detail="Uploaded files in this workspace." />
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_0.8fr]">
        <div className="overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
          <div className="border-b border-[#eef0f5] px-4 py-3">
            <h2 className="text-base font-semibold text-[#1c1c1e]">Snapshot history</h2>
            <p className="mt-1 text-sm text-[#667085]">
              Published snapshots stay available so you can roll downstream
              modules back to a prior chart state.
            </p>
          </div>
          {snapshots.length ? (
            <div className="divide-y divide-[#eef0f4]">
              {snapshots.map((snapshot) => (
                <div key={snapshot.snapshot_id} className="grid gap-3 px-4 py-3 md:grid-cols-[minmax(0,1fr)_170px_150px] md:items-center">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-semibold text-[#1c1c1e]">
                        Snapshot {snapshot.snapshot_id.slice(0, 8)}
                      </p>
                      {snapshot.is_active && (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                          Active
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-[#8d92a3]">
                      Published {dateLabel(snapshot.published_at)} · run {snapshot.run_id.slice(0, 8)} · {snapshot.rule_version}
                    </p>
                  </div>
                  <p className="text-sm text-[#555a6a]">
                    {snapshot.candidate_fact_count} facts · {snapshot.source_count} sources
                  </p>
                  <button
                    type="button"
                    disabled={snapshot.is_active || activatingSnapshotId === snapshot.snapshot_id}
                    onClick={() => onActivateSnapshot(snapshot.snapshot_id)}
                    className="inline-flex w-fit items-center justify-center rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-xs font-semibold text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {activatingSnapshotId === snapshot.snapshot_id ? "Activating..." : snapshot.is_active ? "Active" : "Activate"}
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-5 text-sm text-[#667085]">
              No chart snapshots have been published yet. Run harmonization,
              resolve review items, then publish the latest run.
            </div>
          )}
        </div>

        <div className="rounded-lg border border-[#dfe4ea] bg-white p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-[#1c1c1e]">Publish latest run</h2>
              <p className="mt-1 text-sm leading-6 text-[#667085]">
                Publishing does not modify source files. It activates the latest
                completed run as the chart state downstream screens should use.
              </p>
            </div>
            <HelpButton
              title="What publish means now"
              body="Publish pins a harmonization run as the active chart snapshot. Prior snapshots remain available for rollback and audit."
            />
          </div>

          <div className="mt-4 rounded-lg border border-[#eef0f4] bg-[#fafbff] p-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Latest harmonization run</p>
            {latestRun ? (
              <div className="mt-2 grid gap-2 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-[#667085]">Run ID</span>
                  <span className="font-mono text-xs text-[#1c1c1e]">{latestRun.run_id}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-[#667085]">Completed</span>
                  <span className="font-semibold text-[#1c1c1e]">{dateLabel(latestRun.completed_at)}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-[#667085]">Candidate facts</span>
                  <span className="font-semibold text-[#1c1c1e]">{latestRun.summary.total_candidate_facts}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-[#667085]">Review items</span>
                  <span className="font-semibold text-[#1c1c1e]">{latestRun.summary.review_item_count}</span>
                </div>
              </div>
            ) : (
              <p className="mt-2 text-sm leading-6 text-[#667085]">
                No harmonization run exists for collection <span className="font-mono">{collectionId}</span>.
              </p>
            )}
          </div>

          <button
            type="button"
            disabled={!canPublishLatest || isPublishing}
            onClick={onPublish}
            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#5b76fe] px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-[#dfe4ea] disabled:text-[#667085]"
          >
            <ShieldCheck size={15} />
            {isPublishing ? "Publishing..." : activeSnapshot ? "Publish newer run" : "Publish canonical record"}
          </button>
          {publishBlocker && (
            <p className="mt-2 text-sm leading-6 text-[#667085]">{publishBlocker}</p>
          )}
          {(publishError || activateError || unpublishError) && (
            <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {publishError || activateError || unpublishError}
            </p>
          )}

          {activeSnapshot && (
            <button
              type="button"
              disabled={isUnpublishing}
              onClick={onUnpublish}
              className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-[#dfe4ea] bg-white px-4 py-2 text-sm font-semibold text-[#555a6a] hover:border-red-200 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isUnpublishing ? "Removing access..." : "Unpublish active snapshot"}
            </button>
          )}

          <div className="mt-4 space-y-2">
            {[
              ["1", "Source Intake", `${preparedCount}/${uploadedCount} uploaded files prepared; ${needsPreparationCount} need parsing.`],
              ["2", "Harmonized Record", latestRun ? `${latestRun.summary.total_candidate_facts} candidate facts in latest run.` : "Run harmonization before publish."],
              ["3", "Review", latestRun ? `${latestRun.summary.review_item_count} open review items.` : "No run to review yet."],
              ["4", "Publish Chart", activeSnapshot ? "An active snapshot is available to downstream modules." : "No active chart snapshot yet."],
            ].map(([step, title, body]) => (
              <div key={step} className="flex gap-3 rounded-lg border border-[#eef0f4] bg-[#fafbff] p-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#eef1ff] text-xs font-semibold text-[#5b76fe]">{step}</span>
                <div>
                  <p className="text-sm font-semibold text-[#1c1c1e]">{title}</p>
                  <p className="mt-0.5 text-sm leading-5 text-[#667085]">{body}</p>
                </div>
              </div>
            ))}
          </div>
          <Link to={`/aggregate/context?patient=${patientId}`} className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-[#0f766e]">
            Review Patient Context
            <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_0.8fr]">
        <div className="overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
          <div className="border-b border-[#eef0f5] px-4 py-3">
            <h2 className="text-base font-semibold text-[#1c1c1e]">Source history</h2>
            <p className="mt-1 text-sm text-[#667085]">Files saved to this workspace.</p>
          </div>
          {sources.uploaded_files.length ? (
            <div className="divide-y divide-[#eef0f4]">
              {sources.uploaded_files.map((file) => (
                <div key={file.file_id} className="grid gap-3 px-4 py-3 md:grid-cols-[minmax(0,1fr)_180px_150px] md:items-center">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[#1c1c1e]">{file.file_name}</p>
                    <p className="mt-1 text-xs text-[#8d92a3]">
                      {bytesLabel(file.size_bytes)} · {file.source_name || "No source named"} · {dateLabel(file.uploaded_at)}
                    </p>
                  </div>
                  <p className="text-sm text-[#555a6a]">{file.data_type}</p>
                  <span className={`w-fit rounded-full px-2.5 py-1 text-xs font-semibold ${parseStatusClass(file.parse_status)}`}>
                    {parseStatusLabel(file.parse_status)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-5 text-sm text-[#667085]">No files have been added yet. Start in Source Intake.</div>
          )}
        </div>
        <div className="rounded-lg border border-[#dfe4ea] bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Workspace controls</p>
          <h2 className="mt-1 text-base font-semibold text-[#1c1c1e]">Access and cleanup</h2>
          <p className="mt-2 text-sm leading-6 text-[#667085]">
            Publishing controls downstream chart access. Deleting the workspace
            removes the source files and published snapshot state for this demo
            workspace.
          </p>
          <MetricCard label="Context gaps" value={needsContextCount} detail="Sources missing description or tags." />
        </div>
      </section>
    </div>
  );
}

type WorkspaceDraft = {
  id?: string;
  display_name: string;
  notes: string;
};

function workspaceKindLabel(workspace: PatientListItem): string {
  if (workspace.workspace_type === "synthea") return "Synthea demo patient";
  if (workspace.workspace_type === "demo") return "Demo profile";
  if (workspace.workspace_type === "upload") return "Uploaded workspace";
  return "Patient workspace";
}

function workspaceState(workspace: PatientListItem): { label: string; className: string; detail: string } {
  const sourceCount = workspace.source_count ?? 0;
  const preparedCount = workspace.prepared_source_count ?? 0;
  if (workspace.workspace_type === "synthea") {
    return {
      label: "Seed ready",
      className: "bg-emerald-100 text-emerald-800",
      detail: `${workspace.total_resources.toLocaleString()} seed resources`,
    };
  }
  if (sourceCount === 0) {
    return {
      label: "Empty",
      className: "bg-slate-100 text-slate-700",
      detail: "No source files yet",
    };
  }
  if (preparedCount >= sourceCount) {
    return {
      label: "Ready",
      className: "bg-emerald-100 text-emerald-800",
      detail: `${preparedCount}/${sourceCount} prepared`,
    };
  }
  return {
    label: "Needs prep",
    className: "bg-amber-100 text-amber-800",
    detail: `${preparedCount}/${sourceCount} prepared`,
  };
}

function canManageWorkspace(workspace: PatientListItem): boolean {
  return workspace.workspace_type === "profile" || workspace.workspace_type === "upload" || workspace.id.startsWith("workspace-");
}

function WorkspaceEditorModal({
  draft,
  isSaving,
  error,
  onChange,
  onClose,
  onSubmit,
}: {
  draft: WorkspaceDraft;
  isSaving: boolean;
  error: string | null;
  onChange: (draft: WorkspaceDraft) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  const isEditing = Boolean(draft.id);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#111827]/40 px-4 py-6">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
        className="w-full max-w-xl overflow-hidden rounded-xl border border-[#dfe4ea] bg-white shadow-xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[#eef0f4] px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">{isEditing ? "Rename workspace" : "New workspace"}</p>
            <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">
              {isEditing ? "Update this patient workspace" : "Create a named patient workspace"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[#dfe4ea] text-[#667085] hover:border-[#5b76fe] hover:text-[#5b76fe]"
            aria-label="Close workspace editor"
          >
            <X size={16} />
          </button>
        </div>
        <div className="space-y-4 px-5 py-4">
          <label className="block">
            <span className="text-sm font-semibold text-[#1c1c1e]">Workspace name</span>
            <input
              value={draft.display_name}
              onChange={(event) => onChange({ ...draft, display_name: event.target.value })}
              placeholder="Blake demo upload, Max review packet, Cedars export test"
              className="mt-1 w-full rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm outline-none focus:border-[#5b76fe]"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-[#1c1c1e]">Notes</span>
            <textarea
              value={draft.notes}
              onChange={(event) => onChange({ ...draft, notes: event.target.value })}
              rows={4}
              placeholder="What is this workspace for, and what should we remember about the uploaded records?"
              className="mt-1 w-full rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm outline-none focus:border-[#5b76fe]"
            />
          </label>
          <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] p-3 text-sm leading-6 text-[#667085]">
            Workspaces are saved in server-local demo storage. Source Intake, Harmonized Record, FHIR Charts, and Clinical Insights all use this selected workspace id.
          </div>
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        </div>
        <div className="flex justify-end gap-2 border-t border-[#eef0f4] bg-[#fafbff] px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#dfe4ea] bg-white px-4 py-2 text-sm font-semibold text-[#555a6a]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSaving || !draft.display_name.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-[#5b76fe] px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSaving && <Loader2 size={15} className="animate-spin" />}
            {isEditing ? "Save changes" : "Create workspace"}
          </button>
        </div>
      </form>
    </div>
  );
}

function WorkspaceLibrary({
  patients,
  currentPatientId,
}: {
  patients: PatientListItem[];
  currentPatientId: string;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<WorkspaceDraft | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const workspaces = useMemo(() => {
    const uploadBacked = patients.filter((patient) => patient.workspace_type === "profile" || patient.workspace_type === "upload");
    const seedPatients = patients.filter((patient) => patient.workspace_type === "synthea" || patient.workspace_type === "demo");
    return [...uploadBacked, ...seedPatients];
  }, [patients]);

  const createMutation = useMutation({
    mutationFn: (payload: AggregationCreateProfilePayload) => api.createAggregationProfile(payload),
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ["patients"] });
      setDraft(null);
      setActionError(null);
      navigate(`/aggregate/sources?patient=${response.profile.id}`);
    },
    onError: (error) => setActionError(uploadErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: AggregationUpdateProfilePayload }) => api.updateAggregationProfile(id, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["patients"] });
      setDraft(null);
      setActionError(null);
    },
    onError: (error) => setActionError(uploadErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteAggregationProfile(id),
    onMutate: (id) => {
      setDeletingId(id);
      setActionError(null);
    },
    onSuccess: async (_response, id) => {
      await queryClient.invalidateQueries({ queryKey: ["patients"] });
      setDeletingId(null);
      if (currentPatientId === id) {
        navigate("/aggregate/workspaces", { replace: true });
      }
    },
    onError: (error) => {
      setDeletingId(null);
      setActionError(uploadErrorMessage(error));
    },
  });

  const openCreate = () => {
    setActionError(null);
    createMutation.reset();
    updateMutation.reset();
    setDraft({ display_name: "", notes: "" });
  };

  const openEdit = (workspace: PatientListItem) => {
    setActionError(null);
    createMutation.reset();
    updateMutation.reset();
    setDraft({ id: workspace.id, display_name: workspace.name, notes: "" });
  };

  const submitDraft = () => {
    if (!draft || !draft.display_name.trim()) return;
    const payload = { display_name: draft.display_name.trim(), notes: draft.notes.trim() };
    if (draft.id) {
      updateMutation.mutate({ id: draft.id, payload });
      return;
    }
    createMutation.mutate(payload);
  };

  const requestDelete = (workspace: PatientListItem) => {
    if (!canManageWorkspace(workspace)) return;
    const confirmed = window.confirm(`Delete "${workspace.name}" and all uploaded source files in this workspace?`);
    if (!confirmed) return;
    deleteMutation.mutate(workspace.id);
  };

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-[#dfe4ea] bg-white p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Workspace Library</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">Patient workspaces</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#667085]">
              Use this page to create named upload workspaces, choose what you are working on, and remove demo workspaces when they are no longer useful.
            </p>
          </div>
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#5b76fe] px-4 py-2 text-sm font-semibold text-white"
          >
            <Plus size={16} />
            New workspace
          </button>
        </div>
      </section>

      {actionError && <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{actionError}</div>}

      <section className="overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
        <div className="flex items-center gap-2 border-b border-[#eef0f4] px-4 py-3">
          <FolderOpen size={18} className="text-[#5b76fe]" />
          <h2 className="text-base font-semibold text-[#1c1c1e]">Available workspaces</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="bg-[#f7f9fc] text-xs font-semibold uppercase tracking-wider text-[#667085]">
              <tr>
                <th className="px-4 py-3">Workspace</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Sources</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#eef0f4]">
              {workspaces.map((workspace) => {
                const state = workspaceState(workspace);
                const isCurrent = workspace.id === currentPatientId;
                const manageable = canManageWorkspace(workspace);
                return (
                  <tr key={workspace.id} className={isCurrent ? "bg-[#f7f8ff]" : "hover:bg-[#fafbff]"}>
                    <td className="px-4 py-4 align-top">
                      <div className="flex items-start gap-2">
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-[#1c1c1e]">{workspace.name}</p>
                          <p className="mt-1 font-mono text-xs text-[#8d92a3]">{workspace.id}</p>
                        </div>
                        {isCurrent && <span className="rounded-full bg-[#eef1ff] px-2 py-0.5 text-xs font-semibold text-[#5b76fe]">Current</span>}
                      </div>
                    </td>
                    <td className="px-4 py-4 align-top text-[#555a6a]">{workspaceKindLabel(workspace)}</td>
                    <td className="px-4 py-4 align-top">
                      <p className="font-semibold text-[#1c1c1e]">
                        {workspace.workspace_type === "synthea" ? "Seed bundle" : `${workspace.source_count ?? 0} uploaded`}
                      </p>
                      <p className="mt-1 text-xs text-[#667085]">{state.detail}</p>
                    </td>
                    <td className="px-4 py-4 align-top">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${state.className}`}>{state.label}</span>
                    </td>
                    <td className="px-4 py-4 align-top">
                      <div className="flex justify-end gap-2">
                        <Link
                          to={`/aggregate/sources?patient=${workspace.id}`}
                          className="inline-flex items-center gap-1 rounded-lg bg-[#5b76fe] px-3 py-2 text-xs font-semibold text-white"
                        >
                          Open
                          <ArrowRight size={13} />
                        </Link>
                        {manageable && (
                          <button
                            type="button"
                            onClick={() => openEdit(workspace)}
                            className="inline-flex items-center gap-1 rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-xs font-semibold text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe]"
                          >
                            <Pencil size={13} />
                            Rename
                          </button>
                        )}
                        {manageable && (
                          <button
                            type="button"
                            onClick={() => requestDelete(workspace)}
                            disabled={deletingId === workspace.id}
                            className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {deletingId === workspace.id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] p-4">
        <h2 className="text-base font-semibold text-[#1c1c1e]">How this connects downstream</h2>
        <p className="mt-2 text-sm leading-6 text-[#667085]">
          A workspace is the durable container. Source Intake adds records to it, Data Parsing prepares the records, Harmonized Record resolves the canonical layer, and FHIR Charts reads that selected workspace.
        </p>
      </section>

      {draft && (
        <WorkspaceEditorModal
          draft={draft}
          isSaving={createMutation.isPending || updateMutation.isPending}
          error={actionError}
          onChange={setDraft}
          onClose={() => {
            setDraft(null);
            setActionError(null);
          }}
          onSubmit={submitDraft}
        />
      )}
    </div>
  );
}

function useSelectedAggregationPatient() {
  const [params, setParams] = useSearchParams();
  const patientFromUrl = params.get("patient");
  const patientsQuery = useQuery({
    queryKey: ["patients"],
    queryFn: api.listPatients,
  });
  const patientId = patientFromUrl || patientsQuery.data?.[0]?.id || "";

  useEffect(() => {
    if (patientFromUrl || !patientsQuery.data?.[0]?.id) return;
    const next = new URLSearchParams(params);
    next.set("patient", patientsQuery.data[0].id);
    setParams(next, { replace: true });
  }, [params, patientFromUrl, patientsQuery.data, setParams]);

  return { patientId, patientsQuery };
}

function AggregatorPageShell({
  page,
  guidance = [],
  isLoading,
  hasError,
  children,
}: {
  page: AggregatorPage;
  guidance?: string[];
  isLoading: boolean;
  hasError: boolean;
  children: React.ReactNode;
}) {
  const copy = pageCopy[page];

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-lg border border-[#dfe4ea] bg-white px-5 py-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              {page === "workspaces" && <FolderOpen size={13} />}
              {page === "sources" && <FileSearch size={13} />}
              {page === "publish" && <ShieldCheck size={13} />}
              {copy.badge}
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-[#1c1c1e]">{copy.title}</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-[#667085]">{copy.body}</p>
          </div>
          {page === "workspaces" ? (
            <div className="min-w-[260px] rounded-lg border border-[#dfe4ea] bg-[#f7f8ff] p-3">
              <div className="flex items-center gap-2">
                <FolderOpen size={18} className="text-[#5b76fe]" />
                <p className="text-sm font-semibold text-[#1c1c1e]">Workspace first</p>
              </div>
              <p className="mt-2 text-sm leading-6 text-[#667085]">
                Pick or create the patient container before adding sources, parsing PDFs, and opening downstream charts.
              </p>
            </div>
          ) : page === "sources" ? (
            <div className="min-w-[260px] rounded-lg border border-[#dfe4ea] bg-[#f7f8ff] p-3">
              <div className="flex items-center gap-2">
                <FileUp size={18} className="text-[#5b76fe]" />
                <p className="text-sm font-semibold text-[#1c1c1e]">What you can add</p>
              </div>
              <p className="mt-2 text-sm leading-6 text-[#667085]">
                Portal exports, PDFs, lab reports, medication lists, insurance files, images, CSVs, and device data.
              </p>
            </div>
          ) : (
            <div className="min-w-[260px] rounded-lg border border-[#dfe4ea] bg-[#f7f8ff] p-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={18} className="text-[#5b76fe]" />
                <p className="text-sm font-semibold text-[#1c1c1e]">Active snapshot</p>
              </div>
              <p className="mt-2 text-sm leading-6 text-[#667085]">
                Choose which harmonization run should feed downstream chart
                surfaces and keep prior snapshots available.
              </p>
            </div>
          )}
        </div>
      </section>

      {guidance.length > 0 && (
        <section className="rounded-2xl bg-[#f7f8ff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="grid gap-3 lg:grid-cols-3">
            {guidance.slice(0, 3).map((item) => (
              <div key={item} className="flex gap-3 rounded-xl bg-white p-3">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-[#5b76fe]" />
                <p className="text-sm leading-6 text-[#667085]">{item}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {isLoading && <LoadingState />}
      {hasError && <ErrorState message="Could not load aggregation workflow data. Confirm FastAPI is running and try again." />}
      {!isLoading && !hasError && children}
    </main>
  );
}

export function WorkspaceLibraryPage() {
  const { patientId, patientsQuery } = useSelectedAggregationPatient();
  return (
    <AggregatorPageShell
      page="workspaces"
      isLoading={patientsQuery.isLoading}
      hasError={patientsQuery.isError}
    >
      <WorkspaceLibrary patients={patientsQuery.data ?? []} currentPatientId={patientId} />
    </AggregatorPageShell>
  );
}

export function SourceIntakePage() {
  const { patientId, patientsQuery } = useSelectedAggregationPatient();
  const sourcesQuery = useQuery({
    queryKey: ["aggregation-sources", patientId],
    queryFn: () => api.getAggregationSources(patientId),
    enabled: Boolean(patientId),
  });

  const refreshAll = () => {
    sourcesQuery.refetch();
  };

  return (
    <AggregatorPageShell
      page="sources"
      isLoading={patientsQuery.isLoading || !patientId || sourcesQuery.isLoading}
      hasError={patientsQuery.isError || sourcesQuery.isError}
    >
      {sourcesQuery.data && (
        <SourceInventoryPage patientId={patientId} sources={sourcesQuery.data} refreshAll={refreshAll} />
      )}
    </AggregatorPageShell>
  );
}

export function PublishReadinessPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { patientId, patientsQuery } = useSelectedAggregationPatient();
  const collectionId = patientId ? workspaceCollectionId(patientId) : "";
  const sourcesQuery = useQuery({
    queryKey: ["aggregation-sources", patientId],
    queryFn: () => api.getAggregationSources(patientId),
    enabled: Boolean(patientId),
  });
  const latestRunQuery = useQuery({
    queryKey: ["harmonize-run-latest", collectionId],
    queryFn: () => api.getLatestHarmonizationRun(collectionId),
    enabled: Boolean(collectionId),
  });
  const publishedQuery = useQuery({
    queryKey: ["published-chart", collectionId],
    queryFn: () => api.getPublishedChart(collectionId),
    enabled: Boolean(collectionId),
  });

  const deleteProfileMutation = useMutation({
    mutationFn: () => api.deleteAggregationProfile(patientId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["patients"] });
      navigate("/aggregate/sources", { replace: true });
    },
  });
  const publishMutation = useMutation({
    mutationFn: () => {
      const runId = latestRunQuery.data?.latest_run?.run_id;
      if (!runId) throw new Error("Run harmonization before publishing.");
      return api.publishHarmonizationRun(collectionId, runId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["published-chart", collectionId] });
    },
  });
  const activateMutation = useMutation({
    mutationFn: (snapshotId: string) => api.activatePublishedSnapshot(collectionId, snapshotId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["published-chart", collectionId] });
    },
  });
  const unpublishMutation = useMutation({
    mutationFn: () => api.unpublishActiveChart(collectionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["published-chart", collectionId] });
    },
  });

  const guidance = [
    "Publish only after harmonization has run and review items are resolved.",
    "The active snapshot controls what downstream modules should trust.",
    "Prior snapshots remain available for rollback and audit.",
  ];

  return (
    <AggregatorPageShell
      page="publish"
      guidance={guidance}
      isLoading={patientsQuery.isLoading || !patientId || sourcesQuery.isLoading || latestRunQuery.isLoading || publishedQuery.isLoading}
      hasError={patientsQuery.isError || sourcesQuery.isError || latestRunQuery.isError || publishedQuery.isError}
    >
      {sourcesQuery.data && (
        <ReadinessPage
          sources={sourcesQuery.data}
          patientId={patientId}
          collectionId={collectionId}
          latestRun={latestRunQuery.data?.latest_run ?? null}
          publishedState={publishedQuery.data ?? null}
          publishError={uploadErrorMessage(publishMutation.error)}
          activateError={uploadErrorMessage(activateMutation.error)}
          unpublishError={uploadErrorMessage(unpublishMutation.error)}
          isPublishing={publishMutation.isPending}
          activatingSnapshotId={activateMutation.variables ?? null}
          isUnpublishing={unpublishMutation.isPending}
          onPublish={() => publishMutation.mutate()}
          onActivateSnapshot={(snapshotId) => activateMutation.mutate(snapshotId)}
          onUnpublish={() => {
            if (!window.confirm("Remove the active published chart snapshot? Snapshot history will remain available.")) return;
            unpublishMutation.mutate();
          }}
          isDeleting={deleteProfileMutation.isPending}
          onDeleteWorkspace={() => {
            if (!window.confirm(`Delete ${sourcesQuery.data?.patient_label ?? "this workspace"} and all staged uploads? This cannot be undone.`)) return;
            deleteProfileMutation.mutate();
          }}
        />
      )}
    </AggregatorPageShell>
  );
}

export function DataAggregator() {
  return <SourceIntakePage />;
}
