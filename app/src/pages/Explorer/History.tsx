import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  CalendarDays,
  ChevronRight,
  Clock3,
  FileText,
  Filter,
  Info,
  List,
  Pill,
  Scissors,
  Syringe,
  X,
} from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type {
  CareJourneyResponse,
  EncounterEvent,
  ImmunizationItem,
  MedRow,
  MedicationEpisodeItem,
  PatientOverview,
  ProcedureItem,
  TimelineResponse,
} from "../../types";

type HistoryTab = "encounters" | "medications" | "procedures" | "immunizations";
type ViewMode = "timeline" | "table";
type Tone = "blue" | "teal" | "amber" | "rose";

interface HistoryEvent {
  id: string;
  date: string | null;
  title: string;
  meta: string;
  detail?: string;
  tone: Tone;
}

const TABS: Array<{ id: HistoryTab; label: string; icon: typeof CalendarDays }> = [
  { id: "encounters", label: "Encounters", icon: CalendarDays },
  { id: "medications", label: "Medications", icon: Pill },
  { id: "procedures", label: "Procedures", icon: Scissors },
  { id: "immunizations", label: "Immunizations", icon: Syringe },
];

const TONE_CLASS: Record<Tone, { dot: string; bg: string; text: string }> = {
  blue: { dot: "bg-[#5b76fe]", bg: "bg-[#eef1ff]", text: "text-[#3730a3]" },
  teal: { dot: "bg-[#0f766e]", bg: "bg-[#dff6ef]", text: "text-[#0f766e]" },
  amber: { dot: "bg-[#f59e0b]", bg: "bg-[#fffbeb]", text: "text-[#92400e]" },
  rose: { dot: "bg-[#ef4444]", bg: "bg-[#fef2f2]", text: "text-[#991b1b]" },
};

function fmtDate(value: string | null): string {
  if (!value) return "Unknown date";
  return new Date(value).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function fmtYear(value: string | null): string {
  if (!value) return "Unknown";
  return String(new Date(value).getFullYear());
}

function dateValue(value: string | null): number {
  if (!value) return Number.NEGATIVE_INFINITY;
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? Number.NEGATIVE_INFINITY : timestamp;
}

function groupByYear(events: HistoryEvent[]): Array<{ year: string; events: HistoryEvent[] }> {
  const groups = new Map<string, HistoryEvent[]>();
  for (const event of events) {
    const year = fmtYear(event.date);
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year)!.push(event);
  }
  return Array.from(groups.entries())
    .map(([year, groupedEvents]) => ({ year, events: groupedEvents }))
    .sort((a, b) => {
      if (a.year === "Unknown") return 1;
      if (b.year === "Unknown") return -1;
      return Number(b.year) - Number(a.year);
    });
}

function encounterToHistoryEvent(encounter: EncounterEvent): HistoryEvent {
  return {
    id: encounter.encounter_id,
    date: encounter.start,
    title: encounter.reason_display || encounter.encounter_type || encounter.class_code || "Encounter",
    meta: `${encounter.class_code || "Unknown"} encounter`,
    detail: `${encounter.linked_observation_count} labs/vitals · ${encounter.linked_condition_count} conditions · ${encounter.linked_procedure_count} procedures`,
    tone: (encounter.class_code === "EMER" ? "rose" : "blue") as Tone,
  };
}

function encounterEvents(data: TimelineResponse | undefined): HistoryEvent[] {
  if (!data) return [];
  return data.encounters
    .map(encounterToHistoryEvent)
    .sort((a, b) => dateValue(b.date) - dateValue(a.date));
}

function medicationEpisodeEvents(data: CareJourneyResponse | undefined): HistoryEvent[] {
  if (!data) return [];
  return data.medication_episodes
    .map((med: MedicationEpisodeItem) => ({
      id: med.episode_id,
      date: med.start_date,
      title: med.display,
      meta: med.is_active ? "Active medication episode" : "Historical medication episode",
      detail: [
        med.drug_class || "Unclassified",
        med.request_count ? `${med.request_count} request${med.request_count !== 1 ? "s" : ""}` : null,
        med.end_date ? `ended ${fmtDate(med.end_date)}` : "ongoing or no end date",
      ].filter(Boolean).join(" · "),
      tone: (med.is_active ? "teal" : "blue") as Tone,
    }))
    .sort((a, b) => dateValue(b.date) - dateValue(a.date));
}

function medicationCatalogEvents(data: PatientOverview | undefined): HistoryEvent[] {
  if (!data) return [];
  return data.medications
    .map((med: MedRow) => ({
      id: med.med_id,
      date: med.authored_on,
      title: med.display,
      meta: med.is_active ? "Active medication" : med.status || "Historical medication",
      detail: med.authored_on ? `ordered ${fmtDate(med.authored_on)}` : "No authored date available",
      tone: (med.is_active ? "teal" : "blue") as Tone,
    }))
    .sort((a, b) => dateValue(b.date) - dateValue(a.date));
}

function procedureEvents(data: ProcedureItem[] | undefined): HistoryEvent[] {
  if (!data) return [];
  return data
    .map((procedure) => ({
      id: procedure.procedure_id,
      date: procedure.performed_start,
      title: procedure.display || "Procedure",
      meta: procedure.status || "Unknown status",
      detail: procedure.reason_display || undefined,
      tone: "amber" as const,
    }))
    .sort((a, b) => dateValue(b.date) - dateValue(a.date));
}

function immunizationEvents(data: ImmunizationItem[] | undefined): HistoryEvent[] {
  if (!data) return [];
  return data
    .map((imm) => ({
      id: imm.imm_id,
      date: imm.occurrence_dt,
      title: imm.display || "Immunization",
      meta: imm.status || "Unknown status",
      detail: imm.cvx_code ? `CVX ${imm.cvx_code}` : undefined,
      tone: "teal" as const,
    }))
    .sort((a, b) => dateValue(b.date) - dateValue(a.date));
}

function TimelineList({ events }: { events: HistoryEvent[] }) {
  const groups = groupByYear(events);

  if (events.length === 0) {
    return (
      <div className="rounded-2xl border border-[#e9eaef] bg-white p-8 text-center text-sm text-[#6b7280]">
        No dated records available for this tab.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {groups.map((group) => (
        <section key={group.year}>
          <div className="mb-2 flex items-center gap-3">
            <span className="text-sm font-semibold text-[#5b76fe]">{group.year}</span>
            <div className="h-px flex-1 bg-[#e9eaef]" />
            <span className="text-xs text-[#a5a8b5]">{group.events.length} record{group.events.length !== 1 ? "s" : ""}</span>
          </div>
          <div className="space-y-2">
            {group.events.map((event) => {
              const tone = TONE_CLASS[event.tone];
              return (
                <article key={event.id} className="rounded-xl border border-[#e9eaef] bg-white px-4 py-3 shadow-sm">
                  <div className="grid gap-3 sm:grid-cols-[120px_1fr]">
                    <div className="text-sm font-semibold text-[#555a6a]">{fmtDate(event.date)}</div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${tone.dot}`} />
                        <h3 className="text-sm font-semibold text-[#1c1c1e]">{event.title}</h3>
                        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${tone.bg} ${tone.text}`}>
                          {event.meta}
                        </span>
                      </div>
                      {event.detail && <p className="mt-1 text-sm leading-6 text-[#6b7280]">{event.detail}</p>}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

function TableView({ events }: { events: HistoryEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="rounded-2xl border border-[#e9eaef] bg-white p-8 text-center text-sm text-[#6b7280]">
        No records available for this tab.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-[#e9eaef] bg-white shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#e9eaef] bg-[#f9fafb] text-left text-xs uppercase tracking-[0.12em] text-[#a5a8b5]">
            <th className="px-4 py-3 font-semibold">Date</th>
            <th className="px-4 py-3 font-semibold">Record</th>
            <th className="px-4 py-3 font-semibold">Context</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id} className="border-b border-[#f0f1f5] last:border-0">
              <td className="whitespace-nowrap px-4 py-3 font-medium text-[#555a6a]">{fmtDate(event.date)}</td>
              <td className="px-4 py-3 text-[#1c1c1e]">
                <div className="font-semibold">{event.title}</div>
                <div className="mt-0.5 text-xs text-[#6b7280]">{event.meta}</div>
              </td>
              <td className="px-4 py-3 text-[#6b7280]">{event.detail || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function encounterClassLabel(classCode: string): string {
  const labels: Record<string, string> = {
    AMB: "Ambulatory",
    EMER: "Emergency",
    IMP: "Inpatient",
    VR: "Virtual",
    WELLNESS: "Wellness",
  };
  return labels[classCode] ?? (classCode || "Unknown");
}

function encounterClassTone(classCode: string): string {
  if (classCode === "EMER") return "bg-[#fef2f2] text-[#b91c1c]";
  if (classCode === "IMP") return "bg-[#fffbeb] text-[#92400e]";
  if (classCode === "AMB") return "bg-[#eef1ff] text-[#5b76fe]";
  return "bg-[#f5f6f8] text-[#555a6a]";
}

function resourceSummary(encounter: EncounterEvent): string {
  const parts = [
    encounter.linked_observation_count ? `${encounter.linked_observation_count} Obs` : null,
    encounter.linked_condition_count ? `${encounter.linked_condition_count} Cond` : null,
    encounter.linked_procedure_count ? `${encounter.linked_procedure_count} Proc` : null,
    encounter.linked_medication_count ? `${encounter.linked_medication_count} Med` : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" / ") : "No linked resources";
}

function encounterTypeLabel(encounter: EncounterEvent): string {
  return encounter.encounter_type || encounter.reason_display || encounterClassLabel(encounter.class_code) || "Encounter";
}

function looksLikeSourceName(value: string | null | undefined): boolean {
  if (!value) return false;
  return /\.(json|pdf|csv|xml|txt)$/i.test(value) || /^[a-f0-9]{8,}-/i.test(value);
}

function friendlySourceName(value: string | null | undefined): string {
  if (!value) return "Source unavailable";
  return value.replace(/^[a-f0-9]{8,}-/i, "").replace(/_/g, " ");
}

function providerPrimaryLabel(encounter: EncounterEvent): string {
  if (encounter.practitioner_name && !looksLikeSourceName(encounter.practitioner_name)) return encounter.practitioner_name;
  if (encounter.provider_org && !looksLikeSourceName(encounter.provider_org)) return encounter.provider_org;
  return "Provider not captured";
}

function providerSecondaryLabel(encounter: EncounterEvent): string {
  const sourceCandidate = looksLikeSourceName(encounter.provider_org)
    ? encounter.provider_org
    : looksLikeSourceName(encounter.practitioner_name)
      ? encounter.practitioner_name
      : "";
  if (sourceCandidate) return `Source: ${friendlySourceName(sourceCandidate)}`;
  if (encounter.provider_org) return encounter.provider_org;
  return "Site not captured";
}

function providerFilterLabel(encounter: EncounterEvent): string {
  const primary = providerPrimaryLabel(encounter);
  const secondary = providerSecondaryLabel(encounter).replace(/^Source: /, "");
  if (!secondary || secondary === "Site not captured" || secondary === primary) return primary;
  return `${primary} · ${secondary}`;
}

function EncounterDetailModal({
  encounter,
  onClose,
}: {
  encounter: EncounterEvent;
  onClose: () => void;
}) {
  const resources = [
    { label: "Observations", count: encounter.linked_observation_count },
    { label: "Conditions", count: encounter.linked_condition_count },
    { label: "Procedures", count: encounter.linked_procedure_count },
    { label: "Medications", count: encounter.linked_medication_count },
  ];
  const linkedTotal = resources.reduce((sum, item) => sum + item.count, 0);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#101828]/35 px-4 py-8 backdrop-blur-[2px]">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="encounter-detail-title"
        className="w-full max-w-3xl overflow-hidden rounded-2xl border border-[#dfe4ea] bg-white shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-[#eef0f5] px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#087d75]">Encounter detail</p>
            <h2 id="encounter-detail-title" className="mt-1 text-lg font-semibold text-[#1c1c1e]">
              {encounterTypeLabel(encounter)}
            </h2>
            <p className="mt-1 text-sm text-[#667085]">{fmtDate(encounter.start)}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#dfe4ea] text-[#667085] hover:border-[#5b76fe] hover:text-[#5b76fe]"
            aria-label="Close encounter detail"
          >
            <X size={16} />
          </button>
        </header>

        <div className="space-y-4 p-5">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-[#e9eaef] bg-[#f9fafb] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#98a2b3]">Provider / site</p>
              <p className="mt-2 text-sm font-semibold text-[#1c1c1e]">{providerPrimaryLabel(encounter)}</p>
              <p className="mt-1 text-xs leading-5 text-[#667085]">{providerSecondaryLabel(encounter)}</p>
            </div>
            <div className="rounded-xl border border-[#e9eaef] bg-[#f9fafb] p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#98a2b3]">FHIR class</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${encounterClassTone(encounter.class_code)}`}>
                  {encounterClassLabel(encounter.class_code)}
                </span>
                <span className="text-xs text-[#667085]">{encounter.class_code || "No class code"}</span>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-[#e9eaef]">
            <div className="border-b border-[#eef0f5] px-4 py-3">
              <p className="text-sm font-semibold text-[#1c1c1e]">Linked chart resources</p>
              <p className="mt-1 text-xs text-[#667085]">
                These counts show what the encounter can currently explain in the published chart.
              </p>
            </div>
            {linkedTotal === 0 ? (
              <div className="flex items-start gap-3 p-4 text-sm text-[#667085]">
                <Info size={16} className="mt-0.5 shrink-0 text-[#f59e0b]" />
                <p>
                  No labs, conditions, procedures, or medications are linked to this encounter yet. This is a data-model gap to resolve in the harmonization layer, not a user decision.
                </p>
              </div>
            ) : (
              <div className="grid gap-2 p-4 sm:grid-cols-4">
                {resources.map((item) => (
                  <div key={item.label} className="rounded-lg border border-[#e9eaef] bg-white p-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#98a2b3]">{item.label}</p>
                    <p className="mt-1 text-xl font-semibold text-[#1c1c1e]">{item.count}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <details className="rounded-xl border border-[#e9eaef] bg-[#f9fafb] p-4">
            <summary className="cursor-pointer text-sm font-semibold text-[#475467]">Technical provenance</summary>
            <dl className="mt-3 grid gap-2 text-xs text-[#667085]">
              <div>
                <dt className="font-semibold uppercase tracking-[0.12em] text-[#98a2b3]">Encounter ID</dt>
                <dd className="mt-1 break-all font-mono">{encounter.encounter_id}</dd>
              </div>
              <div>
                <dt className="font-semibold uppercase tracking-[0.12em] text-[#98a2b3]">Source label</dt>
                <dd className="mt-1">{friendlySourceName(encounter.provider_org || encounter.practitioner_name)}</dd>
              </div>
            </dl>
          </details>
        </div>
      </section>
    </div>
  );
}

function EncounterHistoryTable({
  encounters,
  onSelectEncounter,
}: {
  encounters: EncounterEvent[];
  onSelectEncounter: (encounter: EncounterEvent) => void;
}) {
  if (encounters.length === 0) {
    return (
      <div className="rounded-2xl border border-[#e9eaef] bg-white p-8 text-center text-sm text-[#6b7280]">
        No encounters match the current filters.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-[#e9eaef] bg-white shadow-sm">
      <table className="w-full min-w-[980px] text-sm">
        <thead>
          <tr className="border-b border-[#e9eaef] bg-[#f9fafb] text-left text-xs uppercase tracking-[0.12em] text-[#a5a8b5]">
            <th className="px-4 py-3 font-semibold">Date</th>
            <th className="px-4 py-3 font-semibold">Class</th>
            <th className="px-4 py-3 font-semibold">Type</th>
            <th className="px-4 py-3 font-semibold">Reason</th>
            <th className="px-4 py-3 font-semibold">Provider / Site</th>
            <th className="px-4 py-3 font-semibold">Resources</th>
          </tr>
        </thead>
        <tbody>
          {encounters.map((encounter) => (
            <tr
              key={encounter.encounter_id}
              tabIndex={0}
              onClick={() => onSelectEncounter(encounter)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectEncounter(encounter);
                }
              }}
              className="cursor-pointer border-b border-[#f0f1f5] last:border-0 hover:bg-[#fafafa] focus:bg-[#f4f6ff] focus:outline-none"
            >
              <td className="whitespace-nowrap px-4 py-3 font-medium text-[#1c1c1e]">{fmtDate(encounter.start)}</td>
              <td className="px-4 py-3">
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${encounterClassTone(encounter.class_code)}`}>
                  {encounterClassLabel(encounter.class_code)}
                </span>
              </td>
              <td className="px-4 py-3 text-[#475467]">{encounterTypeLabel(encounter)}</td>
              <td className="px-4 py-3 text-[#475467]">{encounter.reason_display || "-"}</td>
              <td className="px-4 py-3 text-[#475467]">
                <div className="font-medium text-[#1c1c1e]">{providerPrimaryLabel(encounter)}</div>
                <div className="mt-0.5 text-xs text-[#667085]">{providerSecondaryLabel(encounter)}</div>
              </td>
              <td className="px-4 py-3">
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#5b76fe]">
                  <FileText size={13} />
                  {resourceSummary(encounter)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ExplorerHistory() {
  const [params] = useSearchParams();
  const patientId = params.get("patient");
  const [tab, setTab] = useState<HistoryTab>("encounters");
  const [view, setView] = useState<ViewMode>("table");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [providerFilter, setProviderFilter] = useState<string>("all");
  const [selectedEncounter, setSelectedEncounter] = useState<EncounterEvent | null>(null);

  const timelineQ = useQuery({
    queryKey: ["timeline", patientId],
    queryFn: () => api.getTimeline(patientId!),
    enabled: !!patientId,
  });
  const careQ = useQuery({
    queryKey: ["care-journey", patientId],
    queryFn: () => api.getCareJourney(patientId!),
    enabled: !!patientId && tab === "medications",
    retry: false,
  });
  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId && tab === "medications",
  });
  const proceduresQ = useQuery({
    queryKey: ["procedures", patientId],
    queryFn: () => api.getProcedures(patientId!),
    enabled: !!patientId && tab === "procedures",
  });
  const immunizationsQ = useQuery({
    queryKey: ["immunizations", patientId],
    queryFn: () => api.getImmunizations(patientId!),
    enabled: !!patientId && tab === "immunizations",
  });

  const eventsByTab = useMemo<Record<HistoryTab, HistoryEvent[]>>(() => {
    const medicationEpisodes = careQ.isSuccess ? medicationEpisodeEvents(careQ.data) : [];
    return {
      encounters: encounterEvents(timelineQ.data),
      medications:
        medicationEpisodes.length > 0
          ? medicationEpisodes
          : medicationCatalogEvents(overviewQ.data),
      procedures: procedureEvents(proceduresQ.data?.procedures),
      immunizations: immunizationEvents(immunizationsQ.data?.immunizations),
    };
  }, [careQ.data, careQ.isSuccess, immunizationsQ.data, overviewQ.data, proceduresQ.data, timelineQ.data]);

  const tabCounts = useMemo<Record<HistoryTab, number | null>>(
    () => ({
      encounters: timelineQ.data?.encounters.length ?? null,
      medications:
        careQ.isSuccess && medicationEpisodeEvents(careQ.data).length > 0
          ? medicationEpisodeEvents(careQ.data).length
          : overviewQ.data?.medications.length ?? null,
      procedures: proceduresQ.data?.total_count ?? null,
      immunizations: immunizationsQ.data?.total_count ?? null,
    }),
    [careQ.data, careQ.isSuccess, immunizationsQ.data, overviewQ.data, proceduresQ.data, timelineQ.data],
  );

  const medicationHasData = (careQ.isSuccess && medicationEpisodeEvents(careQ.data).length > 0) || !!overviewQ.data;
  const isLoading =
    tab === "encounters"
      ? timelineQ.isLoading
      : tab === "medications"
        ? overviewQ.isLoading && !medicationHasData
        : tab === "procedures"
          ? proceduresQ.isLoading
          : immunizationsQ.isLoading;
  const isError =
    tab === "encounters"
      ? timelineQ.isError
      : tab === "medications"
        ? overviewQ.isError && !medicationHasData
        : tab === "procedures"
          ? proceduresQ.isError
          : immunizationsQ.isError;
  const patientName = timelineQ.data?.name || careQ.data?.name || overviewQ.data?.name || proceduresQ.data?.name || immunizationsQ.data?.name || "Patient";
  const encounterTypeOptions = Array.from(new Set((timelineQ.data?.encounters ?? []).map((encounter) => encounterTypeLabel(encounter))))
    .sort((a, b) => a.localeCompare(b));
  const encounterProviderOptions = Array.from(new Set((timelineQ.data?.encounters ?? []).map(providerFilterLabel)))
    .sort((a, b) => a.localeCompare(b));
  const effectiveTypeFilter =
    typeFilter === "all" || encounterTypeOptions.includes(typeFilter)
      ? typeFilter
      : "all";
  const effectiveProviderFilter =
    providerFilter === "all" || encounterProviderOptions.includes(providerFilter)
      ? providerFilter
      : "all";
  const currentEncounters = (timelineQ.data?.encounters ?? [])
    .filter((encounter) => effectiveTypeFilter === "all" || encounterTypeLabel(encounter) === effectiveTypeFilter)
    .filter((encounter) => effectiveProviderFilter === "all" || providerFilterLabel(encounter) === effectiveProviderFilter)
    .sort((a, b) => dateValue(b.start) - dateValue(a.start));
  const currentEvents =
    tab === "encounters"
      ? currentEncounters.map(encounterToHistoryEvent)
      : eventsByTab[tab];

  if (!patientId) {
    return (
      <EmptyState
        icon={CalendarDays}
        title="Select a patient to view longitudinal history"
        bullets={[
          "Encounters, medications, procedures, and immunizations in one workspace",
          "Toggle between table and timeline views",
          "Use the Care Journey for the full visual Gantt timeline",
        ]}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="mx-auto w-full max-w-7xl space-y-4 p-8">
        <div className="h-32 animate-pulse rounded-3xl bg-[#e9eaef]" />
        <div className="h-12 animate-pulse rounded-xl bg-[#e9eaef]" />
        <div className="h-80 animate-pulse rounded-2xl bg-[#e9eaef]" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load {TABS.find((item) => item.id === tab)?.label.toLowerCase() ?? "history"}.</p>
      </div>
    );
  }

  return (
    <main className="mx-auto w-full max-w-7xl space-y-5 p-8">
      <section className="rounded-3xl border border-[#d8f3ec] bg-[#f3fffb] p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-white/75 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#087d75]">
              <Clock3 size={14} />
              Longitudinal History
            </div>
            <h1 className="text-2xl font-semibold text-[#111827]">{patientName}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#3f635f]">
              Consolidated chronological workspace for encounters, medication episodes, procedures, and immunizations.
            </p>
          </div>
          <Link
            to={`/explorer/care-journey?patient=${patientId}`}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-[#95ded1] bg-white px-4 py-2 text-sm font-semibold text-[#087d75] hover:bg-[#e7fbf6]"
          >
            Visual care journey
            <ChevronRight size={15} />
          </Link>
        </div>
      </section>

      <div className="flex flex-col gap-3 rounded-2xl border border-[#e9eaef] bg-white p-2 shadow-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`inline-flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold transition-colors ${
                tab === id ? "bg-[#eef1ff] text-[#5b76fe]" : "text-[#555a6a] hover:bg-[#f5f6f8]"
              }`}
            >
              <Icon size={15} />
              {label}
              <span className="rounded-full bg-white/80 px-1.5 py-0.5 text-[10px] text-[#6b7280]">
                {tabCounts[id] ?? "—"}
              </span>
            </button>
          ))}
        </div>

        <div className="flex rounded-xl border border-[#e9eaef] bg-[#f9fafb] p-1">
          {(["timeline", "table"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setView(mode)}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold capitalize ${
                view === mode ? "bg-white text-[#1c1c1e] shadow-sm" : "text-[#6b7280]"
              }`}
            >
              {mode === "timeline" ? <CalendarDays size={13} /> : <List size={13} />}
              {mode}
            </button>
          ))}
        </div>
      </div>

      {tab === "encounters" && (
        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-[#e9eaef] bg-white px-3 py-2 shadow-sm">
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-1.5 px-1 text-xs font-semibold uppercase tracking-[0.12em] text-[#98a2b3]">
              <Filter size={13} />
              Type
            </div>
            {["all", ...encounterTypeOptions].map((typeOption) => (
              <button
                key={typeOption}
                type="button"
                onClick={() => setTypeFilter(typeOption)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                  effectiveTypeFilter === typeOption
                    ? "bg-[#eef1ff] text-[#5b76fe]"
                    : "bg-[#f9fafb] text-[#667085] hover:bg-[#f2f4f7]"
                }`}
              >
                {typeOption === "all" ? "All" : typeOption}
              </button>
            ))}
          </div>
          <label className="ml-auto flex min-w-[240px] items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#98a2b3]">
            Provider / site
            <select
              value={effectiveProviderFilter}
              onChange={(event) => setProviderFilter(event.target.value)}
              className="min-w-0 flex-1 rounded-lg border border-[#dfe4ea] bg-white px-2 py-1.5 text-xs font-medium normal-case tracking-normal text-[#475467] outline-none focus:border-[#5b76fe]"
            >
              <option value="all">All providers and sites</option>
              {encounterProviderOptions.map((providerOption) => (
                <option key={providerOption} value={providerOption}>
                  {providerOption}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {tab === "encounters" && view === "table" ? (
        <div className="overflow-x-auto">
          <EncounterHistoryTable encounters={currentEncounters} onSelectEncounter={setSelectedEncounter} />
        </div>
      ) : view === "timeline" ? (
        <TimelineList events={currentEvents} />
      ) : (
        <TableView events={currentEvents} />
      )}
      {selectedEncounter && (
        <EncounterDetailModal
          encounter={selectedEncounter}
          onClose={() => setSelectedEncounter(null)}
        />
      )}
    </main>
  );
}
