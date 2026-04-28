import { Link, useSearchParams } from "react-router-dom";
import type { ReactNode } from "react";
import {
  ArrowRight,
  ClipboardCheck,
  DollarSign,
  FileSearch,
  Pill,
  Search,
  ShieldCheck,
  Store,
  TestTubeDiagonal,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${patientId}` : path;
}

type Tone = "blue" | "green" | "orange" | "rose";

interface ModuleCardProps {
  icon: LucideIcon;
  title: string;
  status: string;
  audience: string;
  inputs: string[];
  outputs: string[];
  body: string;
  to: string;
  tone?: Tone;
  action?: string;
}

const toneClasses: Record<Tone, string> = {
  blue: "bg-[#eef1ff] text-[#5b76fe]",
  green: "bg-[#c3faf5] text-[#187574]",
  orange: "bg-[#ffe6cd] text-[#744000]",
  rose: "bg-[#ffd8f4] text-[#7a285f]",
};

function ModuleCard({
  icon: Icon,
  title,
  status,
  audience,
  inputs,
  outputs,
  body,
  to,
  tone = "blue",
  action = "Open module",
}: ModuleCardProps) {
  return (
    <Link
      to={to}
      className="group flex min-h-[320px] flex-col rounded-2xl bg-white p-5 no-underline shadow-[rgb(224_226_232)_0px_0px_0px_1px] transition-colors hover:bg-[#fbfcff]"
    >
      <div className="flex items-start justify-between gap-4">
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${toneClasses[tone]}`}>
          <Icon size={20} />
        </div>
        <span className="rounded-full bg-[#f5f6f8] px-2.5 py-1 text-xs font-semibold text-[#667085]">{status}</span>
      </div>

      <div className="mt-5">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">{audience}</p>
        <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
      </div>

      <div className="mt-5 grid gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Requires</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {inputs.map((input) => (
              <span key={input} className="rounded-full bg-[#f5f6f8] px-2 py-1 text-[11px] font-medium text-[#555a6a]">
                {input}
              </span>
            ))}
          </div>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Produces</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {outputs.map((output) => (
              <span key={output} className="rounded-full bg-[#eef1ff] px-2 py-1 text-[11px] font-semibold text-[#5b76fe]">
                {output}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-auto flex items-center gap-1 pt-6 text-sm font-semibold text-[#5b76fe]">
        {action}
        <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
      </div>
    </Link>
  );
}

function SectionBand({
  label,
  title,
  body,
  tone = "blue",
  children,
}: {
  label: string;
  title: string;
  body: string;
  tone?: "blue" | "teal" | "amber" | "slate";
  children: ReactNode;
}) {
  const toneClasses = {
    blue: "border-[#dfe4ff] bg-[#f7f8ff]",
    teal: "border-[#cdeee9] bg-[#f4fffc]",
    amber: "border-[#f6dfc9] bg-[#fff8f1]",
    slate: "border-[#dfe3ea] bg-[#f7f8fb]",
  }[tone];
  const labelClasses = {
    blue: "text-[#5b76fe]",
    teal: "text-[#0f766e]",
    amber: "text-[#9a5a16]",
    slate: "text-[#555a6a]",
  }[tone];

  return (
    <section className={`space-y-4 rounded-[24px] border p-4 lg:p-5 ${toneClasses}`}>
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <p className={`text-xs font-semibold uppercase tracking-wider ${labelClasses}`}>{label}</p>
          <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">{title}</h2>
        </div>
        <p className="max-w-xl text-sm leading-6 text-[#667085]">{body}</p>
      </div>
      {children}
    </section>
  );
}

export function Marketplace() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <Store size={13} />
              Module Overview
            </p>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
              External opportunities powered by the FHIR Chart
            </h1>
            <p className="mt-3 text-base leading-7 text-[#667085]">
              Marketplace modules help patients use their chart to find things outside the care record: trials, medication
              access, grants, research programs, and specialist review options.
            </p>
          </div>
          <div className="rounded-2xl bg-[#fafbff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:min-w-[280px]">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-[#00b473]" />
              <p className="text-sm font-semibold text-[#1c1c1e]">Module contract</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              Every module declares whether it leaves the private record workspace, what data it needs, and what evidence
              must stay attached to its output.
            </p>
          </div>
        </div>
      </section>

      <SectionBand
        label="Featured Marketplaces"
        title="Outbound modules that help patients find opportunities"
        body="These workflows may search external sources, prepare applications, package evidence, or introduce outside reviewers. They need stronger sharing, consent, and audit boundaries."
        tone="blue"
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <ModuleCard
            icon={Search}
            title="Clinical Trial Match"
            status="Preview"
            audience="External opportunity"
            inputs={["Problems", "Labs", "Age", "Meds"]}
            outputs={["Eligibility signals", "Exclusions", "Share packet"]}
            body="Screens record facts against candidate eligibility criteria and highlights what needs verification."
            to={withPatient("/trials", patientId)}
            tone="rose"
            action="Find trials"
          />
          <ModuleCard
            icon={Pill}
            title="Medication Access"
            status="Preview"
            audience="External affordability"
            inputs={["Active therapies", "Rx fills", "Coverage context"]}
            outputs={["Affordability brief", "Program checklist", "Fulfillment plan"]}
            body="Uses medication context to organize price, assistance, and payer-friction workflows."
            to={withPatient("/medication-access", patientId)}
            tone="green"
            action="Find access paths"
          />
          <ModuleCard
            icon={DollarSign}
            title="Grant Finder"
            status="Concept"
            audience="External support"
            inputs={["Diagnosis", "Meds", "Financial context"]}
            outputs={["Grant matches", "Document checklist", "Application path"]}
            body="Identifies disease foundations, assistance programs, and grant opportunities that fit the patient context."
            to={withPatient("/sharing", patientId)}
            tone="orange"
            action="Preview concept"
          />
          <ModuleCard
            icon={FileSearch}
            title="Research Opportunities"
            status="Concept"
            audience="External research"
            inputs={["Conditions", "Procedures", "Care timeline"]}
            outputs={["Study leads", "Recruitment packet", "Questions"]}
            body="Surfaces registries, studies, and patient communities where the record can support next-step research."
            to={withPatient("/sharing", patientId)}
            tone="blue"
            action="Preview concept"
          />
        </div>
      </SectionBand>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <ClipboardCheck size={18} className="text-[#5b76fe]" />
          <h2 className="text-lg font-semibold text-[#1c1c1e]">Why this controls rule explosion</h2>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {[
            ["Platform", "Owns identity, source aggregation, normalized facts, provenance, and trust metadata."],
            ["External module", "Can search or share outside the record workspace, so it needs consent, packet scope, and audit controls."],
            ["Private insight module", "Runs inside the patient workspace for chart understanding, cited Q&A, or clinician-facing review."],
            ["Review boundary", "Marks partial, inferred, conflicting, outbound, or out-of-scope findings before action."],
          ].map(([title, body]) => (
            <div key={title} className="rounded-xl border border-[#e9eaef] p-4">
              <p className="text-sm font-semibold text-[#1c1c1e]">{title}</p>
              <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl bg-[#f7fffc] p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <TestTubeDiagonal size={18} className="text-[#0f766e]" />
          <h2 className="text-lg font-semibold text-[#0f172a]">Phase 1 implementation posture</h2>
        </div>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-[#35524d]">
          This marketplace is currently a product scaffold. The first build should keep module cards static and route into existing
          working pages. Backend module manifests, rule-pack runtime, and external publishing should come after the shell proves the story.
        </p>
      </section>
    </main>
  );
}
