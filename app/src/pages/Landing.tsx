import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  Boxes,
  Database,
  FileSearch,
  Lock,
  Microscope,
  ShieldCheck,
  Sparkles,
  Stethoscope,
} from "lucide-react";

const entryCards = [
  {
    title: "Open workspace",
    body: "Enter the live application shell starting from Patient Record, with FHIR Charts, Caspian, Workspaces, and Learn available from the top navigation.",
    to: "/patient-record",
    action: "Enter platform",
    icon: Stethoscope,
    tone: "primary",
  },
  {
    title: "Browse patient records",
    body: "Review the synthetic patient pool and pick a prepared record to walk through intake, chart generation, and downstream use.",
    to: "/records-pool",
    action: "Open patient pool",
    icon: Database,
    tone: "neutral",
  },
  {
    title: "Read the product tour",
    body: "See how the modules connect before jumping into the live shell, including trust boundaries, workflow posture, and platform intent.",
    to: "/guided-tour",
    action: "View guided tour",
    icon: Sparkles,
    tone: "neutral",
  },
];

const moduleCards = [
  {
    title: "Patient Record",
    body: "Source intake, harmonization, publishing, and patient context in one operational pipeline.",
    to: "/patient-record",
    icon: FileSearch,
  },
  {
    title: "FHIR Charts",
    body: "Prepared chart surfaces for summary, history, safety, patient data, and chart-grounded review.",
    to: "/fhir-charts",
    icon: Database,
  },
  {
    title: "Caspian",
    body: "Private, first-party clinical workspace for workflow execution, review, and citation-backed reasoning.",
    to: "/caspian",
    icon: ShieldCheck,
  },
  {
    title: "Workspaces",
    body: "External packages and consented tools that operate from the chart without collapsing trust boundaries.",
    to: "/workspaces",
    icon: Boxes,
  },
];

const trustCards = [
  {
    title: "Source-aware chart layer",
    body: "Patient data is collected from scattered exports and normalized into a patient-owned chart with provenance preserved.",
    icon: Database,
  },
  {
    title: "Operational module shell",
    body: "Modules open on top of the prepared chart, so the user experiences a working application rather than a set of disconnected demos.",
    icon: Boxes,
  },
  {
    title: "Clear trust boundaries",
    body: "Private clinical workflows and consented external tools can share one platform while keeping their trust posture visible.",
    icon: Lock,
  },
];

const supportLinks = [
  {
    title: "FHIR primer",
    body: "Plain-language orientation for the data model and chart layer.",
    to: "/learn/fhir-primer",
    icon: BookOpen,
  },
  {
    title: "System architecture",
    body: "How records, charts, workspaces, and learning surfaces fit together.",
    to: "/architecture",
    icon: Boxes,
  },
  {
    title: "Data lab",
    body: "Coverage, trust, QA, and internal evaluation surfaces.",
    to: "/learn",
    icon: Microscope,
  },
];

export function Landing() {
  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f4f7fb_0%,#eef3f8_100%)] text-[#18202b]">
      <header className="border-b border-[#dde5ef] bg-[rgba(255,255,255,0.9)] backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-5">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#7f8aa0]">
              EHI Exchange Platform
            </p>
            <p className="mt-1 text-lg font-semibold text-[#18202b]">
              Clinical workflow workspace
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/learn/fhir-primer"
              className="hidden text-sm font-semibold text-[#52627f] transition-colors hover:text-[#3657ff] sm:inline-flex"
            >
              FHIR primer
            </Link>
            <Link
              to="/patient-record"
              className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(77,104,255,0.22)] transition-colors hover:bg-[#3c57ef]"
            >
              Enter platform
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </header>

      <main className="px-6 py-8">
        <section className="mx-auto max-w-7xl">
          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <section className="rounded-[28px] border border-[#dbe4f0] bg-white px-8 py-8 shadow-[0_18px_50px_rgba(24,32,43,0.06)] lg:px-10 lg:py-10">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#4d68ff]">
                Application Overview
              </p>
              <h1 className="mt-4 max-w-4xl text-4xl font-semibold tracking-tight text-[#171b24] lg:text-6xl">
                Turn fragmented records into chart-ready clinical work.
              </h1>
              <p className="mt-5 max-w-3xl text-base leading-8 text-[#61728d]">
                The platform assembles scattered patient data into a source-aware FHIR Chart, then opens focused application surfaces for review, workflows, decision support, and downstream collaboration.
              </p>

              <div className="mt-7 flex flex-wrap gap-3">
                <Link
                  to="/patient-record"
                  className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef]"
                >
                  Enter platform
                  <ArrowRight size={16} />
                </Link>
                <Link
                  to="/records-pool"
                  className="inline-flex items-center gap-2 rounded-2xl border border-[#d7dfeb] bg-[#f9fbff] px-5 py-3 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff]"
                >
                  Browse patient pool
                </Link>
              </div>
            </section>

            <section className="rounded-[28px] border border-[#dbe4f0] bg-[#f8fbff] p-6 shadow-[0_18px_50px_rgba(24,32,43,0.04)]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#4d68ff]">
                Platform Posture
              </p>
              <div className="mt-4 space-y-4">
                {trustCards.map((card) => {
                  const Icon = card.icon;
                  return (
                    <div key={card.title} className="rounded-2xl border border-[#e2e8f1] bg-white p-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eef2ff] text-[#4d68ff]">
                          <Icon size={18} />
                        </div>
                        <p className="text-base font-semibold text-[#18202b]">{card.title}</p>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-[#62728d]">{card.body}</p>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>

          <section className="mt-6 grid gap-4 xl:grid-cols-3">
            {entryCards.map((card) => {
              const Icon = card.icon;
              const primary = card.tone === "primary";
              return (
                <Link
                  key={card.title}
                  to={card.to}
                  className={`group rounded-[26px] border p-6 shadow-[0_10px_28px_rgba(24,32,43,0.05)] transition-all hover:-translate-y-0.5 ${
                    primary
                      ? "border-[#cad5ff] bg-[linear-gradient(180deg,#f5f7ff_0%,#eef2ff_100%)]"
                      : "border-[#dee6f0] bg-white"
                  }`}
                >
                  <div className={`flex h-12 w-12 items-center justify-center rounded-2xl ${primary ? "bg-white text-[#4d68ff]" : "bg-[#eef2ff] text-[#4d68ff]"}`}>
                    <Icon size={22} />
                  </div>
                  <h2 className="mt-6 text-2xl font-semibold text-[#18202b]">{card.title}</h2>
                  <p className="mt-3 min-h-[88px] text-sm leading-6 text-[#62728d]">{card.body}</p>
                  <span className="mt-6 inline-flex items-center gap-1 text-sm font-semibold text-[#4d68ff] transition-all group-hover:gap-2">
                    {card.action}
                    <ArrowRight size={14} />
                  </span>
                </Link>
              );
            })}
          </section>

          <section className="mt-6 rounded-[28px] border border-[#dbe4f0] bg-white p-6 shadow-[0_14px_36px_rgba(24,32,43,0.04)]">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#4d68ff]">
                  Modules
                </p>
                <h2 className="mt-2 text-2xl font-semibold text-[#18202b]">
                  Work from a prepared chart, not a collection of demos
                </h2>
              </div>
              <p className="max-w-2xl text-sm leading-6 text-[#62728d]">
                Each module assumes the chart is already prepared and uses that shared layer differently: record operations, review surfaces, private workflows, and consented external tools.
              </p>
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
              {moduleCards.map((card) => {
                const Icon = card.icon;
                return (
                  <Link
                    key={card.title}
                    to={card.to}
                    className="group rounded-[24px] border border-[#e0e6ef] bg-[#fbfcff] p-5 transition-all hover:border-[#cad5ff] hover:bg-white"
                  >
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#eef2ff] text-[#4d68ff]">
                      <Icon size={20} />
                    </div>
                    <h3 className="mt-4 text-lg font-semibold text-[#18202b]">{card.title}</h3>
                    <p className="mt-2 min-h-[94px] text-sm leading-6 text-[#62728d]">{card.body}</p>
                    <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-[#4d68ff] transition-all group-hover:gap-2">
                      Open module
                      <ArrowRight size={14} />
                    </span>
                  </Link>
                );
              })}
            </div>
          </section>

          <section className="mt-6 grid gap-4 lg:grid-cols-3">
            {supportLinks.map((card) => {
              const Icon = card.icon;
              return (
                <Link
                  key={card.title}
                  to={card.to}
                  className="group rounded-[24px] border border-[#dde5ef] bg-[rgba(255,255,255,0.82)] p-5 transition-all hover:border-[#cad5ff] hover:bg-white"
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#f3f6fb] text-[#4d68ff]">
                    <Icon size={20} />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold text-[#18202b]">{card.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[#62728d]">{card.body}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-[#4d68ff] transition-all group-hover:gap-2">
                    Open
                    <ArrowRight size={14} />
                  </span>
                </Link>
              );
            })}
          </section>
        </section>
      </main>
    </div>
  );
}
