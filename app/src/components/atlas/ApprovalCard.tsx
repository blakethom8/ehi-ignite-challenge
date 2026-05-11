import { AlertTriangle } from "lucide-react";

export type ApprovalCardProps = {
  /** Reason / body copy. */
  body: string;
  /** Title shown in caps above the body. Defaults to "APPROVAL REQUESTED". */
  title?: string;
  primary: { label: string; onClick?: () => void };
  secondary?: { label: string; onClick?: () => void };
};

/**
 * Caution-toned card the agent surfaces in chat when a controlled action
 * needs explicit clinician sign-off. Pairs with the workbench export gate.
 */
export function ApprovalCard({
  body,
  title = "APPROVAL REQUESTED",
  primary,
  secondary,
}: ApprovalCardProps) {
  return (
    <div
      className="mt-3 grid grid-cols-[18px_1fr] gap-2.5 rounded-[10px] border p-3.5"
      style={{
        background: "var(--caution-tint)",
        borderColor: "var(--caution-line)",
      }}
    >
      <AlertTriangle
        className="mt-0.5 h-4 w-4"
        strokeWidth={1.5}
        style={{ color: "var(--caution)" }}
      />
      <div>
        <div
          className="text-[12px] font-semibold tracking-wide"
          style={{ color: "var(--caution)" }}
        >
          {title}
        </div>
        <div
          className="mt-1 text-[12.5px] leading-[1.5]"
          style={{ color: "var(--ink-1)" }}
        >
          {body}
        </div>
        <div className="mt-2.5 flex gap-2">
          <button
            onClick={primary.onClick}
            className="h-[26px] rounded-md px-3 text-[12px] font-semibold text-white"
            style={{ background: "var(--ink-1)" }}
          >
            {primary.label}
          </button>
          {secondary && (
            <button
              onClick={secondary.onClick}
              className="h-[26px] rounded-md border px-3 text-[12px] font-semibold"
              style={{
                background: "var(--surface-0)",
                borderColor: "var(--line-2)",
                color: "var(--ink-2)",
              }}
            >
              {secondary.label}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
