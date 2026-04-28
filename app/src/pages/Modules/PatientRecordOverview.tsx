import { Database, MessageSquareText } from "lucide-react";

export function PatientRecordOverview() {
  return (
    <main className="mx-auto max-w-6xl space-y-5 p-6">
      <section className="rounded-3xl bg-white p-7 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
          <Database size={13} />
          Patient record overview
        </p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[#1c1c1e]">
          The longitudinal source of truth
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[#667085]">
          This module is the neutral record layer. Use it to orient around demographics, longitudinal care history,
          conditions, medications, allergies, immunizations, labs, and FHIR source coverage before entering a workflow.
        </p>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        {[
          ["Patient Summary", "A concise chart orientation with demographics, care activity, conditions, medications, allergies, labs, and source links."],
          ["History and Care Journey", "Longitudinal views for encounters, procedures, medications, immunizations, and major care episodes."],
          ["FHIR Data", "Development-facing source coverage, resource counts, and raw bundle inspection for trust and debugging."],
        ].map(([title, body]) => (
          <div key={title} className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <h2 className="text-base font-semibold text-[#1c1c1e]">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
          </div>
        ))}
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
          <MessageSquareText size={13} />
          Future record agent
        </p>
        <h2 className="mt-2 text-base font-semibold text-[#1c1c1e]">Ask neutral questions about the source chart</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[#667085]">
          The Patient Record agent should answer chart-grounded questions and cite source evidence. It should stay separate from
          Pre-Op, Clinical Trials, and Medication Access agents because those modules have different tools, goals, and risk posture.
        </p>
      </section>
    </main>
  );
}
