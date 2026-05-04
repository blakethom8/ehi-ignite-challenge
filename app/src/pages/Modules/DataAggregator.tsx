import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Braces,
  CalendarDays,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Download,
  FileSearch,
  FileText,
  FileUp,
  Gauge,
  Loader2,
  Layers3,
  MessageSquareText,
  Play,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react";
import { api } from "../../api/client";
import type {
  AggregationEnvironmentResponse,
  AggregationPreparedPreviewResponse,
  AggregationReadinessItem,
  AggregationReadinessResponse,
  AggregationSourceCard,
  AggregationUploadedFile,
  AggregationUploadPayload,
  PatientOverview,
} from "../../types";

type AggregatorPage = "sources" | "cleaning" | "publish";
type SourceSelection =
  | { type: "baseline"; id: "synthea-fhir" }
  | { type: "upload"; id: string };

const pageCopy: Record<AggregatorPage, { badge: string; title: string; body: string }> = {
  sources: {
    badge: "Source Intake",
    title: "Upload all of your health documents",
    body:
      "Add records from portals, PDFs, labs, pharmacies, wearables, insurance files, screenshots, and anything else that should feed the harmonized record.",
  },
  cleaning: {
    badge: "Cleaning Queue",
    title: "Review uploaded datasets and transformation status",
    body:
      "See each uploaded or connected dataset, how it is being processed, and how confidently it can be mapped into the platform's clinical data model.",
  },
  publish: {
    badge: "Publish Readiness",
    title: "Decide whether the patient packet is ready for downstream use",
    body:
      "Show what can be trusted today, what needs review, and what belongs in the portable chart packet before Clinical Insights or marketplace workflows consume it.",
  },
};

function readinessClass(status: AggregationReadinessItem["status"]): string {
  if (status === "ready") return "bg-emerald-100 text-emerald-800";
  if (status === "missing") return "bg-red-50 text-red-700";
  if (status === "needs_review") return "bg-amber-100 text-amber-800";
  return "bg-slate-100 text-slate-600";
}

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

function confidenceClass(confidence: AggregationUploadedFile["extraction_confidence"] | AggregationSourceCard["confidence"]): string {
  if (confidence === "high") return "bg-emerald-100 text-emerald-800";
  if (confidence === "medium") return "bg-[#eef1ff] text-[#5b76fe]";
  if (confidence === "low") return "bg-amber-100 text-amber-800";
  return "bg-slate-100 text-slate-600";
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
  return Object.entries(preview.resource_counts)
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
  counts: Record<string, number>,
): [string, number][] {
  if (overview?.resource_type_counts.length) {
    return overview.resource_type_counts
      .map((item) => [item.resource_type, item.count] as [string, number])
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);
  }
  return Object.entries(counts)
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
  extractStatus,
  extractStartedAt,
  extractCompletedAt,
  extractError,
  onRunExtraction,
}: {
  patientId: string;
  baselineSource: AggregationSourceCard | null;
  baselineCounts: Record<string, number>;
  selectedSource: SourceSelection | null;
  file: AggregationUploadedFile | null;
  extractInProgress: boolean;
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
  const preparedJsonQuery = useQuery({
    queryKey: ["aggregation-upload-json", patientId, file?.file_id],
    queryFn: () => api.getAggregationUploadJson(patientId, file!.file_id),
    enabled: Boolean(jsonModalOpen && patientId && file && hasPreparedOutput && !selectedIsBaseline),
  });

  useEffect(() => {
    setJsonModalOpen(false);
  }, [file?.file_id, selectedSource?.type]);

  const baselineRows = baselineSampleRows(overview);
  const baselineTotal = baselineSource?.record_count ?? Object.values(baselineCounts).reduce((sum, count) => sum + count, 0);

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
                <CompactMetric label="Estimate" value="Page-based" detail="often 30-90s" />
                <CompactMetric label="Started" value={extractStartedAt ? dateLabel(extractStartedAt) : "Not yet"} detail="job time" />
                <CompactMetric label="Finished" value={extractCompletedAt ? dateLabel(extractCompletedAt) : "Pending"} detail="job time" />
              </div>
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
  const [uploadForm, setUploadForm] = useState<Omit<AggregationUploadPayload, "file">>(emptyUploadForm);
  const collectionId = `upload-${safeUploadSessionId(patientId)}`;
  const baselineSource =
    sources.source_cards.find((source) => source.id === "synthea-fhir" && source.mode === "available") ?? null;
  const uploadMutation = useMutation({
    mutationFn: (payload: AggregationUploadPayload) => api.uploadAggregationFile(patientId, payload),
    onSuccess: () => {
      setUploadModalOpen(false);
      setSelectedFile(null);
      setUploadForm(emptyUploadForm);
      refreshAll();
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (fileId: string) => api.deleteAggregationFile(patientId, fileId),
    onSuccess: refreshAll,
  });
  const extractMutation = useMutation({
    mutationFn: () => api.extractHarmonizeCollection(collectionId),
    onSuccess: (job) => {
      setActiveExtractJobId(job.job_id);
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
  const extractJob = extractJobQuery.data ?? null;
  const extractInProgress =
    extractMutation.isPending ||
    extractJob?.status === "pending" ||
    extractJob?.status === "running";

  useEffect(() => {
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
    if (extractJob?.status !== "complete") return;
    refreshAll();
    queryClient.invalidateQueries({ queryKey: ["aggregation-upload-preview", patientId] });
  }, [extractJob?.status, patientId, queryClient]);

  function openUpload(file?: File | null) {
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

interface TransformationRow {
  id: string;
  name: string;
  type: string;
  status: string;
  confidence: "high" | "medium" | "low" | "unknown" | "not_started";
  fhirTarget: string;
  fields: string[];
  nextStep: string;
  details: string;
}

function mappingTargetForType(type: string): string {
  const normalized = type.toLowerCase();
  if (normalized.includes("fhir")) return "Already structured FHIR resources";
  if (normalized.includes("lab")) return "Observation, DiagnosticReport";
  if (normalized.includes("medication") || normalized.includes("pharmacy")) return "MedicationRequest, MedicationStatement";
  if (normalized.includes("wearable") || normalized.includes("device")) return "Patient-generated observations";
  if (normalized.includes("insurance") || normalized.includes("payer")) return "Coverage, Claim context";
  if (normalized.includes("pdf")) return "DocumentReference plus extracted candidate facts";
  return "DocumentReference and source-linked context";
}

function fieldsForType(type: string): string[] {
  const normalized = type.toLowerCase();
  if (normalized.includes("fhir")) return ["resourceType", "code", "date", "status", "encounter link"];
  if (normalized.includes("lab")) return ["test name", "value", "unit", "reference range", "result date"];
  if (normalized.includes("medication") || normalized.includes("pharmacy")) return ["drug name", "dose", "frequency", "fill date", "current status"];
  if (normalized.includes("wearable") || normalized.includes("device")) return ["metric", "value", "unit", "timestamp", "device source"];
  if (normalized.includes("pdf")) return ["document date", "section text", "clinical terms", "source page"];
  return ["file metadata", "description", "source", "patient context"];
}

function sourceDisplayName(source: AggregationSourceCard): string {
  if (source.category === "synthetic_fhir") return "Existing chart export";
  if (source.category === "private_ehi") return "Local health system export";
  return source.name;
}

function sourceDisplayType(source: AggregationSourceCard): string {
  if (source.category === "synthetic_fhir") return "Structured health record";
  if (source.category === "private_ehi") return "Health system export";
  return source.category.replaceAll("_", " ");
}

function sourceDisplayDetails(source: AggregationSourceCard): string {
  if (source.category === "synthetic_fhir") {
    return "A structured chart export is available as a baseline for transformation review.";
  }
  if (source.category === "private_ehi") {
    return "A locally available health system export can be reviewed as a connected dataset.";
  }
  return source.posture;
}

function buildTransformationRows(sources: AggregationEnvironmentResponse): TransformationRow[] {
  const uploadedRows = sources.uploaded_files.map((file) => ({
    id: `upload-${file.file_id}`,
    name: file.file_name,
    type: file.data_type,
    status: file.status.replace("_", " "),
    confidence: file.extraction_confidence,
    fhirTarget: mappingTargetForType(file.data_type),
    fields: file.contains.length ? file.contains : fieldsForType(file.data_type),
    nextStep: file.description ? "Process and review extracted fields." : "Add a description before processing.",
    details: file.description || "This file needs patient-entered context before transformation review.",
  }));

  const sourceRows = sources.source_cards
    .filter((source) => source.mode === "available" || source.mode === "private")
    .map((source) => ({
      id: source.id,
      name: sourceDisplayName(source),
      type: sourceDisplayType(source),
      status: source.status_label,
      confidence: source.confidence,
      fhirTarget: source.category === "synthetic_fhir" ? "Patient, Condition, MedicationRequest, Observation, Encounter" : "Source-specific mapping review",
      fields: source.evidence.slice(0, 5),
      nextStep: source.category === "synthetic_fhir" ? "Review field coverage and provenance." : "Review field coverage before downstream use.",
      details: sourceDisplayDetails(source),
    }));

  return [...uploadedRows, ...sourceRows];
}

function CleaningQueuePage({ sources }: { sources: AggregationEnvironmentResponse }) {
  const rows = useMemo(() => buildTransformationRows(sources), [sources]);
  const [selectedId, setSelectedId] = useState(rows[0]?.id ?? "");
  const selected = rows.find((row) => row.id === selectedId) ?? rows[0];
  const readyCount = rows.filter((row) => row.confidence === "high").length;
  const reviewCount = rows.filter((row) => row.confidence !== "high").length;

  return (
    <div className="space-y-5">
      <section className="grid gap-4 lg:grid-cols-3">
        <MetricCard label="Datasets" value={rows.length} detail="Uploaded or connected sources." />
        <MetricCard label="High confidence" value={readyCount} detail="Structured or known data shape." />
        <MetricCard label="Needs review" value={reviewCount} detail="Requires context or mapping review." />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <div className="rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center justify-between gap-3 border-b border-[#eef0f5] p-5">
            <div>
              <h2 className="text-lg font-semibold text-[#1c1c1e]">Datasets and transformation status</h2>
              <p className="mt-1 text-sm text-[#667085]">Click a row to inspect mapping targets and field confidence.</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold uppercase tracking-wider text-[#8d92a3]">
                  <th className="border-b border-[#eef0f5] px-5 py-3">Dataset</th>
                  <th className="border-b border-[#eef0f5] px-5 py-3">Type</th>
                  <th className="border-b border-[#eef0f5] px-5 py-3">FHIR / semantic target</th>
                  <th className="border-b border-[#eef0f5] px-5 py-3">Confidence</th>
                  <th className="border-b border-[#eef0f5] px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => setSelectedId(row.id)}
                    className={`cursor-pointer ${selected?.id === row.id ? "bg-[#f7f8ff]" : "hover:bg-[#fafbff]"}`}
                  >
                    <td className="border-b border-[#f2f4f8] px-5 py-4 align-top">
                      <p className="font-semibold text-[#1c1c1e]">{row.name}</p>
                      <p className="mt-1 text-xs text-[#8d92a3]">{row.nextStep}</p>
                    </td>
                    <td className="border-b border-[#f2f4f8] px-5 py-4 align-top text-[#555a6a]">{row.type}</td>
                    <td className="border-b border-[#f2f4f8] px-5 py-4 align-top text-[#555a6a]">{row.fhirTarget}</td>
                    <td className="border-b border-[#f2f4f8] px-5 py-4 align-top">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${confidenceClass(row.confidence)}`}>{row.confidence.replace("_", " ")}</span>
                    </td>
                    <td className="border-b border-[#f2f4f8] px-5 py-4 align-top text-[#555a6a]">{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <aside className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          {selected ? (
            <>
              <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Dataset details</p>
              <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">{selected.name}</h2>
              <p className="mt-2 text-sm leading-6 text-[#667085]">{selected.details}</p>
              <div className="mt-4 rounded-xl bg-[#fafbff] p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Maps toward</p>
                <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">{selected.fhirTarget}</p>
              </div>
              <div className="mt-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Fields we expect to use</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {selected.fields.map((field) => (
                    <span key={field} className="rounded-full bg-[#eef1ff] px-2.5 py-1 text-xs font-semibold text-[#5b76fe]">{field}</span>
                  ))}
                </div>
              </div>
              <div className="mt-4 rounded-xl bg-[#fff8f1] p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">Next step</p>
                <p className="mt-1 text-sm leading-6 text-[#555a6a]">{selected.nextStep}</p>
              </div>
            </>
          ) : (
            <p className="text-sm text-[#667085]">No datasets available yet.</p>
          )}
        </aside>
      </section>
    </div>
  );
}

function ReadinessPage({
  readiness,
  patientId,
}: {
  readiness: AggregationReadinessResponse;
  patientId: string;
}) {
  return (
    <div className="space-y-5">
      <section className="grid gap-4 lg:grid-cols-[0.75fr_1.25fr]">
        <div className="rounded-2xl bg-[#111827] p-6 text-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <Gauge size={20} className="text-[#a5b4fc]" />
            <p className="text-sm font-semibold text-[#d1d5db]">Packet readiness</p>
          </div>
          <p className="mt-4 text-5xl font-semibold">{readiness.readiness_score}</p>
          <p className="mt-2 text-sm leading-6 text-[#d1d5db]">{readiness.posture}</p>
          <div className="mt-5 h-2 rounded-full bg-white/15">
            <div className="h-2 rounded-full bg-[#a5b4fc]" style={{ width: `${readiness.readiness_score}%` }} />
          </div>
        </div>

        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-[#1c1c1e]">Readiness blockers</h2>
              <p className="mt-2 text-sm leading-6 text-[#667085]">
                These are the boundaries we should acknowledge in a demo or before activating downstream modules.
              </p>
            </div>
            <HelpButton
              title="Publish readiness"
              body="Readiness does not mean all production adapters are done. It means the current packet has clear evidence, boundaries, gaps, and next actions."
            />
          </div>
          <div className="mt-4 grid gap-2">
            {readiness.blockers.map((blocker) => (
              <div key={blocker} className="flex items-center gap-2 rounded-xl bg-[#fff8f1] p-3 text-sm text-[#9a5a16]">
                <Clock3 size={16} />
                {blocker}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        {readiness.checklist.map((item) => (
          <div key={item.id} className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold text-[#1c1c1e]">{item.label}</h3>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${readinessClass(item.status)}`}>
                    {item.status.replace("_", " ")}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-[#667085]">{item.body}</p>
              </div>
              <span className="rounded-xl bg-[#f5f6f8] px-3 py-2 text-sm font-semibold text-[#1c1c1e]">{item.score}</span>
            </div>
            <div className="mt-4 rounded-xl bg-[#fafbff] p-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Next action</p>
              <p className="mt-1 text-sm leading-6 text-[#1c1c1e]">{item.next_action}</p>
            </div>
          </div>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_0.85fr]">
        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <Layers3 size={18} className="text-[#5b76fe]" />
            <h2 className="text-lg font-semibold text-[#1c1c1e]">Packet export targets</h2>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {readiness.export_targets.map((target) => (
              <span key={target} className="rounded-full bg-[#eef1ff] px-3 py-1.5 text-sm font-semibold text-[#5b76fe]">
                {target}
              </span>
            ))}
          </div>
        </div>
        <div className="rounded-2xl bg-[#f7fffc] p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <MessageSquareText size={18} className="text-[#0f766e]" />
            <h2 className="text-lg font-semibold text-[#0f172a]">Context before publishing</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-[#35524d]">
            Patient Context should travel alongside the chart packet as a separate patient-reported layer.
          </p>
          <Link to={`/aggregate/context?patient=${patientId}`} className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-[#0f766e]">
            Review Patient Context
            <ArrowRight size={14} />
          </Link>
        </div>
      </section>
    </div>
  );
}

export function DataAggregator() {
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const patientFromUrl = params.get("patient");
  const page: AggregatorPage = location.pathname.includes("/cleaning")
    ? "cleaning"
    : location.pathname.includes("/publish")
      ? "publish"
      : "sources";
  const copy = pageCopy[page];

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

  const sourcesQuery = useQuery({
    queryKey: ["aggregation-sources", patientId],
    queryFn: () => api.getAggregationSources(patientId),
    enabled: Boolean(patientId),
  });

  const readinessQuery = useQuery({
    queryKey: ["aggregation-readiness", patientId],
    queryFn: () => api.getAggregationReadiness(patientId),
    enabled: Boolean(patientId),
  });

  const refreshAll = () => {
    sourcesQuery.refetch();
    readinessQuery.refetch();
  };

  const guidance = useMemo(() => {
    if (page !== "publish") return [];
    return [
      "Review uploaded documents before publishing a patient packet.",
      "Keep patient descriptions, source files, and chart facts clearly separated.",
    ];
  }, [page]);

  const isLoading = !patientId || sourcesQuery.isLoading || (page === "publish" && readinessQuery.isLoading);
  const hasError = sourcesQuery.isError || (page === "publish" && readinessQuery.isError);

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-lg border border-[#dfe4ea] bg-white px-5 py-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              {page === "sources" && <FileSearch size={13} />}
              {page === "cleaning" && <SlidersHorizontal size={13} />}
              {page === "publish" && <ShieldCheck size={13} />}
              {copy.badge}
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-[#1c1c1e]">{copy.title}</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-[#667085]">{copy.body}</p>
          </div>
          {page === "sources" ? (
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
                <p className="text-sm font-semibold text-[#1c1c1e]">{page === "cleaning" ? "Dataset review" : "Packet status"}</p>
              </div>
              <p className="mt-2 text-sm leading-6 text-[#667085]">
                {page === "cleaning"
                  ? "Check each source before it feeds the patient packet."
                  : "Confirm what is ready, what needs review, and what should stay separate."}
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

      {!isLoading && !hasError && page === "sources" && sourcesQuery.data && (
        <SourceInventoryPage patientId={patientId} sources={sourcesQuery.data} refreshAll={refreshAll} />
      )}
      {!isLoading && !hasError && page === "cleaning" && sourcesQuery.data && (
        <CleaningQueuePage sources={sourcesQuery.data} />
      )}
      {!isLoading && !hasError && page === "publish" && readinessQuery.data && (
        <ReadinessPage readiness={readinessQuery.data} patientId={patientId} />
      )}
    </main>
  );
}
