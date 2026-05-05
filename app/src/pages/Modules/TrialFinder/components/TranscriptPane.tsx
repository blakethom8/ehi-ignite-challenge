import {
  AlertOctagon,
  CheckCircle,
  FileText,
  Hash,
  Quote,
  Save,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { TranscriptEvent } from "../../../../types/skills";

interface TranscriptPaneProps {
  events: TranscriptEvent[];
}

const EVENT_TONE: Record<
  string,
  { icon: LucideIcon; bg: string; fg: string; label: string }
> = {
  run_started: { icon: CheckCircle, bg: "#eef1ff", fg: "#3a4ca8", label: "Run started" },
  system_prompt_assembled: { icon: FileText, bg: "#f5f6f8", fg: "#555a6a", label: "Brief assembled" },
  phase_complete: { icon: Hash, bg: "#c3faf5", fg: "#187574", label: "Phase complete" },
  cite: { icon: Quote, bg: "#eef1ff", fg: "#3a4ca8", label: "Citation registered" },
  workspace_write: { icon: FileText, bg: "#f0fdf4", fg: "#166534", label: "Workspace section written" },
  escalation: { icon: AlertOctagon, bg: "#fffbeb", fg: "#92400e", label: "Escalation raised" },
  escalation_resolved: { icon: CheckCircle, bg: "#f0fdf4", fg: "#166534", label: "Escalation resolved" },
  finalize: { icon: CheckCircle, bg: "#f0fdf4", fg: "#166534", label: "Run finalized" },
  run_finished: { icon: CheckCircle, bg: "#f0fdf4", fg: "#166534", label: "Run finished" },
  run_failed: { icon: AlertOctagon, bg: "#fef2f2", fg: "#991b1b", label: "Run failed" },
  save: { icon: Save, bg: "#ffe6cd", fg: "#9a5a16", label: "Save" },
  trial_skipped: { icon: Wrench, bg: "#f5f6f8", fg: "#555a6a", label: "Trial skipped" },
};

const DEFAULT_TONE = {
  icon: Wrench,
  bg: "#f5f6f8",
  fg: "#555a6a",
  label: "Event",
};

export function TranscriptPane({ events }: TranscriptPaneProps) {
  if (!events.length) {
    return (
      <div className="rounded-xl border border-dashed border-[#e9eaef] p-4 text-xs text-[#a5a8b5]">
        No transcript events yet — the run is starting.
      </div>
    );
  }
  return (
    <ol className="space-y-2">
      {events.map((event, idx) => {
        const tone = EVENT_TONE[event.kind] ?? { ...DEFAULT_TONE, label: event.kind };
        const Icon = tone.icon;
        const summary = describeEvent(event);
        const time = formatTime(event.at);
        return (
          <li
            key={`${event.at}-${idx}`}
            className="rounded-xl bg-white p-3 shadow-[rgb(224_226_232)_0px_0px_0px_1px]"
          >
            <div className="flex items-start gap-2.5">
              <span
                className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md"
                style={{ backgroundColor: tone.bg, color: tone.fg }}
              >
                <Icon size={12} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-xs font-semibold text-[#1c1c1e]">{tone.label}</p>
                  <span className="font-mono text-[10px] text-[#a5a8b5]">{time}</span>
                </div>
                {summary ? (
                  <p className="mt-0.5 text-[12px] leading-5 text-[#555a6a]">{summary}</p>
                ) : null}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function describeEvent(event: TranscriptEvent): string {
  const { kind } = event;
  if (kind === "phase_complete") {
    const phase = event.phase as number | undefined;
    const candidates = event.candidate_count as number | undefined;
    const surviving = event.surviving as number | undefined;
    const anchors = event.anchors as number | undefined;
    const parts: string[] = [];
    if (phase !== undefined) parts.push(`phase ${phase}`);
    if (anchors !== undefined) parts.push(`${anchors} anchors`);
    if (candidates !== undefined) parts.push(`${candidates} candidates`);
    if (surviving !== undefined) parts.push(`${surviving} surviving`);
    return parts.join(" · ");
  }
  if (kind === "cite") {
    return `${event.citation_id} (${event.source_kind})`;
  }
  if (kind === "workspace_write") {
    return `${event.section} — ${event.char_count} chars · ${
      Array.isArray(event.citation_ids) ? event.citation_ids.length : 0
    } citations`;
  }
  if (kind === "escalation") {
    return `${event.condition}: ${truncate(String(event.prompt ?? ""), 140)}`;
  }
  if (kind === "escalation_resolved") {
    return `${event.approval_id} → ${event.choice} (${event.actor})`;
  }
  if (kind === "save") {
    const dest = event.destination as string | undefined;
    return dest ? `destination: ${dest}` : "";
  }
  if (kind === "system_prompt_assembled") {
    return `${event.char_count} chars`;
  }
  if (kind === "run_failed") {
    return truncate(String(event.reason ?? ""), 200);
  }
  if (kind === "trial_skipped") {
    return `${event.nct_id}: ${truncate(String(event.reason ?? ""), 100)}`;
  }
  return "";
}

function formatTime(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}
