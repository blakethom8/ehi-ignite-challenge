import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Database,
  UserRound,
} from "lucide-react";
import { api } from "../../api/client";
import { DemoPatientPicker } from "../../components/atlas/DemoPatientPicker";
import { StartStateCard } from "../../components/atlas/StartStateCard";
import type {
  CanonicalSourceSummary,
} from "../../types";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${patientId}` : path;
}

function workspaceCollectionId(patientId: string): string {
  const safe = patientId
    .replace(/[^A-Za-z0-9_.-]+/g, "-")
    .replace(/^[.-]+|[.-]+$/g, "")
    .slice(0, 120) || "patient";
  return `upload-${safe}`;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function formatNumber(value: number | null | undefined): string {
  return (value ?? 0).toLocaleString();
}

function statusClass(status: string): string {
  if (status === "structured" || status === "extracted") return "bg-emerald-50 text-emerald-800";
  if (status === "ready_to_extract" || status === "stored") return "bg-amber-50 text-amber-800";
  if (status === "unsupported") return "bg-red-50 text-red-700";
  return "bg-slate-100 text-slate-700";
}

function FactLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-[#eef0f4] py-2 last:border-b-0">
      <span className="text-sm text-[#667085]">{label}</span>
      <span className="text-right text-sm font-semibold text-[#1c1c1e]">{value}</span>
    </div>
  );
}


export function PatientRecordOverview() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const collectionId = patientId ? workspaceCollectionId(patientId) : "";

  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId ?? ""),
    enabled: !!patientId && !patientId.startsWith("workspace-"),
  });

  const canonicalQ = useQuery({
    queryKey: ["canonical-summary", patientId],
    queryFn: () => api.getCanonicalSummary(patientId ?? ""),
    enabled: !!patientId,
  });

  const sourcesQ = useQuery({
    queryKey: ["aggregation-sources", patientId],
    queryFn: () => api.getAggregationSources(patientId ?? ""),
    enabled: !!patientId,
  });

  const latestRunQ = useQuery({
    queryKey: ["harmonize-run-latest", collectionId],
    queryFn: () => api.getLatestHarmonizationRun(collectionId),
    enabled: !!collectionId,
  });

  const publishedQ = useQuery({
    queryKey: ["published-chart", collectionId],
    queryFn: () => api.getPublishedChart(collectionId),
    enabled: !!collectionId,
  });

  if (!patientId) {
    return (
      <StartStateCard
        icon={Database}
        eyebrow="Patient Record"
        title="Start with a sample chart before opening the record pipeline."
        body="Patient Record now begins on one overview page that combines current chart status, source activity, and snapshot history. Select a synthetic sample chart first so the workspace can load with coherent context."
        bullets={[
          "Review what sources exist and which ones still need preparation.",
          "See whether a published chart version is already active.",
          "Open harmonization and publish steps without bouncing across overlapping overview pages.",
        ]}
        aside={
          <DemoPatientPicker
            destination={(demoPatientId) => `/patient-record?patient=${encodeURIComponent(demoPatientId)}`}
            title="Open Patient Record with a sample chart"
          />
        }
      />
    );
  }

  const overview = overviewQ.data;
  const canonical = canonicalQ.data;
  const sourceEnvironment = sourcesQ.data;
  const latestRun = latestRunQ.data?.latest_run ?? null;
  const publishedState = publishedQ.data ?? null;
  const activeSnapshot = publishedState?.active_snapshot ?? null;
  const chartName = canonical?.patient_name || overview?.name || sourceEnvironment?.patient_label;
  const sourceCount = canonical?.source_count ?? 0;
  const preparedSourceCount = canonical?.prepared_source_count ?? 0;
  const needsPreparationCount = canonical?.needs_preparation_count ?? Math.max(sourceCount - preparedSourceCount, 0);
  const reviewItemCount = canonical?.review_item_count ?? latestRun?.summary.review_item_count ?? 0;
  const readinessPct = canonical
    ? Math.max(
        0,
        Math.min(
          100,
          Math.round(
            sourceCount > 0
              ? (preparedSourceCount / sourceCount) * 100 - Math.min(reviewItemCount * 4, 20)
              : 0,
          ),
        ),
      )
    : 0;
  const chartFactTotal = canonical?.total_resources ?? overview?.total_resources ?? 0;
  const chartStatus = activeSnapshot
    ? "Active chart snapshot is live"
    : !canonical
      ? "Loading chart state"
      : sourceCount === 0
        ? "No sources connected"
        : needsPreparationCount > 0
          ? "Sources need preparation"
          : reviewItemCount > 0
            ? "Review needed before publish"
            : "Ready for use";

  const factLines = overview
    ? [
        ["Patient", `${Math.floor(overview.age_years)} years · ${overview.gender}`],
        ["Record span", `${formatDate(overview.earliest_encounter_dt)} to ${formatDate(overview.latest_encounter_dt)}`],
        ["Active problems", formatNumber(canonical?.canonical_condition_count ?? overview.active_condition_count)],
        ["Active medications", formatNumber(canonical?.canonical_medication_count ?? overview.active_med_count)],
        ["Encounters", formatNumber(canonical?.encounter_count ?? overview.encounter_count)],
        ["Labs and observations", formatNumber(canonical?.canonical_observation_count ?? overview.unique_loinc_count)],
      ]
    : canonical
      ? [
          ["Workspace", canonical.workspace_id],
          ["Record span", `${formatDate(canonical.date_start)} to ${formatDate(canonical.date_end)}`],
          ["Conditions", formatNumber(canonical.canonical_condition_count)],
          ["Medications", formatNumber(canonical.canonical_medication_count)],
          ["Encounters", formatNumber(canonical.encounter_count)],
          ["Labs and observations", formatNumber(canonical.canonical_observation_count)],
        ]
      : [];

  return (
    <main className="mx-auto max-w-6xl space-y-5 p-4 lg:p-6">
      <section className="rounded-lg border border-[#dfe4ea] bg-white px-5 py-5">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
          <div className="min-w-0">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <Database size={13} />
              Patient workspace overview
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-[#1c1c1e] lg:text-3xl">
              {chartName ? `${chartName}'s FHIR Chart` : "Patient-owned FHIR Chart"}
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#667085]">
              This is the working summary for the current chart: what has been
              added, what is usable, and which published version is currently active.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link to={withPatient("/patient-record/sources", patientId)} className="inline-flex items-center gap-1 rounded-lg bg-[#5b76fe] px-3 py-2 text-sm font-semibold text-white">
                Source Intake <ArrowRight size={14} />
              </Link>
              <Link to={withPatient("/patient-record/harmonize", patientId)} className="inline-flex items-center gap-1 rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm font-semibold text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe]">
                Harmonized Record
              </Link>
              <Link to={withPatient("/patient-record/publish", patientId)} className="inline-flex items-center gap-1 rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm font-semibold text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe]">
                Publish Chart
              </Link>
            </div>
          </div>

          <div className="rounded-lg border border-[#eef0f4] bg-[#fafbff] p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-[#1c1c1e]">{chartStatus}</p>
              <span className="text-sm font-semibold text-[#5b76fe]">{readinessPct}%</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#e9eaef]">
              <div className="h-full rounded-full bg-[#00b473]" style={{ width: `${readinessPct}%` }} />
            </div>
            <div className="mt-4 space-y-2 text-sm text-[#667085]">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-[#00b473]" />
                {preparedSourceCount}/{sourceCount} sources prepared
              </div>
              <div className="flex items-center gap-2">
                {activeSnapshot ? (
                  <CheckCircle2 size={14} className="text-[#00b473]" />
                ) : (
                  <AlertTriangle size={14} className="text-[#f59e0b]" />
                )}
                {activeSnapshot
                  ? `Published version ${activeSnapshot.snapshot_id.slice(0, 8)} is active`
                  : "No published version is active yet"}
              </div>
              <div className="flex items-center gap-2">
                {reviewItemCount > 0 ? (
                  <AlertTriangle size={14} className="text-[#f59e0b]" />
                ) : (
                  <CheckCircle2 size={14} className="text-[#00b473]" />
                )}
                {latestRun
                  ? `${latestRun.summary.review_item_count} review items in the latest harmonization run`
                  : "No harmonization run has been published for this chart yet"}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-[#dfe4ea] bg-white p-5">
        <div className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
          <div className="space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Current chart posture</p>
            <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">What is ready right now</h2>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              Review the current workspace sources and how many prepared facts each one is contributing to the chart.
            </p>

            <div className="overflow-hidden rounded-xl border border-[#eef0f4] bg-white">
              <div className="grid grid-cols-[minmax(0,1.3fr)_140px_120px] gap-3 border-b border-[#eef0f4] bg-[#fafbff] px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-[#667085]">
                <span>Workspace source</span>
                <span>Status</span>
                <span className="text-right">Facts</span>
              </div>
              {canonicalQ.isLoading ? (
                <p className="px-4 py-4 text-sm text-[#667085]">Loading current sources...</p>
              ) : canonical?.sources.length ? (
                canonical.sources.map((source: CanonicalSourceSummary) => (
                  <div
                    key={source.id}
                    className="grid grid-cols-[minmax(0,1.3fr)_140px_120px] gap-3 border-b border-[#eef0f4] px-4 py-3 last:border-b-0"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-[#1c1c1e]">{source.label}</p>
                      <p className="mt-1 text-xs text-[#8d92a3]">{source.kind}</p>
                    </div>
                    <div className="flex items-start">
                      <span className={`w-fit rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass(source.status)}`}>
                        {source.status_label}
                      </span>
                    </div>
                    <p className="text-right text-sm font-semibold text-[#1c1c1e]">
                      {formatNumber(source.total_resources)}
                    </p>
                  </div>
                ))
              ) : (
                <p className="px-4 py-4 text-sm text-[#667085]">No connected sources yet. Start in Source Intake.</p>
              )}
            </div>

            <div className="grid gap-3 rounded-xl border border-[#eef0f4] bg-[#fafbff] p-4 sm:grid-cols-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[#667085]">Sources</p>
                <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{formatNumber(sourceCount)}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[#667085]">Prepared facts</p>
                <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{formatNumber(chartFactTotal)}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[#667085]">Needs preparation</p>
                <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{formatNumber(needsPreparationCount)}</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-[#eef0f4] bg-[#fcfcfe] p-4">
            <div className="flex items-center gap-2">
              <UserRound size={17} className="text-[#5b76fe]" />
              <h3 className="text-base font-semibold text-[#1c1c1e]">Patient facts in the chart</h3>
            </div>
            <div className="mt-3">
              {patientId && overviewQ.isLoading && !patientId.startsWith("workspace-") ? (
                <p className="text-sm leading-6 text-[#667085]">Loading patient facts...</p>
              ) : (
                factLines.map(([label, value]) => (
                  <FactLine key={label} label={label} value={value} />
                ))
              )}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
