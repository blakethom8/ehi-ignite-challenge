import { Link } from "react-router-dom";
import { ArrowRight, Boxes, Database, FileSearch, Upload, ShieldCheck } from "lucide-react";
import { HeroPipelineDiagram } from "../components/marketing/HeroPipelineDiagram";
import { MarketingHeader } from "../components/marketing/MarketingHeader";
import { useAccessContext } from "../context/AccessContext";
import { buildDemoSelectionPath, withPatientContext } from "../routing";
import { resolveAccountPath, resolveSessionHomePath } from "../sessionRouting";

const surfaceCards = [
  {
    title: "Data harmonizer",
    body: "Admit FHIR bundles, C-CDA packets, PDFs, and portal exports into one workspace, then harmonize them into an enhanced FHIR extraction layer optimized for LLM use before publishing a canonical chart.",
    caption: "Source-of-truth pipeline",
    to: "/patient-record",
    icon: FileSearch,
    accent: "from-[#eff3ff] via-[#f8faff] to-[#ffffff]",
    edge: "border-[#cad6ff]",
    glow: "shadow-[0_22px_70px_rgba(77,104,255,0.10)]",
    detail: "Ingest • reconcile • canonical publish",
    supporting: "The shared patient layer that downstream charts, guided review, and consented tools all read from.",
  },
  {
    title: "FHIR Charts",
    body: "Browse the prepared record through timeline, labs, safety, conditions, medications, and chart-grounded assistant views built for rapid review.",
    caption: "Chart workspace",
    to: "/fhir-charts",
    icon: Database,
    accent: "from-[#edf8ff] via-[#f7fcff] to-[#ffffff]",
    edge: "border-[#c8e2f1]",
    glow: "shadow-[0_22px_70px_rgba(30,120,185,0.10)]",
    detail: "Summary • timeline • labs • grounded assistant",
    supporting: "Open the same chart through focused visual surfaces instead of scanning raw resource dumps.",
  },
  {
    title: "Caspian",
    body: "Run guided review workflows inside a private workspace where approvals, notes, and evidence-backed reasoning stay attached to the chart.",
    caption: "Guided review workspace",
    to: "/caspian",
    icon: ShieldCheck,
    accent: "from-[#eefaf4] via-[#f8fcfa] to-[#ffffff]",
    edge: "border-[#cbe5d8]",
    glow: "shadow-[0_22px_70px_rgba(54,128,94,0.10)]",
    detail: "Private boundary • approvals • evidence trace",
    supporting: "Designed for high-trust clinical review where every answer needs a visible trail back to record evidence.",
  },
  {
    title: "Plugins",
    body: "Bring in scoped tools that work from the harmonized chart while preserving clear consent, run boundaries, and audit visibility.",
    caption: "Scoped tool surface",
    to: "/workspaces",
    icon: Boxes,
    accent: "from-[#f4efff] via-[#fbf8ff] to-[#ffffff]",
    edge: "border-[#ddd0ff]",
    glow: "shadow-[0_22px_70px_rgba(113,79,196,0.10)]",
    detail: "Trial finder • med access • second opinion",
    supporting: "Extensions can act on the chart, but Atlas keeps the tool scope and patient-data boundary explicit.",
  },
];

export function Landing() {
  const { activePatientId, isUnlocked, mode, user } = useAccessContext();
  const surfaceCardsForState = surfaceCards.map((card) => ({
    ...card,
    to: withPatientContext(card.to, activePatientId),
  }));
  const accountHref = resolveAccountPath(mode, Boolean(user));
  const sessionHomeHref = resolveSessionHomePath(mode, activePatientId);
  const isAuthenticated = mode === "authenticated" && Boolean(user);
  const primaryWorkspaceLabel = activePatientId ? "Resume workspace" : "Upload files";

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#f6f9ff_0%,#eef3f8_42%,#e9eef4_100%)] text-[#18202b]">
      <MarketingHeader />

      <main className="px-6 py-10">
        <section className="mx-auto max-w-7xl">
          <section className="relative overflow-hidden rounded-[36px] px-2 py-4 lg:px-0">
            <div className="absolute inset-x-0 top-0 -z-10 h-[420px] rounded-[40px] bg-[radial-gradient(circle_at_15%_18%,rgba(77,104,255,0.18),transparent_30%),radial-gradient(circle_at_82%_22%,rgba(101,198,255,0.16),transparent_26%),linear-gradient(180deg,rgba(255,255,255,0.72),rgba(255,255,255,0))]" />
            <div className="mx-auto flex max-w-5xl flex-col items-center text-center">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#4d68ff]">
                Consumer health records
              </p>
              <h1 className="mt-5 text-5xl font-semibold leading-[0.94] tracking-[-0.05em] text-[#171b24] sm:text-6xl lg:text-[84px]">
                Bring scattered health records into one reviewable workspace.
              </h1>
              <p className="mt-6 max-w-3xl text-lg leading-8 text-[#5f6f89]">
                {isAuthenticated
                  ? `Signed in as ${user?.display_name}. Open your workspace, continue chart review, or manage your account.`
                  : "Upload any of your health documents to create a harmonized data bundle, use Atlas for insights, or export it for your own use."}
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                {isAuthenticated ? (
                  <>
                    <Link
                      to={sessionHomeHref}
                      className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      {primaryWorkspaceLabel}
                      <ArrowRight size={16} />
                    </Link>
                    <Link
                      to={accountHref}
                      className="inline-flex items-center gap-2 rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.76)] px-5 py-3 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff]"
                    >
                      Account settings
                    </Link>
                  </>
                ) : (
                  <>
                    <Link
                      to={buildDemoSelectionPath()}
                      className="inline-flex items-center gap-2 rounded-2xl bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      Try demo
                      <ArrowRight size={16} />
                    </Link>
                    <Link
                      to="/guest-harmonization"
                      className="inline-flex items-center gap-2 rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.76)] px-5 py-3 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff]"
                    >
                      Try with my files
                      <Upload size={16} />
                    </Link>
                    <Link
                      to={accountHref}
                      className="inline-flex items-center gap-2 rounded-2xl border border-[#d5deea] bg-[rgba(255,255,255,0.76)] px-5 py-3 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#4d68ff] hover:text-[#3657ff]"
                    >
                      Log in / Sign up
                    </Link>
                  </>
                )}
              </div>
            </div>

            <div className="mx-auto mt-10 max-w-5xl">
              <HeroPipelineDiagram />
            </div>
          </section>

          <section className="mt-8">
            <div className="mx-auto mt-8 flex max-w-5xl flex-col items-center gap-3 text-center">
              <div className="max-w-3xl">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#4d68ff]">
                  Workspace surfaces
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[#18202b] sm:text-4xl">
                  One harmonized patient record, four ways to work from it.
                </h2>
              </div>
              <p className="max-w-3xl text-sm leading-7 text-[#62728d]">
                Atlas prepares a shared patient layer first, then opens focused surfaces for chart review, guided workflows, and consented tools while preserving a portable record the patient can use wherever they go next.
              </p>
            </div>

            <div className="mt-6 grid gap-5 xl:grid-cols-2">
              {surfaceCardsForState.map((card) => {
                const Icon = card.icon;
                const cardBody = (
                  <>
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
                      <p className="mt-4 max-w-xl text-sm leading-6 text-[#73829c]">
                        {card.supporting}
                      </p>

                      <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                        <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-[#7887a1]">
                          {card.detail}
                        </p>
                        <span className="inline-flex items-center gap-2 text-sm font-semibold text-[#3558ff] transition-all group-hover:gap-3">
                          {isUnlocked ? "Open surface" : "Available after opening a workspace"}
                          {isUnlocked ? <ArrowRight size={15} /> : null}
                        </span>
                      </div>
                    </div>
                  </>
                );

                if (isUnlocked) {
                  return (
                    <Link
                      key={card.title}
                      to={card.to}
                      className={`group relative overflow-hidden rounded-[30px] border ${card.edge} bg-gradient-to-br ${card.accent} p-6 ${card.glow} transition-transform duration-200 hover:-translate-y-1`}
                    >
                      {cardBody}
                    </Link>
                  );
                }

                return (
                  <div
                    key={card.title}
                    className={`group relative overflow-hidden rounded-[30px] border ${card.edge} bg-gradient-to-br ${card.accent} p-6 ${card.glow}`}
                  >
                    {cardBody}
                  </div>
                );
              })}
            </div>
          </section>
        </section>
      </main>
    </div>
  );
}
