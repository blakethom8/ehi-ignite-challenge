import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Heart, Pill, Maximize2, Clock } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import { CareJourneyChart } from "../../components/CareJourneyChart";
import { CareJourneyDetail } from "../../components/CareJourneyDetail";
import type { SelectedCareItem } from "../../components/CareJourneyChart";

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
            {data.encounters.length} encounters &middot; {dateSpan}
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

      {/* ── Zoom controls ────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 text-xs shrink-0">
        <span className="text-slate-400 font-medium">Zoom</span>
        <button
          onClick={() => {
            const now = new Date();
            const ago = new Date(now.getFullYear() - 5, now.getMonth(), now.getDate());
            setDateRange([ago.toISOString(), now.toISOString()]);
          }}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-slate-300 bg-white text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
        >
          <Clock className="w-3.5 h-3.5" />
          Recent 5Y
        </button>
        <button
          onClick={() => setDateRange(null)}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-slate-300 bg-white text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
        >
          <Maximize2 className="w-3.5 h-3.5" />
          Fit All
        </button>
        {dateRange && (
          <span className="text-[10px] text-slate-400 ml-1">
            {new Date(dateRange[0]).getFullYear()} &ndash; {new Date(dateRange[1]).getFullYear()}
          </span>
        )}

        <span className="text-[10px] text-slate-400 ml-auto">
          Click a row for details
        </span>
      </div>

      {/* ── Gantt chart + detail pane ────────────────────────────────── */}
      <div className="flex border border-slate-200 rounded-lg bg-white overflow-hidden flex-1 min-h-0">
        <div className="flex-1 min-w-0 overflow-auto">
          <CareJourneyChart
            data={data}
            dateRange={dateRange}
            onRowClick={(item) => setSelectedItem(item)}
            selectedRowId={selectedItem?.rowId ?? null}
          />
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
        Click arrows to expand/collapse. Click a bar or dot for details.
        Solid = active, faded = stopped/resolved. Arrow tip = ongoing.
      </p>
    </div>
  );
}
