import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Heart, Pill, Maximize2, Clock, LayoutGrid, CalendarDays } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import { CareJourneyChart } from "../../components/CareJourneyChart";
import { CareJourneyDetail } from "../../components/CareJourneyDetail";
import { EncounterTimeline } from "../../components/EncounterTimeline";
import type { SelectedCareItem } from "../../components/CareJourneyChart";

type ViewMode = "category" | "encounters";

export function ExplorerCareJourney() {
  const [params] = useSearchParams();
  const patientId = params.get("patient");

  const { data, isLoading, error } = useQuery({
    queryKey: ["care-journey", patientId],
    queryFn: () => api.getCareJourney(patientId!),
    enabled: !!patientId,
  });

  const [dateRange, setDateRange] = useState<[string, string] | null>(null);
  const [selectedItem, setSelectedItem] = useState<SelectedCareItem | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("category");

  // ── No patient ─────────────────────────────────────────────────────────
  if (!patientId) {
    return (
      <EmptyState
        icon={Heart}
        title="Select a patient"
        bullets={[
          "Collapsible Gantt timeline of the care journey",
          "Medications grouped by drug class",
          "Conditions, procedures, and encounters over time",
        ]}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 gap-2 text-slate-400">
        <div className="w-4 h-4 border-2 border-slate-300 border-t-blue-500 rounded-full animate-spin" />
        Loading care journey...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center text-red-500 py-12">
        Failed to load care journey data.
      </div>
    );
  }

  // ── Stats ──────────────────────────────────────────────────────────────
  const activeMeds = data.medication_episodes.filter((m) => m.is_active).length;
  const activeConds = data.conditions.filter((c) => c.is_active).length;
  const dateSpan =
    data.earliest_date && data.latest_date
      ? `${new Date(data.earliest_date).getFullYear()} \u2013 ${new Date(data.latest_date).getFullYear()}`
      : "\u2014";

  return (
    <div className="space-y-3 h-full flex flex-col">
      {/* ── Header ───────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4 flex-wrap shrink-0">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">{data.name}</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {data.medication_episodes.length} medications &middot;{" "}
            {data.conditions.length} conditions &middot;{" "}
            {data.procedures.length} procedures &middot;{" "}
            {data.encounters.length} encounters &middot;{" "}
            {data.diagnostic_reports.length} lab reports &middot; {dateSpan}
          </p>
        </div>

        <div className="flex gap-3 text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-blue-50 text-blue-700 rounded-md font-medium">
            <Pill className="w-3.5 h-3.5" />
            {activeMeds} active meds
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-red-50 text-red-700 rounded-md font-medium">
            <Heart className="w-3.5 h-3.5" />
            {activeConds} active conditions
          </div>
        </div>
      </div>

      {/* ── Controls bar ────────────────────────────────────────────── */}
      <div className="flex items-center gap-1.5 text-xs shrink-0 flex-wrap">
        {/* View mode toggle */}
        <div className="flex rounded-md border border-slate-300 overflow-hidden mr-2">
          <button
            onClick={() => { setViewMode("category"); setSelectedItem(null); }}
            className={`flex items-center gap-1 px-2.5 py-1 transition-colors ${
              viewMode === "category" ? "bg-[#5b76fe] text-white" : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            <LayoutGrid className="w-3 h-3" />
            Category
          </button>
          <button
            onClick={() => { setViewMode("encounters"); setSelectedItem(null); }}
            className={`flex items-center gap-1 px-2.5 py-1 transition-colors ${
              viewMode === "encounters" ? "bg-[#5b76fe] text-white" : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            <CalendarDays className="w-3 h-3" />
            Encounters
          </button>
        </div>

        {/* Zoom controls — only for category view */}
        {viewMode === "category" && (
          <>
            <span className="text-slate-400 font-medium mr-0.5">Zoom</span>
            {[
              { label: "1Y", years: 1 },
              { label: "5Y", years: 5 },
              { label: "10Y", years: 10 },
              { label: "20Y", years: 20 },
            ].map(({ label, years }) => (
              <button
                key={label}
                onClick={() => {
                  const now = new Date();
                  const ago = new Date(now.getFullYear() - years, now.getMonth(), now.getDate());
                  setDateRange([ago.toISOString(), now.toISOString()]);
                }}
                className="px-2 py-1 rounded border border-slate-300 bg-white text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
              >
                {label}
              </button>
            ))}
            <button
              onClick={() => setDateRange(null)}
              className="flex items-center gap-1 px-2 py-1 rounded border border-slate-300 bg-white text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
            >
              <Maximize2 className="w-3 h-3" />
              All
            </button>
            {dateRange && (
              <span className="text-[10px] text-slate-400 ml-1">
                {new Date(dateRange[0]).toLocaleDateString("en-US", { month: "short", year: "numeric" })} &ndash;{" "}
                {new Date(dateRange[1]).toLocaleDateString("en-US", { month: "short", year: "numeric" })}
              </span>
            )}
          </>
        )}

        <span className="text-[10px] text-slate-400 ml-auto">
          {viewMode === "category" ? "Click a row for details \u00B7 Drag minimap to zoom" : "Click an encounter for details"}
        </span>
      </div>

      {/* ── Main content + detail pane ───────────────────────────────── */}
      <div className="flex border border-slate-200 rounded-lg bg-white overflow-hidden flex-1 min-h-0">
        <div className="relative flex-1 min-w-0">
          <div className="h-full overflow-y-auto scroll-visible" style={{ scrollbarWidth: "thin", scrollbarGutter: "stable" }}>
            {viewMode === "category" ? (
              <CareJourneyChart
                data={data}
                dateRange={dateRange}
                onDateRangeChange={setDateRange}
                onRowClick={(item) => setSelectedItem(item)}
                selectedRowId={selectedItem?.rowId ?? null}
              />
            ) : (
              <EncounterTimeline
                data={data}
                onSelect={(item) => setSelectedItem(item)}
                selectedRowId={selectedItem?.rowId ?? null}
              />
            )}
          </div>
          {/* Fade indicator when content overflows */}
          <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-t from-white to-transparent" />
        </div>

        {selectedItem && (
          <div className="w-80 shrink-0 border-l border-slate-200 overflow-hidden">
            <CareJourneyDetail
              item={selectedItem}
              patientId={patientId}
              onClose={() => setSelectedItem(null)}
            />
          </div>
        )}
      </div>

      {/* ── Legend ────────────────────────────────────────────────────── */}
      <p className="text-[10px] text-slate-400 leading-relaxed shrink-0">
        {viewMode === "category"
          ? "Click arrows to expand/collapse. Click a bar or dot for details."
          : "Click an encounter to see linked resources in the detail pane."}
        Solid = active, faded = stopped/resolved. Arrow tip = ongoing.
      </p>
    </div>
  );
}
