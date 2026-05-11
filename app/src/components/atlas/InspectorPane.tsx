import { Eye, GitBranch, Pin, Quote } from "lucide-react";
import type { TraceDetail } from "../../types";
import { CITATIONS, type Citation } from "./data";

type InspectorPaneProps = {
  citationId: string | null;
  activeTab?: Tab;
  onTabChange?: (tab: Tab) => void;
  citations?: Record<string, Citation>;
  trace?: TraceDetail | null;
  traceByCitationId?: Record<string, TraceDetail | null>;
  contextItems?: InspectorContextItem[];
};

type Tab = "evidence" | "trace" | "context";
export type InspectorContextItem = { label: string; value: string };

export function InspectorPane({
  citationId,
  activeTab = "evidence",
  onTabChange,
  citations,
  trace,
  traceByCitationId,
  contextItems,
}: InspectorPaneProps) {
  const cite = citationId ? (citations?.[citationId] ?? CITATIONS[citationId] ?? null) : null;
  const selectedTrace = citationId
    ? (traceByCitationId?.[citationId] ?? trace ?? null)
    : (trace ?? null);
  return (
    <div
      className="grid h-full min-h-0 grid-rows-[auto_1fr] overflow-hidden"
      style={{ background: "var(--surface-1)" }}
    >
      <div
        className="flex h-8 items-center gap-2 border-b px-3"
        style={{
          background: "var(--bg-chrome)",
          borderColor: "var(--line-1)",
        }}
      >
        <span
          className="text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--ink-4)" }}
        >
          INSPECTOR
        </span>
        <div className="flex-1" />
        <div className="flex gap-1">
          <ITab active={activeTab === "evidence"} onClick={() => onTabChange?.("evidence")}>
            Evidence
          </ITab>
          <ITab active={activeTab === "trace"} onClick={() => onTabChange?.("trace")}>
            Trace
          </ITab>
          <ITab active={activeTab === "context"} onClick={() => onTabChange?.("context")}>
            Context
          </ITab>
        </div>
      </div>
      <div className="overflow-y-auto px-3.5 pb-5 pt-3.5">
        {activeTab === "evidence" && (cite ? <EvidenceView cite={cite} /> : <Empty />)}
        {activeTab === "trace" && <TraceView trace={selectedTrace} />}
        {activeTab === "context" && <ContextView items={contextItems} />}
      </div>
    </div>
  );
}

function ITab({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="rounded px-2 py-0.5 text-[11px] font-medium"
      style={
        active
          ? {
              background: "var(--surface-0)",
              color: "var(--action)",
              boxShadow: "var(--shadow-1)",
            }
          : { color: "var(--ink-3)" }
      }
    >
      {children}
    </button>
  );
}

function Empty() {
  return (
    <div className="grid h-full place-items-center px-5 text-center">
      <div>
        <div
          className="mx-auto mb-2.5 grid h-8 w-8 place-items-center rounded-md"
          style={{ background: "var(--surface-2)", color: "var(--ink-4)" }}
        >
          <Quote className="h-4 w-4" strokeWidth={1.5} />
        </div>
        <div
          className="mb-1 text-[12.5px] font-semibold"
          style={{ color: "var(--ink-2)" }}
        >
          No citation selected
        </div>
        <div
          className="mx-auto max-w-[220px] text-[11.5px] leading-[1.5]"
          style={{ color: "var(--ink-4)" }}
        >
          Click a citation chip in chat or a source ID in a table to pull evidence here.
        </div>
      </div>
    </div>
  );
}

function EvidenceView({ cite }: { cite: Citation }) {
  return (
    <div key={cite.id}>
      <div
        className="overflow-hidden rounded-[10px] border"
        style={{ background: "var(--surface-0)", borderColor: "var(--line-1)" }}
      >
        <div
          className="border-b px-3 py-2.5"
          style={{
            background: "var(--surface-1)",
            borderColor: "var(--line-1)",
          }}
        >
          <div
            className="text-[11px] font-semibold"
            style={{ color: "var(--action)", fontFamily: "var(--font-mono)" }}
          >
            {cite.id}
          </div>
          <div
            className="mt-0.5 text-[10.5px] uppercase tracking-wider"
            style={{ color: "var(--ink-4)" }}
          >
            {cite.type}
          </div>
        </div>
        <div className="px-3 py-3 text-[12.5px] leading-[1.55]" style={{ color: "var(--ink-1)" }}>
          <div className="mb-2 text-[13px] font-semibold">{cite.title}</div>
          <div>{cite.snippet}</div>
        </div>
        <dl
          className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 border-t px-3 py-2.5 text-[11px]"
          style={{ borderColor: "var(--line-1)" }}
        >
          <Meta label="FHIR ref" value={cite.source} />
          <Meta label="Encounter" value={cite.encounter} />
          <Meta label="Author" value={cite.author} sans />
          <Meta label="Date" value={cite.date} />
        </dl>
        <div
          className="flex gap-1.5 border-t px-3 py-2"
          style={{ borderColor: "var(--line-1)" }}
        >
          <EcBtn icon={<Eye className="h-3 w-3" strokeWidth={1.5} />}>Open in FHIR</EcBtn>
          <EcBtn icon={<Pin className="h-3 w-3" strokeWidth={1.5} />}>Pin to run</EcBtn>
        </div>
      </div>
      <div className="mt-3.5">
        <Label>Related evidence</Label>
        {cite.related.map((r) => (
          <div
            key={r.id}
            className="mb-1 flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[11.5px]"
            style={{
              background: "var(--surface-0)",
              borderColor: "var(--line-1)",
            }}
          >
            <Quote
              className="h-2.5 w-2.5"
              strokeWidth={1.5}
              style={{ color: "var(--ink-4)" }}
            />
            <span style={{ color: "var(--action)", fontFamily: "var(--font-mono)" }}>
              {r.id}
            </span>
            <span
              className="flex-1 truncate"
              style={{ color: "var(--ink-2)" }}
            >
              {r.text}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Meta({ label, value, sans }: { label: string; value: string; sans?: boolean }) {
  return (
    <>
      <dt style={{ color: "var(--ink-4)" }}>{label}</dt>
      <dd
        className="m-0"
        style={{
          color: "var(--ink-2)",
          fontFamily: sans ? "var(--font-sans)" : "var(--font-mono)",
        }}
      >
        {value}
      </dd>
    </>
  );
}

function EcBtn({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <button
      className="inline-flex h-6 items-center gap-1.5 rounded-md border px-2.5 text-[11.5px] font-medium hover:border-[var(--action-line)] hover:bg-[var(--action-tint)] hover:text-[var(--action)]"
      style={{
        background: "var(--surface-0)",
        borderColor: "var(--line-1)",
        color: "var(--ink-2)",
      }}
    >
      {icon}
      {children}
    </button>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-wider"
      style={{ color: "var(--ink-4)" }}
    >
      {children}
    </div>
  );
}

function TraceView({ trace }: { trace: TraceDetail | null }) {
  if (!trace) {
    return (
      <div className="grid h-full place-items-center px-5 text-center">
        <div>
          <div
            className="mx-auto mb-2.5 grid h-8 w-8 place-items-center rounded-md"
            style={{ background: "var(--surface-2)", color: "var(--ink-4)" }}
          >
            <GitBranch className="h-4 w-4" strokeWidth={1.5} />
          </div>
          <div className="mb-1 text-[12.5px] font-semibold" style={{ color: "var(--ink-2)" }}>
            No live trace selected
          </div>
          <div className="mx-auto max-w-[220px] text-[11.5px] leading-[1.5]" style={{ color: "var(--ink-4)" }}>
            Ask Caspian a question or open a citation from a live response to inspect its tool activity here.
          </div>
        </div>
      </div>
    );
  }
  return (
    <div>
      <div
        className="mb-3 rounded-md border px-3 py-2 text-[11.5px]"
        style={{ background: "var(--surface-0)", borderColor: "var(--line-1)", color: "var(--ink-3)" }}
      >
        <div className="font-semibold text-[var(--ink-1)]">Trace {trace.trace_id}</div>
        <div className="mt-1 flex flex-wrap gap-3">
          <span>mode: {trace.mode_used ?? "—"}</span>
          <span>model: {trace.model_used ?? "—"}</span>
          {trace.duration_ms != null && <span>{(trace.duration_ms / 1000).toFixed(1)}s</span>}
        </div>
      </div>
      <Label>Recent tool calls</Label>
      {trace.tool_calls.map((call, i) => (
        <div
          key={i}
          className="mt-1.5 flex items-center gap-2.5 rounded-md border px-3 py-1.5 text-[11.5px]"
          style={{
            background: "var(--surface-0)",
            borderColor: "var(--line-1)",
            color: "var(--ink-3)",
          }}
        >
          <GitBranch className="h-3 w-3" strokeWidth={1.5} style={{ color: "var(--ink-4)" }} />
          <span style={{ color: "var(--ink-2)", fontFamily: "var(--font-mono)" }}>
            {call.tool_name}
          </span>
          <span style={{ color: "var(--ink-4)" }}>→</span>
          <span
            className="flex-1 truncate"
            style={{ color: "var(--action)", fontFamily: "var(--font-mono)" }}
          >
            {call.input_summary || call.output_summary || "tool call"}
          </span>
          {call.duration_ms != null && (
            <span
              className="text-[10.5px]"
              style={{ color: "var(--ink-4)", fontFamily: "var(--font-mono)" }}
            >
              {call.duration_ms.toFixed(0)}ms
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function ContextView({ items }: { items?: InspectorContextItem[] }) {
  if (items && items.length > 0) {
    return (
      <div>
        <Label>Session context</Label>
        <div className="grid gap-1 text-[11.5px]" style={{ fontFamily: "var(--font-mono)", color: "var(--ink-3)" }}>
          {items.map((item) => (
            <div key={item.label} className="flex justify-between gap-3 rounded-md border px-3 py-2" style={{ background: "var(--surface-0)", borderColor: "var(--line-1)" }}>
              <span>{item.label}</span>
              <span style={{ color: "var(--ink-1)" }}>{item.value}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const pinned = [
    { type: "artifact", label: "pre-op-packet-v2.md" },
    { type: "citation", label: "c_1042 · apixaban" },
    { type: "file", label: "anticoagulation-note.txt" },
    { type: "task", label: "approval-anticoag-1" },
  ];
  const coverage = [
    ["MedicationStatement", "14"],
    ["Observation", "208"],
    ["Condition", "17"],
    ["Encounter", "47"],
    ["DocumentReference", "96"],
  ];
  return (
    <div>
      <Label>Pinned to this run</Label>
      {pinned.map((p, i) => (
        <div
          key={i}
          className="mb-1.5 flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[11.5px]"
          style={{
            background: "var(--surface-0)",
            borderColor: "var(--line-1)",
          }}
        >
          <Pin className="h-2.5 w-2.5" strokeWidth={1.5} style={{ color: "var(--ink-4)" }} />
          <span style={{ color: "var(--action)", fontFamily: "var(--font-mono)" }}>
            {p.type}:
          </span>
          <span style={{ color: "var(--ink-2)" }}>{p.label}</span>
        </div>
      ))}
      <div className="mt-4">
        <Label>Source coverage</Label>
        <div className="grid gap-1 text-[11.5px]" style={{ fontFamily: "var(--font-mono)", color: "var(--ink-3)" }}>
          {coverage.map(([k, v]) => (
            <div key={k} className="flex justify-between">
              <span>{k}</span>
              <span style={{ color: "var(--ink-1)" }}>{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
