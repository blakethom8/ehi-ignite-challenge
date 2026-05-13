import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, History } from "lucide-react";
import { api } from "../../../api/client";
import type { FhirComposition } from "../../../types";

/**
 * Renders per-episode FHIR Composition history for the active patient.
 * Reads /api/patient-context/<patient>/augmentation to discover episodes,
 * then lazy-loads each episode's history on expand.
 */
export function NarrativeHistoryPanel({ patientId }: { patientId: string }) {
  const augmentationQuery = useQuery({
    queryKey: ["patient-context-augmentation", patientId],
    queryFn: () => api.getPatientContextAugmentation(patientId),
    enabled: Boolean(patientId),
  });

  const briefs = augmentationQuery.data?.episode_briefs ?? [];

  if (augmentationQuery.isLoading) {
    return (
      <div className="rounded-lg border border-[#dfe4ea] bg-white p-4 text-sm text-[#667085]">
        Loading episode list…
      </div>
    );
  }
  if (briefs.length === 0) {
    return (
      <div className="rounded-lg border border-[#dfe4ea] bg-white p-4 text-sm text-[#667085]">
        No episode narratives yet for this patient. Publish a harmonization run to
        generate the first set of FHIR Compositions.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[#dfe4ea] bg-white">
      <div className="border-b border-[#eef0f5] px-4 py-3">
        <h2 className="inline-flex items-center gap-2 text-base font-semibold text-[#1c1c1e]">
          <History size={15} />
          Narrative history
        </h2>
        <p className="mt-1 text-sm text-[#667085]">
          Every published snapshot regenerates each episode's FHIR Composition.
          Prior versions are archived automatically.
        </p>
      </div>
      <div className="divide-y divide-[#eef0f4]">
        {briefs.map((brief) => (
          <EpisodeRow
            key={brief.episode_id}
            patientId={patientId}
            episodeId={brief.episode_id}
            type={brief.type}
            oneLiner={brief.one_liner}
          />
        ))}
      </div>
    </div>
  );
}

function EpisodeRow({
  patientId,
  episodeId,
  type,
  oneLiner,
}: {
  patientId: string;
  episodeId: string;
  type: string;
  oneLiner: string | null;
}) {
  const slug = episodeId.startsWith("episode-")
    ? episodeId.slice("episode-".length)
    : episodeId;
  const [expanded, setExpanded] = useState(false);
  const [drawerKey, setDrawerKey] = useState<{ slug: string; timestamp: string | null } | null>(
    null,
  );

  const historyQuery = useQuery({
    queryKey: ["narrative-history", patientId, slug],
    queryFn: () => api.getNarrativeHistory(patientId, slug),
    enabled: expanded,
  });

  const versions = historyQuery.data?.versions ?? [];

  return (
    <div className="px-4 py-3">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-start gap-3 text-left"
      >
        <span className="mt-0.5 text-[#7b8597]">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </span>
        <span className="flex-1 min-w-0">
          <span className="block text-sm font-semibold text-[#1c1c1e]">{type}</span>
          {oneLiner && (
            <span className="mt-0.5 block text-xs leading-5 text-[#667085]">
              {oneLiner}
            </span>
          )}
          <span className="mt-0.5 block text-xs text-[#8d92a3]">slug · {slug}</span>
        </span>
      </button>

      {expanded && (
        <div className="mt-3 ml-7 space-y-2">
          <button
            type="button"
            onClick={() => setDrawerKey({ slug, timestamp: null })}
            className="inline-flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-900 hover:bg-emerald-100"
          >
            View current
          </button>

          {historyQuery.isLoading && (
            <p className="text-xs text-[#667085]">Loading history…</p>
          )}
          {historyQuery.isError && (
            <p className="text-xs text-red-700">Failed to load history.</p>
          )}
          {!historyQuery.isLoading && versions.length === 0 && (
            <p className="text-xs text-[#8d92a3]">No prior versions yet.</p>
          )}
          {versions.length > 0 && (
            <ul className="space-y-1">
              {versions.map((version) => (
                <li
                  key={version.timestamp}
                  className="flex items-center justify-between gap-3 rounded-md border border-[#eef0f4] bg-white px-3 py-1.5 text-xs"
                >
                  <span className="min-w-0 truncate">
                    <span className="font-mono text-[#475569]">{version.timestamp}</span>
                    {version.composition_id && (
                      <span className="ml-2 text-[#8d92a3]">
                        ({version.composition_id})
                      </span>
                    )}
                  </span>
                  <button
                    type="button"
                    onClick={() => setDrawerKey({ slug, timestamp: version.timestamp })}
                    className="rounded-md border border-[#dfe4ea] bg-white px-2 py-1 text-xs font-semibold text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe]"
                  >
                    View
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {drawerKey && (
        <CompositionDrawer
          patientId={patientId}
          slug={drawerKey.slug}
          timestamp={drawerKey.timestamp}
          onClose={() => setDrawerKey(null)}
        />
      )}
    </div>
  );
}

function CompositionDrawer({
  patientId,
  slug,
  timestamp,
  onClose,
}: {
  patientId: string;
  slug: string;
  timestamp: string | null;
  onClose: () => void;
}) {
  const isCurrent = timestamp === null;
  const query = useQuery({
    queryKey: isCurrent
      ? ["patient-context-narrative", patientId, slug]
      : ["narrative-archived", patientId, slug, timestamp],
    queryFn: () =>
      isCurrent
        ? api.getPatientContextNarrative(patientId, slug)
        : api.getArchivedNarrative(patientId, slug, timestamp as string),
  });

  return (
    <div role="dialog" aria-label="Narrative" className="fixed inset-0 z-50 flex">
      <button
        type="button"
        aria-label="Close"
        className="flex-1 bg-black/30"
        onClick={onClose}
      />
      <div className="flex h-full w-full max-w-2xl flex-col overflow-y-auto bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-[#e5e7eb] px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-[#0f172a]">Episode narrative</h2>
            <p className="text-xs text-[#64748b]">
              {slug} · {isCurrent ? "current" : timestamp}
            </p>
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
          {query.isLoading && <p className="text-sm text-[#64748b]">Loading…</p>}
          {query.isError && (
            <p className="text-sm text-red-700">Could not load this narrative.</p>
          )}
          {query.data && <CompositionSections composition={query.data} />}
        </div>
      </div>
    </div>
  );
}

function CompositionSections({ composition }: { composition: FhirComposition }) {
  const sections = composition.section ?? [];
  if (sections.length === 0) {
    return <p className="text-sm text-[#64748b]">(no sections)</p>;
  }
  return (
    <div className="flex flex-col gap-4 text-sm text-[#0f172a]">
      {sections.map((section, idx) => (
        <section key={`${section.title}-${idx}`}>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-[#475569]">
            {section.title}
          </h3>
          {section.text?.div ? (
            // Composition div is HTML-escaped at write time
            // (lib/narratives/generator.py:_html_escape).
            <div
              className="mt-1 whitespace-pre-wrap break-words leading-relaxed"
              dangerouslySetInnerHTML={{ __html: section.text.div }}
            />
          ) : (
            <p className="mt-1 italic text-[#94a3b8]">(empty)</p>
          )}
        </section>
      ))}
    </div>
  );
}
