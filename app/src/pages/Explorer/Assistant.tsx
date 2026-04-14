import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import axios from "axios";
import { AlertTriangle, Bot, ChevronRight, MessageSquare, Send, Sparkles, User } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type {
  ProviderAssistantCitation,
  ProviderAssistantResponse,
  ProviderAssistantTurn,
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

// ── Component ────────────────────────────────────────────────────────────────

export function ExplorerAssistant() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const [input, setInput] = useState("");
  const [stance, setStance] = useState<"opinionated" | "balanced">("opinionated");
  const [messagesByPatient, setMessagesByPatient] = useState<Record<string, ChatMessage[]>>({});
  const chatEndRef = useRef<HTMLDivElement>(null);

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
                  <pre className="whitespace-pre-wrap text-[13px] leading-relaxed text-[#1c1c1e] font-sans">{msg.content}</pre>

                  {/* Meta badges */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {confidenceBadge(msg.confidence)}
                    <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                      {msg.engine}
                    </span>
                    {msg.citations.length > 0 && (
                      <span className="text-[10px] text-slate-400">{msg.citations.length} citations</span>
                    )}
                  </div>

                  {/* Citations */}
                  {msg.citations.length > 0 && (
                    <div className="space-y-1 rounded-lg border border-slate-200 bg-slate-50 p-2">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Evidence</p>
                      {msg.citations.map((c) => (
                        <div key={`${c.source_type}:${c.resource_id}`} className="rounded bg-white px-2 py-1.5 text-[11px]">
                          <span className="font-medium text-[#1c1c1e]">{c.label}</span>
                          {c.event_date && <span className="text-slate-400 ml-1">· {fmt(c.event_date)}</span>}
                          <p className="text-slate-600 mt-0.5">{c.detail}</p>
                        </div>
                      ))}
                    </div>
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
