import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowDown, ArrowUp, Clock3, Minus, Search, TestTubeDiagonal } from "lucide-react";
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

function trendIcon(trend: LabValue["trend"]) {
  if (trend === "up") return <ArrowUp size={13} />;
  if (trend === "down") return <ArrowDown size={13} />;
  if (trend === "stable") return <Minus size={13} />;
  return <Minus size={13} />;
}

function trendTone(trend: LabValue["trend"]): string {
  if (trend === "up") return "border-[#dbeafe] bg-[#eff6ff] text-[#3151d3]";
  if (trend === "down") return "border-[#fee2e2] bg-[#fff1f2] text-[#b42318]";
  if (trend === "stable") return "border-[#dcfce7] bg-[#f0fdf4] text-[#087d75]";
  return "border-[#eef0f4] bg-[#f8fafc] text-[#667085]";
}

function flattenLabs(keyLabs: KeyLabsResponse | undefined): LabValue[] {
  if (!keyLabs) return [];
  return Object.values(keyLabs.panels).flat();
}

function labKey(lab: LabValue): string {
  return `${lab.loinc_code}-${lab.display}`;
}

function formatLabValue(lab: LabValue): string {
  if (lab.value == null) return "-";
  return `${lab.value}${lab.unit ? ` ${lab.unit}` : ""}`;
}

function Sparkline({ lab }: { lab: LabValue }) {
  const points = lab.history ?? [];
  if (points.length < 2) {
    return <span className="text-xs text-[#98a2b3]">Single result</span>;
  }

  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = max - min || 1;
  const width = 96;
  const height = 30;
  const polyline = points
    .map((point, index) => {
      const x = points.length === 1 ? width : (index / (points.length - 1)) * width;
      const y = height - ((point.value - min) / spread) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${lab.display} trend`}>
      <polyline
        points={polyline}
        fill="none"
        stroke={lab.trend === "down" ? "#f43f5e" : "#5b76fe"}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
      {points.map((point, index) => {
        const x = points.length === 1 ? width : (index / (points.length - 1)) * width;
        const y = height - ((point.value - min) / spread) * height;
        return <circle key={`${point.effective_dt ?? "undated"}-${index}`} cx={x} cy={y} r="2" fill={lab.trend === "down" ? "#f43f5e" : "#5b76fe"} />;
      })}
    </svg>
  );
}

function LabDetailPanel({ lab, panelName }: { lab: LabValue | null; panelName: string | null }) {
  if (!lab) {
    return (
      <aside className="rounded-xl border border-[#e1e6ef] bg-white p-5">
        <p className="text-sm font-semibold text-[#1c1c1e]">Select a marker</p>
        <p className="mt-2 text-sm leading-6 text-[#667085]">Choose a lab marker to inspect latest value, trend history, and source limitations.</p>
      </aside>
    );
  }

  const latest = lab.history?.[lab.history.length - 1];
  const previous = lab.history?.[lab.history.length - 2];
  const delta = latest && previous ? latest.value - previous.value : null;

  return (
    <aside className="space-y-4 rounded-xl border border-[#e1e6ef] bg-white p-5 lg:sticky lg:top-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#5b76fe]">{panelName ?? "Lab marker"}</p>
        <h2 className="mt-2 text-lg font-semibold text-[#111827]">{lab.display}</h2>
        <p className="mt-1 text-xs text-[#667085]">LOINC {lab.loinc_code}</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-[#e1e6ef] bg-[#f8fafc] p-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#667085]">Latest</p>
          <p className="mt-1 text-xl font-semibold text-[#111827]">{formatLabValue(lab)}</p>
          <p className="mt-1 text-xs text-[#667085]">{fmtDate(lab.effective_dt)}</p>
        </div>
        <div className="rounded-lg border border-[#e1e6ef] bg-[#f8fafc] p-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#667085]">Trend</p>
          <div className={`mt-2 inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-semibold ${trendTone(lab.trend)}`}>
            {trendIcon(lab.trend)}
            {trendSymbol(lab.trend)}
          </div>
          <p className="mt-2 text-xs text-[#667085]">{delta == null ? "Need two results" : `${delta > 0 ? "+" : ""}${delta.toFixed(2)} since prior`}</p>
        </div>
      </div>

      <div className="rounded-lg border border-[#e1e6ef] p-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#667085]">History</p>
          <span className="text-xs text-[#98a2b3]">{lab.history?.length ?? 0} point{lab.history?.length === 1 ? "" : "s"}</span>
        </div>
        <div className="mt-3">
          <Sparkline lab={lab} />
        </div>
        <div className="mt-3 max-h-52 overflow-y-auto">
          {(lab.history ?? []).slice().reverse().map((point, index) => (
            <div key={`${point.effective_dt ?? "undated"}-${index}`} className="flex items-center justify-between border-t border-[#f2f4f7] py-2 text-sm">
              <span className="text-[#667085]">{fmtDate(point.effective_dt)}</span>
              <span className="font-semibold text-[#111827]">
                {point.value} <span className="text-xs font-medium text-[#667085]">{lab.unit}</span>
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-[#fedf89] bg-[#fffbeb] p-3 text-sm leading-6 text-[#92400e]">
        Reference ranges and abnormal interpretation are only shown when present in the source record. This source currently provides values without validated reference limits.
      </div>
    </aside>
  );
}

function LabsContent({
  overview,
  keyLabs,
}: {
  overview: PatientOverview;
  keyLabs: KeyLabsResponse;
}) {
  const [selectedPanel, setSelectedPanel] = useState("All");
  const [selectedLabKey, setSelectedLabKey] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const populatedPanels = useMemo(
    () => Object.entries(keyLabs.panels).filter(([, labs]) => labs.length > 0).sort(([a], [b]) => a.localeCompare(b)),
    [keyLabs.panels],
  );
  const allLabs = useMemo(() => flattenLabs(keyLabs), [keyLabs]);
  const abnormalCount = allLabs.filter((lab) => lab.is_abnormal || keyLabs.alert_flags.some((flag) => flag.loinc_code === lab.loinc_code)).length;
  const latest = latestLabDate(allLabs);
  const filteredLabs = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const panelLabs = selectedPanel === "All" ? allLabs : keyLabs.panels[selectedPanel] ?? [];
    return panelLabs
      .filter((lab) => {
        if (!normalized) return true;
        return `${lab.display} ${lab.loinc_code} ${lab.unit}`.toLowerCase().includes(normalized);
      })
      .sort((a, b) => a.display.localeCompare(b.display));
  }, [allLabs, keyLabs.panels, query, selectedPanel]);

  const selectedLab = useMemo(() => {
    return filteredLabs.find((lab) => labKey(lab) === selectedLabKey) ?? filteredLabs[0] ?? null;
  }, [filteredLabs, selectedLabKey]);
  const selectedLabPanel = useMemo(() => {
    if (!selectedLab) return null;
    return populatedPanels.find(([, labs]) => labs.some((lab) => labKey(lab) === labKey(selectedLab)))?.[0] ?? null;
  }, [populatedPanels, selectedLab]);

  return (
    <main className="mx-auto w-full max-w-7xl space-y-5 p-6">
      <section className="rounded-xl border border-[#d8f3ec] bg-[#f3fffb] p-5">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-white/75 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#087d75]">
              <TestTubeDiagonal size={14} />
              Lab History
            </div>
            <h1 className="text-2xl font-semibold text-[#111827]">{overview.name}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#3f635f]">
              Review lab markers from the active chart snapshot with trend history, panel grouping, and source limitations visible before interpretation.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-4">
            <div className="rounded-xl border border-[#d8f3ec] bg-white px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#667085]">Markers</p>
              <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{allLabs.length}</p>
            </div>
            <div className="rounded-xl border border-[#d8f3ec] bg-white px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#667085]">Latest</p>
              <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{fmtDate(latest)}</p>
            </div>
            <div className="rounded-xl border border-[#d8f3ec] bg-white px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#667085]">Panels</p>
              <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{populatedPanels.length}</p>
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

      {populatedPanels.length === 0 ? (
        <section className="rounded-xl border border-[#e1e6ef] bg-white p-8 text-center text-sm text-[#667085]">
          No quantitative lab values found in the active chart snapshot.
        </section>
      ) : (
        <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
          <div className="overflow-hidden rounded-xl border border-[#e1e6ef] bg-white">
            <div className="border-b border-[#eef0f4] p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-sm font-semibold text-[#1c1c1e]">Lab markers</p>
                  <p className="mt-1 text-sm text-[#667085]">Click a marker to inspect history and interpretation limits.</p>
                </div>
                <label className="relative block w-full lg:w-72">
                  <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#98a2b3]" />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search marker or LOINC"
                    className="h-10 w-full rounded-lg border border-[#d9dee8] bg-white pl-9 pr-3 text-sm outline-none focus:border-[#5b76fe] focus:ring-2 focus:ring-[#5b76fe]/20"
                  />
                </label>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {["All", ...populatedPanels.map(([name]) => name)].map((panel) => {
                  const count = panel === "All" ? allLabs.length : keyLabs.panels[panel]?.length ?? 0;
                  const active = selectedPanel === panel;
                  return (
                    <button
                      key={panel}
                      type="button"
                      onClick={() => {
                        setSelectedPanel(panel);
                        setSelectedLabKey(null);
                      }}
                      className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                        active ? "border-[#5b76fe] bg-[#eef2ff] text-[#3151d3]" : "border-[#e1e6ef] bg-white text-[#667085] hover:border-[#b8c1d4]"
                      }`}
                    >
                      {panel} <span className="ml-1 text-[#98a2b3]">{count}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-sm">
                <thead>
                  <tr className="border-b border-[#eef0f4] bg-[#f8fafc] text-left text-xs uppercase tracking-[0.12em] text-[#98a2b3]">
                    <th className="px-4 py-3 font-semibold">Marker</th>
                    <th className="px-4 py-3 text-right font-semibold">Latest</th>
                    <th className="px-4 py-3 text-center font-semibold">Trend</th>
                    <th className="px-4 py-3 font-semibold">History</th>
                    <th className="px-4 py-3 text-right font-semibold">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLabs.map((lab) => {
                    const active = selectedLab ? labKey(selectedLab) === labKey(lab) : false;
                    return (
                      <tr
                        key={labKey(lab)}
                        onClick={() => setSelectedLabKey(labKey(lab))}
                        className={`cursor-pointer border-b border-[#f2f4f7] last:border-0 ${active ? "bg-[#eef2ff]" : "hover:bg-[#f8fafc]"}`}
                      >
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[#1c1c1e]">{lab.display}</p>
                          <p className="mt-0.5 text-xs text-[#98a2b3]">LOINC {lab.loinc_code}</p>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span className={lab.is_abnormal ? "font-semibold text-[#b42318]" : "font-semibold text-[#1c1c1e]"}>{formatLabValue(lab)}</span>
                        </td>
                        <td className="px-4 py-3">
                          <div className={`mx-auto inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-semibold ${trendTone(lab.trend)}`}>
                            {trendIcon(lab.trend)}
                            {trendSymbol(lab.trend)}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Sparkline lab={lab} />
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-right text-[#667085]">{fmtDate(lab.effective_dt)}</td>
                      </tr>
                    );
                  })}
                  {filteredLabs.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-10 text-center text-sm text-[#667085]">
                        No lab markers match this filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="space-y-4">
            <LabDetailPanel lab={selectedLab} panelName={selectedLabPanel} />
            <section className="rounded-xl border border-[#e1e6ef] bg-white p-4">
              <div className="flex items-center gap-2">
                <Clock3 size={16} className="text-[#667085]" />
                <p className="text-sm font-semibold text-[#1c1c1e]">Recent lab activity</p>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {(keyLabs.timeline_events ?? []).slice(-8).map((month) => (
                  <div key={month.month} className="rounded-lg border border-[#eef0f4] bg-[#f8fafc] px-3 py-2">
                    <p className="text-xs font-semibold text-[#1c1c1e]">{month.label}</p>
                    <p className="mt-1 text-xs text-[#667085]">{month.events.length} result{month.events.length === 1 ? "" : "s"}</p>
                  </div>
                ))}
              </div>
              {keyLabs.timeline_events.length === 0 && <p className="mt-3 text-sm text-[#667085]">No recent lab timeline events found.</p>}
            </section>
          </div>
        </section>
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
