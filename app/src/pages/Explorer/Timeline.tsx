import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronUp, ChevronDown, X, Copy, Check, Code2,
  FlaskConical, Stethoscope, Pill, Scissors, CalendarDays,
} from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type { EncounterEvent, EncounterDetail } from "../../types";

// ── helpers ────────────────────────────────────────────────────────────────

function fmt(dt: string | null, opts?: Intl.DateTimeFormatOptions): string {
  if (!dt) return "—";
  return new Date(dt).toLocaleDateString("en-US", opts ?? {
    year: "numeric", month: "short", day: "numeric",
  });
}

function fmtDuration(hours: number | null): string {
  if (hours === null) return "—";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${hours.toFixed(1)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

const CLASS_META: Record<string, { label: string; color: string; bg: string; dot: string }> = {
  AMB:  { label: "Ambulatory", color: "#5b76fe", bg: "#eef1ff",  dot: "#5b76fe" },
  IMP:  { label: "Inpatient",  color: "#b45309", bg: "#fffbeb",  dot: "#f59e0b" },
  EMER: { label: "Emergency",  color: "#991b1b", bg: "#fef2f2",  dot: "#ef4444" },
  VR:   { label: "Virtual",    color: "#065f46", bg: "#ecfdf5",  dot: "#10b981" },
};

function classMeta(code: string) {
  return CLASS_META[code] ?? { label: code || "Unknown", color: "#555a6a", bg: "#f5f6f8", dot: "#9ca3af" };
}

function ClassBadge({ code }: { code: string }) {
  const m = classMeta(code);
  return (
    <span className="inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full font-medium"
      style={{ color: m.color, backgroundColor: m.bg }}>
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: m.dot }} />
      {m.label}
    </span>
  );
}

function ResourcePill({ label, count, color }: { label: string; count: number; color: string }) {
  if (count === 0) return null;
  return (
    <span className="text-xs px-1.5 py-0.5 rounded font-medium"
      style={{ backgroundColor: color + "18", color }}>
      {count} {label}
    </span>
  );
}

type SortKey = "start" | "class_code" | "encounter_type";
type SortDir = "asc" | "desc";

// ── Raw FHIR Modal ─────────────────────────────────────────────────────────

function RawFhirModal({
  patientId,
  encounterId,
  onClose,
}: {
  patientId: string;
  encounterId: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["encounter-raw", patientId, encounterId],
    queryFn: () => api.getRawEncounter(patientId, encounterId),
  });

  const jsonStr = data ? JSON.stringify(data, null, 2) : "";

  function handleCopy() {
    navigator.clipboard.writeText(jsonStr);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-xl shadow-2xl w-[760px] max-w-[92vw] max-h-[82vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#e9eaef] shrink-0">
          <div className="flex items-center gap-2">
            <Code2 size={16} className="text-[#5b76fe]" />
            <span className="text-sm font-semibold text-[#1c1c1e]">Raw FHIR — Encounter</span>
            <span className="text-xs text-[#a5a8b5] font-mono">{encounterId}</span>
          </div>
          <div className="flex items-center gap-2">
            {data && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-[#e9eaef] hover:bg-[#f5f6f8] text-[#555a6a] transition-colors"
              >
                {copied ? <Check size={12} className="text-[#10b981]" /> : <Copy size={12} />}
                {copied ? "Copied" : "Copy"}
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-[#f5f6f8] text-[#a5a8b5] hover:text-[#1c1c1e] transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto p-5">
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="h-4 bg-[#f5f6f8] rounded animate-pulse" style={{ width: `${60 + i * 8}%` }} />
              ))}
            </div>
          ) : (
            <pre className="text-xs font-mono text-[#1c1c1e] leading-relaxed whitespace-pre-wrap break-all">
              {jsonStr}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Preview pane ───────────────────────────────────────────────────────────

function PreviewPane({
  patientId,
  encounterId,
  onClose,
}: {
  patientId: string;
  encounterId: string;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"summary" | "details">("summary");
  const [showRaw, setShowRaw] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["encounter", patientId, encounterId],
    queryFn: () => api.getEncounterDetail(patientId, encounterId),
  });

  return (
    <>
      <div className="flex flex-col h-full bg-white border-l border-[#e9eaef]">
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-[#e9eaef] shrink-0">
          <div>
            <p className="text-xs text-[#a5a8b5] uppercase tracking-wide mb-1">Encounter</p>
            {data ? (
              <>
                <h2 className="text-sm font-semibold text-[#1c1c1e] leading-snug">
                  {data.encounter_type || "Visit"}
                </h2>
                <p className="text-xs text-[#555a6a] mt-0.5">
                  {fmt(data.start)} · <ClassBadge code={data.class_code} />
                </p>
              </>
            ) : (
              <div className="h-4 w-40 bg-[#f5f6f8] rounded animate-pulse" />
            )}
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setShowRaw(true)}
              title="View raw FHIR JSON"
              className="p-1.5 rounded-lg hover:bg-[#f5f6f8] text-[#a5a8b5] hover:text-[#5b76fe] transition-colors"
            >
              <Code2 size={15} />
            </button>
            <button onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-[#f5f6f8] text-[#a5a8b5] hover:text-[#1c1c1e] transition-colors">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[#e9eaef] px-5 shrink-0">
          {(["summary", "details"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`text-sm py-2.5 mr-5 border-b-2 transition-colors capitalize ${
                tab === t
                  ? "border-[#5b76fe] text-[#5b76fe] font-medium"
                  : "border-transparent text-[#555a6a] hover:text-[#1c1c1e]"
              }`}>
              {t}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-5 space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-12 bg-[#f5f6f8] rounded-lg animate-pulse" />
              ))}
            </div>
          ) : data ? (
            tab === "summary" ? (
              <SummaryTab data={data} />
            ) : (
              <DetailsTab data={data} />
            )
          ) : null}
        </div>
      </div>

      {showRaw && (
        <RawFhirModal
          patientId={patientId}
          encounterId={encounterId}
          onClose={() => setShowRaw(false)}
        />
      )}
    </>
  );
}

function SummaryTab({ data }: { data: EncounterDetail }) {
  const rows = [
    { label: "Type", value: data.encounter_type || "—" },
    { label: "Reason", value: data.reason_display || "—" },
    { label: "Class", value: <ClassBadge code={data.class_code} /> },
    { label: "Date", value: fmt(data.start) },
    { label: "Duration", value: fmtDuration(data.duration_hours) },
    { label: "Provider", value: data.practitioner_name || "—" },
    { label: "Organization", value: data.provider_org || "—" },
  ];

  const counts = [
    { label: "Observations", count: data.observations.length, icon: FlaskConical, color: "#5b76fe" },
    { label: "Conditions", count: data.conditions.length, icon: Stethoscope, color: "#8b5cf6" },
    { label: "Procedures", count: data.procedures.length, icon: Scissors, color: "#f59e0b" },
    { label: "Medications", count: data.medications.length, icon: Pill, color: "#10b981" },
    { label: "Diagnostic Reports", count: data.diagnostic_report_count, icon: FlaskConical, color: "#6b7280" },
  ];

  return (
    <div className="p-5 space-y-5">
      <div className="space-y-2.5">
        {rows.map(({ label, value }) => (
          <div key={label} className="flex gap-3 text-sm">
            <span className="text-[#a5a8b5] w-24 shrink-0">{label}</span>
            <span className="text-[#1c1c1e] font-medium flex-1">{value}</span>
          </div>
        ))}
      </div>

      <div>
        <p className="text-xs font-semibold text-[#a5a8b5] uppercase tracking-wide mb-3">
          Linked Resources
        </p>
        <div className="grid grid-cols-2 gap-2">
          {counts.filter(c => c.count > 0).map(({ label, count, icon: Icon, color }) => (
            <div key={label}
              className="flex items-center gap-2.5 p-3 rounded-lg border border-[#e9eaef] bg-[#fafafa]">
              <Icon size={14} style={{ color }} />
              <div>
                <p className="text-xs text-[#555a6a]">{label}</p>
                <p className="text-sm font-semibold text-[#1c1c1e]">{count}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DetailsTab({ data }: { data: EncounterDetail }) {
  return (
    <div className="p-5 space-y-5">
      {data.observations.length > 0 && (
        <section>
          <p className="text-xs font-semibold text-[#a5a8b5] uppercase tracking-wide mb-2">
            Observations ({data.observations.length})
          </p>
          <div className="space-y-1.5">
            {data.observations.map((obs) => (
              <div key={obs.obs_id}
                className="flex items-start justify-between gap-2 p-2.5 rounded-lg bg-[#f8f9fa] text-sm">
                <div className="min-w-0">
                  <p className="text-[#1c1c1e] font-medium truncate">{obs.display || obs.loinc_code}</p>
                  {obs.loinc_code && (
                    <p className="text-xs text-[#a5a8b5] mt-0.5">LOINC {obs.loinc_code}</p>
                  )}
                </div>
                <div className="text-right shrink-0">
                  {obs.value_type === "quantity" && obs.value_quantity !== null ? (
                    <p className="font-semibold text-[#1c1c1e]">
                      {obs.value_quantity} {obs.value_unit}
                    </p>
                  ) : obs.value_concept_display ? (
                    <p className="text-[#555a6a]">{obs.value_concept_display}</p>
                  ) : null}
                  <p className="text-xs text-[#a5a8b5]">{fmt(obs.effective_dt)}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {data.conditions.length > 0 && (
        <section>
          <p className="text-xs font-semibold text-[#a5a8b5] uppercase tracking-wide mb-2">
            Conditions ({data.conditions.length})
          </p>
          <div className="space-y-1.5">
            {data.conditions.map((c) => (
              <div key={c.condition_id}
                className="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-[#f8f9fa] text-sm">
                <p className="text-[#1c1c1e]">{c.display}</p>
                <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${
                  c.is_active ? "bg-[#c3faf5] text-[#187574]" : "bg-[#f5f6f8] text-[#555a6a]"
                }`}>
                  {c.clinical_status}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {data.procedures.length > 0 && (
        <section>
          <p className="text-xs font-semibold text-[#a5a8b5] uppercase tracking-wide mb-2">
            Procedures ({data.procedures.length})
          </p>
          <div className="space-y-1.5">
            {data.procedures.map((p) => (
              <div key={p.procedure_id} className="p-2.5 rounded-lg bg-[#f8f9fa] text-sm">
                <p className="text-[#1c1c1e] font-medium">{p.display}</p>
                {p.reason_display && (
                  <p className="text-xs text-[#555a6a] mt-0.5">{p.reason_display}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {data.medications.length > 0 && (
        <section>
          <p className="text-xs font-semibold text-[#a5a8b5] uppercase tracking-wide mb-2">
            Medications ({data.medications.length})
          </p>
          <div className="space-y-1.5">
            {data.medications.map((m) => (
              <div key={m.med_id} className="p-2.5 rounded-lg bg-[#f8f9fa] text-sm">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[#1c1c1e] font-medium truncate">{m.display}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 capitalize ${
                    m.status === "active" ? "bg-[#eef1ff] text-[#5b76fe]" : "bg-[#f5f6f8] text-[#555a6a]"
                  }`}>
                    {m.status}
                  </span>
                </div>
                {m.dosage_text && (
                  <p className="text-xs text-[#555a6a] mt-0.5">{m.dosage_text}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {data.observations.length === 0 && data.conditions.length === 0 &&
       data.procedures.length === 0 && data.medications.length === 0 && (
        <p className="text-sm text-[#a5a8b5] text-center py-8">
          No linked resources for this encounter.
        </p>
      )}
    </div>
  );
}

// ── Encounter table ────────────────────────────────────────────────────────

function SortIcon({ column, sortKey, sortDir }: {
  column: SortKey; sortKey: SortKey; sortDir: SortDir;
}) {
  if (column !== sortKey) return <ChevronDown size={12} className="text-[#c7cad5]" />;
  return sortDir === "desc"
    ? <ChevronDown size={12} className="text-[#5b76fe]" />
    : <ChevronUp size={12} className="text-[#5b76fe]" />;
}

function EncounterTable({
  encounters,
  selectedId,
  yearFilter,
  onSelect,
}: {
  encounters: EncounterEvent[];
  selectedId: string | null;
  yearFilter: string | null;
  onSelect: (id: string) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("start");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [classFilter, setClassFilter] = useState<string>("ALL");

  const tableRef = useRef<HTMLDivElement>(null);
  const rowRefs = useRef<Map<string, HTMLTableRowElement>>(new Map());
  const scrollTopRef = useRef<number>(0);

  // Track scroll position so we can restore it when the preview pane closes
  useEffect(() => {
    const el = tableRef.current;
    if (!el) return;
    function onScroll() {
      scrollTopRef.current = el!.scrollTop;
    }
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Restore scroll position when pane closes (selectedId goes from value → null)
  const prevSelectedIdRef = useRef<string | null>(selectedId);
  useEffect(() => {
    const wasSelected = prevSelectedIdRef.current !== null;
    const nowNull = selectedId === null;
    prevSelectedIdRef.current = selectedId;
    if (wasSelected && nowNull) {
      const saved = scrollTopRef.current;
      setTimeout(() => {
        tableRef.current?.scrollTo({ top: saved });
      }, 50);
    }
  }, [selectedId]);

  const allClasses = ["ALL", ...Array.from(new Set(encounters.map(e => e.class_code || "Unknown")))];

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("desc"); }
  }

  const filtered = encounters.filter(e => {
    const matchClass = classFilter === "ALL" || (e.class_code || "Unknown") === classFilter;
    const matchYear = !yearFilter || (e.start && new Date(e.start).getFullYear().toString() === yearFilter);
    return matchClass && matchYear;
  });

  const sorted = [...filtered].sort((a, b) => {
    let av: string | number = 0, bv: string | number = 0;
    if (sortKey === "start") {
      av = a.start ?? ""; bv = b.start ?? "";
    } else if (sortKey === "class_code") {
      av = a.class_code; bv = b.class_code;
    } else if (sortKey === "encounter_type") {
      av = a.encounter_type; bv = b.encounter_type;
    }
    if (av < bv) return sortDir === "asc" ? -1 : 1;
    if (av > bv) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  // Auto-scroll selected row into view
  useEffect(() => {
    if (!selectedId) return;
    const el = rowRefs.current.get(selectedId);
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedId]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const currentIdx = sorted.findIndex(enc => enc.encounter_id === selectedId);
    if (e.key === "ArrowDown") {
      const next = sorted[currentIdx + 1];
      if (next) onSelect(next.encounter_id);
    } else {
      const prev = currentIdx <= 0 ? sorted[sorted.length - 1] : sorted[currentIdx - 1];
      if (prev) onSelect(prev.encounter_id);
    }
  }, [sorted, selectedId, onSelect]);

  const thClass = "px-3 py-2.5 text-left text-xs font-medium text-[#a5a8b5] uppercase tracking-wide cursor-pointer select-none hover:text-[#555a6a] transition-colors";

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#e9eaef] bg-white shrink-0">
        <span className="text-xs text-[#a5a8b5] mr-1">Class:</span>
        {allClasses.map(cls => (
          <button key={cls} onClick={() => setClassFilter(cls)}
            className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
              classFilter === cls
                ? "border-[#5b76fe] bg-[#eef1ff] text-[#5b76fe] font-medium"
                : "border-[#e9eaef] text-[#555a6a] hover:border-[#c7cad5]"
            }`}>
            {cls === "ALL" ? `All (${encounters.length})` : classMeta(cls).label}
          </button>
        ))}
        <span className="ml-auto text-xs text-[#a5a8b5]">{sorted.length} encounters</span>
        {selectedId && (
          <span className="text-xs text-[#a5a8b5]">↑↓ to navigate</span>
        )}
      </div>

      {/* Table */}
      <div
        ref={tableRef}
        tabIndex={0}
        onKeyDown={handleKeyDown}
        className="overflow-y-auto flex-1 outline-none"
      >
        <table className="w-full border-collapse">
          <thead className="bg-[#fafafa] sticky top-0 z-10 border-b border-[#e9eaef]">
            <tr>
              <th className={thClass} onClick={() => toggleSort("start")}>
                <span className="flex items-center gap-1">
                  Date <SortIcon column="start" sortKey={sortKey} sortDir={sortDir} />
                </span>
              </th>
              <th className={thClass} onClick={() => toggleSort("class_code")}>
                <span className="flex items-center gap-1">
                  Class <SortIcon column="class_code" sortKey={sortKey} sortDir={sortDir} />
                </span>
              </th>
              <th className={thClass} onClick={() => toggleSort("encounter_type")}>
                <span className="flex items-center gap-1">
                  Type <SortIcon column="encounter_type" sortKey={sortKey} sortDir={sortDir} />
                </span>
              </th>
              <th className={`${thClass} hidden lg:table-cell`}>Reason</th>
              <th className={`${thClass} hidden xl:table-cell`}>Provider</th>
              <th className={thClass}>Resources</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((enc) => {
              const isSelected = enc.encounter_id === selectedId;
              return (
                <tr
                  key={enc.encounter_id}
                  ref={el => {
                    if (el) rowRefs.current.set(enc.encounter_id, el);
                    else rowRefs.current.delete(enc.encounter_id);
                  }}
                  onClick={() => {
                    onSelect(enc.encounter_id);
                    tableRef.current?.focus();
                  }}
                  className={`border-b border-[#f5f6f8] cursor-pointer transition-colors ${
                    isSelected ? "bg-[#eef1ff]" : "hover:bg-[#fafafa]"
                  }`}
                >
                  <td className="px-3 py-2.5 text-sm text-[#1c1c1e] font-medium whitespace-nowrap">
                    {fmt(enc.start, { year: "numeric", month: "short", day: "numeric" })}
                  </td>
                  <td className="px-3 py-2.5">
                    <ClassBadge code={enc.class_code} />
                  </td>
                  <td className="px-3 py-2.5 text-sm text-[#555a6a] max-w-[200px] truncate">
                    {enc.encounter_type || "—"}
                  </td>
                  <td className="px-3 py-2.5 text-sm text-[#555a6a] max-w-[180px] truncate hidden lg:table-cell">
                    {enc.reason_display || "—"}
                  </td>
                  <td className="px-3 py-2.5 text-sm text-[#555a6a] max-w-[160px] truncate hidden xl:table-cell">
                    {enc.practitioner_name || enc.provider_org || "—"}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      <ResourcePill label="Obs" count={enc.linked_observation_count} color="#5b76fe" />
                      <ResourcePill label="Cond" count={enc.linked_condition_count} color="#8b5cf6" />
                      <ResourcePill label="Proc" count={enc.linked_procedure_count} color="#f59e0b" />
                      <ResourcePill label="Med" count={enc.linked_medication_count} color="#10b981" />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Year filter pills ──────────────────────────────────────────────────────

function YearFilter({
  yearCounts,
  active,
  onChange,
}: {
  yearCounts: Record<string, number>;
  active: string | null;
  onChange: (year: string | null) => void;
}) {
  const years = Object.keys(yearCounts).sort();
  if (years.length === 0) return null;

  const total = Object.values(yearCounts).reduce((a, b) => a + b, 0);
  const max = Math.max(...Object.values(yearCounts));

  return (
    <div className="flex items-end gap-1 overflow-x-auto pb-1">
      {/* All pill */}
      <button
        onClick={() => onChange(null)}
        className={`shrink-0 text-xs px-2.5 py-1 rounded-full border transition-colors ${
          !active
            ? "border-[#5b76fe] bg-[#eef1ff] text-[#5b76fe] font-medium"
            : "border-[#e9eaef] text-[#555a6a] hover:border-[#c7cad5]"
        }`}
      >
        All ({total})
      </button>

      {/* Per-year bars + labels */}
      {years.map(year => {
        const count = yearCounts[year];
        const isActive = active === year;
        const barH = Math.max(4, Math.round((count / max) * 32));
        return (
          <button
            key={year}
            onClick={() => onChange(isActive ? null : year)}
            className={`shrink-0 flex flex-col items-center gap-0.5 px-1 pt-1 rounded transition-colors group ${
              isActive ? "bg-[#eef1ff]" : "hover:bg-[#f5f6f8]"
            }`}
          >
            <div className="flex items-end" style={{ height: 34 }}>
              <div
                className="w-3 rounded-t transition-colors"
                style={{
                  height: barH,
                  backgroundColor: isActive ? "#5b76fe" : "#c7cad5",
                }}
              />
            </div>
            <span className={`text-[10px] leading-none ${isActive ? "text-[#5b76fe] font-semibold" : "text-[#a5a8b5]"}`}>
              {year.slice(2)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ── Composition Panel ─────────────────────────────────────────────────────

interface ClassStats {
  code: string;
  count: number;
  avgObs: number;
  avgCond: number;
  avgProc: number;
  avgMed: number;
}

function computeClassStats(encounters: EncounterEvent[]): ClassStats[] {
  const acc: Record<string, {
    count: number;
    obs: number;
    cond: number;
    proc: number;
    med: number;
  }> = {};

  for (const enc of encounters) {
    const code = enc.class_code || "Unknown";
    if (!acc[code]) acc[code] = { count: 0, obs: 0, cond: 0, proc: 0, med: 0 };
    acc[code].count += 1;
    acc[code].obs  += enc.linked_observation_count;
    acc[code].cond += enc.linked_condition_count;
    acc[code].proc += enc.linked_procedure_count;
    acc[code].med  += enc.linked_medication_count;
  }

  return Object.entries(acc)
    .filter(([, s]) => s.count >= 2)
    .map(([code, s]) => ({
      code,
      count: s.count,
      avgObs:  s.obs  / s.count,
      avgCond: s.cond / s.count,
      avgProc: s.proc / s.count,
      avgMed:  s.med  / s.count,
    }))
    .sort((a, b) => b.count - a.count);
}

function CompositionPanel({ encounters }: { encounters: EncounterEvent[] }) {
  const [open, setOpen] = useState(false);

  const stats = computeClassStats(encounters);
  if (stats.length === 0) return null;

  return (
    <div className="mt-2">
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="text-xs text-[#a5a8b5] hover:text-[#555a6a] transition-colors"
        >
          Composition ▾
        </button>
      ) : (
        <div>
          <button
            onClick={() => setOpen(false)}
            className="text-xs text-[#a5a8b5] hover:text-[#555a6a] transition-colors mb-2"
          >
            Hide ▴
          </button>
          <div className="flex flex-wrap gap-2">
            {stats.map((s) => {
              const m = classMeta(s.code);
              return (
                <div
                  key={s.code}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg border text-xs"
                  style={{ borderColor: m.color + "40", backgroundColor: m.bg }}
                >
                  <ClassBadge code={s.code} />
                  <span className="text-[#555a6a]">
                    {s.avgObs.toFixed(1)} obs · {s.avgCond.toFixed(1)} cond · {s.avgProc.toFixed(1)} proc · {s.avgMed.toFixed(1)} med
                  </span>
                  <span className="text-[#a5a8b5] ml-1">({s.count})</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export function ExplorerTimeline() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const [uiState, setUiState] = useState<{
    patientId: string | null;
    selectedEncounterId: string | null;
    yearFilter: string | null;
  }>({
    patientId,
    selectedEncounterId: null,
    yearFilter: null,
  });

  const setUiStateForActivePatient = useCallback(
    (
      updater: (prev: { selectedEncounterId: string | null; yearFilter: string | null }) => {
        selectedEncounterId: string | null;
        yearFilter: string | null;
      }
    ) => {
      setUiState((prev) => {
        const activeState =
          prev.patientId === patientId
            ? { selectedEncounterId: prev.selectedEncounterId, yearFilter: prev.yearFilter }
            : { selectedEncounterId: null, yearFilter: null };

        const next = updater(activeState);
        return { patientId, ...next };
      });
    },
    [patientId]
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: ["timeline", patientId],
    queryFn: () => api.getTimeline(patientId!),
    enabled: !!patientId,
  });

  const selectedEncounterId =
    uiState.patientId === patientId ? uiState.selectedEncounterId : null;
  const yearFilter = uiState.patientId === patientId ? uiState.yearFilter : null;

  const handleSelect = useCallback((id: string) => {
    setUiStateForActivePatient((prev) => ({
      ...prev,
      selectedEncounterId: prev.selectedEncounterId === id ? null : id,
    }));
  }, [setUiStateForActivePatient]);

  const handleYearFilterChange = useCallback((year: string | null) => {
    setUiStateForActivePatient((prev) => ({
      ...prev,
      yearFilter: year,
    }));
  }, [setUiStateForActivePatient]);

  const closePreview = useCallback(() => {
    setUiStateForActivePatient((prev) => ({
      ...prev,
      selectedEncounterId: null,
    }));
  }, [setUiStateForActivePatient]);

  if (!patientId) {
    return (
      <EmptyState
        icon={CalendarDays}
        title="Choose a patient to begin"
        bullets={[
          "Chronological encounter history with year-by-year filter",
          "Encounter type, class, and linked resource counts",
          "Click any encounter to preview observations, conditions, and more",
        ]}
        stat="1,180 patients available"
      />
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-[#555a6a]">Loading timeline…</p>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-[#600000]">Failed to load timeline.</p>
      </div>
    );
  }

  const previewOpen = selectedEncounterId !== null;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Top bar — patient name + year filter */}
      <div className="bg-white border-b border-[#e9eaef] px-5 py-4 shrink-0">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h1 className="text-lg font-semibold text-[#1c1c1e]">{data.name}</h1>
            <p className="text-xs text-[#a5a8b5]">
              {data.encounters.length} encounters · click a row to preview · ↑↓ to navigate
            </p>
          </div>
        </div>
        <YearFilter
          yearCounts={data.year_counts}
          active={yearFilter}
          onChange={handleYearFilterChange}
        />
        <CompositionPanel encounters={data.encounters} />
      </div>

      {/* Breadcrumb — visible only when a preview pane is open */}
      {previewOpen && (() => {
        const enc = data.encounters.find(e => e.encounter_id === selectedEncounterId);
        const dateLabel = enc?.start ? fmt(enc.start) : "—";
        const typeLabel = enc?.encounter_type || null;
        return (
          <div className="bg-[#fafafa] border-b border-[#e9eaef] px-5 py-2 flex items-center shrink-0">
            <span className="text-xs text-[#a5a8b5]">Timeline</span>
            <span className="text-xs text-[#c7cad5] mx-1.5">›</span>
            <span className="text-xs text-[#a5a8b5]">{dateLabel}</span>
            {typeLabel && (
              <>
                <span className="text-xs text-[#c7cad5] mx-1.5">›</span>
                <span className="text-xs text-[#555a6a] font-medium">{typeLabel}</span>
              </>
            )}
            <span className="text-xs text-[#c7cad5] mx-1.5">›</span>
            <span className="text-xs text-[#a5a8b5]">Encounter preview</span>
            <button
              onClick={closePreview}
              className="ml-auto flex items-center gap-1 text-xs text-[#a5a8b5] hover:text-[#1c1c1e] transition-colors"
              aria-label="Close preview"
            >
              <X size={12} />
              Close
            </button>
          </div>
        );
      })()}

      {/* Main content — table + preview pane */}
      <div className="flex flex-1 overflow-hidden">
        {/* Table */}
        <div className={`flex flex-col overflow-hidden transition-all duration-200 ${
          previewOpen ? "flex-1" : "w-full"
        }`}>
          <EncounterTable
            encounters={data.encounters}
            selectedId={selectedEncounterId}
            yearFilter={yearFilter}
            onSelect={handleSelect}
          />
        </div>

        {/* Preview pane */}
        {previewOpen && patientId && (
          <div className="w-96 shrink-0 flex flex-col overflow-hidden border-l border-[#e9eaef]">
            <PreviewPane
              patientId={patientId}
              encounterId={selectedEncounterId!}
              onClose={closePreview}
            />
          </div>
        )}
      </div>
    </div>
  );
}
