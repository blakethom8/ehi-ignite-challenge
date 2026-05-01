import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BarChart3,
  ChevronsUpDown,
  Database,
  FileSearch,
  GitBranch,
  Pill,
  Search,
  ShieldCheck,
  Stethoscope,
  UserRound,
} from "lucide-react";
import { api } from "../api/client";
import type { PatientListItem } from "../types";

type SortKey =
  | "complexity_score"
  | "total_resources"
  | "encounter_count"
  | "active_condition_count"
  | "active_med_count"
  | "name";
type SortDirection = "asc" | "desc";

const SORT_LABELS: Record<SortKey, string> = {
  name: "Patient",
  complexity_score: "Score",
  total_resources: "Resources",
  encounter_count: "Encounters",
  active_condition_count: "Conditions",
  active_med_count: "Meds",
};

function patientLabel(patient: PatientListItem): string {
  const age = Number.isFinite(patient.age_years) ? `${Math.round(patient.age_years)}y` : null;
  const details = [age, patient.gender].filter(Boolean).join(" ");
  return details ? `${patient.name} - ${details}` : patient.name;
}

function patientUrl(path: string, patient?: PatientListItem): string {
  return patient ? `${path}?patient=${patient.id}` : path;
}

function formatTier(tier: string): string {
  return tier.replace(/_/g, " ");
}

function tierClass(tier: string): string {
  if (tier === "highly_complex" || tier === "complex") return "bg-[#fff1f2] text-[#9f1239]";
  if (tier === "moderate") return "bg-[#fff7ed] text-[#9a3412]";
  return "bg-[#ecfdf5] text-[#047857]";
}

function numericValue(patient: PatientListItem, key: SortKey): number {
  if (key === "name") return 0;
  return patient[key] ?? 0;
}

function SortButton({
  sortKey,
  currentKey,
  direction,
  onSort,
}: {
  sortKey: SortKey;
  currentKey: SortKey;
  direction: SortDirection;
  onSort: (key: SortKey) => void;
}) {
  const active = sortKey === currentKey;
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      className={`inline-flex items-center gap-1 text-left font-semibold ${
        active ? "text-[#1c1c1e]" : "text-[#98a2b3] hover:text-[#475467]"
      }`}
    >
      {SORT_LABELS[sortKey]}
      <ChevronsUpDown size={12} className={active && direction === "desc" ? "rotate-180" : ""} />
    </button>
  );
}

export function PatientRecordPool() {
  const [search, setSearch] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("complexity_score");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const { data: patients = [], isLoading } = useQuery<PatientListItem[]>({
    queryKey: ["patients", "records-pool"],
    queryFn: api.listPatients,
  });

  const cohortStats = useMemo(() => {
    const patientCount = patients.length;
    const resourceTotal = patients.reduce((sum, patient) => sum + patient.total_resources, 0);
    const encounterTotal = patients.reduce((sum, patient) => sum + patient.encounter_count, 0);
    const medTotal = patients.reduce((sum, patient) => sum + patient.active_med_count, 0);
    const conditionTotal = patients.reduce((sum, patient) => sum + patient.active_condition_count, 0);
    const highComplexity = patients.filter((patient) =>
      ["complex", "highly_complex"].includes(patient.complexity_tier),
    ).length;
    const tierCounts = patients.reduce<Record<string, number>>((acc, patient) => {
      acc[patient.complexity_tier] = (acc[patient.complexity_tier] ?? 0) + 1;
      return acc;
    }, {});

    return {
      patientCount,
      resourceTotal,
      avgResources: patientCount ? Math.round(resourceTotal / patientCount) : 0,
      avgEncounters: patientCount ? Math.round(encounterTotal / patientCount) : 0,
      activeMedAverage: patientCount ? medTotal / patientCount : 0,
      activeConditionAverage: patientCount ? conditionTotal / patientCount : 0,
      highComplexity,
      tierCounts,
    };
  }, [patients]);

  const filteredPatients = useMemo(() => {
    const query = search.trim().toLowerCase();
    const matches = query
      ? patients.filter((patient) =>
          [
            patient.name,
            patient.gender,
            patient.complexity_tier,
            String(patient.total_resources),
            String(patient.encounter_count),
          ]
            .join(" ")
            .toLowerCase()
            .includes(query),
        )
      : [...patients];

    return matches.sort((a, b) => {
      let comparison = 0;
      if (sortKey === "name") {
        comparison = a.name.localeCompare(b.name);
      } else {
        comparison = numericValue(a, sortKey) - numericValue(b, sortKey);
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [patients, search, sortDirection, sortKey]);

  const selectedPatient = useMemo(
    () =>
      patients.find((patient) => patient.id === selectedPatientId) ??
      filteredPatients[0] ??
      patients[0],
    [filteredPatients, patients, selectedPatientId],
  );

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection(key === "name" ? "asc" : "desc");
  };

  const previewMetrics = selectedPatient
    ? [
        ["Complexity", `${Math.round(selectedPatient.complexity_score)}/100`],
        ["Resources", selectedPatient.total_resources.toLocaleString()],
        ["Encounters", selectedPatient.encounter_count.toLocaleString()],
        ["Active conditions", selectedPatient.active_condition_count.toLocaleString()],
        ["Active meds", selectedPatient.active_med_count.toLocaleString()],
      ]
    : [];

  const quietActions = [
    { title: "Data Aggregator", to: patientUrl("/aggregate", selectedPatient), icon: GitBranch },
    { title: "FHIR Chart", to: patientUrl("/charts", selectedPatient), icon: Database },
    { title: "Clinical Insights", to: patientUrl("/clinical-insights", selectedPatient), icon: Stethoscope },
    { title: "Medication Access", to: patientUrl("/medication-access", selectedPatient), icon: Pill },
  ];

  return (
    <div className="min-h-screen bg-[#f5f6f8] text-[#1c1c1e]">
      <header className="border-b border-[#e1e4eb] bg-white px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6">
          <Link to="/" className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9aa1b2]">
              EHI Exchange Platform
            </p>
            <p className="text-base font-semibold text-[#1c1c1e]">Pool of Patient Records</p>
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-xl border border-[#dfe3eb] bg-white px-4 py-2 text-sm font-semibold text-[#526075] shadow-sm transition-colors hover:border-[#5b76fe] hover:text-[#5b76fe]"
          >
            Back to overview
          </Link>
        </div>
      </header>

      <main className="px-6 py-8">
        <section className="mx-auto max-w-7xl space-y-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[#5b76fe]">
                Synthetic cohort review
              </p>
              <h1 className="text-3xl font-semibold tracking-tight text-[#18191f] lg:text-4xl">
                Browse the Synthea patient pool before opening a workflow.
              </h1>
              <p className="mt-3 text-sm leading-6 text-[#63708a]">
                Use this internal view to sort the demo cohort, inspect basic chart density, and choose a record with enough signal for a walkthrough.
              </p>
            </div>
            <label className="relative block w-full lg:w-[360px]">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#8f97a8]" size={16} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search name, tier, resource count"
                className="w-full rounded-xl border border-[#dfe3eb] bg-white py-3 pl-10 pr-3 text-sm outline-none transition-colors focus:border-[#5b76fe]"
              />
            </label>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {[
              ["Patients", cohortStats.patientCount.toLocaleString(), "Synthea R4 individual bundles", UserRound],
              ["Resources", cohortStats.resourceTotal.toLocaleString(), `${cohortStats.avgResources.toLocaleString()} avg per patient`, FileSearch],
              ["Encounters", cohortStats.avgEncounters.toLocaleString(), "Average encounters per patient", BarChart3],
              ["Higher complexity", cohortStats.highComplexity.toLocaleString(), "Complex or highly complex records", ShieldCheck],
            ].map(([label, value, detail, Icon]) => (
              <div key={label as string} className="rounded-2xl border border-[#e1e6ef] bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#8a94a6]">{label as string}</p>
                    <p className="mt-2 text-2xl font-semibold text-[#101828]">{value as string}</p>
                    <p className="mt-1 text-sm text-[#667085]">{detail as string}</p>
                  </div>
                  <Icon size={18} className="text-[#5b76fe]" />
                </div>
              </div>
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
            <div className="overflow-hidden rounded-2xl border border-[#e1e6ef] bg-white shadow-sm">
              <div className="flex flex-col gap-2 border-b border-[#e9eaef] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-[#101828]">Patient cohort table</h2>
                  <p className="text-sm text-[#667085]">
                    {isLoading ? "Loading patients" : `${filteredPatients.length.toLocaleString()} visible records`}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-[#667085]">
                  {Object.entries(cohortStats.tierCounts).map(([tier, count]) => (
                    <span key={tier} className={`rounded-full px-2.5 py-1 capitalize ${tierClass(tier)}`}>
                      {formatTier(tier)}: {count}
                    </span>
                  ))}
                </div>
              </div>

              <div className="max-h-[620px] overflow-auto">
                <table className="w-full min-w-[900px] text-sm">
                  <thead className="sticky top-0 z-10 border-b border-[#e9eaef] bg-[#fafafa] text-left text-xs uppercase tracking-[0.12em] text-[#98a2b3]">
                    <tr>
                      <th className="px-4 py-3">
                        <SortButton sortKey="name" currentKey={sortKey} direction={sortDirection} onSort={handleSort} />
                      </th>
                      <th className="px-4 py-3">
                        <SortButton sortKey="complexity_score" currentKey={sortKey} direction={sortDirection} onSort={handleSort} />
                      </th>
                      <th className="px-4 py-3">Tier</th>
                      <th className="px-4 py-3">
                        <SortButton sortKey="total_resources" currentKey={sortKey} direction={sortDirection} onSort={handleSort} />
                      </th>
                      <th className="px-4 py-3">
                        <SortButton sortKey="encounter_count" currentKey={sortKey} direction={sortDirection} onSort={handleSort} />
                      </th>
                      <th className="px-4 py-3">
                        <SortButton sortKey="active_condition_count" currentKey={sortKey} direction={sortDirection} onSort={handleSort} />
                      </th>
                      <th className="px-4 py-3">
                        <SortButton sortKey="active_med_count" currentKey={sortKey} direction={sortDirection} onSort={handleSort} />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {isLoading
                      ? Array.from({ length: 10 }).map((_, index) => (
                          <tr key={index} className="border-b border-[#f0f1f5]">
                            <td colSpan={7} className="px-4 py-3">
                              <div className="h-8 animate-pulse rounded-lg bg-[#f0f2f6]" />
                            </td>
                          </tr>
                        ))
                      : filteredPatients.map((patient) => {
                          const selected = selectedPatient?.id === patient.id;
                          return (
                            <tr
                              key={patient.id}
                              onClick={() => setSelectedPatientId(patient.id)}
                              className={`cursor-pointer border-b border-[#f0f1f5] transition-colors last:border-0 ${
                                selected ? "bg-[#f4f6ff]" : "hover:bg-[#fafafa]"
                              }`}
                            >
                              <td className="px-4 py-3">
                                <div className="font-semibold text-[#101828]">{patient.name}</div>
                                <div className="mt-0.5 text-xs capitalize text-[#667085]">
                                  {Number.isFinite(patient.age_years) ? `${Math.round(patient.age_years)} years` : "Age unknown"} / {patient.gender || "unknown"}
                                </div>
                              </td>
                              <td className="px-4 py-3 font-semibold text-[#101828]">{Math.round(patient.complexity_score)}</td>
                              <td className="px-4 py-3">
                                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${tierClass(patient.complexity_tier)}`}>
                                  {formatTier(patient.complexity_tier)}
                                </span>
                              </td>
                              <td className="px-4 py-3 tabular-nums text-[#475467]">{patient.total_resources.toLocaleString()}</td>
                              <td className="px-4 py-3 tabular-nums text-[#475467]">{patient.encounter_count.toLocaleString()}</td>
                              <td className="px-4 py-3 tabular-nums text-[#475467]">{patient.active_condition_count.toLocaleString()}</td>
                              <td className="px-4 py-3 tabular-nums text-[#475467]">{patient.active_med_count.toLocaleString()}</td>
                            </tr>
                          );
                        })}
                  </tbody>
                </table>
              </div>
            </div>

            <aside className="space-y-4">
              <div className="rounded-2xl border border-[#dfe4ff] bg-[#f7f8ff] p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#5b76fe]">Selected record</p>
                <h2 className="mt-2 text-xl font-semibold text-[#101828]">
                  {selectedPatient ? patientLabel(selectedPatient) : "No patient selected"}
                </h2>
                <p className="mt-2 text-sm leading-6 text-[#667085]">
                  Review the chart density before opening a clinical module. This selection is a demo context, not a patient-facing workflow step.
                </p>

                <div className="mt-4 grid grid-cols-2 gap-2">
                  {previewMetrics.map(([label, value]) => (
                    <div key={label} className="rounded-xl border border-[#dfe4ff] bg-white px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#98a2b3]">{label}</p>
                      <p className="mt-1 text-base font-semibold text-[#101828]">{value}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-[#e1e6ef] bg-white p-5 shadow-sm">
                <h2 className="text-base font-semibold text-[#101828]">Open selected context</h2>
                <p className="mt-1 text-sm leading-6 text-[#667085]">
                  Secondary shortcuts for demo review once a row has the right profile.
                </p>
                <div className="mt-4 space-y-2">
                  {quietActions.map((action) => {
                    const Icon = action.icon;
                    return (
                      <Link
                        key={action.title}
                        to={action.to}
                        className="group flex items-center justify-between gap-3 rounded-xl border border-[#e9eaef] px-3 py-2.5 text-sm font-semibold text-[#475467] transition-colors hover:border-[#5b76fe] hover:text-[#5b76fe]"
                      >
                        <span className="flex items-center gap-2">
                          <Icon size={15} />
                          {action.title}
                        </span>
                        <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    );
                  })}
                </div>
              </div>

              <div className="rounded-2xl border border-[#e1e6ef] bg-white p-5 shadow-sm">
                <h2 className="text-base font-semibold text-[#101828]">Cohort averages</h2>
                <div className="mt-4 space-y-3 text-sm">
                  <div className="flex justify-between gap-3">
                    <span className="text-[#667085]">Active meds per patient</span>
                    <span className="font-semibold text-[#101828]">{cohortStats.activeMedAverage.toFixed(1)}</span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span className="text-[#667085]">Active conditions per patient</span>
                    <span className="font-semibold text-[#101828]">{cohortStats.activeConditionAverage.toFixed(1)}</span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span className="text-[#667085]">Resources per patient</span>
                    <span className="font-semibold text-[#101828]">{cohortStats.avgResources.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            </aside>
          </div>
        </section>
      </main>
    </div>
  );
}
