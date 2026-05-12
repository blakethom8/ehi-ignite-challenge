import type { PublishedChartSnapshot } from "../../../types";

function signedCount(value: number): string {
  if (value === 0) return "No change";
  return value > 0 ? `+${value}` : `${value}`;
}

export function snapshotDeltaLabel(snapshot: PublishedChartSnapshot): string {
  const change = snapshot.change_summary;
  if (!change?.previous_snapshot_id) return "Initial published snapshot";
  return `${signedCount(change.fact_delta)} facts · ${signedCount(change.source_delta)} sources`;
}

function snapshotDateLabel(value: string | null | undefined): string {
  if (!value) return "Not found";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return date.toLocaleDateString();
}

/**
 * Renders the published-chart snapshot list with delta summaries and an
 * Activate affordance per row. Lifted from
 * `app/src/pages/PatientRecord/aggregator/shared.tsx` so the new Snapshots
 * page and the existing Publish Readiness page share one source of truth.
 */
export function SnapshotList({
  snapshots,
  activatingSnapshotId,
  onActivate,
  emptyMessage,
  showHeader = true,
}: {
  snapshots: PublishedChartSnapshot[];
  activatingSnapshotId: string | null;
  onActivate: (snapshotId: string) => void;
  emptyMessage?: string;
  showHeader?: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-[#dfe4ea] bg-white">
      {showHeader && (
        <div className="border-b border-[#eef0f5] px-4 py-3">
          <h2 className="text-base font-semibold text-[#1c1c1e]">Snapshot history</h2>
          <p className="mt-1 text-sm text-[#667085]">
            Published snapshots stay available so you can roll downstream
            modules back to a prior chart state.
          </p>
        </div>
      )}
      {snapshots.length ? (
        <div className="divide-y divide-[#eef0f4]">
          {snapshots.map((snapshot) => (
            <div
              key={snapshot.snapshot_id}
              className="grid gap-3 px-4 py-3 md:grid-cols-[minmax(0,1fr)_180px_150px] md:items-center"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="truncate text-sm font-semibold text-[#1c1c1e]">
                    Snapshot {snapshot.snapshot_id.slice(0, 8)}
                  </p>
                  {snapshot.is_active && (
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                      Active
                    </span>
                  )}
                </div>
                <p className="mt-1 text-xs text-[#8d92a3]">
                  Published {snapshotDateLabel(snapshot.published_at)} · run {snapshot.run_id.slice(0, 8)} · {snapshot.rule_version}
                </p>
                <p className="mt-1 text-xs leading-5 text-[#667085]">
                  {snapshot.change_summary.headline}
                </p>
                {snapshot.review_decision_summary.event_count > 0 && (
                  <p className="mt-1 text-xs leading-5 text-[#667085]">
                    {snapshot.review_decision_summary.event_count} review event
                    {snapshot.review_decision_summary.event_count === 1 ? "" : "s"} captured before publish.
                  </p>
                )}
              </div>
              <div className="text-sm text-[#555a6a]">
                <p>
                  {snapshot.candidate_fact_count} facts · {snapshot.source_count} sources
                </p>
                <p className="mt-1 text-xs text-[#8d92a3]">{snapshotDeltaLabel(snapshot)}</p>
              </div>
              <button
                type="button"
                disabled={snapshot.is_active || activatingSnapshotId === snapshot.snapshot_id}
                onClick={() => onActivate(snapshot.snapshot_id)}
                className="inline-flex w-fit items-center justify-center rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-xs font-semibold text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {activatingSnapshotId === snapshot.snapshot_id
                  ? "Activating..."
                  : snapshot.is_active
                  ? "Active"
                  : "Activate"}
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-5 text-sm text-[#667085]">
          {emptyMessage ??
            "No chart snapshots have been published yet. Run harmonization, resolve review items, then publish the latest run."}
        </div>
      )}
    </div>
  );
}
