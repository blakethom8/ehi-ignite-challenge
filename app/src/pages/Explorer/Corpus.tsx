import { useQuery } from "@tanstack/react-query";
import { Users, Activity, Layers, User, Download } from "lucide-react";
import { api } from "../../api/client";
import type { CorpusStats } from "../../types";

// ── helpers ────────────────────────────────────────────────────────────────

function fmt(n: number, decimals = 0): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// ── sub-components ─────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ElementType;
}) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px] flex items-start gap-4">
      <div className="shrink-0 w-9 h-9 rounded-lg bg-[#eef1ff] flex items-center justify-center">
        <Icon size={18} className="text-[#5b76fe]" />
      </div>
      <div>
        <p className="text-xs text-[#555a6a] uppercase tracking-wide mb-0.5">{label}</p>
        <p className="text-2xl font-semibold text-[#1c1c1e] leading-none">{value}</p>
        {sub && <p className="text-xs text-[#a5a8b5] mt-1">{sub}</p>}
      </div>
    </div>
  );
}

function SectionTitle({ icon: Icon, label }: { icon: React.ElementType; label: string }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <Icon size={16} className="text-[#5b76fe]" />
      <h2 className="text-sm font-semibold text-[#1c1c1e] uppercase tracking-wide">{label}</h2>
    </div>
  );
}

const TIER_CONFIG: Record<
  string,
  { label: string; color: string; bg: string; border: string; order: number }
> = {
  simple: {
    label: "Simple",
    color: "#10b981",
    bg: "#ecfdf5",
    border: "#10b981",
    order: 0,
  },
  moderate: {
    label: "Moderate",
    color: "#5b76fe",
    bg: "#eef1ff",
    border: "#5b76fe",
    order: 1,
  },
  complex: {
    label: "Complex",
    color: "#f59e0b",
    bg: "#fffbeb",
    border: "#f59e0b",
    order: 2,
  },
  highly_complex: {
    label: "Highly Complex",
    color: "#ef4444",
    bg: "#fef2f2",
    border: "#ef4444",
    order: 3,
  },
};

function GenderSplit({ breakdown }: { breakdown: Record<string, number> }) {
  const total = Object.values(breakdown).reduce((a, b) => a + b, 0);
  const male = breakdown["male"] ?? 0;
  const female = breakdown["female"] ?? 0;
  const malePct = total > 0 ? (male / total) * 100 : 0;
  const femalePct = total > 0 ? (female / total) * 100 : 0;

  return (
    <div className="bg-white rounded-xl p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <SectionTitle icon={Users} label="Gender Split" />
      <div className="mb-3">
        <div className="flex rounded-lg overflow-hidden h-8">
          <div
            className="flex items-center justify-center text-white text-xs font-semibold transition-all"
            style={{ width: `${malePct}%`, backgroundColor: "#5b76fe" }}
          >
            {malePct >= 10 ? `${malePct.toFixed(1)}%` : ""}
          </div>
          <div
            className="flex items-center justify-center text-white text-xs font-semibold transition-all"
            style={{ width: `${femalePct}%`, backgroundColor: "#a78bfa" }}
          >
            {femalePct >= 10 ? `${femalePct.toFixed(1)}%` : ""}
          </div>
        </div>
      </div>
      <div className="flex gap-6 text-sm">
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-3 h-3 rounded-sm shrink-0"
            style={{ backgroundColor: "#5b76fe" }}
          />
          <span className="text-[#555a6a]">
            Male <span className="font-semibold text-[#1c1c1e]">{male.toLocaleString()}</span>{" "}
            <span className="text-[#a5a8b5]">({malePct.toFixed(1)}%)</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="inline-block w-3 h-3 rounded-sm shrink-0"
            style={{ backgroundColor: "#a78bfa" }}
          />
          <span className="text-[#555a6a]">
            Female <span className="font-semibold text-[#1c1c1e]">{female.toLocaleString()}</span>{" "}
            <span className="text-[#a5a8b5]">({femalePct.toFixed(1)}%)</span>
          </span>
        </div>
      </div>
    </div>
  );
}

function ComplexityTiers({
  breakdown,
  total,
}: {
  breakdown: Record<string, number>;
  total: number;
}) {
  const sorted = Object.entries(breakdown).sort(([a], [b]) => {
    const aOrder = TIER_CONFIG[a]?.order ?? 99;
    const bOrder = TIER_CONFIG[b]?.order ?? 99;
    return aOrder - bOrder;
  });

  return (
    <div className="bg-white rounded-xl p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <SectionTitle icon={Layers} label="Complexity Tiers" />
      <div className="grid grid-cols-2 gap-3">
        {sorted.map(([key, count]) => {
          const cfg = TIER_CONFIG[key];
          const pct = total > 0 ? (count / total) * 100 : 0;
          return (
            <div
              key={key}
              className="rounded-lg border p-4"
              style={{ backgroundColor: cfg?.bg ?? "#f5f6f8", borderColor: `${cfg?.color ?? "#e9eaef"}33` }}
            >
              <p
                className="text-xs font-semibold uppercase tracking-wide mb-1"
                style={{ color: cfg?.color ?? "#555a6a" }}
              >
                {cfg?.label ?? key}
              </p>
              <p className="text-2xl font-bold text-[#1c1c1e] leading-none">
                {count.toLocaleString()}
              </p>
              <p className="text-xs mt-1" style={{ color: cfg?.color ?? "#555a6a" }}>
                {pct.toFixed(1)}% of corpus
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ClinicalAverages({ stats }: { stats: CorpusStats }) {
  const avgResourcesPerPatient = stats.total_patients > 0
    ? stats.total_resources / stats.total_patients
    : 0;

  const rows: { label: string; value: string; sub?: string }[] = [
    { label: "Avg encounters per patient", value: fmt(stats.avg_encounter_count, 1) },
    { label: "Avg active conditions per patient", value: fmt(stats.avg_active_condition_count, 1) },
    { label: "Avg active medications per patient", value: fmt(stats.avg_active_med_count, 1) },
    {
      label: "Avg resources per patient",
      value: fmt(avgResourcesPerPatient, 1),
      sub: "computed from total_resources / total_patients",
    },
  ];

  return (
    <div className="bg-white rounded-xl p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <SectionTitle icon={Activity} label="Clinical Averages per Patient" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-0 divide-y divide-[#f5f6f8]">
        {rows.map(({ label, value, sub }) => (
          <div key={label} className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm text-[#555a6a]">{label}</p>
              {sub && <p className="text-xs text-[#a5a8b5] mt-0.5">{sub}</p>}
            </div>
            <p className="text-xl font-semibold text-[#1c1c1e] ml-4 shrink-0">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── main content ──────────────────────────────────────────────────────────

function CorpusContent({ stats }: { stats: CorpusStats }) {
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[#1c1c1e]">Patient Corpus</h1>
          <p className="text-sm text-[#555a6a] mt-1">
            1,180 Synthea R4 FHIR bundles · EHI Ignite dataset
          </p>
        </div>
        <a
          href="/api/corpus/export?format=csv"
          download="ehi-export.zip"
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#5b76fe] text-white text-sm font-medium hover:bg-[#4a63e0] transition-colors shrink-0"
        >
          <Download size={15} />
          Export CSV
        </a>
      </div>

      {/* KPI bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="Total Patients"
          value={stats.total_patients.toLocaleString()}
          sub="Synthea R4 bundles"
          icon={Users}
        />
        <KpiCard
          label="Total Encounters"
          value={stats.total_encounters.toLocaleString()}
          sub={`avg ${fmt(stats.avg_encounter_count, 1)} per patient`}
          icon={Activity}
        />
        <KpiCard
          label="Total Resources"
          value={stats.total_resources.toLocaleString()}
          sub={`avg ${fmt(stats.total_resources / stats.total_patients, 0)} per patient`}
          icon={Layers}
        />
        <KpiCard
          label="Avg Age"
          value={`${fmt(stats.avg_age, 1)} yrs`}
          sub="across all patients"
          icon={User}
        />
      </div>

      {/* Population Overview */}
      <div>
        <h2 className="text-base font-semibold text-[#1c1c1e] mb-3">Population Overview</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <GenderSplit breakdown={stats.gender_breakdown} />
          <ComplexityTiers
            breakdown={stats.complexity_tier_breakdown}
            total={stats.total_patients}
          />
        </div>
      </div>

      {/* Clinical Averages */}
      <ClinicalAverages stats={stats} />

      {/* Footer note */}
      <div className="rounded-lg bg-[#fafafa] border border-[#e9eaef] px-4 py-3 text-xs text-[#a5a8b5]">
        Note: Corpus stats are computed on first load and cached in memory. Subsequent loads are instant.
      </div>
    </div>
  );
}

// ── page export ───────────────────────────────────────────────────────────

export function ExplorerCorpus() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["corpus-stats"],
    queryFn: api.getCorpusStats,
    staleTime: Infinity,
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 p-8 text-center">
        <div className="w-8 h-8 rounded-full border-2 border-[#5b76fe] border-t-transparent animate-spin" />
        <div>
          <p className="text-sm font-medium text-[#1c1c1e]">Loading corpus data…</p>
          <p className="text-xs text-[#a5a8b5] mt-1">
            This may take a moment as we analyze 1,180 patient records
          </p>
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-sm text-[#600000]">Failed to load corpus statistics.</div>
      </div>
    );
  }

  return <CorpusContent stats={data} />;
}
