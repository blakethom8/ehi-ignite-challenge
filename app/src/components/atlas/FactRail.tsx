export type FactRailCell = {
  label: string;
  value: string | number;
  /** Use the sans face instead of the default mono. */
  sans?: boolean;
  /** Render as a tier pill rather than a value string. */
  tier?: boolean;
};

export type FactRailProps = {
  cells: FactRailCell[];
};

/**
 * Five-cell horizontal strip of labelled stat values. Used at the top of
 * Caspian briefings under the disposition banner.
 */
export function FactRail({ cells }: FactRailProps) {
  return (
    <div
      className="my-5 grid overflow-hidden rounded-[10px] border"
      style={{
        background: "var(--surface-0)",
        borderColor: "var(--line-1)",
        gridTemplateColumns: `repeat(${cells.length}, 1fr)`,
      }}
    >
      {cells.map((c, i) => (
        <div
          key={i}
          className="border-r p-3.5 last:border-r-0"
          style={{ borderColor: "var(--line-1)" }}
        >
          <div
            className="text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: "var(--ink-4)" }}
          >
            {c.label}
          </div>
          {c.tier ? (
            <span
              className="mt-1 inline-block rounded-full px-1.5 py-px text-[10.5px]"
              style={{
                background: "var(--caution-tint)",
                color: "var(--caution)",
                fontFamily: "var(--font-sans)",
              }}
            >
              {c.value}
            </span>
          ) : (
            <div
              className="mt-1 text-[16px] font-semibold tracking-tight"
              style={{
                color: "var(--ink-1)",
                fontFamily: c.sans ? "var(--font-sans)" : "var(--font-mono)",
              }}
            >
              {c.value}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
