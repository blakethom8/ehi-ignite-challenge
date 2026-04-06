import { BookMarked, Database, Link2 } from "lucide-react";

interface DefinitionItem {
  resource: string;
  coreFields: string;
  interpretation: string;
  downstreamUse: string;
}

const CANONICAL_DEFINITIONS: DefinitionItem[] = [
  {
    resource: "PatientRecord.summary",
    coreFields: "name, birth_date, gender, race, ethnicity, city, state",
    interpretation: "Identity and demographic context used for risk framing and cohort analysis.",
    downstreamUse: "Overview header, population stratification, language/care-context cues",
  },
  {
    resource: "EncounterRecord",
    coreFields: "class_code, encounter_type, period.start/end, provider_org",
    interpretation: "Unit of clinical activity used to anchor timeline and event recency.",
    downstreamUse: "Timeline, encounter composition, recent event summaries",
  },
  {
    resource: "MedicationRecord",
    coreFields: "display, rxnorm_code, status, authored_on, dosage_text, reason_display",
    interpretation: "Prescription events collapsed into episodes for safety and longitudinal logic.",
    downstreamUse: "Safety panel, interaction checks, anesthesia handoff",
  },
  {
    resource: "ConditionRecord",
    coreFields: "display, clinical_status, onset_dt, abatement_dt, is_active",
    interpretation: "Problem-list context with active vs resolved state and temporal burden.",
    downstreamUse: "Condition acuity ranking, clearance domains, risk narratives",
  },
  {
    resource: "ObservationRecord",
    coreFields: "loinc_code, category, value_type, value_quantity, value_unit, effective_dt",
    interpretation: "Labs and vitals with trend direction and threshold semantics.",
    downstreamUse: "Key-labs panel, abnormal flags, distribution analysis",
  },
  {
    resource: "ProcedureRecord",
    coreFields: "display, performed_period, reason_display",
    interpretation: "Historical interventions and perioperative context.",
    downstreamUse: "Procedure history and case-relevance checks",
  },
  {
    resource: "ImmunizationRecord",
    coreFields: "display, cvx_code, status, occurrence_dt",
    interpretation: "Preventive history and exposure context.",
    downstreamUse: "Immunization timeline and vaccine coverage context",
  },
  {
    resource: "AllergyRecord",
    coreFields: "substance, criticality, category",
    interpretation: "Hard safety constraints that should always surface in pre-op workflows.",
    downstreamUse: "Safety warnings, contraindication context, anesthesia checklist",
  },
];

const DERIVED_DEFINITIONS = [
  {
    name: "Medication Episode",
    source: "Grouped MedicationRecord entries by normalized display/RxNorm",
    meaning: "Continuous treatment period with start, recency, and active status",
  },
  {
    name: "Risk Tier",
    source: "Complexity score + active critical class flags",
    meaning: "Simple / Moderate / Complex / Highly Complex prioritization",
  },
  {
    name: "Safety Flag",
    source: "Drug class classification + active/historical status",
    meaning: "Class-level surgical risk action with protocol note",
  },
  {
    name: "Field Coverage Label",
    source: "Corpus field profiler (% patients with populated field)",
    meaning: "Always / Usually / Sometimes / Rarely confidence guidance",
  },
];

export function AnalysisDefinitions() {
  return (
    <div className="mx-auto max-w-7xl px-6 py-8 lg:px-10">
      <section className="rounded-3xl border border-[#c7e7df] bg-[linear-gradient(140deg,#f8fffd_0%,#ebfaf5_45%,#fbfffe_100%)] p-6 lg:p-8">
        <p className="inline-flex items-center gap-2 rounded-full bg-[#d8f5ee] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#0f766e]">
          <BookMarked size={13} />
          Data Dictionary
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#0f172a] lg:text-4xl">
          Canonical Data Definitions
        </h1>
        <p className="mt-3 max-w-4xl text-sm leading-6 text-[#35524d] lg:text-base">
          These definitions are the contract between ingestion and product logic. If a feature cannot map to one of
          these canonical fields or derived definitions, we treat it as speculative and out-of-scope for clinical
          decision support.
        </p>
      </section>

      <section className="mt-6 overflow-hidden rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="overflow-x-auto">
          <table className="min-w-[860px] w-full border-collapse text-left">
            <thead>
              <tr className="bg-[#f7fffc]">
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#55706c]">Resource</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#55706c]">Core fields</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#55706c]">Interpretation</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#55706c]">Used by</th>
              </tr>
            </thead>
            <tbody>
              {CANONICAL_DEFINITIONS.map((item) => (
                <tr key={item.resource} className="border-t border-[#edf0f5] align-top">
                  <td className="px-4 py-3 text-sm font-semibold text-[#0f172a]">{item.resource}</td>
                  <td className="px-4 py-3 text-sm text-[#35524d]">{item.coreFields}</td>
                  <td className="px-4 py-3 text-sm text-[#35524d]">{item.interpretation}</td>
                  <td className="px-4 py-3 text-sm text-[#35524d]">{item.downstreamUse}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-7 grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="flex items-center gap-2 text-sm font-semibold text-[#0f172a]">
            <Database size={16} className="text-[#0f766e]" />
            Derived Definitions
          </p>
          <div className="mt-3 space-y-2.5">
            {DERIVED_DEFINITIONS.map((item) => (
              <div key={item.name} className="rounded-xl border border-[#e5f3ee] bg-[#f8fffc] p-3.5">
                <p className="text-sm font-semibold text-[#0f172a]">{item.name}</p>
                <p className="mt-1 text-xs text-[#55706c]">Source: {item.source}</p>
                <p className="mt-1 text-sm text-[#35524d]">{item.meaning}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="rounded-2xl border border-[#dae8f8] bg-[#f3f8ff] p-5">
          <p className="flex items-center gap-2 text-sm font-semibold text-[#1e3a8a]">
            <Link2 size={16} />
            Traceability Rule
          </p>
          <p className="mt-2 text-sm leading-6 text-[#244589]">
            Every insight must trace back to one of three layers: canonical parser fields, deterministic derived
            definitions, or documented enrichment output. This is the baseline for explainability and for contest
            reviewers validating methodological rigor.
          </p>
          <p className="mt-3 rounded-lg bg-white px-3 py-2 text-xs text-[#36538b]">
            Practical check: if a UI element has no field-level lineage, mark it as prototype-only and keep it out of
            clinical action paths.
          </p>
        </article>
      </section>
    </div>
  );
}
