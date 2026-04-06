import { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Zap,
  AlertOctagon,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { InteractionResult } from "../../types";

// ── Severity config ────────────────────────────────────────────────────────

const SEVERITY_CONFIG = {
  contraindicated: {
    borderColor: "#ef4444",
    badgeBg: "#fef2f2",
    badgeColor: "#991b1b",
    badgeText: "CONTRAINDICATED",
    icon: AlertOctagon,
    iconColor: "#ef4444",
  },
  major: {
    borderColor: "#ef4444",
    badgeBg: "#fef2f2",
    badgeColor: "#991b1b",
    badgeText: "MAJOR",
    icon: AlertOctagon,
    iconColor: "#ef4444",
  },
  moderate: {
    borderColor: "#f59e0b",
    badgeBg: "#fffbeb",
    badgeColor: "#92400e",
    badgeText: "MODERATE",
    icon: AlertTriangle,
    iconColor: "#f59e0b",
  },
} as const;

// ── MedChip ────────────────────────────────────────────────────────────────

function MedChip({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#eef1ff] text-[#3730a3] border border-[#c7d0fe]">
      {name}
    </span>
  );
}

// ── ExpandableRow ──────────────────────────────────────────────────────────

function ExpandableRow({ label, content }: { label: string; content: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-t border-[#e9eaef]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-2.5 hover:bg-[#fafafa] transition-colors text-left"
      >
        <span className="text-[10px] uppercase tracking-wider font-semibold text-[#a5a8b5]">
          {label}
        </span>
        {open ? (
          <ChevronUp size={13} className="text-[#a5a8b5] shrink-0" />
        ) : (
          <ChevronDown size={13} className="text-[#a5a8b5] shrink-0" />
        )}
      </button>
      {open && (
        <div className="px-5 pb-4">
          <p className="bg-[#f5f6f8] rounded-lg p-3 text-sm text-[#555a6a] leading-relaxed">
            {content}
          </p>
        </div>
      )}
    </div>
  );
}

// ── InteractionCard ────────────────────────────────────────────────────────

function InteractionCard({ interaction }: { interaction: InteractionResult }) {
  const config = SEVERITY_CONFIG[interaction.severity] ?? SEVERITY_CONFIG.moderate;
  const SeverityIcon = config.icon;
  const allMeds = [...interaction.drug_a_meds, ...interaction.drug_b_meds];

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
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded-full"
                style={{ backgroundColor: config.badgeBg, color: config.badgeColor }}
              >
                {config.badgeText}
              </span>
            </div>
            <p className="font-semibold text-[#1c1c1e] text-sm">
              {interaction.drug_a_label}{" "}
              <span className="text-[#a5a8b5] font-normal">↔</span>{" "}
              {interaction.drug_b_label}
            </p>
          </div>
        </div>

        {/* Medication pills */}
        {allMeds.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {allMeds.map((med, i) => (
              <MedChip key={i} name={med} />
            ))}
          </div>
        )}
      </div>

      {/* Expandable detail rows */}
      <ExpandableRow label="Mechanism" content={interaction.mechanism} />
      <ExpandableRow label="Clinical Effect" content={interaction.clinical_effect} />
      <ExpandableRow label="Management" content={interaction.management} />
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export function ExplorerInteractions() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["interactions", patientId],
    queryFn: () => api.getInteractions(patientId!),
    enabled: !!patientId,
  });

  // ── Empty state ────────────────────────────────────────────────────────
  if (!patientId) {
    return (
      <EmptyState
        icon={Zap}
        title="No patient selected"
        bullets={[
          "Select a patient from the sidebar",
          "Checks for dangerous drug-drug interactions",
          "Covers anticoagulants, opioids, MAOIs, and more",
        ]}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="p-8 space-y-4 max-w-3xl mx-auto">
        <div className="h-8 w-64 bg-[#e9eaef] rounded animate-pulse" />
        <div className="h-20 bg-[#e9eaef] rounded-xl animate-pulse" />
        <div className="h-20 bg-[#e9eaef] rounded-xl animate-pulse" />
        <div className="h-20 bg-[#e9eaef] rounded-xl animate-pulse" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load interaction data.</p>
      </div>
    );
  }

  const { interactions, contraindicated_count, major_count, moderate_count, active_class_keys, has_interactions } = data;

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-semibold text-[#1c1c1e] mb-3">
          Drug-Drug Interaction Check
        </h1>

        {/* KPI strip */}
        {has_interactions ? (
          <div className="flex flex-wrap gap-2">
            {contraindicated_count > 0 && (
              <span className="inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full bg-[#fef2f2] text-[#991b1b]">
                <AlertOctagon size={14} />
                {contraindicated_count} Contraindicated
              </span>
            )}
            {major_count > 0 && (
              <span className="inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full bg-[#fef2f2] text-[#991b1b]">
                <AlertOctagon size={14} />
                {major_count} Major
              </span>
            )}
            {moderate_count > 0 && (
              <span className="inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full bg-[#fffbeb] text-[#92400e]">
                <AlertTriangle size={14} />
                {moderate_count} Moderate
              </span>
            )}
            <span className="inline-flex items-center text-sm text-[#555a6a] px-2 py-1.5">
              across {active_class_keys.length} active drug class
              {active_class_keys.length !== 1 ? "es" : ""}
            </span>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full bg-[#ecfdf5] text-[#065f46]">
              <CheckCircle size={14} />
              No known interactions detected
            </span>
          </div>
        )}
      </div>

      {/* No-interaction card */}
      {!has_interactions && (
        <div className="bg-white rounded-xl border border-[#e9eaef] px-5 py-6">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-[#ecfdf5] flex items-center justify-center shrink-0">
              <CheckCircle size={20} className="text-[#10b981]" />
            </div>
            <div>
              <p className="font-semibold text-[#1c1c1e]">
                No known interactions detected
              </p>
              <p className="text-sm text-[#555a6a] mt-0.5">
                No dangerous drug combinations found among this patient's active medications.
              </p>
            </div>
          </div>

          {active_class_keys.length > 0 && (
            <div className="mt-4 pt-4 border-t border-[#e9eaef]">
              <p className="text-xs font-semibold text-[#a5a8b5] uppercase tracking-wider mb-2">
                Active drug classes checked
              </p>
              <div className="flex flex-wrap gap-1.5">
                {active_class_keys.map((key) => (
                  <span
                    key={key}
                    className="text-xs px-2.5 py-0.5 rounded-full bg-[#f5f6f8] text-[#555a6a] border border-[#e9eaef]"
                  >
                    {key}
                  </span>
                ))}
              </div>
            </div>
          )}

          {active_class_keys.length === 0 && (
            <div className="mt-4 pt-4 border-t border-[#e9eaef]">
              <p className="text-sm text-[#a5a8b5]">
                No active medications from tracked drug classes.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Interaction cards */}
      {interactions.length > 0 && (
        <div className="space-y-3">
          {interactions.map((interaction, i) => (
            <InteractionCard key={i} interaction={interaction} />
          ))}
        </div>
      )}

      {/* Active drug classes footer (when interactions found) */}
      {has_interactions && active_class_keys.length > 0 && (
        <div className="bg-white rounded-xl border border-[#e9eaef] px-5 py-4">
          <p className="text-xs font-semibold text-[#a5a8b5] uppercase tracking-wider mb-2">
            Active drug classes checked
          </p>
          <div className="flex flex-wrap gap-1.5">
            {active_class_keys.map((key) => (
              <span
                key={key}
                className="text-xs px-2.5 py-0.5 rounded-full bg-[#f5f6f8] text-[#555a6a] border border-[#e9eaef]"
              >
                {key}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
