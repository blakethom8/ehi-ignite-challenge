import type { ExtractionProgress } from "./types";

/**
 * Page-checkpoint grid that ticks green as the backend reports completed
 * pages. Shared between the authenticated extract-job UI and the Guest
 * harmonization progress block — both produce ``ExtractionProgress`` shapes.
 */
export function PdfPageProgressMap({ progress }: { progress: ExtractionProgress | null }) {
  const totalPages = progress?.total_pages ?? null;
  const visiblePages = totalPages ? Math.min(totalPages, 8) : 4;
  const reportedPages = progress?.processed_pages ?? 0;
  const estimatedPages = Math.max(reportedPages, progress?.estimated_processed_pages ?? reportedPages);
  const isRunning = progress?.status === "pending" || progress?.status === "running";
  const hasReportedPageProgress = Boolean(totalPages && reportedPages > 0);
  const hasEstimatedPageProgress = Boolean(totalPages && isRunning && estimatedPages > reportedPages);
  const activePage = totalPages ? Math.min(totalPages, Math.max(1, estimatedPages + 1)) : 1;
  const progressMode = progress?.progress_mode ?? "lifecycle";

  return (
    <div className="rounded-lg border border-[#ead3b9] bg-white px-3 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-[#9a5a16]">
          {progressMode === "reported" ? "Reported page checkpoints" : "Estimated page position"}
        </p>
        <p className="text-xs text-[#667085]">
          {hasReportedPageProgress
            ? `${reportedPages}/${totalPages} pages completed`
            : hasEstimatedPageProgress
              ? `Estimating page ${activePage} of ${totalPages}`
              : totalPages
                ? `${totalPages} pages detected; waiting for first checkpoint`
                : "Counting pages when extraction starts"}
        </p>
      </div>
      <div className="mt-3 grid grid-cols-4 gap-2 sm:grid-cols-8">
        {Array.from({ length: visiblePages }).map((_, index) => {
          const pageNumber = index + 1;
          const isReportedComplete = totalPages ? pageNumber <= reportedPages : false;
          const isEstimatedPassed = totalPages
            ? pageNumber <= estimatedPages && !isReportedComplete
            : false;
          const isActive =
            isRunning && !isReportedComplete && (totalPages ? pageNumber === activePage : index === 0);
          return (
            <div
              key={pageNumber}
              className={`flex h-16 flex-col justify-between rounded-md border px-2 py-2 text-[11px] ${
                isReportedComplete
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : isActive
                    ? "border-[#5b76fe] bg-[#f4f6ff] text-[#4157d8]"
                    : isEstimatedPassed
                      ? "border-[#f1d4a9] bg-[#fff8ed] text-[#9a5a16]"
                      : "border-[#eef0f4] bg-[#f7f9fc] text-[#667085]"
              }`}
            >
              <span className="font-semibold">
                {totalPages ? `Page ${pageNumber}` : ["Read", "Extract", "Map", "Validate"][index]}
              </span>
              <span
                className={`h-1.5 rounded-full ${
                  isReportedComplete
                    ? "bg-emerald-400"
                    : isActive
                      ? "bg-[#5b76fe]"
                      : isEstimatedPassed
                        ? "bg-[#d99a35]"
                        : "bg-[#dfe4ea]"
                }`}
              />
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-xs leading-5 text-[#667085]">
        {progressMode === "reported"
          ? "Green pages come from backend checkpoint events. The current worker reports by completed file, so multiple pages may complete at once."
          : "Blue shows estimated position while the server runs. Green appears only after the backend reports a completed checkpoint."}
      </p>
      {totalPages && totalPages > visiblePages ? (
        <p className="mt-2 text-xs text-[#667085]">
          Showing the first {visiblePages} pages; remaining pages continue in the same server job.
        </p>
      ) : null}
    </div>
  );
}
