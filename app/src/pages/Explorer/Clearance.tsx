import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck, CheckCircle, AlertOctagon, AlertTriangle } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { SafetyFlag, LabValue } from "../../types";

// ── Domain status types ────────────────────────────────────────────────────────

type DomainStatus = "CLEARED" | "FLAGGED" | "REVIEW";

interface DomainResult {
  status: DomainStatus;
  items: string[];
}

// ── Drug class sets ────────────────────────────────────────────────────────────

const CRITICAL_MED_CLASSES = new Set([
  "anticoagulants",
  "antiplatelets",
  "jak_inhibitors",
  "immunosuppressants",
]);

const WARNING_MED_CLASSES = new Set([
  "ace_inhibitors",
  "arbs",
  "nsaids",
  "opioids",
  "anticonvulsants",
]);

// ── Domain logic ───────────────────────────────────────────────────────────────

function computeMedDomain(flags: SafetyFlag[]): DomainResult {
  const activeFlags = flags.filter((f) => f.status === "ACTIVE");
  const criticalActive = activeFlags.filter((f) => CRITICAL_MED_CLASSES.has(f.class_key));
  const warningActive = activeFlags.filter(
    (f) => WARNING_MED_CLASSES.has(f.class_key) && !CRITICAL_MED_CLASSES.has(f.class_key)
  );

  if (criticalActive.length > 0) {
    return {
      status: "FLAGGED",
      items: criticalActive.map((f) => `${f.label} — ${f.surgical_note}`),
    };
  }
  if (warningActive.length > 0) {
    return {
      status: "REVIEW",
      items: warningActive.map((f) => `${f.label} — ${f.surgical_note}`),
    };
  }
  return { status: "CLEARED", items: [] };
}

interface ConditionAcuityMini {
  ranked_active: { display: string; risk_category: string }[];
}

function computeConditionDomain(data: ConditionAcuityMini): DomainResult {
  const active = data.ranked_active;
  const cardiac = active.filter((c) => c.risk_category === "CARDIAC");
  const pulmonary = active.filter((c) => c.risk_category === "PULMONARY");
  const metabolic = active.filter((c) => c.risk_category === "METABOLIC");

  if (cardiac.length > 0 || pulmonary.length > 0) {
    const flagged = [...cardiac, ...pulmonary];
    return {
      status: "FLAGGED",
      items: flagged.map((c) => c.display),
    };
  }
  if (metabolic.length > 0) {
    return {
      status: "REVIEW",
      items: metabolic.map((c) => c.display),
    };
  }
  return { status: "CLEARED", items: [] };
}

function computeLabDomain(panels: Record<string, LabValue[]>): DomainResult {
  const emptyPanels = Object.entries(panels)
    .filter(([, values]) => values.length === 0)
    .map(([name]) => name);

  if (emptyPanels.length > 0) {
    return {
      status: "REVIEW",
      items: emptyPanels.map((p) => `${p} — no data available`),
    };
  }
  return { status: "CLEARED", items: [] };
}

// ── Overall status ─────────────────────────────────────────────────────────────

function overallStatus(statuses: DomainStatus[]): DomainStatus {
  if (statuses.includes("FLAGGED")) return "FLAGGED";
  if (statuses.includes("REVIEW")) return "REVIEW";
  return "CLEARED";
}

// ── Status chip ────────────────────────────────────────────────────────────────

function StatusChip({ status }: { status: DomainStatus }) {
  const config = {
    CLEARED: {
      bg: "#f0fdf4",
      text: "#166534",
      border: "#22c55e",
      label: "CLEARED",
      Icon: CheckCircle,
    },
    FLAGGED: {
      bg: "#fef2f2",
      text: "#991b1b",
      border: "#ef4444",
      label: "FLAGGED",
      Icon: AlertOctagon,
    },
    REVIEW: {
      bg: "#fffbeb",
      text: "#92400e",
      border: "#f59e0b",
      label: "REVIEW",
      Icon: AlertTriangle,
    },
  }[status];

  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border"
      style={{ backgroundColor: config.bg, color: config.text, borderColor: config.border }}
    >
      <config.Icon size={12} />
      {config.label}
    </span>
  );
}

// ── Domain card ────────────────────────────────────────────────────────────────

function DomainCard({
  title,
  result,
  clearedNote,
}: {
  title: string;
  result: DomainResult;
  clearedNote: string;
}) {
  const borderColor =
    result.status === "FLAGGED"
      ? "#ef4444"
      : result.status === "REVIEW"
      ? "#f59e0b"
      : "#22c55e";

  return (
    <div
      className="bg-white rounded-2xl shadow-sm border border-[#e9eaef] overflow-hidden"
      style={{ borderLeftWidth: 4, borderLeftColor: borderColor }}
    >
      <div className="px-6 py-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-[#1c1c1e]">{title}</h2>
          <StatusChip status={result.status} />
        </div>

        {result.status === "CLEARED" ? (
          <p className="text-sm text-[#555a6a]">{clearedNote}</p>
        ) : (
          <ul className="space-y-1.5 mt-1">
            {result.items.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-[#1c1c1e]">
                <span
                  className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0"
                  style={{
                    backgroundColor: result.status === "FLAGGED" ? "#ef4444" : "#f59e0b",
                  }}
                />
                {item}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── Overall status bar ─────────────────────────────────────────────────────────

function OverallBar({ status, name }: { status: DomainStatus; name: string }) {
  const config = {
    CLEARED: {
      bg: "#f0fdf4",
      border: "#22c55e",
      text: "#166534",
      message: "Pre-Op Clearance: Complete",
      Icon: CheckCircle,
    },
    FLAGGED: {
      bg: "#fef2f2",
      border: "#ef4444",
      text: "#991b1b",
      message: "Pre-Op Clearance: Hold — Review Required",
      Icon: AlertOctagon,
    },
    REVIEW: {
      bg: "#fffbeb",
      border: "#f59e0b",
      text: "#92400e",
      message: "Pre-Op Clearance: Incomplete — Pending Review",
      Icon: AlertTriangle,
    },
  }[status];

  return (
    <div
      className="rounded-2xl border px-6 py-4 flex items-center gap-4"
      style={{ backgroundColor: config.bg, borderColor: config.border }}
    >
      <config.Icon size={22} style={{ color: config.text }} className="shrink-0" />
      <div>
        <p className="font-semibold text-sm" style={{ color: config.text }}>
          {config.message}
        </p>
        <p className="text-xs mt-0.5" style={{ color: config.text, opacity: 0.75 }}>
          {name}
        </p>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export function ExplorerClearance() {
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

  const labsQ = useQuery({
    queryKey: ["keyLabs", patientId],
    queryFn: () => api.getKeyLabs(patientId!),
    enabled: !!patientId,
  });

  if (!patientId) {
    return (
      <EmptyState
        icon={ClipboardCheck}
        title="No patient selected"
        bullets={[
          "Select a patient from the sidebar",
          "Clearance checklist evaluates medications, conditions, and labs",
          "Flags surgical holds and items needing review",
        ]}
      />
    );
  }

  const isLoading = safetyQ.isLoading || conditionsQ.isLoading || labsQ.isLoading;
  const isError = safetyQ.isError || conditionsQ.isError || labsQ.isError;

  if (isLoading) {
    return (
      <div className="p-8 space-y-4 max-w-3xl mx-auto">
        <div className="h-14 bg-[#e9eaef] rounded-2xl animate-pulse" />
        <div className="h-32 bg-[#e9eaef] rounded-2xl animate-pulse" />
        <div className="h-32 bg-[#e9eaef] rounded-2xl animate-pulse" />
        <div className="h-32 bg-[#e9eaef] rounded-2xl animate-pulse" />
      </div>
    );
  }

  if (isError || !safetyQ.data || !conditionsQ.data || !labsQ.data) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load clearance data.</p>
      </div>
    );
  }

  const medDomain = computeMedDomain(safetyQ.data.flags);
  const conditionDomain = computeConditionDomain(conditionsQ.data);
  const labDomain = computeLabDomain(labsQ.data.panels);

  const overall = overallStatus([medDomain.status, conditionDomain.status, labDomain.status]);
  const patientName = safetyQ.data.name;

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-[#1c1c1e] mb-1">
          {patientName} — Pre-Op Clearance Checklist
        </h1>
        <p className="text-sm text-[#a5a8b5]">
          Domain-by-domain surgical readiness assessment
        </p>
      </div>

      {/* Overall status bar */}
      <OverallBar status={overall} name={patientName} />

      {/* Domain cards */}
      <DomainCard
        title="Medications"
        result={medDomain}
        clearedNote="No active critical or warning-class medications detected. Proceed without medication hold."
      />
      <DomainCard
        title="Conditions"
        result={conditionDomain}
        clearedNote="No active cardiac, pulmonary, or metabolic conditions identified."
      />
      <DomainCard
        title="Labs"
        result={labDomain}
        clearedNote="All key lab panels have data on file."
      />
    </div>
  );
}
