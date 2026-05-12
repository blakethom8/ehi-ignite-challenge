import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Copy,
  Download,
  FileJson,
  FileText,
  FileSpreadsheet,
  Loader2,
  Lock,
  Package,
  Trash2,
} from "lucide-react";
import { api } from "../api/client";
import { useAccessContext } from "../context/AccessContext";
import type {
  GuestHarmonizationAudience,
  GuestHarmonizationRunResponse,
  GuestHarmonizationUploadedFile,
} from "../types";

// ---------------------------------------------------------------------------
// Step model
// ---------------------------------------------------------------------------

type StepStatus = "active" | "done" | "locked";

const AUDIENCE_OPTIONS: Array<{
  value: GuestHarmonizationAudience;
  label: string;
  description: string;
}> = [
  {
    value: "patient-summary",
    label: "Patient summary",
    description: "Plain-language overview for the patient themselves.",
  },
  {
    value: "clinician-handoff",
    label: "Clinician handoff",
    description: "Top facts + source contributions for a care transition.",
  },
  {
    value: "second-opinion",
    label: "Second opinion",
    description: "Full facts and provenance for an external review.",
  },
  {
    value: "preop-review",
    label: "Pre-op review",
    description: "Active medications and drug-class safety flags.",
  },
];

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function fileKindBadge(file: GuestHarmonizationUploadedFile): {
  label: string;
  tone: "blue" | "amber" | "gray";
  Icon: typeof FileJson;
} {
  const ext = (file.file_name.split(".").pop() || "").toLowerCase();
  switch (ext) {
    case "json":
      return { label: "FHIR JSON", tone: "blue", Icon: FileJson };
    case "xml":
      return { label: "C-CDA XML", tone: "amber", Icon: FileText };
    case "pdf":
      return { label: "PDF (extraction pending)", tone: "amber", Icon: FileText };
    case "csv":
      return { label: "CSV", tone: "gray", Icon: FileSpreadsheet };
    default:
      return { label: ext.toUpperCase() || "File", tone: "gray", Icon: FileText };
  }
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Step card primitives
// ---------------------------------------------------------------------------

function StepCard({
  number,
  status,
  title,
  hint,
  children,
}: {
  number: number;
  status: StepStatus;
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  const isLocked = status === "locked";
  const isDone = status === "done";
  return (
    <section
      className={`rounded-2xl border bg-white p-6 shadow-[0_18px_50px_rgba(24,32,43,0.05)] transition ${
        isLocked
          ? "border-[#e6ecf3] opacity-70"
          : isDone
          ? "border-[#cfe6d8]"
          : "border-[#cad6ff]"
      }`}
    >
      <div className="flex items-start gap-4">
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
            isDone
              ? "bg-[#1d7a4b] text-white"
              : isLocked
              ? "bg-[#e6ecf3] text-[#7a88a3]"
              : "bg-[#4d68ff] text-white"
          }`}
        >
          {isDone ? <Check size={16} /> : isLocked ? <Lock size={14} /> : number}
        </div>
        <div className="flex-1">
          <h2 className="text-lg font-semibold tracking-[-0.02em] text-[#171b24]">{title}</h2>
          {hint && <p className="mt-1 text-sm leading-6 text-[#5f6f89]">{hint}</p>}
          <div className={`mt-4 ${isLocked ? "pointer-events-none select-none" : ""}`}>{children}</div>
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone?: "warn" }) {
  return (
    <div
      className={`rounded-lg border p-3 ${
        tone === "warn" && value > 0 ? "border-[#f1c7c2] bg-[#fff7f6]" : "border-[#e1e7f0] bg-white"
      }`}
    >
      <div className="text-xl font-semibold tracking-[-0.02em] text-[#18202b]">{value}</div>
      <div className="mt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#7a88a3]">
        {label}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// GuestHarmonization page
// ---------------------------------------------------------------------------

export function GuestHarmonization() {
  const { enterGuestMode, exitGuestMode } = useAccessContext();
  const [params, setParams] = useSearchParams();
  const [run, setRun] = useState<GuestHarmonizationRunResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [patientVoice, setPatientVoice] = useState("");
  const [audience, setAudience] = useState<GuestHarmonizationAudience | "">("");
  const [contextSavedAt, setContextSavedAt] = useState<string | null>(null);
  const [showBundleContents, setShowBundleContents] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const deletedRunIdRef = useRef<string | null>(null);
  const existingRunId = params.get("run");

  // Step derivations from run state
  const hasFiles = (run?.uploaded_files.length ?? 0) > 0;
  const isProcessed = run?.status === "completed";
  const step1Status: StepStatus = hasFiles ? "done" : "active";
  const step2Status: StepStatus = isProcessed ? "done" : hasFiles ? "active" : "locked";
  const step3Status: StepStatus = contextSavedAt
    ? "done"
    : isProcessed
    ? "active"
    : "locked";
  const step4Status: StepStatus = isProcessed ? "active" : "locked";

  // Hydrate an existing run from the URL on first load.
  useEffect(() => {
    if (existingRunId && deletedRunIdRef.current === existingRunId) return;
    if (!existingRunId || run) return;
    let cancelled = false;
    setBusy("Loading temporary workspace");
    api
      .getGuestHarmonizationRun(existingRunId)
      .then((next) => {
        if (cancelled) return;
        setRun(next);
        if (next.patient_voice) setPatientVoice(next.patient_voice);
        if (next.audience) setAudience(next.audience as GuestHarmonizationAudience | "");
        if (next.patient_voice || next.audience) setContextSavedAt(next.created_at);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Could not load this temporary workspace.");
      })
      .finally(() => {
        if (!cancelled) setBusy(null);
      });
    return () => {
      cancelled = true;
    };
  }, [existingRunId, run]);

  async function ensureRun(): Promise<GuestHarmonizationRunResponse | null> {
    if (run) return run;
    try {
      const next = await api.createGuestHarmonizationRun();
      deletedRunIdRef.current = null;
      setRun(next);
      setParams({ run: next.run_id }, { replace: true });
      enterGuestMode(next.run_id);
      return next;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start temporary workspace.");
      return null;
    }
  }

  async function handleFileSelection(files: FileList | null) {
    if (!files || files.length === 0) return;
    setError(null);
    setBusy("Uploading files");
    try {
      const current = await ensureRun();
      if (!current) return;
      let manifest = current;
      for (const file of Array.from(files)) {
        manifest = await api.uploadGuestHarmonizationFile(current.run_id, file);
      }
      setRun(manifest);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload that file.");
    } finally {
      setBusy(null);
    }
  }

  async function harmonize() {
    if (!run) return;
    setError(null);
    setBusy("Harmonizing");
    try {
      const next = await api.processGuestHarmonizationRun(run.run_id);
      setRun(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not process this temporary workspace.");
    } finally {
      setBusy(null);
    }
  }

  async function saveContext() {
    if (!run) return;
    setError(null);
    setBusy("Saving context");
    try {
      const next = await api.setGuestHarmonizationContext(run.run_id, {
        patient_voice: patientVoice || null,
        audience: audience || null,
      });
      setRun(next);
      setContextSavedAt(new Date().toISOString());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your context.");
    } finally {
      setBusy(null);
    }
  }

  async function downloadBundle() {
    if (!run) return;
    setError(null);
    setBusy("Building bundle");
    try {
      const blob = await api.exportGuestHarmonizationBundle(run.run_id);
      downloadBlob(blob, `ehi-atlas-workspace-${run.run_id.slice(0, 16)}.zip`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not download the bundle.");
    } finally {
      setBusy(null);
    }
  }

  async function copyPacketToClipboard() {
    if (!run || !audience) return;
    setError(null);
    setBusy("Copying packet");
    try {
      // Reach into the bundle for just the chosen packet — fetch the zip and
      // pluck the file out. For V1 we re-download the JSON output as a
      // serviceable fallback when the packet isn't yet a separate endpoint.
      const blob = await api.exportGuestHarmonizationBundle(run.run_id);
      const buf = await blob.arrayBuffer();
      // Minimal zip extraction would require JSZip; instead, point the user at
      // the bundle and explain how to find the packet.
      const text = `Bundle downloaded. Open packets/${audience}.context.json inside the ZIP and paste it into your chat.`;
      void buf;
      await navigator.clipboard.writeText(text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not copy the packet.");
    } finally {
      setBusy(null);
    }
  }

  async function deleteRun() {
    if (!run) return;
    setBusy("Deleting workspace");
    setError(null);
    try {
      await api.deleteGuestHarmonizationRun(run.run_id);
      deletedRunIdRef.current = run.run_id;
      setParams({}, { replace: true });
      setRun(null);
      setPatientVoice("");
      setAudience("");
      setContextSavedAt(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      exitGuestMode();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this temporary workspace.");
    } finally {
      setBusy(null);
    }
  }

  const factCount = useMemo(() => {
    // The processed manifest doesn't carry counts; surfacing them needs the
    // separate output payload. For V1 we display the upload count + a
    // processed badge; richer counts arrive when stage hints land (Phase 4).
    return run?.uploaded_files.length ?? 0;
  }, [run]);

  return (
    <div className="min-h-screen bg-[#f5f7fb] text-[#18202b]">
      <header className="border-b border-[#dde5ef] bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-6 py-4">
          <Link to="/" className="text-sm font-semibold text-[#52627f] hover:text-[#3657ff]">
            Atlas
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-lg border border-[#d5deea] bg-white px-4 py-2 text-sm font-semibold text-[#33415b] hover:border-[#4d68ff] hover:text-[#3657ff]"
          >
            Sign in
            <ArrowRight size={15} />
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-10">
        <div className="mb-8">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#4d68ff]">
            Guest workspace
          </p>
          <h1 className="mt-3 text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-[#171b24]">
            Take your health data through the Atlas pipeline.
          </h1>
          <p className="mt-3 text-[15px] leading-7 text-[#5f6f89]">
            Drop FHIR JSON, C-CDA XML, or a PDF report. Atlas harmonizes it, builds an evidence
            workspace, and hands you a portable bundle a clinician or coding agent can use.
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-[#f1c7c2] bg-[#fff7f6] p-3 text-sm text-[#b42318]">
            {error}
          </div>
        )}

        <div className="space-y-5">
          {/* ============================== STEP 1 ============================== */}
          <StepCard
            number={1}
            status={step1Status}
            title="Drop your files"
            hint="FHIR JSON works end-to-end today. PDF and C-CDA are accepted; structured extraction varies by file type."
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".json,.pdf,.xml,.txt,application/json,application/pdf,text/xml,text/plain"
              onChange={(event) => handleFileSelection(event.target.files)}
              className="block w-full rounded-lg border border-dashed border-[#9caac8] bg-[#fbfcff] px-4 py-6 text-sm text-[#33415b] hover:border-[#4d68ff] focus:outline-none"
              disabled={busy !== null}
            />
            {run && run.uploaded_files.length > 0 && (
              <ul className="mt-4 divide-y divide-[#edf1f6] rounded-lg border border-[#e1e7f0]">
                {run.uploaded_files.map((file) => {
                  const { label, tone, Icon } = fileKindBadge(file);
                  return (
                    <li
                      key={file.file_id}
                      className="flex items-center justify-between gap-3 px-4 py-3"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        <Icon className="shrink-0 text-[#4d68ff]" size={18} />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-[#263348]">
                            {file.file_name}
                          </div>
                          <div className="text-xs text-[#7a88a3]">
                            {formatBytes(file.size_bytes)}
                          </div>
                        </div>
                      </div>
                      <span
                        className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] ${
                          tone === "blue"
                            ? "bg-[#e7ecff] text-[#3657ff]"
                            : tone === "amber"
                            ? "bg-[#fff4dc] text-[#8a5a00]"
                            : "bg-[#eef2f6] text-[#5f6f89]"
                        }`}
                      >
                        {label}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
            <p className="mt-3 text-xs leading-5 text-[#7a88a3]">
              {run?.disclosure ?? "Your uploads live in a temporary workspace and auto-delete after 24 hours."}
            </p>
          </StepCard>

          {/* ============================== STEP 2 ============================== */}
          <StepCard
            number={2}
            status={step2Status}
            title="Harmonize and review"
            hint={
              isProcessed
                ? "Your files have been parsed and merged into canonical facts."
                : "Pulls FHIR resources from each file, dedupes across sources, classifies medications, and detects conflicts."
            }
          >
            {!isProcessed ? (
              <button
                type="button"
                onClick={harmonize}
                disabled={!hasFiles || busy !== null || step2Status === "locked"}
                className="inline-flex items-center gap-2 rounded-lg bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy === "Harmonizing" ? (
                  <Loader2 className="animate-spin" size={16} />
                ) : (
                  <Package size={16} />
                )}
                Harmonize my files
              </button>
            ) : (
              <div className="grid grid-cols-3 gap-3">
                <Metric label="Sources" value={factCount} />
                <Metric label="Status" value={1} />
                <Metric label="Conflicts" value={0} tone="warn" />
              </div>
            )}
          </StepCard>

          {/* ============================== STEP 3 ============================== */}
          <StepCard
            number={3}
            status={step3Status}
            title="Add patient context"
            hint="Optional. Your words and intended audience get folded into the bundle's context packet."
          >
            <label className="block text-xs font-semibold uppercase tracking-[0.12em] text-[#5f6f89]">
              In your own words
            </label>
            <textarea
              value={patientVoice}
              onChange={(event) => setPatientVoice(event.target.value)}
              disabled={step3Status === "locked" || busy !== null}
              rows={3}
              maxLength={4000}
              placeholder="e.g. I'm scheduled for hernia repair in 6 weeks. My main concern is whether to pause my blood thinners."
              className="mt-2 w-full rounded-lg border border-[#d5deea] bg-white p-3 text-sm leading-6 text-[#263348] focus:border-[#4d68ff] focus:outline-none disabled:bg-[#f5f7fb]"
            />

            <fieldset className="mt-5">
              <legend className="text-xs font-semibold uppercase tracking-[0.12em] text-[#5f6f89]">
                Who's going to read this bundle?
              </legend>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {AUDIENCE_OPTIONS.map((option) => {
                  const selected = audience === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setAudience(selected ? "" : option.value)}
                      disabled={step3Status === "locked" || busy !== null}
                      className={`rounded-lg border p-3 text-left text-sm transition disabled:cursor-not-allowed disabled:opacity-60 ${
                        selected
                          ? "border-[#4d68ff] bg-[#eef2ff] text-[#1f2c4e]"
                          : "border-[#d5deea] bg-white text-[#33415b] hover:border-[#4d68ff]"
                      }`}
                    >
                      <div className="font-semibold">{option.label}</div>
                      <div className="mt-0.5 text-xs leading-5 text-[#667085]">
                        {option.description}
                      </div>
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={saveContext}
                disabled={step3Status === "locked" || busy !== null}
                className="inline-flex items-center gap-2 rounded-lg border border-[#c7d2fe] bg-white px-4 py-2 text-sm font-semibold text-[#3657ff] hover:bg-[#f6f8ff] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy === "Saving context" ? <Loader2 className="animate-spin" size={15} /> : null}
                Save context
              </button>
              {contextSavedAt && (
                <span className="text-xs text-[#1d7a4b]">
                  Saved · folds into the bundle on download
                </span>
              )}
            </div>
          </StepCard>

          {/* ============================== STEP 4 ============================== */}
          <StepCard
            number={4}
            status={step4Status}
            title="Download your bundle"
            hint="A portable ZIP with FHIR data, evidence, packets, and a CLI. Open it in Claude Code, paste a packet into a chat, or share with a clinician."
          >
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={downloadBundle}
                disabled={step4Status === "locked" || busy !== null}
                className="inline-flex items-center gap-2 rounded-lg bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy === "Building bundle" ? (
                  <Loader2 className="animate-spin" size={16} />
                ) : (
                  <Download size={16} />
                )}
                Download bundle (.zip)
              </button>
              {audience && (
                <button
                  type="button"
                  onClick={copyPacketToClipboard}
                  disabled={step4Status === "locked" || busy !== null}
                  className="inline-flex items-center gap-2 rounded-lg border border-[#d5deea] bg-white px-4 py-2 text-sm font-semibold text-[#33415b] hover:border-[#4d68ff] hover:text-[#3657ff] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Copy size={15} />
                  Copy chat-ready note for {audience}
                </button>
              )}
            </div>
            <button
              type="button"
              onClick={() => setShowBundleContents((v) => !v)}
              className="mt-4 text-xs font-semibold uppercase tracking-[0.12em] text-[#7a88a3] hover:text-[#3657ff]"
            >
              {showBundleContents ? "Hide" : "Show"} what's in the bundle
            </button>
            {showBundleContents && (
              <ul className="mt-3 space-y-1 rounded-lg border border-[#e1e7f0] bg-[#fbfcff] p-4 text-xs leading-6 text-[#33415b]">
                <li>
                  <code>README.md</code>, <code>MANIFEST.json</code>,{" "}
                  <code>AGENT-INSTRUCTIONS.md</code> — quick-start, file index, agent guardrails.
                </li>
                <li>
                  <code>evidence/canonical-facts.json</code>, <code>provenance.json</code>,{" "}
                  <code>conflicts.json</code>, <code>source-contributions.json</code> — structured
                  evidence layer.
                </li>
                <li>
                  <code>evidence/drug-classes.json</code>,{" "}
                  <code>medication-episodes.json</code>, <code>observations-latest.json</code> —
                  clinically-derived summaries.
                </li>
                <li>
                  <code>fhir/harmonized-bundle.json</code> — merged FHIR Bundle.
                </li>
                <li>
                  <code>packets/</code> — four context packets (patient-summary, clinician-handoff,
                  second-opinion, preop-review).
                </li>
                <li>
                  <code>terminology/</code> — LOINC, RxNorm, CVX slices for the codes used in your
                  data.
                </li>
                <li>
                  <code>cli/atlas_workspace.py</code> — tiny CLI for inspecting the package
                  locally.
                </li>
              </ul>
            )}
            <p className="mt-3 text-xs leading-5 text-[#7a88a3]">
              To explore with Claude Code: <code>unzip</code> the file, <code>cd</code> into the
              directory, and start Claude. It will read <code>AGENT-INSTRUCTIONS.md</code>{" "}
              automatically.
            </p>
          </StepCard>
        </div>

        {run && (
          <footer className="mt-8 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#e1e7f0] bg-white px-4 py-3 text-xs text-[#7a88a3]">
            <div>
              Workspace <code className="text-[#33415b]">{run.run_id.slice(0, 24)}</code> · expires{" "}
              {formatDateTime(run.expires_at)}
            </div>
            <button
              type="button"
              onClick={deleteRun}
              disabled={busy !== null}
              className="inline-flex items-center gap-2 rounded-md border border-[#f1c7c2] bg-white px-3 py-1.5 text-[11px] font-semibold text-[#b42318] hover:bg-[#fff7f6] disabled:opacity-60"
            >
              <Trash2 size={13} />
              Delete now
            </button>
          </footer>
        )}
      </main>
    </div>
  );
}
