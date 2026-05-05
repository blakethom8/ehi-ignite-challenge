import { useState } from "react";
import { ExternalLink, FileText, Lightbulb, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Citation } from "../../../../types/skills";

const KIND_CONFIG: Record<
  Citation["source_kind"],
  { label: string; icon: LucideIcon; tone: { bg: string; fg: string; border: string } }
> = {
  fhir_resource: {
    label: "Chart fact",
    icon: FileText,
    tone: { bg: "#eef1ff", fg: "#3a4ca8", border: "#c7d0fa" },
  },
  external_url: {
    label: "External source",
    icon: ExternalLink,
    tone: { bg: "#c3faf5", fg: "#187574", border: "#7ee0d8" },
  },
  clinician_input: {
    label: "Clinician input",
    icon: UserRound,
    tone: { bg: "#ffe6cd", fg: "#9a5a16", border: "#f3c89e" },
  },
  agent_inference: {
    label: "Agent inference",
    icon: Lightbulb,
    tone: { bg: "#f5f6f8", fg: "#555a6a", border: "#d6d9e2" },
  },
};

const TIER_LABEL: Record<Citation["evidence_tier"], string> = {
  T1: "T1 — direct chart fact",
  T2: "T2 — harmonized record",
  T3: "T3 — agent inference",
  T4: "T4 — agent guess",
};

interface CitationChipProps {
  citation: Citation;
  inline?: boolean;
}

/**
 * Inline citation chip rendered in place of `[cite:c_NNNN]` markers in the
 * workspace.md stream. Click to expand a popover showing the source kind,
 * evidence tier, and a click-out link if the source is a URL.
 */
export function CitationChip({ citation, inline = true }: CitationChipProps) {
  const [open, setOpen] = useState(false);
  const cfg = KIND_CONFIG[citation.source_kind];
  const Icon = cfg.icon;

  const onClick = () => setOpen((prev) => !prev);

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={onClick}
        className={`inline-flex items-center gap-1 align-baseline ${
          inline ? "text-[11px]" : "text-xs"
        } font-mono font-semibold`}
        style={{
          backgroundColor: cfg.tone.bg,
          color: cfg.tone.fg,
          border: `1px solid ${cfg.tone.border}`,
          borderRadius: 6,
          padding: inline ? "0 4px" : "1px 6px",
          lineHeight: 1.4,
        }}
        aria-label={`Citation ${citation.citation_id}`}
      >
        <Icon size={10} />
        <span>{citation.citation_id}</span>
        <span style={{ opacity: 0.7 }}>{citation.evidence_tier}</span>
      </button>
      {open ? (
        <span
          className="absolute left-0 top-full z-30 mt-1 block w-72 rounded-xl bg-white p-3 text-left text-xs shadow-[rgb(224_226_232)_0px_0px_0px_1px]"
          onClick={(e) => e.stopPropagation()}
        >
          <span className="block text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">
            {cfg.label}
          </span>
          <span className="mt-1 block text-sm font-medium text-[#1c1c1e]">
            {citation.claim}
          </span>
          <span className="mt-2 block text-[11px] text-[#555a6a]">
            {TIER_LABEL[citation.evidence_tier]}
          </span>
          {citation.source_ref ? (
            citation.source_kind === "external_url" ? (
              <a
                href={citation.source_ref}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold text-[#5b76fe] hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                Open source <ExternalLink size={11} />
              </a>
            ) : (
              <span className="mt-2 block break-all rounded bg-[#f5f6f8] px-2 py-1 font-mono text-[10px] text-[#555a6a]">
                {citation.source_ref}
              </span>
            )
          ) : null}
          <span className="mt-2 block text-[10px] text-[#a5a8b5]">
            registered {new Date(citation.access_timestamp).toLocaleString()}
          </span>
        </span>
      ) : null}
    </span>
  );
}
