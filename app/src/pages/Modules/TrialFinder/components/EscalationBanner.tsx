import { useState } from "react";
import { AlertOctagon, MessageSquareText } from "lucide-react";
import type { PendingEscalation } from "../../../../types/skills";

interface EscalationBannerProps {
  escalation: PendingEscalation;
  onResolve: (choice: string, notes: string) => Promise<void>;
  isResolving: boolean;
}

/**
 * The "stop the agent and ask" banner. Shown when the run is in
 * `escalated` state. The clinician's choice is the resolution sent back
 * to the runtime; once resolved, the runner resumes from where it
 * paused.
 */
export function EscalationBanner({
  escalation,
  onResolve,
  isResolving,
}: EscalationBannerProps) {
  const [choice, setChoice] = useState<string>("");
  const [notes, setNotes] = useState<string>("");

  const submit = async () => {
    if (!choice.trim()) return;
    await onResolve(choice.trim(), notes.trim());
  };

  return (
    <section
      className="rounded-2xl border p-5"
      style={{ backgroundColor: "#fffbeb", borderColor: "#f59e0b" }}
    >
      <div className="flex items-start gap-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
          style={{ backgroundColor: "rgba(255,255,255,0.72)", color: "#92400e" }}
        >
          <AlertOctagon size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-[#92400e]">
              Approval gate
            </p>
            <span className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-mono text-[#92400e]">
              {escalation.approval_id} · {escalation.condition}
            </span>
          </div>
          <h3 className="mt-1 text-base font-semibold text-[#1c1c1e]">
            The agent paused here
          </h3>
          <p className="mt-2 text-sm leading-6 text-[#1c1c1e]">
            {escalation.prompt}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto]">
        <div className="space-y-2">
          <label className="block text-xs font-semibold text-[#1c1c1e]">
            Your decision
            <input
              value={choice}
              onChange={(e) => setChoice(e.target.value)}
              placeholder="confirmed | skip | broaden | stop"
              className="mt-1 w-full rounded-lg border border-[#e9eaef] bg-white px-3 py-2 text-sm text-[#1c1c1e] focus:border-[#5b76fe] focus:outline-none"
            />
          </label>
          <label className="block text-xs font-semibold text-[#1c1c1e]">
            Notes (optional)
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Anything the agent should remember on resume."
              className="mt-1 w-full rounded-lg border border-[#e9eaef] bg-white px-3 py-2 text-sm text-[#1c1c1e] focus:border-[#5b76fe] focus:outline-none"
            />
          </label>
        </div>
        <div className="flex flex-col items-end justify-end gap-2">
          <button
            type="button"
            disabled={isResolving || !choice.trim()}
            onClick={submit}
            className="inline-flex items-center gap-2 rounded-lg bg-[#5b76fe] px-4 py-2 text-sm font-semibold text-white shadow-sm transition disabled:cursor-not-allowed disabled:opacity-60"
            style={{ letterSpacing: 0.175 }}
          >
            <MessageSquareText size={14} />
            {isResolving ? "Resuming…" : "Resolve & resume"}
          </button>
          <p className="text-[11px] text-[#92400e]">
            Resolution is logged in the run transcript.
          </p>
        </div>
      </div>
    </section>
  );
}
