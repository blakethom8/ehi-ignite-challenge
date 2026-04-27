import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle,
  ClipboardCheck,
  Gauge,
} from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { SurgicalRiskComponent } from "../../types";

type DomainStatus = "CLEARED" | "FLAGGED" | "REVIEW";

function toDomainStatus(disposition: "CLEARED" | "REVIEW" | "HOLD"): DomainStatus {
  if (disposition === "HOLD") return "FLAGGED";
  return disposition;
}

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
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold"
      style={{ backgroundColor: config.bg, color: config.text, borderColor: config.border }}
    >
      <config.Icon size={12} />
      {config.label}
    </span>
  );
}

function ScoreHero({
  name,
  score,
  maxScore,
  disposition,
  tier,
}: {
  name: string;
  score: number;
  maxScore: number;
  disposition: "CLEARED" | "REVIEW" | "HOLD";
  tier: "LOW" | "MODERATE" | "HIGH";
}) {
  const status = toDomainStatus(disposition);
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
      message: "Pre-Op Clearance: Hold - Review Required",
      Icon: AlertOctagon,
    },
    REVIEW: {
      bg: "#fffbeb",
      border: "#f59e0b",
      text: "#92400e",
      message: "Pre-Op Clearance: Incomplete - Pending Review",
      Icon: AlertTriangle,
    },
  }[status];
  const percent = Math.min(100, Math.round((score / maxScore) * 100));

  return (
    <section
      className="rounded-2xl border p-6"
      style={{ backgroundColor: config.bg, borderColor: config.border }}
    >
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <div
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl"
            style={{ backgroundColor: "rgba(255,255,255,0.72)", color: config.text }}
          >
            <config.Icon size={22} />
          </div>
          <div>
            <p className="text-sm font-semibold" style={{ color: config.text }}>
              {config.message}
            </p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">{name}</h2>
            <p className="mt-1 text-sm" style={{ color: config.text, opacity: 0.78 }}>
              Deterministic surgical risk tier: {tier}
            </p>
          </div>
        </div>

        <div className="min-w-[180px]">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7280]">
                Risk score
              </p>
              <p className="mt-1 text-4xl font-semibold text-[#111827]">
                {score}
                <span className="text-base font-medium text-[#6b7280]">/{maxScore}</span>
              </p>
            </div>
            <Gauge size={24} style={{ color: config.text }} />
          </div>
          <div className="mt-3 h-2 rounded-full bg-white/80">
            <div
              className="h-2 rounded-full"
              style={{ width: `${percent}%`, backgroundColor: config.border }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function ComponentCard({ component }: { component: SurgicalRiskComponent }) {
  const status = component.status;
  const borderColor =
    status === "FLAGGED" ? "#ef4444" : status === "REVIEW" ? "#f59e0b" : "#22c55e";
  const percent = Math.min(100, Math.round((component.score / component.max_score) * 100));

  return (
    <article
      className="rounded-2xl border border-[#e9eaef] bg-white p-5 shadow-sm"
      style={{ borderLeftWidth: 4, borderLeftColor: borderColor }}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-[#1c1c1e]">{component.label}</h2>
          <p className="mt-1 text-sm leading-6 text-[#555a6a]">{component.rationale}</p>
        </div>
        <StatusChip status={status} />
      </div>

      <div className="mt-4 flex items-center gap-3">
        <div className="min-w-[76px] text-sm font-semibold text-[#111827]">
          {component.score}/{component.max_score}
        </div>
        <div className="h-2 flex-1 rounded-full bg-[#eef0f6]">
          <div
            className="h-2 rounded-full"
            style={{ width: `${percent}%`, backgroundColor: borderColor }}
          />
        </div>
      </div>

      {component.evidence.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {component.evidence.map((item) => (
            <li key={item} className="flex items-start gap-2 text-sm text-[#1c1c1e]">
              <span
                className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: borderColor }}
              />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-[#6b7280]">No scoring evidence detected for this domain.</p>
      )}
    </article>
  );
}

export function ExplorerClearance() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const riskQ = useQuery({
    queryKey: ["surgicalRisk", patientId],
    queryFn: () => api.getSurgicalRisk(patientId!),
    enabled: !!patientId,
  });

  if (!patientId) {
    return (
      <EmptyState
        icon={ClipboardCheck}
        title="No patient selected"
        bullets={[
          "Select a patient from the top bar",
          "Clearance uses deterministic rules across medications, conditions, labs, allergies, and interactions",
          "Flags surgical holds and items needing review",
        ]}
      />
    );
  }

  if (riskQ.isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 p-8">
        <div className="h-40 animate-pulse rounded-2xl bg-[#e9eaef]" />
        <div className="grid gap-4 md:grid-cols-2">
          <div className="h-48 animate-pulse rounded-2xl bg-[#e9eaef]" />
          <div className="h-48 animate-pulse rounded-2xl bg-[#e9eaef]" />
          <div className="h-48 animate-pulse rounded-2xl bg-[#e9eaef]" />
          <div className="h-48 animate-pulse rounded-2xl bg-[#e9eaef]" />
        </div>
      </div>
    );
  }

  if (riskQ.isError || !riskQ.data) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load clearance data.</p>
      </div>
    );
  }

  const risk = riskQ.data;

  return (
    <div className="mx-auto max-w-4xl space-y-5 p-8">
      <div>
        <h1 className="mb-1 text-xl font-semibold text-[#1c1c1e]">
          {risk.name} - Pre-Op Clearance Checklist
        </h1>
        <p className="text-sm text-[#6b7280]">
          Rules-backed surgical readiness assessment from parsed Synthea R4 FHIR data
        </p>
      </div>

      <ScoreHero
        name={risk.name}
        score={risk.score}
        maxScore={risk.max_score}
        disposition={risk.disposition}
        tier={risk.tier}
      />

      <section className="grid gap-4 md:grid-cols-2">
        {risk.components.map((component) => (
          <ComponentCard key={component.key} component={component} />
        ))}
      </section>

      <section className="rounded-2xl border border-[#d8f3ec] bg-[#f3fffb] p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-[#087d75]">Scoring Methodology</h2>
            <p className="mt-1 text-sm text-[#3f635f]">
              {risk.rule_version} is deterministic, inspectable, and designed for demo-safe
              clinical triage.
            </p>
          </div>
          <StatusChip status={toDomainStatus(risk.disposition)} />
        </div>
        <ul className="mt-4 grid gap-2 md:grid-cols-2">
          {risk.methodology_notes.map((note) => (
            <li key={note} className="flex items-start gap-2 text-sm leading-6 text-[#1f4f4b]">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#087d75]" />
              <span>{note}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
