import { Fragment, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Award,
  BarChart3,
  CheckCircle2,
  Clock3,
  DatabaseZap,
  ExternalLink,
  FileCheck2,
  FolderOpen,
  Gauge,
  RefreshCw,
  Search,
  Server,
  XCircle,
} from "lucide-react";
import { api } from "../../api/client";
import type { PipelineLabLeaderboardResponse, PipelineLeaderboardRow, PipelineRunSummary } from "../../types";

const EMPTY_DATA: PipelineLabLeaderboardResponse = {
  generated_at: "",
  lab_roots: [],
  pipelines: [],
  recent_runs: [],
  evaluations: [],
  suites: [],
  test_criteria: [],
  test_pdfs: [],
  gold_standard: {
    pipeline_name: "multipass-fhir-gold",
    label: "Gold standard",
    definition: "",
    measurement: "",
    current_run_count: 0,
    latest_run_at: null,
    artifact_policy: "",
  },
  ground_truth: {
    definition: "",
    what_it_is_not: "",
    storage_policy: "",
    comparison_policy: "",
    creation_workflow: [],
    pdf_count: 0,
    versions: [],
  },
  totals: {
    registered_pipelines: 0,
    pipelines_with_runs: 0,
    run_count: 0,
    success_count: 0,
    failure_count: 0,
    eval_run_count: 0,
    suite_count: 0,
  },
};

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Pending";
  return `${Math.round(value * 100)}%`;
}

function formatDecimal(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "Pending";
  return value.toFixed(digits);
}

function formatMs(value: number | null | undefined): string {
  if (value === null || value === undefined || value <= 0) return "Pending";
  if (value >= 1000) return `${(value / 1000).toFixed(1)}s`;
  return `${value}ms`;
}

function formatCost(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Pending";
  if (value === 0) return "$0.00";
  return `$${value.toFixed(value < 0.01 ? 4 : 2)}`;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "Never";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function statusTone(status: string | null | undefined): string {
  if (status === "succeeded") return "border-[#b8eadf] bg-[#ecfbf7] text-[#0f766e]";
  if (status === "failed") return "border-[#ffd4c8] bg-[#fff1ed] text-[#b42318]";
  return "border-[#dfe4ea] bg-white text-[#667085]";
}

function architectureLabel(value: string): string {
  return value
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function metricLabel(metric: "qa" | "best" | "latest" | "speed" | "runs"): string {
  if (metric === "qa") return "Clinical QA";
  if (metric === "best") return "Best F1";
  if (metric === "latest") return "Latest F1";
  if (metric === "speed") return "Speed";
  return "Runs";
}

function sortRows(rows: PipelineLeaderboardRow[], metric: "qa" | "best" | "latest" | "speed" | "runs") {
  const copy = [...rows];
  if (metric === "qa") {
    return copy.sort((a, b) => (b.best_clinical_qa_score || -1) - (a.best_clinical_qa_score || -1));
  }
  if (metric === "speed") {
    return copy.sort((a, b) => (a.avg_latency_ms || Number.MAX_SAFE_INTEGER) - (b.avg_latency_ms || Number.MAX_SAFE_INTEGER));
  }
  if (metric === "latest") {
    return copy.sort((a, b) => (b.latest_weighted_f1 || -1) - (a.latest_weighted_f1 || -1));
  }
  if (metric === "runs") {
    return copy.sort((a, b) => b.run_count - a.run_count);
  }
  return copy.sort((a, b) => (b.best_weighted_f1 || -1) - (a.best_weighted_f1 || -1));
}

function resourceSummary(run: PipelineRunSummary): string {
  const entries = Object.entries(run.resource_counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);
  if (entries.length === 0) return `${run.total_entries} entries`;
  return entries.map(([key, count]) => `${count} ${key}`).join(", ");
}

function sortedResourceCounts(run: PipelineRunSummary | undefined): [string, number][] {
  if (!run) return [];
  return Object.entries(run.resource_counts).sort((a, b) => b[1] - a[1]);
}

function outputSummary(run: PipelineRunSummary | undefined): string {
  if (!run) return "No output";
  const observations = run.resource_counts.Observation || 0;
  const conditions = run.resource_counts.Condition || 0;
  const meds = run.resource_counts.MedicationRequest || 0;
  return `${run.total_entries} entries · ${observations} obs/labs · ${conditions} conditions · ${meds} meds`;
}

type SortDirection = "asc" | "desc";
type SortKey =
  | "name"
  | "description"
  | "architecture"
  | "output"
  | "runs"
  | "last_run"
  | "best_f1"
  | "best_qa"
  | "latest_f1"
  | "loinc"
  | "latency"
  | "cost"
  | "status";

interface SortState {
  key: SortKey;
  direction: SortDirection;
}

function defaultDirection(key: SortKey): SortDirection {
  return key === "name" || key === "architecture" || key === "status" ? "asc" : "desc";
}

function sortValue(row: PipelineLeaderboardRow, key: SortKey): string | number | null {
  const latestRun = row.recent_runs[0];
  if (key === "name") return row.name;
  if (key === "description") return row.description;
  if (key === "architecture") return architectureLabel(row.architecture);
  if (key === "output") return latestRun?.total_entries ?? null;
  if (key === "runs") return row.run_count;
  if (key === "last_run") return row.last_run_at ? new Date(row.last_run_at).getTime() : null;
  if (key === "best_f1") return row.best_weighted_f1;
  if (key === "best_qa") return row.best_clinical_qa_score;
  if (key === "latest_f1") return row.latest_weighted_f1;
  if (key === "loinc") return row.latest_loinc_resolution_rate;
  if (key === "latency") return row.avg_latency_ms;
  if (key === "cost") return row.avg_cost_usd ?? row.estimated_cost_per_pdf_usd;
  return row.last_status || "unknown";
}

function compareRows(a: PipelineLeaderboardRow, b: PipelineLeaderboardRow, sort: SortState): number {
  const aValue = sortValue(a, sort.key);
  const bValue = sortValue(b, sort.key);
  if (aValue === null && bValue === null) return a.name.localeCompare(b.name);
  if (aValue === null) return 1;
  if (bValue === null) return -1;

  let result: number;
  if (typeof aValue === "number" && typeof bValue === "number") {
    result = aValue - bValue;
  } else {
    result = String(aValue).localeCompare(String(bValue));
  }
  if (result === 0) result = a.name.localeCompare(b.name);
  return sort.direction === "asc" ? result : -result;
}

function SortHeader({
  label,
  sortKey,
  sort,
  onSort,
  align = "left",
}: {
  label: string;
  sortKey: SortKey;
  sort: SortState;
  onSort: (key: SortKey) => void;
  align?: "left" | "right";
}) {
  const active = sort.key === sortKey;
  const Icon = !active ? ArrowUpDown : sort.direction === "asc" ? ArrowUp : ArrowDown;
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      className={`flex w-full items-center gap-1.5 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#667085] hover:bg-[#e9edf2] hover:text-[#1c1c1e] ${
        align === "right" ? "justify-end text-right" : "justify-start text-left"
      }`}
    >
      <span>{label}</span>
      <Icon className={`h-3.5 w-3.5 ${active ? "text-[#5b76fe]" : "text-[#98a2b3]"}`} />
    </button>
  );
}

function StatChip({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5 border-r border-[#dfe4ea] pr-3 text-sm last:border-r-0 last:pr-0">
      <span className="text-xs font-semibold uppercase tracking-[0.08em] text-[#667085]">{label}</span>
      <span className="font-semibold text-[#1c1c1e]">{value}</span>
    </span>
  );
}

function StatusPill({ status }: { status: string | null | undefined }) {
  const Icon = status === "succeeded" ? CheckCircle2 : status === "failed" ? XCircle : AlertCircle;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${statusTone(status)}`}>
      <Icon className="h-3.5 w-3.5" />
      {status || "unknown"}
    </span>
  );
}

function ArtifactLinks({ run }: { run: PipelineRunSummary }) {
  const links = [
    ["PDF", run.artifact_urls.source_pdf],
    ["Bundle", run.artifact_urls.bundle],
    ["Eval", run.eval_artifact ? run.artifact_urls.eval : null],
    ["Shape", run.bundle_shape_artifact ? run.artifact_urls.bundle_shape : null],
  ].filter((item): item is [string, string] => Boolean(item[1]));

  return (
    <div className="flex flex-wrap gap-1.5">
      {links.map(([label, href]) => (
        <a
          key={label}
          href={href}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 rounded-md border border-[#dfe4ea] bg-white px-2 py-1 text-xs font-medium text-[#344054] hover:border-[#5b76fe] hover:text-[#4155d8]"
        >
          {label}
          <ExternalLink className="h-3 w-3" />
        </a>
      ))}
    </div>
  );
}

function PipelineTable({ rows, goldPipelineName }: { rows: PipelineLeaderboardRow[]; goldPipelineName: string }) {
  const [expandedPipeline, setExpandedPipeline] = useState<string | null>(null);
  const [sort, setSort] = useState<SortState>({ key: "best_qa", direction: "desc" });
  const sortedRows = useMemo(() => [...rows].sort((a, b) => compareRows(a, b, sort)), [rows, sort]);
  const handleSort = (key: SortKey) => {
    setSort((current) => {
      if (current.key === key) {
        return { key, direction: current.direction === "asc" ? "desc" : "asc" };
      }
      return { key, direction: defaultDirection(key) };
    });
  };

  return (
    <div className="overflow-hidden border border-[#d9dee5] bg-white">
      <div className="overflow-x-auto">
        <table className="min-w-[1440px] w-full border-collapse text-left text-xs">
          <thead className="bg-[#f3f5f7]">
            <tr>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="Pipeline" sortKey="name" sort={sort} onSort={handleSort} /></th>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="Description" sortKey="description" sort={sort} onSort={handleSort} /></th>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="Architecture" sortKey="architecture" sort={sort} onSort={handleSort} /></th>
              <th className="border-r border-b border-[#d9dee5] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#667085]">Backends</th>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="Output" sortKey="output" sort={sort} onSort={handleSort} /></th>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="Runs" sortKey="runs" sort={sort} onSort={handleSort} align="right" /></th>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="Last Run" sortKey="last_run" sort={sort} onSort={handleSort} /></th>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="Best F1" sortKey="best_f1" sort={sort} onSort={handleSort} align="right" /></th>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="Best QA" sortKey="best_qa" sort={sort} onSort={handleSort} align="right" /></th>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="Latest F1" sortKey="latest_f1" sort={sort} onSort={handleSort} align="right" /></th>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="LOINC" sortKey="loinc" sort={sort} onSort={handleSort} align="right" /></th>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="Latency" sortKey="latency" sort={sort} onSort={handleSort} align="right" /></th>
              <th className="border-r border-b border-[#d9dee5] p-0"><SortHeader label="Cost" sortKey="cost" sort={sort} onSort={handleSort} align="right" /></th>
              <th className="border-b border-[#d9dee5] p-0"><SortHeader label="Status" sortKey="status" sort={sort} onSort={handleSort} /></th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row) => {
              const isGold = row.name === goldPipelineName;
              const latestRun = row.recent_runs[0];
              const isExpanded = expandedPipeline === row.name;
              return (
                <Fragment key={row.name}>
                  <tr className={`align-top hover:bg-[#eef4ff] ${isGold ? "bg-[#fff8e6]" : "bg-white"}`}>
                    <td className="max-w-[220px] border-r border-b border-[#e4e7eb] px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2 font-semibold text-[#1c1c1e]">
                        {row.name}
                        {isGold && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-[#e6b84f] bg-[#fff3c4] px-2 py-0.5 text-xs font-semibold text-[#8a5a00]">
                            <Award className="h-3 w-3" />
                            Gold standard
                          </span>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => setExpandedPipeline(isExpanded ? null : row.name)}
                        className="mt-1 text-[11px] font-semibold text-[#5b76fe] hover:text-[#4155d8]"
                      >
                        {isExpanded ? "Hide output structure" : "View output structure"}
                      </button>
                    </td>
                    <td className="max-w-[260px] border-r border-b border-[#e4e7eb] px-3 py-2 text-xs leading-5 text-[#667085]">
                      <div className="line-clamp-3">{row.description || "Registered pipeline awaiting documentation."}</div>
                    </td>
                    <td className="border-r border-b border-[#e4e7eb] px-3 py-2 text-[#344054]">{architectureLabel(row.architecture)}</td>
                    <td className="border-r border-b border-[#e4e7eb] px-3 py-2">
                      <div className="flex max-w-[220px] flex-wrap gap-1.5">
                        {(row.primary_backends.length ? row.primary_backends : ["none"]).map((backend) => (
                          <span key={backend} className="rounded-md border border-[#dfe4ea] bg-white px-2 py-1 text-xs text-[#344054]">
                            {backend}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="border-r border-b border-[#e4e7eb] px-3 py-2 text-xs leading-5 text-[#344054]">{outputSummary(latestRun)}</td>
                    <td className="border-r border-b border-[#e4e7eb] px-3 py-2 text-right font-medium text-[#1c1c1e]">{row.run_count}</td>
                    <td className="border-r border-b border-[#e4e7eb] px-3 py-2 text-[#344054]">{formatDate(row.last_run_at)}</td>
                    <td className="border-r border-b border-[#e4e7eb] px-3 py-2 text-right font-medium text-[#1c1c1e]">{formatDecimal(row.best_weighted_f1)}</td>
                    <td className="border-r border-b border-[#e4e7eb] px-3 py-2 text-right font-medium text-[#1c1c1e]">{formatDecimal(row.best_clinical_qa_score)}</td>
                    <td className="border-r border-b border-[#e4e7eb] px-3 py-2 text-right text-[#344054]">{formatDecimal(row.latest_weighted_f1)}</td>
                    <td className="border-r border-b border-[#e4e7eb] px-3 py-2 text-right text-[#344054]">{formatPercent(row.latest_loinc_resolution_rate)}</td>
                    <td className="border-r border-b border-[#e4e7eb] px-3 py-2 text-right text-[#344054]">{formatMs(row.avg_latency_ms)}</td>
                    <td className="border-r border-b border-[#e4e7eb] px-3 py-2 text-right text-[#344054]">{formatCost(row.avg_cost_usd ?? row.estimated_cost_per_pdf_usd)}</td>
                    <td className="border-b border-[#e4e7eb] px-3 py-2"><StatusPill status={row.last_status} /></td>
                  </tr>
                  {isExpanded && (
                    <tr className={isGold ? "bg-[#fffdf5]" : "bg-[#fafbfc]"}>
                      <td colSpan={14} className="border-b border-[#d9dee5] px-3 py-3">
                        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
                          <div>
                            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                              <h3 className="text-sm font-semibold text-[#1c1c1e]">Latest output structure</h3>
                              {latestRun && <span className="text-xs text-[#667085]">{latestRun.pdf_label} · {latestRun.run_id}</span>}
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {sortedResourceCounts(latestRun).map(([resourceType, count]) => (
                                <span key={resourceType} className="rounded-md border border-[#dfe4ea] bg-white px-2.5 py-1.5 text-xs text-[#344054]">
                                  <span className="font-semibold text-[#1c1c1e]">{count}</span> {resourceType}
                                </span>
                              ))}
                              {!latestRun && <span className="text-sm text-[#667085]">No saved output bundle for this pipeline yet.</span>}
                            </div>
                            <div className="mt-3 grid gap-2 text-xs sm:grid-cols-4">
                              <div className="border-l border-[#dfe4ea] pl-3">
                                <div className="font-semibold text-[#1c1c1e]">{formatPercent(latestRun?.loinc_resolution_rate)}</div>
                                <div className="text-[#667085]">LOINC resolution</div>
                              </div>
                              <div className="border-l border-[#dfe4ea] pl-3">
                                <div className="font-semibold text-[#1c1c1e]">{formatPercent(latestRun?.patient_link_rate)}</div>
                                <div className="text-[#667085]">Patient linkage</div>
                              </div>
                              <div className="border-l border-[#dfe4ea] pl-3">
                                <div className="font-semibold text-[#1c1c1e]">{formatPercent(latestRun?.encounter_link_rate)}</div>
                                <div className="text-[#667085]">Encounter linkage</div>
                              </div>
                              <div className="border-l border-[#dfe4ea] pl-3">
                                <div className="font-semibold text-[#1c1c1e]">{latestRun?.trace_count ?? 0}</div>
                                <div className="text-[#667085]">Saved pass traces</div>
                              </div>
                            </div>
                          </div>
                          <div className="rounded-md border border-[#dfe4ea] bg-white p-3">
                            <div className="text-xs font-semibold uppercase tracking-[0.08em] text-[#667085]">Review artifacts</div>
                            <div className="mt-3">{latestRun ? <ArtifactLinks run={latestRun} /> : null}</div>
                            <p className="mt-3 text-xs leading-5 text-[#667085]">
                              Open the saved Bundle to inspect exact FHIR JSON. Labs currently appear as Observation resources; the next useful split is Observation category coverage by lab, vital, and note-derived findings.
                            </p>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={14} className="px-4 py-10 text-center text-sm text-[#667085]">
                  No pipelines match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RecentRunsTable({ runs }: { runs: PipelineRunSummary[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
      <div className="border-b border-[#edf0f2] px-4 py-3">
        <h2 className="text-base font-semibold text-[#1c1c1e]">Recent Runs</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[980px] w-full border-collapse text-left text-sm">
          <thead className="bg-[#f5f6f8] text-xs font-semibold uppercase tracking-[0.08em] text-[#667085]">
            <tr>
              <th className="px-4 py-3">Run</th>
              <th className="px-4 py-3">Pipeline</th>
              <th className="px-4 py-3">PDF</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Latency</th>
              <th className="px-4 py-3 text-right">F1</th>
              <th className="px-4 py-3">Resources</th>
              <th className="px-4 py-3">Artifacts</th>
              <th className="px-4 py-3">Root</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#edf0f2]">
            {runs.slice(0, 12).map((run) => (
              <tr key={`${run.lab_root}-${run.run_id}`} className="hover:bg-[#fafbfc]">
                <td className="px-4 py-3">
                  <div className="font-medium text-[#1c1c1e]">{run.run_id}</div>
                  <div className="mt-1 text-xs text-[#667085]">{formatDate(run.finished_at || run.started_at)}</div>
                </td>
                <td className="px-4 py-3 text-[#344054]">{run.pipeline_name}</td>
                <td className="px-4 py-3 text-[#344054]">{run.pdf_label}</td>
                <td className="px-4 py-3"><StatusPill status={run.status} /></td>
                <td className="px-4 py-3 text-right text-[#344054]">{formatMs(run.latency_ms)}</td>
                <td className="px-4 py-3 text-right font-medium text-[#1c1c1e]">{formatDecimal(run.weighted_f1)}</td>
                <td className="px-4 py-3 text-[#344054]">{resourceSummary(run)}</td>
                <td className="px-4 py-3"><ArtifactLinks run={run} /></td>
                <td className="px-4 py-3 text-[#667085]">{run.lab_root}</td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-sm text-[#667085]">
                  No lab runs have been recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type DetailPanel = "criteria" | "truth" | "gold" | "pdfs" | "cache" | null;

export function PipelineLab() {
  const [architecture, setArchitecture] = useState("all");
  const [metric, setMetric] = useState<"qa" | "best" | "latest" | "speed" | "runs">("qa");
  const [query, setQuery] = useState("");
  const [detailPanel, setDetailPanel] = useState<DetailPanel>(null);

  const { data = EMPTY_DATA, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["pipeline-lab", "leaderboard"],
    queryFn: api.getPipelineLabLeaderboard,
  });

  const architectures = useMemo(() => {
    const values = new Set(data.pipelines.map((pipeline) => pipeline.architecture || "unknown"));
    return ["all", ...Array.from(values).sort()];
  }, [data.pipelines]);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const filtered = data.pipelines.filter((pipeline) => {
      if (architecture !== "all" && pipeline.architecture !== architecture) return false;
      if (!normalizedQuery) return true;
      return [pipeline.name, pipeline.description, pipeline.architecture, ...pipeline.primary_backends]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery);
    });
    return sortRows(filtered, metric);
  }, [architecture, data.pipelines, metric, query]);

  const successRate = data.totals.run_count > 0 ? data.totals.success_count / data.totals.run_count : null;
  const topPipeline =
    filteredRows.find((row) => row.best_clinical_qa_score !== null) ||
    filteredRows.find((row) => row.best_weighted_f1 !== null) ||
    filteredRows[0];
  const setPanel = (panel: Exclude<DetailPanel, null>) => {
    setDetailPanel((current) => current === panel ? null : panel);
  };

  return (
    <main className="min-h-screen bg-[#f8fafc] p-3 sm:p-4">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-3">
        <header className="border-b border-[#dfe4ea] pb-3">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <h1 className="text-2xl font-semibold tracking-normal text-[#1c1c1e]">Pipeline Lab</h1>
                <span className="inline-flex items-center gap-1.5 text-sm font-medium text-[#5b76fe]">
                  <DatabaseZap className="h-4 w-4" />
                  PDF to FHIR experiments
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1.5">
                <StatChip label="Pipelines" value={`${data.totals.registered_pipelines}`} />
                <StatChip label="Runs" value={`${data.totals.run_count}`} />
                <StatChip label="Success" value={formatPercent(successRate)} />
                <StatChip label="QA Evals" value={`${data.totals.eval_run_count || 0}`} />
                <StatChip label="Suites" value={`${data.totals.suite_count}`} />
                <StatChip label="Leader" value={topPipeline ? `${formatDecimal(topPipeline.best_clinical_qa_score ?? topPipeline.best_weighted_f1)} ${topPipeline.name}` : "Pending"} />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                title="Show test criteria"
                onClick={() => setPanel("criteria")}
                className={`inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium ${
                  detailPanel === "criteria" ? "border-[#5b76fe] bg-[#eef1ff] text-[#4155d8]" : "border-[#cfd6dd] bg-white text-[#344054] hover:bg-[#f5f6f8]"
                }`}
              >
                <Gauge className="h-4 w-4" />
                Criteria
              </button>
              <button
                type="button"
                title="Show gold-standard definition"
                onClick={() => setPanel("gold")}
                className={`inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium ${
                  detailPanel === "gold" ? "border-[#e6b84f] bg-[#fff3c4] text-[#8a5a00]" : "border-[#cfd6dd] bg-white text-[#344054] hover:bg-[#f5f6f8]"
                }`}
              >
                <Award className="h-4 w-4" />
                Gold
              </button>
              <button
                type="button"
                title="Show ground-truth definition"
                onClick={() => setPanel("truth")}
                className={`inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium ${
                  detailPanel === "truth" ? "border-[#0f766e] bg-[#e7fbf7] text-[#0f766e]" : "border-[#cfd6dd] bg-white text-[#344054] hover:bg-[#f5f6f8]"
                }`}
              >
                <FileCheck2 className="h-4 w-4" />
                Truth
              </button>
              <button
                type="button"
                title="Show PDFs used for testing"
                onClick={() => setPanel("pdfs")}
                className={`inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium ${
                  detailPanel === "pdfs" ? "border-[#5b76fe] bg-[#eef1ff] text-[#4155d8]" : "border-[#cfd6dd] bg-white text-[#344054] hover:bg-[#f5f6f8]"
                }`}
              >
                <FolderOpen className="h-4 w-4" />
                PDFs
              </button>
              <button
                type="button"
                title="Show artifact cache"
                onClick={() => setPanel("cache")}
                className={`inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium ${
                  detailPanel === "cache" ? "border-[#5b76fe] bg-[#eef1ff] text-[#4155d8]" : "border-[#cfd6dd] bg-white text-[#344054] hover:bg-[#f5f6f8]"
                }`}
              >
                <Server className="h-4 w-4" />
                Cache
              </button>
              <button
                type="button"
                onClick={() => void refetch()}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-[#cfd6dd] bg-white px-3 text-sm font-medium text-[#344054] hover:bg-[#f5f6f8]"
              >
                <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
                Refresh
              </button>
            </div>
          </div>
        </header>

        {isError && (
          <div className="rounded-lg border border-[#ffd4c8] bg-[#fff1ed] px-4 py-3 text-sm text-[#b42318]">
            Pipeline Lab API is unavailable. Start FastAPI or check `/api/pipeline-lab/leaderboard`.
          </div>
        )}

        {detailPanel && (
          <section className={`border px-3 py-3 text-sm ${
            detailPanel === "gold" ? "border-[#e6b84f] bg-[#fff8e6]" : "border-[#dfe4ea] bg-white"
          }`}>
            {detailPanel === "criteria" && (
              <div>
                <div className="mb-2 flex items-center gap-2 font-semibold text-[#1c1c1e]">
                  <Gauge className="h-4 w-4 text-[#5b76fe]" />
                  Test criteria
                </div>
                <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                  {data.test_criteria.map((criterion) => (
                    <div key={criterion.key} className="border-l border-[#dfe4ea] pl-3">
                      <div className="font-medium text-[#1c1c1e]">{criterion.label}</div>
                      <div className="mt-1 text-xs leading-5 text-[#667085]">{criterion.measurement}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {detailPanel === "gold" && (
              <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px]">
                <div>
                  <div className="mb-1 flex items-center gap-2 font-semibold text-[#8a5a00]">
                    <Award className="h-4 w-4" />
                    {data.gold_standard.label}
                  </div>
                  <p className="leading-6 text-[#6f4a00]">{data.gold_standard.definition}</p>
                  <p className="mt-1 text-xs leading-5 text-[#7a5a16]">{data.gold_standard.measurement}</p>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-[#7a5a16] lg:grid-cols-1">
                  <StatChip label="Runs" value={`${data.gold_standard.current_run_count}`} />
                  <StatChip label="Latest" value={formatDate(data.gold_standard.latest_run_at)} />
                </div>
              </div>
            )}

            {detailPanel === "truth" && (
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
                <div>
                  <div className="mb-2 flex items-center gap-2 font-semibold text-[#0f766e]">
                    <FileCheck2 className="h-4 w-4" />
                    Ground truth
                  </div>
                  <p className="leading-6 text-[#344054]">{data.ground_truth.definition}</p>
                  <p className="mt-2 leading-6 text-[#344054]">{data.ground_truth.what_it_is_not}</p>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <div className="border-l border-[#b8eadf] pl-3">
                      <div className="font-semibold text-[#1c1c1e]">Comparison rule</div>
                      <p className="mt-1 text-xs leading-5 text-[#667085]">{data.ground_truth.comparison_policy}</p>
                    </div>
                    <div className="border-l border-[#b8eadf] pl-3">
                      <div className="font-semibold text-[#1c1c1e]">Storage rule</div>
                      <p className="mt-1 text-xs leading-5 text-[#667085]">{data.ground_truth.storage_policy}</p>
                    </div>
                  </div>
                </div>
                <div>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div className="font-semibold text-[#1c1c1e]">Versioned truth sets</div>
                    <span className="text-xs font-medium text-[#667085]">{data.ground_truth.pdf_count} PDFs</span>
                  </div>
                  <div className="max-h-64 overflow-y-auto border border-[#dfe4ea] bg-white">
                    {data.ground_truth.versions.map((truth) => (
                      <div key={truth.ground_truth_path} className="border-b border-[#edf0f2] px-3 py-2 last:border-b-0">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="truncate font-medium text-[#1c1c1e]">{truth.pdf_label}</div>
                            <div className="mt-1 text-xs text-[#667085]">
                              v{truth.latest_version} · {truth.total_entries} facts · {truth.pdf_sha_prefix}
                            </div>
                          </div>
                          <code className="shrink-0 bg-[#f5f6f8] px-1.5 py-1 text-[11px] text-[#667085]">v{truth.latest_version}</code>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {Object.entries(truth.resource_counts)
                            .sort((a, b) => b[1] - a[1])
                            .slice(0, 5)
                            .map(([type, count]) => (
                              <span key={type} className="rounded border border-[#dfe4ea] px-1.5 py-0.5 text-[11px] text-[#344054]">
                                {count} {type}
                              </span>
                            ))}
                        </div>
                      </div>
                    ))}
                    {data.ground_truth.versions.length === 0 && (
                      <div className="px-3 py-6 text-center text-xs text-[#667085]">
                        No reviewed ground-truth bundles have been saved yet.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {detailPanel === "pdfs" && (
              <div>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 font-semibold text-[#1c1c1e]">
                    <FolderOpen className="h-4 w-4 text-[#5b76fe]" />
                    PDFs used for testing
                  </div>
                  <span className="text-xs font-medium text-[#667085]">{data.test_pdfs.length} PDFs</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-[760px] w-full border-collapse text-left text-xs">
                    <thead className="border-b border-[#edf0f2] font-semibold uppercase tracking-[0.08em] text-[#667085]">
                      <tr>
                        <th className="py-2 pr-3">PDF</th>
                        <th className="py-2 pr-3">SHA</th>
                        <th className="py-2 pr-3 text-right">Runs</th>
                        <th className="py-2 pr-3 text-right">Pipelines</th>
                        <th className="py-2 pr-3">Ground Truth</th>
                        <th className="py-2">Latest</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#edf0f2]">
                      {data.test_pdfs.map((pdf) => (
                        <tr key={`${pdf.pdf_sha256}-${pdf.original_path}`}>
                          <td className="max-w-[340px] py-2 pr-3">
                            <div className="font-medium text-[#1c1c1e]">{pdf.pdf_label}</div>
                            <div className="truncate text-[#667085]">{pdf.original_path}</div>
                          </td>
                          <td className="py-2 pr-3 font-mono text-[#667085]">{pdf.pdf_sha256?.slice(0, 12) || "unknown"}</td>
                          <td className="py-2 pr-3 text-right font-medium text-[#1c1c1e]">{pdf.run_count}</td>
                          <td className="py-2 pr-3 text-right text-[#344054]">{pdf.pipeline_count}</td>
                          <td className="py-2 pr-3 text-[#344054]">{pdf.has_ground_truth ? "Available" : "Not attached"}</td>
                          <td className="py-2 text-[#344054]">{formatDate(pdf.latest_run_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {detailPanel === "cache" && (
              <div className="grid gap-3 lg:grid-cols-[280px_minmax(0,1fr)]">
                <div>
                  <div className="mb-2 flex items-center gap-2 font-semibold text-[#1c1c1e]">
                    <Server className="h-4 w-4 text-[#5b76fe]" />
                    Artifact cache
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {data.lab_roots.map((root) => (
                      <code key={root} className="bg-[#f5f6f8] px-2 py-1.5 text-xs text-[#344054]">{root}</code>
                    ))}
                  </div>
                </div>
                <p className="text-sm leading-6 text-[#667085]">
                  Each run stores the source PDF, manifest, output bundle, bundle-shape metrics, optional eval metrics, optional ground truth, and pass traces when logged. Use the recent-run artifact links to inspect saved outputs.
                </p>
              </div>
            )}
          </section>
        )}

        <section className="border border-[#dfe4ea] bg-white px-3 py-2">
          <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-[#5b76fe]" />
              <h2 className="text-sm font-semibold text-[#1c1c1e]">Leaderboard</h2>
              <span className="text-xs text-[#667085]">Sorted by {metricLabel(metric).toLowerCase()}</span>
            </div>
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
              <label className="relative block min-w-[240px]">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#98a2b3]" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  className="h-10 w-full rounded-md border border-[#cfd6dd] bg-white pl-9 pr-3 text-sm text-[#1c1c1e] outline-none focus:border-[#5b76fe] focus:ring-2 focus:ring-[#dfe5ff]"
                  placeholder="Search pipelines or backends"
                />
              </label>
              <select
                value={architecture}
                onChange={(event) => setArchitecture(event.target.value)}
                className="h-10 rounded-md border border-[#cfd6dd] bg-white px-3 text-sm font-medium text-[#344054] outline-none focus:border-[#5b76fe] focus:ring-2 focus:ring-[#dfe5ff]"
              >
                {architectures.map((item) => (
                  <option key={item} value={item}>
                    {item === "all" ? "All architectures" : architectureLabel(item)}
                  </option>
                ))}
              </select>
              <select
                value={metric}
                onChange={(event) => setMetric(event.target.value as typeof metric)}
                className="h-10 rounded-md border border-[#cfd6dd] bg-white px-3 text-sm font-medium text-[#344054] outline-none focus:border-[#5b76fe] focus:ring-2 focus:ring-[#dfe5ff]"
              >
                <option value="qa">Clinical QA</option>
                <option value="best">Best F1</option>
                <option value="latest">Latest F1</option>
                <option value="speed">Speed</option>
                <option value="runs">Runs</option>
              </select>
            </div>
          </div>
        </section>

        {isLoading ? (
          <div className="flex h-72 items-center justify-center rounded-lg border border-[#dfe4ea] bg-white">
            <div className="flex items-center gap-3 text-sm text-[#667085]">
              <RefreshCw className="h-4 w-4 animate-spin" />
              Loading pipeline artifacts
            </div>
          </div>
        ) : (
          <PipelineTable rows={filteredRows} goldPipelineName={data.gold_standard.pipeline_name} />
        )}

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <RecentRunsTable runs={data.recent_runs} />
          <div className="rounded-lg border border-[#dfe4ea] bg-white">
            <div className="border-b border-[#edf0f2] px-4 py-3">
              <h2 className="text-base font-semibold text-[#1c1c1e]">Suite History</h2>
            </div>
            <div className="divide-y divide-[#edf0f2]">
              {data.suites.slice(0, 8).map((suite) => {
                const suiteRate = suite.cell_count > 0 ? suite.succeeded / suite.cell_count : null;
                return (
                  <div key={`${suite.root}-${suite.suite_run_id}`} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium text-[#1c1c1e]">{suite.suite_name}</p>
                        <p className="mt-1 text-xs text-[#667085]">{suite.suite_run_id}</p>
                      </div>
                      <span className="rounded-md bg-[#f5f6f8] px-2 py-1 text-xs font-medium text-[#344054]">
                        {formatPercent(suiteRate)}
                      </span>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
                      <div className="rounded-md bg-[#f8fafc] p-2">
                        <div className="text-xs text-[#667085]">Cells</div>
                        <div className="font-semibold text-[#1c1c1e]">{suite.cell_count}</div>
                      </div>
                      <div className="rounded-md bg-[#ecfbf7] p-2">
                        <div className="text-xs text-[#0f766e]">Passed</div>
                        <div className="font-semibold text-[#0f766e]">{suite.succeeded}</div>
                      </div>
                      <div className="rounded-md bg-[#fff1ed] p-2">
                        <div className="text-xs text-[#b42318]">Failed</div>
                        <div className="font-semibold text-[#b42318]">{suite.failed}</div>
                      </div>
                    </div>
                    <div className="mt-3 flex items-center gap-2 text-xs text-[#667085]">
                      <Clock3 className="h-3.5 w-3.5" />
                      {formatDate(suite.created_at)}
                    </div>
                  </div>
                );
              })}
              {data.suites.length === 0 && (
                <div className="p-8 text-center text-sm text-[#667085]">
                  Suite results will appear after running `python -m lib.extract.lab suite`.
                </div>
              )}
            </div>
          </div>
        </section>

      </div>
    </main>
  );
}
