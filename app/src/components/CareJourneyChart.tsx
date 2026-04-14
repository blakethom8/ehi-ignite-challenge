import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import type {
  CareJourneyResponse,
  MedicationEpisodeItem,
  ConditionEpisodeItem,
  EncounterMarker,
  ProcedureMarker,
  DiagnosticReportItem,
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
const DIAGNOSTIC_COLOR = "#0891b2"; // cyan/teal for lab reports

// ── Constants ───────────────────────────────────────────────────────────────

const ROW_H = 34;
const LEFT_W = 280;
const MIN_BAR_PX = 4;
const BAR_PAD = 4; // vertical padding inside each row for the bar

// ── Row model ───────────────────────────────────────────────────────────────

export type SourceKind = "medication" | "condition" | "procedure" | "encounter" | "diagnostic_report";

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
        label: m.reason ? `${m.display} — for ${m.reason}` : m.display,
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
          `${m.display}\n${m.reason ? `Reason: ${m.reason}\n` : ""}` +
          `Class: ${cls === "unclassified" ? "Unclassified" : drugClassLabel(cls)}\n` +
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
        label: c.display,
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
      const groupId = `proc_${procName.replace(/\W/g, "_").slice(0, 30)}`;
      rows.push({
        id: groupId,
        label: `${truncate(procName, 30)} (${items.length})`,
        level: 1,
        childCount: items.length,
        collapsible: items.length > 1,
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

      // Individual procedure rows (children)
      if (items.length === 1) {
        // Single-item groups: make the group row itself clickable
        rows[rows.length - 1].sourceKind = "procedure";
        rows[rows.length - 1].sourceData = items[0];
      } else {
        // Multi-item groups: add expandable children
        const sorted = [...items].filter((p) => p.start).sort((a, b) =>
          new Date(b.start!).getTime() - new Date(a.start!).getTime()
        );
        for (const p of sorted) {
          const dateLabel = p.start ? new Date(p.start).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "";
          rows.push({
            id: `proc_item_${p.procedure_id}`,
            label: `${dateLabel}${p.reason_display ? ` — ${p.reason_display}` : ""}`,
            level: 2,
            collapsible: false,
            startMs: toMs(p.start),
            endMs: toMs(p.start) ? toMs(p.start)! + 24 * 60 * 60 * 1000 : null,
            isOngoing: false,
            color: PROCEDURE_COLOR,
            opacity: 0.7,
            sourceKind: "procedure",
            sourceData: p,
            tooltip: `${procName}\nDate: ${fmtDate(p.start)}` +
              (p.reason_display ? `\nReason: ${p.reason_display}` : ""),
            parentId: groupId,
          });
        }
      }
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

    // Encounter class group — collapsible, with dot summary
    rows.push({
      id: `enc_${cls}`,
      label: `${clsLabel} (${items.length})`,
      level: 1,
      childCount: items.length,
      collapsible: true,
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

    // Individual encounter rows (children of the class group)
    // Sort by date descending (most recent first)
    const sorted = [...items].filter((e) => e.start).sort((a, b) => {
      return new Date(b.start!).getTime() - new Date(a.start!).getTime();
    });
    for (const e of sorted) {
      const startMs = toMs(e.start);
      const dateLabel = e.start ? new Date(e.start).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "";
      // Show diagnosis if available, otherwise type_text
      const dxLabel = e.diagnoses && e.diagnoses.length > 0
        ? e.diagnoses[0]
        : e.type_text || "";
      const label = `${dateLabel}${dxLabel ? ` — ${dxLabel}` : ""}`;
      rows.push({
        id: `enc_item_${e.encounter_id}`,
        label,
        level: 2,
        collapsible: false,
        startMs,
        endMs: startMs ? startMs + 24 * 60 * 60 * 1000 : null,
        isOngoing: false,
        color,
        opacity: 0.7,
        sourceKind: "encounter",
        sourceData: e,
        tooltip:
          `${clsLabel} encounter\n${e.type_text}\nDate: ${fmtDate(e.start)}` +
          (e.diagnoses?.length ? `\nDiagnosis: ${e.diagnoses.join(", ")}` : "") +
          (e.reason_display ? `\nReason: ${e.reason_display}` : ""),
        parentId: `enc_${cls}`,
      });
    }
  }

  // ── Diagnostic Reports (grouped by type, shown as dot markers) ────────
  if (data.diagnostic_reports.length > 0) {
    rows.push({
      id: "dx_reports",
      label: "Lab Reports",
      level: 0,
      childCount: data.diagnostic_reports.length,
      collapsible: true,
      startMs: null, endMs: null, isOngoing: false,
      color: DIAGNOSTIC_COLOR, opacity: 1,
      tooltip: `${data.diagnostic_reports.length} diagnostic reports`,
      parentId: null,
    });

    // Group by display name
    const byName = new Map<string, DiagnosticReportItem[]>();
    for (const dr of data.diagnostic_reports) {
      const key = dr.display;
      if (!byName.has(key)) byName.set(key, []);
      byName.get(key)!.push(dr);
    }
    const reportGroups = [...byName.entries()].sort((a, b) => b[1].length - a[1].length);

    for (const [reportName, items] of reportGroups) {
      rows.push({
        id: `dxr_${reportName.replace(/\W/g, "_").slice(0, 30)}`,
        label: `${truncate(reportName, 28)} (${items.length})`,
        level: 1,
        collapsible: false,
        startMs: null, endMs: null, isOngoing: false,
        color: DIAGNOSTIC_COLOR,
        opacity: 1,
        dotMarkers: items
          .filter((dr) => dr.date)
          .map((dr) => ({
            ms: toMs(dr.date)!,
            color: DIAGNOSTIC_COLOR,
            tooltip: `${reportName}\nDate: ${fmtDate(dr.date)}\nResults: ${dr.result_count} observations`,
            sourceKind: "diagnostic_report" as SourceKind,
            sourceData: dr,
          })),
        tooltip: `${items.length}× ${reportName}`,
        parentId: "dx_reports",
      });
    }
  }

  return rows;
}

// ── Time axis helpers ────────────────────────────────────────────────────────

interface Tick { ms: number; label: string; isMajor: boolean }

function computeTicks(minMs: number, maxMs: number, _width: number): Tick[] {
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
  onDateRangeChange?: (range: [string, string] | null) => void;
  onRowClick?: (item: SelectedCareItem) => void;
  selectedRowId?: string | null;
}

export function CareJourneyChart({ data, dateRange, onDateRangeChange, onRowClick, selectedRowId }: CareJourneyChartProps) {
  const allRows = useMemo(() => buildRows(data), [data]);

  // Collapse state: set of ids that are collapsed
  // Default: show top-level groups and subgroup headers, but NOT individual items
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    const s = new Set<string>();
    for (const r of allRows) {
      // Collapse all level-1 subgroups (drug classes, active/resolved, encounter classes)
      if (r.level === 1 && r.collapsible) {
        s.add(r.id);
      }
    }
    // Collapse entire sections that aren't medications/conditions
    s.add("proc");
    s.add("enc");
    s.add("dx_reports");
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

  const expandAll = useCallback(() => setCollapsed(new Set()), []);

  const collapseAll = useCallback(() => {
    const s = new Set<string>();
    for (const r of allRows) {
      if (r.collapsible) s.add(r.id);
    }
    setCollapsed(s);
  }, [allRows]);

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

  // Keyboard navigation: Arrow Up/Down to move between clickable rows
  useEffect(() => {
    if (!selectedRowId || !onRowClick) return;

    const handleKey = (e: KeyboardEvent) => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      e.preventDefault();

      // Get clickable visible rows (those with sourceKind)
      const clickable = visibleRows.filter((r) => r.sourceKind);
      const curIdx = clickable.findIndex((r) => r.id === selectedRowId);
      if (curIdx === -1) return;

      const nextIdx = e.key === "ArrowDown"
        ? Math.min(curIdx + 1, clickable.length - 1)
        : Math.max(curIdx - 1, 0);

      if (nextIdx !== curIdx) {
        const next = clickable[nextIdx];
        onRowClick({ kind: next.sourceKind!, rowId: next.id, data: next.sourceData });

        // Scroll the row into view
        const rowEl = containerRef.current?.querySelector(`[data-row-id="${next.id}"]`);
        rowEl?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    };

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [selectedRowId, visibleRows, onRowClick]);

  // Full data extent (for minimap) — use actual API dates, not the "now" sentinel
  const [fullMin, fullMax] = useMemo(() => {
    const dates: number[] = [];
    for (const m of data.medication_episodes) {
      if (m.start_date) dates.push(new Date(m.start_date).getTime());
      if (m.end_date) dates.push(new Date(m.end_date).getTime());
    }
    for (const c of data.conditions) {
      if (c.onset_date) dates.push(new Date(c.onset_date).getTime());
      if (c.end_date) dates.push(new Date(c.end_date).getTime());
    }
    for (const e of data.encounters) {
      if (e.start) dates.push(new Date(e.start).getTime());
    }
    for (const p of data.procedures) {
      if (p.start) dates.push(new Date(p.start).getTime());
    }
    if (dates.length === 0) {
      return [Date.now() - 5 * 365.25 * 24 * 3600 * 1000, Date.now()];
    }
    const min = Math.min(...dates);
    const max = Math.max(...dates);
    const pad = (max - min) * 0.03;
    return [min - pad, max + pad];
  }, [data]);

  // Visible time range (may be zoomed)
  const [viewMin, viewMax] = useMemo(() => {
    if (dateRange) {
      return [new Date(dateRange[0]).getTime(), new Date(dateRange[1]).getTime()];
    }
    return [fullMin, fullMax];
  }, [fullMin, fullMax, dateRange]);

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
      {/* ── Tooltip (smart positioning — flips when near edges) ────── */}
      {tooltip && (() => {
        const containerW = containerRef.current?.clientWidth ?? 800;
        const containerH = containerRef.current?.clientHeight ?? 600;
        const tipW = 240; // max-w-xs ≈ 20rem = 320px, but most are ~240
        const tipH = 80;

        // Default: right of cursor, below
        let left = tooltip.x + LEFT_W + 8;
        let top = tooltip.y + 32;

        // Flip left if would overflow right edge
        if (left + tipW > containerW - 16) {
          left = tooltip.x + LEFT_W - tipW - 8;
        }
        // Flip up if would overflow bottom
        if (top + tipH > containerH - 16) {
          top = tooltip.y - tipH - 8;
        }
        // Clamp to stay in bounds
        left = Math.max(8, Math.min(left, containerW - tipW - 8));
        top = Math.max(8, top);

        return (
          <div
            className="absolute z-50 pointer-events-none px-2.5 py-1.5 bg-gray-900 text-white text-[11px] rounded-md shadow-lg whitespace-pre-wrap max-w-xs leading-relaxed"
            style={{ left, top }}
          >
            {tooltip.text}
          </div>
        );
      })()}

      {/* ── Minimap / range selector (pinned at top) ────────────────── */}
      <Minimap
        fullMin={fullMin}
        fullMax={fullMax}
        viewMin={viewMin}
        viewMax={viewMax}
        width={svgWidth}
        leftOffset={LEFT_W}
        allRows={allRows}
        onRangeChange={(min, max) => {
          if (onDateRangeChange) {
            onDateRangeChange([new Date(min).toISOString(), new Date(max).toISOString()]);
          }
        }}
      />

      <div className="flex" style={{ height: totalH + 36 }}>
        {/* ── Left panel: tree labels ────────────────────────────────── */}
        <div className="shrink-0 border-r border-slate-200" style={{ width: LEFT_W, overflow: "visible" }}>
          {/* Header with expand/collapse controls */}
          <div className="h-[32px] border-b border-slate-200 bg-slate-50 flex items-center justify-between px-2">
            <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Care Journey</span>
            <div className="flex gap-1">
              <button
                onClick={expandAll}
                className="text-[9px] text-slate-400 hover:text-slate-600 px-1.5 py-0.5 rounded hover:bg-white transition-colors"
                title="Expand all"
              >
                Expand
              </button>
              <button
                onClick={collapseAll}
                className="text-[9px] text-slate-400 hover:text-slate-600 px-1.5 py-0.5 rounded hover:bg-white transition-colors"
                title="Collapse all"
              >
                Collapse
              </button>
            </div>
          </div>

          {visibleRows.map((row) => {
            const isCollapsed = collapsed.has(row.id);
            const isDetailRow = row.level === 2;
            return (
              <div
                key={row.id}
                data-row-id={row.id}
                className={`flex items-center gap-1 select-none ${
                  row.id === selectedRowId
                    ? "bg-blue-50 border-b border-slate-100"
                    : row.level === 0
                    ? "bg-slate-50 border-b border-slate-200 border-t border-t-slate-200"
                    : "border-b border-slate-100"
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
                  // Let detail row text overflow into the SVG area
                  ...(isDetailRow ? { overflow: "visible", position: "relative" as const, zIndex: 2 } : {}),
                }}
                onClick={() => {
                  if (row.sourceKind && row.sourceData && onRowClick) {
                    onRowClick({ kind: row.sourceKind, rowId: row.id, data: row.sourceData });
                  }
                }}
              >
                {row.collapsible ? (
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleCollapse(row.id); }}
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

                {isDetailRow ? (
                  /* Detail rows: text overflows with a fade-out gradient */
                  <span
                    className="whitespace-nowrap pointer-events-none"
                    style={{
                      maskImage: "linear-gradient(to right, black 85%, transparent 100%)",
                      WebkitMaskImage: "linear-gradient(to right, black 85%, transparent 100%)",
                      paddingRight: 60,
                    }}
                    title={row.tooltip.split("\n")[0]}
                  >
                    {row.label}
                  </span>
                ) : (
                  <span className="truncate" title={row.tooltip.split("\n")[0]}>
                    {row.label}
                  </span>
                )}

                {row.childCount != null && row.level < 2 && (
                  <span className="ml-auto pr-2 text-[10px] text-slate-400 tabular-nums shrink-0">
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
                  {/* Section separator for top-level groups */}
                  {row.level === 0 && (
                    <line x1={0} y1={y} x2={svgWidth} y2={y} stroke="#e2e4e8" strokeWidth={1} />
                  )}
                  <line x1={0} y1={y + ROW_H} x2={svgWidth} y2={y + ROW_H} stroke={row.level === 0 ? "#e2e4e8" : "#f1f2f4"} strokeWidth={row.level === 0 ? 1 : 0.5} />

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

// ── Minimap component ───────────────────────────────────────────────────────

interface MinimapProps {
  fullMin: number;
  fullMax: number;
  viewMin: number;
  viewMax: number;
  width: number;
  leftOffset: number;
  allRows: GanttRow[];
  onRangeChange: (min: number, max: number) => void;
}

function Minimap({ fullMin, fullMax, viewMin, viewMax, width, leftOffset, allRows, onRangeChange }: MinimapProps) {
  const minimapRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<"left" | "right" | "center" | null>(null);
  const dragStartRef = useRef<{ x: number; viewMin: number; viewMax: number }>({ x: 0, viewMin: 0, viewMax: 0 });

  const MINIMAP_H = 36;
  const fullRange = fullMax - fullMin;
  if (fullRange <= 0) return null;

  const toX = (ms: number) => ((ms - fullMin) / fullRange) * width;
  const selLeft = toX(viewMin);
  const selRight = toX(viewMax);
  const selWidth = Math.max(selRight - selLeft, 4);

  // Collect all event timestamps for density visualization
  const densityBuckets = useMemo(() => {
    const BUCKETS = 100;
    const buckets = new Array(BUCKETS).fill(0);
    for (const r of allRows) {
      if (r.dotMarkers) {
        for (const d of r.dotMarkers) {
          const idx = Math.floor(((d.ms - fullMin) / fullRange) * BUCKETS);
          if (idx >= 0 && idx < BUCKETS) buckets[idx]++;
        }
      }
      if (r.startMs) {
        const idx = Math.floor(((r.startMs - fullMin) / fullRange) * BUCKETS);
        if (idx >= 0 && idx < BUCKETS) buckets[idx]++;
      }
    }
    const max = Math.max(...buckets, 1);
    return buckets.map((v) => v / max);
  }, [allRows, fullMin, fullRange]);

  const handleMouseDown = useCallback((e: React.MouseEvent, handle: "left" | "right" | "center") => {
    e.preventDefault();
    setDragging(handle);
    dragStartRef.current = { x: e.clientX, viewMin, viewMax };
  }, [viewMin, viewMax]);

  useEffect(() => {
    if (!dragging) return;

    const handleMove = (e: MouseEvent) => {
      const el = minimapRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const scale = fullRange / rect.width;
      const dx = (e.clientX - dragStartRef.current.x) * scale;
      const { viewMin: startMin, viewMax: startMax } = dragStartRef.current;

      let newMin = startMin;
      let newMax = startMax;

      if (dragging === "left") {
        newMin = Math.max(fullMin, Math.min(startMin + dx, startMax - fullRange * 0.01));
      } else if (dragging === "right") {
        newMax = Math.min(fullMax, Math.max(startMax + dx, startMin + fullRange * 0.01));
      } else { // center — pan
        const span = startMax - startMin;
        newMin = startMin + dx;
        newMax = startMax + dx;
        if (newMin < fullMin) { newMin = fullMin; newMax = fullMin + span; }
        if (newMax > fullMax) { newMax = fullMax; newMin = fullMax - span; }
      }

      onRangeChange(newMin, newMax);
    };

    const handleUp = () => setDragging(null);

    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [dragging, fullMin, fullMax, fullRange, onRangeChange]);

  return (
    <div
      ref={minimapRef}
      className="relative select-none"
      style={{ marginLeft: leftOffset, height: MINIMAP_H }}
    >
      {/* Density background */}
      <svg width={width} height={MINIMAP_H} className="block">
        <rect x={0} y={0} width={width} height={MINIMAP_H} fill="#f8f9fa" />
        {densityBuckets.map((v, i) => {
          const bw = width / densityBuckets.length;
          return (
            <rect
              key={i}
              x={i * bw}
              y={MINIMAP_H - v * (MINIMAP_H - 4)}
              width={bw}
              height={v * (MINIMAP_H - 4)}
              fill="#c7d2fe"
              opacity={0.5}
            />
          );
        })}

        {/* Dimmed areas outside selection */}
        <rect x={0} y={0} width={selLeft} height={MINIMAP_H} fill="rgba(0,0,0,0.08)" />
        <rect x={selLeft + selWidth} y={0} width={width - selLeft - selWidth} height={MINIMAP_H} fill="rgba(0,0,0,0.08)" />

        {/* Selection highlight */}
        <rect x={selLeft} y={0} width={selWidth} height={MINIMAP_H} fill="rgba(91,118,254,0.08)" stroke="#5b76fe" strokeWidth={1} />
      </svg>

      {/* Drag handles */}
      <div
        className="absolute top-0 w-1.5 rounded-sm cursor-ew-resize bg-[#5b76fe] hover:bg-[#4a65ed]"
        style={{ left: selLeft - 1, height: MINIMAP_H }}
        onMouseDown={(e) => handleMouseDown(e, "left")}
      />
      <div
        className="absolute top-0 w-1.5 rounded-sm cursor-ew-resize bg-[#5b76fe] hover:bg-[#4a65ed]"
        style={{ left: selLeft + selWidth - 1, height: MINIMAP_H }}
        onMouseDown={(e) => handleMouseDown(e, "right")}
      />
      {/* Center drag area */}
      <div
        className="absolute top-0 cursor-grab active:cursor-grabbing"
        style={{ left: selLeft + 2, width: selWidth - 4, height: MINIMAP_H }}
        onMouseDown={(e) => handleMouseDown(e, "center")}
      />

      {/* Date labels */}
      <div className="absolute top-0 left-0 text-[9px] text-slate-400 px-1 leading-[36px]">
        {new Date(fullMin).getFullYear()}
      </div>
      <div className="absolute top-0 right-0 text-[9px] text-slate-400 px-1 leading-[36px]">
        {new Date(fullMax).getFullYear()}
      </div>
    </div>
  );
}
