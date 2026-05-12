import { useQuery } from "@tanstack/react-query";
import { Plus, Minus, ArrowRight } from "lucide-react";
import { api } from "../../../api/client";

/**
 * Side-by-side diff modal between two snapshots' canonical facts.
 * Defaults to comparing against the chronologically previous snapshot.
 */
export function SnapshotDiffModal({
  collectionId,
  snapshotId,
  onClose,
}: {
  collectionId: string;
  snapshotId: string;
  onClose: () => void;
}) {
  const diffQuery = useQuery({
    queryKey: ["snapshot-diff", collectionId, snapshotId],
    queryFn: () => api.getSnapshotDiff(collectionId, snapshotId),
  });

  return (
    <div role="dialog" aria-label="Snapshot diff" className="fixed inset-0 z-50 flex">
      <button
        type="button"
        aria-label="Close"
        className="flex-1 bg-black/30"
        onClick={onClose}
      />
      <div className="flex h-full w-full max-w-4xl flex-col overflow-y-auto bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-[#e5e7eb] px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-[#0f172a]">Snapshot diff</h2>
            <p className="text-xs text-[#64748b]">vs. chronologically previous snapshot</p>
          </div>
          <button
            type="button"
            className="text-xs text-[#64748b] hover:text-[#0f172a]"
            onClick={onClose}
          >
            Close ✕
          </button>
        </div>

        <div className="px-5 py-4">
          {diffQuery.isLoading && (
            <p className="text-sm text-[#64748b]">Computing diff…</p>
          )}
          {diffQuery.isError && (
            <p className="text-sm text-red-700">
              Could not compute diff. The earliest snapshot has no predecessor —
              try a later snapshot.
            </p>
          )}
          {diffQuery.data && (
            <>
              <div className="mb-4 grid grid-cols-3 gap-3 text-xs">
                <Metric icon={<Plus size={14} />} tone="emerald" label="Added" value={diffQuery.data.totals.added} />
                <Metric icon={<Minus size={14} />} tone="rose" label="Removed" value={diffQuery.data.totals.removed} />
                <Metric icon={<ArrowRight size={14} />} tone="amber" label="Changed" value={diffQuery.data.totals.changed} />
              </div>

              <div className="flex flex-col gap-4">
                {Object.entries(diffQuery.data.categories).map(([category, entries]) => {
                  const total = entries.added.length + entries.removed.length + entries.changed.length;
                  if (total === 0) return null;
                  return (
                    <section key={category} className="rounded-lg border border-[#e5e7eb]">
                      <header className="border-b border-[#eef0f5] px-3 py-2 text-xs font-semibold uppercase tracking-wide text-[#475569]">
                        {category}
                      </header>
                      <div className="divide-y divide-[#eef0f5]">
                        {entries.added.map((row) => (
                          <DiffRow
                            key={`add-${row.merged_ref}`}
                            kind="added"
                            label={row.label || row.merged_ref}
                            detail={row.value}
                          />
                        ))}
                        {entries.removed.map((row) => (
                          <DiffRow
                            key={`rem-${row.merged_ref}`}
                            kind="removed"
                            label={row.label || row.merged_ref}
                            detail={row.value}
                          />
                        ))}
                        {entries.changed.map((row) => (
                          <DiffRow
                            key={`chg-${row.merged_ref}`}
                            kind="changed"
                            label={row.label || row.merged_ref}
                            detail={`${row.before || "(empty)"} → ${row.after || "(empty)"}`}
                          />
                        ))}
                      </div>
                    </section>
                  );
                })}
                {diffQuery.data.totals.added +
                  diffQuery.data.totals.removed +
                  diffQuery.data.totals.changed ===
                  0 && (
                  <p className="text-sm text-[#64748b]">
                    No fact-level differences between the two snapshots.
                  </p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Metric({
  icon,
  tone,
  label,
  value,
}: {
  icon: React.ReactNode;
  tone: "emerald" | "rose" | "amber";
  label: string;
  value: number;
}) {
  const palette: Record<typeof tone, string> = {
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-900",
    rose: "border-rose-200 bg-rose-50 text-rose-900",
    amber: "border-amber-200 bg-amber-50 text-amber-900",
  };
  return (
    <div className={`flex items-center justify-between rounded-md border px-3 py-2 ${palette[tone]}`}>
      <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em]">
        {icon}
        {label}
      </span>
      <span className="text-base font-semibold">{value}</span>
    </div>
  );
}

function DiffRow({
  kind,
  label,
  detail,
}: {
  kind: "added" | "removed" | "changed";
  label: string;
  detail: string;
}) {
  const tone: Record<typeof kind, string> = {
    added: "text-emerald-700",
    removed: "text-rose-700",
    changed: "text-amber-700",
  };
  const glyph: Record<typeof kind, string> = {
    added: "+",
    removed: "−",
    changed: "↻",
  };
  return (
    <div className="grid grid-cols-[24px_minmax(0,1fr)_minmax(0,1.4fr)] gap-3 px-3 py-2 text-xs">
      <span className={`font-mono text-sm ${tone[kind]}`}>{glyph[kind]}</span>
      <span className="min-w-0 truncate font-semibold text-[#1c1c1e]">{label}</span>
      <span className="min-w-0 truncate text-[#475569]">{detail}</span>
    </div>
  );
}
