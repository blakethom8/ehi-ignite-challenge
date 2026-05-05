import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  BookMarked,
  Clock,
  Pin,
  Sparkles,
  UserRound,
} from "lucide-react";
import { api } from "../../api/client";
import { skillsApi } from "../../api/skills";
import { EmptyState } from "../../components/EmptyState";

/**
 * Patient memory layer — full view.
 *
 * Mounts at `/skills/patients/memory?patient=…`. Surfaces the durable
 * cross-skill memory promoted via "Save to patient" or "Save as context
 * package". The agent reads `pinned.md` and any declared
 * `context_packages` at the start of every future skill run for this
 * patient; this page makes that contract visible.
 */
export function PatientMemoryView() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  if (!patientId) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-12">
        <EmptyState
          icon={UserRound}
          title="Pick a patient"
          bullets={["Patient memory is per-patient — pick one to view."]}
        />
      </div>
    );
  }

  return <Loaded patientId={patientId} />;
}

function Loaded({ patientId }: { patientId: string }) {
  const memoryQuery = useQuery({
    queryKey: ["skill-patient-memory", patientId],
    queryFn: () => skillsApi.getPatientMemory(patientId),
  });

  const overviewQuery = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId),
  });

  const recentNotes = useMemo(() => {
    const notes = memoryQuery.data?.notes ?? [];
    return notes.slice().reverse().slice(0, 20);
  }, [memoryQuery.data?.notes]);

  const pinned = memoryQuery.data?.pinned ?? "";
  const packages = memoryQuery.data?.context_packages ?? {};
  const packageNames = Object.keys(packages).sort();

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-6 py-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <Link
            to={`/skills/trial-finder?patient=${encodeURIComponent(patientId)}`}
            className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#5b76fe] hover:underline"
          >
            <ArrowLeft size={12} /> Back to Trial Finder
          </Link>
          <div className="mt-2 flex items-center gap-2">
            <Sparkles size={16} className="text-[#5b76fe]" />
            <h1 className="text-2xl font-semibold text-[#1c1c1e]">
              Patient memory
            </h1>
          </div>
          <p className="mt-1 text-sm text-[#555a6a]">
            {overviewQuery.data?.name ?? patientId} — what every future skill
            run for this patient pre-loads at session start.
          </p>
        </div>
      </header>

      <section className="rounded-2xl bg-[#eef1ff] p-5 shadow-[rgb(199_208_250)_0px_0px_0px_1px]">
        <p className="text-xs leading-5 text-[#3a4ca8]">
          The agent never writes here directly. Promotion happens only via the
          run-view "Save…" drawer (Pin to patient memory or Save as context
          package). Every entry below started as a citation-grounded fact in a
          completed run; click "View all" on the run history to trace it back.
        </p>
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <Pin size={15} className="text-[#3a4ca8]" />
          <h2 className="text-base font-semibold text-[#1c1c1e]">Pinned facts</h2>
        </div>
        {pinned.trim() ? (
          <pre className="mt-3 overflow-x-auto rounded-xl bg-[#f5f6f8] p-4 font-mono text-[12px] leading-6 text-[#1c1c1e] whitespace-pre-wrap">
            {pinned}
          </pre>
        ) : (
          <p className="mt-3 rounded-xl border border-dashed border-[#e9eaef] p-4 text-xs text-[#a5a8b5]">
            No pinned facts yet. Use "Pin to patient memory" on a finished run
            to promote chart-grounded facts here.
          </p>
        )}
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <BookMarked size={15} className="text-[#187574]" />
          <h2 className="text-base font-semibold text-[#1c1c1e]">
            Context packages
          </h2>
          <span className="ml-auto text-[11px] text-[#a5a8b5]">
            {packageNames.length} package{packageNames.length === 1 ? "" : "s"}
          </span>
        </div>
        {packageNames.length === 0 ? (
          <p className="mt-3 rounded-xl border border-dashed border-[#e9eaef] p-4 text-xs text-[#a5a8b5]">
            No context packages yet. Skills can declare them in their
            <code className="mx-1 rounded bg-[#f5f6f8] px-1 font-mono">context_packages:</code>
            frontmatter and they get mounted automatically at session start.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {packageNames.map((name) => (
              <details
                key={name}
                className="rounded-xl border border-[#e9eaef] bg-white"
              >
                <summary className="cursor-pointer list-none rounded-xl px-4 py-2.5 hover:bg-[#fafafb]">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <BookMarked size={13} className="text-[#187574]" />
                      <span className="font-mono text-sm font-semibold text-[#187574]">
                        {name}
                      </span>
                    </div>
                    <span className="text-[10px] text-[#a5a8b5]">
                      {packages[name].length} chars
                    </span>
                  </div>
                </summary>
                <pre className="overflow-x-auto rounded-b-xl bg-[#f5f6f8] p-4 font-mono text-[12px] leading-6 text-[#1c1c1e] whitespace-pre-wrap">
                  {packages[name]}
                </pre>
              </details>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <Clock size={15} className="text-[#5b76fe]" />
          <h2 className="text-base font-semibold text-[#1c1c1e]">
            Recent activity
          </h2>
        </div>
        {recentNotes.length === 0 ? (
          <p className="mt-3 text-xs text-[#a5a8b5]">
            No promotion events yet.
          </p>
        ) : (
          <ol className="mt-3 space-y-2">
            {recentNotes.map((note, idx) => (
              <li
                key={idx}
                className="rounded-xl border border-[#e9eaef] bg-white p-3"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-xs font-semibold text-[#1c1c1e]">
                    {String(note.kind ?? "event").replaceAll("_", " ")}
                  </p>
                  <span className="font-mono text-[10px] text-[#a5a8b5]">
                    {note.at ? new Date(String(note.at)).toLocaleString() : ""}
                  </span>
                </div>
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap font-mono text-[11px] leading-4 text-[#555a6a]">
                  {summarizeNote(note)}
                </pre>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function summarizeNote(note: Record<string, unknown>): string {
  const fields: string[] = [];
  if (note.actor) fields.push(`actor: ${note.actor}`);
  if (note.source_run) fields.push(`run: ${note.source_run}`);
  if (note.source_skill) fields.push(`skill: ${note.source_skill}`);
  if (note.package_name) fields.push(`package: ${note.package_name}`);
  if (typeof note.fact_count === "number") {
    fields.push(`facts: ${note.fact_count}`);
  }
  if (Array.isArray(note.fact_summaries)) {
    fields.push(`first: ${String((note.fact_summaries as string[])[0] ?? "")}`);
  }
  if (typeof note.char_count === "number") {
    fields.push(`size: ${note.char_count} chars`);
  }
  return fields.join("\n");
}
