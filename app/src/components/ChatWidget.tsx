import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { Bot, ChevronRight, Maximize2, MessageSquareText, Minus, Send, Sparkles, X } from "lucide-react";
import { useChatForPatient } from "../context/ChatContext";
import { ChatMessageBubble } from "../pages/Explorer/Assistant";

const QUICK_PROMPTS = [
  "Is this patient safe for surgery?",
  "Summarize active problems",
  "Any blood thinner risks?",
];

export function ChatWidget() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const patientId = searchParams.get("patient");
  const chat = useChatForPatient(patientId);

  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Don't render on the full assistant page (avoid double UI)
  const isAssistantPage = location.pathname === "/explorer/assistant";
  // Don't render if no patient selected
  if (!patientId || isAssistantPage) return null;

  const hasMessages = chat.messages.length > 0;
  const lastAssistantMsg = [...chat.messages].reverse().find((m) => m.role === "assistant");

  // Auto-scroll on new messages
  useEffect(() => {
    if (open && !minimized) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [chat.messages.length, chat.isPending, open, minimized]);

  function handleSubmit(question: string) {
    const trimmed = question.trim();
    if (!trimmed || chat.isPending) return;
    chat.submitQuestion(trimmed);
    setInput("");
  }

  function openFullView() {
    const params = new URLSearchParams(searchParams);
    navigate(`/explorer/assistant?${params.toString()}`);
  }

  // ── Closed state: floating bubble ──────────────────────────────────────
  if (!open) {
    return (
      <div className="fixed bottom-5 right-5 z-40 flex flex-col items-end gap-2">
        {/* Unread indicator */}
        {hasMessages && lastAssistantMsg && (
          <div className="max-w-[280px] rounded-xl rounded-br-sm bg-white px-3 py-2 text-[11px] leading-relaxed text-slate-700 shadow-lg ring-1 ring-slate-200">
            <p className="line-clamp-2">{lastAssistantMsg.content}</p>
          </div>
        )}
        <button
          onClick={() => setOpen(true)}
          className="group flex h-12 w-12 items-center justify-center rounded-full bg-[#5b76fe] text-white shadow-lg shadow-blue-200/50 transition-all hover:scale-105 hover:shadow-xl"
          title="Open AI Assistant"
        >
          <MessageSquareText size={22} className="transition-transform group-hover:scale-110" />
          {hasMessages && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white">
              {chat.messages.filter((m) => m.role === "assistant").length}
            </span>
          )}
        </button>
      </div>
    );
  }

  // ── Minimized state: thin bar ──────────────────────────────────────────
  if (minimized) {
    return (
      <div className="fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full bg-[#5b76fe] pl-4 pr-2 py-2 text-white shadow-lg">
        <Sparkles size={14} />
        <span className="text-[12px] font-medium">Assistant</span>
        {chat.isPending && (
          <div className="ml-1 h-3 w-3 rounded-full border-2 border-white/40 border-t-white animate-spin" />
        )}
        <button onClick={() => setMinimized(false)} className="ml-1 rounded-full p-1 hover:bg-white/20 transition-colors">
          <Maximize2 size={13} />
        </button>
        <button onClick={() => { setOpen(false); setMinimized(false); }} className="rounded-full p-1 hover:bg-white/20 transition-colors">
          <X size={13} />
        </button>
      </div>
    );
  }

  // ── Expanded panel ─────────────────────────────────────────────────────
  return (
    <div className="fixed bottom-5 right-5 z-40 flex w-[380px] flex-col rounded-2xl bg-white shadow-2xl ring-1 ring-slate-200" style={{ maxHeight: "min(560px, calc(100vh - 120px))" }}>
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100">
            <Sparkles size={14} className="text-blue-600" />
          </div>
          <div>
            <p className="text-[12px] font-semibold text-[#1c1c1e]">Provider Assistant</p>
            <p className="text-[10px] text-slate-400">Chart-grounded Q&A</p>
          </div>
        </div>
        <div className="flex items-center gap-0.5">
          <button
            onClick={openFullView}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            title="Open full view"
          >
            <Maximize2 size={14} />
          </button>
          <button
            onClick={() => setMinimized(true)}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            title="Minimize"
          >
            <Minus size={14} />
          </button>
          <button
            onClick={() => setOpen(false)}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            title="Close"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
        {!hasMessages && !chat.isPending && (
          <div className="flex flex-col items-center gap-3 py-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-50">
              <Bot size={20} className="text-blue-500" />
            </div>
            <p className="text-[12px] text-slate-500 text-center">
              Ask a clinical question about this patient.
            </p>
            <div className="w-full space-y-1.5">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => handleSubmit(prompt)}
                  className="flex w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-[11px] text-slate-700 hover:border-blue-300 hover:bg-blue-50/50 transition-colors"
                >
                  <ChevronRight size={10} className="shrink-0 text-blue-400" />
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
            compact
          />
        ))}

        {chat.isPending && (
          <div className="flex gap-2.5">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100">
              <Bot size={12} className="text-blue-600" />
            </div>
            <div className="flex items-center gap-2 text-[11px] text-slate-400">
              <div className="w-3 h-3 border-2 border-slate-300 border-t-blue-500 rounded-full animate-spin" />
              Analyzing...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-slate-100 px-3 py-2.5">
        <form
          onSubmit={(e) => { e.preventDefault(); handleSubmit(input); }}
          className="flex items-center gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(input);
              }
            }}
            placeholder="Ask a question..."
            className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] text-[#1c1c1e] outline-none placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:ring-1 focus:ring-blue-100"
          />
          <button
            type="submit"
            disabled={chat.isPending || input.trim().length === 0}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#5b76fe] text-white disabled:opacity-40 hover:bg-[#4a65ed] transition-colors"
          >
            <Send size={14} />
          </button>
        </form>
      </div>
    </div>
  );
}
