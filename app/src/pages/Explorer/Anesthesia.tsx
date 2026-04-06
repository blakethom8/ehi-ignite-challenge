import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Stethoscope, CheckCircle, AlertTriangle, AlertOctagon } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { SafetyFlag, RankedConditionItem } from "../../types";

// ── Drug class sets ────────────────────────────────────────────────────────────

const ANTICOAG_ANTIPLATELET = new Set(["anticoagulants", "antiplatelets"]);
const OPIOID_CORTICOSTEROID = new Set(["opioids"]);
// corticosteroids are not in the classifier but we handle gracefully

// ── ASA Risk derivation ────────────────────────────────────────────────────────

type AsaLevel = "I" | "II" | "III" | "IV";

interface AsaResult {
  level: AsaLevel;
  rationale: string;
}

function deriveAsa(
  activeConditions: RankedConditionItem[],
  activeFlags: SafetyFlag[]
): AsaResult {
  const hasCardiac = activeConditions.some((c) => c.risk_category === "CARDIAC");
  const hasPulmonary = activeConditions.some((c) => c.risk_category === "PULMONARY");
  const hasCriticalMed = activeFlags.some(
    (f) => f.status === "ACTIVE" && ANTICOAG_ANTIPLATELET.has(f.class_key)
  );
  const totalActiveConditions = activeConditions.length;

  // ASA IV: both cardiac + active anticoagulant/antiplatelet, or severe pulmonary + anticoag
  if ((hasCardiac && hasCriticalMed) || (hasPulmonary && hasCriticalMed)) {
    return {
      level: "IV",
      rationale:
        "Life-threatening disease: active cardiac or pulmonary condition combined with anticoagulant/antiplatelet therapy.",
    };
  }

  // ASA III: cardiac or pulmonary condition, OR any active critical-class medication
  if (hasCardiac || hasPulmonary || hasCriticalMed) {
    return {
      level: "III",
      rationale:
        "Severe systemic disease: active cardiac or pulmonary condition, or high-risk medication class in use.",
    };
  }

  // ASA II: 1–2 non-critical conditions, no critical meds
  if (totalActiveConditions > 0 && totalActiveConditions <= 4) {
    return {
      level: "II",
      rationale:
        "Mild systemic disease: active conditions without cardiac or pulmonary involvement.",
    };
  }

  if (totalActiveConditions > 4) {
    return {
      level: "III",
      rationale:
        "Severe systemic disease: multiple active conditions indicating complex medical history.",
    };
  }

  return {
    level: "I",
    rationale: "Normal healthy patient: no active conditions and no high-risk medications.",
  };
}

// ── ASA badge ─────────────────────────────────────────────────────────────────

function AsaBadge({ level, rationale }: AsaResult) {
  const config = {
    I: { bg: "#f0fdf4", border: "#22c55e", text: "#166534", accent: "#22c55e" },
    II: { bg: "#fffbeb", border: "#f59e0b", text: "#92400e", accent: "#f59e0b" },
    III: { bg: "#fff7ed", border: "#f97316", text: "#9a3412", accent: "#f97316" },
    IV: { bg: "#fef2f2", border: "#ef4444", text: "#991b1b", accent: "#ef4444" },
  }[level];

  return (
    <div
      className="rounded-2xl border px-6 py-5 flex items-start gap-5"
      style={{ backgroundColor: config.bg, borderColor: config.border }}
    >
      <div
        className="w-14 h-14 rounded-xl flex items-center justify-center shrink-0 font-bold text-2xl"
        style={{ backgroundColor: config.accent + "22", color: config.accent }}
      >
        {level}
      </div>
      <div>
        <p className="font-semibold text-sm mb-0.5" style={{ color: config.text }}>
          ASA Physical Status Class {level}
        </p>
        <p className="text-sm" style={{ color: config.text, opacity: 0.8 }}>
          {rationale}
        </p>
      </div>
    </div>
  );
}

// ── Section panel ──────────────────────────────────────────────────────────────

interface PanelProps {
  title: string;
  variant: "red" | "amber" | "green" | "neutral";
  items: string[];
  emptyNote: string;
}

function Panel({ title, variant, items, emptyNote }: PanelProps) {
  const config = {
    red: {
      bg: "#fef2f2",
      border: "#ef4444",
      titleColor: "#991b1b",
      itemColor: "#7f1d1d",
      dot: "#ef4444",
      Icon: AlertOctagon,
    },
    amber: {
      bg: "#fffbeb",
      border: "#f59e0b",
      titleColor: "#92400e",
      itemColor: "#78350f",
      dot: "#f59e0b",
      Icon: AlertTriangle,
    },
    green: {
      bg: "#f0fdf4",
      border: "#22c55e",
      titleColor: "#166534",
      itemColor: "#14532d",
      dot: "#22c55e",
      Icon: CheckCircle,
    },
    neutral: {
      bg: "#f5f6f8",
      border: "#e9eaef",
      titleColor: "#555a6a",
      itemColor: "#1c1c1e",
      dot: "#a5a8b5",
      Icon: CheckCircle,
    },
  }[variant];

  const isEmpty = items.length === 0;

  return (
    <div
      className="rounded-2xl border overflow-hidden"
      style={{
        backgroundColor: isEmpty ? "#ffffff" : config.bg,
        borderColor: isEmpty ? "#e9eaef" : config.border,
        borderLeftWidth: isEmpty ? 1 : 4,
        borderLeftColor: isEmpty ? "#e9eaef" : config.border,
      }}
    >
      <div className="px-5 py-4">
        <div className="flex items-center gap-2 mb-2">
          {!isEmpty && (
            <config.Icon size={15} style={{ color: config.titleColor }} className="shrink-0" />
          )}
          <span
            className="text-sm font-semibold"
            style={{ color: isEmpty ? "#555a6a" : config.titleColor }}
          >
            {title}
          </span>
        </div>

        {isEmpty ? (
          <p className="text-sm text-[#a5a8b5]">{emptyNote}</p>
        ) : (
          <ul className="space-y-1.5">
            {items.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <span
                  className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0"
                  style={{ backgroundColor: config.dot }}
                />
                <span style={{ color: config.itemColor }}>{item}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtAge(birthDate: string | null, ageYears: number): string {
  if (ageYears) return `${ageYears} yo`;
  if (!birthDate) return "Age unknown";
  const age = new Date().getFullYear() - new Date(birthDate).getFullYear();
  return `${age} yo`;
}

function fmtDob(birthDate: string | null): string {
  if (!birthDate) return "—";
  return new Date(birthDate).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

// ── Main page ──────────────────────────────────────────────────────────────────

export function ExplorerAnesthesia() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const safetyQ = useQuery({
    queryKey: ["safety", patientId],
    queryFn: () => api.getSafety(patientId!),
    enabled: !!patientId,
  });

  const conditionsQ = useQuery({
    queryKey: ["conditionAcuity", patientId],
    queryFn: () => api.getConditionAcuity(patientId!),
    enabled: !!patientId,
  });

  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });

  if (!patientId) {
    return (
      <EmptyState
        icon={Stethoscope}
        title="No patient selected"
        bullets={[
          "Select a patient from the sidebar",
          "Anesthesia card summarizes risk factors for handoff",
          "Includes ASA risk level, airway notes, and drug considerations",
        ]}
        iconBg="#fffbeb"
        iconColor="#f59e0b"
      />
    );
  }

  const isLoading = safetyQ.isLoading || conditionsQ.isLoading || overviewQ.isLoading;
  const isError = safetyQ.isError || conditionsQ.isError || overviewQ.isError;

  if (isLoading) {
    return (
      <div className="p-8 space-y-4 max-w-2xl mx-auto">
        <div className="h-20 bg-[#e9eaef] rounded-2xl animate-pulse" />
        <div className="h-16 bg-[#e9eaef] rounded-2xl animate-pulse" />
        <div className="h-28 bg-[#e9eaef] rounded-2xl animate-pulse" />
        <div className="h-28 bg-[#e9eaef] rounded-2xl animate-pulse" />
        <div className="h-14 bg-[#e9eaef] rounded-2xl animate-pulse" />
      </div>
    );
  }

  if (isError || !safetyQ.data || !conditionsQ.data || !overviewQ.data) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load anesthesia data.</p>
      </div>
    );
  }

  const safety = safetyQ.data;
  const conditions = conditionsQ.data;
  const overview = overviewQ.data;

  const activeFlags = safety.flags.filter((f) => f.status === "ACTIVE");
  const activeConditions = conditions.ranked_active;

  // Anesthesia risk conditions: OSA, COPD, cardiac, obesity, diabetes-adjacent
  const ANESTHESIA_RISK_CATEGORIES = new Set(["CARDIAC", "PULMONARY", "METABOLIC"]);
  const riskConditions = activeConditions
    .filter((c) => ANESTHESIA_RISK_CATEGORIES.has(c.risk_category))
    .map((c) => `${c.display} (${c.risk_category.charAt(0) + c.risk_category.slice(1).toLowerCase()})`);

  // Active drug considerations
  const anticoagItems = activeFlags
    .filter((f) => ANTICOAG_ANTIPLATELET.has(f.class_key))
    .flatMap((f) =>
      f.medications
        .filter((m) => m.is_active)
        .map((m) => `${m.display} — ${f.label}`)
    );

  const opioidCorticosteroidItems = activeFlags
    .filter((f) => OPIOID_CORTICOSTEROID.has(f.class_key))
    .flatMap((f) =>
      f.medications
        .filter((m) => m.is_active)
        .map((m) => `${m.display} — ${f.label}`)
    );

  // Airway note: flag if any pulmonary condition
  const hasPulmonary = activeConditions.some((c) => c.risk_category === "PULMONARY");
  const pulmonaryConditions = activeConditions
    .filter((c) => c.risk_category === "PULMONARY")
    .map((c) => c.display);

  // ASA derivation
  const asa = deriveAsa(activeConditions, activeFlags);

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-5">
      {/* Patient header */}
      <div className="bg-white rounded-2xl shadow-sm border border-[#e9eaef] px-6 py-5">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold text-[#1c1c1e]">{overview.name}</h1>
            <p className="text-sm text-[#555a6a] mt-0.5">
              {fmtAge(overview.birth_date, overview.age_years)} ·{" "}
              {overview.gender.charAt(0).toUpperCase() + overview.gender.slice(1)} · DOB{" "}
              {fmtDob(overview.birth_date)}
            </p>
          </div>
          <div className="text-right shrink-0">
            <p className="text-xs text-[#a5a8b5] uppercase tracking-wider font-semibold">
              Anesthesia Handoff Card
            </p>
            <p className="text-xs text-[#a5a8b5] mt-0.5">
              {new Date().toLocaleDateString("en-US", {
                year: "numeric",
                month: "short",
                day: "numeric",
              })}
            </p>
          </div>
        </div>
      </div>

      {/* ASA risk level */}
      <AsaBadge level={asa.level} rationale={asa.rationale} />

      {/* Anesthesia risk factors */}
      <Panel
        title="Anesthesia Risk Factors"
        variant="amber"
        items={riskConditions}
        emptyNote="No high-priority anesthesia risk conditions identified."
      />

      {/* Active drug considerations — anticoag/antiplatelet (red) */}
      <Panel
        title="Anticoagulant / Antiplatelet Medications"
        variant="red"
        items={anticoagItems}
        emptyNote="No active anticoagulant or antiplatelet medications on record."
      />

      {/* Active drug considerations — opioids/corticosteroids (amber) */}
      <Panel
        title="Opioid / Corticosteroid Medications"
        variant="amber"
        items={opioidCorticosteroidItems}
        emptyNote="No active opioid or corticosteroid medications on record."
      />

      {/* Airway notes */}
      <div className="bg-white rounded-2xl shadow-sm border border-[#e9eaef] px-6 py-5">
        <p className="text-sm font-semibold text-[#555a6a] uppercase tracking-wider mb-2">
          Airway Notes
        </p>
        {hasPulmonary ? (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle size={14} className="text-[#f59e0b] shrink-0" />
              <span className="text-sm font-medium text-[#92400e]">
                Pulmonary condition(s) may affect airway management
              </span>
            </div>
            <ul className="space-y-1 ml-5">
              {pulmonaryConditions.map((c, i) => (
                <li key={i} className="text-sm text-[#78350f] flex items-start gap-2">
                  <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-[#f59e0b] shrink-0" />
                  {c}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-[#a5a8b5]">No documented airway alerts.</p>
        )}
      </div>
    </div>
  );
}
