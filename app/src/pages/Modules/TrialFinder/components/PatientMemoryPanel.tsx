import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BookMarked, Pin, Sparkles } from "lucide-react";
import { skillsApi } from "../../../../api/skills";

interface PatientMemoryPanelProps {
  patientId: string;
  /** When provided, the panel links to a deep-view page; otherwise it stays inline-only. */
  detailHref?: string;
}

/**
 * Compact "what the agent will see at session start" panel.
 *
 * The whole point of the patient memory layer is that future skill runs
 * inherit pinned facts and context packages the clinician promoted from
 * earlier runs. That contract is invisible if the UI never shows it. This
 * panel lives on the run view's right rail so the clinician can see, at
 * any moment, the memory the next run's agent will pre-load.
 */
export function PatientMemoryPanel({
  patientId,
  detailHref,
}: PatientMemoryPanelProps) {
  const memoryQuery = useQuery({
    queryKey: ["skill-patient-memory", patientId],
    queryFn: () => skillsApi.getPatientMemory(patientId),
    refetchOnWindowFocus: false,
  });

  const memory = memoryQuery.data;
  const hasPinned = !!memory && memory.pinned.trim().length > 0;
  const hasPackages = !!memory && Object.keys(memory.context_packages).length > 0;
  const isEmpty = !hasPinned && !hasPackages;

  return (
    <section className="rounded-2xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={14} className="text-[#5b76fe]" />
          <h3 className="text-sm font-semibold text-[#1c1c1e]">Patient memory</h3>
        </div>
        {detailHref ? (
          <Link
            to={detailHref}
            className="text-[11px] font-semibold text-[#5b76fe] hover:underline"
          >
            View all
          </Link>
        ) : null}
      </header>
      <p className="mt-1 text-[11px] leading-4 text-[#a5a8b5]">
        What every future skill run for this patient will see at session start.
      </p>

      {memoryQuery.isLoading ? (
        <p className="mt-3 text-xs text-[#a5a8b5]">Loading…</p>
      ) : isEmpty ? (
        <div className="mt-3 rounded-xl border border-dashed border-[#e9eaef] p-3 text-[11px] leading-5 text-[#a5a8b5]">
          No pinned facts or context packages yet. When you finish a run, you
          can promote selected facts here so the next agent inherits them.
        </div>
      ) : (
        <div className="mt-3 space-y-3">
          {hasPinned ? (
            <div>
              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[#3a4ca8]">
                <Pin size={11} />
                Pinned facts
              </div>
              <pre className="mt-1.5 overflow-x-auto rounded-lg bg-[#f5f6f8] p-2.5 font-mono text-[11px] leading-5 text-[#1c1c1e] whitespace-pre-wrap">
                {trimPinned(memory!.pinned)}
              </pre>
            </div>
          ) : null}

          {hasPackages ? (
            <div>
              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[#187574]">
                <BookMarked size={11} />
                Context packages
              </div>
              <ul className="mt-1.5 space-y-1">
                {Object.keys(memory!.context_packages)
                  .sort()
                  .map((name) => (
                    <li
                      key={name}
                      className="flex items-center gap-2 rounded-lg bg-[#c3faf5] px-2.5 py-1.5"
                    >
                      <span className="font-mono text-[11px] font-semibold text-[#187574]">
                        {name}
                      </span>
                      <span className="ml-auto text-[10px] text-[#187574]/70">
                        {memory!.context_packages[name].length} chars
                      </span>
                    </li>
                  ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

function trimPinned(text: string, max = 600): string {
  const cleaned = text.trim();
  if (cleaned.length <= max) return cleaned;
  return cleaned.slice(0, max - 1).trimEnd() + "…";
}
