import { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ShieldAlert,
  AlertOctagon,
  AlertTriangle,
  Info,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Zap,
} from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { SafetyFlag } from "../../types";

// ── helpers ────────────────────────────────────────────────────────────────

function fmt(dt: string | null): string {
  if (!dt) return "—";
  return new Date(dt).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// ── Severity config ────────────────────────────────────────────────────────

const SEVERITY_CONFIG = {
  critical: {
    borderColor: "#ef4444",
    icon: AlertOctagon,
    iconColor: "#ef4444",
    badgeBg: "#fef2f2",
    badgeColor: "#991b1b",
  },
  warning: {
    borderColor: "#f59e0b",
    icon: AlertTriangle,
    iconColor: "#f59e0b",
    badgeBg: "#fffbeb",
    badgeColor: "#92400e",
  },
  info: {
    borderColor: "#5b76fe",
    icon: Info,
    iconColor: "#5b76fe",
    badgeBg: "#eef1ff",
    badgeColor: "#3730a3",
  },
} as const;

// ── FlagCard ───────────────────────────────────────────────────────────────

function FlagCard({ flag }: { flag: SafetyFlag }) {
  const [expanded, setExpanded] = useState(false);
  const [protocolOpen, setProtocolOpen] = useState(false);
  const config = SEVERITY_CONFIG[flag.severity] ?? SEVERITY_CONFIG.info;
  const SeverityIcon = config.icon;

  const statusBg = flag.status === "ACTIVE" ? "#fef2f2" : "#f5f6f8";
  const statusColor = flag.status === "ACTIVE" ? "#991b1b" : "#555a6a";
  const statusLabel = flag.status === "ACTIVE" ? "ACTIVE" : "HISTORICAL";

  return (
    <div
      className="bg-white rounded-xl border border-[#e9eaef] overflow-hidden"
      style={{ borderLeftWidth: 4, borderLeftColor: config.borderColor }}
    >
      {/* Header */}
      <div className="px-5 py-4">
        <div className="flex items-start gap-3">
          <SeverityIcon
            size={18}
            className="mt-0.5 shrink-0"
            style={{ color: config.iconColor }}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-[#1c1c1e] text-sm">
                {flag.label}
              </span>
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded-full"
                style={{ backgroundColor: statusBg, color: statusColor }}
              >
                {statusLabel}
              </span>
            </div>
            <p className="mt-1 text-sm text-[#555a6a] leading-snug">
              {flag.surgical_note}
            </p>
          </div>

          {/* Toggle */}
          {flag.medications.length > 0 && (
            <button
              onClick={() => setExpanded((e) => !e)}
              className="shrink-0 flex items-center gap-1 text-xs text-[#5b76fe] hover:text-[#3b56de] font-medium transition-colors"
            >
              {expanded ? (
                <>
                  Hide <ChevronUp size={13} />
                </>
              ) : (
                <>
                  {flag.medications.length} med
                  {flag.medications.length !== 1 ? "s" : ""}
                  <ChevronDown size={13} />
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Medication list */}
      {expanded && flag.medications.length > 0 && (
        <div className="border-t border-[#e9eaef] divide-y divide-[#e9eaef]">
          {flag.medications.map((med) => (
            <div
              key={med.med_id}
              className="flex items-center justify-between px-5 py-3 bg-[#fafafa]"
            >
              <div>
                <p className="text-sm font-medium text-[#1c1c1e]">
                  {med.display}
                </p>
                <p className="text-xs text-[#a5a8b5] mt-0.5">
                  {fmt(med.authored_on)}
                </p>
              </div>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  med.is_active
                    ? "bg-[#fef2f2] text-[#991b1b]"
                    : "bg-[#f5f6f8] text-[#555a6a]"
                }`}
              >
                {med.status}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Protocol note */}
      {flag.protocol_note && flag.status !== "NONE" && (
        <div className="border-t border-[#e9eaef]">
          <button
            onClick={() => setProtocolOpen((o) => !o)}
            className="w-full flex items-center justify-between px-5 py-2.5 hover:bg-[#fafafa] transition-colors"
          >
            <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold text-[#a5a8b5]">
              <BookOpen size={12} />
              Pre-Op Protocol
            </span>
            {protocolOpen ? (
              <ChevronUp size={13} className="text-[#a5a8b5]" />
            ) : (
              <ChevronDown size={13} className="text-[#a5a8b5]" />
            )}
          </button>
          {protocolOpen && (
            <div className="px-5 pb-4">
              <p className="bg-[#f5f6f8] rounded-lg p-3 text-sm text-[#555a6a] leading-relaxed">
                {flag.protocol_note}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export function ExplorerSafety() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["safety", patientId],
    queryFn: () => api.getSafety(patientId!),
    enabled: !!patientId,
  });

  const { data: interactionData } = useQuery({
    queryKey: ["interactions", patientId],
    queryFn: () => api.getInteractions(patientId!),
    enabled: !!patientId,
  });

  // ── Empty state ────────────────────────────────────────────────────────
  if (!patientId) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="No patient selected"
        bullets={[
          "Select a patient from the sidebar",
          "Safety flags highlight surgical risk medications",
          "Covers anticoagulants, immunosuppressants, and more",
        ]}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="p-8 space-y-4 max-w-3xl mx-auto">
        <div className="h-8 w-64 bg-[#e9eaef] rounded animate-pulse" />
        <div className="h-24 bg-[#e9eaef] rounded-xl animate-pulse" />
        <div className="h-24 bg-[#e9eaef] rounded-xl animate-pulse" />
        <div className="h-24 bg-[#e9eaef] rounded-xl animate-pulse" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load safety data.</p>
      </div>
    );
  }

  const visibleFlags = data.flags.filter((f) => f.status !== "NONE");
  const allClear = visibleFlags.length === 0;

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      {/* Drug-drug interaction alert banner */}
      {interactionData?.has_interactions && (
        <div className="flex items-center justify-between gap-3 px-4 py-3 rounded-xl border bg-[#fffbeb] border-[#fcd34d]">
          <div className="flex items-center gap-2">
            <Zap size={16} className="text-[#d97706] shrink-0" />
            <span className="text-sm font-semibold text-[#92400e]">
              {interactionData.contraindicated_count + interactionData.major_count + interactionData.moderate_count} drug interaction
              {interactionData.contraindicated_count + interactionData.major_count + interactionData.moderate_count !== 1 ? "s" : ""} detected
              {interactionData.contraindicated_count > 0 && (
                <span className="ml-1 text-[#991b1b]">
                  ({interactionData.contraindicated_count} contraindicated)
                </span>
              )}
            </span>
          </div>
          <Link
            to={`/explorer/interactions${patientId ? `?patient=${patientId}` : ""}`}
            className="shrink-0 text-xs font-semibold text-[#5b76fe] hover:text-[#3b56de] transition-colors whitespace-nowrap"
          >
            View Interactions →
          </Link>
        </div>
      )}

      {/* Summary bar */}
      <div>
        <h1 className="text-xl font-semibold text-[#1c1c1e] mb-3">
          {data.name} — Pre-Op Safety Review
        </h1>
        <div className="flex flex-wrap gap-2">
          {data.active_flag_count > 0 && (
            <span className="inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full bg-[#fef2f2] text-[#991b1b]">
              <AlertOctagon size={14} />
              {data.active_flag_count} ACTIVE flag
              {data.active_flag_count !== 1 ? "s" : ""}
            </span>
          )}
          {data.historical_flag_count > 0 && (
            <span className="inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full bg-[#fffbeb] text-[#92400e]">
              <AlertTriangle size={14} />
              {data.historical_flag_count} HISTORICAL flag
              {data.historical_flag_count !== 1 ? "s" : ""}
            </span>
          )}
          {allClear && (
            <span className="inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full bg-[#ecfdf5] text-[#065f46]">
              <CheckCircle size={14} />
              No surgical risk medications
            </span>
          )}
        </div>
      </div>

      {/* All-clear card */}
      {allClear && (
        <div className="bg-white rounded-xl border border-[#e9eaef] px-5 py-6 flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-[#ecfdf5] flex items-center justify-center shrink-0">
            <CheckCircle size={20} className="text-[#10b981]" />
          </div>
          <div>
            <p className="font-semibold text-[#1c1c1e]">
              No surgical risk medications detected
            </p>
            <p className="text-sm text-[#555a6a] mt-0.5">
              None of this patient's medications match known surgical risk drug
              classes.
            </p>
          </div>
        </div>
      )}

      {/* Flag cards */}
      {visibleFlags.length > 0 && (
        <div className="space-y-3">
          {visibleFlags.map((flag) => (
            <FlagCard key={flag.class_key} flag={flag} />
          ))}
        </div>
      )}
    </div>
  );
}
