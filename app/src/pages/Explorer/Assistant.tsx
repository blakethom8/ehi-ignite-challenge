import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { AlertTriangle, Bot, ChevronDown, ChevronRight, Database, Eye, MessageSquare, Search, Send, Sparkles, Terminal, User } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import { AgentSettingsPanel } from "../../components/AgentSettingsPanel";
import { useChatForPatient } from "../../context/ChatContext";
import type { ChatMessage } from "../../context/ChatContext";
import type {
  ProviderAssistantResponse,
  TraceDetail,
  ToolCallDetail,
} from "../../types";

// ── Helpers ──────────────────────────────────────────────────────────────────

const STARTER_PROMPTS = [
  "Is this patient safe for surgery this week?",
  "Any active blood thinner or interaction risk?",
  "What changed recently that affects peri-op risk?",
  "Summarize the active problem list.",
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

function ToolCallsSection({ trace }: { trace: TraceDetail }) {
  return (
    <div className="space-y-1">
      {trace.tool_calls.map((tc, i) => (
        <ToolCallCard key={i} tc={tc} />
      ))}
    </div>
  );
}

function ToolCallCard({ tc }: { tc: ToolCallDetail }) {
  const [expanded, setExpanded] = useState(!!tc.error);
  const icon = TOOL_ICONS[tc.tool_name] || <Terminal size={10} className="text-slate-400" />;
  const hasError = !!tc.error;

  return (
    <div className={`rounded-md border text-[11px] ${hasError ? "border-red-200 bg-red-50" : "border-slate-200 bg-slate-50"}`}>
      <button
        onClick={() => setExpanded(!expanded)}
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

// ── Shared message renderer (used by both full page and widget) ──────────────

export function ChatMessageBubble({
  msg,
  onSubmitFollowUp,
  onViewContext,
  compact = false,
}: {
  msg: ChatMessage;
  onSubmitFollowUp: (question: string) => void;
  onViewContext?: (trace: TraceDetail) => void;
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
          <ToolCallsSection trace={msg.trace} />
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

        <pre className={`whitespace-pre-wrap ${compact ? "text-[12px]" : "text-[13px]"} leading-relaxed text-[#1c1c1e] font-sans`}>{msg.content}</pre>

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

  if (!patientId) {
    return (
      <EmptyState
        icon={MessageSquare}
        title="Choose a patient to start"
        bullets={[
          "Ask clinical questions grounded in chart data",
          "Get concise answers with evidence citations",
          "Assistant challenges weak evidence",
        ]}
      />
    );
  }

  const hasMessages = chat.messages.length > 0;

  return (
    <div className="flex h-full flex-col">
      {contextModal && <ContextModal trace={contextModal} onClose={() => setContextModal(null)} />}

      {/* Header bar */}
      <div className="shrink-0 flex items-center justify-between gap-3 pb-3 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100">
            <Sparkles size={14} className="text-blue-600" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-[#1c1c1e]">Provider Assistant</h1>
            <p className="text-[11px] text-slate-500">
              {overview?.name ?? "Patient"} · chart-grounded Q&A
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Stance toggle */}
          <div className="flex items-center gap-1 text-[11px]">
            {(["opinionated", "balanced"] as const).map((s) => (
              <button
                key={s}
                onClick={() => chat.setStance(s)}
                className={`rounded-full px-2.5 py-1 font-medium transition-colors ${
                  chat.stance === s ? "bg-blue-100 text-blue-700" : "text-slate-500 hover:bg-slate-100"
                }`}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
          {/* Agent settings */}
          <AgentSettingsPanel settings={chat.agentSettings} onUpdate={chat.setAgentSettings} />
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto min-h-0 py-3 space-y-3">
        {!hasMessages && !chat.isPending && (
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
          </div>
        )}

        {chat.messages.map((msg) => (
          <ChatMessageBubble
            key={msg.id}
            msg={msg}
            onSubmitFollowUp={handleSubmit}
            onViewContext={setContextModal}
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
            placeholder="Ask about this patient's chart..."
            className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-[13px] text-[#1c1c1e] outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100 placeholder:text-slate-400"
            style={{ minHeight: 38, maxHeight: 120 }}
          />
          <button
            type="submit"
            disabled={chat.isPending || input.trim().length === 0}
            className="inline-flex h-[38px] items-center gap-1.5 rounded-lg bg-[#5b76fe] px-3 text-[12px] font-semibold text-white disabled:opacity-50 hover:bg-[#4a65ed] transition-colors"
          >
            <Send size={13} />
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
