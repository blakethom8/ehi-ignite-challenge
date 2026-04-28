import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
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

function patientLabel(patient: PatientListItem): string {
  const age = Number.isFinite(patient.age_years) ? `${Math.round(patient.age_years)}y` : null;
  const details = [age, patient.gender].filter(Boolean).join(" ");
  return details ? `${patient.name} - ${details}` : patient.name;
}

function patientUrl(path: string, patient?: PatientListItem): string {
  return patient ? `${path}?patient=${patient.id}` : path;
}

export function PatientRecordPool() {
  const [search, setSearch] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);

  const { data: patients = [], isLoading } = useQuery<PatientListItem[]>({
    queryKey: ["patients", "records-pool"],
    queryFn: api.listPatients,
  });

  const filteredPatients = useMemo(() => {
    const query = search.trim().toLowerCase();
    const matches = query
      ? patients.filter((patient) => patientLabel(patient).toLowerCase().includes(query))
      : [...patients].sort((a, b) => b.complexity_score - a.complexity_score);

    return matches.slice(0, 8);
  }, [patients, search]);

  const selectedPatient = useMemo(
    () =>
      patients.find((patient) => patient.id === selectedPatientId) ??
      filteredPatients[0] ??
      patients[0],
    [filteredPatients, patients, selectedPatientId],
  );

  const nextActions = [
    {
      title: "Data Aggregator",
      body: "Collect records and clean them into the patient-owned FHIR Chart.",
      to: patientUrl("/aggregate", selectedPatient),
      icon: GitBranch,
      primary: true,
    },
    {
      title: "FHIR Chart",
      body: "Open the cleaned chart with facts, source links, and review flags.",
      to: patientUrl("/charts", selectedPatient),
      icon: Database,
    },
    {
      title: "Pre-Op Support",
      body: "Turn the chart into a fast surgical readiness brief.",
      to: patientUrl("/preop", selectedPatient),
      icon: Stethoscope,
    },
    {
      title: "Medication Access",
      body: "Find affordability and access paths using medication context.",
      to: patientUrl("/medication-access", selectedPatient),
      icon: Pill,
    },
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
        <section className="mx-auto max-w-7xl">
          <div className="mb-6 max-w-3xl">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[#5b76fe]">
              Walkthrough guide
            </p>
            <h1 className="text-4xl font-semibold tracking-tight text-[#18191f] lg:text-5xl">
              Choose a synthetic patient and follow the data workflow.
            </h1>
            <p className="mt-4 text-base leading-7 text-[#63708a]">
              This is where formal demos should live. Pick a patient, open Data Aggregator, then move from the cleaned FHIR Chart into clinical or marketplace use cases.
            </p>
          </div>

          <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-[24px] border border-[#e1e6ef] bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">Select patient</h2>
                  <p className="text-sm text-[#6a7386]">
                    {isLoading ? "Loading synthetic records" : `${patients.length.toLocaleString()} synthetic patients available`}
                  </p>
                </div>
                <UserRound size={20} className="text-[#5b76fe]" />
              </div>

              <label className="relative block">
                <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#8f97a8]" size={16} />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search patient name"
                  className="w-full rounded-xl border border-[#dfe3eb] bg-[#fbfcff] py-3 pl-10 pr-3 text-sm outline-none transition-colors focus:border-[#5b76fe] focus:bg-white"
                />
              </label>

              <div className="mt-4 max-h-[430px] space-y-2 overflow-y-auto pr-1">
                {isLoading
                  ? Array.from({ length: 6 }).map((_, index) => (
                      <div key={index} className="h-[74px] animate-pulse rounded-xl bg-[#f0f2f6]" />
                    ))
                  : filteredPatients.map((patient) => {
                      const selected = selectedPatient?.id === patient.id;
                      return (
                        <button
                          key={patient.id}
                          type="button"
                          onClick={() => setSelectedPatientId(patient.id)}
                          className={`w-full rounded-xl border p-3 text-left transition-colors ${
                            selected
                              ? "border-[#5b76fe] bg-[#eef1ff]"
                              : "border-[#e4e8f0] bg-white hover:border-[#bfc8ff]"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="break-words text-sm font-semibold text-[#1c1c1e]">
                                {patientLabel(patient)}
                              </p>
                              <p className="mt-1 text-xs text-[#6a7386]">
                                {patient.total_resources.toLocaleString()} resources / {patient.encounter_count} encounters
                              </p>
                            </div>
                            <span className="shrink-0 rounded-full bg-white px-2 py-1 text-xs font-semibold text-[#566070]">
                              {Math.round(patient.complexity_score)}
                            </span>
                          </div>
                        </button>
                      );
                    })}
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-[24px] border border-[#c9f0e7] bg-[#effbf8] p-6 shadow-sm">
                <div className="flex flex-col justify-between gap-5 md:flex-row md:items-start">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#008f7a]">
                      Selected record
                    </p>
                    <h2 className="mt-2 text-2xl font-semibold">
                      {selectedPatient ? patientLabel(selectedPatient) : "Choose a patient"}
                    </h2>
                    <p className="mt-3 max-w-2xl text-sm leading-6 text-[#496071]">
                      Use this patient to walk through collection, cleaning, FHIR Chart review, and downstream module behavior.
                    </p>
                  </div>
                  <Link
                    to={patientUrl("/aggregate", selectedPatient)}
                    className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-[#5b76fe] px-5 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#445ee8]"
                  >
                    Open Data Aggregator
                    <ArrowRight size={16} />
                  </Link>
                </div>

                <div className="mt-6 grid gap-3 sm:grid-cols-3">
                  {[
                    ["Pull data", "Bring in records from portals, files, clinics, labs, pharmacies, and payers.", FileSearch],
                    ["Clean chart", "Normalize facts, preserve source links, and flag conflicts or missing fields.", ShieldCheck],
                    ["Use it", "Send the chart into clinical insight, marketplace, sharing, or review workflows.", ArrowRight],
                  ].map(([title, body, Icon]) => (
                    <div key={title as string} className="rounded-2xl border border-[#bdebdc] bg-white/75 p-4">
                      <Icon size={18} className="mb-3 text-[#008f7a]" />
                      <h3 className="font-semibold">{title as string}</h3>
                      <p className="mt-1 text-sm leading-6 text-[#5c6d7c]">{body as string}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-[24px] border border-[#e1e6ef] bg-white p-6 shadow-sm">
                <div className="mb-5">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#8f97a8]">
                    Use this selected patient
                  </p>
                  <h2 className="mt-2 text-xl font-semibold">Choose where to go next</h2>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {nextActions.map((action) => {
                    const Icon = action.icon;
                    return (
                      <Link
                        key={action.title}
                        to={action.to}
                        className={`group rounded-2xl border p-4 transition-all hover:-translate-y-0.5 hover:shadow-sm ${
                          action.primary
                            ? "border-[#cfd7ff] bg-[#f5f7ff]"
                            : "border-[#e4e8f0] bg-white hover:border-[#cfd7ff]"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
                            <Icon size={18} />
                          </div>
                          <div className="min-w-0">
                            <h3 className="font-semibold text-[#1c1c1e]">{action.title}</h3>
                            <p className="mt-1 text-sm leading-6 text-[#68748a]">{action.body}</p>
                            <span className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-[#5b76fe] transition-all group-hover:gap-2">
                              Open
                              <ArrowRight size={14} />
                            </span>
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
