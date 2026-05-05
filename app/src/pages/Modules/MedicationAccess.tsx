import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  HeartHandshake,
  Pill,
  ShieldAlert,
  UserRound,
} from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { MedRow, SafetyFlag } from "../../types";

type AccessTier = "specialty" | "controlled" | "assistance" | "standard";

interface AccessSignal {
  med: MedRow;
  tier: AccessTier;
  classLabel: string | null;
  classKey: string | null;
  reason: string;
  action: string;
}

// ── Tier classification ────────────────────────────────────────────────────
//
// Conservative client-side mapping from safety class_key → access tier.
// This is deterministic and inspectable. The actual cost/program lookups
// belong to the future medication-access agent; this module only frames
// what kind of access path applies.

// Class keys come from lib/clinical/drug_classes.json — lowercase plural.
const SPECIALTY_CLASSES = new Set([
  "jak_inhibitors",
  "immunosuppressants",
]);

const CONTROLLED_CLASSES = new Set([
  "opioids",
  "stimulants",
]);

const ASSISTANCE_CLASSES = new Set([
  "anticoagulants",
  "diabetes_medications",
  "psych_medications",
]);

function tierFor(classKey: string | null): AccessTier {
  if (!classKey) return "standard";
  if (SPECIALTY_CLASSES.has(classKey)) return "specialty";
  if (CONTROLLED_CLASSES.has(classKey)) return "controlled";
  if (ASSISTANCE_CLASSES.has(classKey)) return "assistance";
  return "standard";
}

const TIER_CONFIG: Record<
  AccessTier,
  {
    label: string;
    bg: string;
    border: string;
    text: string;
    badgeBg: string;
    Icon: typeof AlertOctagon;
    blurb: string;
  }
> = {
  specialty: {
    label: "Specialty pharmacy",
    bg: "#fef2f2",
    border: "#ef4444",
    text: "#991b1b",
    badgeBg: "#fee2e2",
    Icon: AlertOctagon,
    blurb: "High-cost class. Likely dispensed through a specialty pharmacy with prior auth and patient assistance options.",
  },
  controlled: {
    label: "Controlled substance",
    bg: "#fffbeb",
    border: "#f59e0b",
    text: "#92400e",
    badgeBg: "#fef3c7",
    Icon: ShieldAlert,
    blurb: "Schedule II–IV. Quantity limits, refill timing, and provider DEA verification typically apply.",
  },
  assistance: {
    label: "Assistance candidate",
    bg: "#eff6ff",
    border: "#3b82f6",
    text: "#1e3a8a",
    badgeBg: "#dbeafe",
    Icon: HeartHandshake,
    blurb: "Manufacturer copay cards, patient assistance programs, or 90-day fill commonly reduce out-of-pocket cost.",
  },
  standard: {
    label: "Generic-likely",
    bg: "#f0fdf4",
    border: "#22c55e",
    text: "#166534",
    badgeBg: "#dcfce7",
    Icon: CheckCircle,
    blurb: "No flagged class. Generic equivalents and discount-pharmacy options usually available.",
  },
};

function buildSignals(meds: MedRow[], flags: SafetyFlag[]): AccessSignal[] {
  // Build lookup: med_id → (class_key, label) — first matching active flag wins.
  const medToClass = new Map<string, { classKey: string; label: string }>();
  flags.forEach((flag) => {
    flag.medications.forEach((m) => {
      if (m.is_active && !medToClass.has(m.med_id)) {
        medToClass.set(m.med_id, { classKey: flag.class_key, label: flag.label });
      }
    });
  });

  return meds
    .filter((m) => m.is_active)
    .map((med) => {
      const matched = medToClass.get(med.med_id) ?? null;
      const classKey = matched?.classKey ?? null;
      const tier = tierFor(classKey);

      let reason: string;
      let action: string;
      if (tier === "specialty") {
        reason = `${matched?.label ?? "Specialty class"} — typically high-cost.`;
        action = "Confirm specialty-pharmacy network and start manufacturer assistance enrollment.";
      } else if (tier === "controlled") {
        reason = `${matched?.label ?? "Controlled substance class"} — quantity-limited.`;
        action = "Coordinate refill timing with prescriber; verify state-controlled-substance rules.";
      } else if (tier === "assistance") {
        reason = `${matched?.label ?? "Common chronic class"} — assistance frequently available.`;
        action = "Compare manufacturer copay card vs 90-day mail-order vs discount pharmacy.";
      } else {
        reason = "No flagged class detected on this medication.";
        action = "Default path — discount pharmacy or 90-day generic fill.";
      }

      return { med, tier, classKey, classLabel: matched?.label ?? null, reason, action };
    });
}

// ── Verdict + hero ─────────────────────────────────────────────────────────

type Verdict = "FOCUSED_REVIEW" | "REVIEW" | "STANDARD";

function verdictFor(signals: AccessSignal[]): Verdict {
  if (signals.some((s) => s.tier === "specialty")) return "FOCUSED_REVIEW";
  if (signals.some((s) => s.tier === "controlled" || s.tier === "assistance")) return "REVIEW";
  return "STANDARD";
}

function VerdictHero({ patientName, signals }: { patientName: string; signals: AccessSignal[] }) {
  const verdict = verdictFor(signals);
  const counts = signals.reduce(
    (acc, s) => {
      acc[s.tier] += 1;
      return acc;
    },
    { specialty: 0, controlled: 0, assistance: 0, standard: 0 },
  );

  const config = {
    FOCUSED_REVIEW: {
      bg: "#fef2f2",
      border: "#ef4444",
      text: "#991b1b",
      message: "Focused affordability review needed",
      Icon: AlertOctagon,
    },
    REVIEW: {
      bg: "#fffbeb",
      border: "#f59e0b",
      text: "#92400e",
      message: "Review for assistance and refill rules",
      Icon: AlertTriangle,
    },
    STANDARD: {
      bg: "#f0fdf4",
      border: "#22c55e",
      text: "#166534",
      message: "Standard affordability path likely",
      Icon: CheckCircle,
    },
  }[verdict];

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
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">{patientName}</h2>
            <p className="mt-1 text-sm" style={{ color: config.text, opacity: 0.78 }}>
              {counts.specialty} specialty · {counts.controlled} controlled · {counts.assistance} assistance candidate · {counts.standard} generic-likely
            </p>
          </div>
        </div>
        <div className="min-w-[180px]">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7280]">Active medications</p>
          <p className="mt-1 text-4xl font-semibold text-[#111827]">{signals.length}</p>
        </div>
      </div>
    </section>
  );
}

// ── Per-med card ───────────────────────────────────────────────────────────

function formatDate(value: string | null): string {
  if (!value) return "Date unknown";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function MedCard({ signal }: { signal: AccessSignal }) {
  const cfg = TIER_CONFIG[signal.tier];
  return (
    <article
      className="rounded-2xl border border-[#e9eaef] bg-white p-5 shadow-sm"
      style={{ borderLeftWidth: 4, borderLeftColor: cfg.border }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-[#1c1c1e]">{signal.med.display}</h3>
          <p className="mt-1 text-xs text-[#8d92a3]">
            Authored {formatDate(signal.med.authored_on)} · {signal.med.status}
          </p>
        </div>
        <span
          className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
          style={{ backgroundColor: cfg.badgeBg, color: cfg.text }}
        >
          <cfg.Icon size={12} />
          {cfg.label}
        </span>
      </div>

      <p className="mt-4 text-sm leading-6 text-[#374151]">{signal.reason}</p>

      <div className="mt-3 rounded-lg bg-[#f7f8fc] px-3 py-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-[#6b7280]">Access path</p>
        <p className="mt-1 text-sm leading-5 text-[#1f2937]">{signal.action}</p>
      </div>
    </article>
  );
}

function TierGroup({
  tier,
  signals,
}: {
  tier: AccessTier;
  signals: AccessSignal[];
}) {
  if (signals.length === 0) return null;
  const cfg = TIER_CONFIG[tier];
  return (
    <section>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-base font-semibold text-[#1c1c1e]">{cfg.label}</h2>
        <p className="text-xs text-[#6b7280]">
          {signals.length} {signals.length === 1 ? "medication" : "medications"}
        </p>
      </div>
      <p className="mt-1 max-w-3xl text-sm text-[#667085]">{cfg.blurb}</p>
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        {signals.map((signal) => (
          <MedCard key={signal.med.med_id} signal={signal} />
        ))}
      </div>
    </section>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export function MedicationAccess() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });
  const safetyQ = useQuery({
    queryKey: ["safety", patientId],
    queryFn: () => api.getSafety(patientId!),
    enabled: !!patientId,
  });

  const signals = useMemo(() => {
    if (!overviewQ.data || !safetyQ.data) return [];
    return buildSignals(overviewQ.data.medications, safetyQ.data.flags);
  }, [overviewQ.data, safetyQ.data]);

  const grouped = useMemo(() => {
    const groups: Record<AccessTier, AccessSignal[]> = {
      specialty: [],
      controlled: [],
      assistance: [],
      standard: [],
    };
    signals.forEach((s) => groups[s.tier].push(s));
    return groups;
  }, [signals]);

  if (!patientId) {
    return (
      <EmptyState
        icon={UserRound}
        title="Choose a patient to begin"
        bullets={[
          "Maps active medications to a deterministic affordability tier",
          "Surfaces specialty-pharmacy candidates, controlled-substance constraints, and assistance candidates",
          "Each card carries a concrete next access step",
        ]}
        stat="Medication access module"
      />
    );
  }

  if (overviewQ.isLoading || safetyQ.isLoading) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 p-8">
        <div className="h-40 animate-pulse rounded-2xl bg-[#e9eaef]" />
        <div className="grid gap-4 md:grid-cols-2">
          <div className="h-44 animate-pulse rounded-2xl bg-[#e9eaef]" />
          <div className="h-44 animate-pulse rounded-2xl bg-[#e9eaef]" />
        </div>
      </div>
    );
  }

  if (overviewQ.isError || safetyQ.isError || !overviewQ.data || !safetyQ.data) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load medication access workspace.</p>
      </div>
    );
  }

  const overview = overviewQ.data;

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-6 lg:p-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
            <Pill size={13} />
            Clinical Insight Module
          </p>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-[#1c1c1e]">
            Medication Access
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#667085]">
            Per-medication affordability tier and the access path that applies — derived from active therapies and the deterministic drug-class flagger.
          </p>
        </div>
        <Link
          to={`/explorer?patient=${patientId}`}
          className="hidden shrink-0 items-center gap-1 rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-sm font-semibold text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe] sm:inline-flex"
        >
          Patient record
          <ArrowRight size={14} />
        </Link>
      </div>

      <VerdictHero patientName={overview.name} signals={signals} />

      {signals.length === 0 ? (
        <section className="rounded-2xl border border-[#dfe4ea] bg-white p-6 text-center">
          <Pill size={28} className="mx-auto text-[#5b76fe]" />
          <h2 className="mt-3 text-base font-semibold text-[#1c1c1e]">No active medications</h2>
          <p className="mt-2 text-sm text-[#6b7280]">
            Nothing to assess for affordability. Confirm the chart reflects current therapy.
          </p>
        </section>
      ) : (
        <>
          <TierGroup tier="specialty" signals={grouped.specialty} />
          <TierGroup tier="controlled" signals={grouped.controlled} />
          <TierGroup tier="assistance" signals={grouped.assistance} />
          <TierGroup tier="standard" signals={grouped.standard} />
        </>
      )}

      <section className="rounded-2xl border border-[#d8f3ec] bg-[#f3fffb] p-5">
        <h2 className="text-base font-semibold text-[#087d75]">Methodology</h2>
        <p className="mt-1 text-sm text-[#3f635f]">
          Tiering is a client-side classifier over the deterministic drug-class flagger. No external pricing or program lookups are performed — those belong to the future medication-access agent.
        </p>
        <ul className="mt-3 grid gap-2 md:grid-cols-2">
          {[
            "Each active medication is matched to its first ACTIVE safety class via the chart's drug-class flagger.",
            "Specialty class keys (JAK inhibitors, immunosuppressants) trigger the specialty-pharmacy tier.",
            "Controlled-substance class keys (opioids, stimulants) trigger refill-rule constraints.",
            "Assistance-eligible class keys (anticoagulants, diabetes meds, psychiatric meds) flag manufacturer or copay-card candidates.",
          ].map((note) => (
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
