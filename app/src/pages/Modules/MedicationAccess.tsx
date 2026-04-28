import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, DollarSign, HeartHandshake, MessageSquareText, Pill, Search, Store, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";

function formatDate(value: string | null): string {
  if (!value) return "Unknown";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function AccessCard({
  icon: Icon,
  label,
  body,
}: {
  icon: LucideIcon;
  label: string;
  body: string;
}) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
        <Icon size={18} />
      </div>
      <h3 className="text-sm font-semibold text-[#1c1c1e]">{label}</h3>
      <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
    </div>
  );
}

export function MedicationAccess() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });
  const safetyQ = useQuery({
    queryKey: ["safety", patientId],
    queryFn: () => api.getSafety(patientId!),
    enabled: !!patientId,
  });

  const overview = overviewQ.data;
  const safety = safetyQ.data;
  const activeMeds = useMemo(() => (overview?.medications ?? []).filter((med) => med.is_active).slice(0, 8), [overview]);
  const flaggedClasses = useMemo(
    () => (safety?.flags ?? []).filter((flag) => flag.status === "ACTIVE" && flag.medications.length > 0),
    [safety]
  );

  if (!patientId) {
    return (
      <EmptyState
        icon={UserRound}
        title="Choose a patient to begin"
        bullets={[
          "Review active medications before cost research",
          "Identify classes likely to need special assistance",
          "Prepare a shareable affordability plan",
        ]}
        stat="Medication access module"
      />
    );
  }

  if (overviewQ.isLoading || safetyQ.isLoading) {
    return (
      <div className="mx-auto max-w-7xl space-y-5 p-6">
        <div className="h-56 animate-pulse rounded-3xl bg-[#e9eaef]" />
        <div className="grid gap-4 md:grid-cols-3">
          <div className="h-44 animate-pulse rounded-2xl bg-[#e9eaef]" />
          <div className="h-44 animate-pulse rounded-2xl bg-[#e9eaef]" />
          <div className="h-44 animate-pulse rounded-2xl bg-[#e9eaef]" />
        </div>
      </div>
    );
  }

  if (overviewQ.isError || safetyQ.isError || !overview || !safety) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load medication access workspace.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <Pill size={13} />
              Medication access module
            </p>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
              Affordability brief for {overview.name}
            </h1>
            <p className="mt-3 text-base leading-7 text-[#667085]">
              This module starts with the patient medication list, then organizes the future workflow for pricing, manufacturer
              assistance, coupons, pharmacy comparison, and grant-style support options.
            </p>
          </div>

          <div className="grid min-w-[260px] gap-3 rounded-2xl bg-[#fafbff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Active medications</p>
              <p className="mt-1 text-2xl font-semibold text-[#1c1c1e]">{overview.active_med_count}</p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Safety classes</p>
              <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">{flaggedClasses.length} active flagged classes</p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Last record activity</p>
              <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">{formatDate(overview.latest_encounter_dt)}</p>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <AccessCard
          icon={DollarSign}
          label="How to read this module"
          body="Start with active therapies, then separate clinical medication context from affordability research and support options."
        />
        <AccessCard
          icon={HeartHandshake}
          label="Decision guidance"
          body="Use the output as an access plan: price paths, assistance requirements, likely friction, and items needing clinician or pharmacy verification."
        />
        <AccessCard
          icon={MessageSquareText}
          label="Future access agent"
          body="This module should use a dedicated agent harness for drug normalization, price/source search, assistance programs, and cited recommendations."
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <AccessCard
          icon={DollarSign}
          label="Price comparison"
          body="Compare retail, discount, mail-order, and membership pharmacy prices for active medications."
        />
        <AccessCard
          icon={HeartHandshake}
          label="Support programs"
          body="Collect manufacturer assistance, foundation support, coupons, and patient assistance requirements."
        />
        <AccessCard
          icon={Store}
          label="Fulfillment plan"
          body="Turn the research into a practical next-step list: pharmacy option, enrollment path, and documents needed."
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-[#1c1c1e]">Active Medication Starting Point</h2>
              <p className="mt-1 text-sm text-[#667085]">The affordability workflow begins with current therapies from the FHIR record.</p>
            </div>
            <Link
              to={`/explorer?patient=${patientId}`}
              className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-semibold text-[#5b76fe] hover:bg-[#eef1ff]"
            >
              Patient record
              <ArrowRight size={14} />
            </Link>
          </div>

          <div className="mt-5 space-y-3">
            {activeMeds.length > 0 ? (
              activeMeds.map((med) => (
                <div key={med.med_id} className="rounded-xl border border-[#e9eaef] p-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="font-semibold text-[#1c1c1e]">{med.display}</p>
                      <p className="mt-1 text-sm text-[#667085]">Authored {formatDate(med.authored_on)} · {med.status}</p>
                    </div>
                    <span className="w-fit rounded-full bg-[#eef1ff] px-2.5 py-1 text-xs font-semibold text-[#5b76fe]">
                      Active
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-dashed border-[#d5d9e5] p-6 text-sm text-[#667085]">
                No active medications were found for this patient.
              </div>
            )}
          </div>
        </section>

        <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <Search size={18} className="text-[#5b76fe]" />
            <h2 className="text-lg font-semibold text-[#1c1c1e]">Research Queue</h2>
          </div>
          <div className="mt-5 space-y-4">
            {[
              ["Medication normalization", "Map active medication display names to ingredient, dose form, and candidate generic/brand options."],
              ["Price and support search", "Collect prices and support programs from public sources with source links and update dates."],
              ["Patient-ready plan", "Rank viable options by affordability, friction, and clinical verification needed."],
            ].map(([label, body], index) => (
              <div key={label} className="flex gap-3">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#eef1ff] text-xs font-semibold text-[#5b76fe]">
                  {index + 1}
                </div>
                <div>
                  <p className="text-sm font-semibold text-[#1c1c1e]">{label}</p>
                  <p className="mt-1 text-sm leading-6 text-[#667085]">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
