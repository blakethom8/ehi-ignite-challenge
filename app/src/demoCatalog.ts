import {
  Activity,
  Boxes,
  HeartPulse,
  Microscope,
  Pill,
  SearchCheck,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";

export type DemoCatalogEntry = {
  patientId: string;
  title: string;
  shortTitle: string;
  body: string;
  label: string;
  focus: string;
  highlights: string[];
  icon: LucideIcon;
  accent: string;
  edge: string;
};

export const demoCatalog: DemoCatalogEntry[] = [
  {
    patientId: "demo-high-risk",
    title: "Surgical Review Sample",
    shortTitle: "Surgical review",
    body: "A high-signal pre-op chart with anticoagulation, cardiology, stroke history, and active oncology treatment in view.",
    label: "Prepared sample chart",
    focus: "Best for fast surgical triage, peri-op medication review, and \"is this patient safe this week?\" discussion.",
    highlights: ["Warfarin + clopidogrel", "CHF + AFib + stroke history", "Oncology treatment context"],
    icon: Stethoscope,
    accent: "from-[#eefaf4] via-[#f8fcfa] to-white",
    edge: "border-[#cbe5d8]",
  },
  {
    patientId: "demo-trial-match",
    title: "Trial Match Sample",
    shortTitle: "Trial match",
    body: "An oncology referral chart with active cancer treatment, chronic disease burden, and eligibility-style review questions.",
    label: "Sample workflow",
    focus: "Best for specialty referral, trial screening, and chart-to-evidence handoff workflows.",
    highlights: ["Active docetaxel + leuprolide", "CKD + CAD + diabetes", "Referral and eligibility framing"],
    icon: SearchCheck,
    accent: "from-[#edf8ff] via-[#f7fcff] to-white",
    edge: "border-[#c8e2f1]",
  },
  {
    patientId: "demo-med-access",
    title: "Medication Access Sample",
    shortTitle: "Medication access",
    body: "A longitudinal polypharmacy chart with diabetes, CKD, chronic pain, and treatment continuity concerns.",
    label: "Sample workspace",
    focus: "Best for medication burden, refill continuity, and chronic-care coordination stories.",
    highlights: ["Insulin + metformin", "Neuropathy and retinopathy", "Longitudinal treatment burden"],
    icon: Pill,
    accent: "from-[#fff7ed] via-[#fffbf6] to-white",
    edge: "border-[#fed7aa]",
  },
  // ─── Multi-source aggregation demos ──────────────────────────────────────
  // These four pair a structured FHIR baseline with a fan of pre-staged
  // synthetic source documents (PDF discharge summaries, C-CDA exports,
  // supplemental FHIR feeds from clinics / apps / devices / home monitors).
  // They demonstrate the data-aggregation centerpiece on real multi-source
  // evidence with deliberate cross-source inconsistencies baked in.
  {
    patientId: "demo-aggregate-icu",
    title: "Critical Care Aggregation",
    shortTitle: "ICU multi-source",
    body: "Real (de-identified) MIMIC ICU survivor assembled from seven sources — hospital, anticoag clinic, EP lab, sleep clinic, pre-op intake, and an outside oncology provider's C-CDA + FHIR feed.",
    label: "Multi-source aggregation",
    focus: "Best for showing how Atlas reconciles real ICU charting against outside-provider records — including a self-reported anticoagulation hold the chart doesn't have.",
    highlights: [
      "MIMIC-IV ICU + outside Dana-Farber oncology",
      "CLL · AFib · pacemaker · OSA · TIA",
      "7 source documents · 2 baked inconsistencies",
    ],
    icon: HeartPulse,
    accent: "from-[#fef2f2] via-[#fff8f8] to-white",
    edge: "border-[#fecaca]",
  },
  {
    patientId: "demo-aggregate-oncology",
    title: "Oncology Aggregation",
    shortTitle: "Oncology multi-source",
    body: "HL7 mCODE breast cancer workup paired with imaging, pathology, tumor board, genetic counseling, prior community-gynecologist C-CDA, and 8 weeks of patient-app symptom-tracker FHIR.",
    label: "Multi-source aggregation",
    focus: "Best for showing mCODE structured staging being reconciled against narrative documents and patient-generated health data — including a temporal mismatch where the app implies active chemo the chart doesn't have.",
    highlights: [
      "mCODE staging + biomarkers",
      "Patient-generated symptom-tracker FHIR",
      "6 source documents · 3 baked inconsistencies",
    ],
    icon: Microscope,
    accent: "from-[#fdf4ff] via-[#fef9ff] to-white",
    edge: "border-[#f5d0fe]",
  },
  {
    patientId: "demo-aggregate-cardiac",
    title: "Cardiac Multimodal Aggregation",
    shortTitle: "Cardiac multimodal",
    body: "Synthea Coherent CVD patient with FHIR + DICOM MRI + simulated genomics, plus a cardiology post-arrest consult, stroke discharge, prostate pathology, oncology plan, and Medtronic CareLink pacemaker telemetry FHIR feed.",
    label: "Multimodal aggregation",
    focus: "Best for demonstrating cross-modality aggregation — structured FHIR, imaging, genomics, and live device telemetry — with a temporal version conflict between two pacemaker data sources.",
    highlights: [
      "FHIR + DICOM + DNA + device feed",
      "Cardiac arrest + stroke + prostate cancer",
      "6 source documents · 3 baked inconsistencies",
    ],
    icon: Activity,
    accent: "from-[#eff6ff] via-[#f7fbff] to-white",
    edge: "border-[#bfdbfe]",
  },
  {
    patientId: "demo-aggregate-polypharmacy",
    title: "Polypharmacy Aggregation",
    shortTitle: "Polypharmacy multi-source",
    body: "Synthea geriatric polypharmacy patient with warfarin, dementia, and FOLFOX — assembled from hospital, anticoag clinic, neurology, GI, a stale outside PCP C-CDA, and 60 days of home-monitoring FHIR (BP cuff + glucometer).",
    label: "Multi-source aggregation",
    focus: "Best for showing how home monitoring data exposes uncontrolled HTN + glucose despite a chart that codes both as managed — and surfaces a stale outside PCP list that still has aspirin instead of warfarin.",
    highlights: [
      "Home BP + glucose FHIR feed",
      "AFib on warfarin · Alzheimer's · colorectal on FOLFOX",
      "6 source documents · 3 baked inconsistencies",
    ],
    icon: Boxes,
    accent: "from-[#f0fdf4] via-[#f6fefa] to-white",
    edge: "border-[#bbf7d0]",
  },
];

export const defaultDemoPatientId = demoCatalog[0]?.patientId ?? "demo-high-risk";

export function findDemoCatalogEntry(patientId: string | null | undefined) {
  if (!patientId) return null;
  return demoCatalog.find((entry) => entry.patientId === patientId) ?? null;
}
