import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import type {
  CareJourneyResponse,
  MedicationEpisodeItem,
  ConditionEpisodeItem,
  EncounterMarker,
  ProcedureMarker,
} from "../types";

// ── Colors (exported for reuse in CareJourneyDetail) ────────────────────────

export const DRUG_CLASS_COLORS: Record<string, string> = {
  anticoagulants: "#e74c3c",
  antiplatelets: "#c0392b",
  ace_inhibitors: "#e67e22",
  arbs: "#d35400",
  jak_inhibitors: "#8e44ad",
  immunosuppressants: "#9b59b6",
  nsaids: "#f39c12",
  opioids: "#dc2626",
  anticonvulsants: "#3498db",
  psych_medications: "#2ecc71",
  stimulants: "#1abc9c",
  diabetes_medications: "#34495e",
};
const DEFAULT_MED_COLOR = "#94a3b8";

export const CONDITION_STATUS_COLORS: Record<string, string> = {
  active: "#ef4444",
  recurrence: "#f97316",
  relapse: "#f97316",
  resolved: "#cbd5e1",
  inactive: "#cbd5e1",
  remission: "#22c55e",
};

const ENCOUNTER_CLASS_COLORS: Record<string, string> = {
  EMER: "#ef4444",
  IMP: "#f59e0b",
  AMB: "#5b76fe",
  WELLNESS: "#10b981",
  VR: "#10b981",
};

const PROCEDURE_COLOR = "#8b5cf6";

// ── Constants ───────────────────────────────────────────────────────────────

const ROW_H = 34;
const LEFT_W = 280;
const MIN_BAR_PX = 4;
const BAR_PAD = 4; // vertical padding inside each row for the bar

// ── Row model ───────────────────────────────────────────────────────────────

export type SourceKind = "medication" | "condition" | "procedure" | "encounter";

interface DotMarker {
  ms: number;
  color: string;
  tooltip: string;
  sourceKind?: SourceKind;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  sourceData?: any;
}

interface GanttRow {
  id: string;
  label: string;
  level: 0 | 1 | 2;
  childCount?: number;
  collapsible: boolean;
  // Timeline bar (null = no bar, just a label row)
  startMs: number | null;
  endMs: number | null;
  isOngoing: boolean;
  color: string;
  opacity: number;
  // For dot markers (encounters/procedures at single points)
  dotMarkers?: DotMarker[];
  // Tooltip
  tooltip: string;
  // grouping key for collapse
  parentId: string | null;
  // Source data for click-to-detail
  sourceKind?: SourceKind;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  sourceData?: any;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function toMs(d: string | null | undefined): number | null {
  if (!d) return null;
  const t = new Date(d).getTime();
  return isNaN(t) ? null : t;
}

function fmtDate(d: string | null | undefined): string {
  if (!d) return "ongoing";
  return new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function drugClassLabel(cls: string): string {
  return cls.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "\u2026";
}

// ── Build flat row model from API data ──────────────────────────────────────

function buildRows(data: CareJourneyResponse): GanttRow[] {
  const now = Date.now();
  const rows: GanttRow[] = [];

  // ── Medications ─────────────────────────────────────────────────────────
  const medsByClass = new Map<string, MedicationEpisodeItem[]>();
  for (const m of data.medication_episodes) {
    const cls = m.drug_class || "unclassified";
    if (!medsByClass.has(cls)) medsByClass.set(cls, []);
    medsByClass.get(cls)!.push(m);
  }
  // Sort: classified first (alphabetical), unclassified last
  const classKeys = [...medsByClass.keys()].sort((a, b) => {
    if (a === "unclassified") return 1;
    if (b === "unclassified") return -1;
    return a.localeCompare(b);
  });

  rows.push({
    id: "med",
    label: `Medications`,
    level: 0,
    childCount: data.medication_episodes.length,
    collapsible: true,
    startMs: null, endMs: null, isOngoing: false,
    color: "#5b76fe", opacity: 1,
    tooltip: `${data.medication_episodes.length} medication episodes`,
    parentId: null,
  });

  for (const cls of classKeys) {
    const items = medsByClass.get(cls)!;
    const clsLabel = cls === "unclassified" ? "Other medications" : drugClassLabel(cls);
    const clsColor = DRUG_CLASS_COLORS[cls] || DEFAULT_MED_COLOR;

    rows.push({
      id: `med_${cls}`,
      label: clsLabel,
      level: 1,
      childCount: items.length,
      collapsible: true,
      startMs: null, endMs: null, isOngoing: false,
      color: clsColor, opacity: 1,
      tooltip: `${items.length} ${clsLabel.toLowerCase()}`,
      parentId: "med",
    });

    for (const m of items) {
      const startMs = toMs(m.start_date);
      const endMs = toMs(m.end_date) || now;
      rows.push({
        id: `med_item_${m.episode_id}`,
        label: truncate(m.display, 35),
        level: 2,
        collapsible: false,
        startMs,
        endMs: startMs ? endMs : null,
        isOngoing: m.is_active,
        color: clsColor,
        opacity: m.is_active ? 1.0 : 0.4,
        sourceKind: "medication",
        sourceData: m,
        tooltip:
          `${m.display}\nClass: ${cls === "unclassified" ? "Unclassified" : drugClassLabel(cls)}\n` +
          `Status: ${m.is_active ? "Active" : m.status}\n` +
          `Start: ${fmtDate(m.start_date)}\nEnd: ${fmtDate(m.end_date)}\n` +
          `Prescriptions: ${m.request_count}` +
          (m.duration_days ? `\nDuration: ${Math.round(m.duration_days)} days` : ""),
        parentId: `med_${cls}`,
      });
    }
  }

  // ── Conditions ──────────────────────────────────────────────────────────
  const activeConds = data.conditions.filter((c) => c.is_active);
  const resolvedConds = data.conditions.filter((c) => !c.is_active);

  rows.push({
    id: "cond",
    label: `Conditions`,
    level: 0,
    childCount: data.conditions.length,
    collapsible: true,
    startMs: null, endMs: null, isOngoing: false,
    color: "#ef4444", opacity: 1,
    tooltip: `${data.conditions.length} conditions`,
    parentId: null,
  });

  const addCondGroup = (
    groupId: string,
    label: string,
    items: ConditionEpisodeItem[],
    parentId: string,
  ) => {
    if (items.length === 0) return;
    rows.push({
      id: groupId,
      label,
      level: 1,
      childCount: items.length,
      collapsible: true,
      startMs: null, endMs: null, isOngoing: false,
      color: items[0].is_active ? "#ef4444" : "#94a3b8",
      opacity: 1,
      tooltip: `${items.length} ${label.toLowerCase()}`,
      parentId,
    });
    for (const c of items) {
      const startMs = toMs(c.onset_date);
      const endMs = toMs(c.end_date) || now;
      rows.push({
        id: `cond_item_${c.condition_id}`,
        label: truncate(c.display, 35),
        level: 2,
        collapsible: false,
        startMs,
        endMs: startMs ? endMs : null,
        isOngoing: c.is_active,
        color: CONDITION_STATUS_COLORS[c.clinical_status] || "#94a3b8",
        opacity: c.is_active ? 0.8 : 0.35,
        sourceKind: "condition",
        sourceData: c,
        tooltip:
          `${c.display}\nStatus: ${c.clinical_status}\n` +
          `Onset: ${fmtDate(c.onset_date)}\nEnd: ${fmtDate(c.end_date)}`,
        parentId: groupId,
      });
    }
  };

  addCondGroup("cond_active", `Active (${activeConds.length})`, activeConds, "cond");
  addCondGroup("cond_resolved", `Resolved (${resolvedConds.length})`, resolvedConds, "cond");

  // ── Procedures (grouped by name, shown as dot markers) ──────────────────
  if (data.procedures.length > 0) {
    rows.push({
      id: "proc",
      label: `Procedures`,
      level: 0,
      childCount: data.procedures.length,
      collapsible: true,
      startMs: null, endMs: null, isOngoing: false,
      color: PROCEDURE_COLOR, opacity: 1,
      tooltip: `${data.procedures.length} procedures`,
      parentId: null,
    });

    // Group procedures by display name
    const procByName = new Map<string, ProcedureMarker[]>();
    for (const p of data.procedures) {
      const key = p.display;
      if (!procByName.has(key)) procByName.set(key, []);
      procByName.get(key)!.push(p);
    }
    // Sort by count descending
    const procGroups = [...procByName.entries()].sort((a, b) => b[1].length - a[1].length);

    for (const [procName, items] of procGroups) {
      rows.push({
        id: `proc_${procName.replace(/\W/g, "_").slice(0, 30)}`,
        label: `${truncate(procName, 30)} (${items.length})`,
        level: 1,
        collapsible: false,
        startMs: null, endMs: null, isOngoing: false,
        color: PROCEDURE_COLOR,
        opacity: 1,
        dotMarkers: items
          .filter((p) => p.start)
          .map((p) => ({
            ms: toMs(p.start)!,
            color: PROCEDURE_COLOR,
            tooltip: `${procName}\nDate: ${fmtDate(p.start)}` +
              (p.reason_display ? `\nReason: ${truncate(p.reason_display, 40)}` : ""),
            sourceKind: "procedure" as SourceKind,
            sourceData: p,
          })),
        tooltip: `${items.length}× ${procName}`,
        parentId: "proc",
      });
    }
  }

  // ── Encounters ──────────────────────────────────────────────────────────
  const encByClass = new Map<string, EncounterMarker[]>();
  for (const e of data.encounters) {
    const cls = e.class_code || "OTHER";
    if (!encByClass.has(cls)) encByClass.set(cls, []);
    encByClass.get(cls)!.push(e);
  }

  rows.push({
    id: "enc",
    label: `Encounters`,
    level: 0,
    childCount: data.encounters.length,
    collapsible: true,
    startMs: null, endMs: null, isOngoing: false,
    color: "#5b76fe", opacity: 1,
    tooltip: `${data.encounters.length} encounters`,
    parentId: null,
  });

  const encClassOrder = ["EMER", "IMP", "AMB", "WELLNESS", "VR", "OTHER"];
  for (const cls of encClassOrder) {
    const items = encByClass.get(cls);
    if (!items || items.length === 0) continue;

    const color = ENCOUNTER_CLASS_COLORS[cls] || "#9ca3af";
    const clsLabel = { EMER: "Emergency", IMP: "Inpatient", AMB: "Ambulatory", WELLNESS: "Wellness", VR: "Virtual", OTHER: "Other" }[cls] || cls;

    // Encounters rendered as a single row with dot markers
    rows.push({
      id: `enc_${cls}`,
      label: `${clsLabel} (${items.length})`,
      level: 1,
      collapsible: false,
      startMs: null, endMs: null, isOngoing: false,
      color,
      opacity: 1,
      dotMarkers: items
        .filter((e) => e.start)
        .map((e) => ({
          ms: toMs(e.start)!,
          color,
          tooltip: `${clsLabel}\n${truncate(e.type_text, 50)}\n${fmtDate(e.start)}` +
            (e.reason_display ? `\nReason: ${truncate(e.reason_display, 40)}` : ""),
          sourceKind: "encounter" as SourceKind,
          sourceData: e,
        })),
      tooltip: `${items.length} ${clsLabel.toLowerCase()} encounters`,
      parentId: "enc",
    });
  }

  return rows;
}

// ── Time axis helpers ────────────────────────────────────────────────────────

interface Tick { ms: number; label: string; isMajor: boolean }

function computeTicks(minMs: number, maxMs: number, width: number): Tick[] {
  const rangeYears = (maxMs - minMs) / (365.25 * 24 * 3600 * 1000);
  const ticks: Tick[] = [];

  if (rangeYears > 20) {
    // Decade ticks
    const startYear = Math.floor(new Date(minMs).getFullYear() / 10) * 10;
    const endYear = new Date(maxMs).getFullYear() + 10;
    for (let y = startYear; y <= endYear; y += 5) {
      const ms = new Date(y, 0, 1).getTime();
      if (ms >= minMs && ms <= maxMs) {
        ticks.push({ ms, label: `${y}`, isMajor: y % 10 === 0 });
      }
    }
  } else if (rangeYears > 5) {
    // Yearly ticks
    const startYear = new Date(minMs).getFullYear();
    const endYear = new Date(maxMs).getFullYear() + 1;
    for (let y = startYear; y <= endYear; y++) {
      const ms = new Date(y, 0, 1).getTime();
      if (ms >= minMs && ms <= maxMs) {
        ticks.push({ ms, label: `${y}`, isMajor: true });
      }
    }
  } else if (rangeYears > 1) {
    // Quarterly ticks
    const startDate = new Date(minMs);
    const endDate = new Date(maxMs);
    const d = new Date(startDate.getFullYear(), Math.floor(startDate.getMonth() / 3) * 3, 1);
    while (d.getTime() <= endDate.getTime()) {
      const ms = d.getTime();
      if (ms >= minMs) {
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        ticks.push({
          ms,
          label: d.getMonth() === 0 ? `${d.getFullYear()}` : monthNames[d.getMonth()],
          isMajor: d.getMonth() === 0,
        });
      }
      d.setMonth(d.getMonth() + 3);
    }
  } else {
    // Monthly ticks
    const startDate = new Date(minMs);
    const endDate = new Date(maxMs);
    const d = new Date(startDate.getFullYear(), startDate.getMonth(), 1);
    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    while (d.getTime() <= endDate.getTime()) {
      const ms = d.getTime();
      if (ms >= minMs) {
        ticks.push({
          ms,
          label: d.getMonth() === 0 ? `${monthNames[d.getMonth()]} ${d.getFullYear()}` : monthNames[d.getMonth()],
          isMajor: d.getMonth() === 0,
        });
      }
      d.setMonth(d.getMonth() + 1);
    }
  }
  return ticks;
}

// ── Main component ──────────────────────────────────────────────────────────

export interface SelectedCareItem {
  kind: SourceKind;
  rowId: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
}

interface CareJourneyChartProps {
  data: CareJourneyResponse;
  dateRange: [string, string] | null;
  onRowClick?: (item: SelectedCareItem) => void;
  selectedRowId?: string | null;
}

export function CareJourneyChart({ data, dateRange, onRowClick, selectedRowId }: CareJourneyChartProps) {
  const allRows = useMemo(() => buildRows(data), [data]);

  // Collapse state: set of ids that are collapsed
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    // Default: top-level groups expanded, subgroups collapsed for large groups
    const s = new Set<string>();
    for (const r of allRows) {
      if (r.level === 1 && r.collapsible && (r.childCount ?? 0) > 6) {
        s.add(r.id);
      }
    }
    // Resolved conditions collapsed by default
    s.add("cond_resolved");
    // Procedures collapsed (often very long)
    s.add("proc");
    // Encounters collapsed (lots of dots)
    s.add("enc");
    return s;
  });

  const toggleCollapse = useCallback((id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Filter visible rows based on collapse state
  const visibleRows = useMemo(() => {
    const visible: GanttRow[] = [];
    const hiddenParents = new Set<string>();

    for (const row of allRows) {
      // Check if any ancestor is collapsed
      if (row.parentId && (hiddenParents.has(row.parentId) || collapsed.has(row.parentId))) {
        hiddenParents.add(row.id);
        continue;
      }
      visible.push(row);
    }
    return visible;
  }, [allRows, collapsed]);

  // Time range
  const [viewMin, viewMax] = useMemo(() => {
    if (dateRange) {
      return [new Date(dateRange[0]).getTime(), new Date(dateRange[1]).getTime()];
    }
    // Default: fit all data with padding
    let min = Infinity;
    let max = -Infinity;
    for (const r of allRows) {
      if (r.startMs) min = Math.min(min, r.startMs);
      if (r.endMs) max = Math.max(max, r.endMs);
      if (r.dotMarkers) {
        for (const d of r.dotMarkers) {
          min = Math.min(min, d.ms);
          max = Math.max(max, d.ms);
        }
      }
    }
    if (min === Infinity) { min = Date.now() - 5 * 365.25 * 24 * 3600 * 1000; max = Date.now(); }
    const pad = (max - min) * 0.03;
    return [min - pad, max + pad];
  }, [allRows, dateRange]);

  // Refs and state for hover tooltip
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const svgContainerRef = useRef<HTMLDivElement>(null);
  const [svgWidth, setSvgWidth] = useState(600);

  // Measure actual container width
  useEffect(() => {
    const el = svgContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setSvgWidth(Math.max(entry.contentRect.width, 300));
      }
    });
    ro.observe(el);
    setSvgWidth(Math.max(el.clientWidth, 300));
    return () => ro.disconnect();
  }, []);

  // Scale function — returns pixel x within measured SVG width
  const timeToX = useCallback(
    (ms: number) => ((ms - viewMin) / (viewMax - viewMin)) * svgWidth,
    [viewMin, viewMax, svgWidth],
  );

  const ticks = useMemo(() => computeTicks(viewMin, viewMax, svgWidth), [viewMin, viewMax]);
  const totalH = visibleRows.length * ROW_H;

  return (
    <div ref={containerRef} className="relative">
      {/* ── Tooltip ──────────────────────────────────────────────────── */}
      {tooltip && (
        <div
          className="absolute z-50 pointer-events-none px-2.5 py-1.5 bg-gray-900 text-white text-[11px] rounded-md shadow-lg whitespace-pre-wrap max-w-xs leading-relaxed"
          style={{ left: tooltip.x + LEFT_W + 8, top: tooltip.y + 32 }}
        >
          {tooltip.text}
        </div>
      )}

      <div className="flex" style={{ minHeight: totalH + 36 }}>
        {/* ── Left panel: tree labels ────────────────────────────────── */}
        <div className="shrink-0 border-r border-slate-200" style={{ width: LEFT_W }}>
          {/* Time axis spacer */}
          <div className="h-[32px] border-b border-slate-200 bg-slate-50" />

          {visibleRows.map((row) => {
            const isCollapsed = collapsed.has(row.id);
            return (
              <div
                key={row.id}
                className={`flex items-center gap-1 border-b border-slate-100 select-none ${
                  row.id === selectedRowId
                    ? "bg-blue-50"
                    : row.level === 0
                    ? "bg-slate-50"
                    : ""
                } ${
                  row.level === 0
                    ? "font-semibold text-slate-800"
                    : row.level === 1
                    ? "font-medium text-slate-700"
                    : "text-slate-600"
                } ${row.sourceKind ? "cursor-pointer hover:bg-blue-50/50" : ""}`}
                style={{
                  height: ROW_H,
                  paddingLeft: row.level === 0 ? 8 : row.level === 1 ? 24 : 40,
                  fontSize: row.level === 0 ? 12 : 11,
                }}
                onClick={() => {
                  if (row.sourceKind && row.sourceData && onRowClick) {
                    onRowClick({ kind: row.sourceKind, rowId: row.id, data: row.sourceData });
                  }
                }}
              >
                {row.collapsible ? (
                  <button
                    onClick={() => toggleCollapse(row.id)}
                    className="shrink-0 w-4 h-4 flex items-center justify-center rounded hover:bg-slate-200 transition-colors"
                  >
                    {isCollapsed ? (
                      <ChevronRight className="w-3 h-3" />
                    ) : (
                      <ChevronDown className="w-3 h-3" />
                    )}
                  </button>
                ) : (
                  <span className="shrink-0 w-4" />
                )}

                {/* Color dot */}
                <span
                  className="shrink-0 w-2 h-2 rounded-full"
                  style={{ backgroundColor: row.color }}
                />

                <span className="truncate" title={row.tooltip.split("\n")[0]}>
                  {row.label}
                </span>

                {row.childCount != null && row.level < 2 && (
                  <span className="ml-auto pr-2 text-[10px] text-slate-400 tabular-nums">
                    {row.childCount}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* ── Right panel: SVG timeline ──────────────────────────────── */}
        <div ref={svgContainerRef} className="flex-1 overflow-x-auto">
          <svg
            width={svgWidth}
            height={totalH + 36}
            className="block"
          >
            {/* Time axis */}
            <g>
              <rect x={0} y={0} width={svgWidth} height={32} fill="#f8f9fa" />
              <line x1={0} y1={32} x2={svgWidth} y2={32} stroke="#e2e4e8" strokeWidth={1} />
              {ticks.map((t, i) => {
                const x = timeToX(t.ms);
                return (
                  <g key={i}>
                    <line
                      x1={x} y1={t.isMajor ? 18 : 24} x2={x} y2={32}
                      stroke={t.isMajor ? "#9ca3af" : "#d1d5db"}
                      strokeWidth={t.isMajor ? 1 : 0.5}
                    />
                    {t.isMajor && (
                      <text x={x} y={15} textAnchor="middle" fontSize={10} fill="#6b7280">
                        {t.label}
                      </text>
                    )}
                    {/* Vertical grid line */}
                    <line
                      x1={x} y1={32} x2={x} y2={totalH + 36}
                      stroke={t.isMajor ? "#f1f2f4" : "#f8f9fa"}
                      strokeWidth={t.isMajor ? 1 : 0.5}
                    />
                  </g>
                );
              })}
            </g>

            {/* Row backgrounds + bars */}
            {visibleRows.map((row, i) => {
              const y = 32 + i * ROW_H;

              return (
                <g key={row.id}>
                  {/* Row background */}
                  <rect
                    x={0} y={y} width={svgWidth} height={ROW_H}
                    fill={row.id === selectedRowId ? "#eff6ff" : row.level === 0 ? "#f8f9fa" : i % 2 === 0 ? "white" : "#fcfcfd"}
                  />
                  <line x1={0} y1={y + ROW_H} x2={svgWidth} y2={y + ROW_H} stroke="#f1f2f4" strokeWidth={0.5} />

                  {/* Bar for items with start/end */}
                  {row.startMs != null && row.endMs != null && (() => {
                    const x1 = timeToX(row.startMs);
                    const x2 = timeToX(row.endMs);
                    const barW = Math.max(x2 - x1, MIN_BAR_PX);
                    const barH = ROW_H - BAR_PAD * 2;
                    const barY = y + BAR_PAD;

                    return (
                      <g
                        onMouseEnter={(e) => {
                          const rect = containerRef.current?.getBoundingClientRect();
                          if (rect) {
                            setTooltip({ x: e.clientX - rect.left - LEFT_W, y: e.clientY - rect.top, text: row.tooltip });
                          }
                        }}
                        onMouseLeave={() => setTooltip(null)}
                        onClick={() => {
                          if (row.sourceKind && row.sourceData && onRowClick) {
                            onRowClick({ kind: row.sourceKind, rowId: row.id, data: row.sourceData });
                          }
                        }}
                        style={{ cursor: row.sourceKind ? "pointer" : "default" }}
                      >
                        <rect
                          x={x1} y={barY}
                          width={barW} height={barH}
                          rx={3} ry={3}
                          fill={row.color}
                          opacity={row.opacity}
                        />
                        {/* Ongoing arrow indicator */}
                        {row.isOngoing && (
                          <polygon
                            points={`${x1 + barW},${barY} ${x1 + barW + 7},${barY + barH / 2} ${x1 + barW},${barY + barH}`}
                            fill={row.color}
                            opacity={row.opacity}
                          />
                        )}
                      </g>
                    );
                  })()}

                  {/* Dot markers (encounters) */}
                  {row.dotMarkers && row.dotMarkers.map((dot, di) => {
                    const cx = timeToX(dot.ms);
                    return (
                      <circle
                        key={di}
                        cx={cx}
                        cy={y + ROW_H / 2}
                        r={3.5}
                        fill={dot.color}
                        opacity={0.65}
                        onMouseEnter={(e) => {
                          const rect = containerRef.current?.getBoundingClientRect();
                          if (rect) {
                            setTooltip({ x: e.clientX - rect.left - LEFT_W, y: e.clientY - rect.top, text: dot.tooltip });
                          }
                        }}
                        onMouseLeave={() => setTooltip(null)}
                        onClick={() => {
                          if (dot.sourceKind && dot.sourceData && onRowClick) {
                            onRowClick({ kind: dot.sourceKind, rowId: `${row.id}_dot_${di}`, data: dot.sourceData });
                          }
                        }}
                        style={{ cursor: dot.sourceKind ? "pointer" : "default" }}
                      />
                    );
                  })}

                  {/* Group-level summary bar — only for medication/condition groups (not encounters/procedures) */}
                  {row.level < 2 && row.startMs == null && !row.dotMarkers && (() => {
                    // Skip aggregate bars for encounter and procedure groups — they only show detail when expanded
                    if (row.id === "enc" || row.id === "proc" || row.id.startsWith("enc_")) return null;

                    // Compute aggregate span from children
                    let minMs = Infinity, maxMs = -Infinity;
                    for (const c of allRows) {
                      if (c.parentId === row.id || allRows.some((g) => g.parentId === row.id && g.id === c.parentId)) {
                        if (c.startMs) minMs = Math.min(minMs, c.startMs);
                        if (c.endMs) maxMs = Math.max(maxMs, c.endMs);
                      }
                    }
                    if (minMs === Infinity) return null;
                    const x1 = timeToX(minMs);
                    const x2 = timeToX(maxMs);
                    const barW = Math.max(x2 - x1, MIN_BAR_PX);
                    return (
                      <rect
                        x={x1} y={y + ROW_H - 6}
                        width={barW} height={4}
                        rx={2}
                        fill={row.color}
                        opacity={0.2}
                      />
                    );
                  })()}
                </g>
              );
            })}

            {/* Today line */}
            {(() => {
              const todayX = timeToX(Date.now());
              if (todayX > 0 && todayX < svgWidth) {
                return (
                  <line
                    x1={todayX} y1={32} x2={todayX} y2={totalH + 36}
                    stroke="#ef4444" strokeWidth={1} strokeDasharray="4 2"
                    opacity={0.5}
                  />
                );
              }
              return null;
            })()}
          </svg>
        </div>
      </div>
    </div>
  );
}
