import { Link } from "react-router-dom";
import {
  ArrowRight,
  Boxes,
  Brain,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileSearch,
  GitBranch,
  LockKeyhole,
  Search,
  Share2,
} from "lucide-react";

const architectureSteps = [
  {
    title: "Data sources",
    body: "Portals, hospitals, clinics, labs, pharmacies, payer data, and uploaded files.",
    icon: FileSearch,
    tone: "bg-[#eef1ff] text-[#5b76fe]",
  },
  {
    title: "Data Aggregator",
    body: "Guides collection, tracks source status, and starts post-process cleaning.",
    icon: GitBranch,
    tone: "bg-[#eef1ff] text-[#5b76fe]",
  },
  {
    title: "FHIR Chart",
    body: "The patient-owned, cleaned record with usable facts, provenance, and review flags.",
    icon: Database,
    tone: "bg-[#def7f1] text-[#008f7a]",
  },
  {
    title: "Use cases",
    body: "Private insights, external marketplace modules, sharing, and internal data tools.",
    icon: Boxes,
    tone: "bg-[#fff0d8] text-[#a76300]",
  },
];

const useCaseGroups = [
  {
    title: "Private Clinical Insights",
    body: "Runs inside the patient workspace for chart understanding, pre-op support, Q&A, and caregiver views.",
    icon: Brain,
  },
  {
    title: "Marketplace",
    body: "Uses chart facts for external opportunities like trial matching, medication access, grants, and research.",
    icon: Search,
  },
  {
    title: "Sharing",
    body: "Packages the right evidence for second opinions, referrals, and patient-directed exchange.",
    icon: Share2,
  },
  {
    title: "Internal Tools",
    body: "Explains FHIR quality, field coverage, trust boundaries, and module contracts.",
    icon: ClipboardCheck,
  },
];

export function PlatformArchitecture() {
  return (
    <div className="min-h-screen bg-[#f5f6f8] text-[#1c1c1e]">
      <header className="border-b border-[#e1e4eb] bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6">
          <Link to="/" className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9aa1b2]">
              EHI Exchange Platform
            </p>
            <p className="text-base font-semibold text-[#1c1c1e]">System architecture</p>
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-xl bg-[#5b76fe] px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#445ee8]"
          >
            Enter platform
            <ArrowRight size={15} />
          </Link>
        </div>
      </header>

      <main className="px-6 py-8">
        <section className="mx-auto max-w-7xl">
          <div className="mb-8 grid gap-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-end">
            <div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[#5b76fe]">
                Architecture overview
              </p>
              <h1 className="text-4xl font-semibold tracking-tight text-[#18191f] lg:text-5xl">
                The platform turns scattered patient data into usable chart workflows.
              </h1>
            </div>
            <p className="text-base leading-7 text-[#63708a]">
              This is the high-level map. The real app starts on the home page with selecting a patient. This page explains what happens around that action: collect data, clean it into the FHIR Chart, then route it into controlled use cases.
            </p>
          </div>

          <div className="rounded-[28px] border border-[#dfe5f0] bg-white p-6 shadow-sm">
            <div className="grid gap-4 lg:grid-cols-4">
              {architectureSteps.map((step, index) => {
                const Icon = step.icon;
                return (
                  <div key={step.title} className="relative rounded-2xl border border-[#e4e8f0] bg-[#fbfcff] p-5">
                    {index < architectureSteps.length - 1 ? (
                      <div className="absolute -right-4 top-1/2 hidden h-px w-4 bg-[#cfd7ff] lg:block" />
                    ) : null}
                    <div className="mb-5 flex items-center justify-between">
                      <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${step.tone}`}>
                        <Icon size={20} />
                      </div>
                      <span className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-[#657087]">
                        {index + 1}
                      </span>
                    </div>
                    <h2 className="text-lg font-semibold">{step.title}</h2>
                    <p className="mt-2 text-sm leading-6 text-[#64708a]">{step.body}</p>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
            <div className="rounded-[24px] border border-[#c9f0e7] bg-[#effbf8] p-6">
              <div className="mb-5 flex items-center gap-2">
                <LockKeyhole size={18} className="text-[#008f7a]" />
                <h2 className="text-lg font-semibold">Trust boundary</h2>
              </div>
              <div className="space-y-3">
                {[
                  "FHIR Chart keeps source links, conflicts, and review flags attached to facts.",
                  "Private Clinical Insights stay inside the patient workspace.",
                  "Marketplace and sharing workflows require a clear packet scope and consent boundary.",
                ].map((item) => (
                  <div key={item} className="flex gap-3 rounded-xl border border-[#bdebdc] bg-white/75 p-4 text-sm leading-6 text-[#405c69]">
                    <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-[#008f7a]" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[24px] border border-[#e1e6ef] bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold">Use-case layer</h2>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {useCaseGroups.map((group) => {
                  const Icon = group.icon;
                  return (
                    <div key={group.title} className="rounded-2xl border border-[#e4e8f0] bg-[#fbfcff] p-4">
                      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
                        <Icon size={18} />
                      </div>
                      <h3 className="font-semibold">{group.title}</h3>
                      <p className="mt-1 text-sm leading-6 text-[#667289]">{group.body}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="mt-6 flex flex-col gap-3 rounded-[24px] border border-[#e1e6ef] bg-white p-6 shadow-sm sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Ready to use the platform?</h2>
              <p className="mt-1 text-sm text-[#667289]">
                Go back to the product entry screen, select a patient, and start the data flow.
              </p>
            </div>
            <Link
              to="/"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#5b76fe] px-5 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#445ee8]"
            >
              Select a patient
              <ArrowRight size={16} />
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
