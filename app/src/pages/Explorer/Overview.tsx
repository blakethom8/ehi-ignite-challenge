import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AlertTriangle, User, ChevronDown, ChevronRight, Clock, Database } from "lucide-react";
import type { ReactNode } from "react";
import { api } from "../../api/client";
import type { PatientOverview, KeyLabsResponse, LabValue, LabHistoryPoint, LabAlertFlag, TimelineMonth, TimelineResponse } from "../../types";

// ── helpers ────────────────────────────────────────────────────────────────

function fmt(dt: string | null): string {
  if (!dt) return "—";
  return new Date(dt).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  });
}

function fmtYear(dt: string | null): string {
  if (!dt) return "—";
  return new Date(dt).getFullYear().toString();
}

const TIER_STYLES: Record<string, string> = {
  simple:        "bg-[#c3faf5] text-[#187574]",
  moderate:      "bg-[#ffe6cd] text-[#744000]",
  complex:       "bg-[#ffc6c6] text-[#600000]",
  highly_complex:"bg-[#ffc6c6] text-[#600000]",
};

// ── section prefs hook ─────────────────────────────────────────────────────

function useSectionPrefs(defaultOpen: Record<string, boolean>) {
  const STORAGE_KEY = "ehi-section-prefs";
  const [prefs, setPrefs] = useState<Record<string, boolean>>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? { ...defaultOpen, ...JSON.parse(stored) } : defaultOpen;
    } catch {
      return defaultOpen;
    }
  });

  const toggle = (key: string) => {
    setPrefs(prev => {
      const next = { ...prev, [key]: !prev[key] };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  };

  return { prefs, toggle };
}

// ── collapsible section wrapper ────────────────────────────────────────────

function CollapsibleSection({
  title, sectionKey, isOpen, onToggle, children, badge,
}: {
  title: string;
  sectionKey: string;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
  badge?: string | number;
}) {
  return (
    <div className="bg-white rounded-xl shadow-[rgb(224_226_232)_0px_0px_0px_1px] overflow-hidden">
      <button
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-controls={`section-${sectionKey}`}
        className="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-[#fafafa] transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-[#1c1c1e]">{title}</span>
          {badge !== undefined && (
            <span className="text-xs px-1.5 py-0.5 rounded-full bg-[#f5f6f8] text-[#555a6a]">{badge}</span>
          )}
        </div>
        <ChevronDown
          size={14}
          className={`text-[#a5a8b5] transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
        />
      </button>
      {isOpen && (
        <div id={`section-${sectionKey}`} className="border-t border-[#f0f1f5]">
          {children}
        </div>
      )}
    </div>
  );
}

// ── sub-components ─────────────────────────────────────────────────────────

// ── trend helpers ──────────────────────────────────────────────────────────

function TrendArrow({ trend }: { trend: LabValue["trend"] }) {
  if (trend === "up") return <span className="text-[#f59e0b] font-bold">↑</span>;
  if (trend === "down") return <span className="text-[#f59e0b] font-bold">↓</span>;
  if (trend === "stable") return <span className="text-[#9ca3af]">→</span>;
  return null;
}

// ── sparkline ──────────────────────────────────────────────────────────────

const SPARK_W = 60;
const SPARK_H = 24;
const SPARK_PAD = 2;

function Sparkline({ history }: { history: LabHistoryPoint[] }) {
  if (history.length < 2) return null;

  const values = history.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1; // avoid divide-by-zero when all values identical

  const toX = (i: number) =>
    SPARK_PAD + (i / (values.length - 1)) * (SPARK_W - SPARK_PAD * 2);
  const toY = (v: number) =>
    SPARK_PAD + (1 - (v - min) / range) * (SPARK_H - SPARK_PAD * 2);

  const points = values.map((v, i) => `${toX(i)},${toY(v)}`).join(" ");

  const first = values[0];
  const last = values[values.length - 1];
  const color =
    last > first + range * 0.02
      ? "#5b76fe"
      : last < first - range * 0.02
      ? "#ef4444"
      : "#9ca3af";

  const dotX = toX(values.length - 1);
  const dotY = toY(last);

  return (
    <svg
      width={SPARK_W}
      height={SPARK_H}
      viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}
      className="shrink-0"
      aria-hidden="true"
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={dotX} cy={dotY} r="2.5" fill={color} />
    </svg>
  );
}

// ── lab alert banner ───────────────────────────────────────────────────────

function LabAlertBanner({ flags }: { flags: LabAlertFlag[] }) {
  const [expanded, setExpanded] = useState(false);
  if (flags.length === 0) return null;

  const criticalCount = flags.filter((f) => f.severity === "critical").length;
  const warningCount = flags.filter((f) => f.severity === "warning").length;

  const summaryParts: string[] = [];
  if (criticalCount > 0) summaryParts.push(`${criticalCount} critical`);
  if (warningCount > 0) summaryParts.push(`${warningCount} warning${warningCount !== 1 ? "s" : ""}`);
  const summaryText = summaryParts.join(", ");

  return (
    <div className="mb-3">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-[#f59e0b] bg-[#fffbeb] hover:bg-[#fef3c7] transition-colors text-left"
      >
        <AlertTriangle size={14} className="text-[#f59e0b] shrink-0" />
        <span className="text-sm font-semibold text-[#744000]">
          {flags.length} recent lab alert{flags.length !== 1 ? "s" : ""} — {summaryText}
        </span>
        <ChevronDown
          size={13}
          className={`ml-auto text-[#a5a8b5] transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      {expanded && (
        <div className="mt-1 space-y-1.5">
          {flags.map((flag) => {
            const isCritical = flag.severity === "critical";
            return (
              <div
                key={`${flag.loinc_code}-${flag.days_ago}`}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg border text-sm ${
                  isCritical
                    ? "bg-[#fef2f2] border-[#ef4444]"
                    : "bg-[#fffbeb] border-[#f59e0b]"
                }`}
              >
                <span
                  className={`shrink-0 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                    isCritical
                      ? "bg-[#ef4444] text-white"
                      : "bg-[#f59e0b] text-white"
                  }`}
                >
                  {isCritical ? "CRITICAL" : "WARNING"}
                </span>
                <span className="font-medium text-[#1c1c1e] shrink-0">{flag.lab_name}</span>
                <span className="text-[#555a6a] flex-1">{flag.message}</span>
                <span className="text-[#a5a8b5] text-xs shrink-0">
                  {flag.days_ago === 0 ? "today" : `${flag.days_ago}d ago`}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── lab panel ──────────────────────────────────────────────────────────────

function LabPanel({ name, labs }: { name: string; labs: LabValue[] }) {
  const [open, setOpen] = useState(true);

  return (
    <div className="border border-[#e9eaef] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-[#f9fafb] hover:bg-[#f5f6f8] transition-colors text-left"
      >
        <span className="text-xs font-semibold text-[#1c1c1e] uppercase tracking-wide">{name}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#a5a8b5]">{labs.length} value{labs.length !== 1 ? "s" : ""}</span>
          {open ? <ChevronDown size={14} className="text-[#a5a8b5]" /> : <ChevronRight size={14} className="text-[#a5a8b5]" />}
        </div>
      </button>
      {open && (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-[#a5a8b5] border-b border-[#e9eaef] bg-white">
              <th className="pb-2 pt-2 px-4 font-medium">Lab</th>
              <th className="pb-2 pt-2 px-2 font-medium text-right">Value</th>
              <th className="pb-2 pt-2 px-2 font-medium text-center">History</th>
              <th className="pb-2 pt-2 px-2 font-medium text-center">Trend</th>
              <th className="pb-2 pt-2 px-4 font-medium text-right">Date</th>
            </tr>
          </thead>
          <tbody>
            {labs.map((lab) => (
              <tr key={lab.loinc_code} className="border-b border-[#f5f6f8] hover:bg-[#f9fafb]">
                <td className="py-2 px-4 text-[#1c1c1e]">{lab.display}</td>
                <td className="py-2 px-2 text-right">
                  {lab.value != null ? (
                    <span className={lab.is_abnormal ? "text-[#b91c1c] font-semibold" : "text-[#1c1c1e]"}>
                      {lab.value} <span className="text-[#a5a8b5] text-xs">{lab.unit}</span>
                    </span>
                  ) : (
                    <span className="text-[#a5a8b5]">—</span>
                  )}
                </td>
                <td className="py-2 px-2 text-center">
                  <Sparkline history={lab.history ?? []} />
                </td>
                <td className="py-2 px-2 text-center">
                  <TrendArrow trend={lab.trend} />
                </td>
                <td className="py-2 px-4 text-right text-[#a5a8b5] text-xs">{fmt(lab.effective_dt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Lab History Timeline ───────────────────────────────────────────────────

// LOINC codes that are "critical-direction" codes for dot coloring
const CRITICAL_LOINC_CODES = new Set(["718-7", "4544-3", "6301-6", "2160-0"]);

function dotColor(month: TimelineMonth): string {
  for (const ev of month.events) {
    if (CRITICAL_LOINC_CODES.has(ev.loinc_code)) {
      if (ev.change_direction === "down") return "#ef4444"; // red
      if (ev.change_direction === "up") return "#f59e0b";  // amber
    }
  }
  return "#5b76fe"; // blue (default)
}

function ChangeArrow({ dir }: { dir: "up" | "down" | "stable" }) {
  if (dir === "up") return <span className="text-[#f59e0b] font-bold">↑</span>;
  if (dir === "down") return <span className="text-[#ef4444] font-bold">↓</span>;
  return <span className="text-[#9ca3af]">→</span>;
}

function dateSortValue(value: string | null): number {
  if (!value) return Number.NEGATIVE_INFINITY;
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? Number.NEGATIVE_INFINITY : timestamp;
}

function LabHistoryTimeline({ keyLabs }: { keyLabs: KeyLabsResponse }) {
  const [openMonth, setOpenMonth] = useState<string | null>(null);

  const events = keyLabs.timeline_events ?? [];

  return (
    <div className="mt-3 border-t border-[#f0f1f5] pt-3">
      <div className="flex items-center gap-2 mb-3">
        <Clock size={13} className="text-[#a5a8b5]" />
        <span className="text-xs font-semibold text-[#555a6a] uppercase tracking-wide">
          Lab History Timeline
        </span>
        <span className="text-[10px] text-[#a5a8b5] ml-1">(last 6 months)</span>
      </div>

      {events.length === 0 ? (
        <p className="text-xs text-[#a5a8b5] italic">No lab observations in the last 6 months.</p>
      ) : (
        <div className="overflow-x-auto">
          {/* Timeline row */}
          <div className="relative flex items-start gap-0 min-w-0">
            {/* Connecting line — positioned at dot center */}
            <div
              className="absolute left-0 right-0 border-t border-[#e9eaef]"
              style={{ top: "calc(0.75rem + 10px)" }}  /* text-[10px] ~12px + gap ~10px = label height before dot */
            />

            {events.map((month) => {
              const color = dotColor(month);
              const isOpen = openMonth === month.month;

              return (
                <div
                  key={month.month}
                  className="relative flex flex-col items-center"
                  style={{ minWidth: "80px", flex: "0 0 80px" }}
                >
                  {/* Month label */}
                  <span className="text-[10px] text-[#a5a8b5] mb-1.5 whitespace-nowrap">
                    {month.label}
                  </span>

                  {/* Dot */}
                  <button
                    onClick={() => setOpenMonth(isOpen ? null : month.month)}
                    title={`${month.label} — ${month.events.length} lab${month.events.length !== 1 ? "s" : ""}`}
                    className="relative z-10 w-3 h-3 rounded-full border-2 border-white shadow-sm transition-transform hover:scale-125 focus:outline-none focus:ring-2 focus:ring-offset-1"
                    style={{ backgroundColor: color }}
                    aria-expanded={isOpen}
                    aria-label={`${month.label}: ${month.events.length} observations`}
                  />

                  {/* Count badge below dot */}
                  <span className="mt-1 text-[9px] text-[#a5a8b5]">{month.events.length}</span>
                </div>
              );
            })}
          </div>

          {/* Popover panel — shown below timeline for whichever month is open */}
          {openMonth && (() => {
            const month = events.find((m) => m.month === openMonth);
            if (!month) return null;
            return (
              <div className="mt-3 border border-[#e9eaef] rounded-lg overflow-hidden bg-white">
                <div className="px-3 py-2 bg-[#f9fafb] border-b border-[#e9eaef]">
                  <span className="text-xs font-semibold text-[#1c1c1e]">{month.label}</span>
                  <span className="text-[10px] text-[#a5a8b5] ml-2">{month.events.length} observation{month.events.length !== 1 ? "s" : ""}</span>
                </div>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-[10px] text-[#a5a8b5] border-b border-[#f0f1f5]">
                      <th className="px-3 py-1.5 font-medium">Lab</th>
                      <th className="px-2 py-1.5 font-medium text-right">Value</th>
                      <th className="px-2 py-1.5 font-medium text-center">Change</th>
                      <th className="px-3 py-1.5 font-medium text-right">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {month.events.map((ev) => (
                      <tr key={ev.loinc_code} className="border-b border-[#f5f6f8] hover:bg-[#f9fafb]">
                        <td className="px-3 py-1.5 text-[#1c1c1e]">{ev.display_name}</td>
                        <td className="px-2 py-1.5 text-right text-[#1c1c1e]">
                          {ev.value} <span className="text-[#a5a8b5]">{ev.unit}</span>
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <ChangeArrow dir={ev.change_direction} />
                        </td>
                        <td className="px-3 py-1.5 text-right text-[#a5a8b5]">
                          {new Date(ev.date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}

function CareActivityStrip({ timeline }: { timeline: TimelineResponse | undefined }) {
  if (!timeline || Object.keys(timeline.year_counts).length === 0) return null;

  const yearsWithCounts = Object.entries(timeline.year_counts)
    .map(([year, count]) => ({ year: Number(year), count }))
    .sort((a, b) => a.year - b.year);
  const firstYear = yearsWithCounts[0].year;
  const lastYear = yearsWithCounts[yearsWithCounts.length - 1].year;
  const countsByYear = new Map(yearsWithCounts.map((entry) => [entry.year, entry.count]));
  const fullYearEntries = Array.from({ length: lastYear - firstYear + 1 }, (_, index) => {
    const year = firstYear + index;
    return { year, count: countsByYear.get(year) ?? 0 };
  });
  const maxCount = Math.max(...fullYearEntries.map((entry) => entry.count), 1);
  const gapYears = fullYearEntries.filter((entry) => entry.count === 0).length;
  const peakYear = fullYearEntries.reduce((best, entry) => (entry.count > best.count ? entry : best), fullYearEntries[0]);
  const activeYearSummary = yearsWithCounts
    .map((entry) => `${entry.year} (${entry.count})`)
    .join(", ");
  const recentEncounters = [...timeline.encounters]
    .filter((encounter) => encounter.start)
    .sort((a, b) => (b.start || "").localeCompare(a.start || ""))
    .slice(0, 3);
  const recentByClass = recentEncounters.reduce<Record<string, number>>((acc, encounter) => {
    const key = encounter.class_code || "Unknown";
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
  const recentClassSummary = Object.entries(recentByClass)
    .map(([label, count]) => `${count} ${label}`)
    .join(" / ");

  return (
    <div className="bg-white rounded-xl shadow-[rgb(224_226_232)_0px_0px_0px_1px] px-5 py-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-[#1c1c1e]">Care activity</p>
          <p className="mt-1 text-xs text-[#6b7280]">
            Compact full-range view from {firstYear} to {lastYear}; gray ticks show years without encounters.
          </p>
        </div>
        <Link
          to={`/explorer/timeline?patient=${timeline.patient_id}`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#5b76fe] hover:underline"
        >
          Open encounter timeline
          <ChevronRight size={13} />
        </Link>
      </div>

      <div className="mt-4 rounded-xl border border-[#e9eaef] bg-[#fafafa] px-3 py-3">
        <div className="mb-3 flex flex-wrap gap-2 text-[11px] text-[#6b7280]">
          <span className="rounded-full bg-white px-2.5 py-1">
            Peak: {peakYear.year} ({peakYear.count} encounter{peakYear.count !== 1 ? "s" : ""})
          </span>
          <span className="rounded-full bg-white px-2.5 py-1">
            Gap years: {gapYears}
          </span>
          {recentClassSummary && (
            <span className="rounded-full bg-white px-2.5 py-1">
              Recent mix: {recentClassSummary}
            </span>
          )}
        </div>

        <div
          className="grid items-end gap-px"
          style={{ gridTemplateColumns: `repeat(${fullYearEntries.length}, minmax(0, 1fr))` }}
        >
          {fullYearEntries.map((entry) => {
            const hasActivity = entry.count > 0;
            const height = hasActivity ? 10 + (entry.count / maxCount) * 54 : 4;
            return (
              <div key={entry.year} className="flex min-w-0 flex-col items-center gap-1">
                <div
                  className={`w-full max-w-[12px] rounded-t-sm ${hasActivity ? "bg-[#5b76fe]" : "bg-[#d9dce5]"}`}
                  style={{ height }}
                  title={`${entry.year}: ${entry.count} encounter${entry.count !== 1 ? "s" : ""}`}
                />
              </div>
            );
          })}
        </div>

        <div className="mt-2 flex justify-between text-[10px] text-[#6b7280]">
          <span>{firstYear}</span>
          <span>{Math.floor((firstYear + lastYear) / 2)}</span>
          <span>{lastYear}</span>
        </div>

        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-[11px] leading-5 text-[#6b7280]">
          <span className="font-semibold text-[#555a6a]">Active years:</span> {activeYearSummary}
        </div>
      </div>

      {recentEncounters.length > 0 && (
        <div className="mt-4 grid gap-2 md:grid-cols-3">
          {recentEncounters.map((encounter) => (
            <div key={encounter.encounter_id} className="rounded-lg border border-[#e9eaef] bg-[#fafafa] px-3 py-2">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-[#5b76fe]">
                  {encounter.class_code || "Unknown"}
                </span>
                <span className="text-[10px] text-[#a5a8b5]">{fmt(encounter.start)}</span>
              </div>
              <p className="line-clamp-2 text-xs font-semibold leading-5 text-[#1c1c1e]">
                {encounter.reason_display || encounter.encounter_type || encounter.class_code || "Encounter"}
              </p>
              <p className="mt-1 text-[11px] text-[#6b7280]">
                {encounter.linked_observation_count} labs/vitals · {encounter.linked_condition_count} conditions · {encounter.linked_procedure_count} procedures
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Skeleton ───────────────────────────────────────────────────────────────

function SkeletonRect({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-[#f0f1f5] rounded ${className ?? ""}`} />
  );
}

function OverviewSkeleton() {
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <SkeletonRect className="h-7 w-56" />
          <SkeletonRect className="h-4 w-80" />
        </div>
        <SkeletonRect className="h-6 w-36 rounded-full" />
      </div>

      {/* KPI stat cards — 6 columns */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-white rounded-xl p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px] space-y-2">
            <SkeletonRect className="h-3 w-20" />
            <SkeletonRect className="h-7 w-12" />
            <SkeletonRect className="h-3 w-16" />
          </div>
        ))}
      </div>

      {/* Demographics + Data span */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white rounded-xl p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px] space-y-3">
          <SkeletonRect className="h-4 w-32" />
          <div className="grid grid-cols-2 gap-x-8 gap-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <SkeletonRect key={i} className="h-4 w-full" />
            ))}
          </div>
        </div>
        <div className="bg-white rounded-xl p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px] space-y-3">
          <SkeletonRect className="h-4 w-24" />
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-1">
              <SkeletonRect className="h-3 w-20" />
              <SkeletonRect className="h-4 w-36" />
            </div>
          ))}
        </div>
      </div>

      {/* Resource chart placeholder */}
      <div className="bg-white rounded-xl p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px] space-y-3">
        <SkeletonRect className="h-4 w-40" />
        <SkeletonRect className="h-48 w-full" />
      </div>

      {/* Conditions + Medications tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[0, 1].map((col) => (
          <div key={col} className="bg-white rounded-xl p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px] space-y-3">
            <SkeletonRect className="h-4 w-48" />
            {/* Table header */}
            <div className="flex gap-4 border-b border-[#f0f1f5] pb-2">
              <SkeletonRect className="h-3 w-14" />
              <SkeletonRect className="h-3 w-32" />
              <SkeletonRect className="h-3 w-10" />
            </div>
            {/* 5 skeleton rows */}
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4 py-1">
                <SkeletonRect className="h-5 w-16 rounded-full" />
                <SkeletonRect className="h-4 flex-1" />
                <SkeletonRect className="h-4 w-10" />
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Allergies + Immunizations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[0, 1].map((col) => (
          <div key={col} className="bg-white rounded-xl p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px] space-y-3">
            <SkeletonRect className="h-4 w-44" />
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <SkeletonRect key={i} className="h-7 w-24 rounded-lg" />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Key Labs placeholder */}
      <div className="bg-white rounded-xl p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px] space-y-3">
        <SkeletonRect className="h-4 w-24" />
        {Array.from({ length: 3 }).map((_, i) => (
          <SkeletonRect key={i} className="h-10 w-full rounded-lg" />
        ))}
      </div>
    </div>
  );
}

// ── main component ─────────────────────────────────────────────────────────

function OverviewContent({
  overview,
  keyLabs,
  timeline,
  patientId,
}: {
  overview: PatientOverview;
  keyLabs: KeyLabsResponse | undefined;
  timeline: TimelineResponse | undefined;
  patientId: string;
}) {
  const tierLabel = overview.complexity_tier.replace("_", " ");
  const sortedConditions = [...overview.conditions].sort(
    (a, b) => dateSortValue(b.onset_dt) - dateSortValue(a.onset_dt)
  );
  const sortedMedications = [...overview.medications].sort(
    (a, b) => dateSortValue(b.authored_on) - dateSortValue(a.authored_on)
  );

  const { prefs, toggle } = useSectionPrefs({
    demographics: true,
    dataSpan: true,
    conditions: true,
    medications: true,
    allergies: true,
    immunizations: false,
    keyLabs: true,
  });

  return (
    <div className="p-6 space-y-6">
      <section className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Patient summary</p>
            <h1 className="mt-1 text-2xl font-semibold text-[#1c1c1e]">{overview.name}</h1>
            <p className="text-sm text-[#555a6a] mt-0.5">
              {overview.gender.charAt(0).toUpperCase() + overview.gender.slice(1)} ·{" "}
              {overview.age_years.toFixed(0)} years old ·{" "}
              {overview.city && overview.state ? `${overview.city}, ${overview.state}` : "Location unknown"}
              {overview.is_deceased && (
                <span className="ml-2 text-xs bg-[#ffc6c6] text-[#600000] px-2 py-0.5 rounded-full">
                  Deceased
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to={`/explorer/patient-data?patient=${patientId}`}
              className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full border border-[#e9eaef] text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe] transition-colors"
            >
              <Database size={12} />
              FHIR data
            </Link>
            <span
              className={`text-xs font-medium px-3 py-1 rounded-full capitalize ${
                TIER_STYLES[overview.complexity_tier] ?? "bg-gray-100 text-gray-600"
              }`}
            >
              {tierLabel} complexity · {overview.complexity_score.toFixed(0)}/100
            </span>
          </div>
        </div>

        {/* Demographics + Data span */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <CollapsibleSection
            title="Demographics"
            sectionKey="demographics"
            isOpen={prefs.demographics}
            onToggle={() => toggle("demographics")}
          >
            <div className="px-5 py-4 grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
              {[
                ["Date of Birth", overview.birth_date ?? "—"],
                ["Race", overview.race || "—"],
                ["Ethnicity", overview.ethnicity || "—"],
                ["Language", overview.language || "—"],
                ["Marital Status", overview.marital_status || "—"],
                ...(overview.daly != null ? [["DALY", overview.daly.toFixed(3)]] : []),
                ...(overview.qaly != null ? [["QALY", overview.qaly.toFixed(3)]] : []),
              ].map(([label, val]) => (
                <div key={label} className="flex gap-2">
                  <span className="text-[#a5a8b5] w-28 shrink-0">{label}</span>
                  <span className="text-[#1c1c1e] font-medium">{val}</span>
                </div>
              ))}
            </div>
          </CollapsibleSection>
        </div>

        <div>
          <CollapsibleSection
            title="Data Span"
            sectionKey="dataSpan"
            isOpen={prefs.dataSpan}
            onToggle={() => toggle("dataSpan")}
          >
            <div className="px-5 py-4 space-y-3 text-sm">
              <div>
                <p className="text-[#a5a8b5] text-xs">First Encounter</p>
                <p className="text-[#1c1c1e] font-medium">{fmt(overview.earliest_encounter_dt)}</p>
              </div>
              <div>
                <p className="text-[#a5a8b5] text-xs">Last Encounter</p>
                <p className="text-[#1c1c1e] font-medium">{fmt(overview.latest_encounter_dt)}</p>
              </div>
              <div>
                <p className="text-[#a5a8b5] text-xs">Encounter Classes</p>
                <div className="mt-1 space-y-1">
                  {Object.entries(overview.encounter_class_breakdown).map(([cls, cnt]) => (
                    <div key={cls} className="flex justify-between">
                      <span className="text-[#555a6a]">{cls || "Unknown"}</span>
                      <span className="font-medium">{cnt}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </CollapsibleSection>
        </div>
        </div>
      </section>

      <CareActivityStrip timeline={timeline} />

      {/* Conditions + Medications */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CollapsibleSection
          title="Conditions"
          sectionKey="conditions"
          isOpen={prefs.conditions}
          onToggle={() => toggle("conditions")}
          badge={`${overview.active_condition_count} active · ${overview.resolved_condition_count} resolved`}
        >
          <div className="px-5 py-4">
            {sortedConditions.length === 0 ? (
              <p className="text-sm text-[#a5a8b5]">No conditions recorded.</p>
            ) : (
              <div className="overflow-auto max-h-80">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-[#a5a8b5] border-b border-[#e9eaef]">
                      <th className="pb-2 font-medium">Status</th>
                      <th className="pb-2 font-medium">Condition</th>
                      <th className="pb-2 font-medium">Onset</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedConditions.map((c) => (
                      <tr key={c.condition_id} className="border-b border-[#f5f6f8] hover:bg-[#f9fafb]">
                        <td className="py-1.5 pr-3">
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full ${
                              c.is_active
                                ? "bg-[#c3faf5] text-[#187574]"
                                : "bg-[#f5f6f8] text-[#555a6a]"
                            }`}
                          >
                            {c.is_active ? "Active" : "Resolved"}
                          </span>
                        </td>
                        <td className="py-1.5 pr-3 text-[#1c1c1e]">{c.display}</td>
                        <td className="py-1.5 text-[#a5a8b5]">{fmtYear(c.onset_dt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </CollapsibleSection>

        <CollapsibleSection
          title="Medications"
          sectionKey="medications"
          isOpen={prefs.medications}
          onToggle={() => toggle("medications")}
          badge={`${overview.active_med_count} active · ${overview.total_med_count} total`}
        >
          <div className="px-5 py-4">
            {sortedMedications.length === 0 ? (
              <p className="text-sm text-[#a5a8b5]">No medications recorded.</p>
            ) : (
              <div className="overflow-auto max-h-80">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-[#a5a8b5] border-b border-[#e9eaef]">
                      <th className="pb-2 font-medium">Status</th>
                      <th className="pb-2 font-medium">Medication</th>
                      <th className="pb-2 font-medium">Ordered</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedMedications.map((m) => (
                      <tr key={m.med_id} className="border-b border-[#f5f6f8] hover:bg-[#f9fafb]">
                        <td className="py-1.5 pr-3">
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full capitalize ${
                              m.is_active
                                ? "bg-[#eef1ff] text-[#5b76fe]"
                                : "bg-[#f5f6f8] text-[#555a6a]"
                            }`}
                          >
                            {m.status}
                          </span>
                        </td>
                        <td className="py-1.5 pr-3 text-[#1c1c1e]">{m.display}</td>
                        <td className="py-1.5 text-[#a5a8b5]">{fmtYear(m.authored_on)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </CollapsibleSection>
      </div>

      {/* Allergies + Immunizations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CollapsibleSection
          title="Allergies & Sensitivities"
          sectionKey="allergies"
          isOpen={prefs.allergies}
          onToggle={() => toggle("allergies")}
          badge={overview.allergy_labels.length || undefined}
        >
          <div className="px-5 py-4">
            <p className="text-xs text-[#744000] mb-3">
              Verify cross-reactivity with drug class before prescribing
            </p>
            {overview.allergy_labels.length === 0 ? (
              <div className="flex items-center gap-2 bg-[#ecfdf5] text-[#065f46] rounded-lg px-3 py-2 text-sm">
                <span className="font-medium">No documented allergies</span>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {overview.allergy_labels.map((label) => (
                  <span
                    key={label}
                    className="inline-flex items-center gap-1.5 text-xs bg-[#fffbeb] text-[#744000] border border-[#f59e0b]/40 px-2.5 py-1.5 rounded-lg font-medium"
                  >
                    <AlertTriangle size={12} className="text-[#f59e0b] shrink-0" />
                    {label}
                  </span>
                ))}
              </div>
            )}
          </div>
        </CollapsibleSection>

        <CollapsibleSection
          title="Immunizations"
          sectionKey="immunizations"
          isOpen={prefs.immunizations}
          onToggle={() => toggle("immunizations")}
          badge={`${overview.immunization_count} total · ${overview.unique_vaccines.length} unique`}
        >
          <div className="px-5 py-4">
            {overview.unique_vaccines.length === 0 ? (
              <p className="text-sm text-[#a5a8b5]">No immunizations recorded.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {overview.unique_vaccines.map((v) => (
                  <span key={v} className="text-xs bg-[#f5f6f8] text-[#555a6a] border border-[#e9eaef] px-2.5 py-1 rounded-full">
                    {v}
                  </span>
                ))}
              </div>
            )}
          </div>
        </CollapsibleSection>
      </div>

      {/* Key Labs */}
      {keyLabs && (
        <CollapsibleSection
          title="Key Labs"
          sectionKey="keyLabs"
          isOpen={prefs.keyLabs}
          onToggle={() => toggle("keyLabs")}
        >
          <div className="px-5 py-4">
            {keyLabs.alert_flags && keyLabs.alert_flags.length > 0 && (
              <LabAlertBanner flags={keyLabs.alert_flags} />
            )}
            <LabHistoryTimeline keyLabs={keyLabs} />
            {(() => {
              const populatedPanels = Object.entries(keyLabs.panels).filter(([, labs]) => labs.length > 0);
              if (populatedPanels.length === 0) {
                return (
                  <p className="text-sm text-[#a5a8b5] mt-3">No quantitative lab values found.</p>
                );
              }
              return (
                <div className="space-y-3 mt-3">
                  {populatedPanels.map(([panelName, labs]) => (
                    <LabPanel key={panelName} name={panelName} labs={labs} />
                  ))}
                </div>
              );
            })()}
          </div>
        </CollapsibleSection>
      )}

    </div>
  );
}

// ── page ───────────────────────────────────────────────────────────────────

export function ExplorerOverview() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });

  const { data: keyLabs } = useQuery({
    queryKey: ["key-labs", patientId],
    queryFn: () => api.getKeyLabs(patientId!),
    enabled: !!patientId,
  });

  const { data: timeline } = useQuery({
    queryKey: ["timeline", patientId],
    queryFn: () => api.getTimeline(patientId!),
    enabled: !!patientId,
  });

  if (!patientId) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
          style={{ backgroundColor: "#eef1ff" }}
        >
          <User size={28} style={{ color: "#5b76fe" }} />
        </div>

        <h2 className="text-lg font-semibold text-[#1c1c1e] mb-2">Choose a patient to begin</h2>

        <ul className="text-sm text-[#555a6a] max-w-xs space-y-1.5 text-left list-none">
          {[
            "Demographics, complexity tier, and data span",
            "Full resource distribution across FHIR types",
            "Conditions, medications, allergies, and immunizations",
          ].map((b) => (
            <li key={b} className="flex items-start gap-2">
              <span className="mt-0.5 w-1.5 h-1.5 rounded-full bg-[#5b76fe] shrink-0 inline-block" />
              <span>{b}</span>
            </li>
          ))}
        </ul>

        {/* Flight School banner */}
        <div className="mt-5 max-w-xs w-full rounded-xl border border-[#b2e8e0] bg-[#f0faf8] px-4 py-3 text-left">
          <Link
            to="/analysis/flight-school"
            className="text-sm text-[#187574] hover:underline"
          >
            First time here? Take the 15-minute Flight School →
          </Link>
        </div>

        <div className="mt-3 px-4 py-2 rounded-full bg-[#f5f6f8] border border-[#e9eaef]">
          <span className="text-xs text-[#a5a8b5]">1,180 patients available</span>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return <OverviewSkeleton />;
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-sm text-[#600000]">Failed to load patient data.</div>
      </div>
    );
  }

  return <OverviewContent overview={data} keyLabs={keyLabs} timeline={timeline} patientId={patientId} />;
}
