import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, ChevronRight, Clock3, TestTubeDiagonal } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { KeyLabsResponse, LabValue, PatientOverview } from "../../types";

function fmtDate(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return date.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function latestLabDate(labs: LabValue[]): string | null {
  const timestamp = labs.reduce((latest, lab) => {
    const current = lab.effective_dt ? new Date(lab.effective_dt).getTime() : Number.NEGATIVE_INFINITY;
    return Number.isNaN(current) ? latest : Math.max(latest, current);
  }, Number.NEGATIVE_INFINITY);
  return timestamp === Number.NEGATIVE_INFINITY ? null : new Date(timestamp).toISOString();
}

function trendSymbol(trend: LabValue["trend"]): string {
  if (trend === "up") return "Up";
  if (trend === "down") return "Down";
  if (trend === "stable") return "Stable";
  return "-";
}

function flattenLabs(keyLabs: KeyLabsResponse | undefined): LabValue[] {
  if (!keyLabs) return [];
  return Object.values(keyLabs.panels).flat();
}

function LabCategoryPanel({ name, labs }: { name: string; labs: LabValue[] }) {
  const [open, setOpen] = useState(true);
  const latest = latestLabDate(labs);

  return (
    <section className="overflow-hidden rounded-xl border border-[#e1e6ef] bg-white">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 border-b border-[#eef0f4] bg-[#f8fafc] px-4 py-3 text-left"
      >
        <div>
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-[#1c1c1e]">{name}</p>
            <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-[#667085]">{labs.length} values</span>
          </div>
          <p className="mt-1 text-xs text-[#667085]">Latest {fmtDate(latest)}</p>
        </div>
        {open ? <ChevronDown size={16} className="text-[#98a2b3]" /> : <ChevronRight size={16} className="text-[#98a2b3]" />}
      </button>

      {open && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[780px] text-sm">
            <thead>
              <tr className="border-b border-[#eef0f4] text-left text-xs uppercase tracking-[0.12em] text-[#98a2b3]">
                <th className="px-4 py-3 font-semibold">Marker</th>
                <th className="px-4 py-3 text-right font-semibold">Latest value</th>
                <th className="px-4 py-3 text-center font-semibold">Trend</th>
                <th className="px-4 py-3 text-right font-semibold">Date</th>
                <th className="px-4 py-3 font-semibold">History</th>
              </tr>
            </thead>
            <tbody>
              {labs.map((lab) => (
                <tr key={`${lab.loinc_code}-${lab.effective_dt ?? "undated"}-${lab.display}`} className="border-b border-[#f2f4f7] last:border-0">
                  <td className="px-4 py-3">
                    <p className="font-semibold text-[#1c1c1e]">{lab.display}</p>
                    <p className="mt-0.5 text-xs text-[#98a2b3]">LOINC {lab.loinc_code}</p>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {lab.value == null ? (
                      <span className="text-[#98a2b3]">-</span>
                    ) : (
                      <span className={lab.is_abnormal ? "font-semibold text-[#b42318]" : "font-semibold text-[#1c1c1e]"}>
                        {lab.value} <span className="text-xs font-medium text-[#667085]">{lab.unit}</span>
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center text-xs font-semibold text-[#667085]">{trendSymbol(lab.trend)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-[#667085]">{fmtDate(lab.effective_dt)}</td>
                  <td className="px-4 py-3 text-[#667085]">
                    {lab.history?.length ? `${lab.history.length} point${lab.history.length === 1 ? "" : "s"}` : "Single result"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function LabsContent({
  overview,
  keyLabs,
}: {
  overview: PatientOverview;
  keyLabs: KeyLabsResponse;
}) {
  const populatedPanels = useMemo(
    () => Object.entries(keyLabs.panels).filter(([, labs]) => labs.length > 0),
    [keyLabs.panels],
  );
  const allLabs = useMemo(() => flattenLabs(keyLabs), [keyLabs]);
  const abnormalCount = allLabs.filter((lab) => lab.is_abnormal).length;
  const latest = latestLabDate(allLabs);

  return (
    <main className="mx-auto w-full max-w-7xl space-y-5 p-8">
      <section className="rounded-3xl border border-[#d8f3ec] bg-[#f3fffb] p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-white/75 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#087d75]">
              <TestTubeDiagonal size={14} />
              Lab History
            </div>
            <h1 className="text-2xl font-semibold text-[#111827]">{overview.name}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#3f635f]">
              Consolidated lab markers from the active chart snapshot, grouped for trend review and downstream clinical interpretation.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-xl border border-[#d8f3ec] bg-white px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#667085]">Markers</p>
              <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{allLabs.length}</p>
            </div>
            <div className="rounded-xl border border-[#d8f3ec] bg-white px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#667085]">Latest</p>
              <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{fmtDate(latest)}</p>
            </div>
            <div className="rounded-xl border border-[#d8f3ec] bg-white px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#667085]">Flagged</p>
              <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{abnormalCount}</p>
            </div>
          </div>
        </div>
      </section>

      {keyLabs.alert_flags.length > 0 && (
        <section className="rounded-xl border border-[#fedf89] bg-[#fffbeb] p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-[#b54708]" />
            <div>
              <p className="text-sm font-semibold text-[#7a2e0e]">{keyLabs.alert_flags.length} lab alert{keyLabs.alert_flags.length === 1 ? "" : "s"} found</p>
              <p className="mt-1 text-sm leading-6 text-[#92400e]">
                Alerts are generated from available structured lab values and should be reviewed against source context before clinical use.
              </p>
            </div>
          </div>
        </section>
      )}

      <section className="rounded-xl border border-[#e1e6ef] bg-white p-4">
        <div className="flex items-center gap-2">
          <Clock3 size={16} className="text-[#667085]" />
          <p className="text-sm font-semibold text-[#1c1c1e]">Recent lab activity</p>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {(keyLabs.timeline_events ?? []).slice(-8).map((month) => (
            <div key={month.month} className="rounded-lg border border-[#eef0f4] bg-[#f8fafc] px-3 py-2">
              <p className="text-xs font-semibold text-[#1c1c1e]">{month.label}</p>
              <p className="mt-1 text-xs text-[#667085]">{month.events.length} result{month.events.length === 1 ? "" : "s"}</p>
            </div>
          ))}
          {keyLabs.timeline_events.length === 0 && <p className="text-sm text-[#667085]">No recent lab timeline events found.</p>}
        </div>
      </section>

      {populatedPanels.length === 0 ? (
        <section className="rounded-xl border border-[#e1e6ef] bg-white p-8 text-center text-sm text-[#667085]">
          No quantitative lab values found in the active chart snapshot.
        </section>
      ) : (
        <div className="space-y-3">
          {populatedPanels.map(([name, labs]) => (
            <LabCategoryPanel key={name} name={name} labs={labs} />
          ))}
        </div>
      )}
    </main>
  );
}

export function ExplorerLabs() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });
  const keyLabsQ = useQuery({
    queryKey: ["key-labs", patientId],
    queryFn: () => api.getKeyLabs(patientId!),
    enabled: !!patientId,
  });

  if (!patientId) {
    return (
      <EmptyState
        icon={TestTubeDiagonal}
        title="Select a patient to review lab history"
        bullets={[
          "Group lab values by panel",
          "Review latest values and trend direction",
          "Use published chart data as the source of truth",
        ]}
      />
    );
  }

  if (overviewQ.isLoading || keyLabsQ.isLoading) {
    return (
      <div className="mx-auto w-full max-w-7xl space-y-4 p-8">
        <div className="h-40 animate-pulse rounded-3xl bg-[#e9eaef]" />
        <div className="h-20 animate-pulse rounded-xl bg-[#e9eaef]" />
        <div className="h-96 animate-pulse rounded-xl bg-[#e9eaef]" />
      </div>
    );
  }

  if (overviewQ.isError || keyLabsQ.isError || !overviewQ.data || !keyLabsQ.data) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load lab history for this patient.</p>
      </div>
    );
  }

  return <LabsContent overview={overviewQ.data} keyLabs={keyLabsQ.data} />;
}
