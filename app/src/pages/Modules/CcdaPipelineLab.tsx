import { useMemo, useState, type DragEvent, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  FileCode2,
  FileJson,
  FileText,
  GitCompare,
  ListChecks,
  LoaderCircle,
  Play,
  Server,
  Upload,
} from "lucide-react";
import { api } from "../../api/client";
import type { CcdaLabConversionResponse, CcdaLabProcessorOption, CcdaLabResourceSample } from "../../types";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function detectInputKind(file: File | null): "ccda" | "pdf" | null {
  if (!file) return null;
  const name = file.name.toLowerCase();
  if (name.endsWith(".pdf")) return "pdf";
  if (name.endsWith(".xml") || name.endsWith(".ccda") || name.endsWith(".cda")) return "ccda";
  return null;
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function processorTone(option: CcdaLabProcessorOption): string {
  if (!option.available) return "border-[#e5e7eb] bg-[#f8fafc] text-[#8a93a3]";
  if (option.backend.includes("microsoft")) return "border-[#cdeee9] bg-[#f4fffc] text-[#0f766e]";
  if (option.input_kinds.includes("pdf")) return "border-[#dfe4ff] bg-[#f7f8ff] text-[#4f5edb]";
  return "border-[#f6dfc9] bg-[#fff8f1] text-[#9a5a16]";
}

function Metric({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="border border-[#e8edf3] bg-white p-3">
      <div className="text-xs font-semibold uppercase text-[#7a8190]">{label}</div>
      <div className="mt-1 text-xl font-semibold text-[#1c1c1e]">{value}</div>
      {hint && <div className="mt-1 truncate text-xs text-[#7a8190]">{hint}</div>}
    </div>
  );
}

function ResourceCountPills({ counts }: { counts: Record<string, number> }) {
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (!rows.length) return <div className="text-sm text-[#7a8190]">No FHIR resources emitted.</div>;
  return (
    <div className="flex flex-wrap gap-2">
      {rows.map(([type, count]) => (
        <div key={type} className="inline-flex items-center gap-2 border border-[#dfe4ea] bg-[#f8fafc] px-2.5 py-1.5 text-sm">
          <span className="font-medium text-[#1c1c1e]">{type}</span>
          <span className="rounded-sm bg-white px-1.5 py-0.5 text-xs font-semibold tabular-nums text-[#555a6a]">{count}</span>
        </div>
      ))}
    </div>
  );
}

type SectionFindingStatus = "exact" | "partial" | "missed" | "extra" | "unmapped";

interface SectionFinding {
  key: string;
  title: string;
  code: string | null;
  sourceEntries: number;
  emitted: number;
  expectedTypes: string[];
  status: SectionFindingStatus;
  delta: number;
}

function sectionFindings(result: CcdaLabConversionResponse): SectionFinding[] {
  const sections = result.source_summary?.sections || [];
  return sections.map((section, index) => {
    const mapped = section.expected_resource_types.length > 0;
    const emitted = section.emitted_matching_resources;
    let status: SectionFindingStatus = "unmapped";
    if (mapped && emitted === 0 && section.entry_count > 0) status = "missed";
    else if (mapped && emitted < section.entry_count) status = "partial";
    else if (mapped && emitted > section.entry_count) status = "extra";
    else if (mapped) status = "exact";
    return {
      key: `${section.code || section.title}-${index}`,
      title: section.title,
      code: section.code,
      sourceEntries: section.entry_count,
      emitted,
      expectedTypes: section.expected_resource_types,
      status,
      delta: emitted - section.entry_count,
    };
  });
}

function findingTone(status: SectionFindingStatus): { label: string; className: string; note: string } {
  if (status === "exact") {
    return {
      label: "one-for-one",
      className: "border-[#cdeee9] bg-[#f4fffc] text-[#0f766e]",
      note: "FHIR count matches source entries for this section.",
    };
  }
  if (status === "partial") {
    return {
      label: "partial",
      className: "border-[#f6dfc9] bg-[#fff8f1] text-[#9a5a16]",
      note: "Fewer FHIR records were emitted than source entries.",
    };
  }
  if (status === "missed") {
    return {
      label: "missed",
      className: "border-[#f3c4c4] bg-[#fff5f5] text-[#b42318]",
      note: "No matching FHIR records were emitted.",
    };
  }
  if (status === "extra") {
    return {
      label: "extra output",
      className: "border-[#d9d6fe] bg-[#f6f5ff] text-[#5b21b6]",
      note: "More FHIR records were emitted than source entries.",
    };
  }
  return {
    label: "unmapped",
    className: "border-[#e5e7eb] bg-[#f8fafc] text-[#7a8190]",
    note: "This section is inventoried but not mapped to a FHIR category in the lab.",
  };
}

function ConversionReview({ result }: { result: CcdaLabConversionResponse }) {
  const findings = sectionFindings(result);
  if (!findings.length) return null;
  const counts = findings.reduce<Record<SectionFindingStatus, number>>(
    (acc, finding) => {
      acc[finding.status] += 1;
      return acc;
    },
    { exact: 0, partial: 0, missed: 0, extra: 0, unmapped: 0 },
  );
  const flagged = counts.partial + counts.missed + counts.extra;
  return (
    <div className="border border-[#dfe4ea] bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#eef2f6] px-4 py-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-[#1c1c1e]">
            <GitCompare size={16} />
            Conversion Review
          </div>
          <div className="mt-1 text-sm text-[#555a6a]">
            {flagged > 0
              ? `${flagged} section${flagged === 1 ? "" : "s"} need review for missing or extra FHIR output.`
              : "Every mapped section emitted the same number of FHIR records as source entries."}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="border border-[#cdeee9] bg-[#f4fffc] px-2 py-1 text-xs font-semibold text-[#0f766e]">
            {counts.exact} exact
          </span>
          <span className="border border-[#f6dfc9] bg-[#fff8f1] px-2 py-1 text-xs font-semibold text-[#9a5a16]">
            {counts.partial} partial
          </span>
          <span className="border border-[#f3c4c4] bg-[#fff5f5] px-2 py-1 text-xs font-semibold text-[#b42318]">
            {counts.missed} missed
          </span>
          <span className="border border-[#d9d6fe] bg-[#f6f5ff] px-2 py-1 text-xs font-semibold text-[#5b21b6]">
            {counts.extra} extra
          </span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-[#eef2f6] bg-[#f8fafc] text-xs font-semibold uppercase text-[#7a8190]">
            <tr>
              <th className="px-4 py-2">C-CDA section</th>
              <th className="px-4 py-2">Source entries</th>
              <th className="px-4 py-2">FHIR emitted</th>
              <th className="px-4 py-2">Difference</th>
              <th className="px-4 py-2">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eef2f6]">
            {findings.map((finding) => {
              const tone = findingTone(finding.status);
              return (
                <tr key={finding.key} className="align-top">
                  <td className="max-w-[360px] px-4 py-3">
                    <div className="font-semibold text-[#1c1c1e]">{finding.title}</div>
                    <div className="mt-1 text-xs text-[#7a8190]">
                      {finding.code || "No LOINC code"}
                      {finding.expectedTypes.length > 0 && ` · ${finding.expectedTypes.join(", ")}`}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-semibold tabular-nums text-[#1c1c1e]">{finding.sourceEntries}</td>
                  <td className="px-4 py-3 font-semibold tabular-nums text-[#1c1c1e]">{finding.emitted}</td>
                  <td className="px-4 py-3 tabular-nums text-[#555a6a]">
                    {finding.delta > 0 ? `+${finding.delta}` : finding.delta}
                  </td>
                  <td className="px-4 py-3">
                    <div className={`inline-flex items-center gap-1.5 border px-2 py-1 text-xs font-semibold ${tone.className}`}>
                      {finding.status === "exact" ? <CheckCircle2 size={13} /> : <CircleAlert size={13} />}
                      {tone.label}
                    </div>
                    <div className="mt-1 max-w-[260px] text-xs text-[#7a8190]">{tone.note}</div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SourceContents({ result }: { result: CcdaLabConversionResponse }) {
  const summary = result.source_summary;
  if (!summary) {
    return (
      <div className="border border-[#dfe4ea] bg-white p-4 text-sm text-[#7a8190]">
        Source section inventory is only available for C-CDA XML uploads.
      </div>
    );
  }
  return (
    <div className="border border-[#dfe4ea] bg-white">
      <div className="border-b border-[#eef2f6] px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-[#1c1c1e]">
          <ListChecks size={16} />
          C-CDA Contents
        </div>
        <div className="mt-2 space-y-1 text-sm text-[#555a6a]">
          <div className="break-words">{summary.document_title || "Untitled C-CDA document"}</div>
          <div>{summary.patient_display || "Patient not found in source summary"}</div>
        </div>
      </div>
      <div className="max-h-[560px] overflow-auto">
        {summary.sections.length === 0 && <div className="p-4 text-sm text-[#7a8190]">No structured sections found.</div>}
        {summary.sections.map((section, index) => {
          const mapped = section.expected_resource_types.length > 0;
          const emitted = section.emitted_matching_resources > 0;
          return (
            <div key={`${section.code || section.title}-${index}`} className="border-b border-[#eef2f6] p-4 last:border-b-0">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="break-words text-sm font-semibold text-[#1c1c1e]">{section.title}</div>
                  <div className="mt-1 text-xs text-[#7a8190]">
                    {section.code || "No LOINC code"} · {section.entry_count} source entries
                  </div>
                </div>
                <div
                  className={`shrink-0 border px-2 py-1 text-xs font-semibold ${
                    !mapped
                      ? "border-[#e5e7eb] bg-[#f8fafc] text-[#7a8190]"
                      : emitted
                        ? "border-[#cdeee9] bg-[#f4fffc] text-[#0f766e]"
                        : "border-[#f6dfc9] bg-[#fff8f1] text-[#9a5a16]"
                  }`}
                >
                  {!mapped ? "unmapped" : emitted ? "emitted" : "missing"}
                </div>
              </div>
              {section.expected_resource_types.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {section.expected_resource_types.map((type) => (
                    <span key={type} className="border border-[#dfe4ea] bg-[#f8fafc] px-2 py-1 text-xs text-[#555a6a]">
                      {type}
                    </span>
                  ))}
                  <span className="border border-[#d9efe9] bg-[#f4fffc] px-2 py-1 text-xs text-[#0f766e]">
                    {section.emitted_matching_resources} matching FHIR
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FhirResourceGroups({ result }: { result: CcdaLabConversionResponse }) {
  const groups = result.samples.reduce<Record<string, CcdaLabResourceSample[]>>((acc, sample) => {
    acc[sample.resource_type] = acc[sample.resource_type] || [];
    acc[sample.resource_type].push(sample);
    return acc;
  }, {});
  const orderedTypes = Object.entries(result.resource_counts).sort((a, b) => b[1] - a[1]).map(([type]) => type);
  if (!orderedTypes.length) return <div className="border border-[#dfe4ea] bg-white p-4 text-sm text-[#7a8190]">No FHIR resources emitted.</div>;
  return (
    <div className="space-y-3">
      {orderedTypes.map((type) => {
        const samples = groups[type] || [];
        return (
          <div key={type} className="border border-[#dfe4ea] bg-white">
            <div className="flex items-center justify-between gap-3 border-b border-[#eef2f6] px-4 py-3">
              <div className="font-semibold text-[#1c1c1e]">{type}</div>
              <div className="text-sm font-semibold tabular-nums text-[#555a6a]">{result.resource_counts[type]}</div>
            </div>
            <div className="divide-y divide-[#eef2f6]">
              {samples.slice(0, 8).map((sample, index) => (
                <div key={`${type}-${sample.id || index}`} className="grid gap-2 px-4 py-3 text-sm lg:grid-cols-[minmax(220px,1fr)_120px_120px]">
                  <div className="min-w-0">
                    <div className="whitespace-normal font-medium leading-5 text-[#1c1c1e]">{sample.display || sample.id || "No display text"}</div>
                    {sample.id && <div className="mt-1 truncate font-mono text-xs text-[#7a8190]">{sample.id}</div>}
                  </div>
                  <div className="text-[#555a6a]">{sample.status || "-"}</div>
                  <div className="text-[#555a6a]">{sample.value || sample.date || "-"}</div>
                </div>
              ))}
              {samples.length === 0 && <div className="px-4 py-3 text-sm text-[#7a8190]">No samples captured for this resource type.</div>}
              {result.resource_counts[type] > samples.length && (
                <div className="px-4 py-3 text-xs font-medium text-[#7a8190]">
                  Showing {samples.length} of {result.resource_counts[type]} emitted {type} resources.
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RawDetails({ title, icon, value }: { title: string; icon: ReactNode; value: unknown }) {
  return (
    <details className="border border-[#dfe4ea] bg-white">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-semibold text-[#1c1c1e]">
        {icon}
        {title}
        <ChevronDown className="ml-auto text-[#7a8190]" size={16} />
      </summary>
      <pre className="max-h-[520px] overflow-auto border-t border-[#eef2f6] p-4 text-xs leading-5 text-[#2f3542]">{prettyJson(value)}</pre>
    </details>
  );
}

export function CcdaPipelineLab() {
  const [file, setFile] = useState<File | null>(null);
  const [processorId, setProcessorId] = useState("ccda-microsoft");
  const [skipCache, setSkipCache] = useState(false);
  const [result, setResult] = useState<CcdaLabConversionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isDragActive, setIsDragActive] = useState(false);

  const processorsQuery = useQuery({
    queryKey: ["ccda-lab-processors"],
    queryFn: api.getCcdaLabProcessors,
  });

  const inputKind = detectInputKind(file);
  const processors = processorsQuery.data?.options || [];
  const filteredProcessors = useMemo(() => {
    if (!inputKind) return processors;
    return processors.filter((option) => option.input_kinds.includes(inputKind));
  }, [inputKind, processors]);
  const selectedProcessor = processors.find((option) => option.id === processorId);

  function onFile(nextFile: File | null) {
    setFile(nextFile);
    setResult(null);
    setError(null);
    const nextKind = detectInputKind(nextFile);
    if (nextKind === "ccda") {
      const preferred = processors.find((option) => option.id === "ccda-microsoft" && option.available);
      setProcessorId(preferred?.id || "ccda-auto");
    } else if (nextKind === "pdf") {
      const preferred = processors.find((option) => option.id === "pdfplumber-lab-text") || processors.find((option) => option.input_kinds.includes("pdf"));
      if (preferred) setProcessorId(preferred.id);
    }
  }

  function onDragOver(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = "copy";
    }
    setIsDragActive(true);
  }

  function onDragLeave(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) return;
    setIsDragActive(false);
  }

  function onDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    event.stopPropagation();
    setIsDragActive(false);
    const dropped = event.dataTransfer.files?.[0] || null;
    if (dropped) onFile(dropped);
  }

  const microsoftStatus = processorsQuery.data?.microsoft_status;
  const converterStatus = processorsQuery.isLoading
    ? "Checking converter..."
    : processorsQuery.isError
      ? "Processor API unavailable"
      : microsoftStatus?.reachable
        ? "Microsoft converter reachable"
        : microsoftStatus?.configured
          ? "Microsoft configured but unreachable"
          : "Microsoft converter not configured";
  const converterStatusDetail = microsoftStatus?.endpoint || microsoftStatus?.detail || "";

  async function run() {
    if (!file || !selectedProcessor || !selectedProcessor.available) return;
    setIsRunning(true);
    setError(null);
    setResult(null);
    try {
      const response = await api.convertCcdaLabDocument(file, selectedProcessor.id, skipCache);
      setResult(response);
    } catch (err) {
      const maybe = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(maybe.response?.data?.detail || maybe.message || "Conversion failed.");
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div
      className="min-h-screen bg-[#f6f7fb]"
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="mx-auto max-w-7xl px-6 py-6">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#e2e7ef] pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#0f766e]">
              <FileCode2 size={15} />
              Internal Tools
            </div>
            <h1 className="mt-2 text-2xl font-semibold text-[#1c1c1e]">C-CDA Pipeline Lab</h1>
          </div>
          <div
            className={`flex items-center gap-2 border bg-white px-3 py-2 text-sm ${
              microsoftStatus?.reachable
                ? "border-[#d9efe9] text-[#0f766e]"
                : microsoftStatus?.configured
                  ? "border-[#f6dfc9] text-[#9a5a16]"
                  : "border-[#e5e7eb] text-[#7a8190]"
            }`}
            title={converterStatusDetail}
          >
            <Server size={16} />
            <span>{converterStatus}</span>
            {converterStatusDetail && <span className="hidden max-w-[220px] truncate text-xs text-[#7a8190] md:inline">{converterStatusDetail}</span>}
          </div>
        </div>

        <div className="mt-6 grid gap-5 lg:grid-cols-[420px_minmax(0,1fr)]">
          <section className="border border-[#dfe4ea] bg-white p-4">
            <label
              className={`flex min-h-[150px] cursor-pointer flex-col items-center justify-center border border-dashed px-4 text-center transition ${
                isDragActive
                  ? "border-[#5b76fe] bg-[#eef1ff]"
                  : "border-[#cdd6e1] bg-[#f8fafc] hover:border-[#5b76fe]"
              }`}
              onDragEnter={onDragOver}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
            >
              <Upload size={24} className="text-[#5b76fe]" />
              <span className="mt-3 text-sm font-semibold text-[#1c1c1e]">
                {file ? file.name : isDragActive ? "Drop file to load" : "Upload or drop C-CDA XML or PDF"}
              </span>
              <span className="mt-1 text-xs text-[#7a8190]">
                {file ? `${formatBytes(file.size)} · ${inputKind || "unknown"}` : `Limit ${formatBytes(processorsQuery.data?.upload_limit_bytes || 0)}`}
              </span>
              <input
                type="file"
                accept=".xml,.ccda,.cda,.pdf,application/pdf,text/xml,application/xml"
                className="sr-only"
                onChange={(event) => onFile(event.target.files?.[0] || null)}
              />
            </label>

            <div className="mt-4">
              <label className="text-xs font-semibold uppercase text-[#7a8190]">Processor</label>
              <div className="relative mt-2">
                <select
                  value={processorId}
                  onChange={(event) => setProcessorId(event.target.value)}
                  className="w-full appearance-none border border-[#dfe4ea] bg-white px-3 py-2 pr-9 text-sm font-medium text-[#1c1c1e] outline-none focus:border-[#5b76fe]"
                >
                  {filteredProcessors.map((option) => (
                    <option key={option.id} value={option.id} disabled={!option.available}>
                      {option.label}{!option.available ? " unavailable" : ""}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-2.5 text-[#7a8190]" size={16} />
              </div>
            </div>

            {selectedProcessor && (
              <div className={`mt-3 border px-3 py-2 text-sm ${processorTone(selectedProcessor)}`}>
                <div className="font-semibold">{selectedProcessor.backend || selectedProcessor.label}</div>
                <div className="mt-1 text-xs">{selectedProcessor.description}</div>
              </div>
            )}

            {inputKind === "pdf" && (
              <label className="mt-4 flex items-center gap-2 text-sm text-[#555a6a]">
                <input
                  type="checkbox"
                  checked={skipCache}
                  onChange={(event) => setSkipCache(event.target.checked)}
                  className="h-4 w-4 rounded border-[#cdd6e1]"
                />
                Skip cache
              </label>
            )}

            <button
              onClick={run}
              disabled={!file || !selectedProcessor?.available || isRunning}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 bg-[#5b76fe] px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-[#b9c2d6]"
            >
              {isRunning ? <LoaderCircle className="animate-spin" size={16} /> : <Play size={16} />}
              Run
            </button>

            {error && (
              <div className="mt-4 flex gap-2 border border-[#f3c4c4] bg-[#fff5f5] p-3 text-sm text-[#b42318]">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}
          </section>

          <section className="min-w-0 space-y-5">
            {!result && (
              <div className="flex min-h-[360px] items-center justify-center border border-[#dfe4ea] bg-white text-sm text-[#7a8190]">
                <div className="text-center">
                  <FileJson className="mx-auto text-[#9aa3b2]" size={28} />
                  <div className="mt-3 font-medium">FHIR output appears here</div>
                </div>
              </div>
            )}

            {result && (
              <>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                  <Metric label="C-CDA sections" value={result.coverage.source_section_count || "-"} />
                  <Metric label="C-CDA entries" value={result.coverage.source_entry_count || "-"} />
                  <Metric label="FHIR resources" value={result.coverage.emitted_resource_count} />
                  <Metric label="Clinical resources" value={result.coverage.emitted_clinical_resource_count} />
                  <Metric label="Backend" value={result.backend_used} hint={result.processor_label} />
                  <Metric label="Latency" value={`${result.latency_ms} ms`} />
                </div>

                <div className="border border-[#dfe4ea] bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-semibold text-[#1c1c1e]">
                        <GitCompare size={16} />
                        C-CDA to FHIR Coverage
                      </div>
                      <div className="mt-1 text-sm text-[#555a6a]">
                        {result.coverage.mappable_section_count > 0
                          ? `${result.coverage.mapped_section_count} of ${result.coverage.mappable_section_count} mappable C-CDA sections produced matching FHIR categories.`
                          : "No mappable C-CDA sections were detected from this upload."}
                      </div>
                    </div>
                    <ResourceCountPills counts={result.resource_counts} />
                  </div>
                </div>

                <ConversionReview result={result} />

                {result.warnings.length > 0 && (
                  <div className="flex gap-2 border border-[#f6dfc9] bg-[#fff8f1] p-3 text-sm text-[#9a5a16]">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                    <div>{result.warnings.join(" ")}</div>
                  </div>
                )}

                {result.warnings.length === 0 && (
                  <div className="flex gap-2 border border-[#cdeee9] bg-[#f4fffc] p-3 text-sm text-[#0f766e]">
                    <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
                    <div>Bundle emitted without structural warnings.</div>
                  </div>
                )}

                <div className="grid min-w-0 gap-5 2xl:grid-cols-[420px_minmax(0,1fr)]">
                  <div className="min-w-0">
                    <SourceContents result={result} />
                  </div>

                  <div className="min-w-0 space-y-5">
                    <div className="border border-[#dfe4ea] bg-white">
                      <div className="flex items-center gap-2 border-b border-[#eef2f6] px-4 py-3 text-sm font-semibold text-[#1c1c1e]">
                        <BarChart3 size={16} />
                        FHIR Output by Type
                      </div>
                      <div className="p-4">
                        <FhirResourceGroups result={result} />
                      </div>
                    </div>

                    <RawDetails title="Bundle Shape JSON" icon={<FileText size={16} />} value={result.bundle_shape} />
                    <RawDetails title="FHIR Bundle JSON" icon={<FileJson size={16} />} value={result.bundle} />
                  </div>
                </div>
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
