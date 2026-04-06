import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Beaker, ShieldAlert, TestTubeDiagonal } from "lucide-react";
import { api } from "../../api/client";
import type { FieldCoverageItem } from "../../types";

const COVERAGE_STYLES: Record<FieldCoverageItem["coverage_label"], string> = {
  Always: "bg-[#d8f5ee] text-[#0f766e]",
  Usually: "bg-[#dbeafe] text-[#1d4ed8]",
  Sometimes: "bg-[#ffedd5] text-[#9a3412]",
  Rarely: "bg-[#fee2e2] text-[#991b1b]",
};

function CoverageBar({ pct }: { pct: number }) {
  const bounded = Math.max(0, Math.min(100, pct));
  const tone = bounded >= 95 ? "#0f766e" : bounded >= 70 ? "#2563eb" : bounded >= 30 ? "#d97706" : "#dc2626";

  return (
    <div className="w-full">
      <div className="h-2.5 rounded-full bg-[#eef2f7]">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${bounded}%`, backgroundColor: tone }}
        />
      </div>
      <p className="mt-1 text-xs text-[#64748b]">{bounded.toFixed(1)}%</p>
    </div>
  );
}

function ResourceGroup({ type, items }: { type: string; items: FieldCoverageItem[] }) {
  return (
    <article className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <h2 className="text-sm font-semibold text-[#0f172a]">{type}</h2>
      <div className="mt-3 space-y-3">
        {items.map((field) => (
          <div key={field.field_path} className="rounded-xl border border-[#edf0f5] p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-[#0f172a]">{field.field_path}</p>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${COVERAGE_STYLES[field.coverage_label]}`}>
                {field.coverage_label}
              </span>
            </div>
            <div className="mt-2">
              <CoverageBar pct={field.coverage_pct} />
            </div>
            <p className="mt-1 text-xs text-[#64748b]">
              Present in {field.present_count.toLocaleString()} of {field.total_count.toLocaleString()} patients
            </p>
          </div>
        ))}
      </div>
    </article>
  );
}

export function AnalysisCoverage() {
  const { data: coverage, isLoading: coverageLoading } = useQuery({
    queryKey: ["field-coverage"],
    queryFn: api.getFieldCoverage,
    staleTime: Infinity,
  });

  const { data: allergy, isLoading: allergyLoading } = useQuery({
    queryKey: ["allergy-criticality"],
    queryFn: api.getAllergyCriticalityBreakdown,
    staleTime: Infinity,
  });

  const grouped = useMemo(() => {
    if (!coverage) return [] as [string, FieldCoverageItem[]][];

    const groups = new Map<string, FieldCoverageItem[]>();
    for (const item of coverage.fields) {
      const list = groups.get(item.resource_type);
      if (list) {
        list.push(item);
      } else {
        groups.set(item.resource_type, [item]);
      }
    }

    for (const items of groups.values()) {
      items.sort((a, b) => b.coverage_pct - a.coverage_pct);
    }

    return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [coverage]);

  const cautionFields = useMemo(() => {
    if (!coverage) return [] as FieldCoverageItem[];
    return coverage.fields
      .filter((field) => field.coverage_pct < 70)
      .sort((a, b) => a.coverage_pct - b.coverage_pct)
      .slice(0, 8);
  }, [coverage]);

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 lg:px-10">
      <section className="rounded-3xl border border-[#d0e9e3] bg-[linear-gradient(145deg,#f8fffd_0%,#effbf7_40%,#f8fffd_100%)] p-6 lg:p-8">
        <p className="inline-flex items-center gap-2 rounded-full bg-[#d8f5ee] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#0f766e]">
          <TestTubeDiagonal size={13} />
          Coverage and Reliability
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#0f172a] lg:text-4xl">
          Field Coverage and Data Quality Signals
        </h1>
        <p className="mt-3 max-w-4xl text-sm leading-6 text-[#35524d] lg:text-base">
          Use this page to understand which FHIR fields are consistently populated across the corpus and where
          interpretation should be cautious. Coverage labels are derived from corpus-level prevalence.
        </p>
      </section>

      <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <article className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#55706c]">Patients Profiled</p>
          <p className="mt-1 text-3xl font-semibold text-[#0f172a]">
            {coverageLoading ? "..." : coverage?.total_patients.toLocaleString() ?? "0"}
          </p>
        </article>

        <article className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#55706c]">Fields Tracked</p>
          <p className="mt-1 text-3xl font-semibold text-[#0f172a]">
            {coverageLoading ? "..." : coverage?.fields.length.toLocaleString() ?? "0"}
          </p>
        </article>

        <article className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#55706c]">Allergy Records</p>
          <p className="mt-1 text-3xl font-semibold text-[#0f172a]">
            {allergyLoading ? "..." : allergy?.total_allergy_records.toLocaleString() ?? "0"}
          </p>
        </article>

        <article className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#55706c]">High Criticality Patients</p>
          <p className="mt-1 text-3xl font-semibold text-[#0f172a]">
            {allergyLoading ? "..." : allergy?.patients_with_high_criticality.toLocaleString() ?? "0"}
          </p>
        </article>
      </section>

      <section className="mt-7 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-4">
          {coverageLoading && (
            <div className="h-60 animate-pulse rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]" />
          )}
          {!coverageLoading && grouped.map(([type, items]) => <ResourceGroup key={type} type={type} items={items} />)}
        </div>

        <div className="space-y-4">
          <article className="rounded-2xl border border-[#fed7aa] bg-[#fff7ed] p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-[#9a3412]">
              <AlertTriangle size={15} />
              Fields Requiring Caution
            </p>
            <div className="mt-3 space-y-2.5">
              {coverageLoading && <p className="text-sm text-[#9a3412]">Loading field coverage...</p>}
              {!coverageLoading && cautionFields.length === 0 && (
                <p className="text-sm text-[#9a3412]">No low-coverage fields in the current profile.</p>
              )}
              {!coverageLoading && cautionFields.map((field) => (
                <div key={field.field_path} className="rounded-lg bg-white px-3 py-2">
                  <p className="text-sm font-medium text-[#7c2d12]">{field.field_path}</p>
                  <p className="text-xs text-[#9a3412]">{field.coverage_pct.toFixed(1)}% coverage</p>
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <p className="flex items-center gap-2 text-sm font-semibold text-[#0f172a]">
              <ShieldAlert size={15} className="text-[#0f766e]" />
              Allergy Category Mix
            </p>
            <div className="mt-3 space-y-2">
              {allergyLoading && <p className="text-sm text-[#64748b]">Loading allergy profile...</p>}
              {!allergyLoading &&
                Object.entries(allergy?.category_counts ?? {})
                  .sort((a, b) => b[1] - a[1])
                  .map(([category, count]) => (
                    <div key={category} className="flex items-center justify-between rounded-lg border border-[#edf0f5] px-3 py-2">
                      <p className="text-sm text-[#0f172a]">{category}</p>
                      <p className="text-sm font-semibold text-[#0f766e]">{count.toLocaleString()}</p>
                    </div>
                  ))}
            </div>
          </article>

          <article className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <p className="flex items-center gap-2 text-sm font-semibold text-[#0f172a]">
              <Beaker size={15} className="text-[#0f766e]" />
              Top Allergy Substances
            </p>
            <div className="mt-3 space-y-2">
              {allergyLoading && <p className="text-sm text-[#64748b]">Loading top substances...</p>}
              {!allergyLoading &&
                (allergy?.top_substances ?? []).slice(0, 8).map((entry) => (
                  <div key={`${entry.substance}-${entry.criticality}`} className="rounded-lg border border-[#edf0f5] px-3 py-2">
                    <p className="text-sm font-medium text-[#0f172a]">{entry.substance}</p>
                    <p className="text-xs text-[#64748b]">
                      {entry.count.toLocaleString()} records · criticality: {entry.criticality}
                    </p>
                  </div>
                ))}
            </div>
          </article>
        </div>
      </section>
    </div>
  );
}
