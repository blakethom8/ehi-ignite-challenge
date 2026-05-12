import { Pill, SearchCheck, Stethoscope, type LucideIcon } from "lucide-react";

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
];

export const defaultDemoPatientId = demoCatalog[0]?.patientId ?? "demo-high-risk";

export function findDemoCatalogEntry(patientId: string | null | undefined) {
  if (!patientId) return null;
  return demoCatalog.find((entry) => entry.patientId === patientId) ?? null;
}
