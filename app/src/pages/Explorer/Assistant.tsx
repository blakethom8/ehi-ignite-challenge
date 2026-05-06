import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import {
  AlertTriangle,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  Database,
  Eye,
  Layers3,
  MessageSquare,
  RotateCcw,
  Search,
  Send,
  Sparkles,
  Terminal,
  User,
  X,
} from "lucide-react";
import { api } from "../../api/client";
import { AgentSettingsPanel } from "../../components/AgentSettingsPanel";
import { useChatForPatient } from "../../context/ChatContext";
import type { ChatMessage } from "../../context/ChatContext";
import type {
  ProviderAssistantResponse,
  ProviderAssistantContextPackage,
  TraceDetail,
  ToolCallDetail,
} from "../../types";

// ── Helpers ──────────────────────────────────────────────────────────────────

const STARTER_PROMPTS = [
  "What should I review first in this chart?",
  "Are there any concerning labs or trends?",
  "What changed recently in this patient's record?",
  "Summarize active problems and medications.",
];

const CONTEXT_LIBRARY_PACKAGES: ProviderAssistantContextPackage[] = [
  {
    id: "preop-medication-holds",
    title: "Pre-op Medication Holds",
    type: "Medication safety",
    summary: "Antiplatelets, anticoagulants, NSAIDs, diabetes medications, and perioperative medication questions.",
    instructions:
      "When answering pre-op questions, explicitly review antiplatelets, anticoagulants, NSAIDs, diabetes medications, and supplements. Separate active medications from historical medications. If a hold window depends on procedure type or renal function, say what must be verified.",
  },
  {
    id: "cardiometabolic-review",
    title: "Cardiometabolic Review",
    type: "Disease review",
    summary: "Diabetes, blood pressure, lipids, kidney function, weight, and medication context.",
    instructions:
      "For cardiometabolic questions, look across A1c, blood pressure, lipids, BMI, kidney function, and active therapy. Highlight missing recent labs or unclear treatment adherence. Avoid implying longitudinal control when the data is sparse.",
  },
  {
    id: "patient-context-intake",
    title: "Patient Context Intake",
    type: "Qualitative context",
    summary: "Patient goals, preferences, timeline clarifications, symptoms, and questions not present in chart exports.",
    instructions:
      "When chart evidence is incomplete, identify what patient-reported context would help: current symptoms, medication reality, goals, care preferences, recent outside care, and source gaps. Label these as questions for the patient, not verified chart facts.",
  },
  {
    id: "local-clinical-style-guide",
    title: "Local Clinical Style Guide",
    type: "Organization rules",
    summary: "Concise answer format, escalation posture, and preferred clinical wording.",
    instructions:
      "Answer in a concise clinical review style. Start with the direct answer, then bullets for evidence, uncertainties, and next actions. Use bold only for the most important finding or action. Do not use broad disclaimers unless there is a specific safety boundary.",
  },
];

function fmt(dt: string | null): string {
  if (!dt) return "";
  return new Date(dt).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function confidenceBadge(level: ProviderAssistantResponse["confidence"]) {
  const styles = {
    high: "bg-green-100 text-green-800",
    medium: "bg-amber-100 text-amber-800",
    low: "bg-red-100 text-red-800",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase ${styles[level]}`}>
      {level}
    </span>
  );
}

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (error.message?.trim()) return error.message;
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return "Request failed. Try again.";
}

type AssistantMarkdownBlock =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; lines: string[] }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "separator" };

function parseAssistantMarkdown(content: string): AssistantMarkdownBlock[] {
  const blocks: AssistantMarkdownBlock[] = [];
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  let paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  function flushParagraph() {
    if (paragraph.length > 0) {
      blocks.push({ type: "paragraph", lines: paragraph });
      paragraph = [];
    }
  }

  function flushList() {
    if (list) {
      blocks.push({ type: "list", ordered: list.ordered, items: list.items });
      list = null;
    }
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = /^(#{1,6})\s+(.+)$/.exec(line);
    if (headingMatch) {
      flushParagraph();
      flushList();
      blocks.push({ type: "heading", level: headingMatch[1].length, text: headingMatch[2].trim() });
      continue;
    }

    if (/^[-*_]{3,}$/.test(line)) {
      flushParagraph();
      flushList();
      blocks.push({ type: "separator" });
      continue;
    }

    const unorderedMatch = /^[-*]\s+(.+)$/.exec(line);
    const orderedMatch = /^\d+[.)]\s+(.+)$/.exec(line);
    if (unorderedMatch || orderedMatch) {
      flushParagraph();
      const ordered = Boolean(orderedMatch);
      const text = (orderedMatch?.[1] ?? unorderedMatch?.[1] ?? "").trim();
      if (!list || list.ordered !== ordered) {
        flushList();
        list = { ordered, items: [] };
      }
      list.items.push(text);
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();
  return blocks;
}

function renderInlineMarkdown(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const pattern = /\*\*([^*]+)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    nodes.push(
      <strong key={`${match.index}-${match[1]}`} className="font-semibold text-[#111827]">
        {match[1]}
      </strong>,
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.length ? nodes : [text];
}

function AssistantMarkdown({ content, compact = false }: { content: string; compact?: boolean }) {
  const blocks = parseAssistantMarkdown(content);
  const textSize = compact ? "text-[12px]" : "text-[13px]";

  return (
    <div className={`space-y-3 ${textSize} leading-6 text-[#1c1c1e]`}>
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const levelClass = block.level <= 2 ? "text-[15px]" : "text-[13px]";
          return (
            <h3 key={index} className={`${levelClass} pt-1 font-semibold tracking-normal text-[#111827]`}>
              {renderInlineMarkdown(block.text)}
            </h3>
          );
        }

        if (block.type === "separator") {
          return <div key={index} className="h-px bg-slate-200" />;
        }

        if (block.type === "list") {
          const ListTag = block.ordered ? "ol" : "ul";
          return (
            <ListTag
              key={index}
              className={`${block.ordered ? "list-decimal" : "list-disc"} space-y-1 pl-5 marker:text-slate-400`}
            >
              {block.items.map((item, itemIndex) => (
                <li key={`${index}-${itemIndex}`} className="pl-1">
                  {renderInlineMarkdown(item)}
                </li>
              ))}
            </ListTag>
          );
        }

        return (
          <p key={index} className="max-w-none">
            {renderInlineMarkdown(block.lines.join(" "))}
          </p>
        );
      })}
    </div>
  );
}

// ── Expandable section ───────────────────────────────────────────────────────

function ExpandableSection({
  title, icon, defaultOpen = false, count, children,
}: {
  title: string;
  icon: React.ReactNode;
  defaultOpen?: boolean;
  count?: number;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 w-full px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500 hover:bg-slate-100 transition-colors"
      >
        {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        {icon}
        {title}
        {count != null && <span className="ml-auto text-slate-400 font-normal lowercase">{count}</span>}
      </button>
      {open && <div className="px-2.5 pb-2">{children}</div>}
    </div>
  );
}

// ── Tool calls display ───────────────────────────────────────────────────────

const TOOL_ICONS: Record<string, React.ReactNode> = {
  run_sql: <Database size={10} className="text-purple-500" />,
  query_chart_evidence: <Search size={10} className="text-blue-500" />,
  get_patient_snapshot: <Eye size={10} className="text-green-500" />,
  baseline_evidence: <Terminal size={10} className="text-slate-500" />,
};

type SessionPanelTab = "context" | "settings" | "logs";

type SelectedToolLog = {
  trace: TraceDetail;
  toolCall: ToolCallDetail;
  index: number;
};

function ToolCallsSection({
  trace,
  onSelectToolCall,
}: {
  trace: TraceDetail;
  onSelectToolCall?: (selection: SelectedToolLog) => void;
}) {
  return (
    <div className="space-y-1">
      {trace.tool_calls.map((tc, i) => (
        <ToolCallCard
          key={`${tc.tool_name}-${i}`}
          tc={tc}
          onSelect={() => onSelectToolCall?.({ trace, toolCall: tc, index: i })}
        />
      ))}
    </div>
  );
}

function ToolCallCard({ tc, onSelect }: { tc: ToolCallDetail; onSelect?: () => void }) {
  const [expanded, setExpanded] = useState(!!tc.error);
  const icon = TOOL_ICONS[tc.tool_name] || <Terminal size={10} className="text-slate-400" />;
  const hasError = !!tc.error;

  return (
    <div className={`rounded-md border text-[11px] ${hasError ? "border-red-200 bg-red-50" : "border-slate-200 bg-slate-50"}`}>
      <button
        onClick={() => {
          onSelect?.();
          setExpanded(!expanded);
        }}
        className="flex items-center gap-1.5 w-full px-2 py-1.5 hover:bg-slate-100/50 transition-colors text-left"
      >
        {icon}
        <span className={`font-medium ${hasError ? "text-red-700" : "text-slate-700"}`}>{tc.tool_name}</span>
        <span className={`ml-1 truncate flex-1 ${hasError ? "text-red-500" : "text-slate-400"}`}>
          {hasError ? `Error: ${tc.error}` : tc.output_summary}
        </span>
        {tc.duration_ms != null && (
          <span className="text-[9px] text-slate-400 shrink-0">{tc.duration_ms.toFixed(0)}ms</span>
        )}
        {expanded ? <ChevronDown size={10} className="text-slate-400 shrink-0" /> : <ChevronRight size={10} className="text-slate-400 shrink-0" />}
      </button>
      {expanded && (
        <div className="px-2 pb-2 space-y-1">
          {tc.input_summary && (
            <div>
              <span className="text-[9px] font-semibold uppercase text-slate-400">Input</span>
              <pre className="whitespace-pre-wrap text-[10px] text-slate-600 font-mono bg-white rounded px-1.5 py-1 mt-0.5 max-h-40 overflow-y-auto">
                {tc.input_summary}
              </pre>
            </div>
          )}
          <div>
            <span className="text-[9px] font-semibold uppercase text-slate-400">Result</span>
            <p className={`text-[10px] mt-0.5 ${hasError ? "text-red-600 font-medium" : "text-slate-600"}`}>
              {hasError ? `Error: ${tc.error}` : tc.output_summary}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Context modal ────────────────────────────────────────────────────────────

function ContextModal({ trace, onClose }: { trace: TraceDetail; onClose: () => void }) {
  const [tab, setTab] = useState<"context" | "facts" | "tools">("context");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl w-[90vw] max-w-5xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="shrink-0 border-b border-slate-200 px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold text-[#1c1c1e]">Full Transparency View</h2>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Exactly what the AI received, how it was configured, and what data it used.
              </p>
            </div>
            <button onClick={onClose} className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors">
              ✕
            </button>
          </div>

          {/* Config summary bar */}
          <div className="flex items-center gap-4 rounded-lg bg-slate-50 px-4 py-2.5">
            <div>
              <span className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">Model</span>
              <p className="text-[12px] font-medium text-[#1c1c1e]">{trace.model_used || "unknown"}</p>
            </div>
            <div className="h-6 w-px bg-slate-200" />
            <div>
              <span className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">Mode</span>
              <p className="text-[12px] font-medium text-[#1c1c1e]">{trace.mode_used || trace.trace_id}</p>
            </div>
            <div className="h-6 w-px bg-slate-200" />
            <div>
              <span className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">Max Tokens</span>
              <p className="text-[12px] font-medium text-[#1c1c1e]">{trace.max_tokens_used ?? "—"}</p>
            </div>
            <div className="h-6 w-px bg-slate-200" />
            <div>
              <span className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">Context Size</span>
              <p className="text-[12px] font-medium text-[#1c1c1e]">
                ~{trace.context_token_estimate ?? trace.input_tokens} tokens
              </p>
            </div>
            {trace.duration_ms != null && (
              <>
                <div className="h-6 w-px bg-slate-200" />
                <div>
                  <span className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">Latency</span>
                  <p className="text-[12px] font-medium text-[#1c1c1e]">{(trace.duration_ms / 1000).toFixed(1)}s</p>
                </div>
              </>
            )}
            {trace.total_cost_usd != null && (
              <>
                <div className="h-6 w-px bg-slate-200" />
                <div>
                  <span className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">Cost</span>
                  <p className="text-[12px] font-medium text-[#1c1c1e]">${trace.total_cost_usd.toFixed(4)}</p>
                </div>
              </>
            )}
            {trace.history_turns_sent != null && trace.history_turns_sent > 0 && (
              <>
                <div className="h-6 w-px bg-slate-200" />
                <div>
                  <span className="text-[9px] font-semibold uppercase tracking-wider text-slate-400">History</span>
                  <p className="text-[12px] font-medium text-[#1c1c1e]">{trace.history_turns_sent} prior turns</p>
                </div>
              </>
            )}
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mt-3">
            {([
              { key: "context" as const, label: "System Prompt", desc: "What the AI was told" },
              { key: "facts" as const, label: `Retrieved Facts (${trace.retrieved_facts.length})`, desc: "Patient data used" },
              { key: "tools" as const, label: `Tool Calls (${trace.tool_calls.length})`, desc: "Operations performed" },
            ]).map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`rounded-lg px-3 py-1.5 text-[11px] font-medium transition-colors ${
                  tab === key ? "bg-blue-100 text-blue-700" : "text-slate-500 hover:bg-slate-100"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto p-5 min-h-0">
          {/* System Prompt tab */}
          {tab === "context" && (
            <div>
              <div className="mb-3 rounded-lg bg-amber-50 border border-amber-200 px-4 py-2.5">
                <p className="text-[11px] text-amber-800">
                  This is the <strong>exact system prompt</strong> sent to the AI model. The model sees only this context
                  and your question — nothing else. All clinical data below was extracted from the patient's FHIR bundle.
                </p>
              </div>
              {trace.system_prompt_preview ? (
                <pre className="whitespace-pre-wrap text-[11px] leading-relaxed text-slate-700 font-mono bg-slate-50 rounded-lg p-4 border border-slate-200">
                  {trace.system_prompt_preview}
                </pre>
              ) : (
                <p className="text-[12px] text-slate-400 text-center py-8">
                  No system prompt was captured for this request. This may indicate the deterministic engine was used (no LLM involved).
                </p>
              )}
            </div>
          )}

          {/* Retrieved Facts tab */}
          {tab === "facts" && (
            <div>
              <div className="mb-3 rounded-lg bg-blue-50 border border-blue-200 px-4 py-2.5">
                <p className="text-[11px] text-blue-800">
                  These are the <strong>specific clinical facts</strong> extracted from the patient's chart and used to generate the response.
                  Each fact is traceable to a FHIR resource.
                </p>
              </div>
              {trace.retrieved_facts.length > 0 ? (
                <div className="space-y-1.5">
                  {trace.retrieved_facts.map((fact, i) => {
                    const tag = fact.match(/^\[(\w+)\]/)?.[1] || "";
                    const text = fact.replace(/^\[\w+\]\s*/, "");
                    const tagColor: Record<string, string> = {
                      Safety: "bg-red-100 text-red-700",
                      Med: "bg-purple-100 text-purple-700",
                      Lab: "bg-green-100 text-green-700",
                      Condition: "bg-amber-100 text-amber-700",
                    };
                    return (
                      <div key={i} className="flex items-start gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5">
                        {tag && (
                          <span className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase ${tagColor[tag] || "bg-slate-100 text-slate-600"}`}>
                            {tag}
                          </span>
                        )}
                        <span className="text-[11px] text-slate-700 leading-relaxed">{text}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-[12px] text-slate-400 text-center py-8">
                  No individual facts captured for this response.
                </p>
              )}
            </div>
          )}

          {/* Tool Calls tab */}
          {tab === "tools" && (
            <div>
              <div className="mb-3 rounded-lg bg-purple-50 border border-purple-200 px-4 py-2.5">
                <p className="text-[11px] text-purple-800">
                  These are the <strong>operations the AI performed</strong> to gather data — database queries, chart lookups, and evidence retrieval.
                </p>
              </div>
              {trace.tool_calls.length > 0 ? (
                <div className="space-y-3">
                  {trace.tool_calls.map((tc, i) => (
                    <div key={i} className={`rounded-lg border p-4 text-[11px] ${tc.error ? "border-red-200 bg-red-50" : "border-slate-200 bg-white"}`}>
                      <div className="flex items-center gap-2 mb-2">
                        {TOOL_ICONS[tc.tool_name] || <Terminal size={12} />}
                        <span className="font-semibold text-slate-800 text-[12px]">{tc.tool_name}</span>
                        {tc.duration_ms != null && (
                          <span className="ml-auto text-[10px] text-slate-400">{tc.duration_ms.toFixed(0)}ms</span>
                        )}
                      </div>
                      {tc.input_summary && (
                        <div className="mb-2">
                          <span className="text-[9px] font-semibold uppercase text-slate-400">Input</span>
                          <pre className="whitespace-pre-wrap text-[10px] text-slate-700 font-mono bg-slate-50 rounded px-2.5 py-1.5 mt-0.5 max-h-48 overflow-y-auto">
                            {tc.input_summary}
                          </pre>
                        </div>
                      )}
                      <div>
                        <span className="text-[9px] font-semibold uppercase text-slate-400">Result</span>
                        <p className={`text-[11px] mt-0.5 ${tc.error ? "text-red-600 font-medium" : "text-slate-700"}`}>
                          {tc.error ? `Error: ${tc.error}` : tc.output_summary}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[12px] text-slate-400 text-center py-8">
                  No tool calls were made. The context mode pre-builds all clinical data before calling the AI — no runtime tool use needed.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ContextPackagePreviewModal({
  contextPackage,
  attached,
  onTogglePackage,
  onClose,
}: {
  contextPackage: ProviderAssistantContextPackage;
  attached: boolean;
  onTogglePackage: (contextPackage: ProviderAssistantContextPackage) => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 px-4" onClick={onClose}>
      <div
        className="flex max-h-[82vh] w-full max-w-2xl flex-col rounded-xl bg-white shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="shrink-0 border-b border-slate-200 px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#9a5a16]">Context package</p>
              <h2 className="mt-1 text-lg font-semibold tracking-normal text-[#1c1c1e]">{contextPackage.title}</h2>
              <p className="mt-1 text-sm leading-6 text-[#667085]">{contextPackage.summary}</p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
              title="Close preview"
            >
              <X size={17} />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Package type</p>
              <span className="rounded-full bg-white px-2 py-1 text-[11px] font-semibold text-[#9a5a16]">
                {contextPackage.type}
              </span>
            </div>
          </div>

          <div className="mt-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Prompt instructions</p>
            <pre className="mt-2 max-h-[42vh] overflow-y-auto whitespace-pre-wrap rounded-xl border border-slate-200 bg-white p-4 text-[12px] leading-6 text-slate-700">
              {contextPackage.instructions}
            </pre>
          </div>
        </div>

        <div className="shrink-0 border-t border-slate-200 px-5 py-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] leading-4 text-slate-500">
              This text is sent as session guidance. It does not replace patient-specific chart evidence.
            </p>
            <button
              type="button"
              onClick={() => onTogglePackage(contextPackage)}
              className={`inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-[12px] font-semibold transition-colors ${
                attached ? "bg-[#e9f8ef] text-[#087443]" : "bg-[#fff1df] text-[#9a5a16] hover:bg-[#ffe6cd]"
              }`}
            >
              {attached ? <Check size={13} /> : <Layers3 size={13} />}
              {attached ? "Attached" : "Attach package"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SessionContextPanel({
  openTab,
  onTabChange,
  activePackages,
  onTogglePackage,
  messages,
  selectedToolLog,
  onSelectToolLog,
  stance,
  setStance,
  settings,
  onUpdateSettings,
  onResetChat,
}: {
  openTab: SessionPanelTab;
  onTabChange: (tab: SessionPanelTab) => void;
  activePackages: ProviderAssistantContextPackage[];
  onTogglePackage: (contextPackage: ProviderAssistantContextPackage) => void;
  messages: ChatMessage[];
  selectedToolLog: SelectedToolLog | null;
  onSelectToolLog: (selection: SelectedToolLog) => void;
  stance: "opinionated" | "balanced";
  setStance: (stance: "opinionated" | "balanced") => void;
  settings: ReturnType<typeof useChatForPatient>["agentSettings"];
  onUpdateSettings: ReturnType<typeof useChatForPatient>["setAgentSettings"];
  onResetChat: ReturnType<typeof useChatForPatient>["resetChat"];
}) {
  const [previewPackage, setPreviewPackage] = useState<ProviderAssistantContextPackage | null>(null);
  const activeIds = new Set(activePackages.map((contextPackage) => contextPackage.id));
  const logEvents = messages.flatMap((message) =>
    message.role === "assistant" && message.trace
      ? message.trace.tool_calls.map((toolCall, index) => ({ trace: message.trace!, toolCall, index }))
      : [],
  );
  const activeLog = selectedToolLog ?? logEvents[0] ?? null;
  const panelTitle =
    openTab === "settings" ? "Chat settings" : openTab === "logs" ? "Tool logs" : "Review context";

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const packageId = event.dataTransfer.getData("application/ehi-context-package");
    const contextPackage = CONTEXT_LIBRARY_PACKAGES.find((item) => item.id === packageId);
    if (contextPackage && !activeIds.has(contextPackage.id)) {
      onTogglePackage(contextPackage);
    }
  }

  return (
    <aside className="hidden w-[340px] shrink-0 flex-col border-l border-slate-200 bg-white xl:flex">
      {previewPackage && (
        <ContextPackagePreviewModal
          contextPackage={previewPackage}
          attached={activeIds.has(previewPackage.id)}
          onTogglePackage={onTogglePackage}
          onClose={() => setPreviewPackage(null)}
        />
      )}
      <div className="shrink-0 border-b border-slate-200 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#9a5a16]">Session tools</p>
            <h2 className="truncate text-sm font-semibold text-[#1c1c1e]">{panelTitle}</h2>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-1 rounded-xl bg-slate-100 p-1">
          {[
            ["context", "Context"],
            ["settings", "Settings"],
            ["logs", "Logs"],
          ].map(([tab, label]) => (
            <button
              key={tab}
              type="button"
              onClick={() => onTabChange(tab as SessionPanelTab)}
              className={`rounded-lg px-2 py-1.5 text-[11px] font-semibold transition-colors ${
                openTab === tab ? "bg-white text-[#1c1c1e] shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {openTab === "context" && (
        <div className="flex-1 overflow-y-auto p-2.5">
          <div className="mb-2.5 grid gap-2">
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#5b76fe]">Agent profile</p>
              <h3 className="mt-1 text-xs font-semibold text-[#1c1c1e]">General chart review</h3>
              <p className="mt-1 text-[11px] leading-4 text-slate-500">
                Uses the active published chart, citations, and attached packages. It does not assume a surgical workflow unless you ask for one.
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">System context</p>
              <h3 className="mt-1 text-xs font-semibold text-[#1c1c1e]">Published chart boundary</h3>
              <p className="mt-1 text-[11px] leading-4 text-slate-500">
                Chart facts come from the active published snapshot. Context packages guide review style but do not replace patient evidence.
              </p>
            </div>
          </div>

          <div
            onDragOver={(event) => event.preventDefault()}
            onDrop={handleDrop}
            className="rounded-xl border border-dashed border-[#f0d7bf] bg-[#fffaf4] p-2.5"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-[#9a5a16]">Attached to chat</p>
                <p className="mt-0.5 text-[11px] leading-4 text-[#667085]">Sent as session instructions.</p>
              </div>
              <span className="rounded-full bg-white px-2 py-1 text-[11px] font-semibold text-[#9a5a16]">
                {activePackages.length}
              </span>
            </div>

            <div className="mt-2 space-y-1.5">
              {activePackages.length === 0 ? (
                <p className="rounded-lg bg-white px-2.5 py-2 text-[11px] leading-4 text-slate-500">
                  Attach from the library below or drag a package here.
                </p>
              ) : (
                activePackages.map((contextPackage) => (
                  <div key={contextPackage.id} className="rounded-lg bg-white px-2.5 py-2 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-semibold text-[#1c1c1e]">{contextPackage.title}</p>
                        <p className="truncate text-[10px] text-slate-500">{contextPackage.type}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setPreviewPackage(contextPackage)}
                        className="rounded-md px-1.5 py-1 text-[10px] font-semibold text-[#9a5a16] transition-colors hover:bg-[#fff1df]"
                      >
                        View
                      </button>
                      <button
                        type="button"
                        onClick={() => onTogglePackage(contextPackage)}
                        className="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                        title={`Remove ${contextPackage.title}`}
                      >
                        <X size={13} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="mt-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Context Library</p>
            <div className="mt-2 space-y-1.5">
              {CONTEXT_LIBRARY_PACKAGES.map((contextPackage) => {
                const attached = activeIds.has(contextPackage.id);
                return (
                  <article
                    key={contextPackage.id}
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.setData("application/ehi-context-package", contextPackage.id);
                    }}
                    className="rounded-lg border border-slate-200 bg-white px-2.5 py-2 transition-colors hover:border-[#f0d7bf] hover:bg-[#fffdf9]"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-semibold text-[#1c1c1e]">{contextPackage.title}</p>
                        <p className="truncate text-[10px] font-medium text-[#9a5a16]">
                          {contextPackage.type} · {contextPackage.summary}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setPreviewPackage(contextPackage)}
                        className="inline-flex shrink-0 items-center rounded-full bg-white px-2 py-1 text-[10px] font-semibold text-slate-600 ring-1 ring-slate-200 transition-colors hover:bg-slate-50"
                      >
                        View
                      </button>
                      <button
                        type="button"
                        onClick={() => onTogglePackage(contextPackage)}
                        className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-[10px] font-semibold transition-colors ${
                          attached ? "bg-[#e9f8ef] text-[#087443]" : "bg-[#fff1df] text-[#9a5a16] hover:bg-[#ffe6cd]"
                        }`}
                      >
                        {attached ? <Check size={11} /> : <Layers3 size={11} />}
                        {attached ? "Attached" : "Attach"}
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {openTab === "settings" && (
        <div className="flex-1 overflow-y-auto p-3">
          <div className="rounded-xl border border-slate-200 bg-white p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Session</p>
            <p className="mt-1 text-[11px] leading-4 text-slate-500">
              Start over when changing the review posture or testing a different chart question path.
            </p>
            <button
              type="button"
              onClick={onResetChat}
              className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[12px] font-semibold text-slate-700 transition-colors hover:border-[#5b76fe] hover:text-[#5b76fe]"
            >
              <RotateCcw size={13} />
              Reset conversation
            </button>
          </div>

          <div className="mt-3 rounded-xl bg-slate-50 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Review posture</p>
            <div className="mt-2 grid grid-cols-2 gap-1 rounded-lg bg-white p-1 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
              {(["opinionated", "balanced"] as const).map((nextStance) => (
                <button
                  key={nextStance}
                  type="button"
                  onClick={() => setStance(nextStance)}
                  className={`rounded-md px-2 py-1.5 text-[11px] font-semibold capitalize transition-colors ${
                    stance === nextStance ? "bg-blue-100 text-blue-700" : "text-slate-500 hover:bg-slate-50"
                  }`}
                >
                  {nextStance}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Model and mode</p>
            <AgentSettingsPanel settings={settings} onUpdate={onUpdateSettings} defaultOpen lockOpen />
          </div>

          <div className="mt-3 rounded-xl bg-[#fffaf4] p-3 text-xs leading-5 text-[#667085]">
            Context packages are distinct from chart facts. They guide the assistant’s review style and checklist, but
            the answer still needs patient-specific evidence.
          </div>
        </div>
      )}

      {openTab === "logs" && (
        <div className="flex-1 overflow-y-auto p-2.5">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-2.5">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Tool calls</p>
                <p className="mt-0.5 text-[11px] leading-4 text-slate-500">Select a call to inspect the input and result.</p>
              </div>
              <span className="rounded-full bg-white px-2 py-1 text-[11px] font-semibold text-slate-600">
                {logEvents.length}
              </span>
            </div>

            <div className="mt-2 space-y-1.5">
              {logEvents.length === 0 ? (
                <p className="rounded-lg bg-white px-2.5 py-2 text-[11px] leading-4 text-slate-500">
                  Tool calls, context builds, and retrieval events will appear here after the assistant responds.
                </p>
              ) : (
                logEvents.map((event) => {
                  const eventKey = `${event.trace.trace_id}-${event.index}-${event.toolCall.tool_name}`;
                  const activeKey = activeLog
                    ? `${activeLog.trace.trace_id}-${activeLog.index}-${activeLog.toolCall.tool_name}`
                    : "";
                  const hasError = Boolean(event.toolCall.error);
                  return (
                    <button
                      key={eventKey}
                      type="button"
                      onClick={() => onSelectToolLog(event)}
                      className={`w-full rounded-lg border px-2.5 py-2 text-left transition-colors ${
                        eventKey === activeKey
                          ? "border-[#5b76fe] bg-blue-50"
                          : "border-slate-200 bg-white hover:border-slate-300"
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        {TOOL_ICONS[event.toolCall.tool_name] || <Terminal size={10} className="text-slate-400" />}
                        <span className="truncate text-[11px] font-semibold text-[#1c1c1e]">
                          {event.toolCall.tool_name}
                        </span>
                        {event.toolCall.duration_ms != null && (
                          <span className="ml-auto shrink-0 text-[10px] text-slate-400">
                            {event.toolCall.duration_ms.toFixed(0)}ms
                          </span>
                        )}
                      </div>
                      <p className={`mt-1 truncate text-[10px] ${hasError ? "text-red-600" : "text-slate-500"}`}>
                        {hasError ? `Error: ${event.toolCall.error}` : event.toolCall.output_summary}
                      </p>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {activeLog && (
            <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold text-[#1c1c1e]">{activeLog.toolCall.tool_name}</p>
                  <p className="text-[10px] text-slate-500">Trace {activeLog.trace.trace_id}</p>
                </div>
                {activeLog.toolCall.error ? (
                  <span className="rounded-full bg-red-100 px-2 py-1 text-[10px] font-semibold text-red-700">Error</span>
                ) : (
                  <span className="rounded-full bg-green-100 px-2 py-1 text-[10px] font-semibold text-green-700">OK</span>
                )}
              </div>

              {activeLog.toolCall.input_summary && (
                <div className="mt-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Input</p>
                  <pre className="mt-1 max-h-44 overflow-y-auto rounded-lg bg-slate-50 p-2 text-[10px] leading-4 text-slate-700 font-mono whitespace-pre-wrap">
                    {activeLog.toolCall.input_summary}
                  </pre>
                </div>
              )}

              <div className="mt-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Result</p>
                <p className={`mt-1 text-[11px] leading-4 ${activeLog.toolCall.error ? "text-red-600" : "text-slate-600"}`}>
                  {activeLog.toolCall.error ? `Error: ${activeLog.toolCall.error}` : activeLog.toolCall.output_summary}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

// ── Shared message renderer (used by both full page and widget) ──────────────

export function ChatMessageBubble({
  msg,
  onSubmitFollowUp,
  onViewContext,
  onSelectToolCall,
  compact = false,
}: {
  msg: ChatMessage;
  onSubmitFollowUp: (question: string) => void;
  onViewContext?: (trace: TraceDetail) => void;
  onSelectToolCall?: (selection: SelectedToolLog) => void;
  compact?: boolean;
}) {
  if (msg.role === "user") {
    return (
      <div className="flex gap-2.5">
        <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200">
          <User size={12} className="text-slate-600" />
        </div>
        <p className={`${compact ? "text-[12px]" : "text-[13px]"} font-medium text-[#1c1c1e] leading-relaxed`}>{msg.content}</p>
      </div>
    );
  }

  return (
    <div className="flex gap-2.5">
      <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100">
        <Bot size={12} className="text-blue-600" />
      </div>
      <div className="flex-1 min-w-0 space-y-2">
        {!compact && msg.trace && msg.trace.tool_calls.length > 0 && (
          <ToolCallsSection trace={msg.trace} onSelectToolCall={onSelectToolCall} />
        )}

        {!compact && msg.trace && msg.trace.tool_calls.some((tc) => tc.tool_name === "build_clinical_context") && (
          <p className="text-[11px] text-[#a5a8b5]">
            <Link
              to="/analysis/methodology"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-[#5b76fe] hover:underline transition-colors"
            >
              See the methodology that built this context →
            </Link>
          </p>
        )}

        <AssistantMarkdown content={msg.content} compact={compact} />

        <div className="flex items-center gap-1.5 flex-wrap">
          {confidenceBadge(msg.confidence)}
          <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
            {msg.engine}
          </span>
          {!compact && msg.trace && (
            <>
              {msg.trace.duration_ms != null && (
                <span className="text-[10px] text-slate-400">{(msg.trace.duration_ms / 1000).toFixed(1)}s</span>
              )}
              {msg.trace.input_tokens > 0 && (
                <span className="text-[10px] text-slate-400">
                  {msg.trace.input_tokens.toLocaleString()} in / {msg.trace.output_tokens.toLocaleString()} out tokens
                </span>
              )}
            </>
          )}
          {msg.citations.length > 0 && (
            <span className="text-[10px] text-slate-400">{msg.citations.length} citations</span>
          )}
          {!compact && msg.trace && onViewContext && (
            <button
              onClick={() => onViewContext(msg.trace!)}
              className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-600 hover:bg-blue-100 transition-colors"
            >
              <Eye size={10} />
              View Full Context
            </button>
          )}
        </div>

        {!compact && msg.citations.length > 0 && (
          <ExpandableSection title="Evidence" icon={<Search size={10} />} defaultOpen count={msg.citations.length}>
            <div className="space-y-1">
              {msg.citations.map((c) => (
                <div key={`${c.source_type}:${c.resource_id}`} className="rounded bg-white px-2 py-1.5 text-[11px]">
                  <span className="font-medium text-[#1c1c1e]">{c.label}</span>
                  {c.event_date && <span className="text-slate-400 ml-1">· {fmt(c.event_date)}</span>}
                  <p className="text-slate-600 mt-0.5">{c.detail}</p>
                </div>
              ))}
            </div>
          </ExpandableSection>
        )}

        {!compact && msg.trace && msg.trace.system_prompt_preview && (
          <ExpandableSection title="Agent Context" icon={<Eye size={10} />} defaultOpen={false}>
            <pre className="whitespace-pre-wrap text-[10px] leading-relaxed text-slate-600 font-mono bg-white rounded p-2 max-h-60 overflow-y-auto">
              {msg.trace.system_prompt_preview}
            </pre>
          </ExpandableSection>
        )}

        {msg.followUps.length > 0 && (
          <div className="flex gap-1.5 flex-wrap">
            {msg.followUps.map((fu) => (
              <button
                key={fu}
                onClick={() => onSubmitFollowUp(fu)}
                className={`inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white ${compact ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]"} text-slate-600 hover:border-blue-300 hover:text-blue-700 transition-colors`}
              >
                <ChevronRight size={10} className="text-blue-400" />
                {fu.length > 60 ? fu.slice(0, 57) + "..." : fu}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Component ────────────────────────────────────────────────────────────────

export function ExplorerAssistant() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const [input, setInput] = useState("");
  const chat = useChatForPatient(patientId);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [contextModal, setContextModal] = useState<TraceDetail | null>(null);
  const [sessionPanelTab, setSessionPanelTab] = useState<SessionPanelTab>("context");
  const [selectedToolLog, setSelectedToolLog] = useState<SelectedToolLog | null>(null);

  const { data: overview } = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat.messages.length, chat.isPending]);

  function handleSubmit(question: string) {
    if (!question.trim() || chat.isPending) return;
    chat.submitQuestion(question);
    setInput("");
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    handleSubmit(input);
  }

  function handleSelectToolLog(selection: SelectedToolLog) {
    setSelectedToolLog(selection);
    setSessionPanelTab("logs");
  }

  const hasPatient = Boolean(patientId);
  const hasMessages = chat.messages.length > 0;
  const showBottomComposer = !hasPatient || hasMessages || chat.isPending || chat.isError;

  return (
    <div className="flex h-full overflow-hidden">
      {contextModal && <ContextModal trace={contextModal} onClose={() => setContextModal(null)} />}

      <div className="flex min-w-0 flex-1 flex-col">
      {/* Header bar */}
      <div className="shrink-0 flex items-center justify-between gap-3 pb-3 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100">
            <Sparkles size={14} className="text-blue-600" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-[#1c1c1e]">Provider Assistant</h1>
            <p className="text-[11px] text-slate-500">
              {hasPatient ? overview?.name ?? "Patient" : "Select patient"} · chart-grounded Q&A
            </p>
          </div>
        </div>

        {hasMessages && (
          <button
            type="button"
            onClick={chat.resetChat}
            disabled={chat.isPending}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[12px] font-semibold text-slate-600 transition-colors hover:border-[#5b76fe] hover:text-[#5b76fe] disabled:opacity-50"
          >
            <RotateCcw size={13} />
            New chat
          </button>
        )}
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto min-h-0 py-3 space-y-3">
        {!hasPatient && (
          <div className="flex h-full flex-col items-center justify-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50">
              <MessageSquare size={24} className="text-[#5b76fe]" />
            </div>
            <div className="text-center">
              <h2 className="text-base font-semibold text-[#1c1c1e]">Choose a patient to start</h2>
              <ul className="mt-3 space-y-2 text-left text-sm text-[#667085]">
                {[
                  "Ask clinical questions grounded in chart data",
                  "Get concise answers with evidence citations",
                  "Assistant challenges weak evidence",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[#5b76fe]" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {hasPatient && !hasMessages && !chat.isPending && (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-50">
              <Bot size={24} className="text-blue-500" />
            </div>
            <p className="text-sm text-slate-500 text-center max-w-md">
              Ask a clinical question about this patient. Answers are grounded in chart evidence.
            </p>
            <div className="grid gap-2 sm:grid-cols-2 max-w-lg w-full">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => handleSubmit(prompt)}
                  className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-[12px] text-slate-700 hover:border-blue-300 hover:bg-blue-50/50 transition-colors"
                >
                  <ChevronRight size={12} className="shrink-0 text-blue-400" />
                  {prompt}
                </button>
              ))}
            </div>
            <form
              onSubmit={onSubmit}
              className="mt-2 flex w-full max-w-2xl items-end gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-[0_14px_40px_rgba(15,23,42,0.08)]"
            >
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(input);
                  }
                }}
                rows={2}
                placeholder="Ask about labs, medications, conditions, encounters, or source evidence..."
                className="min-h-[52px] flex-1 resize-none rounded-xl border border-transparent px-3 py-2 text-[13px] text-[#1c1c1e] outline-none focus:border-blue-200 focus:ring-1 focus:ring-blue-100 placeholder:text-slate-400"
              />
              <button
                type="submit"
                disabled={chat.isPending || input.trim().length === 0}
                className="inline-flex h-[38px] shrink-0 items-center gap-1.5 rounded-lg bg-[#5b76fe] px-3 text-[12px] font-semibold text-white transition-colors hover:bg-[#4a65ed] disabled:opacity-50"
              >
                <Send size={13} />
                Send
              </button>
            </form>
          </div>
        )}

        {chat.messages.map((msg) => (
          <ChatMessageBubble
            key={msg.id}
            msg={msg}
            onSubmitFollowUp={handleSubmit}
            onViewContext={setContextModal}
            onSelectToolCall={handleSelectToolLog}
          />
        ))}

        {chat.isPending && (
          <div className="flex gap-2.5">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100">
              <Bot size={12} className="text-blue-600" />
            </div>
            <div className="flex items-center gap-2 text-[12px] text-slate-400">
              <div className="w-3 h-3 border-2 border-slate-300 border-t-blue-500 rounded-full animate-spin" />
              Analyzing chart evidence...
            </div>
          </div>
        )}

        {chat.isError && (
          <div className="flex gap-2.5">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-red-100">
              <AlertTriangle size={12} className="text-red-600" />
            </div>
            <p className="text-[12px] text-red-600">{errorMessage(chat.error)}</p>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input bar */}
      {showBottomComposer && (
      <div className="shrink-0 border-t border-slate-200 pt-3">
        <form onSubmit={onSubmit} className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(input);
              }
            }}
            rows={1}
            placeholder={hasPatient ? "Ask about this patient's chart..." : "Select a patient to ask chart-grounded questions..."}
            disabled={!hasPatient}
            className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-[13px] text-[#1c1c1e] outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100 placeholder:text-slate-400"
            style={{ minHeight: 38, maxHeight: 120 }}
          />
          <button
            type="submit"
            disabled={!hasPatient || chat.isPending || input.trim().length === 0}
            className="inline-flex h-[38px] items-center gap-1.5 rounded-lg bg-[#5b76fe] px-3 text-[12px] font-semibold text-white disabled:opacity-50 hover:bg-[#4a65ed] transition-colors"
          >
            <Send size={13} />
            Send
          </button>
        </form>
      </div>
      )}
      </div>

      <SessionContextPanel
        openTab={sessionPanelTab}
        onTabChange={setSessionPanelTab}
        activePackages={chat.contextPackages}
        onTogglePackage={chat.toggleContextPackage}
        messages={chat.messages}
        selectedToolLog={selectedToolLog}
        onSelectToolLog={handleSelectToolLog}
        stance={chat.stance}
        setStance={chat.setStance}
        settings={chat.agentSettings}
        onUpdateSettings={chat.setAgentSettings}
        onResetChat={chat.resetChat}
      />
    </div>
  );
}
