import { Link } from "react-router-dom";
import {
  ArrowRight,
  Boxes,
  ClipboardCheck,
  Database,
  FileText,
  GitBranch,
  Sparkles,
  Trophy,
} from "lucide-react";

const platformCards = [
  {
    title: "Open the Platform",
    body: "Start in the working app shell with Data Aggregator, FHIR Charts, Clinical Insights, Marketplace, and Internal Tools.",
    to: "/platform",
    action: "Enter platform",
    icon: GitBranch,
    primary: true,
  },
  {
    title: "Start Here: Guided Tour",
    body: "Learn what the platform is supposed to show before jumping into the working app screens.",
    to: "/guided-tour",
    action: "Start learning",
    icon: Sparkles,
  },
  {
    title: "Pool of Patient Records",
    body: "Browse synthetic patients and use one to walk through chart collection, cleaning, and downstream use cases.",
    to: "/records-pool",
    action: "Browse records",
    icon: Database,
  },
];

const contextCards = [
  {
    title: "System Architecture",
    body: "How scattered sources flow into Data Aggregator, FHIR Charts, private insights, marketplace modules, sharing, and internal tools.",
    to: "/architecture",
    action: "View architecture",
    icon: Boxes,
  },
  {
    title: "Product Direction",
    body: "The product direction is a patient-owned data layer with focused clinical and marketplace modules built on top.",
    to: "/clinical-insights",
    action: "View modules",
    icon: Sparkles,
  },
  {
    title: "Data Lab",
    body: "The internal explanation layer for FHIR quality, field coverage, trust boundaries, and module contracts.",
    to: "/analysis",
    action: "Open Data Lab",
    icon: ClipboardCheck,
  },
];

export function Landing() {
  return (
    <div className="min-h-screen bg-[#f5f6f8] text-[#1c1c1e]">
      <header className="border-b border-[#e1e4eb] bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6">
          <Link to="/" className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9aa1b2]">
              EHI Exchange Platform
            </p>
            <p className="text-base font-semibold text-[#1c1c1e]">Application overview</p>
          </Link>
          <Link
            to="/platform"
            className="hidden items-center gap-2 rounded-xl bg-[#5b76fe] px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#445ee8] sm:inline-flex"
          >
            Enter platform
            <ArrowRight size={15} />
          </Link>
        </div>
      </header>

      <main className="px-6 py-8">
        <section className="mx-auto max-w-7xl">
          <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-end">
            <div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[#5b76fe]">
                EHI Ignite concept
              </p>
              <h1 className="max-w-4xl text-4xl font-semibold tracking-tight text-[#18191f] lg:text-6xl">
                Turn scattered patient records into useful clinical workflows.
              </h1>
            </div>
            <div className="max-w-2xl">
              <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center">
                <p className="text-sm font-semibold text-[#526075]">
                  New to FHIR data format?
                </p>
                <Link
                  to="/analysis/fhir-primer"
                  className="inline-flex w-fit items-center gap-1 text-sm font-semibold text-[#5b76fe] transition-all hover:gap-2 hover:text-[#445ee8]"
                >
                  Read the plain-language primer
                  <ArrowRight size={14} />
                </Link>
              </div>
              <p className="text-base leading-7 text-[#63708a]">
                The platform pulls patient data from many places, cleans it into a patient-owned FHIR Chart, then lets that chart power focused modules: pre-op review, clinical understanding, trial matching, medication access, sharing, and internal data review.
              </p>
            </div>
          </div>

          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            {platformCards.map((card) => {
              const Icon = card.icon;
              return (
                <Link
                  key={card.title}
                  to={card.to}
                  className={`group rounded-[24px] border p-6 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md ${
                    card.primary
                      ? "border-[#cfd7ff] bg-[#f3f5ff]"
                      : "border-[#e1e6ef] bg-white"
                  }`}
                >
                  <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-white text-[#5b76fe] shadow-sm">
                    <Icon size={22} />
                  </div>
                  <h2 className="text-xl font-semibold">{card.title}</h2>
                  <p className="mt-2 min-h-[78px] text-sm leading-6 text-[#667289]">{card.body}</p>
                  <span className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-[#5b76fe] transition-all group-hover:gap-2">
                    {card.action}
                    <ArrowRight size={14} />
                  </span>
                </Link>
              );
            })}
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
            <section className="rounded-[24px] border border-[#e1e6ef] bg-white p-6 shadow-sm">
              <div className="mb-5 flex items-center gap-2">
                <Trophy size={18} className="text-[#5b76fe]" />
                <h2 className="text-lg font-semibold">EHI Ignite Challenge</h2>
              </div>
              <p className="text-sm leading-6 text-[#667289]">
                This project is built for the EHI Ignite Challenge: transforming electronic health information into actionable insights. The pitch is not another patient portal or generic FHIR browser. It is a platform for turning raw, scattered records into the right workflow-specific actions.
              </p>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                {[
                  ["Problem", "Records are fragmented and hard to parse quickly."],
                  ["Layer", "The FHIR Chart is the cleaned, source-aware patient record."],
                  ["Value", "Modules turn chart facts into clinical and patient actions."],
                ].map(([title, body]) => (
                  <div key={title} className="rounded-2xl border border-[#e4e8f0] bg-[#fbfcff] p-4">
                    <h3 className="text-sm font-semibold">{title}</h3>
                    <p className="mt-1 text-xs leading-5 text-[#667289]">{body}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="grid gap-4 sm:grid-cols-3">
              {contextCards.map((card) => {
                const Icon = card.icon;
                return (
                  <Link
                    key={card.title}
                    to={card.to}
                    className="group rounded-[24px] border border-[#e1e6ef] bg-white p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-[#cfd7ff] hover:shadow-md"
                  >
                    <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
                      <Icon size={20} />
                    </div>
                    <h2 className="font-semibold">{card.title}</h2>
                    <p className="mt-2 min-h-[96px] text-sm leading-6 text-[#667289]">{card.body}</p>
                    <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-[#5b76fe] transition-all group-hover:gap-2">
                      {card.action}
                      <ArrowRight size={14} />
                    </span>
                  </Link>
                );
              })}
            </section>
          </div>

          <div className="mt-6 rounded-[24px] border border-[#c9f0e7] bg-[#effbf8] p-6">
            <div className="grid gap-4 lg:grid-cols-[0.75fr_1.25fr] lg:items-center">
              <div>
                <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-white text-[#008f7a] shadow-sm">
                  <FileText size={20} />
                </div>
                <h2 className="text-xl font-semibold">Where formal walkthroughs should live</h2>
              </div>
              <p className="text-sm leading-6 text-[#486274]">
                The home page should stay simple. More guided flows belong in separate walkthrough surfaces, especially the Pool of Patient Records, where a reviewer can select a synthetic patient and see how data collection, cleaning, FHIR Chart creation, and downstream modules fit together.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
