import { AlertTriangle, CheckCircle2, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import type {
  WorkflowArtifact,
  WorkflowBannerStatus,
  WorkflowFactCell,
  WorkflowNarrativeSection,
  WorkflowSection,
  WorkflowTableSection,
} from "../../../../types";
import type { RendererProps } from "../types";

/**
 * WorkflowArtifactRenderer
 *
 * Renders a structured Caspian workflow artifact in the workbench: a
 * disposition banner, a 5-cell fact rail, and a sequence of table or
 * narrative sections. The artifact lives on the run canvas at
 * `canvas[tabId]` and is produced by POST /api/caspian/workflows/run.
 *
 * Citation chips are inferred from cell text. Anything matching
 * `Type:Identifier` (e.g. `MedicationRequest:abc-123`) becomes a clickable
 * chip routed to the inspector. Anything starting with `c_` is also a chip.
 */
export function WorkflowArtifactRenderer({
  canvas,
  tabId,
  onCitationClick,
}: RendererProps) {
  const artifact = canvas[tabId] as WorkflowArtifact | undefined;
  if (!artifact) {
    return (
      <div className="px-10 py-8 text-[13px]" style={{ color: "var(--ink-4)" }}>
        No workflow artifact loaded for this tab.
      </div>
    );
  }
  const onCite = (id: string) => onCitationClick?.(id);
  return (
    <div
      className="mx-auto max-w-[820px] px-10 pb-16 pt-8"
      style={{ fontFamily: "var(--font-sans)" }}
    >
      <h1
        className="mb-1.5 text-[28px] font-semibold tracking-tight"
        style={{ fontFamily: "var(--font-serif)", color: "var(--ink-1)" }}
      >
        {artifact.workflow_title}
      </h1>
      <div
        className="mb-7 text-[12px]"
        style={{ color: "var(--ink-4)", fontFamily: "var(--font-mono)" }}
      >
        {artifact.artifact_id} · {formatTimestamp(artifact.generated_at)} · curated by Caspian
      </div>
      <Banner
        status={artifact.banner.status}
        label={artifact.banner.label}
        headline={artifact.banner.headline}
        actionLabel={artifact.banner.action_label}
      />
      {artifact.fact_rail.length > 0 && <FactRail cells={artifact.fact_rail} />}
      {artifact.sections.map((section, index) => (
        <SectionView key={index} section={section} onCite={onCite} />
      ))}
    </div>
  );
}

function Banner({
  status,
  label,
  headline,
  actionLabel,
}: {
  status: WorkflowBannerStatus;
  label: string;
  headline: string;
  actionLabel: string | null;
}) {
  const palette = palettesFor(status);
  return (
    <div
      className="relative mb-6 grid grid-cols-[36px_1fr_auto] items-center gap-3 overflow-hidden rounded-[10px] border p-4"
      style={{ background: palette.tint, borderColor: palette.line }}
    >
      <span
        className="absolute left-0 top-0 h-full w-1"
        style={{ background: palette.accent }}
      />
      <palette.Icon className="h-5 w-5" strokeWidth={1.5} style={{ color: palette.accent }} />
      <div>
        <span
          className="block text-[11px] font-bold tracking-wider"
          style={{ color: palette.accent }}
        >
          {label}
        </span>
        <div
          className="mt-0.5 text-[13.5px] font-medium"
          style={{ color: "var(--ink-1)" }}
        >
          {headline}
        </div>
      </div>
      {actionLabel ? (
        <button
          className="h-[28px] rounded-md px-3 text-[12px] font-semibold text-white"
          style={{ background: "var(--ink-1)" }}
        >
          {actionLabel}
        </button>
      ) : (
        <span />
      )}
    </div>
  );
}

function FactRail({ cells }: { cells: WorkflowFactCell[] }) {
  const visible = cells.slice(0, 5);
  return (
    <div
      className="my-5 grid overflow-hidden rounded-[10px] border"
      style={{
        background: "var(--surface-0)",
        borderColor: "var(--line-1)",
        gridTemplateColumns: `repeat(${visible.length || 1}, minmax(0, 1fr))`,
      }}
    >
      {visible.map((cell, index) => (
        <FactCellView key={index} cell={cell} />
      ))}
    </div>
  );
}

function FactCellView({ cell }: { cell: WorkflowFactCell }) {
  return (
    <div className="border-r p-3.5 last:border-r-0" style={{ borderColor: "var(--line-1)" }}>
      <div
        className="text-[10px] font-semibold uppercase tracking-wider"
        style={{ color: "var(--ink-4)" }}
      >
        {cell.label}
      </div>
      {cell.tone === "tier" || cell.tone === "caution" ? (
        <div className="mt-1 inline-flex items-center gap-1">
          <span
            className="rounded-full px-1.5 py-px text-[10.5px]"
            style={{
              background: "var(--caution-tint)",
              color: "var(--caution)",
              fontFamily: "var(--font-sans)",
            }}
          >
            {cell.value}
          </span>
        </div>
      ) : (
        <div
          className="mt-1 text-[16px] font-semibold tracking-tight"
          style={{ color: "var(--ink-1)", fontFamily: "var(--font-mono)" }}
        >
          {cell.value}
        </div>
      )}
    </div>
  );
}

function SectionView({
  section,
  onCite,
}: {
  section: WorkflowSection;
  onCite: (id: string) => void;
}) {
  if (section.kind === "table") {
    return <TableSectionView section={section} onCite={onCite} />;
  }
  return <NarrativeSectionView section={section} onCite={onCite} />;
}

function TableSectionView({
  section,
  onCite,
}: {
  section: WorkflowTableSection;
  onCite: (id: string) => void;
}) {
  return (
    <>
      <h2
        className="mb-2 mt-7 text-[19px] font-semibold tracking-tight"
        style={{ fontFamily: "var(--font-serif)", color: "var(--ink-1)" }}
      >
        {section.title}
      </h2>
      {section.rows.length === 0 ? (
        <p
          className="mb-3 text-[13px] italic"
          style={{ color: "var(--ink-4)" }}
        >
          {section.empty_note ?? "No matching items in the chart."}
        </p>
      ) : (
        <table className="mb-2 w-full border-collapse text-[12.5px]">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--line-1)" }}>
              {section.columns.map((c) => (
                <th
                  key={c}
                  className="px-2.5 py-2 text-left font-semibold uppercase tracking-wider"
                  style={{ color: "var(--ink-4)", fontSize: 10.5 }}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {section.rows.map((row, i) => (
              <tr key={i} style={{ borderBottom: "1px solid var(--line-1)" }}>
                {row.map((cell, j) => (
                  <td key={j} className="px-2.5 py-2 align-top">
                    {renderRichCell(cell, onCite)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

function NarrativeSectionView({
  section,
  onCite,
}: {
  section: WorkflowNarrativeSection;
  onCite: (id: string) => void;
}) {
  const paragraphs = section.body
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
  return (
    <>
      <h2
        className="mb-2 mt-7 text-[19px] font-semibold tracking-tight"
        style={{ fontFamily: "var(--font-serif)", color: "var(--ink-1)" }}
      >
        {section.title}
      </h2>
      {paragraphs.length === 0 ? (
        <p className="mb-3 text-[13px] italic" style={{ color: "var(--ink-4)" }}>
          —
        </p>
      ) : (
        paragraphs.map((paragraph, idx) => (
          <p
            key={idx}
            className="mb-3 text-[14px] leading-[1.65]"
            style={{ color: "var(--ink-2)" }}
          >
            {renderInline(paragraph, onCite)}
          </p>
        ))
      )}
    </>
  );
}

/**
 * Inline rendering: replaces inline citation tokens with chip elements.
 * Tokens recognized:
 *   - `c_<id>` — already-resolved citation id
 *   - `Type:Identifier` where Type matches a FHIR resource name and Identifier
 *     contains no whitespace (e.g. `Observation:abc-123`)
 */
const CITATION_TOKEN = /(c_[A-Za-z0-9_-]+|(?:MedicationRequest|MedicationStatement|Medication|Condition|Observation|Encounter|Procedure|AllergyIntolerance|Immunization|DocumentReference|DiagnosticReport|ServiceRequest|Patient):[^\s,;\])]+)/g;

function renderInline(text: string, onCite: (id: string) => void): ReactNode {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  CITATION_TOKEN.lastIndex = 0;
  while ((match = CITATION_TOKEN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(<Chip key={`${match.index}`} token={match[0]} onCite={onCite} />);
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts.length === 0 ? text : parts;
}

function renderRichCell(cell: string, onCite: (id: string) => void): ReactNode {
  if (cell === "—" || cell === "") {
    return <span style={{ color: "var(--ink-4)" }}>—</span>;
  }
  // Risk-band shorthand: "!high:Hold ≥ 48 h" etc.
  if (cell.startsWith("!high:") || cell.startsWith("!mod:") || cell.startsWith("!low:")) {
    const sep = cell.indexOf(":");
    const tag = cell.slice(1, sep);
    const text = cell.slice(sep + 1);
    const tone =
      tag === "high"
        ? { color: "var(--critical)", fontWeight: 600 }
        : tag === "mod"
        ? { color: "var(--caution)", fontWeight: 500 }
        : { color: "var(--clear)" };
    return <span style={tone}>{text}</span>;
  }
  const inline = renderInline(cell, onCite);
  if (typeof inline === "string") {
    if (/^[\d.,/-]+(\s|$)/.test(inline)) {
      return (
        <span style={{ fontFamily: "var(--font-mono)", color: "var(--ink-2)" }}>{inline}</span>
      );
    }
    return <span style={{ color: "var(--ink-1)", fontWeight: 500 }}>{inline}</span>;
  }
  return inline;
}

function Chip({ token, onCite }: { token: string; onCite: (id: string) => void }) {
  const id = token;
  return (
    <span
      onClick={() => onCite(id)}
      className="mx-0.5 inline-flex cursor-pointer items-center gap-1 rounded-[4px] border px-1.5 align-baseline text-[11px] leading-[1.4] transition-colors hover:border-[var(--action-line)] hover:bg-[var(--action-tint)]"
      style={{
        background: "var(--surface-0)",
        borderColor: "var(--line-1)",
        color: "var(--action)",
        fontFamily: "var(--font-mono)",
      }}
    >
      {token}
    </span>
  );
}

function palettesFor(status: WorkflowBannerStatus) {
  switch (status) {
    case "clear":
    case "stable":
      return {
        tint: "var(--clear-tint, rgba(4,120,87,0.08))",
        line: "var(--clear-line, rgba(4,120,87,0.35))",
        accent: "var(--clear, #047857)",
        Icon: CheckCircle2,
      };
    case "hold":
    case "critical":
    case "deteriorating":
      return {
        tint: "var(--critical-tint, rgba(185,28,28,0.08))",
        line: "var(--critical-line, rgba(185,28,28,0.35))",
        accent: "var(--critical, #b91c1c)",
        Icon: ShieldAlert,
      };
    case "review":
    case "evolving":
    default:
      return {
        tint: "var(--caution-tint)",
        line: "var(--caution-line)",
        accent: "var(--caution)",
        Icon: AlertTriangle,
      };
  }
}

function formatTimestamp(value: string): string {
  try {
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return value;
    return dt.toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}
