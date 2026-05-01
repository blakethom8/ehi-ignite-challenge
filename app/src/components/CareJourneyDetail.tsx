import { useState } from "react";
import { Code2, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { CONDITION_STATUS_COLORS, DRUG_CLASS_COLORS } from "./careJourneyColors";
import type { SelectedCareItem } from "./CareJourneyChart";
import type {
  MedicationEpisodeItem,
  ConditionEpisodeItem,
  ProcedureMarker,
  EncounterMarker,
  DiagnosticReportItem,
} from "../types";

const DETAIL_NOW_MS = Date.now();

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(d: string | null | undefined): string {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function drugClassLabel(cls: string | null): string {
  if (!cls) return "Unclassified";
  return cls.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatusBadge({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium"
      style={{ backgroundColor: color + "20", color }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 py-2 border-b border-slate-100 last:border-0">
      <span className="w-24 shrink-0 text-[11px] text-[#a5a8b5] pt-0.5">{label}</span>
      <span className="text-[12px] text-[#1c1c1e] min-w-0">{children}</span>
    </div>
  );
}

// ── Medication detail ────────────────────────────────────────────────────────

function MedicationDetail({ med }: { med: MedicationEpisodeItem }) {
  const clsColor = med.drug_class ? (DRUG_CLASS_COLORS[med.drug_class] || "#94a3b8") : "#94a3b8";
  return (
    <div className="space-y-0">
      <Row label="Drug class">
        {med.drug_class ? (
          <StatusBadge label={drugClassLabel(med.drug_class)} color={clsColor} />
        ) : (
          <span className="text-slate-400">Unclassified</span>
        )}
      </Row>
      {med.reason && (
        <Row label="Reason"><span className="font-medium">{med.reason}</span></Row>
      )}
      <Row label="Status">
        <StatusBadge
          label={med.is_active ? "Active" : med.status}
          color={med.is_active ? "#22c55e" : "#94a3b8"}
        />
      </Row>
      <Row label="Start">{fmtDate(med.start_date)}</Row>
      <Row label="End">{med.is_active ? <span className="text-green-600 font-medium">Ongoing</span> : fmtDate(med.end_date)}</Row>
      {med.duration_days != null && (
        <Row label="Duration">{Math.round(med.duration_days)} days</Row>
      )}
      <Row label="Prescriptions">{med.request_count}</Row>
    </div>
  );
}

// ── Condition detail ─────────────────────────────────────────────────────────

function ConditionDetail({ cond }: { cond: ConditionEpisodeItem }) {
  const color = CONDITION_STATUS_COLORS[cond.clinical_status] || "#94a3b8";
  const startMs = cond.onset_date ? new Date(cond.onset_date).getTime() : null;
  const endMs = cond.end_date ? new Date(cond.end_date).getTime() : DETAIL_NOW_MS;
  const years = startMs ? (endMs - startMs) / (365.25 * 24 * 3600 * 1000) : null;

  return (
    <div className="space-y-0">
      <Row label="Status">
        <StatusBadge label={cond.clinical_status} color={color} />
      </Row>
      <Row label="Onset">{fmtDate(cond.onset_date)}</Row>
      <Row label="End">{cond.is_active ? <span className="text-red-500 font-medium">Ongoing</span> : fmtDate(cond.end_date)}</Row>
      {years != null && (
        <Row label="Duration">
          {years < 1 ? `${Math.round(years * 12)} months` : `${years.toFixed(1)} years`}
        </Row>
      )}
    </div>
  );
}

// ── Procedure detail ─────────────────────────────────────────────────────────

function ProcedureDetail({ proc }: { proc: ProcedureMarker }) {
  return (
    <div className="space-y-0">
      <Row label="Date">{fmtDate(proc.start)}</Row>
      {proc.end && <Row label="End">{fmtDate(proc.end)}</Row>}
      {proc.reason_display && <Row label="Reason">{proc.reason_display}</Row>}
    </div>
  );
}

// ── Encounter detail (fetches full data) ─────────────────────────────────────

function EncounterFullDetail({ patientId, enc }: { patientId: string; enc: EncounterMarker }) {
  const [rawOpen, setRawOpen] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["encounter", patientId, enc.encounter_id],
    queryFn: () => api.getEncounterDetail(patientId, enc.encounter_id),
    enabled: !!enc.encounter_id,
  });
  const rawQ = useQuery({
    queryKey: ["encounter-raw", patientId, enc.encounter_id],
    queryFn: () => api.getRawEncounter(patientId, enc.encounter_id),
    enabled: rawOpen && !!enc.encounter_id,
  });

  if (isLoading || !data) {
    return (
      <div className="space-y-3 animate-pulse">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex gap-3">
            <div className="w-24 h-3 bg-slate-100 rounded" />
            <div className="flex-1 h-3 bg-slate-100 rounded" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-0">
      {/* Diagnoses — most important clinical info, shown first */}
      {enc.diagnoses && enc.diagnoses.length > 0 && (
        <div className="mb-2 pb-2 border-b border-slate-200">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5] mb-1.5">Diagnosis</p>
          {enc.diagnoses.map((dx, i) => (
            <div key={i} className="flex items-center gap-1.5 py-0.5">
              <span className="h-1.5 w-1.5 rounded-full bg-red-400 shrink-0" />
              <span className="text-[12px] font-medium text-[#1c1c1e]">{dx}</span>
            </div>
          ))}
        </div>
      )}
      <Row label="Type">{data.encounter_type || "\u2014"}</Row>
      <Row label="Class">
        <StatusBadge
          label={data.class_code}
          color={data.class_code === "EMER" ? "#ef4444" : data.class_code === "IMP" ? "#f59e0b" : "#5b76fe"}
        />
      </Row>
      <Row label="Date">{fmtDate(data.start)}</Row>
      {data.duration_hours != null && (
        <Row label="Duration">
          {data.duration_hours < 1
            ? `${Math.round(data.duration_hours * 60)} min`
            : data.duration_hours < 24
            ? `${data.duration_hours.toFixed(1)} hours`
            : `${(data.duration_hours / 24).toFixed(1)} days`}
        </Row>
      )}
      {data.reason_display && <Row label="Reason">{data.reason_display}</Row>}
      {data.practitioner_name && <Row label="Provider">{data.practitioner_name}</Row>}
      {data.provider_org && <Row label="Organization">{data.provider_org}</Row>}

      {/* Linked resources */}
      {(data.observations.length > 0 || data.conditions.length > 0 || data.procedures.length > 0 || data.medications.length > 0) && (
        <div className="mt-3 pt-3 border-t border-slate-200">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5] mb-2">Linked Resources</p>
          <div className="grid grid-cols-2 gap-1.5">
            {data.observations.length > 0 && (
              <div className="rounded bg-slate-50 px-2 py-1.5 text-center">
                <div className="text-sm font-semibold text-slate-700">{data.observations.length}</div>
                <div className="text-[10px] text-slate-500">Observations</div>
              </div>
            )}
            {data.conditions.length > 0 && (
              <div className="rounded bg-slate-50 px-2 py-1.5 text-center">
                <div className="text-sm font-semibold text-slate-700">{data.conditions.length}</div>
                <div className="text-[10px] text-slate-500">Conditions</div>
              </div>
            )}
            {data.procedures.length > 0 && (
              <div className="rounded bg-slate-50 px-2 py-1.5 text-center">
                <div className="text-sm font-semibold text-slate-700">{data.procedures.length}</div>
                <div className="text-[10px] text-slate-500">Procedures</div>
              </div>
            )}
            {data.medications.length > 0 && (
              <div className="rounded bg-slate-50 px-2 py-1.5 text-center">
                <div className="text-sm font-semibold text-slate-700">{data.medications.length}</div>
                <div className="text-[10px] text-slate-500">Medications</div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-slate-200">
        <button
          type="button"
          onClick={() => setRawOpen((open) => !open)}
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 transition-colors hover:border-[#5b76fe] hover:text-[#5b76fe]"
        >
          <Code2 size={13} />
          {rawOpen ? "Hide raw FHIR JSON" : "Show raw FHIR JSON"}
        </button>
        {rawOpen && (
          <div className="mt-2 max-h-72 overflow-auto rounded-lg border border-slate-200 bg-slate-950 p-3">
            {rawQ.isLoading && <p className="text-[11px] text-slate-300">Loading Encounter resource...</p>}
            {rawQ.isError && <p className="text-[11px] text-red-200">Raw Encounter resource unavailable.</p>}
            {rawQ.data && (
              <pre className="whitespace-pre-wrap break-words text-[10px] leading-5 text-slate-100">
                {JSON.stringify(rawQ.data, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

interface CareJourneyDetailProps {
  item: SelectedCareItem;
  patientId: string;
  onClose: () => void;
}

function DiagnosticReportDetail({ report }: { report: DiagnosticReportItem }) {
  return (
    <div className="space-y-0">
      <Row label="Category">{report.category || "Laboratory"}</Row>
      <Row label="Date">{fmtDate(report.date)}</Row>
      <Row label="Results">{report.result_count} observations</Row>
    </div>
  );
}

const KIND_LABELS: Record<string, string> = {
  medication: "Medication",
  condition: "Condition",
  procedure: "Procedure",
  encounter: "Encounter",
  diagnostic_report: "Lab Report",
};

const KIND_COLORS: Record<string, string> = {
  medication: "#5b76fe",
  condition: "#ef4444",
  procedure: "#8b5cf6",
  encounter: "#5b76fe",
  diagnostic_report: "#0891b2",
};

export function CareJourneyDetail({ item, patientId, onClose }: CareJourneyDetailProps) {
  const name = (() => {
    if (item.kind === "medication") return (item.data as MedicationEpisodeItem).display;
    if (item.kind === "condition") return (item.data as ConditionEpisodeItem).display;
    if (item.kind === "procedure") return (item.data as ProcedureMarker).display;
    if (item.kind === "diagnostic_report") return (item.data as DiagnosticReportItem).display;
    if (item.kind === "encounter") {
      const enc = item.data as EncounterMarker;
      // Show diagnosis as the name if available
      return enc.diagnoses?.length ? enc.diagnoses[0] : enc.type_text || "Encounter";
    }
    return "Details";
  })();

  return (
    <div className="flex h-full flex-col bg-white">
      {/* Header */}
      <div className="shrink-0 border-b border-slate-200 px-4 py-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p
              className="text-[10px] font-semibold uppercase tracking-wider mb-1"
              style={{ color: KIND_COLORS[item.kind] }}
            >
              {KIND_LABELS[item.kind]}
            </p>
            <h3 className="text-sm font-semibold text-[#1c1c1e] leading-snug">{name}</h3>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {item.kind === "medication" && <MedicationDetail med={item.data as MedicationEpisodeItem} />}
        {item.kind === "condition" && <ConditionDetail cond={item.data as ConditionEpisodeItem} />}
        {item.kind === "procedure" && <ProcedureDetail proc={item.data as ProcedureMarker} />}
        {item.kind === "encounter" && <EncounterFullDetail patientId={patientId} enc={item.data as EncounterMarker} />}
        {item.kind === "diagnostic_report" && <DiagnosticReportDetail report={item.data as DiagnosticReportItem} />}
      </div>
    </div>
  );
}
