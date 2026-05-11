import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUp,
  Beaker,
  Boxes,
  FileText,
  GitBranch,
  Globe,
  Lock,
  Paperclip,
  Pin,
  Quote,
  Sparkles,
} from "lucide-react";
import type { ChatAction, ChatMessage } from "./data";
import type { Workspace } from "./types";

const ACTION_ICONS: Record<string, typeof FileText> = {
  FileText,
  Quote,
  Beaker,
  Boxes,
  ArrowRight,
};

type ChatPaneProps = {
  workspace: Workspace;
  messages: ChatMessage[];
  onSend: (text: string) => void;
  onCitationClick: (id: string) => void;
  onReferenceClick: (id: string) => void;
  onAction: (target: string) => void;
  activeCitationId: string | null;
};

export function ChatPane({
  workspace,
  messages,
  onSend,
  onCitationClick,
  onReferenceClick,
  onAction,
  activeCitationId,
}: ChatPaneProps) {
  const [text, setText] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  const submit = () => {
    if (!text.trim()) return;
    onSend(text.trim());
    setText("");
  };

  const placeholder =
    workspace.family === "clinical"
      ? "Ask about the chart, hold a workflow, or open another tab…"
      : "Steer the run, approve a step, or open another tab…";

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
        <div className="text-[12px] font-semibold" style={{ color: "var(--ink-2)" }}>
          {workspace.family === "clinical" ? "Clinical chat" : "Workspace thread"}
          <small
            className="ml-2 font-medium"
            style={{ color: "var(--ink-4)", letterSpacing: 0 }}
          >
            {workspace.title} agent
          </small>
        </div>
        <div className="ml-auto">
          <BoundaryPill workspace={workspace} />
        </div>
      </div>
      <div ref={scrollRef} className="overflow-y-auto px-6 py-4 pb-2">
        <div
          className="mb-4 flex items-center gap-2 border-b pb-3 text-[10.5px]"
          style={{ borderColor: "var(--line-1)", color: "var(--ink-4)" }}
        >
          <span>Session opened 12 min ago</span>
          <DotSep />
          <span>{messages.length} messages</span>
          <DotSep />
          <span>5 citations · 3 tabs · 1 approval pending</span>
        </div>
        {messages.map((m) => (
          <Message
            key={m.id}
            msg={m}
            workspace={workspace}
            onCitationClick={onCitationClick}
            onReferenceClick={onReferenceClick}
            activeCitationId={activeCitationId}
            onAction={onAction}
          />
        ))}
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
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={placeholder}
            rows={2}
            className="resize-none border-0 bg-transparent text-[13px] leading-relaxed outline-none"
            style={{ color: "var(--ink-1)" }}
          />
          <div className="flex items-center gap-1.5">
            <ComposerBtn icon={<Paperclip className="h-3 w-3" strokeWidth={1.5} />}>Attach</ComposerBtn>
            <ComposerBtn icon={<Pin className="h-3 w-3" strokeWidth={1.5} />}>Pin context</ComposerBtn>
            <ComposerBtn outline icon={<Sparkles className="h-3 w-3" strokeWidth={1.5} />}>
              {workspace.family === "clinical" ? "clinical-high" : "marketplace-act"}
            </ComposerBtn>
            <div className="flex-1" />
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
            <button
              onClick={submit}
              disabled={!text.trim()}
              className="grid h-[26px] w-[26px] place-items-center rounded-md text-white transition-colors disabled:cursor-default"
              style={{
                background: text.trim() ? "var(--ink-1)" : "var(--ink-5)",
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

function BoundaryPill({ workspace }: { workspace: Workspace }) {
  const warn = workspace.boundaryTone === "warn";
  return (
    <span
      className="inline-flex h-[22px] items-center gap-1.5 rounded-full border px-2 text-[10.5px] font-semibold tracking-wide"
      style={
        warn
          ? {
              background: "var(--caution-tint)",
              color: "var(--caution)",
              borderColor: "var(--caution-line)",
            }
          : {
              background: "var(--clear-tint)",
              color: "var(--clear)",
              borderColor: "var(--clear-line)",
            }
      }
    >
      {warn ? (
        <Globe className="h-2.5 w-2.5" strokeWidth={1.5} />
      ) : (
        <Lock className="h-2.5 w-2.5" strokeWidth={1.5} />
      )}
      {workspace.boundary}
    </span>
  );
}

function Message({
  msg,
  workspace,
  onCitationClick,
  onReferenceClick,
  activeCitationId,
  onAction,
}: {
  msg: ChatMessage;
  workspace: Workspace;
  onCitationClick: (id: string) => void;
  onReferenceClick: (id: string) => void;
  activeCitationId: string | null;
  onAction: (target: string) => void;
}) {
  if (msg.role === "user") {
    return (
      <div className="mb-5 ml-auto max-w-[720px]">
        <div
          className="rounded-[14px_14px_4px_14px] border px-4 py-3 text-[13px] leading-relaxed"
          style={{
            background: "var(--surface-3)",
            borderColor: "var(--line-1)",
            color: "var(--ink-1)",
          }}
        >
          {msg.content}
        </div>
      </div>
    );
  }
  const isClinical = workspace.family === "clinical";
  return (
    <div className="mb-5 grid max-w-[720px] grid-cols-[28px_1fr] gap-3">
      <div
        className="grid h-[26px] w-[26px] place-items-center rounded-md text-[11px] font-bold text-white"
        style={{
          background: isClinical ? "var(--mod-preop)" : "var(--mod-trials)",
        }}
      >
        {isClinical ? "Px" : "Tf"}
      </div>
      <div>
        <div
          className="mb-1.5 flex items-center gap-1.5 text-[11.5px] font-semibold"
          style={{ color: "var(--ink-3)" }}
        >
          {isClinical ? "Pre-op agent" : "Trial Finder agent"}
          {msg.time && (
            <span className="font-normal" style={{ color: "var(--ink-4)" }}>
              · {msg.time}
            </span>
          )}
        </div>
        {msg.trace && (
          <div
            className="mb-2 flex items-center gap-2.5 rounded-md border px-3 py-2 text-[11.5px]"
            style={{
              background: "var(--surface-2)",
              borderColor: "var(--line-1)",
              color: "var(--ink-3)",
            }}
          >
            <GitBranch className="h-3 w-3" strokeWidth={1.5} />
            <span style={{ color: "var(--ink-2)", fontFamily: "var(--font-mono)" }}>
              {msg.trace.tool}
            </span>
            <span style={{ color: "var(--ink-4)" }}>→</span>
            <span style={{ color: "var(--action)", fontFamily: "var(--font-mono)" }}>
              {msg.trace.target}
            </span>
          </div>
        )}
        <div
          className="text-[14px] leading-[1.62]"
          style={{
            fontFamily: "var(--font-serif)",
            color: "var(--ink-1)",
            letterSpacing: "-0.005em",
          }}
        >
          {msg.blocks.map((b, i) => (
            <p key={i} className="mb-2.5 last:mb-0">
              {renderInline(b, onCitationClick, onReferenceClick, activeCitationId)}
            </p>
          ))}
        </div>
        {msg.approval && (
          <div
            className="mt-3 grid grid-cols-[18px_1fr] gap-2.5 rounded-[10px] border p-3.5"
            style={{
              background: "var(--caution-tint)",
              borderColor: "var(--caution-line)",
            }}
          >
            <AlertTriangle
              className="mt-0.5 h-4 w-4"
              strokeWidth={1.5}
              style={{ color: "var(--caution)" }}
            />
            <div>
              <div
                className="text-[12px] font-semibold tracking-wide"
                style={{ color: "var(--caution)" }}
              >
                APPROVAL REQUESTED
              </div>
              <div
                className="mt-1 text-[12.5px] leading-[1.5]"
                style={{ color: "var(--ink-1)" }}
              >
                {msg.approval.body}
              </div>
              <div className="mt-2.5 flex gap-2">
                <button
                  className="h-[26px] rounded-md px-3 text-[12px] font-semibold text-white"
                  style={{ background: "var(--ink-1)" }}
                >
                  {msg.approval.primary}
                </button>
                <button
                  className="h-[26px] rounded-md border px-3 text-[12px] font-semibold"
                  style={{
                    background: "var(--surface-0)",
                    borderColor: "var(--line-2)",
                    color: "var(--ink-2)",
                  }}
                >
                  {msg.approval.secondary}
                </button>
              </div>
            </div>
          </div>
        )}
        {msg.actions && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {msg.actions.map((a, i) => (
              <ActionChip key={i} action={a} onClick={() => onAction(a.target)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ActionChip({ action, onClick }: { action: ChatAction; onClick: () => void }) {
  const Icon = ACTION_ICONS[action.icon] ?? ArrowRight;
  return (
    <button
      onClick={onClick}
      className="inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-[11.5px] font-medium transition-colors hover:border-[var(--action-line)] hover:bg-[var(--action-tint)] hover:text-[var(--action)]"
      style={{
        background: "var(--surface-0)",
        borderColor: "var(--line-1)",
        color: "var(--ink-2)",
      }}
    >
      <Icon className="h-3 w-3" strokeWidth={1.5} />
      {action.label}
    </button>
  );
}

function renderInline(
  text: string,
  onCitationClick: (id: string) => void,
  onReferenceClick: (id: string) => void,
  activeCitationId: string | null,
): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const regex = /\[(c_\d+|[a-z0-9_.\-]+\.(?:md|json|txt|csv))\]/gi;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const ref = m[1];
    const isCite = ref.startsWith("c_");
    parts.push(
      <CitationChip
        key={i++}
        id={ref}
        active={activeCitationId === ref}
        kind={isCite ? "citation" : "file"}
        onClick={() => (isCite ? onCitationClick(ref) : onReferenceClick(ref))}
      />,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function CitationChip({
  id,
  active,
  kind,
  onClick,
}: {
  id: string;
  active: boolean;
  kind: "citation" | "file";
  onClick: () => void;
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
      {kind === "citation" ? (
        <Quote className="h-2 w-2" strokeWidth={1.5} />
      ) : (
        <FileText className="h-2 w-2" strokeWidth={1.5} />
      )}
      {id}
    </span>
  );
}

function ComposerBtn({
  icon,
  children,
  outline,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
  outline?: boolean;
}) {
  return (
    <button
      className="inline-flex h-6 items-center gap-1.5 rounded-md px-2 text-[11.5px] font-medium hover:bg-[var(--surface-2)] hover:text-[var(--ink-1)]"
      style={{
        color: "var(--ink-3)",
        border: outline ? "1px solid var(--line-1)" : "1px solid transparent",
      }}
    >
      {icon}
      {children}
    </button>
  );
}

function DotSep() {
  return (
    <span
      className="h-px w-px rounded-full"
      style={{ background: "var(--ink-5)" }}
    />
  );
}
