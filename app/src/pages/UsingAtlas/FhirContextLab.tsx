import { useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  FileJson,
  GitBranch,
  Layers3,
  Loader2,
  UploadCloud,
} from "lucide-react";
import { api } from "../../api/client";
import type { FhirContextLabPreviewResponse } from "../../types";
import { PageHeader } from "./components/PageHeader";

function formatNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return value.toLocaleString();
}

function errorMessage(error: unknown): string {
  if (error && typeof error === "object" && "response" in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  if (error instanceof Error) return error.message;
  return "Could not build context for this upload.";
}

function MetricTile({ label, value, sublabel }: { label: string; value: string; sublabel: string }) {
  return (
    <div className="rounded-lg border border-[#e7eaf2] bg-white px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#9aa5c0]">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-[#1d2433]">{value}</p>
      <p className="mt-1 text-xs leading-relaxed text-[#6b7390]">{sublabel}</p>
    </div>
  );
}

function UploadPanel({
  file,
  isLoading,
  onSelect,
  onSubmit,
}: {
  file: File | null;
  isLoading: boolean;
  onSelect: (file: File | null) => void;
  onSubmit: () => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  return (
    <section className="rounded-xl border border-[#dfe5f0] bg-white p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-[#eef1ff]">
            <UploadCloud size={19} className="text-[#5b76fe]" />
          </div>
          <h2 className="text-lg font-semibold text-[#1d2433]">Upload a FHIR package</h2>
          <p className="mt-1 max-w-xl text-sm leading-relaxed text-[#4a5168]">
            Accepts a FHIR JSON Bundle, a single FHIR resource JSON, or a ZIP with JSON files.
            The preview runs in memory and does not create a patient workspace.
          </p>
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#cfd7ff] bg-[#f7f8ff] px-3 py-2 text-sm font-semibold text-[#435be0] transition-colors hover:bg-[#eef1ff]"
        >
          <FileJson size={15} />
          Choose file
        </button>
      </div>

      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".json,.zip,application/json,application/zip"
        onChange={(event) => onSelect(event.target.files?.[0] ?? null)}
      />

      <div className="mt-5 flex flex-col gap-3 rounded-lg border border-dashed border-[#cbd5e1] bg-[#fafbfd] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-medium text-[#1d2433]">
            {file ? file.name : "No file selected"}
          </p>
          <p className="mt-0.5 text-xs text-[#6b7390]">
            {file ? `${formatNumber(file.size)} bytes` : "Your local file is sent only when you run the preview."}
          </p>
        </div>
        <button
          type="button"
          disabled={!file || isLoading}
          onClick={onSubmit}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#1d2433] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#30394d] disabled:cursor-not-allowed disabled:bg-[#c5ccd8]"
        >
          {isLoading ? <Loader2 size={15} className="animate-spin" /> : <GitBranch size={15} />}
          Build context
        </button>
      </div>
    </section>
  );
}

function TraceSteps({ result }: { result: FhirContextLabPreviewResponse }) {
  return (
    <section className="rounded-xl border border-[#e7eaf2] bg-white p-5">
      <div className="mb-4 flex items-center gap-2">
        <Layers3 size={17} className="text-[#5b76fe]" />
        <h2 className="text-lg font-semibold text-[#1d2433]">Transformation trace</h2>
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        {result.trace_steps.map((step, index) => (
          <div key={`${step.label}-${index}`} className="rounded-lg border border-[#e7eaf2] bg-[#fbfcff] p-3">
            <div className="mb-2 flex items-center gap-2">
              <CheckCircle2 size={14} className="text-[#16804f]" />
              <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#6b7390]">
                Step {index + 1}
              </span>
            </div>
            <p className="text-sm font-semibold text-[#1d2433]">{step.label}</p>
            <p className="mt-1 text-xs leading-relaxed text-[#6b7390]">{step.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ResourceCounts({ result }: { result: FhirContextLabPreviewResponse }) {
  const topCounts = Object.entries(result.resource_type_counts).slice(0, 10);
  const maxCount = Math.max(...topCounts.map(([, count]) => count), 1);

  return (
    <section className="rounded-xl border border-[#e7eaf2] bg-white p-5">
      <h2 className="text-lg font-semibold text-[#1d2433]">Resource mix</h2>
      <div className="mt-4 space-y-3">
        {topCounts.map(([resourceType, count]) => (
          <div key={resourceType}>
            <div className="mb-1 flex items-center justify-between gap-3 text-xs">
              <span className="font-medium text-[#1d2433]">{resourceType}</span>
              <span className="text-[#6b7390]">{formatNumber(count)}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[#edf1f7]">
              <div
                className="h-full rounded-full bg-[#5b76fe]"
                style={{ width: `${Math.max(4, (count / maxCount) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function SectionBreakdown({ result }: { result: FhirContextLabPreviewResponse }) {
  return (
    <section className="rounded-xl border border-[#e7eaf2] bg-white p-5">
      <h2 className="text-lg font-semibold text-[#1d2433]">Context sections</h2>
      <div className="mt-4 overflow-hidden rounded-lg border border-[#e7eaf2]">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-[#f8fafc] text-left text-[11px] uppercase tracking-[0.1em] text-[#6b7390]">
            <tr>
              <th className="px-3 py-2 font-semibold">Section</th>
              <th className="px-3 py-2 font-semibold">Items</th>
              <th className="px-3 py-2 font-semibold">Tokens</th>
            </tr>
          </thead>
          <tbody>
            {result.sections.map((section) => (
              <tr key={section.label} className="border-t border-[#e7eaf2]">
                <td className="px-3 py-2 text-[#1d2433]">
                  <span className={section.included ? "font-medium" : "text-[#9aa5c0]"}>
                    {section.label}
                  </span>
                </td>
                <td className="px-3 py-2 text-[#4a5168]">{formatNumber(section.count)}</td>
                <td className="px-3 py-2 text-[#4a5168]">~{formatNumber(section.token_estimate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MarkdownPreview({ markdown }: { markdown: string }) {
  const [copied, setCopied] = useState(false);

  async function copyMarkdown() {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <section className="rounded-xl border border-[#e7eaf2] bg-white p-5">
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#1d2433]">Prompt-ready clinical context</h2>
          <p className="mt-1 text-sm text-[#6b7390]">This is the compact chart context Caspian would reason over.</p>
        </div>
        <button
          type="button"
          onClick={copyMarkdown}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm font-semibold text-[#4a5168] transition-colors hover:bg-[#f5f6fb]"
        >
          <Clipboard size={14} />
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="max-h-[560px] overflow-auto rounded-lg bg-[#101828] p-4 text-[12px] leading-relaxed text-[#f8fafc]">
        <code>{markdown}</code>
      </pre>
    </section>
  );
}

export function FhirContextLab() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<FhirContextLabPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const metrics = useMemo(() => {
    if (!result) return null;
    return [
      {
        label: "Raw estimate",
        value: `~${formatNumber(result.raw_token_estimate)}`,
        sublabel: "tokens in normalized uploaded FHIR",
      },
      {
        label: "Context estimate",
        value: `~${formatNumber(result.context_token_estimate)}`,
        sublabel: "tokens in Caspian context",
      },
      {
        label: "Compression",
        value: result.compression_ratio ? `${result.compression_ratio}x` : "-",
        sublabel: "raw estimate divided by context estimate",
      },
      {
        label: "Clinical facts",
        value: formatNumber(result.fact_count),
        sublabel: `${formatNumber(result.entry_count)} FHIR entries parsed`,
      },
    ];
  }, [result]);

  async function runPreview() {
    if (!file) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.previewFhirContext(file);
      setResult(response);
    } catch (err) {
      setResult(null);
      setError(errorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <article>
      <PageHeader
        eyebrow="Using Atlas"
        title="FHIR Context Lab"
        subtitle="Upload a FHIR package and inspect the compact clinical context Caspian builds before an agent sees the chart."
      />

      <div className="mb-6 rounded-xl border border-[#c7d8ff] bg-[#eef4ff] p-4">
        <p className="text-sm leading-relaxed text-[#34436a]">
          This page is a transparency workbench. It shows the transformation from raw FHIR to prompt-ready
          context, including token estimates, resource mix, section counts, and a lightweight trace. Uploaded
          files are processed for the preview and are not saved as patient workspaces.
        </p>
      </div>

      <UploadPanel file={file} isLoading={isLoading} onSelect={setFile} onSubmit={runPreview} />

      {error && (
        <div className="mt-5 flex gap-3 rounded-xl border border-[#f1bbc0] bg-[#fff0f1] p-4 text-sm text-[#7f2c32]">
          <AlertTriangle size={17} className="mt-0.5 shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {result && (
        <div className="mt-7 space-y-6">
          {result.warnings.length > 0 && (
            <div className="flex gap-3 rounded-xl border border-[#f3d692] bg-[#fff7e5] p-4 text-sm text-[#73521b]">
              <AlertTriangle size={17} className="mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold">Preview warnings</p>
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  {result.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          <section>
            <p className="mb-3 text-sm text-[#6b7390]">
              Source: <span className="font-medium text-[#1d2433]">{result.source_filename}</span>
              {" · "}
              Patient: <span className="font-medium text-[#1d2433]">{result.patient_summary}</span>
            </p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {metrics?.map((metric) => (
                <MetricTile key={metric.label} {...metric} />
              ))}
            </div>
          </section>

          <TraceSteps result={result} />

          <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <ResourceCounts result={result} />
            <SectionBreakdown result={result} />
          </div>

          <MarkdownPreview markdown={result.markdown} />
        </div>
      )}
    </article>
  );
}
