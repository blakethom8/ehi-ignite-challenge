import { Link, useLocation, useSearchParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, ClipboardList, DatabaseZap, FileCheck2, KeyRound, RotateCw, ShieldCheck } from "lucide-react";

const steps = [
  {
    title: "Find portals",
    body: "Help the patient identify health systems, clinics, labs, pharmacies, and payer sources that may hold records.",
    status: "Guide",
  },
  {
    title: "Walk the login",
    body: "A guided assistant helps the patient move through portal access and record export steps without the app storing credentials.",
    status: "Assisted",
  },
  {
    title: "Ingest files",
    body: "Bring in FHIR bundles, C-CDA documents, PDFs, CSVs, and screenshots as source material for normalization.",
    status: "Multi-format",
  },
  {
    title: "Clean and reconcile",
    body: "Deduplicate facts, preserve provenance, identify conflicts, and mark what needs human review.",
    status: "Post-process",
  },
  {
    title: "Publish FHIR Chart",
    body: "Produce the patient-owned FHIR Chart that downstream clinical insights and marketplace modules consume.",
    status: "Ready",
  },
];

const moduleCopy = {
  overview: {
    badge: "Module Overview",
    title: "Guide patients from scattered portals to a usable FHIR Chart",
    body:
      "This is the future onboarding layer. It helps patients collect records from multiple sources, then runs the post-process cleaning that turns scattered exports into the chart used everywhere else in the platform.",
  },
  sources: {
    badge: "Source Inventory",
    title: "Track where the patient has records before aggregation starts",
    body:
      "This submodule should become the checklist of portals, clinics, labs, pharmacies, payer files, uploaded documents, and missing source systems that may contain useful EHI.",
  },
  cleaning: {
    badge: "Cleaning Queue",
    title: "Review normalization gaps before facts become chart intelligence",
    body:
      "This submodule should surface duplicate medications, conflicting dates, sparse fields, uncoded facts, unknown providers, and records that need human confirmation before downstream use.",
  },
  publish: {
    badge: "Publish Readiness",
    title: "Confirm the chart is ready for clinical and marketplace modules",
    body:
      "This submodule should become the activation checklist for provenance coverage, unresolved conflicts, source recency, patient consent, and module-specific readiness checks.",
  },
};

export function DataAggregator() {
  const location = useLocation();
  const [params] = useSearchParams();
  const patientId = params.get("patient");
  const activeKey: keyof typeof moduleCopy = location.pathname.includes("/sources")
    ? "sources"
    : location.pathname.includes("/cleaning")
      ? "cleaning"
      : location.pathname.includes("/publish")
        ? "publish"
        : "overview";
  const copy = moduleCopy[activeKey];
  const chartHref = patientId ? `/charts?patient=${patientId}` : "/charts";

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <DatabaseZap size={13} />
              {copy.badge}
            </p>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
              {copy.title}
            </h1>
            <p className="mt-3 max-w-4xl text-base leading-7 text-[#667085]">
              {copy.body}
            </p>
          </div>
          <div className="rounded-2xl bg-[#f7f8ff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:min-w-[280px]">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-[#5b76fe]" />
              <p className="text-sm font-semibold text-[#1c1c1e]">Prototype posture</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              Model the guided collection experience first. Credential handling, automation, and portal-specific flows come later.
            </p>
          </div>
        </div>
      </section>

      <section className="rounded-[24px] border border-[#dfe4ff] bg-[#f7f8ff] p-5">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Patient walkthrough</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">The aggregation journey</h2>
          </div>
          <p className="max-w-xl text-sm leading-6 text-[#667085]">
            The near-term build should feel like a clean checklist and guided assistant, not a backend data pipeline diagram.
          </p>
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-5">
          {steps.map((step, index) => (
            <div key={step.title} className="relative rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
              <div className="flex items-start justify-between gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
                  {index === 0 && <ClipboardList size={18} />}
                  {index === 1 && <KeyRound size={18} />}
                  {index === 2 && <FileCheck2 size={18} />}
                  {index === 3 && <RotateCw size={18} />}
                  {index === 4 && <CheckCircle2 size={18} />}
                </div>
                <span className="rounded-full bg-[#f5f6f8] px-2.5 py-1 text-xs font-semibold text-[#667085]">{step.status}</span>
              </div>
              <p className="mt-4 text-sm font-semibold text-[#5b76fe]">Step {index + 1}</p>
              <h3 className="mt-1 text-lg font-semibold text-[#1c1c1e]">{step.title}</h3>
              <p className="mt-2 text-sm leading-6 text-[#667085]">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <h2 className="text-lg font-semibold text-[#1c1c1e]">What this owns</h2>
          <div className="mt-4 grid gap-3">
            {[
              ["Patient task guidance", "Show what to collect, where it likely lives, and what is still missing."],
              ["Source inventory", "Track which portals, clinics, and files contributed to the chart."],
              ["Cleaning queue", "Surface duplicate, stale, conflicting, or low-confidence facts before publishing."],
              ["Chart handoff", "Publish a FHIR Chart with provenance and review boundaries attached."],
            ].map(([title, body]) => (
              <div key={title} className="rounded-xl border border-[#e9eaef] p-4">
                <p className="text-sm font-semibold text-[#1c1c1e]">{title}</p>
                <p className="mt-1 text-sm leading-6 text-[#667085]">{body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl bg-[#f7fffc] p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <h2 className="text-lg font-semibold text-[#0f172a]">Future home-page canvas idea</h2>
          <p className="mt-2 text-sm leading-6 text-[#35524d]">
            The interactive home page can use a canvas-style map of the journey: portals and files flowing into a cleaning
            workspace, then into FHIR Charts, Clinical Insights, Marketplace, and Internal Tools. This page keeps the first
            version concrete while leaving room for that richer navigation prototype.
          </p>
          <Link to={chartHref} className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-[#0f766e]">
            View resulting FHIR Chart
            <ArrowRight size={14} />
          </Link>
        </div>
      </section>
    </main>
  );
}
