import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Syringe } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { ImmunizationItem } from "../../types";

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatMonthYear(dt: string | null): string {
  if (!dt) return "Unknown date";
  const d = new Date(dt);
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function getYear(dt: string | null): string {
  if (!dt) return "Unknown";
  return String(new Date(dt).getFullYear());
}

function statusBadge(status: string) {
  const s = status.toLowerCase();
  if (s === "completed") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200">
        completed
      </span>
    );
  }
  if (s === "not-done") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
        not-done
      </span>
    );
  }
  if (s === "entered-in-error") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200">
        entered-in-error
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[#f5f6f8] text-[#555a6a] border border-[#e9eaef]">
      {status || "unknown"}
    </span>
  );
}

// ── Year divider ─────────────────────────────────────────────────────────────

function YearDivider({ year, count }: { year: string; count: number }) {
  return (
    <div className="flex items-center gap-3 py-2 px-1">
      <span className="text-sm font-semibold" style={{ color: "#a5a8b5" }}>
        {year}
      </span>
      <div className="flex-1 border-t" style={{ borderColor: "#e9eaef" }} />
      <span className="text-xs" style={{ color: "#a5a8b5" }}>
        {count} {count === 1 ? "vaccine" : "vaccines"}
      </span>
    </div>
  );
}

// ── Immunization row ─────────────────────────────────────────────────────────

function ImmunizationRow({ imm }: { imm: ImmunizationItem }) {
  return (
    <div className="flex items-start gap-4 py-3 px-4 bg-white rounded-xl border border-[#e9eaef] hover:border-[#c7cad5] transition-colors">
      {/* Date column */}
      <div className="w-24 shrink-0 text-sm font-semibold text-[#1c1c1e] pt-0.5">
        {formatMonthYear(imm.occurrence_dt)}
      </div>

      {/* Vaccine name */}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-[#1c1c1e] leading-snug">{imm.display || "Unknown vaccine"}</p>
      </div>

      {/* CVX badge */}
      {imm.cvx_code && (
        <div className="shrink-0">
          <span className="inline-block font-mono text-xs px-2 py-0.5 rounded bg-[#f5f6f8] text-[#a5a8b5] border border-[#e9eaef]">
            CVX {imm.cvx_code}
          </span>
        </div>
      )}

      {/* Status badge */}
      <div className="shrink-0">{statusBadge(imm.status)}</div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function ExplorerImmunizations() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["immunizations", patientId],
    queryFn: () => api.getImmunizations(patientId!),
    enabled: !!patientId,
  });

  // No patient selected
  if (!patientId) {
    return (
      <div className="h-full flex items-center justify-center">
        <EmptyState
          icon={Syringe}
          title="Select a patient to view immunizations"
          bullets={[
            "Full vaccination history with dates",
            "CVX codes and status badges",
            "Grouped by year",
          ]}
        />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-8 space-y-3 max-w-3xl mx-auto">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-14 bg-white rounded-xl border border-[#e9eaef] animate-pulse" />
        ))}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="h-full flex items-center justify-center">
        <EmptyState
          icon={Syringe}
          title="Failed to load immunization data"
          iconBg="#fff0f0"
          iconColor="#e53e3e"
        />
      </div>
    );
  }

  // No records
  if (data.total_count === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <EmptyState
          icon={Syringe}
          title="No immunization records found"
          stat={`${data.name}`}
          iconBg="#f5f6f8"
          iconColor="#a5a8b5"
        />
      </div>
    );
  }

  // Vaccine summary chips — max 20, then "+ N more"
  const MAX_CHIPS = 20;
  const visibleVaccines = data.unique_vaccines.slice(0, MAX_CHIPS);
  const hiddenCount = data.unique_vaccines.length - visibleVaccines.length;

  // Group immunizations by year
  const groups: Map<string, ImmunizationItem[]> = new Map();
  for (const imm of data.immunizations) {
    const year = getYear(imm.occurrence_dt);
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year)!.push(imm);
  }

  // Sort years descending; "Unknown" goes last
  const sortedYears = Array.from(groups.keys()).sort((a, b) => {
    if (a === "Unknown") return 1;
    if (b === "Unknown") return -1;
    return Number(b) - Number(a);
  });

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[#1c1c1e]">
          {data.name} — Immunization History
        </h1>
        <p className="text-sm text-[#a5a8b5] mt-1">
          {data.total_count} {data.total_count === 1 ? "vaccine" : "vaccines"} recorded
        </p>
      </div>

      {/* Vaccine summary chips */}
      {visibleVaccines.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          {visibleVaccines.map((name) => (
            <span
              key={name}
              className="inline-block px-3 py-1 rounded-full text-xs text-[#555a6a] bg-[#f5f6f8] border border-[#e9eaef]"
            >
              {name}
            </span>
          ))}
          {hiddenCount > 0 && (
            <span className="inline-block px-3 py-1 rounded-full text-xs text-[#a5a8b5] bg-[#f5f6f8] border border-[#e9eaef]">
              +{hiddenCount} more
            </span>
          )}
        </div>
      )}

      {/* Timeline grouped by year */}
      <div className="space-y-1">
        {sortedYears.map((year) => {
          const imms = groups.get(year)!;
          return (
            <div key={year}>
              <YearDivider year={year} count={imms.length} />
              <div className="space-y-2 mt-1 mb-3">
                {imms.map((imm) => (
                  <ImmunizationRow key={imm.imm_id} imm={imm} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
