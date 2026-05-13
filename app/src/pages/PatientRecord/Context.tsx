import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  Bot,
  CheckCircle2,
  ClipboardList,
  Download,
  FileText,
  LockKeyhole,
  MessageSquareText,
  Send,
  UserRound,
} from "lucide-react";
import { api } from "../../api/client";
import type {
  PatientContextGapCard,
  PatientContextSessionResponse,
  PatientContextSourceMode,
} from "../../types";

const categoryLabels: Record<PatientContextGapCard["category"], string> = {
  missing_sources: "Missing sources",
  medication_reality: "Medication reality",
  timeline_gap: "Timeline gaps",
  uncertain_fact: "Uncertain facts",
  qualitative_context: "Patient context",
};

const sourceModeCopy: Record<PatientContextSourceMode, { label: string; detail: string }> = {
  selected_patient: {
    label: "Selected patient",
    detail: "Use the active patient workspace and its current evidence posture.",
  },
  synthetic: {
    label: "Synthetic showcase",
    detail: "Use the demo interview flow for product walkthroughs and UI review.",
  },
  private_blake_cedars: {
    label: "Private Cedars proof-of-life",
    detail: "Use the local Cedars record when it is available on this machine.",
  },
};

function cls(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

function statusStyle(status: PatientContextGapCard["status"]): string {
  if (status === "answered") return "border-clear-line bg-clear-tint text-clear";
  if (status === "skipped") return "border-line-1 bg-surface-1 text-ink-3";
  return "border-caution-line bg-caution-tint text-caution";
}

function errorText(error: unknown): string {
  if (error && typeof error === "object" && "response" in error) {
    const maybe = error as { response?: { data?: { detail?: string } } };
    if (maybe.response?.data?.detail) return maybe.response.data.detail;
  }
  if (error instanceof Error) return error.message;
  return "Request failed.";
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Not generated";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function MetricTile({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <div className="rounded-[10px] border border-line-1 bg-surface-1 px-3 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-3">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink-1">{value}</p>
      <p className="mt-1 text-xs leading-5 text-ink-3">{detail}</p>
    </div>
  );
}

function EmptyCard({ children }: { children: string }) {
  return (
    <div className="rounded-[10px] border border-dashed border-line-2 bg-surface-1 px-4 py-4 text-sm leading-6 text-ink-3">
      {children}
    </div>
  );
}

export function PatientContext() {
  const [params] = useSearchParams();
  const patientFromUrl = params.get("patient");
  const [session, setSession] = useState<PatientContextSessionResponse | null>(null);
  const [selectedGapId, setSelectedGapId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [exportPreview, setExportPreview] = useState("");
  const [sourceMode, setSourceMode] = useState<PatientContextSourceMode>("selected_patient");

  const patientsQuery = useQuery({
    queryKey: ["patients"],
    queryFn: api.listPatients,
  });

  const statusQuery = useQuery({
    queryKey: ["patient-context-status"],
    queryFn: api.getPatientContextStatus,
    retry: false,
  });

  const patientId = patientFromUrl || patientsQuery.data?.[0]?.id || "";

  const activeGapId = useMemo(() => {
    if (!session?.gap_cards.length) return null;
    if (selectedGapId && session.gap_cards.some((gap) => gap.id === selectedGapId)) {
      return selectedGapId;
    }
    return session.gap_cards.find((gap) => gap.status === "open")?.id || session.gap_cards[0].id;
  }, [selectedGapId, session]);

  const createMutation = useMutation({
    mutationFn: () => api.createPatientContextSession(patientId, sourceMode),
    onSuccess: (data) => {
      setSession(data);
      setExportPreview("");
      setSelectedGapId(data.gap_cards.find((gap) => gap.status === "open")?.id || null);
    },
  });

  const turnMutation = useMutation({
    mutationFn: () => api.sendPatientContextTurn(session!.session_id, message, activeGapId),
    onSuccess: (data) => {
      setSession(data);
      setMessage("");
      const next = data.gap_cards.find((gap) => gap.id === data.assistant_message.linked_gap_id)
        || data.gap_cards.find((gap) => gap.status === "open")
        || data.gap_cards[0];
      setSelectedGapId(next?.id || null);
    },
  });

  const exportMutation = useMutation({
    mutationFn: () => api.exportPatientContext(session!.session_id),
    onSuccess: (data) => {
      setExportPreview(data.preview);
      setSession((prev) => prev ? {
        ...prev,
        export_status: {
          generated: true,
          files: data.files,
          generated_at: data.generated_at,
        },
      } : prev);
    },
  });

  const selectedGap = useMemo(
    () => session?.gap_cards.find((gap) => gap.id === activeGapId) || null,
    [session, activeGapId],
  );

  const answeredCount = session?.gap_cards.filter((gap) => gap.status === "answered").length ?? 0;
  const totalCount = session?.gap_cards.length ?? 0;
  const openCount = session?.gap_cards.filter((gap) => gap.status === "open").length ?? 0;
  const latestTurn = session?.turns.at(-1) ?? null;
  const progressPercent = totalCount > 0 ? Math.round((answeredCount / totalCount) * 100) : 0;
  const privateAvailable = statusQuery.data?.private_blake_cedars_available ?? false;
  const files = session?.export_status.files.length
    ? session.export_status.files
    : ["PATIENT_CONTEXT.md", "QUESTIONS.md", "SOURCES.md", "AGENT.md"];

  function submitTurn(event: FormEvent) {
    event.preventDefault();
    if (!session || !message.trim() || turnMutation.isPending) return;
    turnMutation.mutate();
  }

  return (
    <main className="mx-auto max-w-[1500px] space-y-4 p-4 lg:p-6">
      <section className="rounded-[10px] border border-line-1 bg-surface-0 shadow-[var(--shadow-1)]">
        <div className="grid gap-4 p-5 xl:grid-cols-[minmax(0,1.3fr)_360px] xl:p-6">
          <div className="min-w-0">
            <p className="inline-flex items-center gap-2 rounded-full bg-action-tint px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-action">
              <MessageSquareText size={13} />
              Add patient context
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-ink-1">
              Capture the story the chart still cannot tell
            </h1>
            <p className="mt-3 max-w-4xl text-sm leading-7 text-ink-3">
              This guided intake captures patient-reported facts, treatment reality, and missing timeline context
              without changing verified chart data. The workflow is simple: start a session, answer the active prompt,
              review captured context, then export a portable bundle.
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <MetricTile
                label="Progress"
                value={session ? `${answeredCount}/${totalCount}` : "Not started"}
                detail={session ? `${progressPercent}% of the intake completed` : "Start a session to generate gap cards"}
              />
              <MetricTile
                label="Captured facts"
                value={session?.facts.length ?? 0}
                detail={session ? "Patient-reported statements saved as local context" : "No patient-reported facts yet"}
              />
              <MetricTile
                label="Export status"
                value={session?.export_status.generated ? "Generated" : "Pending"}
                detail={session?.export_status.generated_at ? formatDateTime(session.export_status.generated_at) : "Create the Markdown bundle after intake"}
              />
            </div>
            <div className="mt-5 rounded-[10px] border border-line-1 bg-surface-1 px-4 py-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">Current session state</p>
                  <p className="mt-1 text-sm font-semibold text-ink-1">
                    {session ? session.patient_label : "No intake session started"}
                  </p>
                  <p className="mt-1 text-sm leading-6 text-ink-3">
                    {session
                      ? `${openCount} open prompt${openCount === 1 ? "" : "s"} remain. ${selectedGap ? `Current focus: ${selectedGap.title}.` : ""}`
                      : "Choose the evidence posture on the right, then start the guided intake."}
                  </p>
                </div>
                {session && (
                  <div className="min-w-[220px]">
                    <div className="h-2 rounded-full bg-surface-3">
                      <div
                        className="h-2 rounded-full bg-action transition-all"
                        style={{ width: `${Math.max(progressPercent, 8)}%` }}
                      />
                    </div>
                    <p className="mt-2 text-xs text-ink-3">
                      Source posture: <span className="font-semibold text-ink-1">{session.source_posture}</span>
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>

          <aside className="rounded-[10px] border border-line-1 bg-surface-1 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-action">Session setup</p>
                <h2 className="mt-1 text-lg font-semibold text-ink-1">Choose evidence posture</h2>
              </div>
              <UserRound size={18} className="mt-1 text-action" />
            </div>
            <p className="mt-2 text-sm leading-6 text-ink-3">
              Start the intake against the selected patient, the synthetic walkthrough, or the private local record.
            </p>

            <label className="mt-4 block text-sm font-semibold text-ink-1">
              Source mode
              <select
                value={sourceMode}
                onChange={(event) => setSourceMode(event.target.value as PatientContextSourceMode)}
                className="mt-2 w-full rounded-[6px] border border-line-1 bg-surface-0 px-3 py-2.5 text-sm text-ink-1 outline-none focus:border-action"
              >
                <option value="selected_patient">Selected patient</option>
                <option value="synthetic">Synthetic showcase</option>
                <option value="private_blake_cedars" disabled={!privateAvailable}>
                  Private Cedars proof-of-life{privateAvailable ? "" : " (not found locally)"}
                </option>
              </select>
            </label>

            <div className="mt-3 rounded-[10px] border border-line-1 bg-surface-0 px-3 py-3 text-sm leading-6 text-ink-3">
              <p><span className="font-semibold text-ink-1">Patient:</span> {patientId || "Loading patient list..."}</p>
              <p><span className="font-semibold text-ink-1">Selected mode:</span> {sourceModeCopy[sourceMode].label}</p>
              <p><span className="font-semibold text-ink-1">Private source:</span> {privateAvailable ? "Available locally" : "Not detected"}</p>
            </div>
            <p className="mt-3 text-xs leading-5 text-ink-3">{sourceModeCopy[sourceMode].detail}</p>

            <button
              onClick={() => createMutation.mutate()}
              disabled={!patientId || createMutation.isPending}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-[6px] bg-action px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-action-hover disabled:cursor-not-allowed disabled:bg-surface-3 disabled:text-ink-3"
            >
              <ClipboardList size={16} />
              {createMutation.isPending ? "Starting intake..." : session ? "Restart intake session" : "Start guided intake"}
            </button>
            {createMutation.isError && (
              <p className="mt-3 rounded-[10px] border border-critical-line bg-critical-tint px-3 py-3 text-sm text-critical">
                {errorText(createMutation.error)}
              </p>
            )}
          </aside>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)_320px]">
        <aside className="space-y-4">
          <section className="rounded-[10px] border border-line-1 bg-surface-0 shadow-[var(--shadow-1)]">
            <div className="flex items-center justify-between gap-3 border-b border-line-1 px-4 py-3">
              <div>
                <h2 className="text-sm font-semibold text-ink-1">Session map</h2>
                <p className="mt-1 text-xs leading-5 text-ink-3">Review gaps in order and move to the next open question.</p>
              </div>
              <CheckCircle2 size={16} className="text-action" />
            </div>
            <div className="space-y-2 p-3">
              {(session?.gap_cards ?? []).map((gap, index) => {
                const isActive = activeGapId === gap.id;
                return (
                  <button
                    key={gap.id}
                    onClick={() => setSelectedGapId(gap.id)}
                    className={cls(
                      "w-full rounded-[10px] border px-3 py-3 text-left transition-colors",
                      isActive
                        ? "border-action-line bg-action-tint"
                        : "border-line-1 bg-surface-0 hover:bg-surface-1",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-action">
                          Step {index + 1} · {categoryLabels[gap.category]}
                        </p>
                        <p className="mt-1 text-sm font-semibold text-ink-1">{gap.title}</p>
                      </div>
                      <span className={cls("rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em]", statusStyle(gap.status))}>
                        {gap.status}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-5 text-ink-3">{gap.why_it_matters}</p>
                    {gap.evidence.length > 0 && (
                      <p className="mt-2 text-xs text-ink-3">{gap.evidence.length} evidence cue{gap.evidence.length === 1 ? "" : "s"}</p>
                    )}
                  </button>
                );
              })}
              {!session && (
                <EmptyCard>Start an intake session to generate patient-specific context gaps.</EmptyCard>
              )}
            </div>
          </section>

          <section className="rounded-[10px] border border-line-1 bg-surface-0 shadow-[var(--shadow-1)]">
            <div className="border-b border-line-1 px-4 py-3">
              <h2 className="text-sm font-semibold text-ink-1">Captured context</h2>
              <p className="mt-1 text-xs leading-5 text-ink-3">Most recent patient-reported facts that will land in the export bundle.</p>
            </div>
            <div className="space-y-2 p-3">
              {session?.facts.length ? (
                session.facts.slice(-5).reverse().map((fact) => (
                  <div key={fact.id} className="rounded-[10px] border border-line-1 bg-surface-1 px-3 py-3">
                    <p className="text-sm font-medium text-ink-1">{fact.summary}</p>
                    <p className="mt-1 text-xs text-ink-3">
                      {fact.confidence} confidence
                      {fact.linked_gap_id ? " · linked to session gap" : ""}
                    </p>
                  </div>
                ))
              ) : (
                <EmptyCard>Patient-reported context will appear here as the intake captures answers.</EmptyCard>
              )}
            </div>
          </section>
        </aside>

        <section className="rounded-[10px] border border-line-1 bg-surface-0 shadow-[var(--shadow-1)]">
          <div className="border-b border-line-1 px-5 py-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-action">Active question</p>
                <h2 className="mt-1 text-xl font-semibold text-ink-1">
                  {selectedGap ? selectedGap.title : "Clinical intake guide"}
                </h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-ink-3">
                  {selectedGap
                    ? selectedGap.prompt
                    : "Start the guided intake to move through missing records, medication reality, timeline gaps, uncertain facts, and patient goals."}
                </p>
              </div>
              {session && (
                <div className="rounded-[10px] border border-line-1 bg-surface-1 px-3 py-3 text-sm text-ink-3">
                  <p className="font-semibold text-ink-1">{session.patient_label}</p>
                  <p className="mt-1">Latest activity: {latestTurn ? formatDateTime(latestTurn.created_at) : "Session started"}</p>
                </div>
              )}
            </div>
            {selectedGap?.evidence.length ? (
              <div className="mt-4 rounded-[10px] border border-line-1 bg-surface-1 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">Evidence cues for this question</p>
                <ul className="mt-2 space-y-1 text-sm leading-6 text-ink-2">
                  {selectedGap.evidence.slice(0, 4).map((item) => (
                    <li key={item}>- {item}</li>
                  ))}
                </ul>
              </div>
            ) : selectedGap ? (
              <div className="mt-4 rounded-[10px] border border-line-1 bg-surface-1 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">Why this matters</p>
                <p className="mt-2 text-sm leading-6 text-ink-3">{selectedGap.why_it_matters}</p>
              </div>
            ) : null}
          </div>

          <div className="px-5 py-4">
            <div className="rounded-[10px] border border-line-1 bg-surface-1">
              <div className="border-b border-line-1 px-4 py-3">
                <div className="flex items-center gap-2">
                  <Bot size={16} className="text-action" />
                  <h3 className="text-sm font-semibold text-ink-1">Conversation</h3>
                </div>
                <p className="mt-1 text-xs leading-5 text-ink-3">Answer in plain language. Atlas stores the response as patient-reported context, not chart truth.</p>
              </div>
              <div className="max-h-[560px] space-y-3 overflow-y-auto px-4 py-4">
                {(session?.turns ?? []).map((turn) => (
                  <div key={turn.id} className={cls("flex", turn.role === "patient" ? "justify-end" : "justify-start")}>
                    <div className={cls(
                      "max-w-[85%] rounded-[10px] border px-4 py-3",
                      turn.role === "patient"
                        ? "border-action bg-action text-white"
                        : "border-line-1 bg-surface-0 text-ink-1",
                    )}>
                      <p className={cls(
                        "text-[11px] font-semibold uppercase tracking-[0.14em]",
                        turn.role === "patient" ? "text-white/70" : "text-ink-3",
                      )}>
                        {turn.role === "patient" ? "Patient response" : "Atlas intake guide"}
                      </p>
                      <p className="mt-1 text-sm leading-6">{turn.content}</p>
                      <p className={cls(
                        "mt-2 text-[11px]",
                        turn.role === "patient" ? "text-white/70" : "text-ink-4",
                      )}>
                        {formatDateTime(turn.created_at)}
                      </p>
                    </div>
                  </div>
                ))}
                {!session && (
                  <EmptyCard>The guide asks one structured question at a time after you start the session.</EmptyCard>
                )}
              </div>

              <form onSubmit={submitTurn} className="border-t border-line-1 px-4 py-4">
                <label className="block">
                  <span className="text-sm font-semibold text-ink-1">Respond to the current prompt</span>
                  <textarea
                    value={message}
                    onChange={(event) => setMessage(event.target.value)}
                    disabled={!session || turnMutation.isPending}
                    placeholder={session ? "Answer in the patient's own words..." : "Start a session to enable responses"}
                    className="mt-2 min-h-[112px] w-full resize-none rounded-[10px] border border-line-1 bg-surface-0 px-3 py-3 text-sm text-ink-1 outline-none focus:border-action disabled:bg-surface-1"
                  />
                </label>
                <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs leading-5 text-ink-3">
                    {selectedGap ? `Current focus: ${selectedGap.title}` : "No active prompt selected."}
                  </p>
                  <button
                    type="submit"
                    disabled={!session || !message.trim() || turnMutation.isPending}
                    className="inline-flex items-center justify-center gap-2 rounded-[6px] bg-action px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-action-hover disabled:cursor-not-allowed disabled:bg-surface-3 disabled:text-ink-3"
                    aria-label="Send patient context answer"
                  >
                    <Send size={16} />
                    {turnMutation.isPending ? "Saving answer..." : "Save answer"}
                  </button>
                </div>
              </form>
            </div>
            {turnMutation.isError && (
              <p className="mt-3 rounded-[10px] border border-critical-line bg-critical-tint px-3 py-3 text-sm text-critical">
                {errorText(turnMutation.error)}
              </p>
            )}
          </div>
        </section>

        <aside className="space-y-4">
          <section className="rounded-[10px] border border-line-1 bg-surface-0 shadow-[var(--shadow-1)]">
            <div className="flex items-start justify-between gap-3 border-b border-line-1 px-4 py-3">
              <div>
                <h2 className="text-sm font-semibold text-ink-1">Export bundle</h2>
                <p className="mt-1 text-xs leading-5 text-ink-3">Portable Markdown files for clinicians and downstream agents.</p>
              </div>
              <Download size={16} className="mt-1 text-action" />
            </div>
            <div className="p-4">
              <button
                onClick={() => exportMutation.mutate()}
                disabled={!session || exportMutation.isPending}
                className="inline-flex w-full items-center justify-center gap-2 rounded-[6px] bg-ink-1 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-ink-2 disabled:cursor-not-allowed disabled:bg-surface-3 disabled:text-ink-3"
              >
                <FileText size={16} />
                {exportMutation.isPending ? "Generating bundle..." : "Generate Markdown bundle"}
              </button>
              {exportMutation.isError && (
                <p className="mt-3 rounded-[10px] border border-critical-line bg-critical-tint px-3 py-3 text-sm text-critical">
                  {errorText(exportMutation.error)}
                </p>
              )}
              <div className="mt-4 rounded-[10px] border border-line-1 bg-surface-1 px-3 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">Bundle files</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {files.map((file) => (
                    <span key={file} className="rounded-full border border-line-1 bg-surface-0 px-2.5 py-1 text-xs font-semibold text-ink-1">
                      {file}
                    </span>
                  ))}
                </div>
              </div>
              <div className="mt-4 rounded-[10px] border border-line-1 bg-[#0f172a] px-4 py-4 text-xs leading-5 text-[#e5e7eb]">
                <pre className="max-h-[280px] overflow-auto whitespace-pre-wrap break-words font-mono">
                  {exportPreview || "# Patient Context\n\nGenerate the bundle to preview the portable Markdown output."}
                </pre>
              </div>
            </div>
          </section>

          <section className="rounded-[10px] border border-line-1 bg-surface-0 shadow-[var(--shadow-1)]">
            <div className="flex items-center gap-2 border-b border-line-1 px-4 py-3">
              <LockKeyhole size={16} className="text-action" />
              <h2 className="text-sm font-semibold text-ink-1">Privacy and separation</h2>
            </div>
            <div className="space-y-3 p-4 text-sm leading-6 text-ink-3">
              <p>Patient answers are stored as local context artifacts. They do not overwrite the verified chart or the published Atlas record.</p>
              <p>Use this space for the facts that matter clinically but are missing, ambiguous, or out of date in the source record.</p>
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}
