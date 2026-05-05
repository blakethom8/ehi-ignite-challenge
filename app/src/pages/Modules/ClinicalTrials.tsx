import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CalendarRange,
  CheckCircle,
  Stethoscope,
  Target,
  UserRound,
} from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { ProcedureItem, RankedConditionItem } from "../../types";

function formatDate(value: string | null): string {
  if (!value) return "Date unknown";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function monthsBetween(from: string | null, to: Date): number | null {
  if (!from) return null;
  const start = new Date(from);
  if (Number.isNaN(start.getTime())) return null;
  return Math.max(0, Math.round((to.getTime() - start.getTime()) / (30.4 * 24 * 60 * 60 * 1000)));
}

// ── Eligibility signal classification ───────────────────────────────────────
//
// Active conditions are the trial-search anchors. Each anchor gets a
// "search-readiness" status driven by deterministic rules over the chart's
// risk_category, clinical_status, and onset recency.

type AnchorStatus = "ANCHOR" | "VERIFY" | "DEPRIORITIZE";

interface AnchorSignal {
  condition: RankedConditionItem;
  status: AnchorStatus;
  rationale: string;
  verifyItems: string[];
}

// risk_category values come from the chart's body-system classifier:
// CARDIAC, METABOLIC, HEMATOLOGIC, ONCOLOGIC, RESPIRATORY, RENAL, NEURO,
// HEPATIC, INFECTIOUS, PSYCHIATRIC, OTHER, etc. We treat any non-OTHER
// active condition as a search anchor and use the body system to drive
// the verify-before-search guidance.
const VERIFY_HINTS: Record<string, string> = {
  CARDIAC: "Confirm ejection fraction, NYHA class, and rate/rhythm control status.",
  METABOLIC: "Confirm A1c trajectory and current medication response.",
  HEMATOLOGIC: "Confirm anemia type, transfusion history, and recent CBC.",
  ONCOLOGIC: "Confirm staging, biomarker testing, and performance status — most oncology trials require all three.",
  RESPIRATORY: "Confirm spirometry results, exacerbation history, and oxygen requirements.",
  RENAL: "Confirm eGFR trajectory, dialysis status, and proteinuria.",
  NEURO: "Confirm imaging findings and any disease-specific severity scores.",
  HEPATIC: "Confirm Child-Pugh / MELD score and recent LFTs.",
  INFECTIOUS: "Confirm pathogen, treatment phase, and viral load if applicable.",
  PSYCHIATRIC: "Confirm symptom severity scale (PHQ-9, GAD-7, etc.) and treatment response.",
};

function classifyAnchor(condition: RankedConditionItem): AnchorSignal {
  const cat = condition.risk_category;
  const status = condition.clinical_status;
  const months = monthsBetween(condition.onset_dt, new Date());
  const isActive = status === "active";

  if (cat === "OTHER") {
    return {
      condition,
      status: "DEPRIORITIZE",
      rationale: "Non-body-system condition — useful only as an exclusion check, not a primary anchor.",
      verifyItems: [],
    };
  }

  const verify: string[] = [];
  const systemHint = VERIFY_HINTS[cat];
  if (systemHint) verify.push(systemHint);
  verify.push("Check most-recent labs and imaging dates against trial freshness windows.");
  if (months !== null && months > 60) {
    verify.push(`Onset was ~${Math.round(months / 12)}y ago — confirm the condition is still the current treatment focus.`);
  }

  if (!isActive) {
    return {
      condition,
      status: "VERIFY",
      rationale: `${condition.risk_label} system condition with clinical status "${status}" — confirm it is still relevant before searching.`,
      verifyItems: verify,
    };
  }

  return {
    condition,
    status: "ANCHOR",
    rationale: `Active ${condition.risk_label.toLowerCase()} system condition — usable as a first-pass trial-search seed.`,
    verifyItems: verify,
  };
}

const ANCHOR_CONFIG = {
  ANCHOR: {
    bg: "#f0fdf4",
    border: "#22c55e",
    text: "#166534",
    badgeBg: "#dcfce7",
    label: "ANCHOR",
    Icon: CheckCircle,
  },
  VERIFY: {
    bg: "#fffbeb",
    border: "#f59e0b",
    text: "#92400e",
    badgeBg: "#fef3c7",
    label: "VERIFY",
    Icon: AlertTriangle,
  },
  DEPRIORITIZE: {
    bg: "#f9fafb",
    border: "#9ca3af",
    text: "#374151",
    badgeBg: "#f3f4f6",
    label: "DEPRIORITIZE",
    Icon: AlertOctagon,
  },
} as const;

// ── Verdict ────────────────────────────────────────────────────────────────

type Verdict = "READY" | "PARTIAL" | "INSUFFICIENT";

function verdictFor(signals: AnchorSignal[]): Verdict {
  const anchors = signals.filter((s) => s.status === "ANCHOR").length;
  const verify = signals.filter((s) => s.status === "VERIFY").length;
  if (anchors >= 1) return "READY";
  if (verify >= 1) return "PARTIAL";
  return "INSUFFICIENT";
}

function VerdictHero({
  patientName,
  ageYears,
  yearsHistory,
  signals,
}: {
  patientName: string;
  ageYears: number;
  yearsHistory: number;
  signals: AnchorSignal[];
}) {
  const verdict = verdictFor(signals);
  const anchorCount = signals.filter((s) => s.status === "ANCHOR").length;
  const verifyCount = signals.filter((s) => s.status === "VERIFY").length;

  const config = {
    READY: {
      bg: "#f0fdf4",
      border: "#22c55e",
      text: "#166534",
      message: "Search-ready — high-signal anchor available",
      Icon: CheckCircle,
    },
    PARTIAL: {
      bg: "#fffbeb",
      border: "#f59e0b",
      text: "#92400e",
      message: "Partial signal — verify before searching",
      Icon: AlertTriangle,
    },
    INSUFFICIENT: {
      bg: "#f9fafb",
      border: "#9ca3af",
      text: "#374151",
      message: "Insufficient eligibility signal in this chart",
      Icon: AlertOctagon,
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
              {anchorCount} anchor · {verifyCount} verify · {Math.floor(ageYears)}y old · {yearsHistory.toFixed(1)}y of history
            </p>
          </div>
        </div>
        <div className="min-w-[180px]">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7280]">Active conditions</p>
          <p className="mt-1 text-4xl font-semibold text-[#111827]">{signals.length}</p>
        </div>
      </div>
    </section>
  );
}

// ── Per-anchor card ────────────────────────────────────────────────────────

function AnchorCard({ signal }: { signal: AnchorSignal }) {
  const cfg = ANCHOR_CONFIG[signal.status];
  return (
    <article
      className="rounded-2xl border border-[#e9eaef] bg-white p-5 shadow-sm"
      style={{ borderLeftWidth: 4, borderLeftColor: cfg.border }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-[#1c1c1e]">{signal.condition.display}</h3>
          <p className="mt-1 text-xs text-[#8d92a3]">
            Onset {formatDate(signal.condition.onset_dt)} · {signal.condition.clinical_status}
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

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-[#eef1ff] px-2 py-0.5 text-xs font-semibold text-[#5b76fe]">
          {signal.condition.risk_label}
        </span>
        <span className="text-xs text-[#6b7280]">Rank #{signal.condition.risk_rank}</span>
      </div>

      <p className="mt-3 text-sm leading-6 text-[#374151]">{signal.rationale}</p>

      {signal.verifyItems.length > 0 && (
        <div className="mt-3 rounded-lg bg-[#f7f8fc] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#6b7280]">
            Verify before searching
          </p>
          <ul className="mt-2 space-y-1.5">
            {signal.verifyItems.map((item) => (
              <li key={item} className="flex items-start gap-2 text-sm leading-5 text-[#1f2937]">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#5b76fe]" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

function AnchorGroup({
  status,
  signals,
}: {
  status: AnchorStatus;
  signals: AnchorSignal[];
}) {
  if (signals.length === 0) return null;
  const titles = {
    ANCHOR: { title: "Primary search anchors", body: "Strong active conditions usable as first-pass trial-search seeds." },
    VERIFY: { title: "Verify before searching", body: "Conditions that need confirmation or staging before they shape the search." },
    DEPRIORITIZE: { title: "Lower-priority context", body: "Useful for exclusion checks, not as primary anchors." },
  };
  const meta = titles[status];

  return (
    <section>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-base font-semibold text-[#1c1c1e]">{meta.title}</h2>
        <p className="text-xs text-[#6b7280]">
          {signals.length} {signals.length === 1 ? "condition" : "conditions"}
        </p>
      </div>
      <p className="mt-1 max-w-3xl text-sm text-[#667085]">{meta.body}</p>
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        {signals.map((signal) => (
          <AnchorCard key={signal.condition.condition_id} signal={signal} />
        ))}
      </div>
    </section>
  );
}

// ── Recent procedures + record-span context ────────────────────────────────

function RecordSpanCard({
  ageYears,
  gender,
  earliest,
  latest,
  yearsHistory,
  recentProcedures,
}: {
  ageYears: number;
  gender: string;
  earliest: string | null;
  latest: string | null;
  yearsHistory: number;
  recentProcedures: ProcedureItem[];
}) {
  return (
    <section className="rounded-2xl border border-[#dfe4ea] bg-white p-5">
      <div className="flex items-center gap-2">
        <CalendarRange size={18} className="text-[#5b76fe]" />
        <h2 className="text-base font-semibold text-[#1c1c1e]">Patient + record context</h2>
      </div>
      <p className="mt-1 text-sm text-[#667085]">
        Constraints the trial search should pre-filter against.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-[#eef0f4] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#6b7280]">Patient traits</p>
          <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
            {Math.floor(ageYears)} years · {gender}
          </p>
          <p className="mt-1 text-xs text-[#6b7280]">
            Trials filter on age and sex first — confirm both meet inclusion bands.
          </p>
        </div>
        <div className="rounded-xl border border-[#eef0f4] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#6b7280]">Record span</p>
          <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
            {formatDate(earliest)} → {formatDate(latest)}
          </p>
          <p className="mt-1 text-xs text-[#6b7280]">
            {yearsHistory.toFixed(1)}y of longitudinal context. Trials often want recent labs/imaging — verify dates.
          </p>
        </div>
      </div>

      <div className="mt-4">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-[#6b7280]">
          Recent procedures (last 12 months)
        </p>
        {recentProcedures.length > 0 ? (
          <ul className="mt-2 space-y-1.5">
            {recentProcedures.map((p) => (
              <li key={p.procedure_id} className="flex items-start gap-2 text-sm leading-5 text-[#1f2937]">
                <Stethoscope size={13} className="mt-1 shrink-0 text-[#5b76fe]" />
                <div>
                  <span className="font-semibold">{p.display}</span>
                  <span className="ml-2 text-xs text-[#6b7280]">{formatDate(p.performed_start)}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-[#6b7280]">No procedures recorded in the last 12 months.</p>
        )}
      </div>
    </section>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export function ClinicalTrials() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const [renderedAtMs] = useState(() => Date.now());

  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });
  const conditionsQ = useQuery({
    queryKey: ["conditionAcuity", patientId],
    queryFn: () => api.getConditionAcuity(patientId!),
    enabled: !!patientId,
  });
  const proceduresQ = useQuery({
    queryKey: ["procedures", patientId],
    queryFn: () => api.getProcedures(patientId!),
    enabled: !!patientId,
  });

  const signals = useMemo(() => {
    if (!conditionsQ.data) return [];
    return conditionsQ.data.ranked_active.map(classifyAnchor);
  }, [conditionsQ.data]);

  const grouped = useMemo(() => {
    const groups: Record<AnchorStatus, AnchorSignal[]> = {
      ANCHOR: [],
      VERIFY: [],
      DEPRIORITIZE: [],
    };
    signals.forEach((s) => groups[s.status].push(s));
    return groups;
  }, [signals]);

  const recentProcedures = useMemo(() => {
    if (!proceduresQ.data) return [] as ProcedureItem[];
    const cutoff = renderedAtMs - 365 * 24 * 60 * 60 * 1000;
    return proceduresQ.data.procedures
      .filter((p) => {
        if (!p.performed_start) return false;
        const t = new Date(p.performed_start).getTime();
        return !Number.isNaN(t) && t >= cutoff;
      })
      .sort((a, b) => {
        const ta = a.performed_start ? new Date(a.performed_start).getTime() : 0;
        const tb = b.performed_start ? new Date(b.performed_start).getTime() : 0;
        return tb - ta;
      })
      .slice(0, 6);
  }, [proceduresQ.data, renderedAtMs]);

  if (!patientId) {
    return (
      <EmptyState
        icon={UserRound}
        title="Choose a patient to begin"
        bullets={[
          "Classifies each active condition as a search anchor, verify-first, or deprioritized",
          "Each anchor card lists what to confirm before starting trial search",
          "Surfaces patient traits and recent procedures as inclusion-band context",
        ]}
        stat="Clinical trials module"
      />
    );
  }

  if (overviewQ.isLoading || conditionsQ.isLoading || proceduresQ.isLoading) {
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

  if (
    overviewQ.isError ||
    conditionsQ.isError ||
    proceduresQ.isError ||
    !overviewQ.data ||
    !conditionsQ.data ||
    !proceduresQ.data
  ) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load trial-matching workspace.</p>
      </div>
    );
  }

  const overview = overviewQ.data;

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-6 lg:p-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
            <Target size={13} />
            Clinical Insight Module
          </p>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-[#1c1c1e]">
            Trial Matching
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#667085]">
            Per-condition search-readiness — classifies each active anchor and lists what must be verified before generating a trial-search packet.
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

      <VerdictHero
        patientName={overview.name}
        ageYears={overview.age_years}
        yearsHistory={overview.years_of_history}
        signals={signals}
      />

      {signals.length === 0 ? (
        <section className="rounded-2xl border border-[#dfe4ea] bg-white p-6 text-center">
          <Target size={28} className="mx-auto text-[#5b76fe]" />
          <h2 className="mt-3 text-base font-semibold text-[#1c1c1e]">No active conditions to anchor a search</h2>
          <p className="mt-2 text-sm text-[#6b7280]">
            Trial search needs at least one current diagnosis. Confirm the chart reflects active problems.
          </p>
        </section>
      ) : (
        <>
          <AnchorGroup status="ANCHOR" signals={grouped.ANCHOR} />
          <AnchorGroup status="VERIFY" signals={grouped.VERIFY} />
          <AnchorGroup status="DEPRIORITIZE" signals={grouped.DEPRIORITIZE} />
        </>
      )}

      <RecordSpanCard
        ageYears={overview.age_years}
        gender={overview.gender}
        earliest={overview.earliest_encounter_dt}
        latest={overview.latest_encounter_dt}
        yearsHistory={overview.years_of_history}
        recentProcedures={recentProcedures}
      />

      <section className="rounded-2xl border border-[#d8f3ec] bg-[#f3fffb] p-5">
        <h2 className="text-base font-semibold text-[#087d75]">Methodology</h2>
        <p className="mt-1 text-sm text-[#3f635f]">
          Deterministic search-readiness classifier over active conditions. No external trial-registry calls are made — those belong to the future trial-matching agent.
        </p>
        <ul className="mt-3 grid gap-2 md:grid-cols-2">
          {[
            "Each condition is tagged with a body-system risk category (cardiac, metabolic, oncologic, etc.) by the chart's classifier.",
            "Active body-system conditions become anchors; non-active ones are verify-first; OTHER is deprioritized.",
            "Each anchor lists 'verify before searching' items keyed off the body system and onset recency.",
            "Patient age, sex, record span, and recent procedures are surfaced as inclusion-band pre-filters.",
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
