import { useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  BookMarked,
  ClipboardCheck,
  Clock3,
  Eye,
  FileText,
  GitBranch,
  HeartHandshake,
  HeartPulse,
  Layers3,
  LayoutGrid,
  MessageSquareText,
  Pill,
  Plus,
  Search,
  ShieldAlert,
  Star,
  Stethoscope,
  Table2,
  TestTubeDiagonal,
  UserRoundCheck,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${patientId}` : path;
}

type InsightStatus = "Live" | "Preview" | "Concept";
type InventoryViewMode = "cards" | "table";

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

function ViewModeToggle({
  viewMode,
  onChange,
}: {
  viewMode: InventoryViewMode;
  onChange: (mode: InventoryViewMode) => void;
}) {
  return (
    <div className="inline-flex rounded-xl bg-white p-1 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      {[
        { mode: "cards" as const, label: "Cards", icon: LayoutGrid },
        { mode: "table" as const, label: "Table", icon: Table2 },
      ].map(({ mode, label, icon: Icon }) => (
        <button
          key={mode}
          type="button"
          onClick={() => onChange(mode)}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
            viewMode === mode ? "bg-[#1c1c1e] text-white" : "text-[#667085] hover:bg-[#fff1df] hover:text-[#9a5a16]"
          }`}
          aria-pressed={viewMode === mode}
        >
          <Icon size={14} />
          {label}
        </button>
      ))}
    </div>
  );
}

function ModuleTable({
  modules,
  patientId,
  selected,
  onToggle,
}: {
  modules: InsightModule[];
  patientId: string | null;
  selected: Set<string>;
  onToggle: (moduleId: string) => void;
}) {
  return (
    <div className="mt-5 overflow-x-auto rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <table className="w-full min-w-[1040px] border-collapse text-[12px]">
        <thead>
          <tr className="bg-[#fafafa] text-left text-[10px] font-semibold uppercase tracking-wider text-[#8d92a3]">
            <th className="border-b border-[#eef0f5] px-3 py-2">Module</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Status</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Category</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">FHIR signals</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Outputs</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Readiness</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Shown</th>
            <th className="border-b border-[#eef0f5] px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {modules.map((module) => {
            const isSelected = selected.has(module.id);
            return (
              <tr key={module.id} className="hover:bg-[#fffdf9]">
                <td className="border-b border-[#f2f4f8] px-3 py-2">
                  <Link to={withPatient(module.route, patientId)} className="font-semibold text-[#1c1c1e] no-underline hover:text-[#9a5a16]">
                    {module.title}
                  </Link>
                  {module.recommended ? <span className="ml-2 text-[10px] font-semibold uppercase text-[#9a5a16]">Recommended</span> : null}
                </td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#555a6a]">{module.status}</td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#555a6a]">{module.category}</td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#555a6a]">{module.fhir.join(", ")}</td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#555a6a]">{module.outputs.join(", ")}</td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#8a5a24]">{module.readiness}</td>
                <td className="border-b border-[#f2f4f8] px-3 py-2">
                  <button
                    type="button"
                    onClick={() => onToggle(module.id)}
                    className={`rounded-md px-2 py-1 text-[11px] font-semibold transition-colors ${
                      isSelected ? "bg-[#1c1c1e] text-white" : "bg-white text-[#9a5a16] shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#fff1df]"
                    }`}
                  >
                    {isSelected ? "Yes" : "Add"}
                  </button>
                </td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-right">
                  <Link to={withPatient(module.route, patientId)} className="font-semibold text-[#9a5a16] no-underline">Open</Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface ContextVersion {
  version: string;
  date: string;
  note: string;
  author: string;
}

interface ContextPackage {
  id: string;
  title: string;
  type: string;
  usedBy: string;
  status: "Draft" | "Published" | "Review";
  version: string;
  updated: string;
  markdown: string;
  versions: ContextVersion[];
}

interface PublishedContextPackage {
  title: string;
  type: string;
  author: string;
  version: string;
  updated: string;
  summary: string;
  installs: string;
  review: string;
}

const initialContextPackages: ContextPackage[] = [
  {
    id: "preop-medication-holds",
    title: "Pre-op Medication Holds",
    type: "Medication safety",
    usedBy: "Chart Q&A, Pre-Op Support",
    status: "Draft",
    version: "v0.3",
    updated: "Today",
    markdown:
      "# Pre-op Medication Holds\n\n**Use when:** a clinician asks about surgical readiness, bleeding risk, or day-of-procedure medication planning.\n\n## Review checklist\n\n- Separate active medications from historical medications.\n- Look specifically for antiplatelets, anticoagulants, NSAIDs, diabetes medications, supplements, and steroids.\n- State whether the chart contains the last dose, procedure date, renal function, and prescribing indication.\n- If a hold window depends on procedure type, say what must be verified.\n\n## Answer style\n\nStart with the direct safety answer. Then use bullets for evidence, uncertainty, and next actions.",
    versions: [
      { version: "v0.3", date: "Today", note: "Added last-dose and procedure-date checks.", author: "Blake" },
      { version: "v0.2", date: "May 1", note: "Separated active versus historical medication language.", author: "Blake" },
      { version: "v0.1", date: "Apr 29", note: "Initial perioperative medication prompt.", author: "Blake" },
    ],
  },
  {
    id: "cardiometabolic-review",
    title: "Cardiometabolic Review",
    type: "Disease-specific review",
    usedBy: "Chart Q&A, future chronic care module",
    status: "Draft",
    version: "v0.2",
    updated: "Yesterday",
    markdown:
      "# Cardiometabolic Review\n\nReview diabetes, blood pressure, lipids, kidney function, weight, and active therapy together.\n\n## Required evidence\n\n- Most recent A1c, blood pressure, lipid panel, BMI, creatinine/eGFR, and medication list.\n- Recent therapy starts, stops, or dose changes.\n- Missing labs or unclear medication adherence.\n\n## Boundary\n\nDo not imply longitudinal control when the record only contains sparse observations.",
    versions: [
      { version: "v0.2", date: "Yesterday", note: "Added sparse-observation boundary.", author: "Blake" },
      { version: "v0.1", date: "Apr 30", note: "Initial cardiometabolic review structure.", author: "Blake" },
    ],
  },
  {
    id: "patient-context-intake",
    title: "Patient Context Intake",
    type: "Qualitative context",
    usedBy: "Patient Context, Chart Q&A",
    status: "Draft",
    version: "v0.1",
    updated: "May 1",
    markdown:
      "# Patient Context Intake\n\nUse when chart evidence is incomplete and patient-reported context would help.\n\n## Ask about\n\n- Current symptoms and functional limitations.\n- Medication reality: what the patient actually takes, stopped, or cannot access.\n- Recent outside care, portals, PDFs, labs, and device exports.\n- Goals, preferences, concerns, and questions for the clinician.\n\nLabel all answers as patient-reported until reviewed.",
    versions: [{ version: "v0.1", date: "May 1", note: "Initial patient context package.", author: "Blake" }],
  },
  {
    id: "local-clinical-style-guide",
    title: "Local Clinical Style Guide",
    type: "Organization rules",
    usedBy: "All LLM Review sessions",
    status: "Draft",
    version: "v0.4",
    updated: "Today",
    markdown:
      "# Local Clinical Style Guide\n\nUse a concise clinical review style.\n\n## Format\n\n- Start with the direct answer.\n- Use bullets for evidence, uncertainties, and next actions.\n- Use bold only for the most important finding or action.\n- Avoid broad disclaimers unless there is a specific safety boundary.\n\n## Escalation language\n\nSay what should be verified and why it matters clinically.",
    versions: [
      { version: "v0.4", date: "Today", note: "Tightened answer format and bolding rules.", author: "Blake" },
      { version: "v0.3", date: "May 1", note: "Added escalation language.", author: "Blake" },
      { version: "v0.2", date: "Apr 28", note: "Added citation expectations.", author: "Blake" },
    ],
  },
];

const publishedContextPackages: PublishedContextPackage[] = [
  {
    title: "Perioperative medication holds",
    type: "Safety",
    author: "EHI clinical team",
    version: "v1.2",
    updated: "Apr 30",
    summary: "Antiplatelets, anticoagulants, diabetes medications, and NSAID hold logic.",
    installs: "128",
    review: "Clinician reviewed",
  },
  {
    title: "Diabetes review script",
    type: "Disease review",
    author: "Community",
    version: "v0.9",
    updated: "Apr 28",
    summary: "A1c trend, kidney function, therapy history, monitoring gaps, and follow-up questions.",
    installs: "84",
    review: "Preview",
  },
  {
    title: "CKD medication safety",
    type: "Medication policy",
    author: "Nephrology workspace",
    version: "v0.7",
    updated: "Apr 25",
    summary: "Renal dosing, nephrotoxins, sick-day rules, and monitoring gaps.",
    installs: "56",
    review: "Preview",
  },
  {
    title: "Specialist referral brief",
    type: "Workflow",
    author: "Referral ops",
    version: "v0.5",
    updated: "Apr 21",
    summary: "Focused referral and second-opinion packet context with evidence requirements.",
    installs: "41",
    review: "Draft shared",
  },
  {
    title: "Patient-friendly lab explanation",
    type: "Patient communication",
    author: "Patient guidance group",
    version: "v0.4",
    updated: "Apr 19",
    summary: "Plain-language lab explanation, trend framing, and clinician question prompts.",
    installs: "37",
    review: "Preview",
  },
];

function ClinicalInsightsInfoPage({
  eyebrow,
  title,
  body,
  cards,
}: {
  eyebrow: string;
  title: string;
  body: string;
  cards: Array<{ icon: LucideIcon; title: string; body: string }>;
}) {
  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-7">
        <p className="inline-flex items-center gap-2 rounded-full bg-[#fff1df] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">
          <Activity size={13} />
          {eyebrow}
        </p>
        <h1 className="mt-4 max-w-4xl text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">{title}</h1>
        <p className="mt-3 max-w-4xl text-base leading-7 text-[#667085]">{body}</p>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {cards.map(({ icon: Icon, title: cardTitle, body: cardBody }) => (
          <article key={cardTitle} className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#fff1df] text-[#9a5a16]">
              <Icon size={18} />
            </div>
            <h2 className="mt-4 text-base font-semibold text-[#1c1c1e]">{cardTitle}</h2>
            <p className="mt-2 text-sm leading-6 text-[#667085]">{cardBody}</p>
          </article>
        ))}
      </section>
    </main>
  );
}

function ClinicalInsightsContextLibraryPage() {
  const [packages, setPackages] = useState(initialContextPackages);
  const [selectedPackageId, setSelectedPackageId] = useState(initialContextPackages[0]?.id ?? "");
  const [draftMarkdown, setDraftMarkdown] = useState(initialContextPackages[0]?.markdown ?? "");
  const [editorOpen, setEditorOpen] = useState(false);
  const [publishedQuery, setPublishedQuery] = useState("");

  const selectedPackage = packages.find((contextPackage) => contextPackage.id === selectedPackageId) ?? packages[0];
  const filteredPublishedPackages = publishedContextPackages.filter((contextPackage) => {
    const query = publishedQuery.trim().toLowerCase();
    if (!query) return true;
    return [
      contextPackage.title,
      contextPackage.type,
      contextPackage.author,
      contextPackage.summary,
      contextPackage.review,
    ].join(" ").toLowerCase().includes(query);
  });

  function selectPackage(contextPackage: ContextPackage) {
    setSelectedPackageId(contextPackage.id);
    setDraftMarkdown(contextPackage.markdown);
    setEditorOpen(true);
  }

  function saveVersion() {
    if (!selectedPackage) return;
    setPackages((current) =>
      current.map((contextPackage) => {
        if (contextPackage.id !== selectedPackage.id) return contextPackage;
        const latestMinor = Math.max(
          0,
          ...contextPackage.versions.map((version) => Number(version.version.replace(/^v0\./, ""))).filter(Number.isFinite),
        );
        const nextVersion = `v0.${latestMinor + 1}`;
        return {
          ...contextPackage,
          markdown: draftMarkdown,
          version: nextVersion,
          updated: "Just now",
          status: "Draft",
          versions: [
            {
              version: nextVersion,
              date: "Just now",
              note: "Saved Markdown edits as a new draft version.",
              author: "Blake",
            },
            ...contextPackage.versions,
          ],
        };
      }),
    );
  }

  function createPackage() {
    const nextPackage: ContextPackage = {
      id: `new-context-package-${packages.length + 1}`,
      title: "Untitled Context Package",
      type: "Draft package",
      usedBy: "Not attached yet",
      status: "Draft",
      version: "v0.1",
      updated: "Just now",
      markdown:
        "# Untitled Context Package\n\nDescribe when this package should be used.\n\n## Instructions\n\n- Add the review rules or clinical workflow guidance.\n- Describe required evidence.\n- State boundaries and escalation rules.",
      versions: [{ version: "v0.1", date: "Just now", note: "Created new draft package.", author: "Blake" }],
    };
    setPackages((current) => [nextPackage, ...current]);
    setSelectedPackageId(nextPackage.id);
    setDraftMarkdown(nextPackage.markdown);
    setEditorOpen(true);
  }

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full bg-[#fff1df] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">
              <Layers3 size={13} />
              Context management
            </p>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-[#1c1c1e] lg:text-3xl">Context Library</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-[#667085]">
              Create, edit, version, and reuse Markdown context packages that guide LLM Review and clinical modules.
            </p>
          </div>
          <button
            type="button"
            onClick={createPackage}
            className="inline-flex w-fit items-center gap-2 rounded-xl bg-[#1c1c1e] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#333438]"
          >
            <Plus size={16} />
            New package
          </button>
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex flex-col gap-2 border-b border-[#eef0f5] px-5 py-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">My packages</p>
            <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">Saved context sets</h2>
          </div>
          <a href="#published-packages" className="text-sm font-semibold text-[#9a5a16] no-underline">
            Review published packages
          </a>
        </div>
        <table className="w-full min-w-[760px] border-collapse text-sm">
          <thead>
            <tr className="bg-[#fafafa] text-left text-[10px] font-semibold uppercase tracking-wider text-[#8d92a3]">
              <th className="border-b border-[#eef0f5] px-4 py-3">Package</th>
              <th className="border-b border-[#eef0f5] px-4 py-3">Type</th>
              <th className="border-b border-[#eef0f5] px-4 py-3">Used by</th>
              <th className="border-b border-[#eef0f5] px-4 py-3">Version</th>
              <th className="border-b border-[#eef0f5] px-4 py-3">Updated</th>
              <th className="border-b border-[#eef0f5] px-4 py-3">Status</th>
              <th className="border-b border-[#eef0f5] px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {packages.map((contextPackage) => (
              <tr
                key={contextPackage.id}
                className={`hover:bg-[#fffdf9] ${selectedPackage?.id === contextPackage.id ? "bg-[#fffaf4]" : ""}`}
              >
                <td className="border-b border-[#f2f4f8] px-4 py-3 font-semibold text-[#1c1c1e]">{contextPackage.title}</td>
                <td className="border-b border-[#f2f4f8] px-4 py-3 text-[#667085]">{contextPackage.type}</td>
                <td className="border-b border-[#f2f4f8] px-4 py-3 text-[#667085]">{contextPackage.usedBy}</td>
                <td className="border-b border-[#f2f4f8] px-4 py-3 text-[#667085]">{contextPackage.version}</td>
                <td className="border-b border-[#f2f4f8] px-4 py-3 text-[#667085]">{contextPackage.updated}</td>
                <td className="border-b border-[#f2f4f8] px-4 py-3 text-[#9a5a16]">{contextPackage.status}</td>
                <td className="border-b border-[#f2f4f8] px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => selectPackage(contextPackage)}
                    className="inline-flex items-center gap-1 rounded-lg bg-white px-2.5 py-1.5 text-xs font-semibold text-[#9a5a16] shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#fff1df]"
                  >
                    <FileText size={13} />
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {editorOpen && selectedPackage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4"
          onClick={() => setEditorOpen(false)}
        >
          <section
            className="grid h-[86vh] w-full max-w-7xl overflow-hidden rounded-2xl bg-white shadow-2xl xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.55fr)]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex min-h-0 flex-col">
              <div className="flex flex-col gap-3 border-b border-[#eef0f5] px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">Markdown editor</p>
                  <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">{selectedPackage.title}</h2>
                  <p className="mt-1 text-sm text-[#667085]">{selectedPackage.type} · {selectedPackage.version}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-2 text-xs font-semibold text-[#667085] shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#fafafa]"
                  >
                    <Eye size={14} />
                    Preview in chat
                  </button>
                  <button
                    type="button"
                    onClick={saveVersion}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-[#9a5a16] px-3 py-2 text-xs font-semibold text-white hover:bg-[#744000]"
                  >
                    <GitBranch size={14} />
                    Save new version
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditorOpen(false)}
                    className="rounded-lg p-2 text-[#667085] hover:bg-[#f5f6f8] hover:text-[#1c1c1e]"
                    title="Close editor"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>

              <div className="grid min-h-0 flex-1 lg:grid-cols-2">
                <div className="flex min-h-0 flex-col border-b border-[#eef0f5] lg:border-b-0 lg:border-r">
                  <div className="shrink-0 border-b border-[#eef0f5] px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-[#8d92a3]">
                    Markdown
                  </div>
                  <textarea
                    value={draftMarkdown}
                    onChange={(event) => setDraftMarkdown(event.target.value)}
                    className="min-h-0 flex-1 resize-none bg-white p-4 font-mono text-[12px] leading-6 text-[#1c1c1e] outline-none"
                    spellCheck={false}
                  />
                </div>
                <div className="flex min-h-0 flex-col">
                  <div className="shrink-0 border-b border-[#eef0f5] px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-[#8d92a3]">
                    Preview
                  </div>
                  <div className="min-h-0 flex-1 overflow-y-auto p-4 text-sm leading-6 text-[#555a6a]">
                    {draftMarkdown.split("\n").map((line, index) => {
                      if (line.startsWith("# ")) {
                        return <h1 key={index} className="mb-3 text-xl font-semibold text-[#1c1c1e]">{line.replace("# ", "")}</h1>;
                      }
                      if (line.startsWith("## ")) {
                        return <h2 key={index} className="mb-2 mt-4 text-sm font-semibold uppercase tracking-wider text-[#9a5a16]">{line.replace("## ", "")}</h2>;
                      }
                      if (line.startsWith("- ")) {
                        return <p key={index} className="ml-4 list-item text-[#667085]">{line.replace("- ", "")}</p>;
                      }
                      if (!line.trim()) return <div key={index} className="h-2" />;
                      return <p key={index} className="mb-2">{line.replace(/\*\*/g, "")}</p>;
                    })}
                  </div>
                </div>
              </div>
            </div>

            <aside className="min-h-0 overflow-y-auto border-t border-[#eef0f5] bg-[#fbfcff] p-5 xl:border-l xl:border-t-0">
              <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">
                <Clock3 size={14} />
                Version history
              </p>
              <div className="mt-4 space-y-3">
                {selectedPackage.versions.map((version) => (
                  <div key={`${version.version}-${version.date}`} className="rounded-xl border border-[#eef0f5] bg-white p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-[#1c1c1e]">{version.version}</p>
                      <span className="text-xs text-[#8d92a3]">{version.date}</span>
                    </div>
                    <p className="mt-2 text-sm leading-5 text-[#667085]">{version.note}</p>
                    <p className="mt-2 text-[11px] font-semibold uppercase tracking-wider text-[#a5a8b5]">{version.author}</p>
                  </div>
                ))}
              </div>
            </aside>
          </section>
        </div>
      )}

      <section id="published-packages" className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">Published packages</p>
            <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">Review packages published by others</h2>
          </div>
          <label className="flex min-w-[280px] items-center gap-2 rounded-xl bg-[#fafafa] px-3 py-2 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <Search size={16} className="text-[#a5a8b5]" />
            <input
              value={publishedQuery}
              onChange={(event) => setPublishedQuery(event.target.value)}
              placeholder="Search guidelines, disease reviews, or scripts"
              className="w-full bg-transparent text-sm text-[#1c1c1e] outline-none placeholder:text-[#a5a8b5]"
            />
          </label>
        </div>
        <div className="mt-4 overflow-x-auto rounded-xl shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <table className="w-full min-w-[1040px] border-collapse bg-white text-sm">
            <thead>
              <tr className="bg-[#fafafa] text-left text-[10px] font-semibold uppercase tracking-wider text-[#8d92a3]">
                <th className="border-b border-[#eef0f5] px-3 py-2">Package</th>
                <th className="border-b border-[#eef0f5] px-3 py-2">Type</th>
                <th className="border-b border-[#eef0f5] px-3 py-2">Author</th>
                <th className="border-b border-[#eef0f5] px-3 py-2">Version</th>
                <th className="border-b border-[#eef0f5] px-3 py-2">Summary</th>
                <th className="border-b border-[#eef0f5] px-3 py-2">Review</th>
                <th className="border-b border-[#eef0f5] px-3 py-2">Installs</th>
                <th className="border-b border-[#eef0f5] px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {filteredPublishedPackages.map((contextPackage) => (
                <tr key={contextPackage.title} className="hover:bg-[#fffdf9]">
                  <td className="border-b border-[#f2f4f8] px-3 py-2 font-semibold text-[#1c1c1e]">{contextPackage.title}</td>
                  <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#667085]">{contextPackage.type}</td>
                  <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#667085]">{contextPackage.author}</td>
                  <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#667085]">{contextPackage.version}</td>
                  <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#667085]">{contextPackage.summary}</td>
                  <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#9a5a16]">{contextPackage.review}</td>
                  <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#667085]">{contextPackage.installs}</td>
                  <td className="border-b border-[#f2f4f8] px-3 py-2 text-right">
                    <button
                      type="button"
                      className="rounded-lg bg-[#fff1df] px-2.5 py-1.5 text-xs font-semibold text-[#9a5a16] hover:bg-[#ffe6cd]"
                    >
                      Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function ClinicalInsightsFavoritesPage({
  modules,
  patientId,
}: {
  modules: InsightModule[];
  patientId: string | null;
}) {
  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-7">
        <p className="inline-flex items-center gap-2 rounded-full bg-[#fff1df] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">
          <Star size={13} />
          Clinical modules
        </p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">Favorites</h1>
        <p className="mt-3 max-w-4xl text-base leading-7 text-[#667085]">
          Favorite modules are the prepared reviews, dashboards, and workflows that should stay close to this clinical workspace.
        </p>
      </section>

      <ModuleTable modules={modules} patientId={patientId} selected={new Set(modules.map((module) => module.id))} onToggle={() => undefined} />
    </main>
  );
}

export function ClinicalInsights() {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [selected, setSelected] = useState(defaultSelected);
  const [viewMode, setViewMode] = useState<InventoryViewMode>("table");

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

  if (location.pathname.endsWith("/packages") || location.pathname.endsWith("/context-library")) {
    return <ClinicalInsightsContextLibraryPage />;
  }

  if (location.pathname.endsWith("/favorites")) {
    return <ClinicalInsightsFavoritesPage modules={selectedModules} patientId={patientId} />;
  }

  if (location.pathname.endsWith("/create")) {
    return (
      <ClinicalInsightsInfoPage
        eyebrow="Clinical modules"
        title="Create a Module"
        body="Start a reusable clinical workflow that can combine patient data, context packages, output templates, and review rules."
        cards={[
          {
            icon: ClipboardCheck,
            title: "Start from a review workflow",
            body: "Create a structured module such as a surgical readiness brief, medication reconciliation review, or disease dashboard.",
          },
          {
            icon: BookMarked,
            title: "Start from context",
            body: "Turn a guideline, policy, or clinician preference document into reusable instructions for LLM Review.",
          },
          {
            icon: MessageSquareText,
            title: "Define agent behavior",
            body: "Specify what the agent can answer, what it should cite, and when it should ask the clinician for clarification.",
          },
          {
            icon: Activity,
            title: "Connect outputs",
            body: "Choose whether the module produces a brief, table, dashboard, packet, or clinician-facing task list.",
          },
        ]}
      />
    );
  }

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#fff1df] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">
              <Activity size={13} />
              Clinical module inventory
            </p>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-[#1c1c1e] lg:text-3xl">
              Explore clinical insight modules
            </h1>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              Browse prepared reviews, dashboards, and workflows. Each module declares its FHIR signals, outputs, and readiness.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs font-semibold text-[#667085]">
            <span className="rounded-full bg-[#fff8f1] px-3 py-1.5 text-[#9a5a16]">Live modules open into patient data</span>
            <span className="rounded-full bg-[#f5f6f8] px-3 py-1.5">Concepts show future workflow only</span>
          </div>
        </div>
      </section>

      <section className="rounded-[24px] border border-[#f6dfc9] bg-[#fff8f1] p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">Search modules</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">Available clinical insight modules</h2>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <label className="flex min-w-[280px] items-center gap-2 rounded-xl bg-white px-3 py-2 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
              <Search size={16} className="text-[#a5a8b5]" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by condition, signal, or output"
                className="w-full bg-transparent text-sm text-[#1c1c1e] outline-none placeholder:text-[#a5a8b5]"
              />
            </label>
            <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />
          </div>
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
            {selectedModules.length} favorites selected
          </span>
        </div>

        {viewMode === "cards" ? (
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
        ) : (
          <ModuleTable modules={filteredModules} patientId={patientId} selected={selected} onToggle={toggleModule} />
        )}
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
