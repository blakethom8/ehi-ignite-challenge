import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ShieldCheck,
  Clock,
  MessageSquare,
  BarChart3,
  ArrowRight,
  AlertTriangle,
  CheckCircle,
  ShieldAlert,
  Heart,
  FileText,
  Pill,
  Baby,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../api/client";
import type { ClassificationsResponse } from "../types";

const CATEGORY_CONFIG: Record<
  string,
  { label: string; color: string; textColor: string; icon: LucideIcon }
> = {
  high_surgical_risk: { label: "High Surgical Risk", color: "#ffc6c6", textColor: "#600000", icon: AlertTriangle },
  low_risk_routine: { label: "Low Risk / Routine", color: "#c3faf5", textColor: "#187574", icon: CheckCircle },
  polypharmacy: { label: "Polypharmacy", color: "#ffe6cd", textColor: "#744000", icon: Pill },
  potential_drug_interactions: { label: "Drug Interactions", color: "#ffc6c6", textColor: "#600000", icon: ShieldAlert },
  pediatric: { label: "Pediatric", color: "#eef1ff", textColor: "#5b76fe", icon: Baby },
  elderly_complex: { label: "Elderly Complex", color: "#ffe6cd", textColor: "#744000", icon: Heart },
  chronic_disease_cascade: { label: "Chronic Disease Cascade", color: "#ffd8f4", textColor: "#7a1057", icon: Activity },
  minimal_record: { label: "Minimal Record", color: "#f5f6f8", textColor: "#555a6a", icon: FileText },
};

function formatCategoryName(key: string): string {
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function Landing() {
  const navigate = useNavigate();

  const { data: classifications, isLoading: classificationsLoading } = useQuery<ClassificationsResponse>({
    queryKey: ["classifications"],
    queryFn: api.getClassifications,
  });

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-[#e9eaef] bg-white px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity size={20} className="text-[#5b76fe]" />
            <span className="text-lg font-semibold tracking-tight text-[#1c1c1e]">
              EHI Ignite
            </span>
          </div>
          <a
            href="https://github.com/blakethom8/ehi-ignite-challenge"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-[#555a6a] hover:text-[#1c1c1e]"
          >
            GitHub
          </a>
        </div>
      </header>

      {/* Hero */}
      <section className="px-6 py-16 lg:py-24">
        <div className="mx-auto max-w-3xl text-center">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[#5b76fe]">
            HHS EHI Ignite Challenge
          </p>
          <h1 className="mb-4 text-3xl font-bold tracking-tight text-[#1c1c1e] lg:text-5xl">
            The right 5 facts in 30 seconds
          </h1>
          <p className="mx-auto mb-10 max-w-xl text-lg leading-relaxed text-[#555a6a]">
            Clinicians reviewing a chart before surgery don't need 5,000 FHIR resources.
            They need medication risks, active conditions, and safety flags — surfaced
            instantly from the patient's complete electronic health record.
          </p>
          <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
            <button
              onClick={() => navigate("/explorer")}
              className="flex items-center gap-2 rounded-xl bg-[#5b76fe] px-6 py-3 text-sm font-medium text-white shadow-sm transition-colors hover:bg-[#2a41b6]"
            >
              Open Clinical Dashboard
              <ArrowRight size={16} />
            </button>
            <button
              onClick={() => navigate("/analysis")}
              className="flex items-center gap-2 rounded-xl border border-[#e9eaef] bg-white px-6 py-3 text-sm font-medium text-[#555a6a] shadow-sm transition-colors hover:border-[#5b76fe] hover:text-[#5b76fe]"
            >
              Explore the Data
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </section>

      {/* Use Case */}
      <section className="border-t border-[#e9eaef] bg-[#fafbfc] px-6 py-16">
        <div className="mx-auto max-w-4xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#a5a8b5]">
            Use Case
          </p>
          <h2 className="mb-3 text-2xl font-bold tracking-tight text-[#1c1c1e]">
            Pre-operative chart review
          </h2>
          <p className="mb-10 max-w-2xl text-[#555a6a] leading-relaxed">
            A surgeon has 60 seconds between cases to review the next patient's chart.
            The EHR export is thousands of records deep. This tool extracts the
            clinically relevant signal — medication risks, drug interactions, active
            problem list, and lab trends — so the surgeon walks into the OR informed,
            not overwhelmed.
          </p>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                icon: ShieldCheck,
                title: "Safety Panel",
                desc: "Drug class risk flags, allergy criticality, and interaction checks — the pre-op essentials.",
                color: "#ffc6c6",
                textColor: "#600000",
              },
              {
                icon: Clock,
                title: "Care Journey",
                desc: "Medication episodes, condition arcs, and encounters on an interactive Gantt timeline.",
                color: "#c3faf5",
                textColor: "#187574",
              },
              {
                icon: MessageSquare,
                title: "Provider Assistant",
                desc: "Ask questions about the patient's chart. Claude answers with evidence-backed citations.",
                color: "#eef1ff",
                textColor: "#5b76fe",
              },
            ].map(({ icon: Icon, title, desc, color, textColor }) => (
              <div
                key={title}
                className="rounded-2xl border border-[#e9eaef] bg-white p-6"
              >
                <div
                  className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl"
                  style={{ backgroundColor: color }}
                >
                  <Icon size={18} style={{ color: textColor }} />
                </div>
                <h3 className="mb-1 text-sm font-semibold text-[#1c1c1e]">{title}</h3>
                <p className="text-sm leading-relaxed text-[#555a6a]">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Featured Patients */}
      <section className="border-t border-[#e9eaef] px-6 py-16">
        <div className="mx-auto max-w-5xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#a5a8b5]">
            Featured Patients
          </p>
          <h2 className="mb-3 text-2xl font-bold tracking-tight text-[#1c1c1e]">
            Explore by clinical profile
          </h2>
          <p className="mb-10 max-w-2xl text-[#555a6a] leading-relaxed">
            Curated examples from each classification category — pick a profile to jump
            straight into a representative patient record.
          </p>

          {classificationsLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="animate-pulse rounded-2xl border border-[#e9eaef] bg-white p-6"
                >
                  <div className="mb-4 h-10 w-10 rounded-xl bg-[#f0f1f4]" />
                  <div className="mb-2 h-4 w-2/3 rounded bg-[#f0f1f4]" />
                  <div className="mb-4 h-3 w-1/3 rounded bg-[#f0f1f4]" />
                  <div className="space-y-2">
                    <div className="h-3 w-full rounded bg-[#f0f1f4]" />
                    <div className="h-3 w-5/6 rounded bg-[#f0f1f4]" />
                    <div className="h-3 w-4/6 rounded bg-[#f0f1f4]" />
                  </div>
                </div>
              ))}
            </div>
          ) : classifications ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(classifications.categories).map(([key, category]) => {
                const config = CATEGORY_CONFIG[key];
                const Icon = config?.icon ?? FileText;
                const label = config?.label ?? formatCategoryName(key);
                const color = config?.color ?? "#f5f6f8";
                const textColor = config?.textColor ?? "#555a6a";
                const ex = category.best_example;

                return (
                  <div
                    key={key}
                    className="group flex flex-col rounded-2xl border border-[#e9eaef] bg-white p-6 transition-all hover:border-[#5b76fe] hover:shadow-md"
                  >
                    {/* Icon + badge row */}
                    <div className="mb-4 flex items-start justify-between">
                      <div
                        className="flex h-10 w-10 items-center justify-center rounded-xl"
                        style={{ backgroundColor: color }}
                      >
                        <Icon size={18} style={{ color: textColor }} />
                      </div>
                      <span
                        className="rounded-full px-2.5 py-0.5 text-xs font-medium"
                        style={{ backgroundColor: color, color: textColor }}
                      >
                        {category.count} patients
                      </span>
                    </div>

                    {/* Category name */}
                    <h3 className="mb-3 text-sm font-semibold text-[#1c1c1e]">
                      {label}
                    </h3>

                    {/* Best example patient */}
                    <div className="mb-4 flex-1 space-y-1 text-xs text-[#555a6a]">
                      <p className="font-medium text-[#1c1c1e]">
                        {ex.name}, {ex.age}y
                      </p>
                      <p>{ex.total_resources} resources</p>
                      <p>{ex.n_active_conditions} conditions</p>
                      <p>{ex.n_active_medications} medications</p>
                    </div>

                    {/* Link */}
                    <button
                      onClick={() => navigate(`/explorer?patient=${ex.patient_id}`)}
                      className="flex items-center gap-1 text-xs font-medium text-[#5b76fe] transition-all group-hover:gap-2"
                    >
                      View patient <ArrowRight size={12} />
                    </button>
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      </section>

      {/* Two paths */}
      <section className="border-t border-[#e9eaef] px-6 py-16">
        <div className="mx-auto grid max-w-4xl gap-6 lg:grid-cols-2">
          <button
            onClick={() => navigate("/explorer")}
            className="group cursor-pointer rounded-2xl border border-[#e9eaef] bg-white p-8 text-left transition-all hover:border-[#5b76fe] hover:shadow-md"
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#eef1ff]">
              <Activity size={22} className="text-[#5b76fe]" />
            </div>
            <h3 className="mb-2 text-lg font-bold text-[#1c1c1e]">
              Clinical Dashboard
            </h3>
            <p className="mb-4 text-sm leading-relaxed text-[#555a6a]">
              Select a patient and explore their complete health record through
              clinical views — safety flags, medication timeline, condition acuity,
              lab trends, and AI-powered chart Q&A.
            </p>
            <span className="flex items-center gap-1 text-sm font-medium text-[#5b76fe] transition-all group-hover:gap-2">
              Open dashboard <ArrowRight size={14} />
            </span>
          </button>

          <button
            onClick={() => navigate("/analysis")}
            className="group cursor-pointer rounded-2xl border border-[#e9eaef] bg-white p-8 text-left transition-all hover:border-[#00b473] hover:shadow-md"
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#e6f9f0]">
              <BarChart3 size={22} className="text-[#00b473]" />
            </div>
            <h3 className="mb-2 text-lg font-bold text-[#1c1c1e]">
              Data Lab
            </h3>
            <p className="mb-4 text-sm leading-relaxed text-[#555a6a]">
              Explore the underlying data — corpus statistics across 1,180 synthetic
              patients, field coverage profiling, observation distributions, FHIR
              format deep dive, and data methodology.
            </p>
            <span className="flex items-center gap-1 text-sm font-medium text-[#00b473] transition-all group-hover:gap-2">
              Explore data <ArrowRight size={14} />
            </span>
          </button>
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-[#e9eaef] bg-[#fafbfc] px-6 py-16">
        <div className="mx-auto max-w-4xl">
          <h2 className="mb-8 text-2xl font-bold tracking-tight text-[#1c1c1e]">
            How it works
          </h2>
          <div className="grid gap-6 sm:grid-cols-3">
            {[
              {
                step: "1",
                title: "FHIR bundles in",
                desc: "1,180 Synthea R4 patient bundles are parsed and loaded. Each contains conditions, medications, labs, encounters, and procedures.",
              },
              {
                step: "2",
                title: "SQL-on-FHIR warehouse",
                desc: "ViewDefinitions transform raw FHIR resources into queryable SQLite tables — enriched with drug classifications, episode detection, and derived views.",
              },
              {
                step: "3",
                title: "Clinical intelligence out",
                desc: "Structured views surface safety flags, risk tiers, and medication timelines. The AI assistant answers free-text questions grounded in the patient's actual record.",
              },
            ].map(({ step, title, desc }) => (
              <div key={step}>
                <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-[#5b76fe] text-sm font-bold text-white">
                  {step}
                </div>
                <h3 className="mb-1 text-sm font-semibold text-[#1c1c1e]">{title}</h3>
                <p className="text-sm leading-relaxed text-[#555a6a]">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#e9eaef] px-6 py-8">
        <div className="mx-auto flex max-w-4xl flex-col items-center justify-between gap-2 text-xs text-[#a5a8b5] sm:flex-row">
          <span>Built for the HHS EHI Ignite Challenge 2026</span>
          <div className="flex gap-4">
            <a
              href="https://ehignitechallenge.org/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-[#555a6a]"
            >
              Competition site
            </a>
            <a
              href="https://github.com/blakethom8/ehi-ignite-challenge"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-[#555a6a]"
            >
              Source code
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
