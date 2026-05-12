import type { ExtractionProgress } from "./types";

function eventTime(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(11, 19);
  return date.toLocaleTimeString();
}

/**
 * Scrolling worker-event log. Same component used by the authenticated
 * extract-job UI and the Guest harmonization progress block. Shows the
 * most recent six events with stage, source, page range, and message.
 */
export function PdfExtractionEventTimeline({ progress }: { progress: ExtractionProgress | null }) {
  const events = progress?.events ?? [];
  if (!events.length) return null;
  const visibleEvents = events.slice(-6).reverse();

  return (
    <div className="rounded-lg border border-[#dfe4ea] bg-white px-3 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Worker events</p>
        <p className="text-xs text-[#667085]">
          {progress?.progress_mode === "reported" ? "reported checkpoints" : "lifecycle + estimates"}
        </p>
      </div>
      <div className="mt-2 divide-y divide-[#eef1f5] rounded-lg border border-[#eef1f5]">
        {visibleEvents.map((event) => {
          const pages =
            event.page_start && event.page_end
              ? event.page_start === event.page_end
                ? `Page ${event.page_start}`
                : `Pages ${event.page_start}-${event.page_end}`
              : event.page_count
                ? `${event.page_count} pages`
                : null;
          return (
            <div
              key={event.event_id}
              className="grid gap-2 px-3 py-2 text-xs md:grid-cols-[160px_minmax(0,1fr)_150px]"
            >
              <div>
                <p className="font-semibold text-[#1c1c1e]">{event.stage ?? event.event_type}</p>
                <p className="mt-0.5 text-[#8d92a3]">{eventTime(event.created_at)}</p>
              </div>
              <p className="min-w-0 text-[#667085]">{event.message}</p>
              <div className="md:text-right">
                <p className="font-semibold text-[#555a6a]">{pages ?? event.progress_basis ?? "—"}</p>
                <p className="mt-0.5 text-[#8d92a3]">
                  {event.processed_files ?? 0}/{event.total_files ?? 0} files
                  {event.total_pages
                    ? ` · ${event.processed_pages ?? 0}/${event.total_pages} pages`
                    : ""}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
