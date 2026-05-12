/**
 * T8c — Three augmentation panels on the merged-record page:
 *   1. Patient's words   (PatientVoiceSummary)
 *   2. Care episodes     (EpisodeBriefs + drawer with Composition)
 *   3. Conflicts to review (HarmonizationCaveats)
 *
 * See docs/architecture/LLM-CONTEXT-AUGMENTATION-PLAN.md §T8 §3.
 *
 * The panel reads everything from
 *   GET /api/patient-context/{patient_id}/augmentation
 * which the publish hook (T6) refreshes via the narrative service.
 *
 * Hides itself entirely when all three artifacts are empty so the
 * merged-record page degrades gracefully for patients without a
 * Patient Context session yet.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../../api/client";
import type {
  EpisodeBriefDTO,
  FhirComposition,
  HarmonizationCaveatDTO,
  PatientContextAugmentationResponse,
  PatientVoiceSummaryDTO,
} from "../../types";


interface PatientContextPanelsProps {
  patientId: string;
}

export function PatientContextPanels({ patientId }: PatientContextPanelsProps) {
  const augmentationQuery = useQuery({
    queryKey: ["patient-context-augmentation", patientId],
    queryFn: () => api.getPatientContextAugmentation(patientId),
    enabled: Boolean(patientId),
    staleTime: 30_000,
  });
  const aug: PatientContextAugmentationResponse | undefined = augmentationQuery.data;

  if (augmentationQuery.isLoading) {
    return (
      <div className="mb-6 rounded-xl border border-[#e5e7eb] bg-white p-4 text-sm text-[#667085]">
        Loading patient context…
      </div>
    );
  }
  if (!aug) {
    // Endpoint missing or errored — silently degrade.
    return null;
  }
  const hasVoice = Boolean(aug.patient_voice?.summary);
  const hasEpisodes = aug.episode_briefs.length > 0;
  const hasCaveats = aug.caveats.length > 0;
  if (!hasVoice && !hasEpisodes && !hasCaveats) return null;

  return (
    <section
      aria-label="Patient context augmentation"
      className="mb-6 flex flex-col gap-3"
    >
      {hasVoice && aug.patient_voice && (
        <PatientVoiceCard voice={aug.patient_voice} />
      )}
      {hasEpisodes && (
        <CareEpisodesPanel patientId={patientId} briefs={aug.episode_briefs} />
      )}
      {hasCaveats && <ConflictsPanel caveats={aug.caveats} />}
    </section>
  );
}


// ---------------------------------------------------------------------------
// Patient's words card (top)
// ---------------------------------------------------------------------------

function PatientVoiceCard({ voice }: { voice: PatientVoiceSummaryDTO }) {
  return (
    <div className="rounded-xl border border-[#1d4ed8]/30 bg-[#eef2ff] p-4">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[#1e40af]">
        <span aria-hidden>🗣</span>
        Patient's own words
      </div>
      <p className="mt-1 text-sm leading-relaxed text-[#0f172a]">
        {voice.summary}
      </p>
      {voice.citations.length > 0 && (
        <p className="mt-2 text-xs text-[#64748b]">
          From turn{voice.citations.length === 1 ? "" : "s"}:{" "}
          {voice.citations.map((c, idx) => (
            <span key={c}>
              <code className="font-mono">{c}</code>
              {idx < voice.citations.length - 1 ? ", " : ""}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Care episodes panel + drawer
// ---------------------------------------------------------------------------

function CareEpisodesPanel({
  patientId,
  briefs,
}: {
  patientId: string;
  briefs: EpisodeBriefDTO[];
}) {
  const [openSlug, setOpenSlug] = useState<string | null>(null);
  return (
    <div className="rounded-xl border border-[#e5e7eb] bg-white">
      <div className="border-b border-[#e5e7eb] px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[#475569]">
        Care episodes
      </div>
      <ul className="divide-y divide-[#f1f5f9]">
        {briefs.map((brief) => {
          const slug = episodeSlug(brief.episode_id);
          const period = brief.period_end
            ? `${brief.period_start} → ${brief.period_end}`
            : `${brief.period_start} → ongoing`;
          return (
            <li key={brief.episode_id} className="px-4 py-3">
              <button
                type="button"
                className="w-full text-left"
                onClick={() => setOpenSlug(slug)}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-sm font-semibold text-[#0f172a]">{brief.type}</span>
                  <span className="text-xs text-[#64748b]">{period}</span>
                </div>
                <p className="mt-1 text-sm text-[#475569]">{brief.one_liner}</p>
              </button>
            </li>
          );
        })}
      </ul>
      {openSlug && (
        <EpisodeNarrativeDrawer
          patientId={patientId}
          episodeSlug={openSlug}
          onClose={() => setOpenSlug(null)}
        />
      )}
    </div>
  );
}

function episodeSlug(episodeId: string): string {
  return episodeId.startsWith("episode-") ? episodeId.slice("episode-".length) : episodeId;
}

function EpisodeNarrativeDrawer({
  patientId,
  episodeSlug,
  onClose,
}: {
  patientId: string;
  episodeSlug: string;
  onClose: () => void;
}) {
  const narrativeQuery = useQuery({
    queryKey: ["patient-context-narrative", patientId, episodeSlug],
    queryFn: () => api.getPatientContextNarrative(patientId, episodeSlug),
    enabled: Boolean(patientId && episodeSlug),
  });

  return (
    <div
      role="dialog"
      aria-label={`Narrative for ${episodeSlug}`}
      className="fixed inset-0 z-50 flex"
    >
      <button
        type="button"
        aria-label="Close narrative"
        className="flex-1 bg-black/30"
        onClick={onClose}
      />
      <div className="flex h-full w-full max-w-2xl flex-col overflow-y-auto bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-[#e5e7eb] px-5 py-3">
          <h2 className="text-sm font-semibold text-[#0f172a]">Episode narrative</h2>
          <button
            type="button"
            className="text-xs text-[#64748b] hover:text-[#0f172a]"
            onClick={onClose}
          >
            Close ✕
          </button>
        </div>
        <div className="px-5 py-4">
          {narrativeQuery.isLoading && (
            <p className="text-sm text-[#64748b]">Loading narrative…</p>
          )}
          {narrativeQuery.isError && (
            <p className="text-sm text-red-700">
              Narrative not yet generated. Publish a harmonization run to regenerate it.
            </p>
          )}
          {narrativeQuery.data && <CompositionSections composition={narrativeQuery.data} />}
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
            // The Composition's div is already HTML-escaped at write time
            // (see lib/narratives/generator.py _html_escape). Render as
            // dangerouslySetInnerHTML because [[ref:Resource/id]] markers
            // and the surrounding text are intentionally markdown-lite.
            <div
              className="mt-1 whitespace-pre-wrap break-words leading-relaxed"
              // eslint-disable-next-line react/no-danger
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


// ---------------------------------------------------------------------------
// Conflicts panel
// ---------------------------------------------------------------------------

function ConflictsPanel({ caveats }: { caveats: HarmonizationCaveatDTO[] }) {
  return (
    <div className="rounded-xl border border-[#fde68a] bg-[#fffbeb]">
      <div className="border-b border-[#fde68a] px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[#92400e]">
        Conflicts to review
      </div>
      <ul className="divide-y divide-[#fde68a]/60">
        {caveats.map((c, idx) => (
          <li key={`${c.fact_path}-${idx}`} className="px-4 py-3 text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <code className="font-mono text-xs text-[#92400e]">{c.fact_path}</code>
              <ConfidenceBadge confidence={c.confidence} />
            </div>
            <p className="mt-1 text-[#451a03]">
              Verdict: <strong>{c.verdict}</strong>
            </p>
            {c.rationale && (
              <p className="mt-1 text-xs text-[#78350f]">{c.rationale}</p>
            )}
            {c.dissenting_sources.length > 0 && (
              <p className="mt-1 text-xs text-[#78350f]">
                Dissenting sources:{" "}
                {c.dissenting_sources.map((s, i) => (
                  <span key={s}>
                    <code className="font-mono">{s}</code>
                    {i < c.dissenting_sources.length - 1 ? ", " : ""}
                  </span>
                ))}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const c = confidence.toLowerCase();
  const styles =
    c === "low"
      ? "bg-red-100 text-red-800 border-red-200"
      : c === "medium"
      ? "bg-amber-100 text-amber-800 border-amber-200"
      : "bg-emerald-100 text-emerald-800 border-emerald-200";
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${styles}`}
    >
      {confidence} confidence
    </span>
  );
}
