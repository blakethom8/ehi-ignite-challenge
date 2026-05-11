import { CitationChip } from "./CitationChip";

export type EvidenceColumn<Row> = {
  id: keyof Row;
  header: string;
  mono?: boolean;
  align?: "left" | "right";
  /** Render the value as a clickable citation chip. */
  citation?: boolean;
  /** Render the value as a risk band: 'high' | 'mod' | 'low'. */
  risk?: boolean;
};

export type EvidenceTableProps<Row extends Record<string, unknown>> = {
  columns: EvidenceColumn<Row>[];
  rows: Row[];
  onCitationClick?: (id: string) => void;
  activeCitationId?: string | null;
};

/**
 * Dense, surgeon-readable table for medications, labs, comorbidities, etc.
 * Renders citation columns as chips, risk columns with color coding.
 */
export function EvidenceTable<Row extends Record<string, unknown>>({
  columns,
  rows,
  onCitationClick,
  activeCitationId,
}: EvidenceTableProps<Row>) {
  return (
    <table className="mb-2 w-full border-collapse text-[12.5px]">
      <thead>
        <tr style={{ borderBottom: "1px solid var(--line-1)" }}>
          {columns.map((c) => (
            <th
              key={String(c.id)}
              className={`px-2.5 py-2 ${c.align === "right" ? "text-right" : "text-left"} font-semibold uppercase tracking-wider`}
              style={{ color: "var(--ink-4)", fontSize: 10.5 }}
            >
              {c.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} style={{ borderBottom: "1px solid var(--line-1)" }}>
            {columns.map((c) => {
              const raw = row[c.id];
              return (
                <td
                  key={String(c.id)}
                  className={`px-2.5 py-2 align-top ${c.align === "right" ? "text-right" : ""}`}
                >
                  {renderCell(raw, c, onCitationClick, activeCitationId)}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function renderCell<Row>(
  value: unknown,
  col: EvidenceColumn<Row>,
  onCitationClick?: (id: string) => void,
  activeCitationId?: string | null,
): React.ReactNode {
  if (value == null) return null;
  const text = String(value);
  if (col.citation) {
    return (
      <CitationChip
        id={text}
        active={activeCitationId === text}
        onClick={onCitationClick}
      />
    );
  }
  if (col.risk) {
    const tone =
      text === "high"
        ? { color: "var(--critical)", fontWeight: 600 }
        : text === "mod"
        ? { color: "var(--caution)", fontWeight: 500 }
        : { color: "var(--clear)" };
    return <span style={tone as React.CSSProperties}>{text}</span>;
  }
  if (col.mono) {
    return (
      <span style={{ fontFamily: "var(--font-mono)", color: "var(--ink-2)" }}>
        {text}
      </span>
    );
  }
  return <span style={{ color: "var(--ink-1)", fontWeight: 500 }}>{text}</span>;
}
