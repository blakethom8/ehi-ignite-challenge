import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Braces, Database, FileJson2, Layers3, User } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import { FhirViewer } from "../../components/FhirViewer";
import type { PatientOverview } from "../../types";

const CATEGORY_STYLES: Record<string, { bg: string; text: string; bar: string }> = {
  Clinical: { bg: "#eef1ff", text: "#3730a3", bar: "#5b76fe" },
  Billing: { bg: "#fffbeb", text: "#92400e", bar: "#f59e0b" },
  Administrative: { bg: "#f5f6f8", text: "#555a6a", bar: "#9ca3af" },
};

function DataMetric({
  label,
  value,
  note,
}: {
  label: string;
  value: string | number;
  note?: string;
}) {
  return (
    <div className="rounded-xl border border-[#e9eaef] bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#a5a8b5]">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-[#111827]">{value}</p>
      {note && <p className="mt-1 text-xs text-[#6b7280]">{note}</p>}
    </div>
  );
}

function ResourceDistribution({ overview }: { overview: PatientOverview }) {
  const maxCount = Math.max(...overview.resource_type_counts.map((item) => item.count), 1);
  const sorted = [...overview.resource_type_counts].sort((a, b) => b.count - a.count);

  return (
    <section className="rounded-2xl border border-[#e9eaef] bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-[#1c1c1e]">FHIR Resource Distribution</h2>
          <p className="mt-1 text-sm text-[#6b7280]">
            Development-facing bundle composition by FHIR resource type.
          </p>
        </div>
        <span className="rounded-full bg-[#f5f6f8] px-3 py-1 text-xs font-semibold text-[#555a6a]">
          {overview.resource_type_counts.length} resource types
        </span>
      </div>

      <div className="mt-5 space-y-3">
        {sorted.map((item) => {
          const colors = CATEGORY_STYLES[item.category] ?? CATEGORY_STYLES.Administrative;
          const pct = Math.max(4, (item.count / maxCount) * 100);
          return (
            <div key={item.resource_type} className="grid gap-2 sm:grid-cols-[170px_1fr_88px] sm:items-center">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-medium text-[#1c1c1e]">{item.resource_type}</span>
                <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ backgroundColor: colors.bg, color: colors.text }}>
                  {item.category}
                </span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-[#eef0f6]">
                <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: colors.bar }} />
              </div>
              <p className="text-right text-sm font-semibold text-[#111827]">{item.count.toLocaleString()}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function DataNotes({ overview }: { overview: PatientOverview }) {
  return (
    <section className="rounded-2xl border border-[#d8f3ec] bg-[#f3fffb] p-5">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-[#087d75]">
          <Layers3 size={18} />
        </div>
        <div>
          <h2 className="text-base font-semibold text-[#087d75]">Development Data View</h2>
          <p className="mt-1 text-sm leading-6 text-[#3f635f]">
            These metrics are useful for validating FHIR bundle shape, parser coverage, and demo data quality.
            They are separated from Overview because they are not primary clinical decision information.
          </p>
          {overview.parse_warning_count > 0 && (
            <div className="mt-3 flex items-start gap-2 rounded-xl border border-[#f59e0b] bg-[#fffbeb] px-3 py-2 text-sm text-[#92400e]">
              <AlertCircle size={15} className="mt-0.5 shrink-0" />
              <span>{overview.parse_warning_count} parse warnings encountered for this bundle.</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export function ExplorerPatientData() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const [showFhir, setShowFhir] = useState(false);

  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });

  if (!patientId) {
    return (
      <EmptyState
        icon={User}
        title="No patient selected"
        bullets={[
          "Select a patient from the top bar",
          "Inspect FHIR bundle metrics and resource distribution",
          "Open raw FHIR when validating parser behavior",
        ]}
      />
    );
  }

  if (overviewQ.isLoading) {
    return (
      <div className="mx-auto max-w-6xl space-y-5 p-8">
        <div className="h-32 animate-pulse rounded-2xl bg-[#e9eaef]" />
        <div className="grid gap-3 md:grid-cols-4">
          <div className="h-28 animate-pulse rounded-xl bg-[#e9eaef]" />
          <div className="h-28 animate-pulse rounded-xl bg-[#e9eaef]" />
          <div className="h-28 animate-pulse rounded-xl bg-[#e9eaef]" />
          <div className="h-28 animate-pulse rounded-xl bg-[#e9eaef]" />
        </div>
        <div className="h-96 animate-pulse rounded-2xl bg-[#e9eaef]" />
      </div>
    );
  }

  if (overviewQ.isError || !overviewQ.data) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load patient data metrics.</p>
      </div>
    );
  }

  const overview = overviewQ.data;
  const clinicalPct = 100 - overview.billing_pct;

  return (
    <main className="mx-auto max-w-6xl space-y-5 p-8">
      <section className="rounded-3xl border border-[#d8f3ec] bg-[#f3fffb] p-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-white/75 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#087d75]">
              <Database size={14} />
              Patient FHIR data
            </div>
            <h1 className="text-3xl font-semibold text-[#111827]">{overview.name}</h1>
            <p className="mt-2 max-w-3xl text-base leading-7 text-[#3f635f]">
              Bundle composition, raw FHIR access, and parser-facing metrics for development and data quality review.
            </p>
          </div>
          <button
            onClick={() => setShowFhir(true)}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-[#95ded1] bg-white px-4 py-2 text-sm font-semibold text-[#087d75] hover:bg-[#e7fbf6]"
          >
            <Braces size={16} />
            View raw FHIR
          </button>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-4">
        <DataMetric label="Total resources" value={overview.total_resources.toLocaleString()} />
        <DataMetric label="Clinical resources" value={overview.clinical_resource_count.toLocaleString()} note={`${clinicalPct.toFixed(0)}% of total`} />
        <DataMetric label="Billing resources" value={overview.billing_resource_count.toLocaleString()} note={`${overview.billing_pct.toFixed(0)}% of total`} />
        <DataMetric label="Unique lab types" value={overview.unique_loinc_count} />
      </section>

      <section className="grid gap-3 md:grid-cols-4">
        <DataMetric label="Encounters" value={overview.encounter_count} />
        <DataMetric label="Years of history" value={overview.years_of_history.toFixed(1)} />
        <DataMetric label="Avg resources / encounter" value={overview.avg_resources_per_encounter.toFixed(1)} />
        <DataMetric label="Parse warnings" value={overview.parse_warning_count} />
      </section>

      <ResourceDistribution overview={overview} />

      <section className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-[#e9eaef] bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <FileJson2 size={17} className="text-[#5b76fe]" />
            <h2 className="text-base font-semibold text-[#1c1c1e]">Encounter Classes</h2>
          </div>
          <div className="mt-4 space-y-2">
            {Object.entries(overview.encounter_class_breakdown).map(([label, count]) => (
              <div key={label || "unknown"} className="flex items-center justify-between rounded-lg bg-[#f9fafb] px-3 py-2 text-sm">
                <span className="text-[#555a6a]">{label || "Unknown"}</span>
                <span className="font-semibold text-[#111827]">{count}</span>
              </div>
            ))}
          </div>
        </section>

        <DataNotes overview={overview} />
      </section>

      {showFhir && (
        <FhirViewer
          patientId={patientId}
          patientName={overview.name}
          onClose={() => setShowFhir(false)}
        />
      )}
    </main>
  );
}
