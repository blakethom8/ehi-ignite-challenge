import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart2, FlaskConical, Users, Hash } from "lucide-react";
import { api } from "../../api/client";
import type { ObservationDistribution } from "../../types";

// ── helpers ────────────────────────────────────────────────────────────────

function fmt(n: number, decimals = 1): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// ── KPI card ───────────────────────────────────────────────────────────────

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

// ── Percentile bar ─────────────────────────────────────────────────────────

function PercentileBar({ d }: { d: ObservationDistribution }) {
  const range = d.max - d.min;
  if (range <= 0) return null;

  // Convert a value to a percentage position within [min, max]
  const pct = (v: number) => Math.max(0, Math.min(100, ((v - d.min) / range) * 100));

  const p10Left = pct(d.p10);
  const p25Left = pct(d.p25);
  const iqrWidth = pct(d.p75) - pct(d.p25);
  const p90Left = pct(d.p90);

  return (
    <div className="relative h-6 flex items-center mt-3 mb-1">
      {/* Background track */}
      <div className="absolute inset-x-0 h-1.5 rounded-full bg-[#e9eaef]" />

      {/* Whisker p10→p90 */}
      <div
        className="absolute h-0.5 bg-[#c7cad5]"
        style={{ left: `${p10Left}%`, width: `${p90Left - p10Left}%` }}
      />

      {/* IQR box p25→p75 */}
      <div
        className="absolute h-3 rounded bg-[#5b76fe] opacity-70"
        style={{ left: `${p25Left}%`, width: `${iqrWidth}%` }}
      />

      {/* Median tick */}
      <div
        className="absolute w-0.5 h-5 bg-[#5b76fe] rounded-full"
        style={{ left: `${pct(d.median)}%`, transform: "translateX(-50%)" }}
      />

      {/* Min / Max labels */}
      <span className="absolute left-0 -bottom-4 text-[10px] text-[#a5a8b5]">
        {fmt(d.min, 2)}
      </span>
      <span className="absolute right-0 -bottom-4 text-[10px] text-[#a5a8b5]">
        {fmt(d.max, 2)}
      </span>

      {/* p10 tick */}
      <div
        className="absolute w-px h-3 bg-[#c7cad5]"
        style={{ left: `${p10Left}%` }}
        title={`p10: ${fmt(d.p10, 2)}`}
      />

      {/* p90 tick */}
      <div
        className="absolute w-px h-3 bg-[#c7cad5]"
        style={{ left: `${p90Left}%` }}
        title={`p90: ${fmt(d.p90, 2)}`}
      />
    </div>
  );
}

// ── Histogram ──────────────────────────────────────────────────────────────

function MiniHistogram({
  counts,
  labels,
}: {
  counts: number[];
  labels: string[];
}) {
  const max = Math.max(...counts, 1);
  return (
    <div className="flex items-end gap-px h-12 mt-5">
      {counts.map((count, i) => {
        const heightPct = (count / max) * 100;
        return (
          <div
            key={i}
            className="group relative flex-1 flex flex-col justify-end cursor-default"
            style={{ height: "100%" }}
          >
            <div
              className="w-full rounded-sm bg-[#5b76fe] opacity-60 group-hover:opacity-100 transition-opacity"
              style={{ height: `${Math.max(heightPct, 2)}%` }}
            />
            {/* Tooltip */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10 pointer-events-none">
              <div className="bg-[#1c1c1e] text-white text-[10px] rounded px-2 py-1 whitespace-nowrap shadow-lg">
                {labels[i]}
                <br />
                {count.toLocaleString()} obs
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Distribution card ──────────────────────────────────────────────────────

function DistributionCard({ d }: { d: ObservationDistribution }) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-[#1c1c1e] text-sm leading-snug truncate">
            {d.display_name}
          </p>
          <div className="flex items-center gap-2 mt-1">
            <span className="inline-block text-[10px] font-mono bg-[#eef1ff] text-[#5b76fe] rounded px-1.5 py-0.5">
              {d.loinc_code}
            </span>
            {d.unit && (
              <span className="text-[10px] text-[#a5a8b5]">{d.unit}</span>
            )}
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-[#f5f6f8] p-2">
          <p className="text-[10px] text-[#a5a8b5] uppercase tracking-wide">Count</p>
          <p className="text-sm font-semibold text-[#1c1c1e]">{d.count.toLocaleString()}</p>
        </div>
        <div className="rounded-lg bg-[#f5f6f8] p-2">
          <p className="text-[10px] text-[#a5a8b5] uppercase tracking-wide">Patients</p>
          <p className="text-sm font-semibold text-[#1c1c1e]">{d.patient_count.toLocaleString()}</p>
        </div>
        <div className="rounded-lg bg-[#f5f6f8] p-2">
          <p className="text-[10px] text-[#a5a8b5] uppercase tracking-wide">Mean</p>
          <p className="text-sm font-semibold text-[#1c1c1e]">{fmt(d.mean, 2)}</p>
        </div>
      </div>

      {/* Percentile summary */}
      <div className="mt-3 text-[11px] text-[#555a6a] flex flex-wrap gap-x-3 gap-y-0.5">
        <span>p10 <strong className="text-[#1c1c1e]">{fmt(d.p10, 2)}</strong></span>
        <span>p25 <strong className="text-[#1c1c1e]">{fmt(d.p25, 2)}</strong></span>
        <span>median <strong className="text-[#1c1c1e]">{fmt(d.median, 2)}</strong></span>
        <span>p75 <strong className="text-[#1c1c1e]">{fmt(d.p75, 2)}</strong></span>
        <span>p90 <strong className="text-[#1c1c1e]">{fmt(d.p90, 2)}</strong></span>
      </div>

      {/* Percentile bar */}
      <PercentileBar d={d} />

      {/* Histogram */}
      <MiniHistogram counts={d.histogram} labels={d.bucket_labels} />
    </div>
  );
}

// ── main page ──────────────────────────────────────────────────────────────

function DistributionsContent({
  distributions,
  totalFound,
  codesShown,
}: {
  distributions: ObservationDistribution[];
  totalFound: number;
  codesShown: number;
}) {
  const [search, setSearch] = useState("");

  const totalObs = distributions.reduce((sum, d) => sum + d.count, 0);

  const filtered = search.trim()
    ? distributions.filter(
        (d) =>
          d.display_name.toLowerCase().includes(search.toLowerCase()) ||
          d.loinc_code.includes(search)
      )
    : distributions;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-[#1c1c1e]">Observation Distributions</h1>
        <p className="text-sm text-[#555a6a] mt-1">
          Population-level lab value distributions across 1,180 patients
        </p>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <KpiCard
          label="LOINC Codes Found"
          value={totalFound.toLocaleString()}
          sub="quantitative codes in corpus"
          icon={Hash}
        />
        <KpiCard
          label="Codes Shown"
          value={codesShown.toLocaleString()}
          sub="top 30 by observation count"
          icon={BarChart2}
        />
        <KpiCard
          label="Total Observations"
          value={totalObs.toLocaleString()}
          sub="across shown codes"
          icon={Users}
        />
      </div>

      {/* Search */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <FlaskConical
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[#a5a8b5]"
          />
          <input
            type="text"
            placeholder="Filter by name or LOINC code…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-2 rounded-lg border border-[#e9eaef] bg-white text-sm text-[#1c1c1e] placeholder:text-[#a5a8b5] focus:outline-none focus:border-[#5b76fe] transition-colors"
          />
        </div>
        {search && (
          <p className="text-xs text-[#a5a8b5]">
            {filtered.length} of {codesShown} codes
          </p>
        )}
      </div>

      {/* Card grid */}
      {filtered.length > 0 ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {filtered.map((d) => (
            <DistributionCard key={d.loinc_code} d={d} />
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center py-16 text-sm text-[#a5a8b5]">
          No LOINC codes match &ldquo;{search}&rdquo;
        </div>
      )}

      {/* Footer note */}
      <div className="rounded-lg bg-[#fafafa] border border-[#e9eaef] px-4 py-3 text-xs text-[#a5a8b5]">
        Only LOINC codes with ≥20 quantitative observations are shown. Distributions are computed
        on first load and cached in memory. Percentile bar: whiskers = p10/p90, box = IQR (p25–p75),
        line = median.
      </div>
    </div>
  );
}

// ── page export ───────────────────────────────────────────────────────────

export function ExplorerDistributions() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["observation-distributions"],
    queryFn: api.getObservationDistributions,
    staleTime: Infinity,
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 p-8 text-center">
        <div className="w-8 h-8 rounded-full border-2 border-[#5b76fe] border-t-transparent animate-spin" />
        <div>
          <p className="text-sm font-medium text-[#1c1c1e]">Computing distributions…</p>
          <p className="text-xs text-[#a5a8b5] mt-1">
            Scanning 1,180 patient records — this takes ~60 s on first load
          </p>
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-sm text-[#600000]">Failed to load observation distributions.</div>
      </div>
    );
  }

  return (
    <DistributionsContent
      distributions={data.distributions}
      totalFound={data.total_loinc_codes_found}
      codesShown={data.loinc_codes_shown}
    />
  );
}
