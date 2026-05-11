import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  Database,
  FileBarChart,
  FileJson2,
  Heart,
  ListChecks,
  Share2,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../../api/client";
import { DemoPatientPicker } from "../../components/atlas/DemoPatientPicker";
import { StartStateCard } from "../../components/atlas/StartStateCard";
import type { CanonicalSourceSummary } from "../../types";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${patientId}` : path;
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

function MetricText({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-[#667085]">{label}</p>
      <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{value}</p>
      {note && <p className="mt-0.5 text-xs leading-5 text-[#667085]">{note}</p>}
    </div>
  );
}

function FactLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-[#eef0f4] py-2 last:border-b-0">
      <span className="text-sm text-[#667085]">{label}</span>
      <span className="text-right text-sm font-semibold text-[#1c1c1e]">{value}</span>
    </div>
  );
}

function ChartLinkRow({
  icon: Icon,
  title,
  body,
  to,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  to: string;
}) {
  return (
    <Link
      to={to}
      className="group grid gap-3 border-b border-[#eef0f4] py-3 no-underline last:border-b-0 sm:grid-cols-[28px_minmax(0,1fr)_auto] sm:items-center"
    >
      <Icon size={17} className="text-[#5b76fe]" />
      <div className="min-w-0">
        <p className="text-sm font-semibold text-[#1c1c1e]">{title}</p>
        <p className="mt-0.5 text-sm leading-5 text-[#667085]">{body}</p>
      </div>
      <span className="inline-flex items-center gap-1 text-sm font-semibold text-[#5b76fe]">
        Open <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}

function SourceRow({ source }: { source: CanonicalSourceSummary }) {
  return (
    <div className="grid gap-2 border-b border-[#eef0f4] py-2 last:border-b-0 md:grid-cols-[minmax(0,1fr)_150px_110px] md:items-center">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-[#1c1c1e]">{source.label}</p>
        <p className="mt-0.5 text-xs text-[#8d92a3]">{source.kind}</p>
      </div>
      <span className={`w-fit rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass(source.status)}`}>
        {source.status_label}
      </span>
      <p className="text-sm text-[#555a6a] md:text-right">{formatNumber(source.total_resources)} facts</p>
    </div>
  );
}

export function PatientRecordOverview() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

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

  if (!patientId) {
    return (
      <StartStateCard
        icon={Database}
        eyebrow="Patient Record"
        title="Start with a sample chart before opening the record pipeline."
        body="Patient Record opens as a guided workspace for intake, harmonization, publish, and context capture. Select a synthetic sample chart first so the module can load with coherent chart context."
        bullets={[
          "Review what sources exist and which ones still need preparation.",
          "Open harmonization and publish steps with one consistent patient context.",
          "Keep the first page simple before expanding into deeper record operations.",
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
  const chartName = canonical?.patient_name || overview?.name;
  const sourceCount = canonical?.source_count ?? 0;
  const preparedSourceCount = canonical?.prepared_source_count ?? 0;
  const needsPreparationCount = canonical?.needs_preparation_count ?? Math.max(sourceCount - preparedSourceCount, 0);
  const reviewItemCount = canonical?.review_item_count ?? 0;
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
  const chartStatus = !patientId
    ? "No patient selected"
    : !canonical
      ? "Loading chart state"
      : sourceCount === 0
        ? "No sources connected"
        : needsPreparationCount > 0
          ? "Sources need preparation"
          : reviewItemCount > 0
            ? "Review needed before publish"
            : "Ready for downstream modules";

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
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
          <div className="min-w-0">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <Database size={13} />
              Module Overview
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-[#1c1c1e] lg:text-3xl">
              {chartName ? `${chartName}'s FHIR Chart` : "Patient-owned FHIR Chart"}
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#667085]">
              This is the operating view for the canonical chart: what data has been collected, what is usable, and what still blocks downstream modules.
            </p>
          </div>

          <div className="border-t border-[#eef0f4] pt-4 lg:border-l lg:border-t-0 lg:pl-5 lg:pt-0">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-[#1c1c1e]">{chartStatus}</p>
              <span className="text-sm font-semibold text-[#5b76fe]">{readinessPct}%</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#e9eaef]">
              <div className="h-full rounded-full bg-[#00b473]" style={{ width: `${readinessPct}%` }} />
            </div>
            <div className="mt-3 space-y-2 text-sm text-[#667085]">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-[#00b473]" />
                {preparedSourceCount}/{sourceCount} sources prepared
              </div>
              <div className="flex items-center gap-2">
                {reviewItemCount > 0 ? (
                  <AlertTriangle size={14} className="text-[#f59e0b]" />
                ) : (
                  <CheckCircle2 size={14} className="text-[#00b473]" />
                )}
                {reviewItemCount} review items
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-[#dfe4ea] bg-white p-5">
        <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Data aggregation</p>
            <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">Current chart posture</h2>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              Aggregation should answer three questions without ceremony: how many sources are connected, how much is prepared, and what still needs review.
            </p>

            <div className="mt-5 grid gap-4 border-y border-[#eef0f4] py-4 sm:grid-cols-2">
              <MetricText label="Sources" value={formatNumber(sourceCount)} note={`${preparedSourceCount} prepared`} />
              <MetricText label="Prepared facts" value={formatNumber(chartFactTotal)} note="available to chart views" />
              <MetricText label="Needs preparation" value={formatNumber(needsPreparationCount)} note="PDFs or files pending processing" />
              <MetricText label="Review items" value={formatNumber(reviewItemCount)} note="conflicts or unresolved decisions" />
            </div>

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

          <div>
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-[#1c1c1e]">Sources feeding this chart</h3>
              {canonical?.storage_mode && <span className="text-xs text-[#8d92a3]">{canonical.storage_mode}</span>}
            </div>
            <div className="mt-3 rounded-lg border border-[#eef0f4] px-3">
              {canonicalQ.isLoading && <p className="py-3 text-sm text-[#667085]">Loading source summary...</p>}
              {!canonicalQ.isLoading && canonical?.sources.length ? (
                canonical.sources.slice(0, 6).map((source) => <SourceRow key={source.id} source={source} />)
              ) : !canonicalQ.isLoading ? (
                <p className="py-3 text-sm text-[#667085]">No connected sources yet. Start in Source Intake.</p>
              ) : null}
            </div>
            {canonical && canonical.sources.length > 6 && (
              <p className="mt-2 text-xs text-[#667085]">Showing 6 of {canonical.sources.length} sources.</p>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-lg border border-[#dfe4ea] bg-white p-5">
          <div className="flex items-center gap-2">
            <UserRound size={17} className="text-[#5b76fe]" />
            <h2 className="text-base font-semibold text-[#1c1c1e]">Patient facts in the chart</h2>
          </div>
          <div className="mt-4">
            {!patientId && (
              <p className="text-sm leading-6 text-[#667085]">Select a patient from the header to populate this overview.</p>
            )}
            {patientId && overviewQ.isLoading && !patientId.startsWith("workspace-") && (
              <p className="text-sm leading-6 text-[#667085]">Loading patient facts...</p>
            )}
            {factLines.map(([label, value]) => (
              <FactLine key={label} label={label} value={value} />
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-[#dfe4ea] bg-white p-5">
          <div className="flex items-center gap-2">
            <ShieldCheck size={17} className="text-[#0f766e]" />
            <h2 className="text-base font-semibold text-[#1c1c1e]">Open the chart views</h2>
          </div>
          <div className="mt-3">
            <ChartLinkRow
              icon={BarChart3}
              title="Clinical Snapshot"
              body="Demographics, active problems, medications, allergies, labs, and provenance."
              to={withPatient("/fhir-charts", patientId)}
            />
            <ChartLinkRow
              icon={CalendarDays}
              title="History"
              body="Longitudinal encounters, conditions, medications, procedures, and immunizations."
              to={withPatient("/fhir-charts/history", patientId)}
            />
            <ChartLinkRow
              icon={Heart}
              title="Care Journey"
              body="Medication episodes, conditions, and care activity on one timeline."
              to={withPatient("/fhir-charts/care-journey", patientId)}
            />
            <ChartLinkRow
              icon={FileBarChart}
              title="Labs and Observations"
              body="Latest observations and raw patient data available to downstream modules."
              to={withPatient("/fhir-charts/patient-data", patientId)}
            />
            <ChartLinkRow
              icon={Share2}
              title="Sharing Packet"
              body="Create a scoped packet for a care team or second opinion."
              to={withPatient("/sharing", patientId)}
            />
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-[#dfe4ea] bg-[#f7f9fc] p-5">
        <div className="grid gap-3 text-sm leading-6 text-[#667085] md:grid-cols-3">
          <div className="flex gap-2">
            <Activity size={16} className="mt-1 shrink-0 text-[#5b76fe]" />
            <p><span className="font-semibold text-[#1c1c1e]">Collect:</span> add portal exports, PDFs, labs, pharmacy records, and other patient-held files.</p>
          </div>
          <div className="flex gap-2">
            <ListChecks size={16} className="mt-1 shrink-0 text-[#5b76fe]" />
            <p><span className="font-semibold text-[#1c1c1e]">Clean:</span> prepare sources into consistent chart facts with provenance intact.</p>
          </div>
          <div className="flex gap-2">
            <FileJson2 size={16} className="mt-1 shrink-0 text-[#5b76fe]" />
            <p><span className="font-semibold text-[#1c1c1e]">Use:</span> publish the reviewed chart into FHIR Charts, Caspian, and marketplace modules.</p>
          </div>
        </div>
      </section>
    </main>
  );
}
