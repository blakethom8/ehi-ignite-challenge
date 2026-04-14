import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import axios from "axios";
import { AlertTriangle, Bot, ChevronDown, ChevronRight, Database, Eye, MessageSquare, Search, Send, Sparkles, Terminal, User } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type {
  ProviderAssistantCitation,
  ProviderAssistantResponse,
  ProviderAssistantTurn,
  TraceDetail,
  ToolCallDetail,
} from "../../types";

// ── Types ────────────────────────────────────────────────────────────────────

type ChatMessage =
  | { id: string; role: "user"; content: string }
  | {
      id: string;
      role: "assistant";
      content: string;
      confidence: ProviderAssistantResponse["confidence"];
      engine: ProviderAssistantResponse["engine"];
      citations: ProviderAssistantCitation[];
      followUps: string[];
      trace: TraceDetail | null;
    };

const STARTER_PROMPTS = [
  "Is this patient safe for surgery this week?",
  "Any active blood thinner or interaction risk?",
  "What changed recently that affects peri-op risk?",
  "Summarize the active problem list.",
];

// ── Helpers ──────────────────────────────────────────────────────────────────

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
  const [expanded, setExpanded] = useState(!!tc.error); // auto-expand errors
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
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl w-[90vw] max-w-4xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-5 py-3 border-b border-slate-200">
          <div>
            <h2 className="text-sm font-semibold text-[#1c1c1e]">Agent Context &amp; Execution Trace</h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Trace {trace.trace_id.slice(0, 8)}
              {trace.duration_ms != null && ` · ${(trace.duration_ms / 1000).toFixed(1)}s`}
              {trace.input_tokens > 0 && ` · ${trace.input_tokens.toLocaleString()} input tokens`}
              {trace.output_tokens > 0 && ` · ${trace.output_tokens.toLocaleString()} output tokens`}
              {trace.total_cost_usd != null && ` · $${trace.total_cost_usd.toFixed(4)}`}
            </p>
          </div>
          <button onClick={onClose} className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors">
            ✕
          </button>
        </div>

        {/* Body — two columns */}
        <div className="flex-1 overflow-hidden flex min-h-0">
          {/* Left: Tool calls + retrieved facts */}
          <div className="w-1/2 border-r border-slate-200 overflow-y-auto p-4 space-y-4">
            {/* Tool calls */}
            {trace.tool_calls.length > 0 && (
              <div>
                <h3 className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
                  Tool Calls ({trace.tool_calls.length})
                </h3>
                <div className="space-y-2">
                  {trace.tool_calls.map((tc, i) => (
                    <div key={i} className={`rounded-lg border p-3 text-[11px] ${tc.error ? "border-red-200 bg-red-50" : "border-slate-200 bg-white"}`}>
                      <div className="flex items-center gap-1.5 mb-1.5">
                        {TOOL_ICONS[tc.tool_name] || <Terminal size={10} />}
                        <span className="font-semibold text-slate-800">{tc.tool_name}</span>
                        {tc.duration_ms != null && (
                          <span className="ml-auto text-[9px] text-slate-400">{tc.duration_ms.toFixed(0)}ms</span>
                        )}
                      </div>
                      {tc.input_summary && (
                        <div className="mb-1.5">
                          <span className="text-[9px] font-semibold uppercase text-slate-400">Input</span>
                          <pre className="whitespace-pre-wrap text-[10px] text-slate-700 font-mono bg-slate-50 rounded px-2 py-1 mt-0.5 max-h-48 overflow-y-auto">
                            {tc.input_summary}
                          </pre>
                        </div>
                      )}
                      <div>
                        <span className="text-[9px] font-semibold uppercase text-slate-400">Result</span>
                        <p className={`text-[10px] mt-0.5 ${tc.error ? "text-red-600 font-medium" : "text-slate-700"}`}>
                          {tc.error ? `Error: ${tc.error}` : tc.output_summary}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Retrieved facts — the actual data used */}
            {trace.retrieved_facts.length > 0 && (
              <div>
                <h3 className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
                  Retrieved Facts ({trace.retrieved_facts.length})
                </h3>
                <div className="space-y-1">
                  {trace.retrieved_facts.map((fact, i) => (
                    <div key={i} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-700 leading-relaxed">
                      <span className="text-[9px] font-semibold text-blue-500 mr-1.5">F{i + 1}</span>
                      {fact}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right: System prompt / context */}
          <div className="w-1/2 overflow-y-auto p-4">
            <h3 className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
              Agent Context / System Prompt
            </h3>
            {trace.system_prompt_preview ? (
              <pre className="whitespace-pre-wrap text-[10px] leading-relaxed text-slate-700 font-mono bg-slate-50 rounded-lg p-3">
                {trace.system_prompt_preview}
              </pre>
            ) : (
              <p className="text-[11px] text-slate-400">No system prompt captured for this request.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Component ────────────────────────────────────────────────────────────────

export function ExplorerAssistant() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const [input, setInput] = useState("");
  const [stance, setStance] = useState<"opinionated" | "balanced">("opinionated");
  const [messagesByPatient, setMessagesByPatient] = useState<Record<string, ChatMessage[]>>({});
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [contextModal, setContextModal] = useState<TraceDetail | null>(null);

  const messages = useMemo(() => {
    if (!patientId) return [];
    return messagesByPatient[patientId] ?? [];
  }, [messagesByPatient, patientId]);

  const { data: overview } = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });

  const mutation = useMutation({
    mutationFn: async (payload: {
      patientId: string;
      question: string;
      history: ProviderAssistantTurn[];
      stance: "opinionated" | "balanced";
    }) => {
      return api.chatProviderAssistant({
        patient_id: payload.patientId,
        question: payload.question,
        history: payload.history,
        stance: payload.stance,
      });
    },
    onSuccess: (data, variables) => {
      setMessagesByPatient((prev) => {
        const current = prev[variables.patientId] ?? [];
        return {
          ...prev,
          [variables.patientId]: [
            ...current,
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content: data.answer,
              confidence: data.confidence,
              engine: data.engine,
              citations: data.citations,
              followUps: data.follow_ups,
              trace: data.trace,
            },
          ],
        };
      });
    },
  });

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, mutation.isPending]);

  const lastFollowUps = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return (messages[i] as Extract<ChatMessage, { role: "assistant" }>).followUps;
    }
    return [];
  }, [messages]);

  function submitQuestion(rawQuestion: string) {
    if (!patientId) return;
    const question = rawQuestion.trim();
    if (!question || mutation.isPending) return;

    const history: ProviderAssistantTurn[] = messages.map((m) => ({ role: m.role, content: m.content }));

    setMessagesByPatient((prev) => ({
      ...prev,
      [patientId]: [...(prev[patientId] ?? []), { id: crypto.randomUUID(), role: "user", content: question }],
    }));
    setInput("");
    mutation.mutate({ patientId, question, history, stance });
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    submitQuestion(input);
  }

  // ── No patient ─────────────────────────────────────────────────────────
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

  const hasMessages = messages.length > 0;

  return (
    <div className="flex h-full flex-col">
      {/* Context modal */}
      {contextModal && <ContextModal trace={contextModal} onClose={() => setContextModal(null)} />}

      {/* ── Header bar ──────────────────────────────────────────────── */}
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

        {/* Stance toggle */}
        <div className="flex items-center gap-1 text-[11px]">
          <span className="text-slate-400 mr-1">Style</span>
          {(["opinionated", "balanced"] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStance(s)}
              className={`rounded-full px-2.5 py-1 font-medium transition-colors ${
                stance === s ? "bg-blue-100 text-blue-700" : "text-slate-500 hover:bg-slate-100"
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* ── Chat area ───────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto min-h-0 py-3 space-y-3">
        {/* Welcome state — show starter prompts */}
        {!hasMessages && !mutation.isPending && (
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
                  onClick={() => submitQuestion(prompt)}
                  className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-[12px] text-slate-700 hover:border-blue-300 hover:bg-blue-50/50 transition-colors"
                >
                  <ChevronRight size={12} className="shrink-0 text-blue-400" />
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-2.5 ${msg.role === "user" ? "" : ""}`}>
            {/* Avatar */}
            <div className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
              msg.role === "user" ? "bg-slate-200" : "bg-blue-100"
            }`}>
              {msg.role === "user" ? <User size={12} className="text-slate-600" /> : <Bot size={12} className="text-blue-600" />}
            </div>

            <div className="flex-1 min-w-0">
              {/* User message */}
              {msg.role === "user" && (
                <p className="text-[13px] font-medium text-[#1c1c1e] leading-relaxed">{msg.content}</p>
              )}

              {/* Assistant message */}
              {msg.role === "assistant" && (
                <div className="space-y-2">
                  {/* Tool calls — show what the agent did */}
                  {msg.trace && msg.trace.tool_calls.length > 0 && (
                    <ToolCallsSection trace={msg.trace} />
                  )}

                  <pre className="whitespace-pre-wrap text-[13px] leading-relaxed text-[#1c1c1e] font-sans">{msg.content}</pre>

                  {/* Meta badges */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {confidenceBadge(msg.confidence)}
                    <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                      {msg.engine}
                    </span>
                    {msg.trace && (
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
                    {msg.trace && (
                      <button
                        onClick={() => setContextModal(msg.trace)}
                        className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-600 hover:bg-blue-100 transition-colors"
                      >
                        <Eye size={10} />
                        View Full Context
                      </button>
                    )}
                  </div>

                  {/* Citations */}
                  {msg.citations.length > 0 && (
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

                  {/* Context — what the agent had access to */}
                  {msg.trace && msg.trace.system_prompt_preview && (
                    <ExpandableSection title="Agent Context" icon={<Eye size={10} />} defaultOpen={false}>
                      <pre className="whitespace-pre-wrap text-[10px] leading-relaxed text-slate-600 font-mono bg-white rounded p-2 max-h-60 overflow-y-auto">
                        {msg.trace.system_prompt_preview}
                      </pre>
                    </ExpandableSection>
                  )}

                  {/* Follow-up prompts — inline */}
                  {msg.followUps.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap">
                      {msg.followUps.map((fu) => (
                        <button
                          key={fu}
                          onClick={() => submitQuestion(fu)}
                          className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600 hover:border-blue-300 hover:text-blue-700 transition-colors"
                        >
                          <ChevronRight size={10} className="text-blue-400" />
                          {fu.length > 60 ? fu.slice(0, 57) + "..." : fu}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading */}
        {mutation.isPending && (
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

        {/* Error */}
        {mutation.isError && (
          <div className="flex gap-2.5">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-red-100">
              <AlertTriangle size={12} className="text-red-600" />
            </div>
            <p className="text-[12px] text-red-600">{errorMessage(mutation.error)}</p>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* ── Input bar (pinned to bottom) ────────────────────────────── */}
      <div className="shrink-0 border-t border-slate-200 pt-3">
        <form onSubmit={onSubmit} className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submitQuestion(input);
              }
            }}
            rows={1}
            placeholder="Ask about this patient's chart..."
            className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-[13px] text-[#1c1c1e] outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100 placeholder:text-slate-400"
            style={{ minHeight: 38, maxHeight: 120 }}
          />
          <button
            type="submit"
            disabled={mutation.isPending || input.trim().length === 0}
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
