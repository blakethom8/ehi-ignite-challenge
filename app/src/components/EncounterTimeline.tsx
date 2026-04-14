import { useMemo } from "react";
import type { CareJourneyResponse, EncounterMarker } from "../types";
import type { SelectedCareItem } from "./CareJourneyChart";

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(d: string | null | undefined): string {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

const CLASS_STYLES: Record<string, { label: string; color: string; bg: string }> = {
  AMB: { label: "Ambulatory", color: "#5b76fe", bg: "#eef1ff" },
  IMP: { label: "Inpatient", color: "#b45309", bg: "#fffbeb" },
  EMER: { label: "Emergency", color: "#991b1b", bg: "#fef2f2" },
  WELLNESS: { label: "Wellness", color: "#065f46", bg: "#ecfdf5" },
  VR: { label: "Virtual", color: "#065f46", bg: "#ecfdf5" },
};

function ClassBadge({ code }: { code: string }) {
  const style = CLASS_STYLES[code] || { label: code || "Unknown", color: "#555a6a", bg: "#f5f6f8" };
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full font-medium"
      style={{ color: style.color, backgroundColor: style.bg }}
    >
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: style.color }} />
      {style.label}
    </span>
  );
}

// ── Component ────────────────────────────────────────────────────────────────

interface EncounterTimelineProps {
  data: CareJourneyResponse;
  onSelect: (item: SelectedCareItem) => void;
  selectedRowId: string | null;
}

export function EncounterTimeline({ data, onSelect, selectedRowId }: EncounterTimelineProps) {
  // Sort encounters by date descending (most recent first)
  const encounters = useMemo(() => {
    return [...data.encounters]
      .filter((e) => e.start)
      .sort((a, b) => new Date(b.start!).getTime() - new Date(a.start!).getTime());
  }, [data.encounters]);

  // Build lookup: find medications/conditions/procedures that happened around the same date
  // (within ±1 day of the encounter start)
  const medsAtEncounter = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const enc of encounters) {
      if (!enc.start) continue;
      const encMs = new Date(enc.start).getTime();
      const DAY = 24 * 60 * 60 * 1000;
      const nearby: string[] = [];
      for (const m of data.medication_episodes) {
        if (m.start_date) {
          const mMs = new Date(m.start_date).getTime();
          if (Math.abs(mMs - encMs) < DAY) {
            nearby.push(`\uD83D\uDC8A ${m.display}${m.reason ? ` (${m.reason})` : ""}`);
          }
        }
      }
      for (const p of data.procedures) {
        if (p.start) {
          const pMs = new Date(p.start).getTime();
          if (Math.abs(pMs - encMs) < DAY) {
            nearby.push(`\u2702 ${p.display}${p.reason_display ? ` (${p.reason_display})` : ""}`);
          }
        }
      }
      if (nearby.length > 0) map.set(enc.encounter_id, nearby);
    }
    return map;
  }, [encounters, data.medication_episodes, data.procedures]);

  if (encounters.length === 0) {
    return <div className="text-center text-slate-400 py-8 text-sm">No encounters found.</div>;
  }

  return (
    <div className="divide-y divide-slate-100">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 bg-slate-50 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        <span className="w-24 shrink-0">Date</span>
        <span className="w-20 shrink-0">Class</span>
        <span className="flex-1">Details</span>
      </div>

      {encounters.map((enc) => {
        const rowId = `enc_tl_${enc.encounter_id}`;
        const isSelected = selectedRowId === rowId;
        const linked = medsAtEncounter.get(enc.encounter_id) || [];

        return (
          <div
            key={enc.encounter_id}
            className={`flex items-start gap-3 px-4 py-2.5 cursor-pointer transition-colors ${
              isSelected ? "bg-blue-50" : "hover:bg-slate-50"
            }`}
            onClick={() => onSelect({ kind: "encounter", rowId, data: enc })}
          >
            {/* Date */}
            <span className="w-24 shrink-0 text-[11px] text-slate-500 pt-0.5 tabular-nums">
              {fmtDate(enc.start)}
            </span>

            {/* Class badge */}
            <span className="w-20 shrink-0 pt-0.5">
              <ClassBadge code={enc.class_code} />
            </span>

            {/* Details */}
            <div className="flex-1 min-w-0">
              {/* Diagnosis or type */}
              <div className="text-[12px] text-slate-800 font-medium leading-snug">
                {enc.diagnoses.length > 0 ? (
                  enc.diagnoses.map((dx, i) => (
                    <span key={i}>
                      {i > 0 && <span className="text-slate-300"> · </span>}
                      {dx}
                    </span>
                  ))
                ) : (
                  <span className="text-slate-500">{enc.type_text || "Encounter"}</span>
                )}
              </div>

              {/* Linked resources from that visit */}
              {linked.length > 0 && (
                <div className="mt-1 text-[10px] text-slate-400 leading-relaxed">
                  {linked.map((item, i) => (
                    <div key={i}>{item}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
