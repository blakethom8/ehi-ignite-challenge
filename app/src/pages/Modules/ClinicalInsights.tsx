import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  ClipboardCheck,
  HeartHandshake,
  HeartPulse,
  MessageSquareText,
  Pill,
  Search,
  ShieldAlert,
  Stethoscope,
  TestTubeDiagonal,
  UserRoundCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${patientId}` : path;
}

type InsightStatus = "Live" | "Preview" | "Concept";

interface InsightModule {
  id: string;
  icon: LucideIcon;
  title: string;
  category: string;
  status: InsightStatus;
  route: string;
  body: string;
  fhir: string[];
  outputs: string[];
  readiness: string;
  recommended?: boolean;
}

const insightModules: InsightModule[] = [
  {
    id: "chart-qa",
    icon: MessageSquareText,
    title: "Chart Q&A",
    category: "Agent",
    status: "Live",
    route: "/explorer/assistant",
    body: "Ask record-grounded questions with source-linked answers, review flags, and scoped clinical context.",
    fhir: ["Conditions", "Medications", "Labs", "Encounters"],
    outputs: ["Cited answers", "Follow-up questions", "Evidence trail"],
    readiness: "Strong current fit",
    recommended: true,
  },
  {
    id: "preop",
    icon: Stethoscope,
    title: "Pre-Op Support",
    category: "Safety",
    status: "Live",
    route: "/preop",
    body: "Convert the patient chart into a surgical readiness brief for medication holds, anesthesia, and clearance review.",
    fhir: ["Meds", "Allergies", "Problems", "Recent care"],
    outputs: ["Briefing", "Medication holds", "Anesthesia handoff"],
    readiness: "Strong current fit",
    recommended: true,
  },
  {
    id: "med-safety",
    icon: Pill,
    title: "Medication Safety",
    category: "Safety",
    status: "Preview",
    route: "/explorer/safety",
    body: "Review active medication episodes, duplicates, high-risk classes, missing indications, and transition-of-care questions.",
    fhir: ["MedicationRequest", "Conditions", "Encounters"],
    outputs: ["Safety flags", "Reconciliation list", "Questions"],
    readiness: "Data-backed concept",
    recommended: true,
  },
  {
    id: "cardiometabolic",
    icon: HeartPulse,
    title: "Cardiometabolic Briefing",
    category: "Chronic care",
    status: "Concept",
    route: "/explorer",
    body: "Combine diabetes, blood pressure, lipids, kidney function, obesity, and medication adherence into one clinical brief.",
    fhir: ["A1c", "BP", "Lipids", "BMI", "Meds"],
    outputs: ["Control snapshot", "Care gaps", "Trend summary"],
    readiness: "Strong cohort support",
    recommended: true,
  },
  {
    id: "lab-explainer",
    icon: TestTubeDiagonal,
    title: "Lab Result Explainer",
    category: "Patient guidance",
    status: "Concept",
    route: "/explorer/history",
    body: "Turn abnormal lab flags into a plain-language explanation with trend context, severity, and what needs review.",
    fhir: ["Observations", "Reference ranges", "Trends"],
    outputs: ["Lab context", "Trend read", "Ask-your-doctor prompts"],
    readiness: "Strong data volume",
    recommended: true,
  },
  {
    id: "pregnancy",
    icon: HeartHandshake,
    title: "Pregnancy & Postpartum",
    category: "Life stage",
    status: "Concept",
    route: "/explorer/history",
    body: "Summarize prenatal history, pregnancy events, labs, blood pressure, medications, and postpartum risk windows.",
    fhir: ["Pregnancy encounters", "Vitals", "Labs", "Procedures"],
    outputs: ["Pregnancy timeline", "Warning-sign guide", "Follow-up needs"],
    readiness: "Cohort-supported concept",
  },
  {
    id: "kidney-safety",
    icon: ShieldAlert,
    title: "Kidney Medication Safety",
    category: "Safety",
    status: "Concept",
    route: "/explorer/history",
    body: "Use creatinine/eGFR, CKD problems, and medication context to flag renal dosing and nephrotoxin questions.",
    fhir: ["Creatinine", "eGFR", "CKD", "Meds"],
    outputs: ["Renal risk brief", "Dose-review prompts", "Sick-day questions"],
    readiness: "Targeted cohort support",
  },
  {
    id: "cancer-survivorship",
    icon: ClipboardCheck,
    title: "Cancer Survivorship",
    category: "Specialty",
    status: "Concept",
    route: "/explorer/care-journey",
    body: "Create a treatment-summary view for oncology history, procedures, medications, follow-up needs, and specialist handoff.",
    fhir: ["Cancer conditions", "Procedures", "Meds", "Providers"],
    outputs: ["Treatment summary", "Follow-up plan", "Questions"],
    readiness: "Moderate cohort support",
  },
  {
    id: "clinical-profile",
    icon: UserRoundCheck,
    title: "Clinical Profile",
    category: "Summary",
    status: "Preview",
    route: "/charts",
    body: "Create a patient-readable profile of active problems, care history, and the most important open questions.",
    fhir: ["Demographics", "Conditions", "Meds", "Timeline"],
    outputs: ["Plain-language profile", "Top concerns", "Question list"],
    readiness: "Strong current fit",
  },
  {
    id: "caregiver-view",
    icon: HeartHandshake,
    title: "Caregiver View",
    category: "Sharing",
    status: "Concept",
    route: "/sharing",
    body: "Create a limited, consent-scoped view for a trusted helper supporting the patient's care.",
    fhir: ["Summary", "Meds", "Care plan", "Questions"],
    outputs: ["Care summary", "Question guide", "Access boundary"],
    readiness: "Needs sharing controls",
  },
];

const defaultSelected = new Set(["chart-qa", "preop", "med-safety", "cardiometabolic", "lab-explainer"]);
const categories = ["All", ...Array.from(new Set(insightModules.map((module) => module.category)))];

function StatusBadge({ status }: { status: InsightStatus }) {
  const classes =
    status === "Live"
      ? "bg-[#e9f8ef] text-[#087443]"
      : status === "Preview"
        ? "bg-[#eef1ff] text-[#5b76fe]"
        : "bg-[#f5f6f8] text-[#667085]";

  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${classes}`}>{status}</span>;
}

function ModuleCard({
  module,
  patientId,
  selected,
  onToggle,
}: {
  module: InsightModule;
  patientId: string | null;
  selected: boolean;
  onToggle: (moduleId: string) => void;
}) {
  const Icon = module.icon;

  return (
    <article
      className={`flex min-h-[340px] flex-col rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px] ${
        selected ? "ring-2 ring-[#f4bd8d]" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#ffe6cd] text-[#744000]">
          <Icon size={20} />
        </div>
        <StatusBadge status={module.status} />
      </div>

      <div className="mt-5">
        <div className="flex items-center gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#9a5a16]">{module.category}</p>
          {module.recommended ? (
            <span className="rounded-full bg-[#fff1df] px-2 py-0.5 text-[10px] font-semibold text-[#9a5a16]">
              Recommended
            </span>
          ) : null}
        </div>
        <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">{module.title}</h2>
        <p className="mt-2 text-sm leading-6 text-[#667085]">{module.body}</p>
      </div>

      <div className="mt-5 grid gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">FHIR signals</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {module.fhir.map((signal) => (
              <span key={signal} className="rounded-full bg-[#f5f6f8] px-2 py-1 text-[11px] font-medium text-[#555a6a]">
                {signal}
              </span>
            ))}
          </div>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Produces</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {module.outputs.map((output) => (
              <span key={output} className="rounded-full bg-[#fff1df] px-2 py-1 text-[11px] font-semibold text-[#9a5a16]">
                {output}
              </span>
            ))}
          </div>
        </div>
      </div>

      <p className="mt-4 rounded-xl bg-[#fffaf4] px-3 py-2 text-xs font-semibold text-[#8a5a24]">{module.readiness}</p>

      <div className="mt-auto flex items-center justify-between gap-3 pt-5">
        <button
          type="button"
          onClick={() => onToggle(module.id)}
          className={`rounded-full px-3 py-2 text-sm font-semibold transition-colors ${
            selected ? "bg-[#1c1c1e] text-white" : "bg-[#fff1df] text-[#9a5a16] hover:bg-[#ffe6cd]"
          }`}
        >
          {selected ? "Shown on main page" : "Add to main page"}
        </button>
        <Link
          to={withPatient(module.route, patientId)}
          className="inline-flex items-center gap-1 text-sm font-semibold text-[#9a5a16] no-underline"
        >
          Open
          <ArrowRight size={14} />
        </Link>
      </div>
    </article>
  );
}

function SelectedShelf({
  modules,
  patientId,
}: {
  modules: InsightModule[];
  patientId: string | null;
}) {
  return (
    <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">Main page selection</p>
          <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">Modules shown in the patient workspace</h2>
        </div>
        <p className="max-w-xl text-sm leading-6 text-[#667085]">
          This shelf previews the patient-selected module set. In production this would persist to the patient profile or
          organization workspace.
        </p>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {modules.map((module) => {
          const Icon = module.icon;
          return (
            <Link
              key={module.id}
              to={withPatient(module.route, patientId)}
              className="rounded-xl border border-[#f2d8be] bg-[#fffaf4] p-4 no-underline transition-colors hover:bg-[#fff3e7]"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ffe6cd] text-[#744000]">
                  <Icon size={17} />
                </div>
                <StatusBadge status={module.status} />
              </div>
              <p className="mt-3 text-sm font-semibold text-[#1c1c1e]">{module.title}</p>
              <p className="mt-1 text-xs leading-5 text-[#667085]">{module.outputs[0]}</p>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

export function ClinicalInsights() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [selected, setSelected] = useState(defaultSelected);

  const filteredModules = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return insightModules.filter((module) => {
      const matchesCategory = category === "All" || module.category === category;
      const searchableText = [module.title, module.category, module.body, ...module.fhir, ...module.outputs].join(" ").toLowerCase();
      return matchesCategory && (!normalizedQuery || searchableText.includes(normalizedQuery));
    });
  }, [category, query]);

  const selectedModules = useMemo(() => insightModules.filter((module) => selected.has(module.id)), [selected]);

  function toggleModule(moduleId: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(moduleId)) {
        next.delete(moduleId);
      } else {
        next.add(moduleId);
      }
      return next;
    });
  }

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-4xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#fff1df] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">
              <Activity size={13} />
              Clinical module inventory
            </p>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
              Choose the clinical insights that belong on the main patient workspace
            </h1>
            <p className="mt-3 text-base leading-7 text-[#667085]">
              Clinical modules stay inside the PHI-controlled workspace. Each module declares the FHIR signals it uses,
              the output it creates, and whether it is live, preview-ready, or still a concept.
            </p>
          </div>
          <div className="rounded-2xl bg-[#fff8f1] p-4 shadow-[rgb(246_223_201)_0px_0px_0px_1px] lg:min-w-[280px]">
            <p className="text-sm font-semibold text-[#1c1c1e]">Inventory rule</p>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              We can show concepts here without faking outputs. A concept can explain the future workflow while only live
              modules open into working patient data.
            </p>
          </div>
        </div>
      </section>

      <SelectedShelf modules={selectedModules} patientId={patientId} />

      <section className="rounded-[24px] border border-[#f6dfc9] bg-[#fff8f1] p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">Search modules</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">Available clinical insight modules</h2>
          </div>
          <label className="flex min-w-[280px] items-center gap-2 rounded-xl bg-white px-3 py-2 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <Search size={16} className="text-[#a5a8b5]" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by condition, signal, or output"
              className="w-full bg-transparent text-sm text-[#1c1c1e] outline-none placeholder:text-[#a5a8b5]"
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {categories.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setCategory(item)}
              className={`rounded-full px-3 py-1.5 text-sm font-semibold transition-colors ${
                category === item ? "bg-[#1c1c1e] text-white" : "bg-white text-[#667085] hover:bg-[#fff1df] hover:text-[#9a5a16]"
              }`}
            >
              {item}
            </button>
          ))}
        </div>

        <div className="mt-5 flex flex-wrap gap-1.5">
          <span className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-[#667085]">
            {filteredModules.length} modules shown
          </span>
          <span className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-[#667085]">
            {selectedModules.length} selected for main page
          </span>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredModules.map((module) => (
            <ModuleCard
              key={module.id}
              module={module}
              patientId={patientId}
              selected={selected.has(module.id)}
              onToggle={toggleModule}
            />
          ))}
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {[
          [ShieldAlert, "Review boundary", "Marks inferred, partial, stale, conflicting, or high-risk findings before action."],
          [Stethoscope, "Clinician posture", "Clinical outputs should be brief, cited, and scoped to the workflow question."],
          [MessageSquareText, "Agent surface", "The split-screen agent belongs here first: chart evidence on the left, dialogue and next actions on the right."],
        ].map(([Icon, title, body]) => {
          const TypedIcon = Icon as LucideIcon;
          return (
            <div key={title as string} className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#fff1df] text-[#9a5a16]">
                <TypedIcon size={18} />
              </div>
              <h2 className="mt-4 text-base font-semibold text-[#1c1c1e]">{title as string}</h2>
              <p className="mt-2 text-sm leading-6 text-[#667085]">{body as string}</p>
            </div>
          );
        })}
      </section>
    </main>
  );
}
