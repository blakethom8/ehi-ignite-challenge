import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Boxes,
  Database,
  FileSearch,
  Pill,
  SearchCheck,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import { useAccessContext } from "../context/AccessContext";

const demoWorkspaces = [
  {
    patientId: "demo-high-risk",
    title: "Surgical Review Sample",
    body: "Review a prepared synthetic chart with medications, conditions, and surgical-risk signals.",
    to: "/patient-record",
    icon: Stethoscope,
    accent: "from-[#eefaf4] via-[#f8fcfa] to-white",
    edge: "border-[#cbe5d8]",
    label: "Prepared sample chart",
  },
  {
    patientId: "demo-trial-match",
    title: "Trial Match Sample",
    body: "Explore how a structured chart can support trial-search workflows.",
    to: "/workspaces/trial-finder",
    icon: SearchCheck,
    accent: "from-[#edf8ff] via-[#f7fcff] to-white",
    edge: "border-[#c8e2f1]",
    label: "Sample workflow",
  },
  {
    patientId: "demo-med-access",
    title: "Medication Access Sample",
    body: "Review medication burden and access-oriented workflow surfaces.",
    to: "/workspaces/med-access",
    icon: Pill,
    accent: "from-[#fff7ed] via-[#fffbf6] to-white",
    edge: "border-[#fed7aa]",
    label: "Sample workspace",
  },
];

const moduleCards = [
  {
    title: "Patient Record",
    body: "Organize sources, review extracted facts, and publish a usable health-record workspace.",
    caption: "Prepared chart layer",
    to: "/patient-record",
    icon: FileSearch,
    accent: "from-[#eff3ff] via-[#f8faff] to-[#ffffff]",
    edge: "border-[#cad6ff]",
    glow: "shadow-[0_22px_70px_rgba(77,104,255,0.10)]",
    detail: "Source intake • review queue • canonical publish",
  },
  {
    title: "FHIR Charts",
    body: "Open prepared chart surfaces for summary, history, safety, patient data, and chart-grounded review.",
    caption: "Chart views",
    to: "/fhir-charts",
    icon: Database,
    accent: "from-[#edf8ff] via-[#f7fcff] to-[#ffffff]",
    edge: "border-[#c8e2f1]",
    glow: "shadow-[0_22px_70px_rgba(30,120,185,0.10)]",
    detail: "Summary • timeline • labs • grounded assistant",
  },
  {
    title: "Caspian",
    body: "A private workspace for guided review, approvals, and citation-backed reasoning.",
    caption: "Private workflow agent",
    to: "/caspian",
    icon: ShieldCheck,
    accent: "from-[#eefaf4] via-[#f8fcfa] to-[#ffffff]",
    edge: "border-[#cbe5d8]",
    glow: "shadow-[0_22px_70px_rgba(54,128,94,0.10)]",
    detail: "Private boundary • approvals • evidence trace",
  },
  {
    title: "Plugins",
    body: "Consented tools can work from the chart while keeping every trust boundary visible.",
    caption: "External workflow surfaces",
    to: "/workspaces",
    icon: Boxes,
    accent: "from-[#f4efff] via-[#fbf8ff] to-[#ffffff]",
    edge: "border-[#ddd0ff]",
    glow: "shadow-[0_22px_70px_rgba(113,79,196,0.10)]",
    detail: "Trial finder • med access • second opinion",
  },
];

export function Landing() {
  const navigate = useNavigate();
  const {
    activePatientId,
    activePatientName,
    enterDemoPatient,
    isDemo,
    isLoading,
    isUnlocked,
    user,
  } = useAccessContext();
  const [pendingPatientId, setPendingPatientId] = useState<string | null>(null);
  const [demoError, setDemoError] = useState<string | null>(null);
  const moduleCardsForState = moduleCards.map((card) => ({
    ...card,
    to: activePatientId ? `${card.to}?patient=${encodeURIComponent(activePatientId)}` : card.to,
  }));

  const openDemoWorkspace = async (patientId: string, path: string) => {
    setDemoError(null);
    setPendingPatientId(patientId);
    try {
      await enterDemoPatient(patientId);
      navigate(`${path}?patient=${encodeURIComponent(patientId)}`);
    } catch (error) {
      setDemoError(
        error instanceof Error && error.message.trim()
          ? error.message
          : "Could not open the sample chart. Try again.",
      );
    } finally {
      setPendingPatientId(null);
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#f6f9ff_0%,#eef3f8_42%,#e9eef4_100%)] text-[#18202b]">
      <header className="border-b border-[#dde5ef] bg-[rgba(255,255,255,0.88)] backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-5">
          <Link to="/" className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#7f8aa0]">
              Atlas
            </p>
            <p className="mt-1 text-lg font-semibold text-[#18202b]">
              Health-record workspace
            </p>
          </Link>
          <div className="flex items-center gap-3">
            <Link
              to="/using-atlas"
              className="hidden text-sm font-semibold text-[#52627f] transition-colors hover:text-[#3657ff] sm:inline-flex"
            >
              About Atlas
            </Link>
            <Link
              to="/account"
              className="hidden rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.78)] px-4 py-2.5 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff] sm:inline-flex"
            >
              Log in / Sign up
            </Link>
            <a
              href="#demo-workspaces"
              className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(77,104,255,0.22)] transition-colors hover:bg-[#3c57ef]"
            >
              Try demo
              <ArrowRight size={16} />
            </a>
          </div>
        </div>
      </header>

      <main className="px-6 py-10">
        <section className="mx-auto max-w-7xl">
          <section className="relative overflow-hidden rounded-[36px] px-2 py-4 lg:px-0">
            <div className="absolute inset-x-0 top-0 -z-10 h-[420px] rounded-[40px] bg-[radial-gradient(circle_at_15%_18%,rgba(77,104,255,0.18),transparent_30%),radial-gradient(circle_at_82%_22%,rgba(101,198,255,0.16),transparent_26%),linear-gradient(180deg,rgba(255,255,255,0.72),rgba(255,255,255,0))]" />
            <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
              <div className="max-w-4xl">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#4d68ff]">
                  Consumer health records
                </p>
                <h1 className="mt-5 text-5xl font-semibold leading-[0.94] tracking-[-0.05em] text-[#171b24] sm:text-6xl lg:text-[84px]">
                  Bring scattered health records into one reviewable workspace.
                </h1>
                <p className="mt-6 max-w-3xl text-lg leading-8 text-[#5f6f89]">
                  Try Atlas with a prepared sample chart, or use an account to save private record workspaces and return later.
                </p>
                <div className="mt-8 flex flex-wrap gap-3">
                  <a
                    href="#demo-workspaces"
                    className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef]"
                  >
                    Try demo
                    <ArrowRight size={16} />
                  </a>
                  <Link
                    to="/account"
                    className="inline-flex items-center gap-2 rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.76)] px-5 py-3 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff]"
                  >
                    Log in / Sign up
                  </Link>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                {isUnlocked && activePatientId ? (
                  <div className="rounded-[24px] border border-[rgba(77,104,255,0.14)] bg-[rgba(255,255,255,0.82)] p-5 backdrop-blur sm:col-span-3 lg:col-span-1">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4d68ff]">
                      Active workspace
                    </p>
                    <p className="mt-3 text-xl font-semibold text-[#18202b]">
                      {activePatientName ?? activePatientId}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-[#3e4d68]">
                      {isDemo
                        ? "A synthetic sample chart is active. No real patient data is used."
                        : user
                          ? `Signed in as ${user.display_name}. Open your saved health-record workspace or switch charts.`
                          : "Your account workspace is active."}
                    </p>
                    <Link
                      to={`/patient-record?patient=${encodeURIComponent(activePatientId)}`}
                      className="mt-4 inline-flex items-center gap-2 rounded-2xl bg-[#eef2ff] px-4 py-2.5 text-sm font-semibold text-[#3657ff]"
                    >
                      Continue workspace
                      <ArrowRight size={15} />
                    </Link>
                  </div>
                ) : (
                  <>
                    <div className="rounded-[24px] border border-[rgba(77,104,255,0.14)] bg-[rgba(255,255,255,0.72)] p-5 backdrop-blur">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7a88a3]">
                        Try now
                      </p>
                      <p className="mt-3 text-sm leading-6 text-[#3e4d68]">
                        Open a prepared sample chart without creating an account.
                      </p>
                    </div>
                    <div className="rounded-[24px] border border-[rgba(77,104,255,0.14)] bg-[rgba(255,255,255,0.72)] p-5 backdrop-blur">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7a88a3]">
                        Synthetic records
                      </p>
                      <p className="mt-3 text-sm leading-6 text-[#3e4d68]">
                        Demo workspaces use generated Synthea charts, never real patient data.
                      </p>
                    </div>
                    <div className="rounded-[24px] border border-[rgba(77,104,255,0.14)] bg-[rgba(255,255,255,0.72)] p-5 backdrop-blur">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7a88a3]">
                        Account access
                      </p>
                      <p className="mt-3 text-sm leading-6 text-[#3e4d68]">
                        Log in separately when you already have a saved account.
                      </p>
                    </div>
                  </>
                )}
              </div>
            </div>
          </section>

          <section className="mt-8" id="demo-workspaces">
            <div className="rounded-[30px] border border-[#cad6ff] bg-[rgba(255,255,255,0.78)] p-6 shadow-[0_22px_70px_rgba(77,104,255,0.08)]">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                <div className="max-w-2xl">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#4d68ff]">
                    Demo workspaces
                  </p>
                  <h2 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[#18202b] sm:text-4xl">
                    Start with a prepared sample chart.
                  </h2>
                </div>
                <p className="max-w-2xl text-sm leading-7 text-[#62728d]">
                  These are synthetic records. No real patient data is used.
                </p>
              </div>

              {demoError && (
                <p className="mt-4 rounded-2xl border border-[#fecdca] bg-[#fff1f3] px-4 py-3 text-sm text-[#b42318]">
                  {demoError}
                </p>
              )}

              <div className="mt-6 grid gap-4 lg:grid-cols-3">
                {demoWorkspaces.map((workspace) => {
                  const Icon = workspace.icon;
                  return (
                    <button
                      key={workspace.patientId}
                      type="button"
                      disabled={isLoading || pendingPatientId !== null}
                      onClick={() => void openDemoWorkspace(workspace.patientId, workspace.to)}
                      className={`group overflow-hidden rounded-[26px] border ${workspace.edge} bg-gradient-to-br ${workspace.accent} p-5 text-left shadow-[0_16px_42px_rgba(32,52,89,0.06)] transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-70`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex h-12 w-12 items-center justify-center rounded-[16px] border border-[rgba(77,104,255,0.12)] bg-white/75 text-[#3558ff]">
                          <Icon size={22} />
                        </div>
                        <span className="rounded-full border border-[rgba(24,32,43,0.08)] bg-white/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6f7e98]">
                          {workspace.label}
                        </span>
                      </div>
                      <h3 className="mt-7 text-xl font-semibold tracking-[-0.03em] text-[#18202b]">
                        {workspace.title}
                      </h3>
                      <p className="mt-3 min-h-[72px] text-sm leading-6 text-[#556784]">
                        {workspace.body}
                      </p>
                      <span className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[#3558ff] transition-all group-hover:gap-3">
                        {pendingPatientId === workspace.patientId ? "Opening..." : "Open sample"}
                        <ArrowRight size={15} />
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mt-8 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#4d68ff]">
                  {isUnlocked ? "Workspace surfaces" : "Next step"}
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[#18202b] sm:text-4xl">
                  {isUnlocked ? "Four working environments, one prepared chart." : "Choose a sample or account before opening chart tools."}
                </h2>
              </div>
              <p className="max-w-2xl text-sm leading-7 text-[#62728d]">
                {isUnlocked
                  ? "These are the main Atlas surfaces for the active chart."
                  : "Atlas keeps patient-specific routes closed until there is an explicit sample chart or account workspace."}
              </p>
            </div>

            {isUnlocked ? (
              <div className="mt-6 grid gap-5 xl:grid-cols-2">
                {moduleCardsForState.map((card) => {
                  const Icon = card.icon;
                  return (
                    <Link
                      key={card.title}
                      to={card.to}
                      className={`group relative overflow-hidden rounded-[30px] border ${card.edge} bg-gradient-to-br ${card.accent} p-6 ${card.glow} transition-transform duration-200 hover:-translate-y-1`}
                    >
                      <div className="absolute inset-y-0 right-0 w-[44%] bg-[linear-gradient(135deg,rgba(255,255,255,0.04),rgba(255,255,255,0.44))]" />
                      <div className="absolute right-6 top-6 h-24 w-24 rounded-full border border-[rgba(77,104,255,0.10)] bg-[radial-gradient(circle,rgba(255,255,255,0.9),rgba(255,255,255,0))]" />

                      <div className="relative">
                        <div className="flex items-start justify-between gap-6">
                          <div className="flex h-14 w-14 items-center justify-center rounded-[18px] border border-[rgba(77,104,255,0.12)] bg-[rgba(255,255,255,0.72)] text-[#3558ff]">
                            <Icon size={24} />
                          </div>
                          <div className="rounded-full border border-[rgba(24,32,43,0.08)] bg-[rgba(255,255,255,0.65)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6f7e98]">
                            {card.caption}
                          </div>
                        </div>

                        <h3 className="mt-10 text-[30px] font-semibold tracking-[-0.04em] text-[#18202b]">
                          {card.title}
                        </h3>
                        <p className="mt-3 max-w-xl text-base leading-7 text-[#556784]">
                          {card.body}
                        </p>

                        <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                          <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-[#7887a1]">
                            {card.detail}
                          </p>
                          <span className="inline-flex items-center gap-2 text-sm font-semibold text-[#3558ff] transition-all group-hover:gap-3">
                            Open surface
                            <ArrowRight size={15} />
                          </span>
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            ) : (
              <div className="mt-6 rounded-[24px] border border-[#d8e0eb] bg-white/70 p-5 text-sm leading-7 text-[#556784]">
                Open one of the sample cards above, or log in to an account, then Atlas will show the chart, workflow, and plugin surfaces for that workspace.
              </div>
            )}
          </section>
        </section>
      </main>
    </div>
  );
}
