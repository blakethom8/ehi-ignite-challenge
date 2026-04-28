import { Link, useSearchParams } from "react-router-dom";
import { Activity, ArrowRight, ClipboardCheck, FileText, MessageSquareText, ShieldAlert, Stethoscope } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const PREOP_AREAS: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: ClipboardCheck,
    title: "30-second surgical brief",
    body: "Summarizes what matters before a procedure: readiness blockers, open questions, and the evidence behind them.",
  },
  {
    icon: FileText,
    title: "Inputs it expects",
    body: "Reads normalized chart facts and can reference sibling modules such as clearance, medication holds, labs, and problem review.",
  },
  {
    icon: ShieldAlert,
    title: "Review boundary",
    body: "Marks sparse, stale, conflicting, or inferred findings so the module does not overstate what the chart supports.",
  },
];

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${patientId}` : path;
}

export function PreOpOverview() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  return (
    <main className="mx-auto max-w-6xl space-y-5 p-6">
      <section className="rounded-3xl bg-white p-7 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
          <Activity size={13} />
          Clinical Insight Module
        </p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[#1c1c1e]">Pre-Op Support</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[#667085]">
          This is one standalone module inside Clinical Insights. It is scoped to a pre-surgery question: what in
          this patient's chart changes readiness, anesthesia handoff, day-of-surgery coordination, or the follow-up
          questions a clinician should review?
        </p>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        {PREOP_AREAS.map(({ icon: Icon, title, body }) => (
          <div key={title} className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
              <Icon size={18} />
            </div>
            <h2 className="text-base font-semibold text-[#1c1c1e]">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
          </div>
        ))}
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Sibling modules</p>
            <h2 className="mt-1 text-base font-semibold text-[#1c1c1e]">Pre-Op Support does not own the whole workspace</h2>
          </div>
          <p className="max-w-2xl text-sm leading-6 text-[#667085]">
            Clearance, Medication Holds, Patient Briefing, and Chart Q&A are separate Clinical Insights modules. Pre-Op
            Support can consume their outputs, but Clinical Insights is the parent workspace.
          </p>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {[
            ["/explorer/clearance", ClipboardCheck, "Clearance", "Readiness check"],
            ["/explorer/safety", ShieldAlert, "Medication Holds", "Medication safety review"],
            ["/explorer/assistant", MessageSquareText, "Chart Q&A", "Cited clinical questions"],
          ].map(([path, Icon, title, body]) => {
            const TypedIcon = Icon as LucideIcon;
            return (
              <Link
                key={title as string}
                to={withPatient(path as string, patientId)}
                className="group rounded-xl border border-[#e9eaef] bg-[#fbfcff] p-4 no-underline transition-colors hover:border-[#dfe4ff] hover:bg-[#f7f8ff]"
              >
                <div className="flex items-center gap-2 text-sm font-semibold text-[#1c1c1e]">
                  <TypedIcon size={15} className="text-[#5b76fe]" />
                  {title as string}
                </div>
                <p className="mt-2 text-sm text-[#667085]">{body as string}</p>
                <p className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-[#5b76fe]">
                  Open sibling module
                  <ArrowRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                </p>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
          <Stethoscope size={13} />
          Future pre-op agent
        </p>
        <h2 className="mt-2 text-base font-semibold text-[#1c1c1e]">A dedicated AI chart assistant for surgical review</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[#667085]">
          The Pre-Op agent should be scoped to surgical risk questions, medication hold reasoning, anesthesia-ready
          summaries, and cited chart evidence. It should not share the same prompt harness as trials or affordability research.
        </p>
      </section>
    </main>
  );
}
