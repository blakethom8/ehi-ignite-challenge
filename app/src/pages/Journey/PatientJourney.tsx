import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  CheckCircle,
  HeartPulse,
  Pill,
  Stethoscope,
  TestTube2,
  User,
} from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type {
  CareJourneyResponse,
  ConditionAcuityResponse,
  KeyLabsResponse,
  PatientOverview,
  SafetyResponse,
  SurgicalRiskComponent,
  SurgicalRiskResponse,
} from "../../types";

type Tone = "red" | "amber" | "green" | "blue" | "neutral";

const toneConfig: Record<Tone, { bg: string; border: string; text: string; soft: string }> = {
  red: { bg: "#fef2f2", border: "#ef4444", text: "#991b1b", soft: "#fff7f7" },
  amber: { bg: "#fffbeb", border: "#f59e0b", text: "#92400e", soft: "#fffdf2" },
  green: { bg: "#f0fdf4", border: "#22c55e", text: "#166534", soft: "#f8fff9" },
  blue: { bg: "#eef1ff", border: "#5b76fe", text: "#3730a3", soft: "#f8f9ff" },
  neutral: { bg: "#f5f6f8", border: "#d9dce5", text: "#555a6a", soft: "#ffffff" },
};

function fmtDate(value: string | null): string {
  if (!value) return "Unknown";
  return new Date(value).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function fmtAge(ageYears: number): string {
  if (!ageYears) return "Age unknown";
  return `${Math.round(ageYears)} years`;
}

function fmtPatientAge(ageYears: number): string {
  if (!ageYears) return "Age unknown";
  return `${Math.round(ageYears)}-year-old`;
}

function fmtLabValue(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(2).replace(/\.?0+$/, "");
}

function shortLabName(display: string): string {
  return display.replace(/\s*\[[^\]]+\]/g, "").replace(/\s+in Blood$/i, "").trim();
}

function titleCase(value: string): string {
  if (!value) return "Unknown";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function riskTone(risk: SurgicalRiskResponse): Tone {
  if (risk.disposition === "HOLD") return "red";
  if (risk.disposition === "REVIEW") return "amber";
  return "green";
}

function componentByKey(risk: SurgicalRiskResponse, key: string): SurgicalRiskComponent | undefined {
  return risk.components.find((component) => component.key === key);
}

function topMedicationAlerts(safety: SafetyResponse): string[] {
  return safety.flags
    .filter((flag) => flag.status === "ACTIVE")
    .sort((a, b) => {
      const score = { critical: 0, warning: 1, info: 2 };
      return score[a.severity] - score[b.severity];
    })
    .flatMap((flag) =>
      flag.medications
        .filter((med) => med.is_active)
        .map((med) => `${med.display} - ${flag.label}`)
    )
    .slice(0, 4);
}

function topComorbidities(conditions: ConditionAcuityResponse): string[] {
  return conditions.ranked_active
    .filter((condition) => condition.risk_category !== "OTHER")
    .slice(0, 5)
    .map((condition) => `${condition.display} (${condition.risk_label})`);
}

function keyLabFacts(labs: KeyLabsResponse): string[] {
  if (labs.alert_flags.length > 0) {
    return labs.alert_flags.slice(0, 4).map((flag) => flag.message);
  }

  const preferredPanels = ["Hematology", "Coagulation", "Metabolic", "Renal"];
  const facts: string[] = [];
  for (const panel of preferredPanels) {
    const value = labs.panels[panel]?.[0];
    if (!value || value.value === null) continue;
    const unit = value.unit ? ` ${value.unit}` : "";
    facts.push(`${shortLabName(value.display)}: ${fmtLabValue(value.value)}${unit} (${fmtDate(value.effective_dt)})`);
  }
  return facts.slice(0, 4);
}

function anesthesiaNotes(risk: SurgicalRiskResponse, conditions: ConditionAcuityResponse): string[] {
  const notes: string[] = [];
  const medicationComponent = componentByKey(risk, "medications");
  const labComponent = componentByKey(risk, "labs");
  const hasPulmonary = conditions.ranked_active.some((condition) => condition.risk_category === "PULMONARY");
  const hasCardiac = conditions.ranked_active.some((condition) => condition.risk_category === "CARDIAC");

  if (medicationComponent?.status === "FLAGGED") {
    notes.push("Medication hold plan required before anesthesia handoff.");
  }
  if (labComponent && labComponent.score > 0) {
    notes.push("Confirm lab readiness before day-of-surgery decision.");
  }
  if (hasCardiac) {
    notes.push("Active cardiac history should be highlighted for anesthesia review.");
  }
  if (hasPulmonary) {
    notes.push("Pulmonary history may affect airway and post-op monitoring.");
  }

  return notes.slice(0, 4);
}

function recentCareEvents(care: CareJourneyResponse): string[] {
  return [...care.encounters]
    .filter((encounter) => encounter.start)
    .sort((a, b) => (b.start || "").localeCompare(a.start || ""))
    .slice(0, 3)
    .map((encounter) => {
      const label = encounter.reason_display || encounter.type_text || encounter.class_code || "Encounter";
      return `${label} - ${fmtDate(encounter.start)}`;
    });
}

function BriefCard({
  title,
  items,
  empty,
  tone,
  icon: Icon,
}: {
  title: string;
  items: string[];
  empty: string;
  tone: Tone;
  icon: typeof AlertTriangle;
}) {
  const colors = toneConfig[tone];
  const hasItems = items.length > 0;

  return (
    <section
      className="rounded-2xl border bg-white p-5 shadow-sm"
      style={{ borderColor: hasItems ? colors.border : "#e9eaef", borderLeftWidth: hasItems ? 4 : 1 }}
    >
      <div className="flex items-center gap-2">
        <Icon size={17} style={{ color: hasItems ? colors.text : "#6b7280" }} />
        <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-[#555a6a]">
          {title}
        </h2>
      </div>
      {hasItems ? (
        <ul className="mt-4 space-y-3">
          {items.map((item) => (
            <li key={item} className="flex items-start gap-2 text-sm leading-6 text-[#1c1c1e]">
              <span
                className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: colors.border }}
              />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm leading-6 text-[#6b7280]">{empty}</p>
      )}
    </section>
  );
}

function FactRail({ overview, care }: { overview: PatientOverview; care: CareJourneyResponse }) {
  const facts = [
    { label: "Patient", value: `${fmtAge(overview.age_years)} / ${titleCase(overview.gender)}` },
    { label: "Data span", value: `${overview.years_of_history.toFixed(1)} years` },
    { label: "Active meds", value: String(overview.active_med_count) },
    { label: "Active problems", value: String(overview.active_condition_count) },
    { label: "Encounters", value: String(care.encounters.length || overview.encounter_count) },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-5">
      {facts.map((fact) => (
        <div key={fact.label} className="rounded-xl border border-[#e9eaef] bg-white px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#a5a8b5]">
            {fact.label}
          </p>
          <p className="mt-1 text-lg font-semibold text-[#111827]">{fact.value}</p>
        </div>
      ))}
    </div>
  );
}

function RiskHero({ risk, overview }: { risk: SurgicalRiskResponse; overview: PatientOverview }) {
  const tone = riskTone(risk);
  const colors = toneConfig[tone];
  const dispositionLabel =
    risk.disposition === "HOLD"
      ? "Hold - review required"
      : risk.disposition === "REVIEW"
      ? "Review before proceeding"
      : "No hold detected";

  return (
    <section
      className="rounded-3xl border p-7"
      style={{ backgroundColor: colors.bg, borderColor: colors.border }}
    >
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-2xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-white/75 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em]" style={{ color: colors.text }}>
            <HeartPulse size={14} />
            30-second surgical briefing
          </div>
          <h1 className="text-3xl font-semibold leading-tight text-[#111827]">Surgical disposition</h1>
          <p className="mt-2 text-base leading-7 text-[#334155]">
            {fmtPatientAge(overview.age_years)} {overview.gender} with {overview.active_condition_count} active
            conditions, {overview.active_med_count} active medications, and{" "}
            {overview.years_of_history.toFixed(1)} years of longitudinal FHIR history.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <span className="rounded-full bg-white/80 px-3 py-1 text-sm font-semibold" style={{ color: colors.text }}>
              {dispositionLabel}
            </span>
            <span className="rounded-full bg-white/70 px-3 py-1 text-sm text-[#475569]">
              Tier {risk.tier}
            </span>
            <span className="rounded-full bg-white/70 px-3 py-1 text-sm text-[#475569]">
              {risk.rule_version}
            </span>
          </div>
        </div>

        <div className="w-full rounded-2xl bg-white/82 p-5 shadow-sm lg:w-[260px]">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#64748b]">
            Surgical risk score
          </p>
          <div className="mt-3 flex items-end gap-1">
            <span className="text-5xl font-semibold text-[#111827]">{risk.score}</span>
            <span className="pb-2 text-lg font-medium text-[#64748b]">/{risk.max_score}</span>
          </div>
          <div className="mt-4 h-2 rounded-full bg-[#e9eaef]">
            <div
              className="h-2 rounded-full"
              style={{ width: `${Math.min(100, risk.score)}%`, backgroundColor: colors.border }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

export function PatientJourney() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });
  const riskQ = useQuery({
    queryKey: ["surgicalRisk", patientId],
    queryFn: () => api.getSurgicalRisk(patientId!),
    enabled: !!patientId,
  });
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
  const careQ = useQuery({
    queryKey: ["care-journey", patientId],
    queryFn: () => api.getCareJourney(patientId!),
    enabled: !!patientId,
  });

  if (!patientId) {
    return (
      <EmptyState
        icon={User}
        title="Choose a patient to begin"
        bullets={[
          "30-second surgical risk briefing",
          "Critical medications, comorbidities, labs, and anesthesia notes",
          "Separate from the detailed visual care timeline",
        ]}
        stat="1,180 patients available"
        iconBg="#eef1ff"
        iconColor="#5b76fe"
      />
    );
  }

  const isLoading =
    overviewQ.isLoading ||
    riskQ.isLoading ||
    safetyQ.isLoading ||
    conditionsQ.isLoading ||
    labsQ.isLoading ||
    careQ.isLoading;
  const isError =
    overviewQ.isError ||
    riskQ.isError ||
    safetyQ.isError ||
    conditionsQ.isError ||
    labsQ.isError ||
    careQ.isError;

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl space-y-5 p-8">
        <div className="h-64 animate-pulse rounded-3xl bg-[#e9eaef]" />
        <div className="grid gap-4 md:grid-cols-3">
          <div className="h-44 animate-pulse rounded-2xl bg-[#e9eaef]" />
          <div className="h-44 animate-pulse rounded-2xl bg-[#e9eaef]" />
          <div className="h-44 animate-pulse rounded-2xl bg-[#e9eaef]" />
        </div>
      </div>
    );
  }

  if (
    isError ||
    !overviewQ.data ||
    !riskQ.data ||
    !safetyQ.data ||
    !conditionsQ.data ||
    !labsQ.data ||
    !careQ.data
  ) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load patient journey briefing.</p>
      </div>
    );
  }

  const overview = overviewQ.data;
  const risk = riskQ.data;
  const safety = safetyQ.data;
  const conditions = conditionsQ.data;
  const labs = labsQ.data;
  const care = careQ.data;

  const meds = topMedicationAlerts(safety);
  const comorbidities = topComorbidities(conditions);
  const labFacts = keyLabFacts(labs);
  const anesthesia = anesthesiaNotes(risk, conditions);
  const careEvents = recentCareEvents(care);

  return (
    <main className="mx-auto max-w-6xl space-y-5 p-8">
      <section className="space-y-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#5b76fe]">Patient briefing</p>
          <h2 className="mt-1 text-2xl font-semibold text-[#111827]">{overview.name}</h2>
          <p className="mt-1 text-sm text-[#64748b]">
            Patient-specific pre-op disposition, evidence, and action items generated from this FHIR record.
          </p>
        </div>
        <RiskHero risk={risk} overview={overview} />
        <FactRail overview={overview} care={care} />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <BriefCard
          title="Critical Meds"
          items={meds}
          empty="No active medication hold alerts detected."
          tone={meds.length > 0 ? "red" : "green"}
          icon={Pill}
        />
        <BriefCard
          title="Key Comorbidities"
          items={comorbidities}
          empty="No high-priority active comorbidities detected."
          tone={comorbidities.length > 0 ? "amber" : "green"}
          icon={Activity}
        />
        <BriefCard
          title="Recent Labs"
          items={labFacts}
          empty="No recent lab alerts or preferred panel values available."
          tone={labs.alert_flags.length > 0 ? "amber" : "blue"}
          icon={TestTube2}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <BriefCard
          title="Anesthesia Notes"
          items={anesthesia}
          empty="No anesthesia-specific escalation notes detected."
          tone={anesthesia.length > 0 ? "amber" : "green"}
          icon={Stethoscope}
        />
        <BriefCard
          title="Recent Care Context"
          items={careEvents}
          empty="No dated encounters available in the care journey."
          tone="neutral"
          icon={CalendarClock}
        />
      </section>

      <section className="rounded-2xl border border-[#d8f3ec] bg-[#f3fffb] p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-[#087d75]">
              {risk.disposition === "HOLD" ? <AlertOctagon size={16} /> : <CheckCircle size={16} />}
              Curated briefing, not a full chart browser
            </div>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-[#3f635f]">
              This page pulls forward the few facts that should drive a fast surgical conversation.
              The detailed longitudinal chart remains available in Care Journey.
            </p>
          </div>
          <Link
            to={`/explorer/care-journey?patient=${patientId}`}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-[#95ded1] bg-white px-4 py-2 text-sm font-semibold text-[#087d75] hover:bg-[#e7fbf6]"
          >
            Open timeline
            <ArrowRight size={15} />
          </Link>
        </div>
      </section>
    </main>
  );
}
