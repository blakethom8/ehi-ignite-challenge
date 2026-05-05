import { Link } from "react-router-dom";
import { Clock, AlertOctagon, CheckCircle, Loader, XCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { RunListItem, RunStatus } from "../../../../types/skills";

interface RunHistorySidebarProps {
  patientId: string;
  runs: RunListItem[];
  activeRunId: string | null;
}

const STATUS_TONE: Record<RunStatus, { icon: LucideIcon; bg: string; fg: string; label: string }> = {
  created: { icon: Loader, bg: "#f5f6f8", fg: "#555a6a", label: "Created" },
  running: { icon: Loader, bg: "#eef1ff", fg: "#3a4ca8", label: "Running" },
  escalated: { icon: AlertOctagon, bg: "#fffbeb", fg: "#92400e", label: "Escalated" },
  validated: { icon: CheckCircle, bg: "#c3faf5", fg: "#187574", label: "Validated" },
  finished: { icon: CheckCircle, bg: "#f0fdf4", fg: "#166534", label: "Finished" },
  failed: { icon: XCircle, bg: "#fef2f2", fg: "#991b1b", label: "Failed" },
};

export function RunHistorySidebar({
  patientId,
  runs,
  activeRunId,
}: RunHistorySidebarProps) {
  if (!runs.length) {
    return (
      <aside className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <Clock size={14} className="text-[#5b76fe]" />
          <h3 className="text-sm font-semibold text-[#1c1c1e]">Recent runs</h3>
        </div>
        <p className="mt-2 text-xs text-[#a5a8b5]">
          No runs yet for this patient. Start one from the brief on the left.
        </p>
      </aside>
    );
  }

  return (
    <aside className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock size={14} className="text-[#5b76fe]" />
          <h3 className="text-sm font-semibold text-[#1c1c1e]">Recent runs</h3>
        </div>
        <span className="text-[11px] text-[#a5a8b5]">{runs.length}</span>
      </div>
      <ul className="mt-3 space-y-2">
        {runs.map((run) => {
          const tone = STATUS_TONE[run.status];
          const Icon = tone.icon;
          const isActive = activeRunId === run.run_id;
          const target = `/skills/trial-finder?patient=${encodeURIComponent(
            patientId
          )}&run=${encodeURIComponent(run.run_id)}`;
          return (
            <li key={run.run_id}>
              <Link
                to={target}
                className={`flex items-center gap-2 rounded-xl border p-2 text-xs transition ${
                  isActive
                    ? "border-[#5b76fe] bg-[#eef1ff]"
                    : "border-[#e9eaef] bg-white hover:bg-[#fafafb]"
                }`}
              >
                <span
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md"
                  style={{ backgroundColor: tone.bg, color: tone.fg }}
                >
                  <Icon size={11} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-[11px] text-[#1c1c1e]">
                    {run.run_id}
                  </p>
                  <p className="text-[10px] text-[#a5a8b5]">
                    {tone.label}
                    {run.started_at
                      ? ` · ${new Date(run.started_at).toLocaleString()}`
                      : ""}
                  </p>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
