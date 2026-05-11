import type { RendererProps } from "../types";

/**
 * Renders a markdown artifact stored in the run's canvas under
 * `canvas[tabId]` as `{ preview: string }`.
 */
export function MarkdownDocRenderer({ canvas, tabId }: RendererProps) {
  const artifact = (canvas[tabId] || canvas[`artifact:${tabId}`]) as { preview?: string } | undefined;
  const body = artifact?.preview ?? "_No content yet. Run a tool to populate this artifact._";

  // Minimal markdown rendering — paragraphs + h1/h2/h3 + list items.
  const lines = body.split("\n");

  return (
    <div className="mx-auto max-w-[780px] px-10 py-8" style={{ fontFamily: "var(--font-sans)" }}>
      {lines.map((raw, i) => {
        const line = raw.trimEnd();
        if (line.startsWith("# ")) {
          return (
            <h1
              key={i}
              className="mb-2 mt-3 text-[28px] font-semibold tracking-tight"
              style={{ fontFamily: "var(--font-serif)", color: "var(--ink-1)" }}
            >
              {line.slice(2)}
            </h1>
          );
        }
        if (line.startsWith("## ")) {
          return (
            <h2 key={i} className="mb-1 mt-5 text-[16.5px] font-semibold" style={{ color: "var(--ink-1)" }}>
              {line.slice(3)}
            </h2>
          );
        }
        if (line.startsWith("### ")) {
          return (
            <h3 key={i} className="mb-1 mt-3 text-[14px] font-semibold uppercase tracking-wider" style={{ color: "var(--ink-2)" }}>
              {line.slice(4)}
            </h3>
          );
        }
        if (line.startsWith("- ")) {
          return (
            <div key={i} className="ml-4 text-[13.5px] leading-[1.65]" style={{ color: "var(--ink-2)" }}>
              • {line.slice(2)}
            </div>
          );
        }
        if (!line) {
          return <div key={i} className="h-3" />;
        }
        if (line.startsWith("**") && line.endsWith("**")) {
          return (
            <div key={i} className="mt-1 text-[13px] font-semibold" style={{ color: "var(--ink-1)" }}>
              {line.slice(2, -2)}
            </div>
          );
        }
        return (
          <p key={i} className="my-1 text-[13.5px] leading-[1.65]" style={{ color: "var(--ink-2)" }}>
            {line}
          </p>
        );
      })}
    </div>
  );
}
