import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
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
  Layers3,
  ListChecks,
  Share2,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../../api/client";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${patientId}` : path;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "Unknown";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

type Tone = "blue" | "teal" | "amber" | "slate";

const toneClasses: Record<Tone, { band: string; label: string; icon: string; soft: string }> = {
  blue: {
    band: "border-[#dfe4ff] bg-[#f7f8ff]",
    label: "text-[#5b76fe]",
    icon: "bg-[#eef1ff] text-[#5b76fe]",
    soft: "bg-[#eef1ff] text-[#5b76fe]",
  },
  teal: {
    band: "border-[#cdeee9] bg-[#f4fffc]",
    label: "text-[#0f766e]",
    icon: "bg-[#c3faf5] text-[#187574]",
    soft: "bg-[#e7fbf7] text-[#0f766e]",
  },
  amber: {
    band: "border-[#f6dfc9] bg-[#fff8f1]",
    label: "text-[#9a5a16]",
    icon: "bg-[#ffe6cd] text-[#744000]",
    soft: "bg-[#fff1df] text-[#9a5a16]",
  },
  slate: {
    band: "border-[#dfe3ea] bg-[#f7f8fb]",
    label: "text-[#555a6a]",
    icon: "bg-[#eef0f5] text-[#555a6a]",
    soft: "bg-[#eef0f5] text-[#555a6a]",
  },
};

function SectionBand({
  label,
  title,
  body,
  tone = "blue",
  children,
}: {
  label: string;
  title: string;
  body: string;
  tone?: Tone;
  children: ReactNode;
}) {
  return (
    <section className={`space-y-4 rounded-[24px] border p-4 lg:p-5 ${toneClasses[tone].band}`}>
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <p className={`text-xs font-semibold uppercase tracking-wider ${toneClasses[tone].label}`}>{label}</p>
          <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">{title}</h2>
        </div>
        <p className="max-w-xl text-sm leading-6 text-[#667085]">{body}</p>
      </div>
      {children}
    </section>
  );
}

function StatCard({ label, value, note, tone = "blue" }: { label: string; value: string; note: string; tone?: Tone }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <p className={`text-[10px] font-semibold uppercase tracking-wider ${toneClasses[tone].label}`}>{label}</p>
      <p className="mt-2 text-2xl font-semibold text-[#1c1c1e]">{value}</p>
      <p className="mt-1 text-sm text-[#667085]">{note}</p>
    </div>
  );
}

function ActionCard({
  icon: Icon,
  title,
  body,
  to,
  action,
  tone = "blue",
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  to: string;
  action: string;
  tone?: Tone;
}) {
  return (
    <Link
      to={to}
      className="group flex min-h-[220px] flex-col rounded-2xl bg-white p-5 no-underline shadow-[rgb(224_226_232)_0px_0px_0px_1px] transition-colors hover:bg-[#fbfcff]"
    >
      <div className="flex items-start justify-between gap-4">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${toneClasses[tone].icon}`}>
          <Icon size={18} />
        </div>
        <ArrowRight size={16} className="mt-1 text-[#a5a8b5] transition-colors group-hover:text-[#5b76fe]" />
      </div>
      <h2 className="mt-4 text-base font-semibold text-[#1c1c1e]">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
      <div className="mt-auto pt-5 text-sm font-semibold text-[#5b76fe]">{action}</div>
    </Link>
  );
}

export function PatientRecordOverview() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId && !patientId.startsWith("workspace-"),
  });

  const canonicalQ = useQuery({
    queryKey: ["canonical-summary", patientId],
    queryFn: () => api.getCanonicalSummary(patientId!),
    enabled: !!patientId,
  });

  const overview = overviewQ.data;
  const canonical = canonicalQ.data;
  const chartName = canonical?.patient_name || overview?.name;
  const readinessPct = canonical
    ? Math.max(
        0,
        Math.min(
          100,
          Math.round(
            canonical.source_count > 0
              ? (canonical.prepared_source_count / canonical.source_count) * 100 - Math.min(canonical.review_item_count * 4, 20)
              : 0,
          ),
        ),
      )
    : 78;

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <Database size={13} />
          Module Overview
            </p>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
              {chartName ? `${chartName}'s FHIR Chart` : "The patient-owned FHIR Chart"}
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-[#667085]">
              This page reads from the canonical patient workspace: source files are collected, prepared, and exposed as
              one source-aware chart for downstream modules.
            </p>
          </div>

          <div className="min-w-[260px] rounded-2xl bg-[#fafbff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Activation readiness</p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#e9eaef]">
              <div className="h-full rounded-full bg-[#00b473]" style={{ width: `${readinessPct}%` }} />
            </div>
            <p className="mt-3 text-sm font-semibold text-[#1c1c1e]">{readinessPct}% module-ready</p>
            <div className="mt-3 space-y-2 text-sm text-[#667085]">
              <div className="flex items-center gap-2"><CheckCircle2 size={14} className="text-[#00b473]" /> Workspace selected</div>
              <div className="flex items-center gap-2"><CheckCircle2 size={14} className="text-[#00b473]" /> {canonical?.prepared_source_count ?? 0} prepared sources</div>
              <div className="flex items-center gap-2"><AlertTriangle size={14} className="text-[#f59e0b]" /> {canonical?.review_item_count ?? 0} review items</div>
            </div>
          </div>
        </div>
      </section>

      <SectionBand
        label="Chart Takeaways"
        title="What this page should tell you quickly"
        body="Start here to know whether the chart has enough connected data, what is usable, and what still needs review."
        tone="blue"
      >
        <div className="grid gap-4 md:grid-cols-3">
          <StatCard
            label="Data gathered"
            value={`${canonical?.source_count ?? 0} sources`}
            note={`${canonical?.prepared_source_count ?? 0} prepared for canonical use`}
            tone="blue"
          />
          <StatCard
            label="Usable chart facts"
            value={(canonical?.total_resources ?? overview?.total_resources ?? 0).toLocaleString()}
            note="Prepared resources available to downstream modules"
            tone="teal"
          />
          <StatCard
            label="Needs review"
            value={`${canonical?.review_item_count ?? 0} items`}
            note="Unprepared sources or source conflicts before module activation"
            tone="amber"
          />
        </div>
      </SectionBand>

      <section className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="rounded-[24px] border border-[#cdeee9] bg-[#f4fffc] p-5">
          <div className="flex items-center gap-2">
            <ShieldCheck size={18} className="text-[#0f766e]" />
            <h2 className="text-lg font-semibold text-[#1c1c1e]">How the chart gets made</h2>
          </div>
          <div className="mt-5 grid gap-3">
            {[
              ["Collect", "Bring patient records together from portals, files, clinics, labs, pharmacies, and payers."],
              ["Clean", "Turn raw FHIR and other formats into consistent chart facts."],
              ["Check", "Preserve source links and flag conflicts before any module acts on the chart."],
              ["Use", "Send clean chart facts into Clinical Insights, Marketplace modules, and sharing packets."],
            ].map(([title, body]) => (
              <div key={title} className="rounded-xl border border-[#e9eaef] p-4">
                <p className="text-sm font-semibold text-[#1c1c1e]">{title}</p>
                <p className="mt-1 text-sm leading-6 text-[#667085]">{body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[24px] border border-[#f6dfc9] bg-[#fff8f1] p-5">
          <div className="flex items-center gap-2">
            <Layers3 size={18} className="text-[#9a5a16]" />
            <h2 className="text-lg font-semibold text-[#1c1c1e]">Selected patient</h2>
          </div>
          <div className="mt-5 space-y-3">
            {!patientId && (
              <div className="rounded-xl border border-dashed border-[#d5d9e5] p-5">
                <div className="flex items-center gap-2">
                  <UserRound size={16} className="text-[#a5a8b5]" />
                  <p className="text-sm font-semibold text-[#1c1c1e]">Select a patient to populate this chart.</p>
                </div>
                <p className="mt-2 text-sm leading-6 text-[#667085]">
                  The top patient selector sets the patient context for record, marketplace, and module views.
                </p>
              </div>
            )}
            {patientId && overviewQ.isLoading && <div className="h-40 animate-pulse rounded-xl bg-[#e9eaef]" />}
            {overview && (
              <>
                <div className="rounded-xl bg-[#fafbff] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Demographics</p>
                  <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                    {Math.floor(overview.age_years)} years · {overview.gender}
                  </p>
                </div>
                <div className="rounded-xl bg-[#fafbff] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Record span</p>
                  <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                    {formatDate(overview.earliest_encounter_dt)} to {formatDate(overview.latest_encounter_dt)}
                  </p>
                </div>
                <div className="rounded-xl bg-[#fafbff] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Module-ready facts</p>
                  <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                    {canonical?.canonical_condition_count ?? overview.active_condition_count} conditions ·{" "}
                    {canonical?.canonical_medication_count ?? overview.active_med_count} meds ·{" "}
                    {canonical?.encounter_count ?? overview.encounter_count} encounters
                  </p>
                </div>
              </>
            )}
            {patientId && !overview && !overviewQ.isLoading && canonical && (
              <>
                <div className="rounded-xl bg-[#fafbff] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Workspace</p>
                  <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">{canonical.workspace_id}</p>
                </div>
                <div className="rounded-xl bg-[#fafbff] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Record span</p>
                  <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                    {formatDate(canonical.date_start)} to {formatDate(canonical.date_end)}
                  </p>
                </div>
                <div className="rounded-xl bg-[#fafbff] p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Canonical source posture</p>
                  <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                    {canonical.source_count} sources · {canonical.total_resources.toLocaleString()} prepared resources
                  </p>
                </div>
              </>
            )}
          </div>
        </div>
      </section>

      <SectionBand
        label="FHIR Charts"
        title="What you can do with this chart"
        body="Open the working views that make the chart useful: a snapshot, timeline, latest observations, source data, and sharing packet."
        tone="teal"
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <ActionCard
            icon={BarChart3}
            title="Chart Snapshot"
            body="A fast patient summary with active problems, medications, allergies, labs, and provenance."
            to={withPatient("/explorer", patientId)}
            action="Open snapshot"
            tone="blue"
          />
          <ActionCard
            icon={Activity}
            title="Medication Episodes"
            body="Convert fragmented FHIR medication requests into active therapy windows and hold candidates."
            to={withPatient("/explorer/care-journey", patientId)}
            action="Review episodes"
            tone="amber"
          />
          <ActionCard
            icon={FileBarChart}
            title="Latest Observations"
            body="Show the most recent labs and vitals that matter for downstream modules."
            to={withPatient("/explorer/patient-data", patientId)}
            action="Inspect observations"
            tone="teal"
          />
          <ActionCard
            icon={ListChecks}
            title="Critical Review Queue"
            body="Highlight stale status, conflicting facts, inferred values, and fields that need human review."
            to={withPatient("/sharing", patientId)}
            action="Open review queue"
            tone="slate"
          />
        </div>
      </SectionBand>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <ActionCard
          icon={UserRound}
          title="Summary"
          body="Clinician-readable patient summary with demographics, active problems, medications, allergies, and labs."
          to={withPatient("/explorer", patientId)}
          action="Open summary"
        />
        <ActionCard
          icon={CalendarDays}
          title="History"
          body="Longitudinal tables and timelines for encounters, medications, procedures, and immunizations."
          to={withPatient("/explorer/history", patientId)}
          action="Open history"
          tone="slate"
        />
        <ActionCard
          icon={Heart}
          title="Care Journey"
          body="Visual timeline of medication episodes, conditions, and care activity."
          to={withPatient("/explorer/care-journey", patientId)}
          action="Open timeline"
          tone="teal"
        />
        <ActionCard
          icon={FileJson2}
          title="Source Data"
          body="FHIR bundle metrics, resource distribution, and data quality signals."
          to={withPatient("/explorer/patient-data", patientId)}
          action="Open FHIR data"
          tone="amber"
        />
        <ActionCard
          icon={Share2}
          title="Sharing"
          body="Build a second-opinion or care-team packet from this FHIR Chart."
          to={withPatient("/sharing", patientId)}
          action="Build packet"
        />
      </section>
    </main>
  );
}
