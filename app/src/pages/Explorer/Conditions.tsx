import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle, ChevronDown, ChevronRight, Activity } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { RankedConditionItem } from "../../types";

// ── Category color map ────────────────────────────────────────────────────────

interface CategoryStyle {
  bg: string;
  text: string;
  border: string;
  dot: string;
}

const CATEGORY_STYLES: Record<string, CategoryStyle> = {
  CARDIAC:     { bg: "#fef2f2",  text: "#991b1b",  border: "#ef4444",  dot: "#ef4444"  },
  PULMONARY:   { bg: "#fffbeb",  text: "#92400e",  border: "#f59e0b",  dot: "#f59e0b"  },
  METABOLIC:   { bg: "#fff7ed",  text: "#9a3412",  border: "#f97316",  dot: "#f97316"  },
  RENAL:       { bg: "#f0f9ff",  text: "#075985",  border: "#0ea5e9",  dot: "#0ea5e9"  },
  HEPATIC:     { bg: "#faf5ff",  text: "#6b21a8",  border: "#a855f7",  dot: "#a855f7"  },
  HEMATOLOGIC: { bg: "#fff1f2",  text: "#9f1239",  border: "#f43f5e",  dot: "#f43f5e"  },
  NEUROLOGIC:  { bg: "#f0fdf4",  text: "#166534",  border: "#22c55e",  dot: "#22c55e"  },
  IMMUNOLOGIC: { bg: "#ecfdf5",  text: "#065f46",  border: "#10b981",  dot: "#10b981"  },
  ONCOLOGIC:   { bg: "#f3f3f3",  text: "#1c1c1e",  border: "#555a6a",  dot: "#555a6a"  },
  VASCULAR:    { bg: "#eef1ff",  text: "#3730a3",  border: "#6366f1",  dot: "#6366f1"  },
  OTHER:       { bg: "#f5f6f8",  text: "#555a6a",  border: "#c7cad5",  dot: "#c7cad5"  },
};

function getCategoryStyle(category: string): CategoryStyle {
  return CATEGORY_STYLES[category] ?? CATEGORY_STYLES.OTHER;
}

// ── Anesthesia spotlight categories ─────────────────────────────────────────

const ANESTHESIA_CATEGORIES = new Set(["PULMONARY", "CARDIAC", "METABOLIC"]);

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatOnset(dt: string | null): string {
  if (!dt) return "Unknown onset";
  const d = new Date(dt);
  if (isNaN(d.getTime())) return "Unknown onset";
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short" });
}

// Group conditions by risk_category, preserving order of first appearance
function groupByCategory(items: RankedConditionItem[]): Map<string, RankedConditionItem[]> {
  const map = new Map<string, RankedConditionItem[]>();
  for (const item of items) {
    const existing = map.get(item.risk_category);
    if (existing) {
      existing.push(item);
    } else {
      map.set(item.risk_category, [item]);
    }
  }
  return map;
}

// ── CategoryChip ─────────────────────────────────────────────────────────────

function CategoryChip({ category, label }: { category: string; label: string }) {
  const style = getCategoryStyle(category);
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border shrink-0"
      style={{ backgroundColor: style.bg, color: style.text, borderColor: style.border }}
    >
      {label}
    </span>
  );
}

// ── ConditionRow ─────────────────────────────────────────────────────────────

function ConditionRow({ item }: { item: RankedConditionItem }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-[#e9eaef] last:border-b-0">
      <CategoryChip category={item.risk_category} label={item.risk_label} />
      <span className="flex-1 text-sm text-[#1c1c1e] font-medium">{item.display}</span>
      <span className="text-xs text-[#a5a8b5] shrink-0">{formatOnset(item.onset_dt)}</span>
    </div>
  );
}

// ── CategorySection ───────────────────────────────────────────────────────────

function CategorySection({ category, items }: { category: string; items: RankedConditionItem[] }) {
  const style = getCategoryStyle(category);
  const label = items[0]?.risk_label ?? category;
  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 px-1 mb-1">
        <span
          className="w-2.5 h-2.5 rounded-full shrink-0"
          style={{ backgroundColor: style.dot }}
        />
        <span className="text-xs font-semibold text-[#555a6a] uppercase tracking-wider">
          {label}
        </span>
        <span className="text-xs text-[#a5a8b5]">({items.length})</span>
      </div>
      <div className="bg-white rounded-xl border border-[#e9eaef] overflow-hidden">
        {items.map((item) => (
          <ConditionRow key={item.condition_id} item={item} />
        ))}
      </div>
    </div>
  );
}

// ── AnesthesiaSpotlight ──────────────────────────────────────────────────────

function AnesthesiaSpotlight({ conditions }: { conditions: RankedConditionItem[] }) {
  const flagged = conditions.filter((c) => ANESTHESIA_CATEGORIES.has(c.risk_category));

  if (flagged.length === 0) {
    return (
      <div className="mb-6 px-4 py-3 bg-[#f0fdf4] border border-[#22c55e] rounded-xl flex items-center gap-3">
        <CheckCircle size={16} className="text-[#16a34a] shrink-0" />
        <span className="text-sm text-[#166534]">No high-priority anesthesia concerns identified</span>
      </div>
    );
  }

  return (
    <div className="mb-6 border-l-4 border-[#f59e0b] bg-[#fffbeb] rounded-r-xl overflow-hidden">
      <div className="px-4 pt-3 pb-2 flex items-center gap-2">
        <span className="text-sm font-semibold text-[#92400e]">⚠ Anesthesia Considerations</span>
        <span className="text-xs text-[#b45309]">{flagged.length} condition{flagged.length !== 1 ? "s" : ""}</span>
      </div>
      <div className="border-t border-[#fde68a]">
        {flagged.map((item) => (
          <div
            key={item.condition_id}
            className="flex items-center gap-3 px-4 py-2.5 border-b border-[#fde68a] last:border-b-0"
          >
            <CategoryChip category={item.risk_category} label={item.risk_label} />
            <span className="flex-1 text-sm text-[#92400e] font-medium">{item.display}</span>
            <span className="text-xs text-[#b45309] shrink-0">{formatOnset(item.onset_dt)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── ResolvedSection ───────────────────────────────────────────────────────────

function ResolvedSection({ items }: { items: RankedConditionItem[] }) {
  const [open, setOpen] = useState(false);
  const grouped = groupByCategory(items);

  return (
    <div className="mt-6">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 mb-3 text-sm font-medium text-[#555a6a] hover:text-[#1c1c1e] transition-colors"
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        Resolved Conditions
        <span className="text-xs text-[#a5a8b5] font-normal">({items.length})</span>
      </button>

      {open && (
        <div className="opacity-70">
          {Array.from(grouped.entries()).map(([category, condItems]) => (
            <div key={category} className="mb-3">
              <div className="flex items-center gap-2 px-1 mb-1">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: getCategoryStyle(category).dot }}
                />
                <span className="text-xs font-semibold text-[#a5a8b5] uppercase tracking-wider">
                  {condItems[0]?.risk_label ?? category}
                </span>
                <span className="text-xs text-[#c7cad5]">({condItems.length})</span>
              </div>
              <div className="bg-white rounded-xl border border-[#e9eaef] overflow-hidden">
                {condItems.map((item) => (
                  <div
                    key={item.condition_id}
                    className="flex items-center gap-3 px-4 py-2.5 border-b border-[#e9eaef] last:border-b-0"
                  >
                    <span className="flex-1 text-sm text-[#a5a8b5]">{item.display}</span>
                    <span className="text-xs text-[#c7cad5] shrink-0">{formatOnset(item.onset_dt)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function ExplorerConditions() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["conditionAcuity", patientId],
    queryFn: () => api.getConditionAcuity(patientId!),
    enabled: !!patientId,
  });

  // No patient selected
  if (!patientId) {
    return (
      <EmptyState
        icon={Activity}
        title="Select a patient"
        bullets={["Choose a patient from the sidebar to view their conditions"]}
        iconBg="#fffbeb"
        iconColor="#f59e0b"
      />
    );
  }

  if (isLoading) {
    return (
      <div className="p-8 space-y-4 max-w-3xl mx-auto">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 bg-white rounded-xl border border-[#e9eaef] animate-pulse" />
        ))}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <EmptyState
        icon={Activity}
        title="Could not load conditions"
        bullets={["Check that the API is running and the patient exists"]}
        iconBg="#fef2f2"
        iconColor="#ef4444"
      />
    );
  }

  const { name, active_count, resolved_count, ranked_active, ranked_resolved } = data;
  const grouped = groupByCategory(ranked_active);

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[#1c1c1e]">{name} — Conditions</h1>
        <p className="text-sm text-[#a5a8b5] mt-0.5">
          {active_count} active · {resolved_count} resolved
        </p>
      </div>

      {/* Anesthesia spotlight */}
      <AnesthesiaSpotlight conditions={ranked_active} />

      {/* Active conditions */}
      {ranked_active.length === 0 ? (
        <div className="flex items-center gap-3 px-4 py-4 bg-[#f0fdf4] border border-[#22c55e] rounded-xl mb-4">
          <CheckCircle size={18} className="text-[#16a34a] shrink-0" />
          <span className="text-sm font-medium text-[#166534]">No active conditions recorded</span>
        </div>
      ) : (
        <div>
          <p className="text-xs font-semibold text-[#a5a8b5] uppercase tracking-wider mb-3 px-1">
            Active Conditions
          </p>
          {Array.from(grouped.entries()).map(([category, items]) => (
            <CategorySection key={category} category={category} items={items} />
          ))}
        </div>
      )}

      {/* Resolved conditions */}
      {ranked_resolved.length > 0 && <ResolvedSection items={ranked_resolved} />}
    </div>
  );
}
