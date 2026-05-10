import { Link } from "react-router-dom";
import {
  ArrowRight,
  EyeOff,
  FileSearch,
  Lock,
  Shield,
  ShieldOff,
  Tag,
} from "lucide-react";
import { PageHeader } from "./components/PageHeader";

// ─── Trust property card ─────────────────────────────────────────────────────

interface TrustCardProps {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  body: string;
}

function TrustCard({ icon: Icon, title, body }: TrustCardProps) {
  return (
    <div className="flex flex-col rounded-xl border border-[#e7eaf2] bg-white p-5">
      <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-[#eef1ff]">
        <Icon size={18} className="text-[#5b76fe]" />
      </div>
      <p className="text-[15px] font-semibold text-[#1d2433]">{title}</p>
      <p className="mt-2.5 flex-1 text-[14px] leading-[1.6] text-[#4a5168]">{body}</p>
    </div>
  );
}

// ─── Privacy bullet ──────────────────────────────────────────────────────────

interface PrivacyItemProps {
  label: string;
  detail: string;
}

function PrivacyItem({ label, detail }: PrivacyItemProps) {
  return (
    <li className="flex gap-3 py-2.5 border-b border-[#f0f1f7] last:border-0">
      <span className="mt-0.5 h-1.5 w-1.5 shrink-0 translate-y-[6px] rounded-full bg-[#5b76fe]" />
      <span className="text-[14px] leading-[1.6] text-[#4a5168]">
        <span className="font-semibold text-[#1d2433]">{label}</span>
        {" — "}
        {detail}
      </span>
    </li>
  );
}

// ─── Section link row ─────────────────────────────────────────────────────────

interface SectionLinkProps {
  label: string;
  description: string;
  to: string;
  external?: boolean;
}

function SectionLink({ label, description, to, external }: SectionLinkProps) {
  const className =
    "group flex items-start gap-4 rounded-xl border border-[#e7eaf2] bg-white p-4 transition-colors hover:border-[#cfd7ff] hover:bg-[#fdfdff]";

  const inner = (
    <>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-[#1d2433]">{label}</p>
        <p className="mt-0.5 text-sm text-[#6b7390]">{description}</p>
      </div>
      <ArrowRight
        size={16}
        className="mt-0.5 shrink-0 text-[#9aa5c0] transition-transform group-hover:translate-x-0.5 group-hover:text-[#5b76fe]"
      />
    </>
  );

  if (external) {
    return (
      <a href={to} target="_blank" rel="noopener noreferrer" className={className}>
        {inner}
      </a>
    );
  }

  return (
    <Link to={to} className={className}>
      {inner}
    </Link>
  );
}

// ─── Trust property data ──────────────────────────────────────────────────────

const TRUST_CARDS: TrustCardProps[] = [
  {
    icon: Tag,
    title: "Typed clinical facts",
    body: "Observations, Conditions, Medications, and other resources are stored as structured FHIR-shaped objects. AI consumers query typed facts — not raw document text. The schema constrains what the model can claim.",
  },
  {
    icon: FileSearch,
    title: "Citation edges",
    body: "Every fact retains a provenance edge back to its source document, page reference, and extraction method. An assistant answer that cannot cite is a bug, not a feature. Orphaned claims are rejected at harmonization time.",
  },
  {
    icon: EyeOff,
    title: "Evidence packet discipline",
    body: "Applications never receive the full bundle. Each query is served a scoped packet of typed facts relevant to that specific question. The AI sees the minimum necessary context — bounded structurally, not just by prompt instruction.",
  },
  {
    icon: Lock,
    title: "Access scopes",
    body: "Role-based access control lives at the bundle level. A patient grants access to a chart snapshot, not the archive. Scopes can be revoked. Every access generates an audit event with timestamp, requesting entity, and evidence scope.",
  },
];

// ─── Privacy commitments ──────────────────────────────────────────────────────

const PRIVACY_ITEMS: PrivacyItemProps[] = [
  {
    label: "Encryption at rest and in transit",
    detail: "PHI storage targets AES-256 at rest; all API and web traffic uses TLS 1.3.",
  },
  {
    label: "HIPAA BAA-capable deployment",
    detail:
      "Production deployment paths include Hetzner Cloud, AWS, and Azure with signed BAAs.",
  },
  {
    label: "Audit logging",
    detail:
      "All PHI access is logged with timestamp, requesting entity, and evidence scope. Audit trails are retained for compliance review.",
  },
  {
    label: "Private inference option",
    detail:
      "Local model paths — Gemma 4 31B via Ollama — support on-premise or air-gapped deployment where PHI must not leave the environment.",
  },
  {
    label: "Data minimization",
    detail:
      "Applications receive evidence packets, never raw record dumps. The assistant never holds unrestricted bundle access.",
  },
];

// ─── Page ────────────────────────────────────────────────────────────────────

export function TrustworthyAi() {
  return (
    <article>
      <PageHeader
        title="Trustworthy AI"
        subtitle="Why trust comes from the bundle architecture, not the AI prompt."
      />

      {/* ── The bundle is the trust boundary ──────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          The bundle is the trust boundary
        </h2>
        <p className="text-[15px] leading-[1.65] text-[#4a5168]">
          Most "trustworthy AI" claims live at the prompt level — guardrails written into
          system instructions that the model can drift from, be overridden in, or simply
          fail to honor under unusual input. Atlas pushes trust down to the bundle layer:
          typed clinical facts with citation edges, access scopes baked into the artifact
          itself, evidence-packet discipline encoded structurally.
        </p>
        <p className="mt-4 text-[15px] leading-[1.65] text-[#4a5168]">
          This means every application that consumes the bundle inherits the trust
          properties — Atlas's own assistant, third-party Marketplace skills, and portable
          exports alike. The pipeline produces a trust-carrying artifact; applications don't
          have to implement trust separately.
        </p>
        <blockquote className="mt-5 rounded-r-lg border-l-[3px] border-[#5b76fe] bg-[#eef1ff] py-3 pl-4 pr-5">
          <p className="text-[15px] font-semibold leading-snug text-[#1d2433]">
            Parse once. Structure once. Validate once. Cite forever.
          </p>
        </blockquote>
      </section>

      {/* ── What the bundle gives applications ────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          What the bundle gives applications
        </h2>
        <p className="mb-5 text-[14px] leading-relaxed text-[#6b7390]">
          Four structural properties flow from the bundle to every application that consumes
          it. Each is a design constraint, not a runtime instruction.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          {TRUST_CARDS.map((card) => (
            <TrustCard key={card.title} {...card} />
          ))}
        </div>
      </section>

      {/* ── Privacy + deployment posture ──────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Privacy and deployment posture
        </h2>
        <p className="mb-4 text-[14px] leading-relaxed text-[#6b7390]">
          The Phase 1 prototype uses synthetic Synthea data and keeps PHI-like test
          artifacts out of source control. The architecture is designed for HIPAA-aware
          deployment from day one.
        </p>
        <div className="rounded-xl border border-[#e7eaf2] bg-white px-5 pb-1 pt-2">
          <ul className="divide-y divide-[#f0f1f7]">
            {PRIVACY_ITEMS.map((item) => (
              <PrivacyItem key={item.label} {...item} />
            ))}
          </ul>
        </div>
      </section>

      {/* ── Missing-information discipline ────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Missing-information discipline
        </h2>
        <div className="flex gap-4">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#eef1ff]">
            <ShieldOff size={18} className="text-[#5b76fe]" />
          </div>
          <div>
            <p className="text-[15px] leading-[1.65] text-[#4a5168]">
              When a fact isn't in the bundle, the application says so explicitly. Atlas
              does not infer, guess, or fill in missing clinical data with LLM-generated
              content. This is enforced structurally: a missing field is{" "}
              <code className="rounded bg-[#f4f5f9] px-1.5 py-0.5 font-mono text-[13px] text-[#1d2433]">
                null
              </code>{" "}
              in a typed FHIR resource, not an LLM-authored placeholder.
            </p>
            <p className="mt-3 text-[15px] leading-[1.65] text-[#4a5168]">
              The assistant signals gaps: "no CBC result found in this record," "no
              anticoagulant flagged — verify with patient." These disclosures are determined
              by the bundle's structure, not by model judgment. The model cannot decide to
              omit a missing-information flag.
            </p>
          </div>
        </div>
        <blockquote className="mt-5 rounded-r-lg border-l-[3px] border-[#5b76fe] bg-[#eef1ff] py-3 pl-4 pr-5">
          <p className="text-[14px] leading-[1.6] text-[#4a5168]">
            <span className="font-semibold text-[#1d2433]">Example assistant pattern —</span>{" "}
            "Not yet cleared. Address medication holds and obtain missing baseline labs.
            See source records for each claim."
          </p>
          <p className="mt-2 text-[12px] text-[#6b7390]">
            Response grounded in 15 typed facts: safety flags, active medications, recent
            encounters, missing labs. Each claim links to a source provenance edge.
          </p>
        </blockquote>
      </section>

      {/* ── Open source note ──────────────────────────────────────────────── */}
      <section className="mb-10">
        <div className="flex gap-4 rounded-xl border border-[#e7eaf2] bg-white p-5">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#eef1ff]">
            <Shield size={18} className="text-[#5b76fe]" />
          </div>
          <div>
            <p className="text-[15px] font-semibold text-[#1d2433]">
              Trust properties are inspectable
            </p>
            <p className="mt-2 text-[14px] leading-[1.6] text-[#4a5168]">
              Atlas is open source. The harmonization logic, provenance graph, agent tools,
              and evidence-packet assembly are all in the repo — not hidden behind a model
              or a closed API. This means the trust claims here can be audited, not just
              asserted.
            </p>
            <a
              href="https://github.com/blakethom8/ehi-ignite-challenge"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2.5 inline-flex items-center gap-1.5 text-[13px] font-semibold text-[#5b76fe] hover:underline"
            >
              View the repository
              <ArrowRight size={13} />
            </a>
          </div>
        </div>
      </section>

      {/* ── Where to next ─────────────────────────────────────────────────── */}
      <section className="mb-2">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Where to next
        </h2>
        <div className="flex flex-col gap-2.5">
          <SectionLink
            label="Standards and ecosystem"
            description="FHIR R4, C-CDA, TEFCA, QHINs, and where Atlas fits in the landscape."
            to="/using-atlas/standards"
          />
          <SectionLink
            label="Application overview"
            description="How the four application surfaces — Charts, Insights, Export, Marketplace — consume the bundle."
            to="/using-atlas"
          />
          <SectionLink
            label="Open the patient explorer"
            description="See the safety panel, citations, and missing-information flags in a working prototype."
            to="/fhir-charts"
          />
        </div>
      </section>
    </article>
  );
}
