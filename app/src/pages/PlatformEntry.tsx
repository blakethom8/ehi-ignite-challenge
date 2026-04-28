import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Brain,
  Database,
  GitBranch,
  Search,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { api } from "../api/client";
import type { PatientListItem } from "../types";

function patientLabel(patient: PatientListItem): string {
  const age = Number.isFinite(patient.age_years) ? `${Math.round(patient.age_years)}y` : null;
  const details = [age, patient.gender].filter(Boolean).join(" ");
  return details ? `${patient.name} - ${details}` : patient.name;
}

function patientUrl(path: string, patient?: PatientListItem): string {
  return patient ? `${path}?patient=${patient.id}` : path;
}

export function PlatformEntry() {
  const [search, setSearch] = useState("");
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const patientId = searchParams.get("patient");

  const { data: patients = [], isLoading } = useQuery<PatientListItem[]>({
    queryKey: ["patients", "platform-entry"],
    queryFn: api.listPatients,
  });

  const filteredPatients = useMemo(() => {
    const query = search.trim().toLowerCase();
    const matches = query
      ? patients.filter((patient) => patientLabel(patient).toLowerCase().includes(query))
      : [...patients].sort((a, b) => b.complexity_score - a.complexity_score);

    return matches.slice(0, 80);
  }, [patients, search]);

  const selectedPatient = patientId
    ? patients.find((patient) => patient.id === patientId)
    : undefined;

  const actions = [
    {
      title: "Data Aggregator",
      to: patientUrl("/aggregate", selectedPatient),
      icon: GitBranch,
    },
    {
      title: "FHIR Chart",
      to: patientUrl("/charts", selectedPatient),
      icon: Database,
    },
    {
      title: "Clinical Insights",
      to: patientUrl("/clinical-insights", selectedPatient),
      icon: Brain,
    },
  ];

  return (
    <main className="mx-auto flex min-h-full max-w-7xl flex-col justify-center py-8">
      <section className="mx-auto w-full max-w-6xl">
        <div className="mb-5 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#5b76fe]">
              No workspace selected
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-[#18191f] lg:text-4xl">
              Select a patient record to enter the platform.
            </h1>
          </div>
          <div className="max-w-xl rounded-2xl border border-[#c9f0e7] bg-[#effbf8] p-4">
            <div className="flex gap-3">
              <ShieldCheck size={18} className="mt-0.5 shrink-0 text-[#008f7a]" />
              <p className="text-sm leading-6 text-[#486274]">
                This selector is shown for the demo because we are using synthetic Synthea patient records. In the real product, patient context would usually come from onboarding, identity linking, or an existing workspace.
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-[28px] border border-[#dfe5f0] bg-white shadow-sm">
          <div className="flex flex-col gap-4 border-b border-[#e7eaf1] p-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <SlidersHorizontal size={17} className="text-[#5b76fe]" />
                <h2 className="text-lg font-semibold">Advanced patient selection</h2>
              </div>
              <p className="mt-1 text-sm text-[#68748a]">
                {isLoading ? "Loading synthetic records" : `${patients.length.toLocaleString()} synthetic records available`}
              </p>
            </div>

            <label className="relative block w-full lg:w-[360px]">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#8f97a8]" size={16} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search patient name"
                className="w-full rounded-xl border border-[#dfe3eb] bg-[#fbfcff] py-3 pl-10 pr-3 text-sm outline-none transition-colors focus:border-[#5b76fe] focus:bg-white"
              />
            </label>
          </div>

          <div className="max-h-[500px] overflow-auto">
            <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
              <thead className="sticky top-0 z-10 bg-[#fbfcff] text-xs uppercase tracking-[0.12em] text-[#8a93a6]">
                <tr>
                  <th className="border-b border-[#e7eaf1] px-5 py-3 font-semibold">Patient</th>
                  <th className="border-b border-[#e7eaf1] px-4 py-3 font-semibold">Age / Sex</th>
                  <th className="border-b border-[#e7eaf1] px-4 py-3 font-semibold">Resources</th>
                  <th className="border-b border-[#e7eaf1] px-4 py-3 font-semibold">Encounters</th>
                  <th className="border-b border-[#e7eaf1] px-4 py-3 font-semibold">Conditions</th>
                  <th className="border-b border-[#e7eaf1] px-4 py-3 font-semibold">Meds</th>
                  <th className="border-b border-[#e7eaf1] px-4 py-3 font-semibold">Complexity</th>
                  <th className="border-b border-[#e7eaf1] px-5 py-3 font-semibold" />
                </tr>
              </thead>
              <tbody>
                {isLoading
                  ? Array.from({ length: 8 }).map((_, index) => (
                      <tr key={index}>
                        <td colSpan={8} className="px-5 py-2">
                          <div className="h-12 animate-pulse rounded-xl bg-[#f0f2f6]" />
                        </td>
                      </tr>
                    ))
                  : filteredPatients.map((patient) => {
                      const selected = patient.id === patientId;
                      return (
                        <tr
                          key={patient.id}
                          className={`cursor-pointer transition-colors ${
                            selected ? "bg-[#eef1ff]" : "hover:bg-[#f7f8ff]"
                          }`}
                          onClick={() => navigate(`/explorer?patient=${patient.id}`)}
                        >
                          <td className="border-b border-[#eef0f5] px-5 py-3">
                            <p className="font-semibold text-[#1c1c1e]">{patient.name}</p>
                            <p className="mt-0.5 text-xs text-[#8a93a6]">{patient.complexity_tier.replace("_", " ")}</p>
                          </td>
                          <td className="border-b border-[#eef0f5] px-4 py-3 text-[#5d687c]">
                            {Math.round(patient.age_years)} / {patient.gender}
                          </td>
                          <td className="border-b border-[#eef0f5] px-4 py-3 font-semibold text-[#1c1c1e]">
                            {patient.total_resources.toLocaleString()}
                          </td>
                          <td className="border-b border-[#eef0f5] px-4 py-3 text-[#5d687c]">{patient.encounter_count}</td>
                          <td className="border-b border-[#eef0f5] px-4 py-3 text-[#5d687c]">{patient.active_condition_count}</td>
                          <td className="border-b border-[#eef0f5] px-4 py-3 text-[#5d687c]">{patient.active_med_count}</td>
                          <td className="border-b border-[#eef0f5] px-4 py-3">
                            <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#566070]">
                              {Math.round(patient.complexity_score)}
                            </span>
                          </td>
                          <td className="border-b border-[#eef0f5] px-5 py-3 text-right">
                            <button
                              type="button"
                              className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
                                selected
                                  ? "bg-[#5b76fe] text-white"
                                  : "bg-[#eef1ff] text-[#5b76fe]"
                              }`}
                            >
                              {selected ? "Selected" : "Select"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="mt-5 rounded-[24px] border border-[#e1e6ef] bg-white p-5 shadow-sm">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8f97a8]">
                Selected patient context
              </p>
              <h2 className="mt-1 text-xl font-semibold">
                {selectedPatient ? patientLabel(selectedPatient) : "No patient selected"}
              </h2>
              <p className="mt-1 text-sm text-[#68748a]">
                {selectedPatient
                  ? "Choose where to open this patient in the platform."
                  : "Select a patient from the table or the header dropdown to continue."}
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              {actions.map((action) => {
                const Icon = action.icon;
                return (
                  <Link
                    key={action.title}
                    to={action.to}
                    className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold shadow-sm transition-colors ${
                      selectedPatient
                        ? "border border-[#dfe3eb] bg-white text-[#526075] hover:border-[#5b76fe] hover:text-[#5b76fe]"
                        : "pointer-events-none border border-[#e5e8ef] bg-[#f4f6fa] text-[#a4abb8]"
                    }`}
                  >
                    <Icon size={16} />
                    {action.title}
                    <ArrowRight size={14} />
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
