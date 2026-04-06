import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import axios from "axios";
import { AlertTriangle, Bot, MessageSquare, Send, Shield, User } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";
import type {
  ProviderAssistantCitation,
  ProviderAssistantResponse,
  ProviderAssistantTurn,
} from "../../types";

type ChatMessage =
  | {
      id: string;
      role: "user";
      content: string;
    }
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
  "Is this patient safe to proceed this week? What are the top blockers?",
  "Any active blood thinner or interaction risk I need to resolve pre-op?",
  "What changed in the last 6 months that affects peri-op risk?",
  "Push back on my plan if the chart evidence is weak.",
];

function fmt(dt: string | null): string {
  if (!dt) return "date not provided";
  return new Date(dt).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function confidenceStyle(level: ProviderAssistantResponse["confidence"]): string {
  if (level === "high") return "bg-[#dcfce7] text-[#166534]";
  if (level === "medium") return "bg-[#fef3c7] text-[#92400e]";
  return "bg-[#fee2e2] text-[#991b1b]";
}

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim().length > 0) {
      return detail;
    }
    if (typeof error.message === "string" && error.message.trim().length > 0) {
      return error.message;
    }
  }
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  return "Assistant request failed. Try again.";
}

export function ExplorerAssistant() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const [input, setInput] = useState("");
  const [stance, setStance] = useState<"opinionated" | "balanced">("opinionated");
  const [messagesByPatient, setMessagesByPatient] = useState<Record<string, ChatMessage[]>>({});

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

  const lastAssistantFollowUps = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const message = messages[i];
      if (message.role === "assistant") {
        return message.followUps;
      }
    }
    return [] as string[];
  }, [messages]);

  function submitQuestion(rawQuestion: string) {
    if (!patientId) return;
    const question = rawQuestion.trim();
    if (!question || mutation.isPending) return;

    const history: ProviderAssistantTurn[] = messages.map((message) => ({
      role: message.role,
      content: message.content,
    }));

    setMessagesByPatient((prev) => {
      const current = prev[patientId] ?? [];
      return {
        ...prev,
        [patientId]: [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "user",
            content: question,
          },
        ],
      };
    });
    setInput("");
    mutation.mutate({ patientId, question, history, stance });
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitQuestion(input);
  }

  if (!patientId) {
    return (
      <EmptyState
        icon={MessageSquare}
        title="Choose a patient to start Provider Assistant"
        bullets={[
          "Ask direct clinical questions about chart history and risk",
          "Receive concise answers with citations and confidence",
          "Assistant will push back when evidence is weak",
        ]}
        stat="1,180 patients available"
      />
    );
  }

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col px-6 py-6 lg:px-8">
      <section className="rounded-2xl border border-[#d9e3f7] bg-[linear-gradient(130deg,#f8fbff_0%,#edf4ff_55%,#f8fbff_100%)] p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full bg-[#e7efff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#1e40af]">
              <Bot size={13} />
              Provider Assistant
            </p>
            <h1 className="mt-2 text-2xl font-semibold text-[#0f172a]">Direct chart Q&A with evidence</h1>
            <p className="mt-1 text-sm text-[#334155]">
              {overview?.name ?? "Patient"} · asks and answers are chart-grounded, concise, and intentionally opinionated when risk is present.
            </p>
          </div>

          <div className="rounded-xl bg-white p-3 shadow-[rgb(217_227_247)_0px_0px_0px_1px]">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#475569]">Response style</p>
            <div className="mt-2 flex gap-2">
              <button
                onClick={() => setStance("opinionated")}
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  stance === "opinionated" ? "bg-[#dbeafe] text-[#1d4ed8]" : "bg-[#f1f5f9] text-[#64748b]"
                }`}
              >
                Opinionated
              </button>
              <button
                onClick={() => setStance("balanced")}
                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  stance === "balanced" ? "bg-[#dbeafe] text-[#1d4ed8]" : "bg-[#f1f5f9] text-[#64748b]"
                }`}
              >
                Balanced
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-4 grid gap-3 sm:grid-cols-2">
        {STARTER_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => submitQuestion(prompt)}
            className="rounded-xl border border-[#e2e8f0] bg-white px-3 py-2 text-left text-sm text-[#334155] hover:border-[#93c5fd] hover:bg-[#f8fbff]"
          >
            {prompt}
          </button>
        ))}
      </section>

      <section className="mt-4 flex-1 overflow-hidden rounded-2xl border border-[#e2e8f0] bg-white">
        <div className="h-full overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="rounded-xl border border-[#dbeafe] bg-[#eff6ff] p-4 text-sm text-[#1e3a8a]">
              Ask a focused question. The assistant will answer directly, cite chart evidence, and challenge unsafe assumptions.
            </div>
          )}

          <div className="space-y-4">
            {messages.map((message) => (
              <article key={message.id} className="space-y-2">
                <div className="flex items-start gap-2">
                  <div
                    className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
                      message.role === "user" ? "bg-[#dbeafe]" : "bg-[#dcfce7]"
                    }`}
                  >
                    {message.role === "user" ? (
                      <User size={14} className="text-[#1d4ed8]" />
                    ) : (
                      <Bot size={14} className="text-[#166534]" />
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold uppercase tracking-wider text-[#64748b]">
                      {message.role === "user" ? "Provider" : "Assistant"}
                    </p>
                    <pre className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[#0f172a] font-sans">{message.content}</pre>
                  </div>
                </div>

                {message.role === "assistant" && (
                  <>
                    <div className="ml-9 flex items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${confidenceStyle(message.confidence)}`}>
                        confidence: {message.confidence}
                      </span>
                      <span className="rounded-full bg-[#e2e8f0] px-2 py-0.5 text-[10px] font-semibold uppercase text-[#334155]">
                        engine: {message.engine}
                      </span>
                      {message.citations.length > 0 && (
                        <span className="text-xs text-[#64748b]">{message.citations.length} citation(s)</span>
                      )}
                    </div>

                    {message.citations.length > 0 && (
                      <div className="ml-9 space-y-2 rounded-xl border border-[#e2e8f0] bg-[#f8fafc] p-3">
                        <p className="text-xs font-semibold uppercase tracking-wider text-[#64748b]">Evidence</p>
                        {message.citations.map((citation) => (
                          <div key={`${citation.source_type}:${citation.resource_id}`} className="rounded-lg bg-white px-3 py-2">
                            <p className="text-sm font-medium text-[#0f172a]">{citation.label}</p>
                            <p className="text-xs text-[#64748b]">
                              {citation.source_type} · {citation.resource_id} · {fmt(citation.event_date)}
                            </p>
                            <p className="mt-1 text-xs text-[#334155]">{citation.detail}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </article>
            ))}

            {mutation.isPending && (
              <div className="ml-9 inline-flex items-center gap-2 rounded-lg bg-[#f8fafc] px-3 py-2 text-sm text-[#64748b]">
                <Bot size={14} />
                Thinking through chart evidence...
              </div>
            )}

            {mutation.isError && (
              <div className="ml-9 inline-flex items-center gap-2 rounded-lg bg-[#fef2f2] px-3 py-2 text-sm text-[#991b1b]">
                <AlertTriangle size={14} />
                {errorMessage(mutation.error)}
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="mt-4 grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
        <form onSubmit={onSubmit} className="rounded-2xl border border-[#e2e8f0] bg-white p-3">
          <label className="text-xs font-semibold uppercase tracking-wider text-[#64748b]">Ask provider assistant</label>
          <div className="mt-2 flex items-end gap-2">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              rows={3}
              placeholder="Example: Is there any active anticoagulant risk, and what would you block on first?"
              className="min-h-[78px] flex-1 resize-none rounded-xl border border-[#e2e8f0] px-3 py-2 text-sm text-[#0f172a] outline-none focus:border-[#93c5fd]"
            />
            <button
              type="submit"
              disabled={mutation.isPending || input.trim().length === 0}
              className="inline-flex h-10 items-center gap-1 rounded-xl bg-[#2563eb] px-3 text-sm font-semibold text-white disabled:opacity-60"
            >
              <Send size={14} />
              Send
            </button>
          </div>
        </form>

        <article className="rounded-2xl border border-[#dcfce7] bg-[#f0fdf4] p-3">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#166534]">
            <Shield size={14} />
            Follow-up prompts
          </p>
          <div className="mt-2 space-y-2">
            {lastAssistantFollowUps.length === 0 && (
              <p className="text-sm text-[#166534]">Ask your first question to generate targeted follow-ups.</p>
            )}
            {lastAssistantFollowUps.map((prompt) => (
              <button
                key={prompt}
                onClick={() => setInput(prompt)}
                className="w-full rounded-lg bg-white px-2.5 py-2 text-left text-sm text-[#14532d] hover:bg-[#f8fffb]"
              >
                {prompt}
              </button>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
