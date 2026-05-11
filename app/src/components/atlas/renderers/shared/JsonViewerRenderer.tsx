import type { RendererProps } from "../types";

/**
 * Renders the manifest (or any JSON payload) stored in canvas under
 * the tab id or `canvas.manifest` for the special `manifest.json` tab.
 */
export function JsonViewerRenderer({ canvas, tabId }: RendererProps) {
  const payload = canvas[tabId] ?? canvas.manifest ?? canvas;
  const text = JSON.stringify(payload, null, 2);
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
        {text}
      </pre>
    </div>
  );
}
