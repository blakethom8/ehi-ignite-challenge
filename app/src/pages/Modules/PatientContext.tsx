import { useEffect, useMemo, useState } from "react";
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

function statusStyle(status: PatientContextGapCard["status"]): string {
  if (status === "answered") return "bg-emerald-100 text-emerald-800";
  if (status === "skipped") return "bg-slate-100 text-slate-500";
  return "bg-amber-100 text-amber-800";
}

function errorText(error: unknown): string {
  if (error && typeof error === "object" && "response" in error) {
    const maybe = error as { response?: { data?: { detail?: string } } };
    if (maybe.response?.data?.detail) return maybe.response.data.detail;
  }
  if (error instanceof Error) return error.message;
  return "Request failed.";
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

  useEffect(() => {
    if (!selectedGapId && session?.gap_cards.length) {
      const open = session.gap_cards.find((gap) => gap.status === "open");
      setSelectedGapId(open?.id || session.gap_cards[0].id);
    }
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
    mutationFn: () => api.sendPatientContextTurn(session!.session_id, message, selectedGapId),
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
    () => session?.gap_cards.find((gap) => gap.id === selectedGapId) || null,
    [session, selectedGapId],
  );

  const answeredCount = session?.gap_cards.filter((gap) => gap.status === "answered").length ?? 0;
  const totalCount = session?.gap_cards.length ?? 0;
  const privateAvailable = statusQuery.data?.private_blake_cedars_available ?? false;

  function submitTurn(event: FormEvent) {
    event.preventDefault();
    if (!session || !message.trim() || turnMutation.isPending) return;
    turnMutation.mutate();
  }

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-2xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <MessageSquareText size={13} />
              Patient Context
            </p>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
              Guided intake for the story the chart cannot tell
            </h1>
            <p className="mt-3 max-w-4xl text-base leading-7 text-[#667085]">
              A clinical-intake agent walks through missing sources, medication reality, timeline gaps, uncertain facts,
              and patient goals. Answers stay separate as patient-reported context and export as portable Markdown.
            </p>
          </div>
          <div className="min-w-[280px] rounded-2xl bg-[#f7f8ff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <div className="flex items-center gap-2">
              <LockKeyhole size={18} className="text-[#5b76fe]" />
              <p className="text-sm font-semibold text-[#1c1c1e]">Privacy posture</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              Patient answers are local context artifacts. They do not update the verified chart or Atlas gold record.
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-[#1c1c1e]">Start context session</h2>
              <p className="mt-1 text-sm leading-6 text-[#667085]">
                Choose the evidence posture before the intake begins.
              </p>
            </div>
            <UserRound size={20} className="text-[#5b76fe]" />
          </div>

          <div className="mt-4 grid gap-3">
            <label className="text-sm font-semibold text-[#1c1c1e]">
              Source mode
              <select
                value={sourceMode}
                onChange={(event) => setSourceMode(event.target.value as PatientContextSourceMode)}
                className="mt-2 w-full rounded-xl border border-[#dfe4ea] bg-white px-3 py-2 text-sm"
              >
                <option value="selected_patient">Selected patient</option>
                <option value="synthetic">Synthetic showcase</option>
                <option value="private_blake_cedars" disabled={!privateAvailable}>
                  Private Cedars proof-of-life{privateAvailable ? "" : " (not found locally)"}
                </option>
              </select>
            </label>

            <div className="rounded-xl bg-[#fafbff] p-3 text-sm leading-6 text-[#667085]">
              <p><span className="font-semibold text-[#1c1c1e]">Patient:</span> {patientId || "Loading patient list..."}</p>
              <p><span className="font-semibold text-[#1c1c1e]">Private source:</span> {privateAvailable ? "Available locally" : "Not detected"}</p>
            </div>

            <button
              onClick={() => createMutation.mutate()}
              disabled={!patientId || createMutation.isPending}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#5b76fe] px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              <ClipboardList size={16} />
              {createMutation.isPending ? "Starting..." : session ? "Restart intake" : "Start guided intake"}
            </button>
            {createMutation.isError && (
              <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{errorText(createMutation.error)}</p>
            )}
          </div>
        </div>

        <div className="rounded-2xl bg-[#f7fffc] p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <FileText size={18} className="text-[#0f766e]" />
            <h2 className="text-lg font-semibold text-[#0f172a]">Live context preview</h2>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <div className="rounded-xl bg-white p-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Progress</p>
              <p className="mt-1 text-2xl font-semibold text-[#1c1c1e]">{answeredCount}/{totalCount || 5}</p>
            </div>
            <div className="rounded-xl bg-white p-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Facts</p>
              <p className="mt-1 text-2xl font-semibold text-[#1c1c1e]">{session?.facts.length ?? 0}</p>
            </div>
            <div className="rounded-xl bg-white p-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Export</p>
              <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                {session?.export_status.generated ? "Generated" : "Not generated"}
              </p>
            </div>
          </div>
          <div className="mt-4 rounded-xl bg-white p-4">
            {session?.facts.length ? (
              <ul className="space-y-2 text-sm leading-6 text-[#35524d]">
                {session.facts.slice(-4).map((fact) => (
                  <li key={fact.id}>- {fact.summary}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm leading-6 text-[#667085]">
                Patient-reported context will appear here as the guided intake captures answers.
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[0.85fr_1.15fr_0.9fr]">
        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-[#1c1c1e]">Adaptive checklist</h2>
            <CheckCircle2 size={18} className="text-[#5b76fe]" />
          </div>
          <div className="mt-4 space-y-3">
            {(session?.gap_cards ?? []).map((gap) => (
              <button
                key={gap.id}
                onClick={() => setSelectedGapId(gap.id)}
                className={`w-full rounded-xl border p-3 text-left transition ${
                  selectedGapId === gap.id ? "border-[#5b76fe] bg-[#f7f8ff]" : "border-[#e9eaef] bg-white hover:bg-[#fafbff]"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-semibold text-[#1c1c1e]">{gap.title}</p>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${statusStyle(gap.status)}`}>
                    {gap.status}
                  </span>
                </div>
                <p className="mt-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
                  {categoryLabels[gap.category]}
                </p>
                <p className="mt-2 text-sm leading-5 text-[#667085]">{gap.why_it_matters}</p>
              </button>
            ))}
            {!session && (
              <p className="rounded-xl bg-[#fafbff] p-4 text-sm leading-6 text-[#667085]">
                Start an intake session to generate patient-specific gap cards.
              </p>
            )}
          </div>
        </div>

        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <Bot size={18} className="text-[#5b76fe]" />
            <h2 className="text-lg font-semibold text-[#1c1c1e]">Clinical intake guide</h2>
          </div>
          <div className="mt-4 max-h-[520px] space-y-3 overflow-y-auto rounded-xl bg-[#fafbff] p-4">
            {(session?.turns ?? []).map((turn) => (
              <div key={turn.id} className={`flex ${turn.role === "patient" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                  turn.role === "patient" ? "bg-[#5b76fe] text-white" : "bg-white text-[#1c1c1e]"
                }`}>
                  {turn.content}
                </div>
              </div>
            ))}
            {!session && (
              <p className="text-sm leading-6 text-[#667085]">
                The guide will ask one structured question at a time after you start the session.
              </p>
            )}
          </div>

          {selectedGap && (
            <div className="mt-4 rounded-xl border border-[#dfe4ff] bg-[#f7f8ff] p-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Current focus</p>
              <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">{selectedGap.title}</p>
              <p className="mt-1 text-sm leading-6 text-[#667085]">{selectedGap.prompt}</p>
            </div>
          )}

          <form onSubmit={submitTurn} className="mt-4 flex gap-2">
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              disabled={!session || turnMutation.isPending}
              placeholder="Answer in your own words..."
              className="min-h-[76px] flex-1 resize-none rounded-xl border border-[#dfe4ea] px-3 py-2 text-sm outline-none focus:border-[#5b76fe]"
            />
            <button
              type="submit"
              disabled={!session || !message.trim() || turnMutation.isPending}
              className="inline-flex w-12 items-center justify-center rounded-xl bg-[#5b76fe] text-white disabled:cursor-not-allowed disabled:opacity-60"
              aria-label="Send patient context answer"
            >
              <Send size={18} />
            </button>
          </form>
          {turnMutation.isError && (
            <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700">{errorText(turnMutation.error)}</p>
          )}
        </div>

        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-[#1c1c1e]">Markdown bundle</h2>
              <p className="mt-1 text-sm leading-6 text-[#667085]">Portable context files for clinicians and future agents.</p>
            </div>
            <Download size={18} className="text-[#5b76fe]" />
          </div>
          <button
            onClick={() => exportMutation.mutate()}
            disabled={!session || exportMutation.isPending}
            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#1c1c1e] px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            <FileText size={16} />
            {exportMutation.isPending ? "Generating..." : "Generate Markdown bundle"}
          </button>
          {exportMutation.isError && (
            <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700">{errorText(exportMutation.error)}</p>
          )}
          <div className="mt-4 rounded-xl bg-[#fafbff] p-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Files</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(session?.export_status.files.length ? session.export_status.files : ["PATIENT_CONTEXT.md", "QUESTIONS.md", "SOURCES.md", "AGENT.md"]).map((file) => (
                <span key={file} className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#1c1c1e]">
                  {file}
                </span>
              ))}
            </div>
          </div>
          <pre className="mt-4 max-h-[300px] overflow-auto rounded-xl bg-[#111827] p-4 text-xs leading-5 text-[#e5e7eb]">
            {exportPreview || "# Patient Context\n\nGenerate the bundle to preview the portable Markdown output."}
          </pre>
        </div>
      </section>
    </main>
  );
}
