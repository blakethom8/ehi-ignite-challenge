import { Activity, ClipboardCheck, MessageSquareText, Pill, Stethoscope } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const PREOP_AREAS: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: ClipboardCheck,
    title: "Patient Briefing",
    body: "The 30-second patient-specific surgical disposition with supporting chart evidence.",
  },
  {
    icon: Pill,
    title: "Medication Holds",
    body: "Active medication classes that may require holding, bridging, monitoring, or anesthesia review.",
  },
  {
    icon: Stethoscope,
    title: "Anesthesia Handoff",
    body: "A compact handoff view for conditions, labs, risks, and perioperative coordination.",
  },
];

export function PreOpOverview() {
  return (
    <main className="mx-auto max-w-6xl space-y-5 p-6">
      <section className="rounded-3xl bg-white p-7 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
          <Activity size={13} />
          Pre-Op support overview
        </p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[#1c1c1e]">
          A surgical briefing workspace
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[#667085]">
          This module is for the pre-surgery question: what in the chart changes readiness, medication holds,
          anesthesia handoff, or day-of-surgery coordination? Patient-specific disposition belongs in Patient Briefing.
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
        <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
          <MessageSquareText size={13} />
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
