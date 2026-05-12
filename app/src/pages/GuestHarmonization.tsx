import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, Download, FileJson, Loader2, Trash2, Upload } from "lucide-react";
import { api } from "../api/client";
import { useAccessContext } from "../context/AccessContext";
import type { GuestHarmonizationOutputPackage, GuestHarmonizationRunResponse } from "../types";

function formatDateTime(value: string | null | undefined) {
  if (!value) return "Not available";
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

function downloadJson(fileName: string, payload: GuestHarmonizationOutputPackage) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

export function GuestHarmonization() {
  const { enterGuestMode, exitGuestMode } = useAccessContext();
  const [params, setParams] = useSearchParams();
  const [run, setRun] = useState<GuestHarmonizationRunResponse | null>(null);
  const [output, setOutput] = useState<GuestHarmonizationOutputPackage | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const deletedRunIdRef = useRef<string | null>(null);
  const existingRunId = params.get("run");
  const canProcess = Boolean(run && run.uploaded_files.length > 0 && busy === null);
  const factCount = output?.facts.length ?? 0;
  const sourceCount = output?.source_files.length ?? run?.uploaded_files.length ?? 0;
  const issueCount = output?.quality_issues.length ?? 0;
  const uploadHint = selectedFile
    ? `Selected ${selectedFile.name}. Click "Upload selected file" to add it to this workspace.`
    : "Choose a JSON, PDF, XML, or TXT file, then upload it into this temporary workspace.";

  const statusLabel = useMemo(() => {
    if (!run) return "Not started";
    if (run.status === "completed") return "Output ready";
    if (run.status === "processing") return "Processing";
    if (run.status === "expired") return "Expired";
    if (run.uploaded_files.length > 0) return "Ready to process";
    return "Temporary workspace ready";
  }, [run]);

  useEffect(() => {
    if (existingRunId && deletedRunIdRef.current === existingRunId) return;
    if (!existingRunId || run) return;
    let cancelled = false;
    setBusy("Loading temporary workspace");
    api.getGuestHarmonizationRun(existingRunId)
      .then((next) => {
        if (!cancelled) setRun(next);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load this temporary workspace.");
      })
      .finally(() => {
        if (!cancelled) setBusy(null);
      });
    return () => {
      cancelled = true;
    };
  }, [existingRunId, run]);

  useEffect(() => {
    if (!existingRunId || !run || output || run.status !== "completed" || run.outputs.length === 0) return;
    let cancelled = false;
    api.getGuestHarmonizationOutput(existingRunId)
      .then((payload) => {
        if (!cancelled) setOutput(payload);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Temporary workspace loaded, but the portable output could not be restored.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [existingRunId, output, run]);

  async function startRun() {
    setBusy("Starting temporary workspace");
    setError(null);
    setOutput(null);
    try {
      const next = await api.createGuestHarmonizationRun();
      deletedRunIdRef.current = null;
      setRun(next);
      setParams({ run: next.run_id }, { replace: true });
      // Flip AccessContext to the guest mode so capabilities + persistence
      // namespaces follow suit. The guest cookie is already set by the API.
      enterGuestMode(next.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start temporary workspace.");
    } finally {
      setBusy(null);
    }
  }

  async function uploadFile() {
    if (!run || !selectedFile) return;
    setBusy("Uploading file");
    setError(null);
    try {
      const next = await api.uploadGuestHarmonizationFile(run.run_id, selectedFile);
      setRun(next);
      setSelectedFile(null);
      setOutput(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not upload that file.");
    } finally {
      setBusy(null);
    }
  }

  async function processRun() {
    if (!run) return;
    setBusy("Building portable output");
    setError(null);
    try {
      const next = await api.processGuestHarmonizationRun(run.run_id);
      const payload = await api.getGuestHarmonizationOutput(run.run_id);
      setRun(next);
      setOutput(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not process this temporary workspace.");
    } finally {
      setBusy(null);
    }
  }

  async function deleteRun() {
    if (!run) return;
    setBusy("Deleting temporary workspace");
    setError(null);
    try {
      await api.deleteGuestHarmonizationRun(run.run_id);
      deletedRunIdRef.current = run.run_id;
      setParams({}, { replace: true });
      setRun(null);
      setOutput(null);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      // Drop back to anonymous; the guest cookie has been revoked server-side
      // and we want capabilities to refetch.
      exitGuestMode();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this temporary workspace.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="min-h-screen bg-[#f5f7fb] text-[#18202b]">
      <header className="border-b border-[#dde5ef] bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-5">
          <Link to="/" className="text-sm font-semibold text-[#52627f] hover:text-[#3657ff]">
            Atlas
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-lg border border-[#d5deea] bg-white px-4 py-2 text-sm font-semibold text-[#33415b] hover:border-[#4d68ff] hover:text-[#3657ff]"
          >
            Explore sample demo
            <ArrowRight size={15} />
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-10">
        <section className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#4d68ff]">
              Guest harmonization
            </p>
            <h1 className="mt-4 text-5xl font-semibold leading-[0.98] tracking-[-0.04em] text-[#171b24]">
              Try Atlas with your own files.
            </h1>
            <p className="mt-5 text-lg leading-8 text-[#5f6f89]">
              Upload health-record files, preview the structured output, and download a portable harmonized record without creating an account.
            </p>
            <div className="mt-6 rounded-lg border border-[#cad6ff] bg-white p-4 text-sm leading-6 text-[#3e4d68]">
              {run?.disclosure ?? "Guest uploads are processed in a temporary workspace and automatically deleted. Download your output or create an account to save your workspace."}
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              {!run ? (
                <button
                  type="button"
                  onClick={startRun}
                  disabled={busy !== null}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {busy ? <Loader2 className="animate-spin" size={16} /> : <Upload size={16} />}
                  Start temporary workspace
                </button>
              ) : (
                <button
                  type="button"
                  onClick={deleteRun}
                  disabled={busy !== null}
                  className="inline-flex items-center gap-2 rounded-lg border border-[#f1c7c2] bg-white px-5 py-3 text-sm font-semibold text-[#b42318] hover:bg-[#fff7f6] disabled:cursor-not-allowed disabled:opacity-70"
                >
                  <Trash2 size={16} />
                  Delete workspace
                </button>
              )}
              <Link
                to="/"
                className="inline-flex items-center gap-2 rounded-lg border border-[#d5deea] bg-white px-5 py-3 text-sm font-semibold text-[#33415b] hover:border-[#4d68ff] hover:text-[#3657ff]"
              >
                Log in / Sign up
              </Link>
            </div>
          </div>

          <div className="rounded-lg border border-[#d8e0eb] bg-white p-5 shadow-[0_18px_50px_rgba(24,32,43,0.06)]">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#edf1f6] pb-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7a88a3]">
                  Status
                </p>
                <h2 className="mt-1 text-2xl font-semibold tracking-[-0.03em]">{statusLabel}</h2>
              </div>
              {run && (
                <div className="text-right text-xs font-medium leading-5 text-[#667085]">
                  <div>{run.run_id}</div>
                  <div>Expires {formatDateTime(run.expires_at)}</div>
                </div>
              )}
            </div>

            {error && (
              <div className="mt-4 rounded-lg border border-[#f1c7c2] bg-[#fff7f6] p-3 text-sm text-[#b42318]">
                {error}
              </div>
            )}

            {run && (
              <div className="mt-5 grid gap-5">
                <div className="rounded-lg border border-[#e1e7f0] bg-[#fbfcff] p-4">
                  <label
                    htmlFor="guest-harmonization-file"
                    className="block text-xs font-semibold uppercase tracking-[0.14em] text-[#6f7e98]"
                  >
                    Upload file
                  </label>
                  <div className="mt-3 flex flex-col gap-3 sm:flex-row">
                    <input
                      id="guest-harmonization-file"
                      ref={fileInputRef}
                      type="file"
                      accept=".json,.pdf,.xml,.txt,application/json,application/pdf,text/xml,text/plain"
                      onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                      className="min-w-0 flex-1 rounded-lg border border-[#d5deea] bg-white px-3 py-2 text-sm"
                    />
                    <button
                      type="button"
                      onClick={uploadFile}
                      disabled={!selectedFile || busy !== null}
                      className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#18202b] px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {busy === "Uploading file" ? <Loader2 className="animate-spin" size={15} /> : <Upload size={15} />}
                      Upload selected file
                    </button>
                  </div>
                  <p className="mt-3 text-xs leading-5 text-[#667085]">
                    {uploadHint}
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <Metric label="Sources" value={sourceCount} />
                  <Metric label="Facts" value={factCount} />
                  <Metric label="Quality issues" value={issueCount} />
                </div>

                <div className="rounded-lg border border-[#e1e7f0]">
                  <div className="flex items-center justify-between border-b border-[#edf1f6] px-4 py-3">
                    <h3 className="text-sm font-semibold text-[#33415b]">Uploaded files</h3>
                    <span className="text-xs font-medium text-[#7a88a3]">{run.uploaded_files.length}</span>
                  </div>
                  <div className="divide-y divide-[#edf1f6]">
                    {run.uploaded_files.length === 0 ? (
                      <p className="px-4 py-5 text-sm text-[#667085]">
                        No files uploaded yet. Selecting a file does not upload it until you press "Upload selected file".
                      </p>
                    ) : (
                      run.uploaded_files.map((file) => (
                        <div key={file.file_id} className="flex items-center justify-between gap-4 px-4 py-3">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-[#263348]">{file.file_name}</div>
                            <div className="text-xs text-[#667085]">{file.content_type} • {formatBytes(file.size_bytes)}</div>
                          </div>
                          <FileJson className="shrink-0 text-[#4d68ff]" size={18} />
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={processRun}
                    disabled={!canProcess}
                    className="inline-flex items-center gap-2 rounded-lg bg-[#4d68ff] px-5 py-3 text-sm font-semibold text-white hover:bg-[#3c57ef] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {busy === "Building portable output" ? <Loader2 className="animate-spin" size={16} /> : <FileJson size={16} />}
                    Build output
                  </button>
                  {output && (
                    <button
                      type="button"
                      onClick={() => downloadJson("atlas-harmonized-record.json", output)}
                      className="inline-flex items-center gap-2 rounded-lg border border-[#c7d2fe] bg-white px-5 py-3 text-sm font-semibold text-[#3657ff] hover:bg-[#f6f8ff]"
                    >
                      <Download size={16} />
                      Download JSON
                    </button>
                  )}
                </div>
                {!canProcess && (
                  <p className="text-xs leading-5 text-[#667085]">
                    {selectedFile
                      ? "Finish uploading the selected file before building output."
                      : "Build output becomes available after at least one file is uploaded."}
                  </p>
                )}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-[#e1e7f0] bg-white p-4">
      <div className="text-2xl font-semibold tracking-[-0.03em] text-[#18202b]">{value}</div>
      <div className="mt-1 text-xs font-semibold uppercase tracking-[0.14em] text-[#7a88a3]">{label}</div>
    </div>
  );
}
