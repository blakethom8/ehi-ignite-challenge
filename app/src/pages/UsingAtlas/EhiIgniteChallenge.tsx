import { useState } from "react";
import { BookOpen, ChevronDown, ChevronUp, FileText, GitBranch, ShieldCheck } from "lucide-react";
import { PageHeader } from "./components/PageHeader";

function ChallengeCard({
  icon: Icon,
  label,
  role,
  body,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  role: string;
  body: string;
}) {
  return (
    <div className="flex flex-col rounded-xl border border-[#e7eaf2] bg-white p-5">
      <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-[#eef1ff]">
        <Icon size={18} className="text-[#5b76fe]" />
      </div>
      <p className="text-base font-semibold text-[#1d2433]">{label}</p>
      <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-wide text-[#5b76fe]">{role}</p>
      <p className="mt-2.5 text-sm leading-relaxed text-[#4a5168]">{body}</p>
    </div>
  );
}

function ChallengeLink({
  label,
  description,
  to,
}: {
  label: string;
  description: string;
  to: string;
}) {
  return (
    <a
      href={to}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex items-start gap-4 rounded-xl border border-[#e7eaf2] bg-white p-4 transition-colors hover:border-[#cfd7ff] hover:bg-[#fdfdff]"
    >
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-[#1d2433]">{label}</p>
        <p className="mt-0.5 text-sm text-[#6b7390]">{description}</p>
      </div>
      <span className="mt-0.5 shrink-0 text-[#9aa5c0] transition-transform group-hover:translate-x-0.5 group-hover:text-[#5b76fe]">
        →
      </span>
    </a>
  );
}

const PROPOSAL_SECTIONS = [
  {
    title: "What we proposed",
    body: [
      "EHI Atlas was submitted as a patient-owned, portable evidence workspace for fragmented Electronic Health Information.",
      "The proposal centers on turning FHIR bundles, C-CDAs, PDFs, portal downloads, and other patient-held records into one harmonized clinical workspace with provenance, summaries, safety checks, charts, and handoff-ready outputs.",
    ],
  },
  {
    title: "Problem and solution",
    body: [
      "The proposal argues that EHI is increasingly available but still not usable enough for real care decisions. Patients and clinicians may have the files, but they still struggle to answer simple, practical questions about medications, lab trends, missing context, and which source supports which fact.",
      "Atlas responds by structuring records before asking AI to reason over them. The durable product is the evidence workspace itself, not a one-off model summary.",
    ],
  },
  {
    title: "How the workflow works",
    body: [
      "The submitted workflow moves through Source Intake, Harmonized Record, Patient Context, Publish Chart, and portable workspace packaging.",
      "Each source is prepared, mapped into FHIR-compatible facts, linked back to provenance, and then exposed through charts, assistant views, review queues, and future command-line or agent-facing interfaces.",
    ],
  },
  {
    title: "Prototype and trust posture",
    body: [
      "The Phase 1 submission was explicit that the prototype already demonstrates the architecture and user-facing surfaces, while operational controls are still maturing.",
      "Trust in the proposal comes from deterministic harmonization, source-backed evidence, bounded AI over prepared context, patient-controlled sharing, and a clear path to stronger privacy, security, audit, and deployment controls in later phases.",
    ],
  },
];

function ProposalDocumentAccordion() {
  const [open, setOpen] = useState(false);

  return (
    <section className="overflow-hidden rounded-xl border border-[#e7eaf2] bg-white">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-start gap-4 p-4 text-left transition-colors hover:bg-[#fdfdff]"
        aria-expanded={open}
      >
        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#eef1ff]">
          <FileText size={17} className="text-[#5b76fe]" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-[#1d2433]">Proposal document</p>
          <p className="mt-0.5 text-sm text-[#6b7390]">
            Read the Phase 1 submission inline as a drop-down overview of the problem, proposed solution, workflow, and prototype posture.
          </p>
        </div>
        <span className="mt-1 shrink-0 text-[#9aa5c0]">
          {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </span>
      </button>

      {open && (
        <div className="border-t border-[#eef0f5] bg-[#fafbff] p-4">
          <div className="rounded-xl border border-[#dfe4ea] bg-white p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#5b76fe]">
              Phase 1 proposal readme
            </p>
            <h3 className="mt-2 text-lg font-semibold text-[#1d2433]">
              EHI Atlas: a patient-owned, portable evidence workspace for fragmented EHI
            </h3>
            <p className="mt-2 text-sm leading-6 text-[#4a5168]">
              This section adapts the submitted proposal document into a readable in-app summary so reviewers can understand the design without leaving the prototype.
            </p>
            <a
              href="https://github.com/blakethom8/ehi-ignite-challenge/blob/master/report/ehi-atlas-phase1-submission-review.pdf"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-2 rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm font-semibold text-[#33415b] transition-colors hover:border-[#5b76fe] hover:text-[#5b76fe]"
            >
              Open submitted PDF
            </a>
          </div>

          <div className="mt-4 space-y-3">
            {PROPOSAL_SECTIONS.map((section) => (
              <div key={section.title} className="rounded-xl border border-[#dfe4ea] bg-white p-4">
                <h4 className="text-sm font-semibold uppercase tracking-[0.12em] text-[#5b76fe]">
                  {section.title}
                </h4>
                <div className="mt-3 space-y-3">
                  {section.body.map((paragraph) => (
                    <p key={paragraph} className="text-sm leading-6 text-[#4a5168]">
                      {paragraph}
                    </p>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

export function EhiIgniteChallenge() {
  return (
    <article>
      <PageHeader
        title="EHI Ignite Challenge"
        subtitle="Why Atlas was built, what was submitted, and how the current prototype should be understood."
      />

      <section className="mb-10">
        <p className="text-[16px] leading-[1.7] text-[#1d2433]">
          Atlas was built as Blake Thomson&apos;s submission to the HHS EHI Ignite Challenge: a design and prototype effort focused on making fragmented Electronic Health Information usable for real review workflows instead of just export compliance.
        </p>
        <p className="mt-4 text-[16px] leading-[1.7] text-[#4a5168]">
          The current hosted app is a working prototype. It demonstrates the product direction, information architecture, data-preparation pipeline, and review surfaces that were submitted for challenge evaluation, while still remaining a work in progress rather than a finished production deployment.
        </p>
        <p className="mt-4 text-[16px] leading-[1.7] text-[#4a5168]">
          That means the strongest claim here is not that every operational detail is complete today. It is that the core idea, workflow, and evidence model are concrete enough to inspect, test, and extend.
        </p>
      </section>

      <section className="mb-10">
        <div className="grid gap-4 md:grid-cols-3">
          <ChallengeCard
            icon={GitBranch}
            label="Challenge status"
            role="Phase 1 prototype"
            body="This repository captures the concept, interaction model, and working demo surfaces submitted for challenge review. It is intentionally ahead on workflow design and still maturing on operational hardening."
          />
          <ChallengeCard
            icon={ShieldCheck}
            label="Current posture"
            role="Prototype disclosure"
            body="Public demo paths use synthetic data where possible, while hosted upload paths remain proof-of-concept surfaces. The current site should not be interpreted as a production-hardened or HIPAA-reviewed environment."
          />
          <ChallengeCard
            icon={BookOpen}
            label="About Blake"
            role="Builder background"
            body="Blake Thomson brings healthcare data strategy and business-development experience, with a focus on turning fragmented health-system data into usable operational and clinical tools."
          />
        </div>
      </section>

      <section className="mb-2">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Submission materials
        </h2>
        <p className="mb-5 text-sm leading-relaxed text-[#6b7390]">
          The repo, PDF packet, and supporting report folder are all linked here so reviewers can move directly from the live prototype to the submitted materials.
        </p>
        <div className="flex flex-col gap-2.5">
          <ChallengeLink
            label="GitHub repository"
            description="Source code, architecture docs, and the running Atlas prototype."
            to="https://github.com/blakethom8/ehi-ignite-challenge"
          />
          <ProposalDocumentAccordion />
        </div>
      </section>
    </article>
  );
}
