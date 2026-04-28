import { Archive, Database, FileJson2, GitBranch, Layers3, PackageCheck, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

function ContractCard({
  icon: Icon,
  title,
  owner,
  body,
  fields,
}: {
  icon: LucideIcon;
  title: string;
  owner: string;
  body: string;
  fields: string[];
}) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-[rgb(213_235_229)_0px_0px_0px_1px]">
      <div className="flex items-start justify-between gap-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#dff6ef] text-[#0f766e]">
          <Icon size={18} />
        </div>
        <span className="rounded-full bg-[#edf9f5] px-2.5 py-1 text-xs font-semibold text-[#0f766e]">{owner}</span>
      </div>
      <h2 className="mt-4 text-base font-semibold text-[#0f172a]">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-[#35524d]">{body}</p>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {fields.map((field) => (
          <span key={field} className="rounded-full bg-white px-2 py-1 text-[11px] font-semibold text-[#55706c] shadow-[rgb(213_235_229)_0px_0px_0px_1px]">
            {field}
          </span>
        ))}
      </div>
    </div>
  );
}

export function DataCatalog() {
  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(213_235_229)_0px_0px_0px_1px] lg:p-8">
        <p className="inline-flex items-center gap-2 rounded-full bg-[#dff6ef] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#0f766e]">
          <Archive size={13} />
          Internal data catalog
        </p>
        <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#0f172a] lg:text-4xl">
          Platform contracts for module builders
        </h1>
        <p className="mt-3 max-w-4xl text-base leading-7 text-[#35524d]">
          Data Lab explains FHIR. Data Catalog explains what this platform exposes after aggregation: normalized objects,
          SQL-on-FHIR tables, derived views, evidence packets, and module manifests.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ContractCard
          icon={Database}
          title="AggregatedPatientRecord"
          owner="Platform"
          body="The patient-owned FHIR Chart created after sources are connected, normalized, and reconciled."
          fields={["identity", "sources", "facts", "provenance", "conflicts"]}
        />
        <ContractCard
          icon={ShieldCheck}
          title="EvidencePacket"
          owner="Platform"
          body="The portable evidence object that ties every module output back to source resources and normalized rows."
          fields={["source refs", "row refs", "rule id", "trust tier", "output"]}
        />
        <ContractCard
          icon={PackageCheck}
          title="ModuleManifest"
          owner="Module"
          body="The declaration each marketplace module provides before it can run against the FHIR Chart."
          fields={["inputs", "outputs", "publisher", "version", "review status"]}
        />
        <ContractCard
          icon={GitBranch}
          title="RulePack"
          owner="Module"
          body="Workflow-scoped deterministic rules, evidence requirements, and review-required boundaries."
          fields={["rules", "scope", "evidence", "review states", "out-of-scope"]}
        />
      </section>

      <section className="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-2xl bg-white p-5 shadow-[rgb(213_235_229)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <Layers3 size={18} className="text-[#0f766e]" />
            <h2 className="text-lg font-semibold text-[#0f172a]">Warehouse layers</h2>
          </div>
          <div className="mt-5 space-y-3">
            {[
              ["Pure ViewDefinition tables", "patient, condition, medication_request, observation, encounter"],
              ["Filtered subset views", "condition_active as the problem-list convenience layer"],
              ["Enriched columns", "medication_request.drug_class from deterministic classification"],
              ["Derived artifacts", "medication_episode and observation_latest for workflow-ready questions"],
            ].map(([title, body]) => (
              <div key={title} className="rounded-xl border border-[#d5ebe5] p-4">
                <p className="text-sm font-semibold text-[#0f172a]">{title}</p>
                <p className="mt-1 text-sm leading-6 text-[#35524d]">{body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl bg-white p-5 shadow-[rgb(213_235_229)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <FileJson2 size={18} className="text-[#0f766e]" />
            <h2 className="text-lg font-semibold text-[#0f172a]">Module input contract</h2>
          </div>
          <div className="mt-5 overflow-hidden rounded-xl border border-[#d5ebe5]">
            <div className="grid grid-cols-[1fr_1.1fr_1fr] gap-3 bg-[#edf9f5] px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-[#55706c]">
              <span>Input</span>
              <span>Backed by</span>
              <span>First consumers</span>
            </div>
            {[
              ["active_conditions", "condition_active", "Pre-Op, Trials"],
              ["medication_episodes", "medication_episode", "Pre-Op, Med Access"],
              ["latest_observations", "observation_latest", "Pre-Op, Trials"],
              ["source_conflicts", "future aggregation contract", "Sharing, Second Opinion"],
              ["evidence_packet", "future evidence contract", "All modules"],
            ].map(([input, backedBy, consumers]) => (
              <div key={input} className="grid grid-cols-[1fr_1.1fr_1fr] gap-3 border-t border-[#d5ebe5] px-4 py-3 text-sm">
                <span className="font-semibold text-[#0f172a]">{input}</span>
                <span className="text-[#35524d]">{backedBy}</span>
                <span className="text-[#35524d]">{consumers}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
