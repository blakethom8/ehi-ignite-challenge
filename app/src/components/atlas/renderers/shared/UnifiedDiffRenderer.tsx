import type { RendererProps } from "../types";

/** Pure projection of a stored diff payload. */
export function UnifiedDiffRenderer({ canvas, tabId }: RendererProps) {
  const diff = (canvas[tabId] || canvas.diff) as { hunks?: string } | undefined;
  return (
    <div className="mx-auto max-w-[920px] px-8 py-7">
      <pre
        className="overflow-auto rounded-md border p-4 text-[12px] leading-[1.55]"
        style={{
          background: "var(--surface-0)",
          borderColor: "var(--line-1)",
          color: "var(--ink-1)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {diff?.hunks ?? "_No diff available._"}
      </pre>
    </div>
  );
}
