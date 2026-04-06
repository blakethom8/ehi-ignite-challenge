import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { AlertCircle, AlertTriangle, User, ChevronDown, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { PatientOverview, ResourceTypeCount, KeyLabsResponse, LabValue, LabHistoryPoint, LabAlertFlag } from "../../types";

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

const CATEGORY_COLORS: Record<string, string> = {
  Clinical:       "#5b76fe",
  Billing:        "#f59e0b",
  Administrative: "#9ca3af",
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

function StatCard({
  label, value, sub,
}: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-xl p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <p className="text-xs text-[#555a6a] uppercase tracking-wide mb-1">{label}</p>
      <p className="text-2xl font-semibold text-[#1c1c1e]">{value}</p>
      {sub && <p className="text-xs text-[#a5a8b5] mt-0.5">{sub}</p>}
    </div>
  );
}


function ResourceChart({ data }: { data: ResourceTypeCount[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || data.length === 0) return;

    const byCategory = data.reduce<Record<string, { x: number[]; y: string[] }>>(
      (acc, d) => {
        if (!acc[d.category]) acc[d.category] = { x: [], y: [] };
        acc[d.category].x.push(d.count);
        acc[d.category].y.push(d.resource_type);
        return acc;
      },
      {}
    );

    const traces = Object.entries(byCategory).map(([cat, vals]) => ({
      type: "bar" as const,
      orientation: "h" as const,
      name: cat,
      x: vals.x,
      y: vals.y,
      marker: { color: CATEGORY_COLORS[cat] ?? "#9ca3af" },
    }));

    const height = Math.max(250, data.length * 26);

    import("plotly.js-dist-min").then((Plotly) => {
      if (!ref.current) return;
      Plotly.react(ref.current, traces, {
        barmode: "stack",
        height,
        margin: { l: 180, r: 20, t: 10, b: 30 },
        yaxis: { autorange: "reversed" as const, tickfont: { size: 12 } },
        xaxis: { tickfont: { size: 11 } },
        legend: { orientation: "h" as const, y: -0.08, x: 0 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { family: "Noto Sans" },
      }, { displayModeBar: false, responsive: true });
    });
  }, [data]);

  return <div ref={ref} style={{ width: "100%" }} />;
}

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

function OverviewContent({ overview, keyLabs }: { overview: PatientOverview; keyLabs: KeyLabsResponse | undefined }) {
  const tierLabel = overview.complexity_tier.replace("_", " ");

  const { prefs, toggle } = useSectionPrefs({
    demographics: true,
    dataSpan: true,
    resources: true,
    conditions: true,
    medications: true,
    allergies: true,
    immunizations: false,
    keyLabs: true,
  });

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[#1c1c1e]">{overview.name}</h1>
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
        <span
          className={`text-xs font-medium px-3 py-1 rounded-full capitalize ${
            TIER_STYLES[overview.complexity_tier] ?? "bg-gray-100 text-gray-600"
          }`}
        >
          {tierLabel} complexity · {overview.complexity_score.toFixed(0)}/100
        </span>
      </div>

      {/* Top metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard label="Total Resources" value={overview.total_resources.toLocaleString()} />
        <StatCard
          label="Clinical"
          value={overview.clinical_resource_count.toLocaleString()}
          sub={`${(100 - overview.billing_pct).toFixed(0)}% of total`}
        />
        <StatCard
          label="Billing"
          value={overview.billing_resource_count.toLocaleString()}
          sub={`${overview.billing_pct.toFixed(0)}% of total`}
        />
        <StatCard label="Encounters" value={overview.encounter_count} />
        <StatCard label="Years of History" value={overview.years_of_history.toFixed(1)} />
        <StatCard label="Unique Lab Types" value={overview.unique_loinc_count} />
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

      {/* Resource distribution */}
      <CollapsibleSection
        title="Resource Distribution"
        sectionKey="resources"
        isOpen={prefs.resources}
        onToggle={() => toggle("resources")}
        badge={overview.resource_type_counts.length}
      >
        <div className="px-5 py-4">
          <ResourceChart data={overview.resource_type_counts} />
        </div>
      </CollapsibleSection>

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
            {overview.conditions.length === 0 ? (
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
                    {overview.conditions.map((c) => (
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
            {overview.medications.length === 0 ? (
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
                    {overview.medications.map((m) => (
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
            {(() => {
              const populatedPanels = Object.entries(keyLabs.panels).filter(([, labs]) => labs.length > 0);
              if (populatedPanels.length === 0) {
                return (
                  <p className="text-sm text-[#a5a8b5]">No quantitative lab values found.</p>
                );
              }
              return (
                <div className="space-y-3">
                  {populatedPanels.map(([panelName, labs]) => (
                    <LabPanel key={panelName} name={panelName} labs={labs} />
                  ))}
                </div>
              );
            })()}
          </div>
        </CollapsibleSection>
      )}

      {/* Parse warnings */}
      {overview.parse_warning_count > 0 && (
        <div className="flex items-start gap-2 bg-[#ffe6cd] text-[#744000] rounded-xl p-4 text-sm">
          <AlertCircle size={16} className="shrink-0 mt-0.5" />
          <span>{overview.parse_warning_count} parse warnings encountered for this bundle.</span>
        </div>
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

  if (!patientId) {
    return (
      <EmptyState
        icon={User}
        title="Choose a patient to begin"
        bullets={[
          "Demographics, complexity tier, and data span",
          "Full resource distribution across FHIR types",
          "Conditions, medications, allergies, and immunizations",
        ]}
        stat="1,180 patients available"
      />
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

  return <OverviewContent overview={data} keyLabs={keyLabs} />;
}
