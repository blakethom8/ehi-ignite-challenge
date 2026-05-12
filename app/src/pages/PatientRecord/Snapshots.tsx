import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { History } from "lucide-react";
import { api } from "../../api/client";
import { SnapshotList } from "../../components/atlas/snapshots/SnapshotList";
import { NarrativeHistoryPanel } from "../../components/atlas/snapshots/NarrativeHistoryPanel";
import { SnapshotDiffModal } from "../../components/atlas/snapshots/SnapshotDiffModal";

type BundleAudience =
  | ""
  | "patient-summary"
  | "clinician-handoff"
  | "second-opinion"
  | "preop-review";

const AUDIENCE_OPTIONS: Array<{ value: BundleAudience; label: string }> = [
  { value: "", label: "No primary packet" },
  { value: "patient-summary", label: "Patient summary" },
  { value: "clinician-handoff", label: "Clinician handoff" },
  { value: "second-opinion", label: "Second opinion" },
  { value: "preop-review", label: "Pre-op review" },
];

function collectionForPatient(patientId: string | null): string | null {
  if (!patientId) return null;
  return patientId.startsWith("workspace-") ? patientId : `workspace-${patientId}`;
}

export function PatientRecordSnapshots() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const collectionId = useMemo(() => collectionForPatient(patientId), [patientId]);
  const queryClient = useQueryClient();
  const [activatingId, setActivatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [audience, setAudience] = useState<BundleAudience>("");
  const [diffSnapshotId, setDiffSnapshotId] = useState<string | null>(null);

  const publishedQuery = useQuery({
    queryKey: ["published-chart", collectionId],
    queryFn: () => (collectionId ? api.getPublishedChart(collectionId) : Promise.resolve(null)),
    enabled: !!collectionId,
  });

  const activateMutation = useMutation({
    mutationFn: (snapshotId: string) => {
      if (!collectionId) throw new Error("No collection selected.");
      return api.activatePublishedSnapshot(collectionId, snapshotId);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["published-chart", collectionId] });
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : "Could not activate snapshot.");
    },
    onSettled: () => setActivatingId(null),
  });

  const handleActivate = (snapshotId: string) => {
    setError(null);
    setActivatingId(snapshotId);
    activateMutation.mutate(snapshotId);
  };

  const snapshots = publishedQuery.data?.snapshots ?? [];
  const active = publishedQuery.data?.active_snapshot ?? null;

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <header className="mb-6">
        <p className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#5b76fe]">
          <History size={13} />
          Snapshots
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.02em] text-[#171b24]">
          Chart history
        </h1>
        <p className="mt-2 text-sm leading-6 text-[#5f6f89]">
          Every harmonization run that gets published is preserved as a snapshot.
          Roll downstream modules (FHIR Charts, Caspian) back to any prior state
          by activating an earlier snapshot. Activation does not delete history.
        </p>
      </header>

      {!collectionId && (
        <div className="rounded-lg border border-[#dfe4ea] bg-white p-6 text-sm text-[#667085]">
          Choose a patient from the URL (?patient=…) to see their snapshot history.
        </div>
      )}

      {publishedQuery.isLoading && (
        <div className="rounded-lg border border-[#dfe4ea] bg-white p-6 text-sm text-[#667085]">
          Loading snapshot history…
        </div>
      )}

      {publishedQuery.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Could not load snapshot history.
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {publishedQuery.data && (
        <>
          {active && (
            <section className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
              <p>
                Active snapshot: <code className="font-mono">{active.snapshot_id.slice(0, 8)}</code>{" "}
                · {active.candidate_fact_count} facts · {active.source_count} sources
              </p>
              <p className="mt-1 text-xs leading-5 text-emerald-900">
                {active.change_summary.headline}
              </p>
            </section>
          )}
          <div className="mb-3 flex items-center gap-2 text-xs text-[#5d6474]">
            <label htmlFor="snapshot-audience" className="font-semibold uppercase tracking-[0.12em] text-[#7b8597]">
              Primary packet:
            </label>
            <select
              id="snapshot-audience"
              value={audience}
              onChange={(event) => setAudience(event.target.value as BundleAudience)}
              className="cursor-pointer rounded-md border border-[#dfe4ea] bg-white px-2 py-1.5 text-xs font-semibold text-[#555a6a] focus:outline-none"
            >
              {AUDIENCE_OPTIONS.map((option) => (
                <option key={option.value || "none"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <SnapshotList
            snapshots={snapshots}
            activatingSnapshotId={activatingId}
            onActivate={handleActivate}
            buildDownloadHref={(snapshotId) => {
              if (!collectionId) return "#";
              const params = new URLSearchParams({ snapshot: snapshotId });
              if (audience) params.set("audience", audience);
              return `/api/harmonize/${encodeURIComponent(collectionId)}/export-workspace?${params.toString()}`;
            }}
            onDiff={(snapshotId) => setDiffSnapshotId(snapshotId)}
          />

          {patientId && (
            <div className="mt-6">
              <NarrativeHistoryPanel patientId={patientId} />
            </div>
          )}

          {diffSnapshotId && collectionId && (
            <SnapshotDiffModal
              collectionId={collectionId}
              snapshotId={diffSnapshotId}
              onClose={() => setDiffSnapshotId(null)}
            />
          )}
        </>
      )}
    </div>
  );
}
