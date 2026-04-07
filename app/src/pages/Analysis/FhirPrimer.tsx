import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  XCircle,
  FileJson2,
  Network,
  ShieldAlert,
  Layers,
  ExternalLink,
} from "lucide-react";
import { api } from "../../api/client";

// ── Collapsible JSON viewer ─────────────────────────────────────────────────

function JsonBlock({
  title,
  subtitle,
  json,
  annotations,
  defaultOpen = false,
}: {
  title: string;
  subtitle: string;
  json: string;
  annotations?: { line: string; note: string }[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-xl border border-[#d4e8e2] bg-white overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-[#f7fffc] transition-colors"
      >
        {open ? <ChevronDown size={14} className="text-[#0f766e]" /> : <ChevronRight size={14} className="text-[#0f766e]" />}
        <FileJson2 size={15} className="text-[#0f766e]" />
        <div className="flex-1">
          <span className="text-sm font-semibold text-[#0f172a]">{title}</span>
          <span className="ml-2 text-xs text-[#64748b]">{subtitle}</span>
        </div>
      </button>
      {open && (
        <div className="border-t border-[#e5f4ef]">
          <pre className="px-4 py-3 text-[13px] leading-[1.65] bg-[#0f172a] text-[#e2e8f0] overflow-x-auto">
            <code>{json}</code>
          </pre>
          {annotations && annotations.length > 0 && (
            <div className="px-4 py-3 bg-[#f0fdf9] border-t border-[#d4e8e2] space-y-1.5">
              {annotations.map((a, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <code className="shrink-0 rounded bg-[#0f766e]/10 px-1.5 py-0.5 font-mono text-[#0f766e]">{a.line}</code>
                  <span className="text-[#35524d]">{a.note}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Resource hierarchy node ─────────────────────────────────────────────────

function ResourceNode({
  name,
  codingSystem,
  count,
  description,
  children,
  color = "#0f766e",
}: {
  name: string;
  codingSystem?: string;
  count?: string;
  description: string;
  children?: React.ReactNode;
  color?: string;
}) {
  return (
    <div className="relative">
      <div className="flex items-start gap-3 py-1.5">
        <div
          className="mt-1 h-3 w-3 rounded-full shrink-0 border-2"
          style={{ borderColor: color, backgroundColor: `${color}20` }}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-[#0f172a]">{name}</span>
            {codingSystem && (
              <span className="text-[10px] font-mono rounded-full bg-[#f1f5f9] px-2 py-0.5 text-[#64748b]">
                {codingSystem}
              </span>
            )}
            {count && (
              <span className="text-[10px] font-semibold rounded-full bg-[#d8f5ee] px-2 py-0.5 text-[#0f766e]">
                {count}
              </span>
            )}
          </div>
          <p className="text-xs text-[#64748b] mt-0.5">{description}</p>
        </div>
      </div>
      {children && (
        <div className="ml-1.5 border-l-2 border-[#d4e8e2] pl-5 space-y-0.5">{children}</div>
      )}
    </div>
  );
}

// ── Quality issue card ──────────────────────────────────────────────────────

function QualityIssue({
  severity,
  title,
  detail,
  impact,
}: {
  severity: "critical" | "warning" | "info";
  title: string;
  detail: string;
  impact: string;
}) {
  const config = {
    critical: { bg: "bg-[#fef2f2]", border: "border-[#fecaca]", icon: XCircle, iconColor: "text-[#ef4444]" },
    warning: { bg: "bg-[#fffbeb]", border: "border-[#fed7aa]", icon: AlertTriangle, iconColor: "text-[#f59e0b]" },
    info: { bg: "bg-[#f0fdf9]", border: "border-[#d4e8e2]", icon: CheckCircle, iconColor: "text-[#0f766e]" },
  }[severity];
  const Icon = config.icon;

  return (
    <div className={`rounded-xl border ${config.border} ${config.bg} p-4`}>
      <div className="flex items-start gap-3">
        <Icon size={16} className={`${config.iconColor} mt-0.5 shrink-0`} />
        <div>
          <p className="text-sm font-semibold text-[#0f172a]">{title}</p>
          <p className="text-sm text-[#35524d] mt-1">{detail}</p>
          <p className="text-xs text-[#64748b] mt-2 italic">Impact: {impact}</p>
        </div>
      </div>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export function AnalysisFhirPrimer() {
  const { data: stats } = useQuery({
    queryKey: ["corpus-stats"],
    queryFn: api.getCorpusStats,
    staleTime: Infinity,
  });

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 lg:px-10">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="rounded-3xl border border-[#b7e6dc] bg-[linear-gradient(135deg,#f5fffc_0%,#e9fbf6_55%,#f0fff9_100%)] p-6 lg:p-8">
        <p className="inline-flex items-center gap-2 rounded-full bg-[#d8f5ee] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#0f766e]">
          <BookOpen size={13} />
          FHIR Data Primer
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#0f172a] lg:text-4xl">
          Understanding the Data: FHIR R4 from the Ground Up
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[#35524d] lg:text-base">
          Before interpreting clinical data, you need to understand what you're looking at.
          This primer walks through the FHIR R4 data format — what's in each patient bundle,
          how resources relate to each other, and where the real-world data quality challenges live.
          Every JSON example below is pulled directly from our {stats?.total_patients.toLocaleString() ?? "1,180"}-patient
          Synthea corpus.
        </p>
      </section>

      {/* ── Section 1: What is FHIR? ─────────────────────────────────────── */}
      <section className="mt-8">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0f766e] text-xs font-bold text-white">1</div>
          <h2 className="text-xl font-semibold text-[#0f172a]">What is FHIR?</h2>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <p className="text-sm leading-6 text-[#35524d]">
              <strong className="text-[#0f172a]">FHIR (Fast Healthcare Interoperability Resources)</strong> is
              the HL7 standard for exchanging healthcare data electronically. Version <strong>R4</strong> (Release 4)
              is the current production standard used by most US health systems under the 21st Century Cures Act.
            </p>
            <p className="text-sm leading-6 text-[#35524d] mt-3">
              A <strong>FHIR Bundle</strong> is a container that packages all of a patient's clinical data into
              a single JSON document. Each Bundle contains an array of <strong>entries</strong>, where each entry
              holds one <strong>Resource</strong> — a discrete clinical concept like an encounter, a lab result,
              a medication order, or a diagnosis.
            </p>
            <p className="text-sm leading-6 text-[#35524d] mt-3">
              This is the data structure mandated by the ONC's information blocking rules — when patients
              request their records under the Cures Act, this is the format they receive.
            </p>
          </div>

          <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#0f766e] mb-3">Our Corpus at a Glance</p>
            <div className="space-y-3">
              {[
                { label: "Patient Bundles", value: stats?.total_patients.toLocaleString() ?? "1,180", note: "Each file = one patient's complete longitudinal record" },
                { label: "Total Resources", value: stats?.total_resources.toLocaleString() ?? "527,113", note: "Clinical + administrative FHIR resources across all patients" },
                { label: "Total Encounters", value: stats?.total_encounters.toLocaleString() ?? "46,868", note: "Individual clinical visits spanning decades of history" },
                { label: "Data Source", value: "Synthea", note: "Synthetic but structurally identical to real EHR exports" },
              ].map(s => (
                <div key={s.label} className="flex items-baseline gap-3">
                  <span className="text-lg font-semibold text-[#0f172a] w-20 text-right shrink-0">{s.value}</span>
                  <div>
                    <span className="text-sm font-medium text-[#0f172a]">{s.label}</span>
                    <span className="text-xs text-[#64748b] ml-1.5">— {s.note}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Section 2: Bundle Structure ─────────────────────────────────── */}
      <section className="mt-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0f766e] text-xs font-bold text-white">2</div>
          <h2 className="text-xl font-semibold text-[#0f172a]">Anatomy of a FHIR Bundle</h2>
        </div>

        <p className="text-sm text-[#35524d] mb-4 max-w-3xl">
          Every patient file in our corpus is a FHIR Bundle of type <code className="rounded bg-[#f1f5f9] px-1.5 py-0.5 text-xs font-mono text-[#0f766e]">transaction</code>.
          The outer wrapper is minimal — the real data lives in the <code className="rounded bg-[#f1f5f9] px-1.5 py-0.5 text-xs font-mono text-[#0f766e]">entry</code> array,
          which can contain hundreds to thousands of resources depending on the patient's history.
        </p>

        <JsonBlock
          title="Bundle wrapper"
          subtitle="The outer container — one per patient file"
          defaultOpen={true}
          json={`{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "57ca2c16-7008-41e5-b338-4758b2fc46f0",
        ...
      }
    },
    {
      "resource": {
        "resourceType": "Encounter",
        "id": "defe0e4c-de52-435d-b1fd-b8364fcc2f87",
        ...
      }
    },
    // ... hundreds more entries
  ]
}`}
          annotations={[
            { line: "resourceType", note: "Always \"Bundle\" — the top-level container per the FHIR spec" },
            { line: "type", note: "\"transaction\" means this is a complete set of resources meant to be processed together" },
            { line: "entry[]", note: "Flat array of all resources. A complex patient can have 1,900+ entries. Our corpus averages ~447 per patient." },
          ]}
        />

        <div className="mt-4 rounded-xl border border-[#d4e8e2] bg-[#f7fffc] p-4">
          <p className="text-sm font-semibold text-[#0f172a] mb-2">Typical resource distribution in a single patient bundle</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {[
              { type: "Observation", count: "~250–1,300", pct: "60–70%", desc: "Labs, vitals, surveys" },
              { type: "DiagnosticReport", count: "~50–130", pct: "7–10%", desc: "Lab report containers" },
              { type: "Encounter", count: "~20–110", pct: "5–8%", desc: "Clinical visits" },
              { type: "Claim / EOB", count: "~40–220", pct: "10–15%", desc: "Billing artifacts" },
              { type: "Procedure", count: "~10–40", pct: "2–3%", desc: "Surgeries, screenings" },
              { type: "Condition", count: "~5–20", pct: "1–2%", desc: "Active/resolved diagnoses" },
              { type: "MedicationRequest", count: "~3–15", pct: "<1%", desc: "Rx orders" },
              { type: "Immunization", count: "~8–15", pct: "<1%", desc: "Vaccines administered" },
            ].map(r => (
              <div key={r.type} className="rounded-lg bg-white border border-[#e5f4ef] px-3 py-2">
                <p className="text-xs font-semibold text-[#0f172a]">{r.type}</p>
                <p className="text-[11px] text-[#0f766e] font-mono">{r.count} <span className="text-[#a5a8b5]">({r.pct})</span></p>
                <p className="text-[10px] text-[#64748b] mt-0.5">{r.desc}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-[#64748b] mt-3 italic">
            Observation resources dominate every bundle. A single encounter can generate 10–30 observations
            (one per vital sign, lab result, or survey question). This is normal — not noise.
          </p>
        </div>
      </section>

      {/* ── Section 3: Core Resource Types ────────────────────────────────── */}
      <section className="mt-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0f766e] text-xs font-bold text-white">3</div>
          <h2 className="text-xl font-semibold text-[#0f172a]">Core Resource Types — Real JSON Examples</h2>
        </div>

        <p className="text-sm text-[#35524d] mb-5 max-w-3xl">
          Each resource type has a distinct schema with required and optional fields. The examples below are
          extracted verbatim from our corpus — this is exactly what the raw data looks like before our parser
          normalizes it.
        </p>

        <div className="space-y-4">
          {/* Patient */}
          <JsonBlock
            title="Patient"
            subtitle="Demographics — exactly 1 per bundle"
            defaultOpen={true}
            json={`{
  "resourceType": "Patient",
  "id": "57ca2c16-7008-41e5-b338-4758b2fc46f0",
  "name": [
    {
      "use": "official",
      "family": "Lockman863",
      "given": ["Barabara924"],
      "prefix": ["Mrs."]
    }
  ],
  "gender": "female",
  "birthDate": "1921-07-04",
  "address": [
    {
      "city": "Springfield",
      "state": "Massachusetts"
    }
  ],
  "extension": [
    {
      "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
      "extension": [
        { "url": "text", "valueString": "White" }
      ]
    }
  ]
}`}
            annotations={[
              { line: "name[]", note: "Array of HumanName objects — FHIR supports multiple names (maiden, official, nickname). We take the first entry." },
              { line: "gender", note: "Administrative gender, not clinical sex. Values: male | female | other | unknown." },
              { line: "birthDate", note: "ISO date without time. Age is computed at query time, not stored." },
              { line: "extension[]", note: "US Core extensions for race/ethnicity — not part of base FHIR, added by US implementation guides." },
            ]}
          />

          {/* Encounter */}
          <JsonBlock
            title="Encounter"
            subtitle="A clinical visit — linked to all resources generated during that visit"
            json={`{
  "resourceType": "Encounter",
  "id": "defe0e4c-de52-435d-b1fd-b8364fcc2f87",
  "status": "finished",
  "class": {
    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
    "code": "AMB"
  },
  "type": [
    {
      "coding": [
        {
          "system": "http://snomed.info/sct",
          "code": "424441002",
          "display": "Prenatal initial visit"
        }
      ],
      "text": "Prenatal initial visit"
    }
  ],
  "period": {
    "start": "1945-04-23T01:44:36-04:00",
    "end": "1945-04-23T02:29:36-04:00"
  },
  "participant": [
    {
      "individual": {
        "reference": "urn:uuid:0000016d-3a85-4cca-0000-000000000140",
        "display": "Dr. Mira443 Pacocha935"
      }
    }
  ]
}`}
            annotations={[
              { line: "class.code", note: "AMB = ambulatory, IMP = inpatient, EMER = emergency, VR = virtual. Critical for encounter classification." },
              { line: "type[].coding", note: "SNOMED CT coded visit type. The display text is human-readable; the code is machine-comparable." },
              { line: "period", note: "Start/end as ISO datetimes with timezone. Duration is computed: (end - start). Timezone offsets vary." },
              { line: "participant", note: "References use urn:uuid: format within Bundles. These resolve to Practitioner resources in the same Bundle." },
              { line: "reasonCode", note: "NOT SHOWN — 62% of encounters in our corpus have no reasonCode. This is a major data quality gap." },
            ]}
          />

          {/* Observation */}
          <JsonBlock
            title="Observation"
            subtitle="A single measurement — lab result, vital sign, or survey answer"
            json={`{
  "resourceType": "Observation",
  "id": "ad4253e8-dc5b-4a64-9eb5-eb72af97df96",
  "status": "final",
  "category": [
    {
      "coding": [
        {
          "system": "http://terminology.hl7.org/.../observation-category",
          "code": "vital-signs",
          "display": "vital-signs"
        }
      ]
    }
  ],
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "8302-2",
        "display": "Body Height"
      }
    ]
  },
  "valueQuantity": {
    "value": 166.67,
    "unit": "cm",
    "system": "http://unitsofmeasure.org",
    "code": "cm"
  },
  "effectiveDateTime": "1988-03-21T00:44:36-05:00"
}`}
            annotations={[
              { line: "category", note: "Observation categories: vital-signs, laboratory, survey, social-history. Determines which panel a result belongs to." },
              { line: "code.coding", note: "LOINC code — the universal lab/vital identifier. Our corpus has 99 unique LOINC codes across 1,180 patients." },
              { line: "valueQuantity", note: "Numeric result with unit from UCUM (Unified Code for Units of Measure). Note: Synthea values often have excessive decimal precision." },
              { line: "effectiveDateTime", note: "When the observation was taken. Critical for trend analysis — we compute ↑↓→ direction from sequential values." },
            ]}
          />

          {/* Condition */}
          <JsonBlock
            title="Condition"
            subtitle="A diagnosis — active or resolved"
            json={`{
  "resourceType": "Condition",
  "id": "a39af9c3-b23d-4249-aafd-5d63e500fb39",
  "clinicalStatus": {
    "coding": [
      {
        "system": "http://terminology.hl7.org/.../condition-clinical",
        "code": "active"
      }
    ]
  },
  "code": {
    "coding": [
      {
        "system": "http://snomed.info/sct",
        "code": "19169002",
        "display": "Miscarriage in first trimester"
      }
    ]
  },
  "onsetDateTime": "1945-04-23T01:44:36-04:00",
  "recordedDate": "1945-04-23T01:44:36-04:00"
}`}
            annotations={[
              { line: "clinicalStatus", note: "\"active\" or \"resolved\" — determines whether this condition is current. We rank active conditions by surgical risk." },
              { line: "code.system", note: "SNOMED CT — the global clinical terminology standard. Over 350,000 concepts. Our ranker maps display text to 11 surgical risk categories." },
              { line: "verificationStatus", note: "NOT SHOWN — confirms vs. provisional vs. refuted. Synthea marks everything confirmed; real EHR data varies." },
              { line: "abatementDateTime", note: "NOT SHOWN — when the condition resolved. Only present for resolved conditions." },
            ]}
          />

          {/* MedicationRequest */}
          <JsonBlock
            title="MedicationRequest"
            subtitle="A medication order — the basis for drug safety analysis"
            json={`{
  "resourceType": "MedicationRequest",
  "id": "9707f7e0-72ee-4a25-a59e-6c0607213489",
  "status": "active",
  "intent": "order",
  "medicationCodeableConcept": {
    "coding": [
      {
        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
        "code": "999969",
        "display": "Amlodipine 5 MG / Hydrochlorothiazide 12.5 MG / Olmesartan medoxomil 20 MG"
      }
    ]
  },
  "authoredOn": "1961-10-08T01:44:36-04:00"
}`}
            annotations={[
              { line: "status", note: "\"active\" = currently prescribed; \"stopped\" = discontinued. Our drug classifier only flags active medications for surgical risk." },
              { line: "RxNorm code", note: "999969 maps to a specific formulation. RxNorm is the standard for medication identity in US clinical systems." },
              { line: "display", note: "Full drug name with strength — this is what our drug-class keyword matcher scans against for surgical risk classification." },
              { line: "dosageInstruction", note: "NOT SHOWN — 64% of MedicationRequests in our corpus lack dosage instructions. This is realistic: many EHR exports omit dose details." },
            ]}
          />
        </div>
      </section>

      {/* ── Section 4: Resource Hierarchy ──────────────────────────────────── */}
      <section className="mt-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0f766e] text-xs font-bold text-white">4</div>
          <h2 className="text-xl font-semibold text-[#0f172a]">Resource Hierarchy — How Everything Connects</h2>
        </div>

        <p className="text-sm text-[#35524d] mb-5 max-w-3xl">
          FHIR resources reference each other through <code className="rounded bg-[#f1f5f9] px-1.5 py-0.5 text-xs font-mono text-[#0f766e]">reference</code> fields.
          Within a Bundle, these are <code className="rounded bg-[#f1f5f9] px-1.5 py-0.5 text-xs font-mono text-[#0f766e]">urn:uuid:</code> pointers
          that resolve to other entries in the same file. The Patient is the root; Encounters are the primary
          organizing unit; everything else hangs off encounters.
        </p>

        <div className="rounded-2xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2 mb-5">
            <Network size={16} className="text-[#0f766e]" />
            <p className="text-sm font-semibold text-[#0f766e]">FHIR Resource Relationships</p>
          </div>

          <ResourceNode
            name="Patient"
            count="1 per bundle"
            description="The root resource — demographics, identifiers, and contact information"
          >
            <ResourceNode
              name="Encounter"
              codingSystem="SNOMED CT"
              count={`avg ${stats ? (stats.total_encounters / stats.total_patients).toFixed(0) : "40"}/patient`}
              description="Clinical visits — ambulatory, inpatient, emergency, virtual"
              color="#2563eb"
            >
              <ResourceNode
                name="Observation"
                codingSystem="LOINC"
                description="Lab results, vital signs, survey answers — linked to the encounter where they were recorded"
                color="#7c3aed"
              />
              <ResourceNode
                name="Condition"
                codingSystem="SNOMED CT"
                description="Diagnoses — onset linked to an encounter, may span many encounters over time"
                color="#dc2626"
              />
              <ResourceNode
                name="Procedure"
                codingSystem="SNOMED CT / CPT"
                description="Surgeries, screenings, interventions performed during the encounter"
                color="#ea580c"
              />
              <ResourceNode
                name="MedicationRequest"
                codingSystem="RxNorm"
                description="Prescriptions ordered during the encounter — status tracks active vs. stopped"
                color="#0891b2"
              />
              <ResourceNode
                name="DiagnosticReport"
                codingSystem="LOINC"
                description="Container grouping multiple Observation results into a single report (e.g., CBC panel)"
                color="#64748b"
              />
            </ResourceNode>

            <ResourceNode
              name="AllergyIntolerance"
              codingSystem="SNOMED CT"
              description="Allergy/sensitivity records — substance, criticality, and reaction details"
              color="#b91c1c"
            />
            <ResourceNode
              name="Immunization"
              codingSystem="CVX"
              description="Vaccines administered — date, vaccine code, status"
              color="#15803d"
            />
            <ResourceNode
              name="CarePlan"
              description="Treatment plans with goals and activities — often linked to chronic conditions"
              color="#64748b"
            />
            <ResourceNode
              name="CareTeam"
              description="Providers involved in the patient's care — practitioner references and roles"
              color="#64748b"
            />
          </ResourceNode>

          <div className="mt-5 rounded-lg bg-[#f8fafc] border border-[#e2e8f0] p-3">
            <p className="text-xs text-[#64748b]">
              <strong className="text-[#0f172a]">Coding systems matter.</strong> Each resource type
              uses a specific terminology standard — SNOMED CT for clinical findings, LOINC for labs,
              RxNorm for medications, CVX for vaccines. These codes are what make FHIR data machine-readable
              and cross-system comparable. Our app uses these codes for drug classification, condition
              ranking, and lab panel matching.
            </p>
          </div>
        </div>
      </section>

      {/* ── Section 5: Data Quality Reality Check ──────────────────────── */}
      <section className="mt-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0f766e] text-xs font-bold text-white">5</div>
          <h2 className="text-xl font-semibold text-[#0f172a]">Data Quality Reality Check</h2>
        </div>

        <p className="text-sm text-[#35524d] mb-5 max-w-3xl">
          FHIR defines the schema — it doesn't guarantee the data is complete, accurate, or clinically useful.
          Our Synthea corpus is cleaner than most real-world EHR exports, but it still has significant gaps.
          Understanding these gaps is essential for building trustworthy clinical features.
        </p>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#0f766e] mb-1">Field-Level Gaps</p>

            <QualityIssue
              severity="critical"
              title="AllergyIntolerance.reaction — 100% absent"
              detail="Every allergy record in the corpus is missing the reaction array. We know the substance (e.g., Penicillin) but not what happens (rash, anaphylaxis, etc.). Real EHR data has this ~40% of the time."
              impact="Cannot assess allergy severity or cross-reactivity risk from data alone. Our cross-reactivity warnings use drug-class heuristics instead."
            />

            <QualityIssue
              severity="critical"
              title="Immunization.lotNumber — 100% absent"
              detail="No vaccine lot numbers in Synthea. Real EHR exports usually include these for recall tracking."
              impact="Cannot support vaccine recall lookups or lot-specific adverse event correlation."
            />

            <QualityIssue
              severity="warning"
              title="MedicationRequest.dosageInstruction — 64% absent"
              detail="Nearly two-thirds of medication orders have no dosage information. We know what was prescribed but not how much or how often."
              impact="Drug interaction severity cannot be dose-adjusted. Our interaction checker uses class-level rules rather than dose-dependent thresholds."
            />

            <QualityIssue
              severity="warning"
              title="Encounter.reasonCode — 62% absent"
              detail="Most encounters don't state why the patient came in. The encounter type (SNOMED code) provides some context, but it's often generic."
              impact="Timeline view shows many encounters without a clear reason. Clinical narrative reconstruction requires inference from linked conditions."
            />
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#0f766e] mb-1">Structural Considerations</p>

            <QualityIssue
              severity="warning"
              title="Observation values have excessive precision"
              detail='Synthea generates values like 166.66990094613146 cm for height. Real clinical data rounds appropriately (166.7 cm). This is cosmetic but reveals synthetic origin.'
              impact="Our display rounds to 1 decimal. Analysts comparing raw JSON should be aware this precision is synthetic noise."
            />

            <QualityIssue
              severity="info"
              title="Observation.valueQuantity — 99.99% populated"
              detail="Almost every observation has a numeric value. This is actually better than real EHR data, where transcription errors, free-text entries, and device failures create gaps."
              impact="Our lab panels and trend analysis are reliable across the corpus. Real-world deployment would need more robust null handling."
            />

            <QualityIssue
              severity="info"
              title="Condition.clinicalStatus — always present and coded"
              detail='Every condition has a clear "active" or "resolved" status. Real EHR data sometimes omits this or uses free-text equivalents.'
              impact="Our condition acuity ranker works cleanly. Production systems would need status inference for uncoded conditions."
            />

            <QualityIssue
              severity="warning"
              title="Device resources — rare (2% of patients)"
              detail="Only ~24 patients in the corpus have Device resources (implants, pacemakers). Synthea generates these sparingly."
              impact="Device/implant tracking features have limited test coverage. Real EHR exports from surgical populations would have much higher device prevalence."
            />
          </div>
        </div>
      </section>

      {/* ── Section 6: Synthea vs Real EHR ──────────────────────────────── */}
      <section className="mt-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0f766e] text-xs font-bold text-white">6</div>
          <h2 className="text-xl font-semibold text-[#0f172a]">Synthea vs. Real EHR Exports</h2>
        </div>

        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="text-sm text-[#35524d] mb-4">
            Our corpus is generated by <strong>Synthea</strong> — a synthetic patient generator that
            produces FHIR R4 bundles conforming to US Core Implementation Guide profiles. The data
            is structurally valid but has important differences from real patient records.
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#e5f4ef]">
                  <th className="text-left py-2 pr-4 text-xs font-semibold text-[#0f766e] uppercase tracking-wider">Aspect</th>
                  <th className="text-left py-2 pr-4 text-xs font-semibold text-[#0f766e] uppercase tracking-wider">Synthea (Our Data)</th>
                  <th className="text-left py-2 text-xs font-semibold text-[#0f766e] uppercase tracking-wider">Real EHR Export</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f1f5f9]">
                {[
                  { aspect: "Patient identity", synthea: "Synthetic names and addresses — safe for public demos", real: "Real PHI — requires de-identification before any sharing" },
                  { aspect: "Clinical plausibility", synthea: "Disease progressions follow epidemiological models (e.g., diabetes → CKD)", real: "Highly variable — real patients don't follow textbook progressions" },
                  { aspect: "Coding consistency", synthea: "Every resource has valid SNOMED/LOINC/RxNorm codes", real: "Mix of coded and free-text entries; legacy codes; local extensions" },
                  { aspect: "Temporal patterns", synthea: "Regular intervals between encounters; predictable follow-up", real: "Irregular — gaps from switching providers, non-compliance, insurance changes" },
                  { aspect: "Data volume", synthea: "~447 resources/patient average", real: "Can be 2,000–50,000+ for patients with chronic conditions" },
                  { aspect: "Missing data", synthea: "Systematically absent (same fields always missing)", real: "Randomly absent — varies by provider, EHR vendor, documentation habits" },
                  { aspect: "Free text / notes", synthea: "No clinical notes or narrative text", real: "Rich clinical notes — often the most valuable part of the record" },
                  { aspect: "Multi-system data", synthea: "Single coherent record", real: "Merged from multiple hospitals — duplicate entries, conflicting statuses" },
                ].map(row => (
                  <tr key={row.aspect}>
                    <td className="py-2.5 pr-4 font-medium text-[#0f172a] whitespace-nowrap">{row.aspect}</td>
                    <td className="py-2.5 pr-4 text-[#35524d]">{row.synthea}</td>
                    <td className="py-2.5 text-[#35524d]">{row.real}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 rounded-lg bg-[#fffbeb] border border-[#fed7aa] p-3 flex items-start gap-2">
            <AlertTriangle size={14} className="text-[#f59e0b] mt-0.5 shrink-0" />
            <p className="text-xs text-[#92400e]">
              <strong>Key takeaway:</strong> Synthea data validates that our parsing and classification logic
              handles the FHIR R4 spec correctly. But real-world deployment requires additional handling for
              free-text entries, duplicate resolution, partial records, and vendor-specific extensions that
              Synthea doesn't produce.
            </p>
          </div>
        </div>
      </section>

      {/* ── Section 7: Coding Systems Reference ───────────────────────── */}
      <section className="mt-10 mb-12">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0f766e] text-xs font-bold text-white">7</div>
          <h2 className="text-xl font-semibold text-[#0f172a]">Coding Systems Reference</h2>
        </div>

        <p className="text-sm text-[#35524d] mb-5 max-w-3xl">
          FHIR uses standardized coding systems so that clinical concepts are machine-comparable across
          institutions. These are the systems present in our corpus and how our app uses each one.
        </p>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            {
              name: "SNOMED CT",
              url: "http://snomed.info/sct",
              used_for: "Conditions, procedures, encounter types, allergy substances",
              our_use: "Condition acuity ranking (11 surgical risk categories) and procedure classification",
              example: "38341003 = Hypertension",
            },
            {
              name: "LOINC",
              url: "http://loinc.org",
              used_for: "Laboratory tests, vital signs, clinical surveys, diagnostic report types",
              our_use: "Key labs panel matching (Hematology, Metabolic, Coagulation, Cardiac), alert threshold checking, observation distributions",
              example: "718-7 = Hemoglobin",
            },
            {
              name: "RxNorm",
              url: "http://www.nlm.nih.gov/research/umls/rxnorm",
              used_for: "Medications — maps drug name + strength + form to a unique concept",
              our_use: "Drug class classification (10 surgical risk classes), drug-drug interaction checking, hold/bridge protocol lookup",
              example: "855332 = Warfarin Sodium 5 MG",
            },
            {
              name: "CVX",
              url: "http://hl7.org/fhir/sid/cvx",
              used_for: "Vaccine products administered",
              our_use: "Immunization timeline display with CVX code badges",
              example: "140 = Influenza, seasonal",
            },
            {
              name: "ICD-10-CM",
              url: "http://hl7.org/fhir/sid/icd-10-cm",
              used_for: "Billing diagnosis codes — often present alongside SNOMED codes on conditions",
              our_use: "Not directly used — our ranker operates on SNOMED display text for broader matching",
              example: "I10 = Essential hypertension",
            },
            {
              name: "UCUM",
              url: "http://unitsofmeasure.org",
              used_for: "Units for observation values (mg/dL, mmol/L, cm, kg, etc.)",
              our_use: "Lab alert thresholds are unit-aware — critical for correct clinical interpretation",
              example: "mg/dL, g/dL, mEq/L, %",
            },
          ].map(sys => (
            <div key={sys.name} className="rounded-xl border border-[#d4e8e2] bg-white p-4">
              <div className="flex items-center gap-2 mb-2">
                <Layers size={14} className="text-[#0f766e]" />
                <span className="text-sm font-semibold text-[#0f172a]">{sys.name}</span>
              </div>
              <p className="text-[11px] font-mono text-[#64748b] mb-2 truncate" title={sys.url}>{sys.url}</p>
              <p className="text-xs text-[#35524d]"><strong>Used for:</strong> {sys.used_for}</p>
              <p className="text-xs text-[#35524d] mt-1"><strong>Our app:</strong> {sys.our_use}</p>
              <p className="text-[11px] text-[#64748b] mt-2 font-mono">e.g. {sys.example}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
