import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  FileText,
  FileUp,
  Inbox,
  Layers3,
  Link2,
  Loader2,
  Pill,
  PlayCircle,
  ShieldAlert,
  Sparkles,
  Stethoscope,
  Syringe,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../../api/client";
import type {
  HarmonizeMergedAllergy,
  HarmonizeMergedCondition,
  HarmonizeMergedImmunization,
  HarmonizeMergedMedication,
  HarmonizeMergedObservation,
  HarmonizeLatestObservation,
  HarmonizeProvenanceResponse,
  HarmonizeCanonicalSelection,
  HarmonizeCanonicalSelectionLatest,
  HarmonizeRunReviewItem,
  HarmonizeObservationSource,
  HarmonizeClinicalNote,
  HarmonizeClinicalArtifact,
  HarmonizeReviewDecisionPayload,
} from "../../types";
import { formatDisplayNumber, formatMeasurement } from "../../utils/format";
import { PatientContextPanels } from "./PatientContextPanels";

type ResourceTab =
  | "labs"
  | "conditions"
  | "medications"
  | "allergies"
  | "immunizations";

type WorkspaceTab =
  | "record"
  | "review"
  | "sources"
  | "provenance";

type ReviewDecision = HarmonizeReviewDecisionPayload["decision"];

function cls(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

function safeUploadSessionId(value: string): string {
  return value.replace(/[^A-Za-z0-9_.-]+/g, "-").replace(/^[.-]+|[.-]+$/g, "").slice(0, 120) || "patient";
}

/** Source kind → small badge label/color. */
function kindBadge(kind: string): { label: string; color: string } {
  if (kind === "fhir-pull") return { label: "FHIR pull", color: "bg-emerald-100 text-emerald-800" };
  if (kind === "extracted-pdf") return { label: "PDF extraction", color: "bg-amber-100 text-amber-800" };
  if (kind === "ccda-xml") return { label: "C-CDA", color: "bg-sky-100 text-sky-800" };
  return { label: kind, color: "bg-slate-100 text-slate-700" };
}

function sourceStatusClass(status: string): string {
  if (status === "structured" || status === "extracted") return "bg-emerald-100 text-emerald-800";
  if (status === "pending_extraction") return "bg-amber-100 text-amber-800";
  if (status === "empty_extraction" || status === "unparsed_structured") return "bg-amber-100 text-amber-800";
  if (status === "identity_mismatch") return "bg-red-50 text-red-700";
  return "bg-red-50 text-red-700";
}

function reviewDateLabel(value: string | null | undefined): string {
  if (!value) return "No date";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function reviewValueLabel(value: number | null, unit: string | null, rawValue?: number | null, rawUnit?: string | null): string {
  const displayValue = value ?? rawValue;
  const displayUnit = unit ?? rawUnit ?? "";
  if (displayValue == null) return "No numeric value";
  return formatMeasurement(displayValue, displayUnit);
}

function canonicalSelectionValueLabel(value: HarmonizeCanonicalSelectionLatest | null | undefined): string {
  if (!value) return "No selected value";
  if (value.value == null) return "No selected value";
  return formatMeasurement(value.value, value.unit);
}

function sourceMatchesLatest(
  source: HarmonizeObservationSource,
  latest: HarmonizeLatestObservation | null,
): boolean {
  if (!latest) return false;
  const sourceValue = source.value ?? source.raw_value;
  const latestValue = latest.value;
  return (
    sourceValue === latestValue &&
    source.source_label === latest.source_label &&
    source.effective_date === latest.effective_date
  );
}

function conflictSpreadLabel(
  sources: HarmonizeObservationSource[],
  canonicalUnit: string | null,
): string | null {
  const values = sources
    .map((source) => source.value ?? source.raw_value)
    .filter((value): value is number => typeof value === "number");
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return null;
  const unit = canonicalUnit ?? sources.find((source) => source.unit || source.raw_unit)?.unit ?? sources.find((source) => source.raw_unit)?.raw_unit ?? "";
  return `${formatDisplayNumber(min)}-${formatDisplayNumber(max)}${unit ? ` ${unit}` : ""}`;
}

function reviewDecisionLabel(decision: string | null): string {
  if (decision === "accepted") return "Accepted candidate";
  if (decision === "dismissed") return "Dismissed";
  if (decision === "source_fixed") return "Source fixed";
  if (decision === "overridden") return "Alternate applied";
  if (decision === "kept_separate") return "Kept separate";
  if (decision === "deferred") return "Deferred";
  return "Decision saved";
}

function reviewDecisionSummaryLabel(decisions: Record<string, number>): string {
  const parts = Object.entries(decisions)
    .filter(([, count]) => count > 0)
    .map(([decision, count]) => `${count} ${reviewDecisionLabel(decision).toLowerCase()}`);
  return parts.length ? parts.join(" · ") : "No saved decisions yet";
}

function shortReference(value: string | null | undefined): string {
  if (!value) return "No technical reference";
  const [resourceType, id] = value.split("/");
  if (!id) return value;
  return `${resourceType}/${id.slice(0, 10)}…`;
}

type ContributionTimelineEvent = {
  id: string;
  date: string;
  kind: string;
  primary: string;
  secondary: string;
  tone: "blue" | "red" | "purple" | "amber" | "teal" | "slate";
};

type ContributionTimelineCluster = {
  key: string;
  date: string;
  events: ContributionTimelineEvent[];
};

function matchingContributionSources<T extends { document_reference: string | null }>(
  sources: T[],
  documentReference: string,
): T[] {
  const matched = sources.filter((source) => source.document_reference === documentReference);
  return matched.length > 0 ? matched : sources;
}

function contributionEventTimestamp(value: string): number {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
}

function contributionEventDayKey(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toISOString().slice(0, 10);
}

function groupContributionTimeline(events: ContributionTimelineEvent[]): ContributionTimelineCluster[] {
  const clusters = new Map<string, ContributionTimelineCluster>();

  events.forEach((event) => {
    const key = contributionEventDayKey(event.date);
    const existing = clusters.get(key);
    if (existing) {
      existing.events.push(event);
      return;
    }
    clusters.set(key, { key, date: event.date, events: [event] });
  });

  return Array.from(clusters.values())
    .map((cluster) => ({
      ...cluster,
      events: cluster.events.sort((a, b) => contributionEventTimestamp(b.date) - contributionEventTimestamp(a.date)),
    }))
    .sort((a, b) => contributionEventTimestamp(b.date) - contributionEventTimestamp(a.date));
}

function timelineToneClass(tone: ContributionTimelineEvent["tone"]): string {
  if (tone === "red") return "bg-red-50 text-red-700";
  if (tone === "purple") return "bg-violet-50 text-violet-700";
  if (tone === "amber") return "bg-amber-50 text-amber-800";
  if (tone === "teal") return "bg-teal-50 text-teal-700";
  if (tone === "blue") return "bg-blue-50 text-blue-700";
  return "bg-slate-100 text-slate-700";
}

function artifactActorLabel(artifact: HarmonizeClinicalArtifact): string {
  return (
    artifact.provider ||
    artifact.service_provider ||
    artifact.site ||
    artifact.performer_organization_labels[0] ||
    artifact.performer_practitioner_labels[0] ||
    artifact.performer_labels[0] ||
    artifact.source_label ||
    "Source record"
  );
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <div className="rounded-[10px] border border-line-1 bg-surface-1 px-3 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-3">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink-1">{value}</p>
      {detail && <p className="mt-1 text-xs leading-5 text-ink-3">{detail}</p>}
    </div>
  );
}

const workspaceTabs: {
  id: WorkspaceTab;
  label: string;
  description: string;
  icon: LucideIcon;
}[] = [
  {
    id: "record",
    label: "Merged record",
    description: "Inspect canonical facts by resource type.",
    icon: Layers3,
  },
  {
    id: "review",
    label: "Review blockers",
    description: "Resolve source issues and fact conflicts.",
    icon: AlertTriangle,
  },
  {
    id: "sources",
    label: "Source evidence",
    description: "See what each source contributed to the record.",
    icon: FileText,
  },
  {
    id: "provenance",
    label: "Provenance",
    description: "Trace each merged fact back to its source edges.",
    icon: Link2,
  },
];

function reviewSeverityClass(severity: HarmonizeRunReviewItem["severity"]): string {
  if (severity === "high") return "border-critical-line bg-critical-tint text-critical";
  if (severity === "medium") return "border-caution-line bg-caution-tint text-caution";
  return "border-line-1 bg-surface-1 text-ink-3";
}

function reviewCategoryLabel(item: HarmonizeRunReviewItem): string {
  return item.category === "fact" ? "Fact conflict" : "Source issue";
}

function WorkspaceTabs({
  active,
  onChange,
  meta,
}: {
  active: WorkspaceTab;
  onChange: (tab: WorkspaceTab) => void;
  meta?: Partial<Record<WorkspaceTab, string>>;
}) {
  return (
    <div className="rounded-[10px] border border-line-1 bg-surface-0 p-2 shadow-[var(--shadow-1)]">
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {workspaceTabs.map((item) => {
          const Icon = item.icon;
          const selected = active === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={cls(
                "rounded-[10px] border px-3 py-3 text-left transition-colors",
                selected
                  ? "border-action-line bg-action-tint text-action"
                  : "border-line-1 bg-surface-0 text-ink-3 hover:bg-surface-1 hover:text-ink-1",
              )}
            >
              <div className="flex items-start gap-3">
                <div className={cls(
                  "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px]",
                  selected ? "bg-surface-0 text-action" : "bg-surface-1 text-ink-3",
                )}>
                  <Icon size={14} />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold">{item.label}</p>
                    {meta?.[item.id] && (
                      <span className={cls(
                        "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em]",
                        selected ? "bg-surface-0 text-action" : "bg-surface-1 text-ink-3",
                      )}>
                        {meta[item.id]}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs leading-5 text-ink-3">{item.description}</p>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SourcesPanel({
  collectionId,
  canExtract = false,
  extractInProgress = false,
  onExtract,
}: {
  collectionId: string;
  canExtract?: boolean;
  extractInProgress?: boolean;
  onExtract?: () => void;
}) {
  const [selectedDocRef, setSelectedDocRef] = useState<string | null>(null);
  const [selectedSourceLabel, setSelectedSourceLabel] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["harmonize-sources", collectionId],
    queryFn: () => api.getHarmonizeSources(collectionId),
    enabled: !!collectionId,
  });
  const diffQuery = useQuery({
    queryKey: ["harmonize-source-diff", collectionId],
    queryFn: () => api.getHarmonizeSourceDiff(collectionId),
    enabled: !!collectionId,
  });

  if (isLoading) return <p className="text-sm text-[#667085]">Loading sources…</p>;
  if (error || !data) return <p className="text-sm text-red-700">Couldn't load sources.</p>;

  const diffByLabel = new Map(
    (diffQuery.data?.sources ?? []).map((s) => [s.label, s]),
  );
  const staged = data.sources.length;
  const structured = data.sources.filter((s) => s.status === "structured").length;
  const extracted = data.sources.filter((s) => s.status === "extracted").length;
  const pending = data.sources.filter((s) => s.status === "pending_extraction").length;
  const failures = data.sources.filter((s) => s.status === "missing" || s.status === "identity_mismatch").length;
  const sourceContributions = diffQuery.data?.sources.reduce(
    (sum, source) => sum + source.totals.unique.all + source.totals.shared.all,
    0,
  ) ?? 0;

  return (
    <div className="rounded-lg border border-[#dfe4ea] bg-white p-4">
      <div className="mb-4 rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] px-3 py-2.5">
        <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["Files staged", staged, "Sources in collection"],
            ["Structured", structured, "FHIR-like ready"],
            ["Prepared PDFs", extracted, "Candidate facts"],
            ["Needs prep", pending, "Waiting on extraction"],
            ["Contributions", diffQuery.isLoading ? "…" : sourceContributions, `${failures} source issues`],
          ].map(([label, value, detail]) => (
            <div key={label} className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">{label}</p>
              <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{value}</p>
              <p className="mt-0.5 truncate text-xs text-[#8d92a3]">{detail}</p>
            </div>
          ))}
        </div>
      </div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-[#5b76fe]" />
          <h3 className="text-sm font-semibold text-[#1c1c1e]">
            Sources in this collection
          </h3>
          <span className="ml-2 text-xs text-[#a5a8b5]">
            (click a row to see what it contributed)
          </span>
        </div>
        {canExtract && pending > 0 && onExtract && (
          <button
            type="button"
            disabled={extractInProgress}
            onClick={onExtract}
            className={cls(
              "inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              extractInProgress
                ? "bg-[#dfe4ea] text-[#667085]"
                : "bg-[#5b76fe] text-white hover:bg-[#4760e8]",
            )}
          >
            {extractInProgress ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Preparing…
              </>
            ) : (
              <>
                <Sparkles size={14} /> Prepare pending sources
              </>
            )}
          </button>
        )}
      </div>
      <div className="overflow-x-auto rounded-lg border border-[#dfe4ea]">
        <table className="w-full text-sm">
          <thead className="bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
            <tr>
              <th className="px-4 py-2">Source</th>
              <th className="px-4 py-2 hidden sm:table-cell">Kind</th>
              <th className="px-4 py-2 hidden md:table-cell">Status</th>
              <th
                className="px-4 py-2 text-right"
                title="Facts only this source contributed — the high-signal set"
              >
                Unique
              </th>
              <th
                className="px-4 py-2 text-right hidden md:table-cell"
                title="Facts shared with at least one other source"
              >
                Shared
              </th>
              <th className="px-4 py-2 text-right hidden lg:table-cell">Total raw</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eef0f4] bg-white">
            {data.sources.map((s) => {
              const badge = kindBadge(s.kind);
              const clickable = !!s.document_reference;
              const isSelected =
                clickable && selectedDocRef === s.document_reference;
              const diff = diffByLabel.get(s.label);
              const unique = diff?.totals.unique.all ?? 0;
              const shared = diff?.totals.shared.all ?? 0;
              return (
                <tr
                  key={s.id}
                  onClick={() => {
                    if (!clickable) return;
                    if (isSelected) {
                      setSelectedDocRef(null);
                      setSelectedSourceLabel(null);
                    } else {
                      setSelectedDocRef(s.document_reference);
                      setSelectedSourceLabel(s.label);
                    }
                  }}
                  className={cls(
                    !s.available && "opacity-50",
                    clickable && "cursor-pointer hover:bg-[#f7f9fc]",
                    isSelected && "bg-[#eef2ff]",
                  )}
                >
                  <td className="px-4 py-2 font-medium text-[#1c1c1e]">{s.label}</td>
                  <td className="px-4 py-2 hidden sm:table-cell">
                    <span
                      className={cls(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        badge.color,
                      )}
                    >
                      {badge.label}
                    </span>
                  </td>
                  <td className="px-4 py-2 hidden md:table-cell">
                    <span className={cls("rounded-full px-2 py-0.5 text-xs font-medium", sourceStatusClass(s.status))}>
                      {s.status_label || s.status.replace("_", " ")}
                    </span>
                  </td>
                  <td
                    className={cls(
                      "px-4 py-2 text-right tabular-nums",
                      unique > 0 ? "font-semibold text-[#5b76fe]" : "text-[#a5a8b5]",
                    )}
                  >
                    {diffQuery.isLoading ? "…" : unique}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[#667085] hidden md:table-cell">
                    {diffQuery.isLoading ? "…" : shared}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[#a5a8b5] hidden lg:table-cell">
                    {s.total_resources}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {selectedDocRef && (
        <ContributionsPanel
          collectionId={collectionId}
          documentReference={selectedDocRef}
          uniqueDiff={
            selectedSourceLabel
              ? diffByLabel.get(selectedSourceLabel) ?? null
              : null
          }
          onClose={() => {
            setSelectedDocRef(null);
            setSelectedSourceLabel(null);
          }}
        />
      )}
    </div>
  );
}

function ReviewQueuePanel({
  collectionId,
  patientId,
}: {
  collectionId: string;
  patientId?: string | null;
}) {
  const queryClient = useQueryClient();
  const sourcesQuery = useQuery({
    queryKey: ["harmonize-sources", collectionId],
    queryFn: () => api.getHarmonizeSources(collectionId),
    enabled: !!collectionId,
  });
  const observationsQuery = useQuery({
    queryKey: ["harmonize-observations", collectionId, "review"],
    queryFn: () => api.getHarmonizeObservations(collectionId, false),
    enabled: !!collectionId,
  });
  const latestRunQuery = useQuery({
    queryKey: ["harmonize-run-latest", collectionId],
    queryFn: () => api.getLatestHarmonizationRun(collectionId),
    enabled: !!collectionId,
  });
  const resolveMutation = useMutation({
    mutationFn: ({
      runId,
      item,
      decision,
      notes,
      selectedSourceRef,
    }: {
      runId: string;
      item: HarmonizeRunReviewItem;
      decision: ReviewDecision;
      notes: string;
      selectedSourceRef?: string | null;
    }) =>
      api.resolveHarmonizationReviewItem(collectionId, runId, {
        item_id: item.id,
        decision,
        notes,
        selected_source_ref: selectedSourceRef ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["harmonize-run-latest", collectionId] });
    },
  });

  const latestRun = latestRunQuery.data?.latest_run ?? null;
  const sources = sourcesQuery.data?.sources ?? [];
  const sourceIssues = sources.filter(
    (source) =>
      source.status !== "structured" &&
      source.status !== "extracted",
  );
  const openRunItems = useMemo(
    () => latestRun?.review_items.filter((item) => !item.resolved) ?? [],
    [latestRun?.review_items],
  );
  const resolvedRunItems = useMemo(
    () => latestRun?.review_items.filter((item) => item.resolved) ?? [],
    [latestRun?.review_items],
  );
  const labConflicts = openRunItems.filter(
    (item) => item.category === "fact" && item.resource_type === "Observation",
  ).length;
  const crossSourceLabs = observationsQuery.data?.cross_source ?? 0;
  const reviewItems = latestRun ? openRunItems.length : sourceIssues.length + (
    observationsQuery.data?.merged.filter((item) => item.has_conflict).length ?? 0
  );
  const isLoading = sourcesQuery.isLoading || observationsQuery.isLoading || latestRunQuery.isLoading;
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  const matchingObservation = (item: HarmonizeRunReviewItem) =>
    item.merged_ref
      ? observationsQuery.data?.merged.find((obs) => obs.merged_ref === item.merged_ref) ?? null
      : null;

  const sourceLabel = (item: HarmonizeRunReviewItem) =>
    item.source_id ? sources.find((source) => source.id === item.source_id)?.label ?? item.source_id : null;

  const resolveItem = (
    item: HarmonizeRunReviewItem,
    decision: ReviewDecision,
    notes: string,
    selectedSourceRef?: string | null,
  ) => {
    if (!latestRun) return;
    resolveMutation.mutate({ runId: latestRun.run_id, item, decision, notes, selectedSourceRef });
  };

  useEffect(() => {
    if (openRunItems.length === 0) {
      if (selectedItemId !== null) setSelectedItemId(null);
      return;
    }
    if (!selectedItemId || !openRunItems.some((item) => item.id === selectedItemId)) {
      setSelectedItemId(openRunItems[0].id);
    }
  }, [openRunItems, selectedItemId]);

  const activeItem = openRunItems.find((item) => item.id === selectedItemId) ?? openRunItems[0] ?? null;
  const activeObservation = activeItem ? matchingObservation(activeItem) : null;
  const activeSourceLabel = activeItem ? sourceLabel(activeItem) : null;
  const activeRecommended = activeObservation?.latest ?? null;
  const activeSpread = activeObservation
    ? conflictSpreadLabel(activeObservation.sources, activeObservation.canonical_unit)
    : null;

  return (
    <section className="rounded-[10px] border border-line-1 bg-surface-0 p-4 shadow-[var(--shadow-1)]">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            {reviewItems > 0 ? (
              <AlertTriangle size={16} className="text-caution" />
            ) : (
              <CheckCircle2 size={16} className="text-clear" />
            )}
            <h2 className="text-sm font-semibold text-ink-1">Review blockers</h2>
          </div>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-ink-3">
            Review is the final human gate before publish. Fix source-preparation issues, resolve conflicting fact
            candidates, and leave the run with an explicit audit trail.
          </p>
        </div>
        <div className="grid min-w-full gap-2 sm:grid-cols-3 lg:min-w-[520px]">
          <MetricCard
            label="Open blockers"
            value={isLoading ? "…" : reviewItems}
            detail="Issues that must be reviewed before publish"
          />
          <MetricCard
            label="Lab conflicts"
            value={isLoading ? "…" : labConflicts}
            detail="Same-day value spread"
          />
          <MetricCard
            label="Shared facts"
            value={isLoading ? "…" : crossSourceLabs}
            detail="Cross-source evidence"
          />
        </div>
      </div>
      {!isLoading && !latestRun && (
        <div className="mt-4 rounded-[10px] border border-line-1 bg-surface-1 px-4 py-4 text-sm leading-6 text-ink-3">
          Run harmonization first. The review workspace is populated from the persisted run artifact so each decision
          can be carried into Publish Chart with the exact candidate set that was reviewed.
        </div>
      )}
      {!isLoading && latestRun && openRunItems.length === 0 && (
        <div className="mt-4 rounded-[10px] border border-clear-line bg-clear-tint px-4 py-4 text-sm text-clear">
          <span className="font-semibold">No open review items.</span>{" "}
          This run can move to Publish Chart when you are ready to activate it downstream.
          {resolvedRunItems.length > 0 && (
            <span className="ml-1">
              {resolvedRunItems.length} prior decision
              {resolvedRunItems.length === 1 ? "" : "s"} saved on this run.
            </span>
          )}
        </div>
      )}
      {!isLoading && latestRun && activeItem && (
        <div className="mt-4 grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="rounded-[10px] border border-line-1 bg-surface-1 p-2">
            <div className="border-b border-line-1 px-2 py-2">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">Queue</p>
              <p className="mt-1 text-sm text-ink-3">{openRunItems.length} item{openRunItems.length === 1 ? "" : "s"} need a decision.</p>
            </div>
            <div className="space-y-2 p-2">
              {openRunItems.map((item, index) => {
                const observation = matchingObservation(item);
                const label = sourceLabel(item);
                const selected = item.id === activeItem.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setSelectedItemId(item.id)}
                    className={cls(
                      "w-full rounded-[10px] border px-3 py-3 text-left transition-colors",
                      selected ? "border-action-line bg-action-tint" : "border-line-1 bg-surface-0 hover:bg-surface-1",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-action">
                          Item {index + 1} · {reviewCategoryLabel(item)}
                        </p>
                        <p className="mt-1 text-sm font-semibold text-ink-1">
                          {observation?.canonical_name ?? item.title}
                        </p>
                      </div>
                      <span className={cls(
                        "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em]",
                        reviewSeverityClass(item.severity),
                      )}>
                        {item.severity}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-3 text-sm leading-5 text-ink-3">{item.body}</p>
                    <p className="mt-2 text-xs text-ink-3">
                      {label ? `Source: ${label}` : observation?.loinc_code ? `LOINC ${observation.loinc_code}` : item.resource_type ?? "Clinical fact"}
                    </p>
                  </button>
                );
              })}
            </div>
          </aside>

          <div className="space-y-4">
            <article className="rounded-[10px] border border-caution-line bg-caution-tint p-4">
              <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(0,1fr)_300px]">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-surface-0 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-caution">
                      {reviewCategoryLabel(activeItem)}
                    </span>
                    <span className={cls(
                      "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em]",
                      reviewSeverityClass(activeItem.severity),
                    )}>
                      {activeItem.severity} severity
                    </span>
                  </div>
                  <h3 className="mt-3 text-lg font-semibold text-ink-1">
                    {activeObservation?.canonical_name ?? activeItem.title}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-ink-3">{activeItem.body}</p>

                  {activeObservation && (
                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                      <MetricCard
                        label="Fact under review"
                        value={activeObservation.canonical_name}
                        detail={activeObservation.loinc_code
                          ? `LOINC ${activeObservation.loinc_code}${activeObservation.canonical_unit ? ` · canonical unit ${activeObservation.canonical_unit}` : ""}`
                          : activeItem.resource_type ?? "Clinical fact"}
                      />
                      <MetricCard
                        label="Current candidate"
                        value={activeRecommended
                          ? reviewValueLabel(activeRecommended.value, activeObservation.canonical_unit ?? activeRecommended.unit)
                          : "Needs judgment"}
                        detail={activeRecommended
                          ? `${reviewDateLabel(activeRecommended.effective_date)} · ${activeRecommended.source_label}`
                          : "No recommended value was found"}
                      />
                      <MetricCard
                        label="Why review"
                        value={activeSpread ? "Value spread detected" : "Conflicting evidence"}
                        detail={activeSpread
                          ? `Same-day values span ${activeSpread}; confirm which value should represent this fact.`
                          : "Multiple source values share the same day or fact identity and need a reviewer decision."}
                      />
                    </div>
                  )}

                  {activeObservation && (
                    <div className="mt-4 rounded-[10px] border border-caution-line bg-surface-0 px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-caution">Reviewer guidance</p>
                      <p className="mt-2 text-sm leading-6 text-ink-3">
                        Accept the current candidate only if the value, date, and source below match the canonical
                        fact you want downstream charts and agents to use. Alternate rows remain preserved as provenance.
                      </p>
                    </div>
                  )}

                  {activeSourceLabel && (
                    <p className="mt-3 text-xs text-ink-3">
                      Source: <span className="font-semibold text-ink-1">{activeSourceLabel}</span>
                    </p>
                  )}
                </div>

                <div className="flex flex-col gap-3">
                  {activeItem.category === "source" && (
                    <div className="rounded-[10px] border border-line-1 bg-surface-0 p-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">Source fix workflow</p>
                      <p className="mt-2 text-sm leading-6 text-ink-3">
                        Open Source Intake on this file, repair or extract it, then re-run harmonization before
                        publishing.
                      </p>
                      <Link
                        to={`/patient-record/sources${patientId ? `?patient=${encodeURIComponent(patientId)}${activeItem.source_id ? `&source=${encodeURIComponent(activeItem.source_id)}` : ""}` : activeItem.source_id ? `?source=${encodeURIComponent(activeItem.source_id)}` : ""}`}
                        className="mt-3 inline-flex w-full items-center justify-center rounded-[6px] border border-line-1 bg-surface-0 px-3 py-2 text-sm font-semibold text-ink-2 hover:border-action hover:text-action"
                      >
                        Fix in Source Intake
                      </Link>
                    </div>
                  )}

                  <button
                    type="button"
                    disabled={resolveMutation.isPending}
                    onClick={() =>
                      resolveItem(
                        activeItem,
                        activeItem.category === "fact" ? "accepted" : "dismissed",
                        activeItem.category === "fact"
                          ? "Accepted current candidate canonical fact after review."
                          : "Dismissed source blocker after review.",
                      )
                    }
                    className="inline-flex items-center justify-center gap-2 rounded-[6px] bg-action px-3 py-2.5 text-sm font-semibold text-white hover:bg-action-hover disabled:bg-surface-3 disabled:text-ink-3"
                  >
                    {resolveMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                    {activeItem.category === "fact" ? "Use candidate in canonical record" : "Mark reviewed"}
                  </button>

                  {activeItem.category === "fact" && (
                    <>
                      <button
                        type="button"
                        disabled={resolveMutation.isPending}
                        onClick={() =>
                          resolveItem(
                            activeItem,
                            "kept_separate",
                            "Reviewer kept conflicting values separate and preserved each value as source-backed evidence.",
                          )
                        }
                        className="inline-flex w-full items-center justify-center rounded-[6px] border border-line-1 bg-surface-0 px-3 py-2 text-sm font-semibold text-ink-2 hover:border-action hover:text-action disabled:bg-surface-1 disabled:text-ink-4"
                      >
                        Keep values separate
                      </button>
                      <button
                        type="button"
                        disabled={resolveMutation.isPending}
                        onClick={() =>
                          resolveItem(
                            activeItem,
                            "deferred",
                            "Reviewer deferred this conflict. It remains blocking until a final decision is recorded.",
                          )
                        }
                        className="inline-flex w-full items-center justify-center rounded-[6px] border border-caution-line bg-surface-0 px-3 py-2 text-sm font-semibold text-caution hover:bg-caution-tint disabled:bg-surface-1 disabled:text-ink-4"
                      >
                        Defer review
                      </button>
                      <div className="rounded-[10px] border border-line-1 bg-surface-0 px-3 py-3 text-xs leading-5 text-ink-3">
                        <p className="font-semibold uppercase tracking-[0.16em] text-ink-3">Decision model</p>
                        <p className="mt-2">
                          Accept uses the current candidate. Keep separate resolves the blocker while retaining all
                          source-backed values. Alternate preference updates this run&apos;s candidate pick before publish.
                          Defer keeps this run blocked.
                        </p>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </article>

            {activeObservation && (
              <section className="overflow-hidden rounded-[10px] border border-line-1 bg-surface-0">
                <div className="border-b border-line-1 px-4 py-3">
                  <p className="text-sm font-semibold text-ink-1">Source values under review</p>
                  <p className="mt-1 text-xs leading-5 text-ink-3">Compare every candidate value before choosing the canonical row for this run.</p>
                </div>
                <div className="divide-y divide-line-1">
                  {activeObservation.sources.map((source) => {
                    const isCandidate = sourceMatchesLatest(source, activeRecommended);
                    return (
                      <div
                        key={`${activeItem.id}-${source.source_observation_ref}`}
                        className={cls(
                          "grid gap-3 px-4 py-3 text-sm md:grid-cols-[minmax(0,1.1fr)_140px_150px_170px]",
                          isCandidate && "bg-clear-tint",
                        )}
                      >
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-semibold text-ink-1">{source.source_label}</p>
                            <span className={cls(
                              "rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em]",
                              isCandidate ? "bg-clear-tint text-clear" : "bg-surface-1 text-ink-3",
                            )}>
                              {isCandidate ? "Current pick" : "Alternate"}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-ink-3">
                            {activeObservation.loinc_code ? `LOINC ${activeObservation.loinc_code}` : "Observation"}
                          </p>
                          <details className="mt-2 text-xs text-ink-3">
                            <summary className="cursor-pointer list-none hover:text-action">
                              Technical reference: {shortReference(source.source_observation_ref)}
                            </summary>
                            <p className="mt-1 break-all font-mono text-[11px]">{source.source_observation_ref}</p>
                          </details>
                        </div>
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-3">Value</p>
                          <p className="mt-1 font-semibold text-ink-1">
                            {reviewValueLabel(source.value, source.unit, source.raw_value, source.raw_unit)}
                          </p>
                        </div>
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-3">Observed date</p>
                          <p className="mt-1 text-ink-2">{reviewDateLabel(source.effective_date)}</p>
                        </div>
                        <div className="flex items-center md:justify-end">
                          {isCandidate ? (
                            <span className="rounded-full bg-clear-tint px-2.5 py-1 text-xs font-semibold text-clear">
                              Current pick
                            </span>
                          ) : (
                            <button
                              type="button"
                              disabled={resolveMutation.isPending}
                              onClick={() =>
                                resolveItem(
                                  activeItem,
                                  "overridden",
                                  "Reviewer selected this alternate source value as the candidate for this run.",
                                  source.source_observation_ref,
                                )
                              }
                              className="inline-flex items-center justify-center rounded-[6px] border border-line-1 bg-surface-0 px-2.5 py-1.5 text-xs font-semibold text-ink-2 hover:border-action hover:text-action disabled:bg-surface-1 disabled:text-ink-4"
                            >
                              Use this value
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}
          </div>
        </div>
      )}
      {!isLoading && latestRun && resolvedRunItems.length > 0 && (
        <details className="mt-4 rounded-[10px] border border-line-1 bg-surface-1">
          <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-ink-1 hover:text-action">
            Resolved decisions ({resolvedRunItems.length})
          </summary>
          <div className="grid gap-2 border-t border-line-1 bg-surface-0 px-4 py-4 text-sm md:grid-cols-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">Audit events</p>
              <p className="mt-1 font-semibold text-ink-1">{latestRun.review_decision_summary.event_count}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">Decision mix</p>
              <p className="mt-1 text-ink-2">{reviewDecisionSummaryLabel(latestRun.review_decision_summary.decisions)}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">Latest event</p>
              <p className="mt-1 text-ink-2">
                {latestRun.review_decision_summary.latest_event_at
                  ? reviewDateLabel(latestRun.review_decision_summary.latest_event_at)
                  : "No timestamp"}
              </p>
            </div>
          </div>
          <div className="divide-y divide-line-1 border-t border-line-1">
            {resolvedRunItems.slice(0, 6).map((item) => {
              const observation = matchingObservation(item);
              const selectedSource = observation?.sources.find(
                (source) => source.source_observation_ref === item.selected_source_ref,
              ) ?? null;
              const selectedValue = selectedSource
                ? reviewValueLabel(
                    selectedSource.value,
                    selectedSource.unit,
                    selectedSource.raw_value,
                    selectedSource.raw_unit,
                  )
                : observation?.latest
                  ? reviewValueLabel(observation.latest.value, observation.canonical_unit ?? observation.latest.unit)
                  : null;
              return (
                <div key={item.id} className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[220px_1fr_220px]">
                  <div>
                    <p className="font-semibold text-ink-1">{reviewDecisionLabel(item.decision)}</p>
                    <p className="text-xs text-ink-3">{item.resolved_at ? reviewDateLabel(item.resolved_at) : "No timestamp"}</p>
                  </div>
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-ink-1">
                      {observation?.canonical_name ?? item.title}
                    </p>
                    <p className="line-clamp-2 text-xs leading-5 text-ink-3">
                      {item.decision_notes || item.body}
                    </p>
                    {observation?.loinc_code && (
                      <p className="mt-0.5 text-xs text-ink-4">
                        LOINC {observation.loinc_code}
                        {observation.canonical_unit ? ` · canonical unit ${observation.canonical_unit}` : ""}
                      </p>
                    )}
                  </div>
                  <div className="text-xs text-ink-3 md:text-right">
                    {selectedValue ? (
                      <div>
                        <p className="font-semibold text-ink-1">{selectedValue}</p>
                        <p className="mt-0.5">
                          {selectedSource?.source_label ?? observation?.latest?.source_label ?? "Current candidate"}
                        </p>
                        {item.selected_source_ref && (
                          <p className="mt-0.5 font-mono text-[11px]" title={item.selected_source_ref}>
                            {shortReference(item.selected_source_ref)}
                          </p>
                        )}
                      </div>
                    ) : (
                      <span>{item.category === "fact" ? item.resource_type ?? "Fact" : "Source"}</span>
                    )}
                  </div>
                </div>
              );
            })}
            {resolvedRunItems.length > 6 && (
              <div className="px-4 py-3 text-xs text-ink-3">
                Showing 6 of {resolvedRunItems.length} saved decisions.
              </div>
            )}
          </div>
          {latestRun.review_events.length > 0 && (
            <div className="border-t border-line-1 bg-surface-0 px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">
                Event ledger
              </p>
              <div className="mt-2 divide-y divide-line-1 rounded-[10px] border border-line-1">
                {latestRun.review_events.slice(-4).reverse().map((event) => (
                  <div key={event.event_id} className="grid gap-2 px-3 py-2 text-xs md:grid-cols-[150px_1fr_160px]">
                    <p className="font-semibold text-ink-1">{reviewDecisionLabel(event.decision)}</p>
                    <p className="min-w-0 truncate text-ink-3">
                      {event.notes || event.item_id}
                    </p>
                    <p className="text-ink-4 md:text-right">
                      {reviewDateLabel(event.created_at)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </details>
      )}
      {resolveMutation.error && (
        <p className="mt-3 text-sm text-red-700">
          Couldn't save review decision: {(resolveMutation.error as Error).message}
        </p>
      )}
    </section>
  );
}


function ContributionsPanel({
  collectionId,
  documentReference,
  uniqueDiff,
  onClose,
}: {
  collectionId: string;
  documentReference: string;
  uniqueDiff: import("../../types").HarmonizeSourceDiffSource | null;
  onClose: () => void;
}) {
  const [showUniqueOnly, setShowUniqueOnly] = useState(false);
  const [selectedNote, setSelectedNote] = useState<HarmonizeClinicalNote | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-contributions", collectionId, documentReference],
    queryFn: () =>
      api.getHarmonizeContributions(collectionId, documentReference),
  });

  // Pick which dataset to display: either the full contribution payload
  // or the unique-to-this-source subset from the source-diff endpoint.
  const view = useMemo(() => (
    showUniqueOnly && uniqueDiff
      ? {
          observations: uniqueDiff.unique_facts.observations,
          conditions: uniqueDiff.unique_facts.conditions,
          medications: uniqueDiff.unique_facts.medications,
          allergies: uniqueDiff.unique_facts.allergies,
          immunizations: uniqueDiff.unique_facts.immunizations,
          encounters: [],
          procedures: [],
          diagnostic_reports: [],
          clinical_notes: [],
          totals: {
            observations: uniqueDiff.totals.unique.observations,
            conditions: uniqueDiff.totals.unique.conditions,
            medications: uniqueDiff.totals.unique.medications,
            allergies: uniqueDiff.totals.unique.allergies,
            immunizations: uniqueDiff.totals.unique.immunizations,
            encounters: uniqueDiff.totals.unique.encounters ?? 0,
            procedures: uniqueDiff.totals.unique.procedures ?? 0,
            diagnostic_reports: uniqueDiff.totals.unique.diagnostic_reports ?? 0,
            clinical_notes: uniqueDiff.totals.unique.clinical_notes ?? 0,
            all: uniqueDiff.totals.unique.all,
          },
        }
      : data
        ? {
            observations: data.observations,
            conditions: data.conditions,
            medications: data.medications,
            allergies: data.allergies,
            immunizations: data.immunizations,
            encounters: data.encounters,
            procedures: data.procedures,
            diagnostic_reports: data.diagnostic_reports,
            clinical_notes: data.clinical_notes,
            totals: data.totals,
          }
        : null
  ), [data, showUniqueOnly, uniqueDiff]);

  const timelineEvents = useMemo<ContributionTimelineEvent[]>(() => {
    if (!view) return [];
    const events: ContributionTimelineEvent[] = [];

    view.observations.forEach((observation) => {
      matchingContributionSources(observation.sources, documentReference).forEach((source) => {
        if (!source.effective_date) return;
        const valueLabel = reviewValueLabel(source.value, source.unit, source.raw_value, source.raw_unit);
        events.push({
          id: `lab-${source.source_observation_ref}`,
          date: source.effective_date,
          kind: "Lab",
          primary: observation.canonical_name,
          secondary: `${valueLabel}${observation.loinc_code ? ` · LOINC ${observation.loinc_code}` : ""}`,
          tone: "blue",
        });
      });
    });

    view.conditions.forEach((condition) => {
      matchingContributionSources(condition.sources, documentReference).forEach((source) => {
        if (!source.onset_date) return;
        events.push({
          id: `condition-${source.source_condition_ref}`,
          date: source.onset_date,
          kind: "Condition",
          primary: condition.canonical_name,
          secondary: `${source.clinical_status ?? (condition.is_active ? "active" : "inactive")}${
            condition.snomed ? ` · SCT ${condition.snomed}` : ""
          }`,
          tone: "red",
        });
      });
    });

    view.medications.forEach((medication) => {
      matchingContributionSources(medication.sources, documentReference).forEach((source) => {
        if (!source.authored_on) return;
        events.push({
          id: `medication-${source.source_request_ref}`,
          date: source.authored_on,
          kind: "Medication",
          primary: medication.canonical_name,
          secondary: `${source.status ?? (medication.is_active ? "active" : "recorded")}${
            medication.rxnorm_codes[0] ? ` · RxNorm ${medication.rxnorm_codes[0]}` : ""
          }`,
          tone: "purple",
        });
      });
    });

    view.allergies.forEach((allergy) => {
      matchingContributionSources(allergy.sources, documentReference).forEach((source) => {
        if (!source.recorded_date) return;
        events.push({
          id: `allergy-${source.source_allergy_ref}`,
          date: source.recorded_date,
          kind: "Allergy",
          primary: allergy.canonical_name,
          secondary: `${source.criticality ?? allergy.highest_criticality ?? "criticality unknown"}${
            allergy.snomed ? ` · SCT ${allergy.snomed}` : ""
          }`,
          tone: "amber",
        });
      });
    });

    view.immunizations.forEach((immunization) => {
      matchingContributionSources(immunization.sources, documentReference).forEach((source) => {
        if (!source.occurrence_date) return;
        events.push({
          id: `immunization-${source.source_immunization_ref}`,
          date: source.occurrence_date,
          kind: "Immunization",
          primary: immunization.canonical_name,
          secondary: `${source.status ?? "recorded"}${immunization.cvx ? ` · CVX ${immunization.cvx}` : ""}`,
          tone: "teal",
        });
      });
    });

    view.encounters.forEach((encounter) => {
      const date = encounter.period_start ?? encounter.period_end;
      if (!date) return;
      events.push({
        id: `encounter-${encounter.source_id}-${encounter.id}`,
        date,
        kind: "Encounter",
        primary: encounter.type || encounter.reason || "Encounter",
        secondary: [
          artifactActorLabel(encounter),
          encounter.class_code ? `Class ${encounter.class_code}` : "",
          encounter.status,
        ].filter(Boolean).join(" · "),
        tone: "slate",
      });
    });

    view.procedures.forEach((procedure) => {
      const date = procedure.performed_start ?? procedure.performed_end;
      if (!date) return;
      events.push({
        id: `procedure-${procedure.source_id}-${procedure.id}`,
        date,
        kind: "Procedure",
        primary: procedure.display || procedure.type || "Procedure",
        secondary: [
          procedure.status,
          artifactActorLabel(procedure),
          procedure.encounter_id ? `Encounter ${shortReference(procedure.encounter_id)}` : "",
        ].filter(Boolean).join(" · "),
        tone: "teal",
      });
    });

    view.diagnostic_reports.forEach((report) => {
      if (!report.effective_date) return;
      events.push({
        id: `report-${report.source_id}-${report.id}`,
        date: report.effective_date,
        kind: "Report",
        primary: report.display || report.type || "Diagnostic report",
        secondary: [
          report.category,
          report.status,
          report.result_refs.length > 0 ? `${report.result_refs.length} result refs` : "",
          report.has_presented_form ? "attached note" : "",
        ].filter(Boolean).join(" · "),
        tone: "amber",
      });
    });

    view.clinical_notes.forEach((note) => {
      const date = note.time ?? note.date;
      if (!date) return;
      events.push({
        id: `note-${note.resource_id}-${note.note_index}`,
        date,
        kind: "Clinical note",
        primary: note.section_title || note.resource_type || "Clinical note",
        secondary: `${note.author ? `${note.author} · ` : ""}${note.encounter_id ? `Encounter ${shortReference(note.encounter_id)}` : shortReference(`${note.resource_type}/${note.resource_id}`)}`,
        tone: "slate",
      });
    });

    return events
      .sort((a, b) => contributionEventTimestamp(b.date) - contributionEventTimestamp(a.date))
      .slice(0, 16);
  }, [documentReference, view]);

  return (
    <div className="mt-4 rounded-xl border border-[#dfe4ea] bg-[#fafbfd] p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
            Reverse Provenance walk
          </p>
          <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
            {showUniqueOnly ? (
              <>
                What did <span className="font-mono">{data?.label ?? "this source"}</span> uniquely contribute?
              </>
            ) : (
              <>
                What did <span className="font-mono">{data?.label ?? "this source"}</span> contribute?
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {uniqueDiff && (
            <label className="flex items-center gap-1.5 text-xs text-[#667085]">
              <input
                type="checkbox"
                checked={showUniqueOnly}
                onChange={(e) => setShowUniqueOnly(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-[#dfe4ea]"
              />
              Unique only
            </label>
          )}
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#dfe4ea] bg-white px-2 py-1 text-xs text-[#667085]"
          >
            Close
          </button>
        </div>
      </div>

      {isLoading || !view ? (
        <p className="mt-3 text-sm text-[#667085]">Walking the Provenance graph…</p>
      ) : (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <ContributionStat label="Labs" value={view.totals.observations} />
            <ContributionStat label="Conditions" value={view.totals.conditions} />
            <ContributionStat label="Medications" value={view.totals.medications} />
            <ContributionStat label="Allergies" value={view.totals.allergies} />
            <ContributionStat label="Immunizations" value={view.totals.immunizations} />
            <ContributionStat label="Encounters" value={view.totals.encounters ?? 0} />
            <ContributionStat label="Procedures" value={view.totals.procedures ?? 0} />
            <ContributionStat label="Reports" value={view.totals.diagnostic_reports ?? 0} />
            <ContributionStat label="Clinical notes" value={view.totals.clinical_notes ?? 0} />
          </div>
          {showUniqueOnly && view.totals.all === 0 && (
            <p className="mt-3 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
              Every fact this source contributes is also in another source.
              Removing this source from the harmonization wouldn't lose any
              data — but would lose the cross-source confirmation.
            </p>
          )}
          <SourceContributionTimeline events={timelineEvents} />
          <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
            <ContributionList
              title="Conditions"
              items={view.conditions.map((c) => ({
                primary: c.canonical_name,
                secondary: c.snomed
                  ? `SCT ${c.snomed}`
                  : c.icd10
                    ? `ICD-10 ${c.icd10}`
                    : "text-only",
              }))}
            />
            <ContributionList
              title="Medications"
              items={view.medications.map((m) => ({
                primary: m.canonical_name,
                secondary:
                  m.rxnorm_codes.length > 0
                    ? `RxNorm ${m.rxnorm_codes[0]}${m.rxnorm_codes.length > 1 ? ` +${m.rxnorm_codes.length - 1}` : ""}`
                    : "text-only",
              }))}
            />
            <ContributionList
              title="Immunizations"
              items={view.immunizations.map((i) => ({
                primary: i.canonical_name,
                secondary: `${i.occurrence_date?.slice(0, 10) ?? "—"}${i.cvx ? ` · CVX ${i.cvx}` : ""}`,
              }))}
            />
            <ContributionList
              title="Allergies"
              items={view.allergies.map((a) => ({
                primary: a.canonical_name,
                secondary: a.snomed
                  ? `SCT ${a.snomed}`
                  : a.rxnorm
                    ? `RxNorm ${a.rxnorm}`
                    : "text-only",
              }))}
            />
            <ContributionList
              title="Encounters"
              items={view.encounters.map((encounter) => ({
                primary: encounter.type || encounter.reason || "Encounter",
                secondary: [
                  encounter.period_start ? reviewDateLabel(encounter.period_start) : "",
                  encounter.class_code ? `Class ${encounter.class_code}` : "",
                  artifactActorLabel(encounter),
                ].filter(Boolean).join(" · "),
              }))}
            />
            <ContributionList
              title="Procedures"
              items={view.procedures.map((procedure) => ({
                primary: procedure.display || procedure.type || "Procedure",
                secondary: [
                  procedure.performed_start ? reviewDateLabel(procedure.performed_start) : "",
                  procedure.status,
                  artifactActorLabel(procedure),
                ].filter(Boolean).join(" · "),
              }))}
            />
            <ContributionList
              title="Reports"
              items={view.diagnostic_reports.map((report) => ({
                primary: report.display || report.type || "Diagnostic report",
                secondary: [
                  report.effective_date ? reviewDateLabel(report.effective_date) : "",
                  report.result_refs.length > 0 ? `${report.result_refs.length} result refs` : "",
                  report.has_presented_form ? "note attached" : "",
                ].filter(Boolean).join(" · "),
              }))}
            />
            <ClinicalNoteContributionList
              notes={view.clinical_notes}
              onOpen={setSelectedNote}
            />
          </div>
          {view.totals.observations > 0 && (
            <p className="mt-3 text-xs text-[#a5a8b5]">
              + {view.totals.observations} lab observation
              {view.totals.observations === 1 ? "" : "s"} {showUniqueOnly ? "uniquely contributed" : "contributed"} (open the
              Labs tab to drill in).
            </p>
          )}
        </>
      )}
      {selectedNote && (
        <ClinicalNoteModal note={selectedNote} onClose={() => setSelectedNote(null)} />
      )}
    </div>
  );
}

function SourceContributionTimeline({ events }: { events: ContributionTimelineEvent[] }) {
  const clusters = groupContributionTimeline(events);

  return (
    <section className="mt-4 rounded-lg border border-[#dfe4ea] bg-white">
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-[#eef0f4] px-3 py-2.5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">
            Source timeline
          </p>
          <p className="mt-1 text-xs leading-5 text-[#667085]">
            Dated facts captured from this source, grouped by clinical date.
          </p>
        </div>
        {events.length > 0 && (
          <span className="rounded-full bg-[#f0f3fa] px-2 py-1 text-xs font-medium text-[#667085]">
            {clusters.length} date cluster{clusters.length === 1 ? "" : "s"} · {events.length} facts
          </span>
        )}
      </div>
      {events.length === 0 ? (
        <p className="px-3 py-3 text-sm text-[#667085]">
          No dated facts found for this source yet. Undated facts still appear in the resource lists below.
        </p>
      ) : (
        <div className="max-h-80 divide-y divide-[#eef0f4] overflow-y-auto">
          {clusters.map((cluster) => {
            const kinds = Array.from(new Set(cluster.events.map((event) => event.kind)));
            return (
              <div key={cluster.key} className="grid gap-3 px-3 py-3 text-sm sm:grid-cols-[132px_minmax(0,1fr)]">
                <div>
                  <p className="font-semibold tabular-nums text-[#1c1c1e]">
                    {reviewDateLabel(cluster.date)}
                  </p>
                  <p className="mt-1 text-[11px] font-medium text-[#8b90a0]">
                    {cluster.events.length} fact{cluster.events.length === 1 ? "" : "s"}
                  </p>
                </div>
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap gap-1.5">
                    {kinds.slice(0, 5).map((kind) => {
                      const tone = cluster.events.find((event) => event.kind === kind)?.tone ?? "slate";
                      return (
                        <span
                          key={kind}
                          className={cls(
                            "inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold",
                            timelineToneClass(tone),
                          )}
                        >
                          {kind}
                        </span>
                      );
                    })}
                    {kinds.length > 5 && (
                      <span className="inline-flex rounded-full bg-[#f0f3fa] px-2 py-0.5 text-[11px] font-semibold text-[#667085]">
                        +{kinds.length - 5} more
                      </span>
                    )}
                  </div>
                  <div className="rounded-lg border border-[#eef0f4] bg-[#fafbfd]">
                    {cluster.events.slice(0, 5).map((event) => (
                      <div key={event.id} className="border-b border-[#eef0f4] px-3 py-2 last:border-b-0">
                        <div className="flex min-w-0 items-start justify-between gap-2">
                          <p className="min-w-0 truncate font-semibold text-[#1c1c1e]">{event.primary}</p>
                          <span className="shrink-0 text-[11px] font-semibold text-[#667085]">{event.kind}</span>
                        </div>
                        <p className="mt-0.5 truncate text-xs text-[#667085]">{event.secondary}</p>
                      </div>
                    ))}
                    {cluster.events.length > 5 && (
                      <p className="px-3 py-2 text-xs font-medium text-[#667085]">
                        + {cluster.events.length - 5} more facts on this date.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function ContributionStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-[#dfe4ea] bg-white p-2 text-center">
      <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">
        {label}
      </p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums text-[#1c1c1e]">
        {value}
      </p>
    </div>
  );
}

function ContributionList({
  title,
  items,
}: {
  title: string;
  items: { primary: string; secondary: string }[];
}) {
  if (items.length === 0) return null;
  return (
    <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">
        {title} · {items.length}
      </p>
      <ul className="mt-2 space-y-1 text-sm">
        {items.map((it, i) => (
          <li key={i} className="flex items-start justify-between gap-2">
            <span className="truncate font-medium text-[#1c1c1e]">{it.primary}</span>
            <span className="shrink-0 text-xs text-[#667085]">{it.secondary}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ClinicalNoteContributionList({
  notes,
  onOpen,
}: {
  notes: HarmonizeClinicalNote[];
  onOpen: (note: HarmonizeClinicalNote) => void;
}) {
  if (notes.length === 0) return null;
  return (
    <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">
        Clinical notes · {notes.length}
      </p>
      <ul className="mt-2 divide-y divide-[#eef0f4] text-sm">
        {notes.slice(0, 12).map((note) => {
          const preview = note.text.length > 150 ? `${note.text.slice(0, 150)}...` : note.text;
          return (
            <li key={`${note.resource_id}-${note.note_index}`} className="py-2 first:pt-0 last:pb-0">
              <button
                type="button"
                onClick={() => onOpen(note)}
                className="block w-full rounded-md text-left hover:bg-[#f7f9fc]"
              >
                <span className="block font-medium leading-5 text-[#1c1c1e]">
                  {preview}
                </span>
                <span className="mt-1 block text-xs text-[#667085]">
                  {note.resource_type}
                  {note.date ? ` · ${reviewDateLabel(note.date)}` : ""}
                  {note.encounter_id ? ` · Encounter ${note.encounter_id}` : ""}
                  {note.source_label ? ` · ${note.source_label}` : ""}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {notes.length > 12 && (
        <p className="mt-2 text-xs text-[#a5a8b5]">
          Showing first 12 notes from this source. Use the prepared JSON export for the complete artifact set.
        </p>
      )}
    </div>
  );
}

function ClinicalNoteModal({
  note,
  onClose,
}: {
  note: HarmonizeClinicalNote;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/45 px-4 py-6">
      <div className="flex max-h-[86vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-[#dfe4ea] bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-[#eef0f4] px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              Clinical note
            </p>
            <h3 className="mt-1 text-lg font-semibold text-[#1c1c1e]">
              {note.resource_type}
              {note.date ? ` · ${reviewDateLabel(note.date)}` : ""}
            </h3>
            <p className="mt-1 text-sm text-[#667085]">
              {note.source_label || "Source document"} · {note.resource_id || "No resource id"}
              {note.encounter_id ? ` · Encounter ${note.encounter_id}` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-sm font-semibold text-[#667085] hover:bg-[#f7f9fc]"
          >
            Close
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-4">
          <pre className="whitespace-pre-wrap break-words rounded-lg bg-[#0f172a] p-4 font-mono text-xs leading-6 text-[#e5e7eb]">
            {note.text}
          </pre>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] p-3">
              <dt className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Source</dt>
              <dd className="mt-1 font-medium text-[#1c1c1e]">{note.source_label || note.source_id}</dd>
            </div>
            <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] p-3">
              <dt className="text-xs font-semibold uppercase tracking-wider text-[#667085]">FHIR reference</dt>
              <dd className="mt-1 break-all font-mono text-xs text-[#1c1c1e]">
                {note.resource_type}/{note.resource_id || "unknown"}#{note.note_index}
              </dd>
            </div>
            {note.encounter_id && (
              <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] p-3">
                <dt className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Encounter</dt>
                <dd className="mt-1 break-all font-mono text-xs text-[#1c1c1e]">
                  Encounter/{note.encounter_id}
                </dd>
              </div>
            )}
            {(note.author || note.time || note.section_title || note.attachment_content_type) && (
              <div className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] p-3">
                <dt className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Note metadata</dt>
                <dd className="mt-1 space-y-1 text-xs text-[#1c1c1e]">
                  {note.author && <p>Author: {note.author}</p>}
                  {note.time && <p>Time: {reviewDateLabel(note.time)}</p>}
                  {note.section_title && <p>Section: {note.section_title}</p>}
                  {note.attachment_content_type && <p>Attachment: {note.attachment_content_type}</p>}
                </dd>
              </div>
            )}
          </dl>
        </div>
      </div>
    </div>
  );
}

function HarmonizeGuideModal({ onClose }: { onClose: () => void }) {
  const steps = [
    "Confirm the right source workspace is active.",
    "Run harmonization to create a persisted candidate record.",
    "Review blockers, source evidence, and provenance.",
    "Move to Publish Chart once the run is clear.",
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/45 px-4 py-6">
      <div className="flex max-h-[86vh] w-full max-w-xl flex-col overflow-hidden rounded-xl border border-[#dfe4ea] bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-[#eef0f4] px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              Harmonized record
            </p>
            <h3 className="mt-1 text-lg font-semibold text-[#1c1c1e]">
              How this page works
            </h3>
            <p className="mt-1 text-sm text-[#667085]">
              Keep this nearby if you want the intended review flow without leaving the harmonized record surface.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-sm font-semibold text-[#667085] hover:bg-[#f7f9fc]"
          >
            Close
          </button>
        </div>
        <div className="space-y-3 overflow-y-auto px-5 py-4">
          {steps.map((step, index) => (
            <div key={step} className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Step {index + 1}</p>
              <p className="mt-1 text-sm font-medium leading-6 text-[#1c1c1e]">{step}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CanonicalSelectionCard({
  selection,
}: {
  selection: HarmonizeCanonicalSelection;
}) {
  const selected = selection.selected_latest;
  const previous = selection.previous_latest;
  const decision = selection.decision ?? "reviewed";

  return (
    <div className="rounded-lg border border-[#b7c4ff] bg-[#f5f7ff] p-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
            Canonical selection
          </p>
          <p className="mt-1 font-semibold text-[#1c1c1e]">
            {reviewDecisionLabel(decision)}
          </p>
        </div>
        <span className="rounded-full bg-white px-2 py-1 text-xs font-medium text-[#667085]">
          {selection.applied ? "Applied to latest run" : "Decision recorded"}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <div className="rounded-lg border border-[#dfe4ea] bg-white p-2.5">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">
            Selected value
          </p>
          <p className="mt-1 font-semibold text-[#1c1c1e]">
            {canonicalSelectionValueLabel(selected)}
          </p>
          <p className="mt-1 text-xs text-[#667085]">
            {selected?.effective_date ? reviewDateLabel(selected.effective_date) : "No date"} ·{" "}
            {selection.selected_source_label ?? selected?.source_label ?? "Unknown source"}
          </p>
        </div>
        <div className="rounded-lg border border-[#dfe4ea] bg-white p-2.5">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">
            Previous candidate
          </p>
          <p className="mt-1 font-semibold text-[#1c1c1e]">
            {canonicalSelectionValueLabel(previous)}
          </p>
          <p className="mt-1 text-xs text-[#667085]">
            {previous?.effective_date ? reviewDateLabel(previous.effective_date) : "No date"} ·{" "}
            {previous?.source_label ?? "Unknown source"}
          </p>
        </div>
      </div>
      {selection.selected_source_ref && (
        <code className="mt-2 block rounded bg-white px-2 py-1 text-xs text-[#667085]">
          Selected source: {shortReference(selection.selected_source_ref)}
        </code>
      )}
      {selection.notes && (
        <p className="mt-2 rounded bg-white px-2 py-1.5 text-xs leading-5 text-[#667085]">
          {selection.notes}
        </p>
      )}
      {selection.warning && (
        <p className="mt-2 rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
          {selection.warning}
        </p>
      )}
    </div>
  );
}

function ProvenancePanel({
  collectionId,
  mergedRef,
}: {
  collectionId: string;
  mergedRef: string | null;
}) {
  const { data, isLoading } = useQuery<HarmonizeProvenanceResponse>({
    queryKey: ["harmonize-provenance", collectionId, mergedRef],
    queryFn: () => api.getHarmonizeProvenance(collectionId, mergedRef as string),
    enabled: !!mergedRef,
  });

  if (!mergedRef) {
    return (
      <p className="text-sm text-[#667085]">
        Pick a merged fact to see its Provenance lineage.
      </p>
    );
  }
  if (isLoading) return <p className="text-sm text-[#667085]">Loading lineage…</p>;
  if (!data) return <p className="text-sm text-red-700">Couldn't load Provenance.</p>;

  const prov = data.provenance;
  const activity = prov.activity?.coding?.[0]?.code ?? "—";
  return (
    <div className="space-y-3">
      {data.canonical_selection && (
        <CanonicalSelectionCard selection={data.canonical_selection} />
      )}
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-[#667085]">
        <Link2 size={14} />
        <span className="font-semibold">Activity:</span>
        <code className="rounded bg-[#f0f3fa] px-1.5 py-0.5 text-[11px] text-[#1c1c1e]">
          {activity}
        </code>
        <span>· {prov.entity?.length ?? 0} source edge(s)</span>
      </div>
      <ul className="space-y-2">
        {prov.entity?.map((e, idx) => {
          const ext = Object.fromEntries(
            (e.extension ?? []).map((x) => [
              x.url.split("/").pop() ?? x.url,
              x.valueString,
            ]),
          );
          return (
            <li
              key={idx}
              className="rounded-lg border border-[#dfe4ea] bg-white p-3 text-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-[#1c1c1e]">
                  {ext["source-label"] ?? "?"}
                </span>
                <code className="rounded bg-[#f0f3fa] px-1.5 py-0.5 text-[11px] text-[#5b76fe]">
                  {ext["harmonize-activity"] ?? "?"}
                </code>
              </div>
              <code className="mt-1 block truncate text-xs text-[#667085]">
                {e.what?.reference}
              </code>
            </li>
          );
        })}
      </ul>
      <details className="rounded-lg border border-[#dfe4ea] bg-[#fafbfd] p-2 text-xs">
        <summary className="cursor-pointer font-semibold text-[#667085]">
          Raw FHIR Provenance JSON
        </summary>
        <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap break-all text-[10px] leading-snug text-[#1c1c1e]">
          {JSON.stringify(prov, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function RecordWorkspace({
  collectionId,
  tab,
  onTabChange,
}: {
  collectionId: string;
  tab: ResourceTab;
  onTabChange: (tab: ResourceTab) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#eef0f4] px-4">
        <button
          type="button"
          onClick={() => onTabChange("labs")}
          className={cls(
            "flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium",
            tab === "labs"
              ? "border-[#5b76fe] text-[#5b76fe]"
              : "border-transparent text-[#667085] hover:text-[#1c1c1e]",
          )}
        >
          <Activity size={14} />
          Labs
        </button>
        <button
          type="button"
          onClick={() => onTabChange("conditions")}
          className={cls(
            "flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium",
            tab === "conditions"
              ? "border-[#5b76fe] text-[#5b76fe]"
              : "border-transparent text-[#667085] hover:text-[#1c1c1e]",
          )}
        >
          <Stethoscope size={14} />
          Conditions
        </button>
        <button
          type="button"
          onClick={() => onTabChange("medications")}
          className={cls(
            "flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium",
            tab === "medications"
              ? "border-[#5b76fe] text-[#5b76fe]"
              : "border-transparent text-[#667085] hover:text-[#1c1c1e]",
          )}
        >
          <Pill size={14} />
          Medications
        </button>
        <button
          type="button"
          onClick={() => onTabChange("allergies")}
          className={cls(
            "flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium",
            tab === "allergies"
              ? "border-[#5b76fe] text-[#5b76fe]"
              : "border-transparent text-[#667085] hover:text-[#1c1c1e]",
          )}
        >
          <ShieldAlert size={14} />
          Allergies
        </button>
        <button
          type="button"
          onClick={() => onTabChange("immunizations")}
          className={cls(
            "flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium",
            tab === "immunizations"
              ? "border-[#5b76fe] text-[#5b76fe]"
              : "border-transparent text-[#667085] hover:text-[#1c1c1e]",
          )}
        >
          <Syringe size={14} />
          Immunizations
        </button>
      </div>
      <div className="p-5">
        {tab === "labs" ? (
          <LabsTab collectionId={collectionId} />
        ) : tab === "conditions" ? (
          <ConditionsTab collectionId={collectionId} />
        ) : tab === "medications" ? (
          <MedicationsTab collectionId={collectionId} />
        ) : tab === "allergies" ? (
          <AllergiesTab collectionId={collectionId} />
        ) : (
          <ImmunizationsTab collectionId={collectionId} />
        )}
      </div>
    </div>
  );
}

function ProvenanceWorkspace({ collectionId }: { collectionId: string }) {
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-observations", collectionId, "provenance"],
    queryFn: () => api.getHarmonizeObservations(collectionId, false),
    enabled: !!collectionId,
  });

  const facts: HarmonizeMergedObservation[] = useMemo(() => data?.merged ?? [], [data?.merged]);
  const effectiveSelectedRef = selectedRef ?? facts[0]?.merged_ref ?? null;
  const selected = useMemo(
    () => facts.find((item) => item.merged_ref === effectiveSelectedRef) ?? facts[0] ?? null,
    [facts, effectiveSelectedRef],
  );

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_1fr]">
      <section className="rounded-lg border border-[#dfe4ea] bg-white">
        <div className="border-b border-[#eef0f4] px-4 py-3">
          <p className="text-sm font-semibold text-[#1c1c1e]">Canonical facts</p>
          <p className="mt-1 text-xs leading-5 text-[#667085]">
            Select a merged lab fact to inspect the FHIR Provenance edges. Other
            resource types can use this same pattern as the provenance UI matures.
          </p>
        </div>
        {isLoading ? (
          <p className="p-4 text-sm text-[#667085]">Loading canonical facts…</p>
        ) : facts.length === 0 ? (
          <p className="p-4 text-sm text-[#667085]">No facts available for provenance review.</p>
        ) : (
          <div className="max-h-[620px] overflow-y-auto">
            {facts.slice(0, 80).map((fact) => {
              const selectedFact = selected?.merged_ref === fact.merged_ref;
              return (
                <button
                  key={fact.merged_ref ?? fact.canonical_name}
                  type="button"
                  onClick={() => setSelectedRef(fact.merged_ref)}
                  className={cls(
                    "block w-full border-b border-[#eef0f4] px-4 py-3 text-left last:border-b-0 hover:bg-[#f7f9fc]",
                    selectedFact && "bg-[#eef2ff]",
                  )}
                >
                  <span className="block truncate text-sm font-semibold text-[#1c1c1e]">
                    {fact.canonical_name}
                  </span>
                  <span className="mt-1 block text-xs text-[#667085]">
                    {fact.source_count} source{fact.source_count === 1 ? "" : "s"}
                    {fact.loinc_code ? ` · LOINC ${fact.loinc_code}` : ""}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-[#dfe4ea] bg-white p-4">
        <div className="mb-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
            Provenance lineage
          </p>
          <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">
            {selected?.canonical_name ?? "Select a canonical fact"}
          </h2>
        </div>
        <ProvenancePanel
          collectionId={collectionId}
          mergedRef={selected?.merged_ref ?? null}
        />
      </section>
    </div>
  );
}

function useCrossSourceFilter(collectionId: string) {
  const shouldDefaultCrossOnly = (id: string) => !id.startsWith("upload-") && !id.startsWith("workspace-");
  const [filterState, setFilterState] = useState(() => ({
    collectionId,
    crossOnly: shouldDefaultCrossOnly(collectionId),
  }));
  const crossOnly =
    filterState.collectionId === collectionId
      ? filterState.crossOnly
      : shouldDefaultCrossOnly(collectionId);
  const setCrossOnly = useCallback(
    (next: boolean) => {
      setFilterState({ collectionId, crossOnly: next });
    },
    [collectionId],
  );

  return [crossOnly, setCrossOnly] as const;
}

function LabsTab({ collectionId }: { collectionId: string }) {
  const [crossOnly, setCrossOnly] = useCrossSourceFilter(collectionId);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-observations", collectionId, crossOnly],
    queryFn: () => api.getHarmonizeObservations(collectionId, crossOnly),
    enabled: !!collectionId,
  });

  const merged: HarmonizeMergedObservation[] = useMemo(() => data?.merged ?? [], [data?.merged]);
  const selected = useMemo(
    () => merged.find((m) => m.merged_ref === selectedRef) ?? merged[0] ?? null,
    [merged, selectedRef],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard
          label="Canonical labs"
          value={data?.total ?? 0}
          detail="Distinct facts after identity resolution"
        />
        <MetricCard
          label="Cross-source merges"
          value={data?.cross_source ?? 0}
          detail="Labs found in ≥2 sources"
        />
        <MetricCard
          label="Conflicts"
          value={merged.filter((m) => m.has_conflict).length}
          detail=">10% same-day spread"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-[#667085]">
          <input
            type="checkbox"
            checked={crossOnly}
            onChange={(e) => {
              setCrossOnly(e.target.checked);
              setSelectedRef(null);
            }}
            className="h-4 w-4 rounded border-[#dfe4ea]"
          />
          Show only cross-source merges
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
          {isLoading ? (
            <p className="p-6 text-sm text-[#667085]">Loading labs…</p>
          ) : merged.length === 0 ? (
            <p className="p-6 text-sm text-[#667085]">No labs to display.</p>
          ) : (
            <div className="max-h-[640px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <tr>
                    <th className="px-4 py-2">Lab</th>
                    <th className="px-4 py-2 hidden md:table-cell">LOINC</th>
                    <th className="px-4 py-2 text-right hidden sm:table-cell">Sources</th>
                    <th className="px-4 py-2 text-right">Latest</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef0f4] bg-white">
                  {merged.map((m) => {
                    const isSelected = selected?.merged_ref === m.merged_ref;
                    return (
                      <tr
                        key={m.merged_ref ?? m.canonical_name}
                        onClick={() => setSelectedRef(m.merged_ref)}
                        className={cls(
                          "cursor-pointer hover:bg-[#f7f9fc]",
                          isSelected && "bg-[#eef2ff]",
                        )}
                      >
                        <td className="px-4 py-2 font-medium text-[#1c1c1e]">
                          {m.canonical_name.length > 50
                            ? m.canonical_name.slice(0, 50) + "…"
                            : m.canonical_name}
                        </td>
                        <td className="px-4 py-2 text-[#667085] hidden md:table-cell">
                          <code className="text-xs">{m.loinc_code ?? "—"}</code>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e] hidden sm:table-cell">
                          {m.source_count}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e]">
                          {m.latest?.value != null
                            ? formatMeasurement(m.latest.value, m.latest.unit)
                            : "—"}
                        </td>
                        <td className="px-4 py-2">
                          {m.has_conflict && (
                            <AlertTriangle
                              size={14}
                              className="text-amber-600"
                              aria-label="Same-day cross-source conflict"
                            />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
            <h4 className="text-sm font-semibold text-[#1c1c1e]">
              {selected?.canonical_name ?? "—"}
            </h4>
            {selected?.loinc_code && (
              <p className="mt-1 text-xs text-[#667085]">
                LOINC <code>{selected.loinc_code}</code> · canonical unit{" "}
                <code>{selected.canonical_unit ?? "—"}</code>
              </p>
            )}
            {selected && (
              <ul className="mt-3 space-y-1 text-sm">
                {selected.sources.map((s, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between border-b border-[#eef0f4] py-1 last:border-b-0"
                  >
                    <span className="text-[#667085]">
                      {s.effective_date ? s.effective_date.slice(0, 10) : "—"} ·{" "}
                      {s.source_label}
                    </span>
                    <span className="tabular-nums font-medium text-[#1c1c1e]">
                      {s.value != null ? formatMeasurement(s.value, s.unit) : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
            <h4 className="mb-2 text-sm font-semibold text-[#1c1c1e]">
              Provenance lineage
            </h4>
            <ProvenancePanel
              collectionId={collectionId}
              mergedRef={selected?.merged_ref ?? null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function ConditionsTab({ collectionId }: { collectionId: string }) {
  const [crossOnly, setCrossOnly] = useCrossSourceFilter(collectionId);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-conditions", collectionId, crossOnly],
    queryFn: () => api.getHarmonizeConditions(collectionId, crossOnly),
    enabled: !!collectionId,
  });

  const merged: HarmonizeMergedCondition[] = useMemo(() => data?.merged ?? [], [data?.merged]);
  const selected = useMemo(
    () => merged.find((m) => m.merged_ref === selectedRef) ?? merged[0] ?? null,
    [merged, selectedRef],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard
          label="Canonical conditions"
          value={data?.total ?? 0}
          detail="Distinct facts after identity resolution"
        />
        <MetricCard
          label="Cross-source merges"
          value={data?.cross_source ?? 0}
          detail="Conditions found in ≥2 sources"
        />
        <MetricCard
          label="Active"
          value={merged.filter((m) => m.is_active).length}
          detail="Status active / recurrent / unknown"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-[#667085]">
          <input
            type="checkbox"
            checked={crossOnly}
            onChange={(e) => {
              setCrossOnly(e.target.checked);
              setSelectedRef(null);
            }}
            className="h-4 w-4 rounded border-[#dfe4ea]"
          />
          Show only cross-source merges
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
          {isLoading ? (
            <p className="p-6 text-sm text-[#667085]">Loading conditions…</p>
          ) : merged.length === 0 ? (
            <p className="p-6 text-sm text-[#667085]">No conditions to display.</p>
          ) : (
            <div className="max-h-[640px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <tr>
                    <th className="px-4 py-2">Condition</th>
                    <th className="px-4 py-2 hidden md:table-cell">SNOMED</th>
                    <th className="px-4 py-2 hidden lg:table-cell">ICD-10</th>
                    <th className="px-4 py-2 text-right hidden sm:table-cell">Sources</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef0f4] bg-white">
                  {merged.map((m) => {
                    const isSelected = selected?.merged_ref === m.merged_ref;
                    return (
                      <tr
                        key={m.merged_ref ?? m.canonical_name}
                        onClick={() => setSelectedRef(m.merged_ref)}
                        className={cls(
                          "cursor-pointer hover:bg-[#f7f9fc]",
                          isSelected && "bg-[#eef2ff]",
                        )}
                      >
                        <td className="px-4 py-2 font-medium text-[#1c1c1e]">
                          {m.canonical_name.length > 60
                            ? m.canonical_name.slice(0, 60) + "…"
                            : m.canonical_name}
                        </td>
                        <td className="px-4 py-2 text-[#667085] hidden md:table-cell">
                          <code className="text-xs">{m.snomed ?? "—"}</code>
                        </td>
                        <td className="px-4 py-2 text-[#667085] hidden lg:table-cell">
                          <code className="text-xs">{m.icd10 ?? "—"}</code>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e] hidden sm:table-cell">
                          {m.source_count}
                        </td>
                        <td className="px-4 py-2 text-center">
                          {m.is_active ? (
                            <span className="text-emerald-600">●</span>
                          ) : (
                            <span className="text-[#dfe4ea]">○</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
            <h4 className="text-sm font-semibold text-[#1c1c1e]">
              {selected?.canonical_name ?? "—"}
            </h4>
            {selected && (
              <p className="mt-1 text-xs text-[#667085]">
                {selected.snomed && (
                  <span>
                    SNOMED <code>{selected.snomed}</code>{" "}
                  </span>
                )}
                {selected.icd10 && (
                  <span>
                    · ICD-10 <code>{selected.icd10}</code>
                  </span>
                )}
                {selected.icd9 && (
                  <span>
                    · ICD-9 <code>{selected.icd9}</code>
                  </span>
                )}
              </p>
            )}
            {selected && (
              <ul className="mt-3 space-y-1 text-sm">
                {selected.sources.map((s, i) => (
                  <li key={i} className="border-b border-[#eef0f4] py-1 last:border-b-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#1c1c1e]">{s.source_label}</span>
                      <span className="text-xs text-[#667085]">
                        {s.onset_date ? s.onset_date.slice(0, 10) : "—"}
                      </span>
                    </div>
                    <p className="text-xs text-[#667085]">{s.display}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
            <h4 className="mb-2 text-sm font-semibold text-[#1c1c1e]">
              Provenance lineage
            </h4>
            <ProvenancePanel
              collectionId={collectionId}
              mergedRef={selected?.merged_ref ?? null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function MedicationsTab({ collectionId }: { collectionId: string }) {
  const [crossOnly, setCrossOnly] = useCrossSourceFilter(collectionId);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-medications", collectionId, crossOnly],
    queryFn: () => api.getHarmonizeMedications(collectionId, crossOnly),
    enabled: !!collectionId,
  });

  const merged: HarmonizeMergedMedication[] = useMemo(() => data?.merged ?? [], [data?.merged]);
  const selected = useMemo(
    () => merged.find((m) => m.merged_ref === selectedRef) ?? merged[0] ?? null,
    [merged, selectedRef],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard
          label="Canonical medications"
          value={data?.total ?? 0}
          detail="Distinct meds after identity resolution"
        />
        <MetricCard
          label="Cross-source merges"
          value={data?.cross_source ?? 0}
          detail="Meds found in ≥2 sources"
        />
        <MetricCard
          label="Active"
          value={merged.filter((m) => m.is_active).length}
          detail="Status active / on-hold / unknown"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-[#667085]">
          <input
            type="checkbox"
            checked={crossOnly}
            onChange={(e) => {
              setCrossOnly(e.target.checked);
              setSelectedRef(null);
            }}
            className="h-4 w-4 rounded border-[#dfe4ea]"
          />
          Show only cross-source merges
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
          {isLoading ? (
            <p className="p-6 text-sm text-[#667085]">Loading medications…</p>
          ) : merged.length === 0 ? (
            <p className="p-6 text-sm text-[#667085]">No medications to display.</p>
          ) : (
            <div className="max-h-[640px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <tr>
                    <th className="px-4 py-2">Medication</th>
                    <th className="px-4 py-2 hidden md:table-cell">RxNorm</th>
                    <th className="px-4 py-2 text-right hidden sm:table-cell">Sources</th>
                    <th className="px-4 py-2 text-center">Active</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef0f4] bg-white">
                  {merged.map((m) => {
                    const isSelected = selected?.merged_ref === m.merged_ref;
                    return (
                      <tr
                        key={m.merged_ref ?? m.canonical_name}
                        onClick={() => setSelectedRef(m.merged_ref)}
                        className={cls(
                          "cursor-pointer hover:bg-[#f7f9fc]",
                          isSelected && "bg-[#eef2ff]",
                        )}
                      >
                        <td className="px-4 py-2 font-medium text-[#1c1c1e]">
                          {m.canonical_name.length > 50
                            ? m.canonical_name.slice(0, 50) + "…"
                            : m.canonical_name}
                        </td>
                        <td className="px-4 py-2 text-[#667085] hidden md:table-cell">
                          <code className="text-xs">
                            {m.rxnorm_codes[0] ?? "—"}
                            {m.rxnorm_codes.length > 1 && ` +${m.rxnorm_codes.length - 1}`}
                          </code>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e] hidden sm:table-cell">
                          {m.source_count}
                        </td>
                        <td className="px-4 py-2 text-center">
                          {m.is_active ? (
                            <span className="text-emerald-600">●</span>
                          ) : (
                            <span className="text-[#dfe4ea]">○</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
            <h4 className="text-sm font-semibold text-[#1c1c1e]">
              {selected?.canonical_name ?? "—"}
            </h4>
            {selected && selected.rxnorm_codes.length > 0 && (
              <p className="mt-1 text-xs text-[#667085]">
                RxNorm codes:{" "}
                {selected.rxnorm_codes.slice(0, 5).map((c, i) => (
                  <code key={c} className="text-xs">
                    {c}
                    {i < Math.min(selected.rxnorm_codes.length, 5) - 1 ? ", " : ""}
                  </code>
                ))}
                {selected.rxnorm_codes.length > 5 &&
                  ` (+${selected.rxnorm_codes.length - 5} more)`}
              </p>
            )}
            {selected && (
              <ul className="mt-3 space-y-1 text-sm">
                {selected.sources.map((s, i) => (
                  <li key={i} className="border-b border-[#eef0f4] py-1 last:border-b-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#1c1c1e]">{s.source_label}</span>
                      <span className="text-xs text-[#667085]">
                        {s.status ?? "—"}
                      </span>
                    </div>
                    <p className="text-xs text-[#667085]">{s.display}</p>
                    {s.authored_on && (
                      <p className="text-[10px] text-[#a5a8b5]">
                        authored {s.authored_on.slice(0, 10)}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
            <h4 className="mb-2 text-sm font-semibold text-[#1c1c1e]">
              Provenance lineage
            </h4>
            <ProvenancePanel
              collectionId={collectionId}
              mergedRef={selected?.merged_ref ?? null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function AllergiesTab({ collectionId }: { collectionId: string }) {
  const [crossOnly, setCrossOnly] = useCrossSourceFilter(collectionId);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-allergies", collectionId, crossOnly],
    queryFn: () => api.getHarmonizeAllergies(collectionId, crossOnly),
    enabled: !!collectionId,
  });

  const merged: HarmonizeMergedAllergy[] = useMemo(() => data?.merged ?? [], [data?.merged]);
  const selected = useMemo(
    () => merged.find((m) => m.merged_ref === selectedRef) ?? merged[0] ?? null,
    [merged, selectedRef],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard
          label="Canonical allergies"
          value={data?.total ?? 0}
          detail="Distinct allergies after identity resolution"
        />
        <MetricCard
          label="Cross-source merges"
          value={data?.cross_source ?? 0}
          detail="Allergies in ≥2 sources"
        />
        <MetricCard
          label="High criticality"
          value={merged.filter((m) => m.highest_criticality === "high").length}
          detail="Worst-severity rollup"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-[#667085]">
          <input
            type="checkbox"
            checked={crossOnly}
            onChange={(e) => {
              setCrossOnly(e.target.checked);
              setSelectedRef(null);
            }}
            className="h-4 w-4 rounded border-[#dfe4ea]"
          />
          Show only cross-source merges
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
          {isLoading ? (
            <p className="p-6 text-sm text-[#667085]">Loading allergies…</p>
          ) : merged.length === 0 ? (
            <p className="p-6 text-sm text-[#667085]">No allergies to display.</p>
          ) : (
            <div className="max-h-[640px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <tr>
                    <th className="px-4 py-2">Allergy</th>
                    <th className="px-4 py-2 hidden md:table-cell">SNOMED</th>
                    <th className="px-4 py-2">Criticality</th>
                    <th className="px-4 py-2 text-right hidden sm:table-cell">Sources</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef0f4] bg-white">
                  {merged.map((m) => {
                    const isSelected = selected?.merged_ref === m.merged_ref;
                    return (
                      <tr
                        key={m.merged_ref ?? m.canonical_name}
                        onClick={() => setSelectedRef(m.merged_ref)}
                        className={cls(
                          "cursor-pointer hover:bg-[#f7f9fc]",
                          isSelected && "bg-[#eef2ff]",
                        )}
                      >
                        <td className="px-4 py-2 font-medium text-[#1c1c1e]">
                          {m.canonical_name.length > 50
                            ? m.canonical_name.slice(0, 50) + "…"
                            : m.canonical_name}
                        </td>
                        <td className="px-4 py-2 text-[#667085] hidden md:table-cell">
                          <code className="text-xs">{m.snomed ?? "—"}</code>
                        </td>
                        <td className="px-4 py-2">
                          {m.highest_criticality === "high" ? (
                            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                              high
                            </span>
                          ) : m.highest_criticality === "low" ? (
                            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                              low
                            </span>
                          ) : (
                            <span className="text-xs text-[#a5a8b5]">—</span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e] hidden sm:table-cell">
                          {m.source_count}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
            <h4 className="text-sm font-semibold text-[#1c1c1e]">
              {selected?.canonical_name ?? "—"}
            </h4>
            {selected && (
              <p className="mt-1 text-xs text-[#667085]">
                {selected.snomed && <span>SNOMED <code>{selected.snomed}</code></span>}
                {selected.rxnorm && <span> · RxNorm <code>{selected.rxnorm}</code></span>}
              </p>
            )}
            {selected && (
              <ul className="mt-3 space-y-1 text-sm">
                {selected.sources.map((s, i) => (
                  <li key={i} className="border-b border-[#eef0f4] py-1 last:border-b-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#1c1c1e]">{s.source_label}</span>
                      <span className="text-xs text-[#667085]">
                        {s.criticality ?? "—"}
                      </span>
                    </div>
                    <p className="text-xs text-[#667085]">{s.display}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
            <h4 className="mb-2 text-sm font-semibold text-[#1c1c1e]">
              Provenance lineage
            </h4>
            <ProvenancePanel
              collectionId={collectionId}
              mergedRef={selected?.merged_ref ?? null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function ImmunizationsTab({ collectionId }: { collectionId: string }) {
  const [crossOnly, setCrossOnly] = useCrossSourceFilter(collectionId);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["harmonize-immunizations", collectionId, crossOnly],
    queryFn: () => api.getHarmonizeImmunizations(collectionId, crossOnly),
    enabled: !!collectionId,
  });

  const merged: HarmonizeMergedImmunization[] = useMemo(() => data?.merged ?? [], [data?.merged]);
  const selected = useMemo(
    () => merged.find((m) => m.merged_ref === selectedRef) ?? merged[0] ?? null,
    [merged, selectedRef],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard
          label="Immunization events"
          value={data?.total ?? 0}
          detail="Distinct (vaccine, date) events"
        />
        <MetricCard
          label="Cross-source merges"
          value={data?.cross_source ?? 0}
          detail="Events in ≥2 sources"
        />
        <MetricCard
          label="Most recent"
          value={
            merged.length > 0 && merged[merged.length - 1].occurrence_date
              ? merged[merged.length - 1].occurrence_date!.slice(0, 10)
              : "—"
          }
          detail="Latest occurrence date"
        />
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-[#667085]">
          <input
            type="checkbox"
            checked={crossOnly}
            onChange={(e) => {
              setCrossOnly(e.target.checked);
              setSelectedRef(null);
            }}
            className="h-4 w-4 rounded border-[#dfe4ea]"
          />
          Show only cross-source merges
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
          {isLoading ? (
            <p className="p-6 text-sm text-[#667085]">Loading immunizations…</p>
          ) : merged.length === 0 ? (
            <p className="p-6 text-sm text-[#667085]">No immunizations to display.</p>
          ) : (
            <div className="max-h-[640px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#f7f9fc] text-left text-xs font-semibold uppercase tracking-wider text-[#667085]">
                  <tr>
                    <th className="px-4 py-2">Date</th>
                    <th className="px-4 py-2">Vaccine</th>
                    <th className="px-4 py-2 hidden md:table-cell">CVX</th>
                    <th className="px-4 py-2 text-right hidden sm:table-cell">Sources</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef0f4] bg-white">
                  {merged.map((m) => {
                    const isSelected = selected?.merged_ref === m.merged_ref;
                    return (
                      <tr
                        key={m.merged_ref ?? m.canonical_name}
                        onClick={() => setSelectedRef(m.merged_ref)}
                        className={cls(
                          "cursor-pointer hover:bg-[#f7f9fc]",
                          isSelected && "bg-[#eef2ff]",
                        )}
                      >
                        <td className="px-4 py-2 tabular-nums text-[#667085]">
                          {m.occurrence_date ? m.occurrence_date.slice(0, 10) : "—"}
                        </td>
                        <td className="px-4 py-2 font-medium text-[#1c1c1e]">
                          {m.canonical_name.length > 50
                            ? m.canonical_name.slice(0, 50) + "…"
                            : m.canonical_name}
                        </td>
                        <td className="px-4 py-2 text-[#667085] hidden md:table-cell">
                          <code className="text-xs">{m.cvx ?? "—"}</code>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-[#1c1c1e] hidden sm:table-cell">
                          {m.source_count}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
            <h4 className="text-sm font-semibold text-[#1c1c1e]">
              {selected?.canonical_name ?? "—"}
            </h4>
            {selected && (
              <p className="mt-1 text-xs text-[#667085]">
                {selected.cvx && <span>CVX <code>{selected.cvx}</code></span>}
                {selected.ndc && <span> · NDC <code>{selected.ndc}</code></span>}
                {selected.occurrence_date && (
                  <span> · {selected.occurrence_date.slice(0, 10)}</span>
                )}
              </p>
            )}
            {selected && (
              <ul className="mt-3 space-y-1 text-sm">
                {selected.sources.map((s, i) => (
                  <li key={i} className="border-b border-[#eef0f4] py-1 last:border-b-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-[#1c1c1e]">{s.source_label}</span>
                      <span className="text-xs text-[#667085]">
                        {s.status ?? "—"}
                      </span>
                    </div>
                    <p className="text-xs text-[#667085]">{s.display}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-lg border border-[#dfe4ea] bg-white p-3">
            <h4 className="mb-2 text-sm font-semibold text-[#1c1c1e]">
              Provenance lineage
            </h4>
            <ProvenancePanel
              collectionId={collectionId}
              mergedRef={selected?.merged_ref ?? null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export function HarmonizeView() {
  const [tab, setTab] = useState<ResourceTab>("labs");
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("record");
  const [showGuide, setShowGuide] = useState(false);
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const requestedCollection = searchParams.get("collection");

  const collectionsQuery = useQuery({
    queryKey: ["harmonize-collections"],
    queryFn: () => api.getHarmonizeCollections(),
  });
  const workspaceQuery = useQuery({
    queryKey: ["harmonize-workspace", patientId],
    queryFn: () => api.getHarmonizeWorkspace(patientId as string),
    enabled: Boolean(patientId),
  });
  const patientsQuery = useQuery({
    queryKey: ["patients"],
    queryFn: api.listPatients,
    staleTime: Infinity,
  });
  const collections = collectionsQuery.data?.collections ?? [];
  const patientWorkspace = workspaceQuery.data ?? null;
  const collectionIdsKey = [
    patientWorkspace?.id ?? "",
    ...collections.map((collection) => collection.id),
  ].join("|");
  const selectedPatient = patientsQuery.data?.find((patient) => patient.id === patientId) ?? null;
  const uploadCollectionId = patientId ? `upload-${safeUploadSessionId(patientId)}` : "";
  const patientUploadCollection = uploadCollectionId
    ? collections.find((collection) => collection.id === uploadCollectionId) ?? null
    : null;
  const requestedValidCollection = requestedCollection && (
    collections.some((collection) => collection.id === requestedCollection) ||
    requestedCollection === patientWorkspace?.id
  )
    ? requestedCollection
    : "";
  const defaultFixtureCollection =
    collections.find((collection) => collection.id === "synthea-demo") ?? collections[0] ?? null;
  const autoCollectionId =
    patientWorkspace?.id || patientUploadCollection?.id || requestedValidCollection || defaultFixtureCollection?.id || "";
  const [activeExtractJobId, setActiveExtractJobId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setActiveExtractJobId(null);
    });
    return () => {
      cancelled = true;
    };
  }, [patientId, requestedValidCollection, collectionIdsKey]);

  const activeId = autoCollectionId;
  const activeCollection =
    activeId === patientWorkspace?.id ? patientWorkspace : collections.find((c) => c.id === activeId) ?? null;
  const isPatientWorkspace = activeId === patientWorkspace?.id && !!patientWorkspace;
  const isUploadCollection = activeId === uploadCollectionId && !!patientUploadCollection;
  const isDeveloperFixture = !!activeId && !isPatientWorkspace && !isUploadCollection;
  const activeCollectionHasNoSources =
    !!activeCollection && activeCollection.source_count === 0 && !isDeveloperFixture;

  // Async extract: kick off a background job, then poll until complete.
  // The mutation just starts the job; the polling query owns the lifecycle.
  const extractMutation = useMutation({
    mutationFn: () => api.extractHarmonizeCollection(activeId),
    onSuccess: (job) => {
      setActiveExtractJobId(job.job_id);
    },
  });

  const extractJobQuery = useQuery({
    queryKey: ["harmonize-extract-job", activeExtractJobId],
    queryFn: () => api.getHarmonizeExtractJob(activeExtractJobId as string),
    enabled: !!activeExtractJobId,
    // Poll every 1.5s while the job is still running. Once complete or
    // failed, refetchInterval returns false and React Query stops.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "complete" || status === "failed") return false;
      return 1500;
    },
  });

  // When the job completes, bust dependent caches once and clear the job.
  useEffect(() => {
    const status = extractJobQuery.data?.status;
    if (status === "complete") {
      queryClient.invalidateQueries({ queryKey: ["harmonize-sources", activeId] });
      queryClient.invalidateQueries({ queryKey: ["harmonize-observations", activeId] });
      queryClient.invalidateQueries({ queryKey: ["harmonize-conditions", activeId] });
      queryClient.invalidateQueries({ queryKey: ["harmonize-medications", activeId] });
      queryClient.invalidateQueries({ queryKey: ["harmonize-allergies", activeId] });
      queryClient.invalidateQueries({ queryKey: ["harmonize-immunizations", activeId] });
      queryClient.invalidateQueries({ queryKey: ["harmonize-source-diff", activeId] });
    }
  }, [extractJobQuery.data?.status, activeId, queryClient]);

  const extractInProgress =
    extractMutation.isPending ||
    (!!activeExtractJobId &&
      (extractJobQuery.data?.status === "pending" ||
        extractJobQuery.data?.status === "running"));
  const extractJob = extractJobQuery.data ?? null;
  const latestRunQuery = useQuery({
    queryKey: ["harmonize-run-latest", activeId],
    queryFn: () => api.getLatestHarmonizationRun(activeId),
    enabled: !!activeId,
  });
  const runMutation = useMutation({
    mutationFn: () => api.runHarmonization(activeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["harmonize-run-latest", activeId] });
    },
  });
  const latestRun = latestRunQuery.data?.latest_run ?? null;
  const openRunReviewItems = latestRun?.review_items.filter((item) => !item.resolved) ?? [];

  const isLoadingCollections = collectionsQuery.isLoading || (Boolean(patientId) && workspaceQuery.isLoading);
  const hasNoCollections =
    !isLoadingCollections && collections.length === 0 && !patientWorkspace;
  const formatRunDate = (value: string | null | undefined) => {
    if (!value) return "Not run yet";
    return new Date(value).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };
  const preparedSourceCount = latestRun?.summary.prepared_source_count ?? 0;
  const totalSourceCount = latestRun?.summary.source_count ?? activeCollection?.source_count ?? 0;
  const sourcesLink = `/patient-record/sources${patientId ? `?patient=${encodeURIComponent(patientId)}` : ""}`;
  const publishLink = `/patient-record/publish${patientId ? `?patient=${encodeURIComponent(patientId)}` : ""}`;
  const workspaceMeta: Partial<Record<WorkspaceTab, string>> = {
    record: latestRun ? `${latestRun.summary.total_candidate_facts} facts` : "Live preview",
    review: latestRun ? (openRunReviewItems.length > 0 ? `${openRunReviewItems.length} open` : "Clear") : "Run first",
    sources: activeCollection ? `${activeCollection.source_count} sources` : "No sources",
    provenance: latestRun ? "Lineage ready" : "After run",
  };
  const nextAction = activeCollectionHasNoSources
    ? {
        title: "Add source material before harmonization",
        body: "This workspace exists, but it does not yet contain prepared records to merge into a candidate chart.",
      }
    : !latestRun
      ? {
          title: "Run harmonization to create the candidate record",
          body: "The record tables below are a live preview. A persisted run is the durable handoff into review and publish.",
        }
      : openRunReviewItems.length > 0
        ? {
            title: "Resolve review blockers before publish",
            body: "Focus on the review workspace to clear source issues and fact conflicts on the latest harmonization run.",
          }
        : latestRun.summary.publishable
          ? {
              title: "Candidate record is ready for Publish Chart",
              body: "The run has a saved audit trail and no open blockers, so downstream activation is available.",
            }
          : {
              title: "Re-run harmonization after source updates",
              body: "Source preparation or matcher output changed. Generate a fresh run before publishing.",
            };

  return (
    <div className="space-y-4">
      <header className="rounded-[10px] border border-line-1 bg-surface-0 px-5 py-4 shadow-[var(--shadow-1)] xl:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-action">
              <Layers3 size={14} />
              <span>Harmonized record</span>
            </div>
            <h1 className="mt-2 text-2xl font-semibold text-ink-1">
              Merge, review, and trace the canonical record
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-3">
              Native FHIR pulls and vision-extracted PDFs become one longitudinal record. The goal here is to move
              from source collection to a reviewable candidate chart, then publish only after blockers are cleared.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowGuide(true)}
            className="inline-flex shrink-0 items-center gap-2 rounded-[8px] border border-line-1 bg-surface-1 px-3 py-2 text-sm font-semibold text-ink-2 hover:border-action hover:text-action"
          >
            <BookOpen size={15} />
            How this works
          </button>
        </div>
      </header>

      {/* T8c — patient voice / care episodes / conflicts. Hides itself when
          no augmentation artifacts exist on disk for this patient. */}
      {patientId && <PatientContextPanels patientId={patientId} />}

      {isLoadingCollections && (
        <div className="rounded-[10px] border border-line-1 bg-surface-0 p-5 shadow-[var(--shadow-1)]">
          <p className="flex items-center gap-2 text-sm text-ink-3">
            <Loader2 size={14} className="animate-spin" />
            Loading collections...
          </p>
        </div>
      )}

      {hasNoCollections && (
        <div className="rounded-[10px] border border-line-1 bg-surface-0 p-8 text-center shadow-[var(--shadow-1)]">
          <div className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-full bg-action-tint text-action">
            <Inbox size={20} />
          </div>
          <h2 className="mt-4 text-lg font-semibold text-ink-1">
            No collections yet
          </h2>
          <p className="mt-2 mx-auto max-w-xl text-sm leading-6 text-ink-3">
            The harmonize layer needs at least one document collection to merge.
            On a fresh checkout, the Synthea demo collection auto-registers from
            the public sample data. If you're seeing this state, that bundle
            wasn't found at <code className="text-xs">data/synthea-samples/</code>.
          </p>
          <p className="mt-3 mx-auto max-w-xl text-sm leading-6 text-ink-3">
            Either pull the Synthea sample data into{" "}
            <code className="text-xs">data/synthea-samples/synthea-r4-individual/fhir/</code>,
            or upload at least one document on the Patient Record page. Uploads
            automatically register as a harmonize collection.
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
            <Link
              to="/patient-record/sources"
              className="inline-flex items-center gap-2 rounded-[6px] bg-action px-4 py-2 text-sm font-semibold text-white hover:bg-action-hover"
            >
              <FileUp size={14} />
              Upload documents
            </Link>
            <a
              href="https://github.com/synthetichealth/synthea#quick-start"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-[6px] border border-line-1 bg-surface-0 px-4 py-2 text-sm font-semibold text-ink-2"
            >
              Synthea quick-start →
            </a>
          </div>
        </div>
      )}

      {!isLoadingCollections && !hasNoCollections && (
        <>
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1.08fr)_352px] xl:items-start">
            <section className="self-start rounded-[10px] border border-line-1 bg-surface-0 px-5 py-3.5 shadow-[var(--shadow-1)]">
              <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_max-content] xl:items-start">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-action">Active workspace</p>
                    {activeCollection && (
                      <span className="rounded-full bg-surface-1 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-3">
                        {activeCollection.source_count} sources
                      </span>
                    )}
                  </div>
                  <h2 className="mt-1 max-w-2xl text-lg font-semibold leading-8 text-ink-1">
                    {selectedPatient?.name ?? activeCollection?.name ?? "Selected patient workspace"}
                  </h2>
                  <p className="mt-1.5 max-w-2xl text-sm leading-6 text-ink-3">
                    {activeCollection?.description ?? "The selected patient's baseline and uploaded source files are feeding this harmonized record."}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2 xl:max-w-[340px] xl:justify-end">
                  <Link
                    to={sourcesLink}
                    className="inline-flex items-center gap-2 rounded-[6px] border border-line-1 bg-surface-0 px-3 py-2 text-sm font-semibold text-ink-2 hover:border-action hover:text-action"
                  >
                    <FileUp size={14} />
                    Manage sources
                  </Link>
                </div>
              </div>

              {extractJob?.status === "complete" && (
                <div className="mt-4 rounded-[10px] border border-line-1 bg-surface-1 p-4 text-sm">
                  <p className="font-semibold text-ink-1">
                    Extracted {extractJob.results.length} PDF{extractJob.results.length === 1 ? "" : "s"}
                  </p>
                  {extractJob.results.length > 0 ? (
                    <ul className="mt-2 space-y-1 text-xs text-ink-3">
                      {extractJob.results.map((result) => (
                        <li key={result.source_id}>
                          <span className="font-medium text-ink-1">{result.label}</span>: {result.entry_count} resources
                          {result.cache_hit ? " (cached)" : ` (${result.elapsed_seconds.toFixed(1)}s)`}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-xs text-ink-3">
                      No pending PDFs. Every uploaded PDF already had a cached extraction.
                    </p>
                  )}
                </div>
              )}
              {extractJob?.status === "failed" && (
                <p className="mt-4 rounded-[10px] border border-critical-line bg-critical-tint px-4 py-3 text-sm text-critical">
                  Extraction failed: {extractJob.error ?? "unknown error"}
                </p>
              )}
              {extractMutation.error && !extractJob && (
                <p className="mt-4 rounded-[10px] border border-critical-line bg-critical-tint px-4 py-3 text-sm text-critical">
                  Couldn&apos;t start extract job: {(extractMutation.error as Error).message ?? "unknown error"}
                </p>
              )}

              <div className="mt-3 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                  label="Last run"
                  value={latestRunQuery.isLoading ? "…" : formatRunDate(latestRun?.completed_at)}
                  detail={latestRun?.rule_version ?? "No persisted run yet"}
                />
                <MetricCard
                  label="Publish state"
                  value={latestRun ? (latestRun.summary.publishable ? "Ready" : "Blocked") : "Not run"}
                  detail={latestRun ? `${preparedSourceCount}/${totalSourceCount} sources prepared` : "Run first"}
                />
                <MetricCard
                  label="Candidate facts"
                  value={latestRun?.summary.total_candidate_facts ?? "—"}
                  detail="Persisted in latest run"
                />
                <MetricCard
                  label="Review items"
                  value={latestRun?.summary.review_item_count ?? "—"}
                  detail="Source gaps or fact conflicts"
                />
              </div>
            </section>

            <section className="self-start rounded-[10px] border border-line-1 bg-surface-0 p-3.5 shadow-[var(--shadow-1)]">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-action">Next action</p>
              <h2 className="mt-0.5 text-lg font-semibold leading-8 text-ink-1">{nextAction.title}</h2>
              <p className="mt-1 text-sm leading-6 text-ink-3">{nextAction.body}</p>

              <button
                type="button"
                disabled={runMutation.isPending || !activeId}
                onClick={() => runMutation.mutate()}
                className={cls(
                  "mt-3 inline-flex w-full items-center justify-center gap-2 rounded-[6px] px-4 py-2.5 text-sm font-semibold transition-colors",
                  runMutation.isPending
                    ? "bg-surface-3 text-ink-3"
                    : "bg-action text-white hover:bg-action-hover",
                )}
              >
                {runMutation.isPending ? (
                  <>
                    <Loader2 size={15} className="animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <PlayCircle size={15} />
                    {latestRun ? "Re-run harmonization" : "Run harmonization"}
                  </>
                )}
              </button>

              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setWorkspaceTab(openRunReviewItems.length > 0 ? "review" : "record")}
                  className="inline-flex items-center gap-2 rounded-[6px] border border-line-1 bg-surface-0 px-3 py-2 text-sm font-semibold text-ink-2 hover:border-action hover:text-action"
                >
                  {openRunReviewItems.length > 0 ? "Open review blockers" : "Open merged record"}
                </button>
                {latestRun?.summary.publishable && (
                  <Link
                    to={publishLink}
                    className="inline-flex items-center gap-2 rounded-[6px] border border-line-1 bg-surface-0 px-3 py-2 text-sm font-semibold text-ink-2 hover:border-action hover:text-action"
                  >
                    Publish chart
                  </Link>
                )}
              </div>

              {latestRun && openRunReviewItems.length > 0 && (
                <div className="mt-2.5 rounded-[10px] border border-caution-line bg-caution-tint px-4 py-2.5 text-sm text-caution">
                  <span className="font-semibold">{openRunReviewItems[0].title}</span>
                  <span className="ml-1">{openRunReviewItems[0].body}</span>
                  {openRunReviewItems.length > 1 && (
                    <span className="ml-1">
                      +{openRunReviewItems.length - 1} more item{openRunReviewItems.length === 2 ? "" : "s"} in the run.
                    </span>
                  )}
                </div>
              )}
              {runMutation.error && (
                <p className="mt-2.5 rounded-[10px] border border-critical-line bg-critical-tint px-4 py-2.5 text-sm text-critical">
                  Couldn&apos;t run harmonization: {(runMutation.error as Error).message}
                </p>
              )}
            </section>
          </div>

          {activeCollectionHasNoSources && (
            <section className="rounded-[10px] border border-line-1 bg-surface-0 p-6 shadow-[var(--shadow-1)]">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="max-w-3xl">
                  <div className="inline-flex h-10 w-10 items-center justify-center rounded-[10px] bg-action-tint text-action">
                    <Inbox size={18} />
                  </div>
                  <h2 className="mt-3 text-lg font-semibold text-ink-1">No sources ready for harmonization</h2>
                  <p className="mt-2 text-sm leading-6 text-ink-3">
                    This workspace exists, but Source Intake does not have any prepared source files yet. Upload a
                    portal export or PDF first. The harmonized record will stay empty until there is source data to merge.
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Link
                    to={sourcesLink}
                    className="inline-flex items-center gap-2 rounded-[6px] bg-action px-4 py-2 text-sm font-semibold text-white hover:bg-action-hover"
                  >
                    <FileUp size={14} />
                    Add sources
                  </Link>
                  <Link
                    to={`/patient-record${patientId ? `?patient=${encodeURIComponent(patientId)}` : ""}`}
                    className="inline-flex items-center gap-2 rounded-[6px] border border-line-1 bg-surface-0 px-4 py-2 text-sm font-semibold text-ink-2 hover:border-action hover:text-action"
                  >
                    Workspace overview
                  </Link>
                </div>
              </div>
            </section>
          )}

          {!activeCollectionHasNoSources && (
            <>
              <WorkspaceTabs active={workspaceTab} onChange={setWorkspaceTab} meta={workspaceMeta} />

              {activeId && workspaceTab === "record" && (
                <RecordWorkspace
                  collectionId={activeId}
                  tab={tab}
                  onTabChange={setTab}
                />
              )}

              {activeId && workspaceTab === "review" && (
                <ReviewQueuePanel collectionId={activeId} patientId={patientId} />
              )}

              {activeId && workspaceTab === "sources" && (
                <SourcesPanel
                  collectionId={activeId}
                  canExtract={isUploadCollection || isPatientWorkspace}
                  extractInProgress={extractInProgress}
                  onExtract={() => extractMutation.mutate()}
                />
              )}

              {activeId && workspaceTab === "provenance" && (
                <ProvenanceWorkspace collectionId={activeId} />
              )}
            </>
          )}
        </>
      )}

      {!isLoadingCollections && !hasNoCollections && (
        <p className="text-xs leading-5 text-ink-3">
          The Provenance graph is the Atlas wedge: every merged fact retains pointers back to its sources via FHIR
          Provenance entities. Atlas extension URLs (<code>source-label</code>, <code>harmonize-activity</code>)
          carry the lineage that downstream consumers read to render explainability.
        </p>
      )}

      {showGuide && <HarmonizeGuideModal onClose={() => setShowGuide(false)} />}
    </div>
  );
}
