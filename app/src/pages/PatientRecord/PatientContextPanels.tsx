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
import {
  AlertTriangle,
  ChevronRight,
  ClipboardList,
  History,
  Loader2,
  MessageSquareText,
  X,
} from "lucide-react";

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

function cls(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

function formatDateLabel(value: string | null | undefined): string {
  if (!value) return "No date";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
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
      <div className="rounded-[10px] border border-line-1 bg-surface-0 px-4 py-3 text-sm text-ink-3 shadow-[var(--shadow-1)]">
        <p className="flex items-center gap-2">
          <Loader2 size={14} className="animate-spin text-action" />
          Loading patient context augmentation...
        </p>
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
      className="rounded-[10px] border border-line-1 bg-surface-0 shadow-[var(--shadow-1)]"
    >
      <div className="flex flex-col gap-3 border-b border-line-1 px-4 py-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="inline-flex items-center gap-2 rounded-full bg-action-tint px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-action">
            <ClipboardList size={13} />
            Patient context
          </p>
          <h2 className="mt-3 text-base font-semibold text-ink-1">
            Additional context captured outside the verified chart
          </h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-ink-3">
            Use patient-reported story, episode summaries, and unresolved caveats to add narrative context without
            altering canonical chart facts.
          </p>
        </div>
        <p className="max-w-sm text-sm leading-6 text-ink-3">
          This section is supportive evidence. The harmonized record and publish decision still depend on reviewed
          source-backed facts below.
        </p>
      </div>

      <div className="grid gap-4 p-4 xl:grid-cols-[1.05fr_1fr_1fr]">
        {hasVoice && aug.patient_voice && <PatientVoiceCard voice={aug.patient_voice} />}
        {hasEpisodes && <CareEpisodesPanel patientId={patientId} briefs={aug.episode_briefs} />}
        {hasCaveats && <ConflictsPanel caveats={aug.caveats} />}
      </div>
    </section>
  );
}

function PatientVoiceCard({ voice }: { voice: PatientVoiceSummaryDTO }) {
  return (
    <section className="rounded-[10px] border border-action-line bg-action-tint p-4">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-action">
        <MessageSquareText size={14} />
        Patient voice
      </div>
      <p className="mt-3 text-sm leading-6 text-ink-1">{voice.summary}</p>
      {voice.citations.length > 0 && (
        <div className="mt-4 border-t border-action-line pt-3 text-xs text-ink-3">
          <p className="font-semibold uppercase tracking-[0.14em] text-ink-3">Evidence links</p>
          <p className="mt-1">
            Turn{voice.citations.length === 1 ? "" : "s"}:{" "}
            {voice.citations.map((citation, index) => (
              <span key={citation}>
                <code className="rounded bg-white px-1.5 py-0.5 text-[11px] text-ink-1">{citation}</code>
                {index < voice.citations.length - 1 ? ", " : ""}
              </span>
            ))}
          </p>
        </div>
      )}
    </section>
  );
}

function CareEpisodesPanel({
  patientId,
  briefs,
}: {
  patientId: string;
  briefs: EpisodeBriefDTO[];
}) {
  const [openSlug, setOpenSlug] = useState<string | null>(null);

  return (
    <section className="rounded-[10px] border border-line-1 bg-surface-0">
      <div className="border-b border-line-1 px-4 py-3">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">
          <History size={14} />
          Care episodes
        </div>
        <p className="mt-2 text-sm leading-6 text-ink-3">
          Open a narrative when you need the patient story behind a major treatment window.
        </p>
      </div>
      <ul className="divide-y divide-line-1">
        {briefs.map((brief) => {
          const slug = episodeSlug(brief.episode_id);
          const period = brief.period_end
            ? `${formatDateLabel(brief.period_start)} to ${formatDateLabel(brief.period_end)}`
            : `${formatDateLabel(brief.period_start)} to ongoing`;
          return (
            <li key={brief.episode_id}>
              <button
                type="button"
                className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-1"
                onClick={() => setOpenSlug(slug)}
              >
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink-1">{brief.type}</p>
                  <p className="mt-1 text-xs text-ink-3">{period}</p>
                  <p className="mt-2 text-sm leading-6 text-ink-2">{brief.one_liner}</p>
                </div>
                <ChevronRight size={16} className="mt-1 shrink-0 text-ink-4" />
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
    </section>
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
      className="fixed inset-0 z-50 flex bg-[rgba(15,23,42,0.28)]"
    >
      <button
        type="button"
        aria-label="Close narrative"
        className="hidden flex-1 lg:block"
        onClick={onClose}
      />
      <div className="flex h-full w-full max-w-3xl flex-col overflow-y-auto border-l border-line-1 bg-surface-0 shadow-[var(--shadow-3)]">
        <div className="flex items-start justify-between gap-4 border-b border-line-1 px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-action">Episode narrative</p>
            <h2 className="mt-1 text-lg font-semibold text-ink-1">{episodeSlug}</h2>
            <p className="mt-1 text-sm text-ink-3">Narrative Composition generated from the patient context pipeline.</p>
          </div>
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-[6px] border border-line-1 bg-surface-0 text-ink-3 hover:bg-surface-1 hover:text-ink-1"
            onClick={onClose}
            aria-label="Close episode narrative"
          >
            <X size={16} />
          </button>
        </div>
        <div className="px-5 py-4">
          {narrativeQuery.isLoading && <p className="text-sm text-ink-3">Loading narrative...</p>}
          {narrativeQuery.isError && (
            <p className="rounded-[10px] border border-critical-line bg-critical-tint px-3 py-3 text-sm text-critical">
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
    return <p className="text-sm text-ink-3">(no sections)</p>;
  }
  return (
    <div className="flex flex-col gap-4 text-sm text-ink-1">
      {sections.map((section, index) => (
        <section key={`${section.title}-${index}`} className="rounded-[10px] border border-line-1 bg-surface-1 p-4">
          <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-3">{section.title}</h3>
          {section.text?.div ? (
            <div
              className="mt-2 whitespace-pre-wrap break-words leading-6"
              dangerouslySetInnerHTML={{ __html: section.text.div }}
            />
          ) : (
            <p className="mt-2 italic text-ink-4">(empty)</p>
          )}
        </section>
      ))}
    </div>
  );
}

function ConflictsPanel({ caveats }: { caveats: HarmonizationCaveatDTO[] }) {
  return (
    <section className="rounded-[10px] border border-caution-line bg-caution-tint">
      <div className="border-b border-caution-line px-4 py-3">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-caution">
          <AlertTriangle size={14} />
          Caveats to review
        </div>
        <p className="mt-2 text-sm leading-6 text-ink-2">
          Narrative generation found facts with disagreement or lower confidence. Keep them in view during review.
        </p>
      </div>
      <ul className="divide-y divide-caution-line">
        {caveats.map((caveat, index) => (
          <li key={`${caveat.fact_path}-${index}`} className="px-4 py-3 text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <code className="text-xs text-caution">{caveat.fact_path}</code>
              <ConfidenceBadge confidence={caveat.confidence} />
            </div>
            <p className="mt-2 text-ink-1">
              Verdict: <strong>{caveat.verdict}</strong>
            </p>
            {caveat.rationale && <p className="mt-1 text-xs leading-5 text-ink-3">{caveat.rationale}</p>}
            {caveat.dissenting_sources.length > 0 && (
              <p className="mt-2 text-xs leading-5 text-ink-3">
                Dissenting sources:{" "}
                {caveat.dissenting_sources.map((source, sourceIndex) => (
                  <span key={source}>
                    <code className="rounded bg-white px-1.5 py-0.5 text-[11px] text-ink-1">{source}</code>
                    {sourceIndex < caveat.dissenting_sources.length - 1 ? ", " : ""}
                  </span>
                ))}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const normalized = confidence.toLowerCase();
  return (
    <span
      className={cls(
        "rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em]",
        normalized === "low" && "border-critical-line bg-critical-tint text-critical",
        normalized === "medium" && "border-caution-line bg-white text-caution",
        normalized !== "low" && normalized !== "medium" && "border-clear-line bg-clear-tint text-clear",
      )}
    >
      {confidence} confidence
    </span>
  );
}
