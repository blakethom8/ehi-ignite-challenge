import { GitBranch } from "lucide-react";

export type ToolTraceProps = {
  tool: string;
  target: string;
};

/**
 * Tool-call indicator rendered above an agent message. Mono name, arrow,
 * mono target. Subtle surface so the message body stays primary.
 */
export function ToolTrace({ tool, target }: ToolTraceProps) {
  return (
    <div
      className="mb-2 flex items-center gap-2.5 rounded-md border px-3 py-2 text-[11.5px]"
      style={{
        background: "var(--surface-2)",
        borderColor: "var(--line-1)",
        color: "var(--ink-3)",
      }}
    >
      <GitBranch className="h-3 w-3" strokeWidth={1.5} />
      <span style={{ color: "var(--ink-2)", fontFamily: "var(--font-mono)" }}>
        {tool}
      </span>
      <span style={{ color: "var(--ink-4)" }}>→</span>
      <span style={{ color: "var(--action)", fontFamily: "var(--font-mono)" }}>
        {target}
      </span>
    </div>
  );
}
