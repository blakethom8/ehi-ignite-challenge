import { useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  AlertTriangle,
  ArrowUp,
  Bot,
  CheckCircle2,
  FileText,
  GitBranch,
  Loader2,
  RotateCcw,
  Sparkles,
  User,
  XCircle,
} from "lucide-react";
import { CitationChip } from "./CitationChip";
import { CaspianAgentSettingsPopover } from "./CaspianAgentSettingsPopover";
import type { CaspianAssistantMessage, LiveToolCall } from "./useCaspianAssistantSession";
import type { AgentSettings } from "../../context/ChatContext";

type CaspianChatPaneProps = {
  patientId: string | null;
  sessionTitle: string;
  messages: CaspianAssistantMessage[];
  isPending: boolean;
  error: unknown;
  activeCitationId: string | null;
  onSubmit: (question: string) => void;
  onReset: () => void;
  onCitationClick: (id: string) => void;
  onOpenTrace: () => void;
  /** Open a workspace file path in the workbench (file chip click). */
  onOpenFile?: (path: string) => void;
  /** Caspian agent settings (mode/model/maxTokens). */
  agentSettings?: AgentSettings;
  onUpdateAgentSettings?: (next: AgentSettings) => void;
  /** Live tool-call events for the in-flight agent turn (empty between turns). */
  liveToolCalls?: LiveToolCall[];
};

const TOOL_LABELS: Record<string, string> = {
  baseline_evidence: "Building baseline chart evidence",
  get_patient_snapshot: "Pulling patient safety snapshot",
  query_chart_evidence: "Querying chart evidence",
  run_sql: "Running SQL over the chart",
};

function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? tool;
}

function ToolCallIcon({ status }: { status: LiveToolCall["status"] }) {
  if (status === "running") {
    return <Loader2 className="mt-0.5 h-3 w-3 animate-spin text-[var(--action)]" strokeWidth={1.5} />;
  }
  if (status === "error") {
    return <XCircle className="mt-0.5 h-3 w-3 text-red-500" strokeWidth={1.5} />;
  }
  return <CheckCircle2 className="mt-0.5 h-3 w-3 text-emerald-500" strokeWidth={1.5} />;
}

const STARTER_PROMPTS = [
  "What should I review first in this chart?",
  "Summarize active problems and medications.",
  "Are there any pre-op medication risks?",
];

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return "Request failed. Try again.";
}

function timeLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

function MessageBubble({
  message,
  activeCitationId,
  onSubmit,
  onCitationClick,
  onOpenTrace,
  onOpenFile,
}: {
  message: CaspianAssistantMessage;
  activeCitationId: string | null;
  onSubmit: (question: string) => void;
  onCitationClick: (id: string) => void;
  onOpenTrace: () => void;
  onOpenFile?: (path: string) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="mb-5 ml-auto max-w-[720px]">
        <div className="grid grid-cols-[28px_1fr] gap-3">
          <div className="grid h-[26px] w-[26px] place-items-center rounded-md bg-slate-200">
            <User className="h-3.5 w-3.5 text-slate-600" strokeWidth={1.5} />
          </div>
          <div>
            <div className="mb-1.5 text-[11.5px] font-semibold text-[var(--ink-3)]">
              Clinician <span className="font-normal text-[var(--ink-4)]">· {timeLabel(message.createdAt)}</span>
            </div>
            <div
              className="rounded-[14px_14px_4px_14px] border px-4 py-3 text-[13px] leading-relaxed"
              style={{
                background: "var(--surface-3)",
                borderColor: "var(--line-1)",
                color: "var(--ink-1)",
              }}
            >
              {message.content}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-5 grid max-w-[760px] grid-cols-[28px_1fr] gap-3">
      <div className="grid h-[26px] w-[26px] place-items-center rounded-md bg-[var(--action-tint)] text-[var(--action)]">
        <Bot className="h-3.5 w-3.5" strokeWidth={1.5} />
      </div>
      <div>
        <div className="mb-1.5 flex flex-wrap items-center gap-1.5 text-[11.5px] font-semibold text-[var(--ink-3)]">
          Caspian
          <span className="font-normal text-[var(--ink-4)]">· {timeLabel(message.createdAt)}</span>
          <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
            {message.engine}
          </span>
          <span className="rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
            {message.confidence}
          </span>
          {message.trace && (
            <button
              onClick={onOpenTrace}
              className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700 transition-colors hover:bg-blue-100"
            >
              <GitBranch className="h-2.5 w-2.5" strokeWidth={1.5} />
              {message.trace.tool_calls.length} tool calls
            </button>
          )}
        </div>
        <div
          className="space-y-2 text-[14px] leading-[1.62]"
          style={{
            fontFamily: "var(--font-serif)",
            color: "var(--ink-1)",
            letterSpacing: "-0.005em",
            whiteSpace: "pre-wrap",
          }}
        >
          {message.content}
        </div>
        {message.citations.length > 0 && (
          <div className="mt-3">
            <div className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-[var(--ink-4)]">
              Evidence
            </div>
            <div className="flex flex-wrap gap-1.5">
              {message.citations.map((citation) => (
                <CitationChip
                  key={citation.id}
                  id={citation.id}
                  kind="citation"
                  active={activeCitationId === citation.id}
                  onClick={onCitationClick}
                />
              ))}
            </div>
          </div>
        )}
        {message.filesCreated && message.filesCreated.length > 0 && (
          <div className="mt-3">
            <div className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-[var(--ink-4)]">
              Files created
            </div>
            <div className="flex flex-wrap gap-1.5">
              {message.filesCreated.map((path) => (
                <button
                  key={path}
                  onClick={() => onOpenFile?.(path)}
                  className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11.5px] transition-colors hover:bg-[var(--action-tint)]"
                  style={{
                    background: "var(--surface-0)",
                    borderColor: "var(--line-1)",
                    color: "var(--action)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  <FileText className="h-3 w-3" strokeWidth={1.5} />
                  {path}
                </button>
              ))}
            </div>
          </div>
        )}
        {message.followUps.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {message.followUps.map((followUp) => (
              <button
                key={followUp}
                onClick={() => onSubmit(followUp)}
                className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600 transition-colors hover:border-blue-300 hover:text-blue-700"
              >
                <Sparkles className="h-2.5 w-2.5 text-blue-400" strokeWidth={1.5} />
                {followUp.length > 72 ? `${followUp.slice(0, 69)}...` : followUp}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function CaspianChatPane({
  patientId,
  sessionTitle,
  messages,
  isPending,
  error,
  activeCitationId,
  onSubmit,
  onReset,
  onCitationClick,
  onOpenTrace,
  onOpenFile,
  agentSettings,
  onUpdateAgentSettings,
  liveToolCalls = [],
}: CaspianChatPaneProps) {
  const [text, setText] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length, isPending]);

  const disabled = !patientId || isPending;

  const submit = () => {
    if (!text.trim() || disabled) return;
    onSubmit(text.trim());
    setText("");
  };

  return (
    <section
      className="grid h-full min-h-0 grid-rows-[auto_1fr_auto] overflow-hidden"
      style={{
        background: "var(--surface-1)",
        borderRight: "1px solid var(--line-1)",
      }}
    >
      <div
        className="flex items-center gap-2.5 border-b px-3.5 py-2.5"
        style={{ borderColor: "var(--line-1)", background: "var(--surface-1)" }}
      >
        <div className="min-w-0">
          <div className="text-[12px] font-semibold text-[var(--ink-2)]">
            Clinical chat
            <small className="ml-2 font-medium text-[var(--ink-4)]">{sessionTitle}</small>
          </div>
          <div className="text-[10.5px] text-[var(--ink-4)]">
            {patientId ? `Patient ${patientId}` : "Choose a patient to start reviewing a chart in Caspian."}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          {agentSettings && onUpdateAgentSettings && (
            <CaspianAgentSettingsPopover
              settings={agentSettings}
              onUpdate={onUpdateAgentSettings}
            />
          )}
          <button
            onClick={onReset}
            className="inline-flex items-center gap-1 rounded border px-2.5 py-1 text-[11px] font-medium hover:bg-[var(--surface-2)]"
            style={{
              background: "var(--surface-1)",
              borderColor: "var(--line-2)",
              color: "var(--ink-1)",
            }}
          >
            <RotateCcw className="h-2.5 w-2.5" strokeWidth={1.5} />
            Reset
          </button>
        </div>
      </div>
      <div ref={scrollRef} className="overflow-y-auto px-6 py-4 pb-2">
        {!patientId && (
          <div
            className="mb-4 rounded-[10px] border px-3.5 py-3 text-[12.5px]"
            style={{ background: "rgba(180,83,9,0.04)", borderColor: "rgba(180,83,9,0.24)", color: "var(--ink-1)" }}
          >
            Choose a patient before starting a Caspian conversation.
          </div>
        )}
        {Boolean(error) && (
          <div
            className="mb-4 grid grid-cols-[16px_1fr] gap-2 rounded-[10px] border px-3.5 py-3 text-[12.5px]"
            style={{ background: "rgba(220,38,38,0.05)", borderColor: "rgba(220,38,38,0.24)", color: "var(--ink-1)" }}
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 text-red-600" strokeWidth={1.5} />
            <div>{errorMessage(error)}</div>
          </div>
        )}
        {messages.length === 0 && patientId && (
          <div className="mb-6 rounded-[10px] border px-4 py-4" style={{ background: "var(--surface-0)", borderColor: "var(--line-1)" }}>
            <div className="mb-2 text-[12.5px] font-semibold text-[var(--ink-1)]">Start a chart review</div>
            <div className="mb-3 text-[12px] leading-[1.55] text-[var(--ink-3)]">
              Ask a direct question about the chart or begin with one of these prompts.
            </div>
            <div className="flex flex-wrap gap-1.5">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => onSubmit(prompt)}
                  className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600 transition-colors hover:border-blue-300 hover:text-blue-700"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            activeCitationId={activeCitationId}
            onSubmit={onSubmit}
            onCitationClick={onCitationClick}
            onOpenTrace={onOpenTrace}
            onOpenFile={onOpenFile}
          />
        ))}
        {isPending && (
          <div className="grid max-w-[760px] grid-cols-[28px_1fr] gap-3">
            <div className="grid h-[26px] w-[26px] place-items-center rounded-md bg-[var(--action-tint)] text-[var(--action)]">
              <Bot className="h-3.5 w-3.5" strokeWidth={1.5} />
            </div>
            <div
              className="rounded-[14px] border px-4 py-3"
              style={{ borderColor: "var(--line-1)", background: "var(--surface-0)" }}
            >
              <div className="flex items-center gap-2 text-[13px] font-medium text-[var(--ink-2)]">
                <span className="inline-flex gap-1">
                  <span
                    className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--action)]"
                    style={{ animationDelay: "0ms" }}
                  />
                  <span
                    className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--action)]"
                    style={{ animationDelay: "150ms" }}
                  />
                  <span
                    className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--action)]"
                    style={{ animationDelay: "300ms" }}
                  />
                </span>
                {liveToolCalls.length === 0
                  ? "Thinking across the chart…"
                  : "Working across the chart…"}
              </div>
              <div className="mt-1 text-[11.5px] leading-[1.5] text-[var(--ink-4)]">
                Pulling evidence, weighing risk, and assembling citations for the next answer.
              </div>
              {liveToolCalls.length > 0 ? (
                <ul className="mt-3 space-y-1.5">
                  {liveToolCalls.map((call) => (
                    <li
                      key={call.id}
                      className="grid grid-cols-[14px_1fr_auto] items-start gap-2 rounded-md border px-2.5 py-1.5 text-[11.5px]"
                      style={{
                        background: "var(--surface-1)",
                        borderColor: "var(--line-1)",
                        color: "var(--ink-2)",
                      }}
                    >
                      <ToolCallIcon status={call.status} />
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-baseline gap-1.5">
                          <span className="font-medium text-[var(--ink-1)]">
                            {toolLabel(call.tool)}
                          </span>
                          <span
                            className="text-[10.5px]"
                            style={{ color: "var(--ink-4)", fontFamily: "var(--font-mono)" }}
                          >
                            {call.tool}
                          </span>
                        </div>
                        <div
                          className="mt-0.5 truncate text-[11px]"
                          style={{ color: "var(--ink-3)" }}
                        >
                          {call.status === "running"
                            ? call.input_summary
                            : call.output_summary || call.input_summary}
                        </div>
                      </div>
                      <span
                        className="text-[10.5px]"
                        style={{ color: "var(--ink-4)", fontFamily: "var(--font-mono)" }}
                      >
                        {call.status === "running"
                          ? "…"
                          : call.duration_ms != null
                            ? `${Math.max(1, Math.round(call.duration_ms))}ms`
                            : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="mt-3 space-y-1.5">
                  <div className="h-2.5 w-[72%] animate-pulse rounded-full bg-[var(--surface-2)]" />
                  <div className="h-2.5 w-[58%] animate-pulse rounded-full bg-[var(--surface-2)]" />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
      <div
        className="border-t px-4 py-3"
        style={{
          borderColor: "var(--line-1)",
          background: "var(--surface-1)",
        }}
      >
        <div
          className="grid gap-2 rounded-xl border p-3 transition-colors focus-within:border-[var(--action)]"
          style={{
            background: "var(--surface-0)",
            borderColor: "var(--line-2)",
            gridTemplateRows: "1fr auto",
          }}
        >
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder={patientId ? "Ask about the chart, evidence, risk, or next action…" : "Select a patient to start"}
            rows={2}
            disabled={disabled}
            className="resize-none border-0 bg-transparent text-[13px] leading-relaxed outline-none disabled:cursor-not-allowed"
            style={{ color: "var(--ink-1)" }}
          />
          <div className="flex items-center gap-1.5">
            <span
              className="rounded border px-1.5 text-[10.5px]"
              style={{
                background: "var(--surface-2)",
                borderColor: "var(--line-1)",
                color: "var(--ink-3)",
                fontFamily: "var(--font-mono)",
              }}
            >
              ↵ to send
            </span>
            <div className="flex-1" />
            <button
              onClick={submit}
              disabled={!text.trim() || disabled}
              className="grid h-[26px] w-[26px] place-items-center rounded-md text-white transition-colors disabled:cursor-default"
              style={{
                background: text.trim() && !disabled ? "var(--ink-1)" : "var(--ink-5)",
              }}
            >
              <ArrowUp className="h-3 w-3" strokeWidth={1.5} />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
