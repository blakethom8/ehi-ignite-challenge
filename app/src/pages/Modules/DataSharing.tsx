import { Link, useLocation, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  FileJson2,
  FileText,
  MessageSquareText,
  ShieldCheck,
  Share2,
  UserRound,
} from "lucide-react";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${patientId}` : path;
}

function StepCard({ step, title, body }: { step: string; title: string; body: string }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#eef1ff] text-sm font-semibold text-[#5b76fe]">
        {step}
      </div>
      <h2 className="mt-4 text-base font-semibold text-[#1c1c1e]">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
    </div>
  );
}

function PacketRow({ label, detail, status }: { label: string; detail: string; status: string }) {
  return (
    <div className="flex flex-col gap-3 border-b border-[#e9eaef] py-4 last:border-0 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-sm font-semibold text-[#1c1c1e]">{label}</p>
        <p className="mt-1 text-sm leading-6 text-[#667085]">{detail}</p>
      </div>
      <span className="w-fit rounded-full bg-[#eef1ff] px-2.5 py-1 text-xs font-semibold text-[#5b76fe]">{status}</span>
    </div>
  );
}

export function DataSharing() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const patientId = searchParams.get("patient");
  const secondOpinion = location.pathname.startsWith("/second-opinion");

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              {secondOpinion ? <MessageSquareText size={13} /> : <Share2 size={13} />}
              {secondOpinion ? "Second opinion module" : "Data sharing"}
            </p>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
              {secondOpinion ? "Package the FHIR Chart for specialist review" : "Share a scoped evidence packet"}
            </h1>
            <p className="mt-3 text-base leading-7 text-[#667085]">
              Sharing should start from the unified patient record, not a pile of raw files. The platform chooses scope,
              preserves provenance, and sends a review-ready packet with explicit consent and expiration.
            </p>
          </div>
          <div className="rounded-2xl bg-[#fafbff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:min-w-[280px]">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-[#00b473]" />
              <p className="text-sm font-semibold text-[#1c1c1e]">Prototype only</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              This flow defines the product shape. Real consent, delivery, and audit backend are intentionally out of scope for this pass.
            </p>
          </div>
        </div>
      </section>

      {!patientId && (
        <section className="rounded-2xl border border-dashed border-[#c7cad5] bg-white p-5">
          <div className="flex items-center gap-2">
            <UserRound size={18} className="text-[#a5a8b5]" />
            <p className="text-sm font-semibold text-[#1c1c1e]">Select a patient to make this packet patient-specific.</p>
          </div>
          <p className="mt-2 text-sm leading-6 text-[#667085]">
            The current page can still show the concept without a selected patient.
          </p>
        </section>
      )}

      <section className="grid gap-4 md:grid-cols-3">
        <StepCard
          step="1"
          title="Choose packet scope"
          body="Pick clinical summary, active medication episodes, current labs, source conflicts, and module outputs."
        />
        <StepCard
          step="2"
          title="Select recipients"
          body="Send to a specialist reviewer, care team member, or marketplace module with time-limited access."
        />
        <StepCard
          step="3"
          title="Preserve evidence"
          body="Attach source systems, normalized rows, rule outputs, and review-required gaps to every shared fact."
        />
      </section>

      <section className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-[#1c1c1e]">Packet Builder</h2>
              <p className="mt-1 text-sm text-[#667085]">A shareable packet is a scoped view of the unified patient record.</p>
            </div>
            <Link
              to={withPatient("/charts", patientId)}
              className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-semibold text-[#5b76fe] hover:bg-[#eef1ff]"
            >
              FHIR Chart
              <ArrowRight size={14} />
            </Link>
          </div>

          <div className="mt-5">
            <PacketRow label="Clinical summary" detail="Demographics, active problems, major medication context, and recent care activity." status="Included" />
            <PacketRow label="Medication episodes" detail="Active and historical medication courses with drug class and source rows." status="Included" />
            <PacketRow label="Latest key labs" detail="Most recent numeric observations by LOINC with date, value, and unit." status="Included" />
            <PacketRow label="Source conflicts" detail="Fields where systems disagree or the platform needs human review." status="Included" />
            <PacketRow label="Raw FHIR appendix" detail="Optional source bundle or document bundle export for deep review." status="Optional" />
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <div className="flex items-center gap-2">
              <Clock3 size={18} className="text-[#5b76fe]" />
              <h2 className="text-lg font-semibold text-[#1c1c1e]">Recipient Access</h2>
            </div>
            <div className="mt-5 space-y-3">
              {[
                ["Neurosurgery reviewer", "7 days", "Selected"],
                ["Primary care clinician", "30 days", "Selected"],
                ["Marketplace specialist", "Pending", "Optional"],
              ].map(([recipient, duration, status]) => (
                <div key={recipient} className="flex items-center justify-between gap-3 rounded-xl border border-[#e9eaef] p-3">
                  <div>
                    <p className="text-sm font-semibold text-[#1c1c1e]">{recipient}</p>
                    <p className="mt-1 text-xs text-[#667085]">{duration}</p>
                  </div>
                  <span className="rounded-full bg-[#f5f6f8] px-2 py-1 text-[11px] font-semibold text-[#555a6a]">{status}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <div className="flex items-center gap-2">
              <FileText size={18} className="text-[#5b76fe]" />
              <h2 className="text-lg font-semibold text-[#1c1c1e]">Export Formats</h2>
            </div>
            <div className="mt-5 grid gap-3">
              {[
                [FileText, "Human-readable brief", "Clinician-facing PDF or web packet."],
                [FileJson2, "Evidence packet JSON", "Source refs, normalized facts, module outputs."],
                [CheckCircle2, "FHIR document bundle", "Standards-aligned exchange artifact."],
              ].map(([Icon, title, body]) => {
                const ExportIcon = Icon as typeof FileText;
                return (
                  <div key={String(title)} className="flex gap-3 rounded-xl bg-[#fafbff] p-3">
                    <ExportIcon size={17} className="mt-0.5 shrink-0 text-[#5b76fe]" />
                    <div>
                      <p className="text-sm font-semibold text-[#1c1c1e]">{String(title)}</p>
                      <p className="mt-1 text-sm leading-6 text-[#667085]">{String(body)}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
