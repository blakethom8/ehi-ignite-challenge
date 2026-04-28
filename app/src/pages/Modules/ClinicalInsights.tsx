import { Link, useSearchParams } from "react-router-dom";
import { Activity, ArrowRight, HeartHandshake, MessageSquareText, ShieldAlert, Stethoscope, UserRoundCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${patientId}` : path;
}

function InsightCard({
  icon: Icon,
  title,
  status,
  body,
  to,
  outputs,
}: {
  icon: LucideIcon;
  title: string;
  status: string;
  body: string;
  to: string;
  outputs: string[];
}) {
  return (
    <Link
      to={to}
      className="group flex min-h-[280px] flex-col rounded-2xl bg-white p-5 no-underline shadow-[rgb(224_226_232)_0px_0px_0px_1px] transition-colors hover:bg-[#fffdf9]"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#ffe6cd] text-[#744000]">
          <Icon size={20} />
        </div>
        <span className="rounded-full bg-[#fff1df] px-2.5 py-1 text-xs font-semibold text-[#9a5a16]">{status}</span>
      </div>
      <h2 className="mt-5 text-lg font-semibold text-[#1c1c1e]">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
      <div className="mt-5">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Produces</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {outputs.map((output) => (
            <span key={output} className="rounded-full bg-[#fff1df] px-2 py-1 text-[11px] font-semibold text-[#9a5a16]">
              {output}
            </span>
          ))}
        </div>
      </div>
      <div className="mt-auto flex items-center gap-1 pt-6 text-sm font-semibold text-[#9a5a16]">
        Open module
        <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
      </div>
    </Link>
  );
}

export function ClinicalInsights() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <p className="inline-flex items-center gap-2 rounded-full bg-[#fff1df] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">
          <Activity size={13} />
          Clinical insights market
        </p>
        <h1 className="mt-5 max-w-4xl text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
          Private modules for understanding and acting on the patient chart
        </h1>
        <p className="mt-3 max-w-4xl text-base leading-7 text-[#667085]">
          These modules stay inside the PHI-controlled workspace. They use the FHIR Chart to create briefs, review queues,
          care summaries, and cited answers without sending patient data into an external marketplace flow.
        </p>
      </section>

      <section className="rounded-[24px] border border-[#f6dfc9] bg-[#fff8f1] p-5">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">Private clinical modules</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">Clinical insights built on the FHIR Chart</h2>
          </div>
          <p className="max-w-xl text-sm leading-6 text-[#667085]">
            This is the right home for pre-op, chart Q&A, caregiver views, and patient-specific clinical profiles.
          </p>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <InsightCard
            icon={Activity}
            title="Pre-Op Support"
            status="Installed"
            body="Turns the FHIR Chart into a fast surgical readiness workspace for medication holds, anesthesia context, and pre-op risk review."
            outputs={["Briefing", "Medication holds", "Anesthesia handoff"]}
            to={withPatient("/preop", patientId)}
          />
          <InsightCard
            icon={UserRoundCheck}
            title="Clinical Profile"
            status="Concept"
            body="Creates a patient-readable profile of active problems, care history, and top questions that need review."
            outputs={["Plain-language profile", "Top concerns", "Question list"]}
            to={withPatient("/charts", patientId)}
          />
          <InsightCard
            icon={MessageSquareText}
            title="Chart Q&A"
            status="Concept"
            body="Lets a patient, caregiver, or clinician ask chart-grounded questions with source-linked answers and review flags."
            outputs={["Cited answers", "Follow-up questions", "Review flags"]}
            to={withPatient("/explorer/assistant", patientId)}
          />
          <InsightCard
            icon={HeartHandshake}
            title="Caregiver View"
            status="Concept"
            body="Creates a limited, consent-scoped view for a trusted helper supporting the patient's care."
            outputs={["Care summary", "Question guide", "Access boundary"]}
            to={withPatient("/sharing", patientId)}
          />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {[
          [ShieldAlert, "Review boundary", "Marks inferred, partial, stale, conflicting, or high-risk findings before action."],
          [Stethoscope, "Clinician posture", "Clinical outputs should be brief, cited, and scoped to the workflow question."],
          [MessageSquareText, "Agent surface", "The split-screen agent belongs here first: chart evidence on the left, dialogue and next actions on the right."],
        ].map(([Icon, title, body]) => {
          const TypedIcon = Icon as LucideIcon;
          return (
            <div key={title as string} className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#fff1df] text-[#9a5a16]">
                <TypedIcon size={18} />
              </div>
              <h2 className="mt-4 text-base font-semibold text-[#1c1c1e]">{title as string}</h2>
              <p className="mt-2 text-sm leading-6 text-[#667085]">{body as string}</p>
            </div>
          );
        })}
      </section>
    </main>
  );
}
