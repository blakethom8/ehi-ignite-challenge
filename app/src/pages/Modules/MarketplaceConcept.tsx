import { Link, useLocation, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  ClipboardCheck,
  DollarSign,
  FileSearch,
  MessageSquareText,
  ShieldCheck,
  Store,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../../api/client";

type ConceptKey = "grants" | "research" | "payer";

interface ConceptConfig {
  key: ConceptKey;
  label: string;
  title: string;
  eyebrow: string;
  body: string;
  icon: LucideIcon;
  tone: string;
  usefulFor: string[];
  chartInputs: string[];
  futureSignals: string[];
  workflow: [string, string][];
  outputs: [string, string][];
  preview: {
    title: string;
    subtitle: string;
    lanes: [string, string][];
    cards: [string, string, string][];
  };
}

const CONCEPTS: Record<ConceptKey, ConceptConfig> = {
  grants: {
    key: "grants",
    label: "Grant Finder",
    title: "Find patient support programs from the chart context",
    eyebrow: "Financial support marketplace",
    body:
      "Grant Finder would turn diagnoses, therapies, and treatment burden into a support-program search packet. The current page is a product scaffold: it uses chart facts to define the search, but it does not claim real grant matches yet.",
    icon: DollarSign,
    tone: "bg-[#fff8f1] text-[#9a5a16]",
    usefulFor: ["High-cost diagnosis support", "Foundation grants", "Treatment-adjacent travel or copay help"],
    chartInputs: ["Active conditions", "Medication context", "Care timeline", "Procedure history"],
    futureSignals: ["Household/financial eligibility", "Insurance status", "Geography", "Program availability"],
    workflow: [
      ["Build eligibility packet", "Extract diagnoses, therapies, care recency, and evidence links from the FHIR Chart."],
      ["Search support categories", "Look for disease foundations, manufacturer support, nonprofit funds, and local assistance."],
      ["Prepare application path", "Return a checklist of required documents, forms, and questions for patient verification."],
    ],
    outputs: [
      ["Program shortlist", "Candidate programs with why they may fit and what still needs verification."],
      ["Document checklist", "Income, insurance, medication, diagnosis, and clinician attestation items."],
      ["Patient action plan", "Low-friction next steps the patient or advocate can complete."],
    ],
    preview: {
      title: "Future grant search workspace",
      subtitle: "A patient advocate can move from chart-backed eligibility signals to a support-program application checklist.",
      lanes: [
        ["Chart packet", "Conditions, active therapy, treatment recency"],
        ["Search queue", "Foundation, manufacturer, nonprofit, local support"],
        ["Application plan", "Required documents, patient questions, clinician attestation"],
      ],
      cards: [
        ["Eligibility signal", "Chart-backed", "Diagnosis and treatment context ready for external search."],
        ["Program result", "Future search", "Candidate grant cards will show source, fit rationale, and verification gaps."],
        ["Next step", "Patient review", "Collect financial and insurance fields only after explicit patient consent."],
      ],
    },
  },
  research: {
    key: "research",
    label: "Research Opportunities",
    title: "Turn the FHIR Chart into a research participation brief",
    eyebrow: "Registry and study discovery",
    body:
      "Research Opportunities is broader than trial matching. It can surface registries, observational studies, biobanks, patient communities, and condition-specific research programs from a structured patient packet.",
    icon: FileSearch,
    tone: "bg-[#eef1ff] text-[#5b76fe]",
    usefulFor: ["Rare or complex conditions", "Cancer registries", "Longitudinal observational programs"],
    chartInputs: ["Condition history", "Procedures", "Age", "Care recency"],
    futureSignals: ["Patient preferences", "Travel radius", "Contact permission", "Study registry search"],
    workflow: [
      ["Summarize research phenotype", "Create a patient-safe summary of relevant conditions, timeline, and care patterns."],
      ["Separate study types", "Distinguish interventional trials from registries, natural-history studies, and communities."],
      ["Package for discussion", "Produce clinician questions and patient-facing rationale before any outreach."],
    ],
    outputs: [
      ["Research map", "Opportunity categories with evidence-backed relevance."],
      ["Screening questions", "What to ask a study coordinator or clinician before sharing records."],
      ["Consent-ready packet", "A scoped packet that can be shared only after explicit patient approval."],
    ],
    preview: {
      title: "Future research discovery workspace",
      subtitle: "The patient can compare registries, studies, and research communities without losing the source evidence behind their match.",
      lanes: [
        ["Phenotype brief", "Conditions, procedures, timeline, age"],
        ["Opportunity map", "Registries, observational studies, communities"],
        ["Discussion packet", "Questions, fit rationale, consent boundary"],
      ],
      cards: [
        ["Research profile", "Chart-backed", "Longitudinal phenotype summary generated from available FHIR facts."],
        ["Opportunity card", "Future search", "Study and registry results will show inclusion terms, location, and source links."],
        ["Coordinator questions", "Patient review", "Questions to verify before sharing any identifiable record details."],
      ],
    },
  },
  payer: {
    key: "payer",
    label: "Payer Check",
    title: "Convert chart evidence into coverage and prior-auth readiness",
    eyebrow: "Payer impact workflow",
    body:
      "Payer Check focuses on reducing administrative friction. It can assemble diagnosis, medication, procedure, lab, and prior-care evidence into a coverage packet for benefits checks, prior authorization, or appeal preparation.",
    icon: ShieldCheck,
    tone: "bg-[#f4fffc] text-[#0f766e]",
    usefulFor: ["Prior authorization", "Step therapy evidence", "Medical-necessity packets"],
    chartInputs: ["Diagnoses", "Current meds", "Procedures", "Claims/EOB presence"],
    futureSignals: ["Plan benefits", "Coverage policy", "Formulary", "Patient insurance documents"],
    workflow: [
      ["Identify requested service", "Start from a medication, procedure, referral, imaging order, or durable equipment need."],
      ["Gather supporting evidence", "Attach chart facts that support medical necessity and prior treatment history."],
      ["Flag payer gaps", "Show missing plan/formulary details that the patient or clinician must provide."],
    ],
    outputs: [
      ["Coverage brief", "Why the request may be medically necessary, with cited chart evidence."],
      ["Prior-auth checklist", "Fields and attachments needed before submission."],
      ["Appeal starter", "If denied, draft the evidence inventory and missing-document list."],
    ],
    preview: {
      title: "Future payer readiness workspace",
      subtitle: "A patient or care team can assemble coverage evidence before a benefits check, prior auth, or appeal.",
      lanes: [
        ["Requested item", "Medication, imaging, procedure, referral, equipment"],
        ["Evidence packet", "Diagnoses, prior therapy, procedures, labs, claims"],
        ["Payer action", "Benefits check, prior auth, appeal starter"],
      ],
      cards: [
        ["Medical-necessity facts", "Chart-backed", "Diagnosis and treatment history pulled from the FHIR Chart."],
        ["Policy comparison", "Future payer data", "Coverage criteria and formulary checks will be attached with source dates."],
        ["Submission checklist", "Human review", "Missing plan, member, or policy fields stay flagged until confirmed."],
      ],
    },
  },
};

function conceptFromPath(pathname: string): ConceptConfig {
  if (pathname.startsWith("/grants")) return CONCEPTS.grants;
  if (pathname.startsWith("/research-opportunities")) return CONCEPTS.research;
  return CONCEPTS.payer;
}

function formatDate(value: string | null): string {
  if (!value) return "Unknown";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function InfoCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <h3 className="text-sm font-semibold text-[#1c1c1e]">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
    </div>
  );
}

function PillList({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">{title}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.map((item) => (
          <span key={item} className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function FutureWorkspacePreview({ concept }: { concept: ConceptConfig }) {
  return (
    <section className="rounded-3xl border border-[#dfe4ff] bg-[#f7f8ff] p-5 lg:p-6">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Illustrative future state</p>
          <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">{concept.preview.title}</h2>
        </div>
        <p className="max-w-2xl text-sm leading-6 text-[#667085]">{concept.preview.subtitle}</p>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <div className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Workspace flow</p>
          <div className="mt-4 space-y-3">
            {concept.preview.lanes.map(([label, body], index) => (
              <div key={label} className="flex gap-3">
                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-xs font-semibold ${concept.tone}`}>
                  {index + 1}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[#1c1c1e]">{label}</p>
                  <p className="mt-1 text-sm leading-6 text-[#667085]">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {concept.preview.cards.map(([title, status, body]) => (
            <div key={title} className="flex min-h-[210px] flex-col rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold text-[#1c1c1e]">{title}</p>
                <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold ${status === "Chart-backed" ? "bg-[#f4fffc] text-[#0f766e]" : "bg-[#f5f6f8] text-[#555a6a]"}`}>
                  {status}
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-[#667085]">{body}</p>
              <div className="mt-auto pt-4">
                <div className="h-2 rounded-full bg-[#edf0f7]" />
                <div className="mt-2 h-2 w-2/3 rounded-full bg-[#edf0f7]" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function MarketplaceConcept() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const patientId = searchParams.get("patient");
  const concept = conceptFromPath(location.pathname);
  const ConceptIcon = concept.icon;

  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });

  const overview = overviewQ.data;
  const topConditions = (overview?.conditions ?? []).filter((condition) => condition.is_active).slice(0, 5);
  const topMeds = (overview?.medications ?? []).filter((med) => med.is_active).slice(0, 5);

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider ${concept.tone}`}>
              <ConceptIcon size={13} />
              {concept.eyebrow}
            </p>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
              {concept.title}
            </h1>
            <p className="mt-3 text-base leading-7 text-[#667085]">{concept.body}</p>
          </div>
          <div className="rounded-2xl bg-[#fafbff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:min-w-[280px]">
            <div className="flex items-center gap-2">
              <Store size={18} className="text-[#5b76fe]" />
              <p className="text-sm font-semibold text-[#1c1c1e]">Marketplace posture</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              This is a concept workspace. It can organize real chart facts now; external search, submissions, and data sharing need explicit consent and future backend work.
            </p>
          </div>
        </div>
      </section>

      {!patientId && (
        <section className="rounded-2xl border border-dashed border-[#c7cad5] bg-white p-5">
          <div className="flex items-center gap-2">
            <UserRound size={18} className="text-[#a5a8b5]" />
            <p className="text-sm font-semibold text-[#1c1c1e]">Select a patient to make this module patient-specific.</p>
          </div>
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <PillList title="Useful for" items={concept.usefulFor} tone={concept.tone} />
        <PillList title="Chart inputs" items={concept.chartInputs} tone="bg-[#eef1ff] text-[#5b76fe]" />
        <PillList title="Future external signals" items={concept.futureSignals} tone="bg-[#f5f6f8] text-[#555a6a]" />
      </div>

      <FutureWorkspacePreview concept={concept} />

      <section className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-[#1c1c1e]">Patient Signal Packet</h2>
              <p className="mt-1 text-sm text-[#667085]">
                Real chart facts that can seed the module before external search or sharing.
              </p>
            </div>
            <Link
              to={patientId ? `/explorer?patient=${patientId}` : "/records-pool"}
              className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-semibold text-[#5b76fe] hover:bg-[#eef1ff]"
            >
              FHIR Chart
              <ArrowRight size={14} />
            </Link>
          </div>

          {overviewQ.isLoading ? (
            <div className="mt-5 space-y-3">
              <div className="h-16 animate-pulse rounded-xl bg-[#e9eaef]" />
              <div className="h-16 animate-pulse rounded-xl bg-[#e9eaef]" />
              <div className="h-16 animate-pulse rounded-xl bg-[#e9eaef]" />
            </div>
          ) : overview ? (
            <div className="mt-5 grid gap-3">
              <InfoCard
                title={overview.name}
                body={`${Math.floor(overview.age_years)} years · ${overview.gender} · ${overview.active_condition_count} active conditions · ${overview.active_med_count} active medications · latest activity ${formatDate(overview.latest_encounter_dt)}.`}
              />
              <InfoCard
                title="Active condition anchors"
                body={topConditions.length > 0 ? topConditions.map((condition) => condition.display).join("; ") : "No active conditions available in the chart."}
              />
              <InfoCard
                title="Active medication anchors"
                body={topMeds.length > 0 ? topMeds.map((med) => med.display).join("; ") : "No active medications available in the chart."}
              />
            </div>
          ) : (
            <div className="mt-5 rounded-xl border border-dashed border-[#d5d9e5] p-5 text-sm leading-6 text-[#667085]">
              Patient-specific chart facts appear here after a patient is selected.
            </div>
          )}
        </div>

        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <ClipboardCheck size={18} className="text-[#5b76fe]" />
            <h2 className="text-lg font-semibold text-[#1c1c1e]">Prototype workflow</h2>
          </div>
          <div className="mt-5 space-y-4">
            {concept.workflow.map(([label, body], index) => (
              <div key={label} className="flex gap-3">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#eef1ff] text-xs font-semibold text-[#5b76fe]">
                  {index + 1}
                </div>
                <div>
                  <p className="text-sm font-semibold text-[#1c1c1e]">{label}</p>
                  <p className="mt-1 text-sm leading-6 text-[#667085]">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {concept.outputs.map(([title, body]) => (
          <InfoCard key={title} title={title} body={body} />
        ))}
      </section>

      <section className="rounded-2xl bg-[#f7fffc] p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <MessageSquareText size={18} className="text-[#0f766e]" />
          <h2 className="text-lg font-semibold text-[#0f172a]">Design principle</h2>
        </div>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-[#35524d]">
          Marketplace modules should feel like structured opportunity workspaces, not generic ads. The patient controls which facts leave
          the private record layer, and every output should carry evidence, missing-data warnings, and a clear review boundary.
        </p>
      </section>
    </main>
  );
}
