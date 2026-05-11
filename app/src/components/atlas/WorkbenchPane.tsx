import {
  AlertTriangle,
  Beaker,
  Braces,
  Columns,
  Download,
  FileText,
  GitCompare,
  MapPin,
  MoreHorizontal,
  Plus,
  Quote,
  Shield,
  Sparkles,
  Users2,
  X,
} from "lucide-react";
import { PATIENT, type WorkbenchTab } from "./data";
import { RENDERERS } from "./renderers";
import type { Workspace } from "./types";

const TAB_ICONS: Record<string, typeof FileText> = {
  FileText,
  GitCompare,
  Braces,
  Beaker,
};

type WorkbenchPaneProps = {
  workspace: Workspace;
  tabs: WorkbenchTab[];
  activeTabId: string | null;
  onSelectTab: (id: string) => void;
  onCloseTab: (id: string) => void;
  onCitationClick: (id: string) => void;
  activeCitationId: string | null;
  /** Active run id (plugin workspaces). */
  runId?: string | null;
  /** Canvas state for the active run, keyed by tool id / artifact id. */
  canvas?: Record<string, unknown>;
};

export function WorkbenchPane({
  workspace,
  tabs,
  activeTabId,
  onSelectTab,
  onCloseTab,
  onCitationClick,
  activeCitationId,
  runId = null,
  canvas = {},
}: WorkbenchPaneProps) {
  const tab = tabs.find((t) => t.id === activeTabId) ?? null;
  return (
    <section
      className="grid h-full min-h-0 grid-rows-[auto_auto_1fr_auto] overflow-hidden"
      style={{
        background: "var(--surface-0)",
        borderRight: "1px solid var(--line-1)",
      }}
    >
      <div
        className="flex h-9 items-center gap-2.5 border-b px-3"
        style={{
          background: "var(--bg-chrome)",
          borderColor: "var(--line-1)",
        }}
      >
        <span
          className="text-[11.5px] font-semibold tracking-wider"
          style={{ color: "var(--ink-3)" }}
        >
          WORKBENCH
        </span>
        <div className="flex-1" />
        <PhBtn icon={<Columns className="h-3 w-3" strokeWidth={1.5} />} title="Split" />
        <PhBtn icon={<GitCompare className="h-3 w-3" strokeWidth={1.5} />} title="Diff" />
        <PhBtn icon={<Download className="h-3 w-3" strokeWidth={1.5} />} title="Export" />
        <PhBtn icon={<MoreHorizontal className="h-3 w-3" strokeWidth={1.5} />} title="More" />
      </div>
      <div
        className="flex items-stretch overflow-x-auto border-b"
        style={{
          background: "var(--bg-chrome)",
          borderColor: "var(--line-1)",
        }}
      >
        {tabs.map((t) => {
          const Icon = TAB_ICONS[t.icon] ?? FileText;
          const active = t.id === activeTabId;
          return (
            <div
              key={t.id}
              onClick={() => onSelectTab(t.id)}
              className="group relative flex cursor-pointer items-center gap-2 whitespace-nowrap border-r px-3 text-[12px] transition-colors"
              style={{
                background: active ? "var(--surface-0)" : "transparent",
                color: active ? "var(--ink-1)" : "var(--ink-3)",
                borderColor: "var(--line-1)",
                height: 34,
              }}
            >
              <Icon
                className="h-3 w-3"
                strokeWidth={1.5}
                style={{ color: active ? "var(--action)" : "var(--ink-4)" }}
              />
              <span>{t.label}</span>
              {t.dirty && (
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: "var(--action)" }}
                />
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onCloseTab(t.id);
                }}
                className="grid h-3.5 w-3.5 place-items-center rounded text-transparent group-hover:text-[var(--ink-3)] hover:bg-[var(--surface-3)] hover:!text-[var(--ink-1)]"
              >
                <X className="h-2.5 w-2.5" strokeWidth={1.5} />
              </button>
              {active && (
                <span
                  className="absolute left-0 right-0 -bottom-px h-0.5"
                  style={{ background: "var(--action)" }}
                />
              )}
            </div>
          );
        })}
        <div className="ml-auto flex items-center gap-1 px-2">
          <PhBtn icon={<Plus className="h-3 w-3" strokeWidth={1.5} />} title="New tab" />
        </div>
      </div>
      <div
        className="overflow-y-auto"
        key={tab?.id}
        style={{ background: "var(--surface-0)" }}
      >
        {tab ? (
          tab.renderer ? (
            (() => {
              const Renderer = RENDERERS[tab.renderer];
              return (
                <Renderer
                  runId={runId}
                  canvas={canvas}
                  tabId={tab.id}
                  onCitationClick={onCitationClick}
                />
              );
            })()
          ) : (
            renderTab(tab, onCitationClick, activeCitationId)
          )
        ) : (
          <div className="p-8 text-[13px]" style={{ color: "var(--ink-4)" }}>
            No tab open.
          </div>
        )}
      </div>
      <div
        className="flex h-6 items-center gap-2.5 border-t px-3 text-[10.5px]"
        style={{
          background: "var(--bg-chrome)",
          borderColor: "var(--line-1)",
          color: "var(--ink-4)",
          fontFamily: "var(--font-mono)",
        }}
      >
        <span className="inline-flex items-center gap-1.5">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: "var(--action)" }}
          />
          {runId ?? `workspace/${workspace.id}`} · {workspace.runState ?? "idle"}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Sparkles className="h-2.5 w-2.5" strokeWidth={1.5} />
          clinical-high · ctx 41k
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Shield className="h-2.5 w-2.5" strokeWidth={1.5} />
          {workspace.boundary.split(" ")[0]}
        </span>
        <span className="flex-1" />
        <span>{tab?.id ?? ""}</span>
        <span>ln 1, col 1</span>
        <span>UTF-8</span>
      </div>
    </section>
  );
}

function PhBtn({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <button
      title={title}
      className="grid h-[22px] w-[22px] place-items-center rounded text-[var(--ink-4)] hover:bg-[var(--surface-2)] hover:text-[var(--ink-1)]"
    >
      {icon}
    </button>
  );
}

function renderTab(
  tab: WorkbenchTab,
  onCitationClick: (id: string) => void,
  activeCitationId: string | null,
) {
  switch (tab.kind) {
    case "preop-brief":
      return <PreopBrief onCitationClick={onCitationClick} activeCitationId={activeCitationId} />;
    case "anticoag-note":
      return <AnticoagNote onCitationClick={onCitationClick} />;
    case "summary-json":
      return <SummaryJson />;
    case "diff":
      return <DiffView />;
    case "trial-board":
      return <TrialBoard />;
    case "packet-outline":
      return <PacketOutline />;
    case "manifest-json":
      return <ManifestJson />;
  }
}

function Cite({
  id,
  onClick,
  active,
}: {
  id: string;
  onClick: () => void;
  active: boolean;
}) {
  return (
    <span
      onClick={onClick}
      className="mx-0.5 inline-flex cursor-pointer items-center gap-1 rounded-[4px] border px-1.5 align-baseline text-[11px] leading-[1.4] transition-colors hover:border-[var(--action-line)] hover:bg-[var(--action-tint)]"
      style={{
        background: active ? "var(--action-tint-2)" : "var(--surface-0)",
        borderColor: active ? "var(--action)" : "var(--line-1)",
        color: "var(--action)",
        fontFamily: "var(--font-mono)",
      }}
    >
      <Quote className="h-2 w-2" strokeWidth={1.5} />
      {id}
    </span>
  );
}

function DocFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="mx-auto max-w-[760px] px-10 pb-16 pt-8"
      style={{ fontFamily: "var(--font-sans)" }}
    >
      {children}
    </div>
  );
}

function H1({ children }: { children: React.ReactNode }) {
  return (
    <h1
      className="mb-1.5 text-[28px] font-semibold tracking-tight"
      style={{ fontFamily: "var(--font-serif)", color: "var(--ink-1)" }}
    >
      {children}
    </h1>
  );
}

function H2({ children }: { children: React.ReactNode }) {
  return (
    <h2
      className="mb-2 mt-7 text-[19px] font-semibold tracking-tight"
      style={{ fontFamily: "var(--font-serif)", color: "var(--ink-1)" }}
    >
      {children}
    </h2>
  );
}

function H3({ children }: { children: React.ReactNode }) {
  return (
    <h3
      className="mb-2 mt-5 text-[12px] font-semibold uppercase tracking-wider"
      style={{ color: "var(--ink-3)" }}
    >
      {children}
    </h3>
  );
}

function DocSub({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="mb-7 text-[12px]"
      style={{ color: "var(--ink-4)", fontFamily: "var(--font-mono)" }}
    >
      {children}
    </div>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="mb-3 text-[14px] leading-[1.65]"
      style={{ color: "var(--ink-2)" }}
    >
      {children}
    </p>
  );
}

function PreopBrief({
  onCitationClick,
  activeCitationId,
}: {
  onCitationClick: (id: string) => void;
  activeCitationId: string | null;
}) {
  const cite = (id: string) => (
    <Cite id={id} onClick={() => onCitationClick(id)} active={activeCitationId === id} />
  );
  return (
    <DocFrame>
      <H1>Pre-op clearance briefing</H1>
      <DocSub>artifact:pre-op-packet-v2.md · 2025-05-08 · draft · curated by Pre-op agent</DocSub>
      <div
        className="relative mb-6 grid grid-cols-[36px_1fr_auto] items-center gap-3 overflow-hidden rounded-[10px] border p-4"
        style={{
          background: "var(--caution-tint)",
          borderColor: "var(--caution-line)",
        }}
      >
        <span
          className="absolute left-0 top-0 h-full w-1"
          style={{ background: "var(--caution)" }}
        />
        <AlertTriangle className="h-5 w-5" strokeWidth={1.5} style={{ color: "var(--caution)" }} />
        <div>
          <span
            className="block text-[11px] font-bold tracking-wider"
            style={{ color: "var(--caution)" }}
          >
            REVIEW · ANTICOAGULATION
          </span>
          <div className="mt-0.5 text-[13.5px] font-medium" style={{ color: "var(--ink-1)" }}>
            Surgery is operable pending confirmation of apixaban hold interval and a refreshed INR.
          </div>
        </div>
        <button
          className="h-[28px] rounded-md px-3 text-[12px] font-semibold text-white"
          style={{ background: "var(--ink-1)" }}
        >
          Approve hold
        </button>
      </div>
      <div
        className="my-5 grid grid-cols-5 overflow-hidden rounded-[10px] border"
        style={{ background: "var(--surface-0)", borderColor: "var(--line-1)" }}
      >
        <FactCell label="Patient" value={PATIENT.name} sans />
        <FactCell label="Age · Sex" value={PATIENT.ageSex} />
        <FactCell label="Complexity" tier="Tier C" />
        <FactCell label="FHIR resources" value="1,184" />
        <FactCell label="OR date" value="2025-05-12" />
      </div>
      <p
        className="mb-3 text-[16px] leading-[1.65]"
        style={{ fontFamily: "var(--font-serif)", color: "var(--ink-1)" }}
      >
        The patient is a 68-year-old female scheduled for an open inguinal hernia repair on
        2025-05-12. Chronic atrial fibrillation is managed on apixaban {cite("c_1042")}. Hematologic
        baseline {cite("c_1078")} is acceptable; INR repeat is pending {cite("c_1091")}.
      </p>
      <H2>Critical medications</H2>
      <DenseTable
        columns={["Drug", "Dose · since", "Hold rule", "Source"]}
        rows={[
          ["Apixaban", "5 mg BID · 2023-06-14", { kind: "risk-high", text: "Hold ≥ 48 h pre-op" }, { kind: "citation", id: "c_1042" }],
          ["Metformin", "1000 mg BID · 2019-11-02", { kind: "risk-mod", text: "Hold AM of surgery" }, "c_1056"],
          ["Lisinopril", "10 mg QD · 2018-03-08", { kind: "risk-mod", text: "Hold AM of surgery" }, "c_1061"],
          ["Atorvastatin", "40 mg QHS · 2017-09-14", { kind: "risk-low", text: "Continue" }, "c_1068"],
        ]}
        onCitationClick={onCitationClick}
      />
      <H2>Recent labs</H2>
      <DenseTable
        columns={["Test", "Value", "Date", "Flag", "Source"]}
        rows={[
          ["Hgb", "12.4 g/dL", "2025-04-22", { kind: "risk-low", text: "In range" }, { kind: "citation", id: "c_1078" }],
          ["Platelets", "218 × 10⁹/L", "2025-04-22", { kind: "risk-low", text: "In range" }, "c_1078"],
          ["INR", "—", "pending", { kind: "risk-mod", text: "Order placed" }, { kind: "citation", id: "c_1091" }],
          ["eGFR", "62 mL/min/1.73 m²", "2025-04-22", { kind: "risk-mod", text: "Mild reduction" }, "c_1080"],
        ]}
        onCitationClick={onCitationClick}
      />
      <H2>Active comorbidities</H2>
      <DenseTable
        columns={["Condition", "Onset", "Risk band", "Source"]}
        rows={[
          ["Atrial fibrillation (paroxysmal)", "2023-05", { kind: "risk-high", text: "Surgical bleed" }, "c_1041"],
          ["Type 2 diabetes mellitus", "2019-11", { kind: "risk-mod", text: "Glycemic" }, "c_1055"],
          ["HTN, controlled", "2018-03", { kind: "risk-low", text: "Baseline" }, "c_1060"],
        ]}
        onCitationClick={onCitationClick}
      />
      <H2>Anesthesia handoff</H2>
      <P>
        No documented airway complication on prior anesthesia notes {cite("c_1094")}. Anesthesia
        consult cleared 2025-04-18, contingent on the hematologic recheck.
      </P>
      <H3>Next action</H3>
      <P>
        <strong style={{ color: "var(--ink-1)", fontWeight: 600 }}>
          Pause for clinician approval
        </strong>{" "}
        on the apixaban hold interval. The packet will not export until the approval card in chat is
        acknowledged.
      </P>
    </DocFrame>
  );
}

function FactCell({
  label,
  value,
  sans,
  tier,
}: {
  label: string;
  value?: string;
  sans?: boolean;
  tier?: string;
}) {
  return (
    <div
      className="border-r p-3.5 last:border-r-0"
      style={{ borderColor: "var(--line-1)" }}
    >
      <div
        className="text-[10px] font-semibold uppercase tracking-wider"
        style={{ color: "var(--ink-4)" }}
      >
        {label}
      </div>
      {tier ? (
        <div className="mt-1 inline-flex items-center gap-1">
          <span
            className="rounded-full px-1.5 py-px text-[10.5px]"
            style={{
              background: "var(--caution-tint)",
              color: "var(--caution)",
              fontFamily: "var(--font-sans)",
            }}
          >
            {tier}
          </span>
        </div>
      ) : (
        <div
          className="mt-1 text-[16px] font-semibold tracking-tight"
          style={{
            color: "var(--ink-1)",
            fontFamily: sans ? "var(--font-sans)" : "var(--font-mono)",
          }}
        >
          {value}
        </div>
      )}
    </div>
  );
}

type Cell =
  | string
  | { kind: "risk-high" | "risk-mod" | "risk-low"; text: string }
  | { kind: "citation"; id: string };

function DenseTable({
  columns,
  rows,
  onCitationClick,
}: {
  columns: string[];
  rows: Cell[][];
  onCitationClick: (id: string) => void;
}) {
  return (
    <table className="mb-2 w-full border-collapse text-[12.5px]">
      <thead>
        <tr style={{ borderBottom: "1px solid var(--line-1)" }}>
          {columns.map((c) => (
            <th
              key={c}
              className="px-2.5 py-2 text-left font-semibold uppercase tracking-wider"
              style={{ color: "var(--ink-4)", fontSize: 10.5 }}
            >
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr
            key={i}
            style={{ borderBottom: "1px solid var(--line-1)" }}
          >
            {row.map((cell, j) => (
              <td key={j} className="px-2.5 py-2 align-top">
                {renderCell(cell, onCitationClick)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function renderCell(cell: Cell, onCitationClick: (id: string) => void): React.ReactNode {
  if (typeof cell === "string") {
    if (cell.startsWith("c_")) {
      return (
        <span
          className="cursor-pointer"
          onClick={() => onCitationClick(cell)}
          style={{
            color: "var(--action)",
            fontFamily: "var(--font-mono)",
            fontSize: 11.5,
          }}
        >
          {cell}
        </span>
      );
    }
    if (/\d/.test(cell) || cell.includes(".") || cell.includes("/")) {
      return (
        <span style={{ fontFamily: "var(--font-mono)", color: "var(--ink-2)" }}>
          {cell}
        </span>
      );
    }
    return <span style={{ color: "var(--ink-1)", fontWeight: 500 }}>{cell}</span>;
  }
  if (cell.kind === "citation") {
    return (
      <span
        className="cursor-pointer"
        onClick={() => onCitationClick(cell.id)}
        style={{
          color: "var(--action)",
          fontFamily: "var(--font-mono)",
          fontSize: 11.5,
        }}
      >
        {cell.id}
      </span>
    );
  }
  const tone =
    cell.kind === "risk-high"
      ? { color: "var(--critical)", fontWeight: 600 }
      : cell.kind === "risk-mod"
      ? { color: "var(--caution)", fontWeight: 500 }
      : { color: "var(--clear)" };
  return <span style={tone}>{cell.text}</span>;
}

function AnticoagNote({ onCitationClick }: { onCitationClick: (id: string) => void }) {
  return (
    <DocFrame>
      <H1>Anticoagulation note</H1>
      <DocSub>context/anticoagulation-note.txt · curated 2025-05-06</DocSub>
      <pre
        className="overflow-x-auto whitespace-pre-wrap rounded-md border p-3.5 text-[12.5px]"
        style={{
          background: "var(--surface-1)",
          borderColor: "var(--line-1)",
          fontFamily: "var(--font-mono)",
          lineHeight: 1.7,
          color: "var(--ink-1)",
        }}
      >{`Patient: M. Hollister (MRN 8.4127.881)
Indication: chronic atrial fibrillation, CHA2DS2-VASc 3
Agent: apixaban 5 mg BID since 2023-06-14
Last dose: 2025-05-07 evening

Pre-op timing (open inguinal hernia repair, CPT 49505):
  - Bleed risk:        moderate
  - Recommended hold:  >= 48 h before incision
  - Restart:           24 h after hemostasis confirmed
  - Bridge:            not indicated (CHA2DS2-VASc 3, non-MV AF)

Pending: INR recheck ordered 2025-05-06 (ServiceRequest/req-9981).
Goal: INR < 1.4 morning of surgery.`}</pre>
      <H3>Sources</H3>
      <P>
        Apixaban active list <Cite id="c_1042" onClick={() => onCitationClick("c_1042")} active={false} /> recent CBC{" "}
        <Cite id="c_1078" onClick={() => onCitationClick("c_1078")} active={false} /> INR order{" "}
        <Cite id="c_1091" onClick={() => onCitationClick("c_1091")} active={false} />
      </P>
    </DocFrame>
  );
}

function SummaryJson() {
  return (
    <pre
      className="overflow-x-auto px-10 py-8 text-[12px] leading-[1.7]"
      style={{ fontFamily: "var(--font-mono)", color: "var(--ink-2)" }}
    >
{`{
  "artifact": "clearance-summary",
  "version": "v2",
  "patient_ref": "Patient/8.4127.881",
  "or_date": "2025-05-12",
  "procedure": "CPT 49505 — inguinal hernia repair, open",
  "disposition": "REVIEW",
  "rationale": "Apixaban hold interval pending clinician approval",
  "holds": [
    { "drug": "apixaban", "hours": 48, "basis": "c_1042" },
    { "drug": "metformin", "hours": 12, "basis": "c_1056" }
  ],
  "approval_required": true,
  "approver_role": "attending",
  "export_blocked_until": "approval-anticoag-1",
  "citations": ["c_1042", "c_1078", "c_1091", "c_1094"]
}`}
    </pre>
  );
}

function DiffView() {
  const rows: { kind: "del" | "add" | "ctx" | "head"; line?: number; marker?: string; text: string }[] = [
    { kind: "head", text: "@@ pre-op-packet · v1 → v2 · disposition block @@" },
    { kind: "del", line: 12, marker: "-", text: '"disposition": "CLEAR"' },
    { kind: "add", line: 12, marker: "+", text: '"disposition": "REVIEW"' },
    { kind: "del", line: 13, marker: "-", text: '"rationale": "All hold rules satisfied"' },
    { kind: "add", line: 13, marker: "+", text: '"rationale": "Apixaban hold interval pending clinician approval"' },
    { kind: "head", text: "@@ holds @@" },
    { kind: "ctx", line: 17, marker: " ", text: '{ "drug": "metformin", "hours": 12, "basis": "c_1056" },' },
    { kind: "add", line: 18, marker: "+", text: '{ "drug": "apixaban",  "hours": 48, "basis": "c_1042" },' },
    { kind: "ctx", line: 19, marker: " ", text: '{ "drug": "lisinopril","hours": 12, "basis": "c_1061" },' },
  ];
  return (
    <div className="px-6 py-6 text-[12.5px]" style={{ fontFamily: "var(--font-mono)" }}>
      {rows.map((r, i) => {
        if (r.kind === "head") {
          return (
            <div
              key={i}
              className="mt-3 mb-1 px-2 py-1 text-[11px] font-semibold"
              style={{ color: "var(--ink-3)", background: "var(--surface-2)" }}
            >
              {r.text}
            </div>
          );
        }
        const bg =
          r.kind === "add"
            ? "rgba(4,120,87,0.08)"
            : r.kind === "del"
            ? "rgba(185,28,28,0.06)"
            : "transparent";
        const color =
          r.kind === "add" ? "var(--clear)" : r.kind === "del" ? "var(--critical)" : "var(--ink-2)";
        return (
          <div
            key={i}
            className="grid grid-cols-[40px_14px_1fr] items-baseline px-2"
            style={{ background: bg, color }}
          >
            <span className="text-right pr-2 text-[10.5px]" style={{ color: "var(--ink-4)" }}>
              {r.line}
            </span>
            <span>{r.marker}</span>
            <span className="whitespace-pre-wrap">{r.text}</span>
          </div>
        );
      })}
    </div>
  );
}

function TrialBoard() {
  const trials = [
    {
      id: "NCT-0421187",
      title: "Phase III ABL-tyrosine kinase inhibitor in chronic myeloid leukemia (post-imatinib intolerance)",
      fit: 0.92,
      risk: "Moderate travel burden",
      site: "MSKCC — New York, NY",
      enroll: "2/40",
      primary: "Open packet",
    },
    {
      id: "NCT-0387714",
      title: "Open-label study of bcl-2 inhibitor in relapsed AML — biomarker-stratified",
      fit: 0.68,
      risk: "Exclusion criteria uncertain",
      site: "Mayo Clinic — Rochester, MN",
      enroll: "12/30",
      primary: "Pause for review",
    },
    {
      id: "NCT-0294512",
      title: "Maintenance therapy in MDS — community oncology arm",
      fit: 0.41,
      risk: "Site responsiveness unknown",
      site: "Community Network — multi-site",
      enroll: "—",
      primary: "Keep in backlog",
    },
  ];
  return (
    <div className="mx-auto max-w-[820px] px-10 pb-16 pt-8">
      <H1>Candidate board · Hollister</H1>
      <DocSub>working/candidate-board.json · 14 candidates ranked · last refresh 2 min ago</DocSub>
      <div className="space-y-3">
        {trials.map((t) => (
          <div
            key={t.id}
            className="grid grid-cols-[1fr_auto] gap-4 rounded-md border p-4"
            style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}
          >
            <div>
              <div
                className="text-[11px] font-semibold tracking-wider"
                style={{ color: "var(--action)", fontFamily: "var(--font-mono)" }}
              >
                trial:{t.id}
              </div>
              <div
                className="mt-1 text-[14px] font-semibold"
                style={{ color: "var(--ink-1)" }}
              >
                {t.title}
              </div>
              <div
                className="mt-2 flex flex-wrap gap-3 text-[11.5px]"
                style={{ color: "var(--ink-3)" }}
              >
                <span className="inline-flex items-center gap-1.5">
                  <MapPin className="h-3 w-3" strokeWidth={1.5} />
                  {t.site}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Users2 className="h-3 w-3" strokeWidth={1.5} />
                  {t.enroll}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <AlertTriangle className="h-3 w-3" strokeWidth={1.5} />
                  {t.risk}
                </span>
              </div>
            </div>
            <div className="flex flex-col items-end justify-between gap-2">
              <FitMeter value={t.fit} />
              <div className="flex gap-1.5">
                <button
                  className="h-[26px] rounded-md border px-2.5 text-[11.5px] font-medium"
                  style={{
                    background: "var(--surface-0)",
                    borderColor: "var(--line-2)",
                    color: "var(--ink-2)",
                  }}
                >
                  Compare
                </button>
                <button
                  className="h-[26px] rounded-md px-2.5 text-[11.5px] font-medium text-white"
                  style={{ background: "var(--action)" }}
                >
                  {t.primary}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FitMeter({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 w-24 overflow-hidden rounded-full"
        style={{ background: "var(--surface-3)" }}
      >
        <span
          className="block h-full rounded-full"
          style={{
            width: `${value * 100}%`,
            background: value > 0.75 ? "var(--clear)" : value > 0.5 ? "var(--caution)" : "var(--critical)",
          }}
        />
      </div>
      <span
        className="text-[11.5px]"
        style={{
          color: "var(--ink-2)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}

function PacketOutline() {
  return (
    <DocFrame>
      <H1>Outreach packet outline</H1>
      <DocSub>working/packet-outline.md · drafted by Trial Finder agent</DocSub>
      <H2>1. Patient anchors (de-identified)</H2>
      <P>Age band, primary diagnosis with onset year, biomarker profile (BCR-ABL+, complete), prior lines of therapy, performance status (ECOG 1).</P>
      <H2>2. Eligibility match summary</H2>
      <P>Inclusion criteria addressed line-by-line against patient evidence. Exclusion gaps flagged with FHIR references.</P>
      <H2>3. Travel and logistics</H2>
      <P>Distance to MSKCC site is 38 mi. Caregiver support documented. No identified financial blocker.</P>
      <H2>4. Pending approvals</H2>
      <P>Outbound contact requires explicit consent for external registry communication. Approval card surfaces in chat before packet is sent.</P>
    </DocFrame>
  );
}

function ManifestJson() {
  return (
    <pre
      className="overflow-x-auto px-10 py-8 text-[12px] leading-[1.7]"
      style={{ fontFamily: "var(--font-mono)", color: "var(--ink-2)" }}
    >
{`{
  "package": "trial-finder",
  "version": "2.4.1",
  "boundary": "consented-external",
  "connectors": ["clinicaltrials.gov", "patient-workspace", "web-search"],
  "requires_consent": true,
  "exports": ["markdown", "json", "shareable-bundle"]
}`}
    </pre>
  );
}
